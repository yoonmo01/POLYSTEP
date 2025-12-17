# app/services/browser_service.py

import asyncio
import json
import logging
import inspect
import os
import re
import base64
import sys
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set, Tuple

import httpx
from dotenv import load_dotenv, find_dotenv

from browser_use import Agent, Browser, ChatGoogle

# ✅ (추가) JSON이 아닌 텍스트 최종결과(정책 못 찾음 등) 복구용 휴리스틱
_NOT_FOUND_HINTS = [
    "could not be found",
    "cannot be found",
    "not be found",
    "no matching data",
    "no data available",
    "자료가 없습니다",
    "조회된",
    "없습니다",
    # ✅ 한국어 실패/미발견 케이스(LLM이 자연어로 실패 요약할 때 대비)
    "찾을 수 없",         # 찾을 수 없었습니다/없음 등
    "발견하지 못",        # 발견하지 못했습니다
    "확인할 수 없",       # 확인할 수 없습니다
    "정보가 없",          # 정보가 없습니다
    "페이지가 비어",      # 페이지가 비어 있어
    "상세 정보를",        # 상세 정보를 담은 ... 발견하지 못했습니다 (같은 패턴)
]
_JUDGE_FAIL_HINTS = [
    "Judge Verdict: ❌ FAIL",
    "Failure Reason:",
    "⚖️  Judge Verdict",
]

# ✅ browser-use 버전에 따라 Controller가 없을 수 있음
try:
    from browser_use import Controller  # type: ignore
except Exception:
    Controller = None  # type: ignore

from app.utils.file_utils import ensure_download_dir
from app.models import Policy

logger = logging.getLogger(__name__)

# ✅ Windows에서 subprocess를 쓰는 라이브러리(browser-use/Playwright) 안전장치
_IS_WINDOWS = sys.platform.startswith("win")
_IS_LINUX = sys.platform.startswith("linux")

# (옵션) import 시점에도 policy를 한 번 세팅해둔다 (이미 생성된 loop에는 영향 없고, 새 loop에만 적용)
if _IS_WINDOWS:
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("[BrowserService] (import) set WindowsProactorEventLoopPolicy")
    except Exception as e:
        logger.warning("[BrowserService] (import) failed to set Proactor policy: %s", e)

# ✅ .env 로딩을 "확실하게"
_DOTENV_PATH = find_dotenv(".env", usecwd=True)
_DOTENV_OVERRIDE = os.getenv("DOTENV_OVERRIDE", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)
load_dotenv(_DOTENV_PATH, override=_DOTENV_OVERRIDE)
logger.info(
    "[BrowserService] dotenv loaded from: %s (override=%s)",
    _DOTENV_PATH or "(not found)",
    _DOTENV_OVERRIDE,
)

# WebSocket 쪽에서는 async 콜백을 쓸 수 있으니까 이렇게 타입 정의
AsyncLogCallback = Optional[Callable[[str], Awaitable[None]]]
AsyncScreenshotCallback = Optional[Callable[[str], Awaitable[None]]]

_SCREENSHOT_TIMEOUT_RE = re.compile(
    r"ScreenshotWatchdog\.on_ScreenshotEvent.*timed out", re.IGNORECASE
)
_DOMWATCHDOG_SCREENSHOT_FAIL_RE = re.compile(r"Clean screenshot failed", re.IGNORECASE)

# ✅ Browser 시작/런치(CDP) 타임아웃 계열 패턴 (이번 AWS 에러 대응)
_BROWSER_START_TIMEOUT_RE = re.compile(
    r"(BrowserStartEvent|BrowserLaunchEvent).*timed out|Cannot connect to host 127\.0\.0\.1:\d+|_wait_for_cdp_url",
    re.IGNORECASE,
)


def _is_browser_snapshot_timeout(e: Exception) -> bool:
    msg = f"{type(e).__name__}: {e}"
    return bool(
        _SCREENSHOT_TIMEOUT_RE.search(msg) or _DOMWATCHDOG_SCREENSHOT_FAIL_RE.search(msg)
    )


def _is_browser_start_timeout(e: Exception) -> bool:
    msg = f"{type(e).__name__}: {e}"
    return bool(_BROWSER_START_TIMEOUT_RE.search(msg))


def _normalize_url(raw: Optional[str]) -> str:
    """
    ✅ 정책/DB에 'www.xxx.com' 처럼 scheme 없는 URL이 들어오는 케이스 정규화.
    """
    s = (raw or "").strip()
    if not s:
        return ""
    s = s.replace(" ", "").replace("\n", "").replace("\r", "")
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    try:
        p = urlparse(s)
        if not p.netloc:
            return s
    except Exception:
        return s
    return s


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _build_kwargs_for_callable(fn: Any, desired: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ 라이브러리 버전 차이로 __init__ 시그니처가 달라도,
    실제로 받는 파라미터만 골라서 안전하게 kwargs를 구성한다.
    """
    try:
        sig = inspect.signature(fn)
        allowed = set(sig.parameters.keys())
        return {k: v for k, v in desired.items() if (k in allowed and v is not None)}
    except Exception:
        return {k: v for k, v in desired.items() if v is not None}


def _is_overload_error(e: Exception) -> bool:
    msg = f"{type(e).__name__}: {e}"
    return (
        ("503" in msg)
        or ("UNAVAILABLE" in msg)
        or ("overload" in msg.lower())
        or ("overloaded" in msg.lower())
    )


def _normalize_text_for_windows(text: str) -> str:
    return (text or "").replace("\u00a0", " ").replace("\u200b", " ").strip()


def _has_display() -> bool:
    """
    ✅ Linux 서버에서 headful 실행 가능 여부(대부분 DISPLAY 없음)
    """
    if not _IS_LINUX:
        return True
    disp = (os.getenv("DISPLAY", "") or "").strip()
    wayland = (os.getenv("WAYLAND_DISPLAY", "") or "").strip()
    return bool(disp or wayland)


def _should_force_headless(headless: bool) -> bool:
    """
    ✅ Linux + DISPLAY 없음이면 headless 강제
    """
    if _IS_LINUX and not _has_display():
        return True
    return headless


# ============================================================
# ✅ (추가) logging -> WebSocket(log_callback) 브릿지
# ============================================================
class _WSQueueLogHandler(logging.Handler):
    def __init__(self, loop: asyncio.AbstractEventLoop, q: "asyncio.Queue[str]"):
        super().__init__()
        self._loop = loop
        self._q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._loop.call_soon_threadsafe(self._q.put_nowait, msg)
        except Exception:
            pass


class _WSStream:
    def __init__(
        self, loop: asyncio.AbstractEventLoop, q: "asyncio.Queue[str]", prefix: str = ""
    ):
        self._loop = loop
        self._q = q
        self._prefix = prefix
        self._buf = ""

    def write(self, s: str) -> int:
        if not s:
            return 0
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = (self._prefix + line).strip()
            if line:
                self._loop.call_soon_threadsafe(self._q.put_nowait, line)
        return len(s)

    def flush(self) -> None:
        line = (self._prefix + (self._buf or "")).strip()
        if line:
            self._loop.call_soon_threadsafe(self._q.put_nowait, line)
        self._buf = ""

    @property
    def encoding(self) -> str:
        return "utf-8"

    @property
    def errors(self) -> str:
        return "replace"


# ============================================================
# ✅ (핵심) "파일 감시" 대신, Playwright 페이지를 직접 캡처해서 WS로 스트리밍
# ============================================================
def _is_page_like(obj: Any) -> bool:
    if obj is None:
        return False
    try:
        shot = getattr(obj, "screenshot", None)
        if callable(shot):
            if hasattr(obj, "goto") or hasattr(obj, "url") or hasattr(obj, "_url"):
                return True
    except Exception:
        return False
    return False


def _deep_find_page_like(root: Any, max_depth: int = 4, max_nodes: int = 400) -> Any:
    if root is None:
        return None

    seen: Set[int] = set()
    q: "deque[Tuple[Any, int]]" = deque([(root, 0)])
    n = 0

    while q and n < max_nodes:
        cur, depth = q.popleft()
        n += 1

        if cur is None:
            continue

        try:
            oid = id(cur)
            if oid in seen:
                continue
            seen.add(oid)
        except Exception:
            pass

        try:
            if _is_page_like(cur):
                return cur
        except Exception:
            pass

        if depth >= max_depth:
            continue

        if isinstance(cur, dict):
            for v in list(cur.values())[:60]:
                if v is not None:
                    q.append((v, depth + 1))
            continue

        if isinstance(cur, (list, tuple, set)):
            for v in list(cur)[:60]:
                if v is not None:
                    q.append((v, depth + 1))
            continue

        try:
            d = getattr(cur, "__dict__", None)
            if isinstance(d, dict):
                for _, v in list(d.items())[:120]:
                    if v is None:
                        continue
                    if isinstance(v, (str, int, float, bool, bytes)):
                        continue
                    q.append((v, depth + 1))
        except Exception:
            pass

        try:
            for name in dir(cur)[:120]:
                if name.startswith("__"):
                    continue
                if name in ("_loop", "_logger"):
                    continue
                try:
                    v = getattr(cur, name, None)
                except Exception:
                    continue
                if v is None:
                    continue
                if inspect.isfunction(v) or inspect.ismodule(v) or inspect.isclass(v):
                    continue
                if isinstance(v, (str, int, float, bool, bytes)):
                    continue
                q.append((v, depth + 1))
        except Exception:
            pass

    return None


def _try_get_playwright_page(browser: Any) -> Any:
    candidates = [
        ("page",),
        ("_page",),
        ("browser_session", "page"),
        ("browser_session", "_page"),
        ("_browser_session", "page"),
        ("_browser_session", "_page"),
        ("session", "page"),
        ("_session", "page"),
        ("manager", "page"),
        ("_manager", "page"),
        ("playwright_page",),
        ("_playwright_page",),
        ("_browser", "contexts"),
        ("_browser",),
        ("_context",),
        ("context",),
    ]

    for path in candidates:
        cur = browser
        ok = True
        for key in path:
            if cur is None:
                ok = False
                break
            cur = getattr(cur, key, None)

        if not ok or cur is None:
            continue

        try:
            if isinstance(cur, list) and cur:
                ctx = cur[-1]
                pages = getattr(ctx, "pages", None)
                if pages:
                    return pages[-1]
            if _is_page_like(cur):
                return cur
        except Exception:
            pass

    ctx = getattr(browser, "context", None) or getattr(browser, "_context", None)
    if ctx is not None:
        try:
            pages = getattr(ctx, "pages", None)
            if pages:
                return pages[-1]
        except Exception:
            pass

    try:
        found = _deep_find_page_like(browser, max_depth=4, max_nodes=400)
        if found is not None:
            return found
    except Exception:
        pass

    return None


async def _pump_live_screenshots(
    browser: Any,
    screenshot_callback: AsyncScreenshotCallback,
    log_callback: AsyncLogCallback = None,
    interval_sec: float = 0.5,
    jpeg_quality: int = 55,
    max_bytes: int = 900_000,
) -> None:
    if not screenshot_callback:
        return

    page = None
    last_warn = 0.0

    while True:
        try:
            if page is None:
                page = _try_get_playwright_page(browser)
                if page is None:
                    now = time.time()
                    if log_callback and (now - last_warn > 2.0):
                        await log_callback(
                            "⚠️ live screenshot: Playwright page를 아직 못 찾았습니다(재시도 중)..."
                        )
                        last_warn = now
                    await asyncio.sleep(0.2)
                    continue

            buf = await asyncio.wait_for(
                page.screenshot(type="jpeg", quality=jpeg_quality, full_page=False),
                timeout=6.0,
            )
            if buf and len(buf) <= max_bytes:
                b64 = base64.b64encode(buf).decode("utf-8")
                await screenshot_callback(b64)
            else:
                if log_callback and buf:
                    await log_callback(
                        f"⚠️ live screenshot too large, skip ({len(buf)} bytes)"
                    )

            await asyncio.sleep(interval_sec)

        except asyncio.CancelledError:
            return
        except asyncio.TimeoutError:
            page = None
            if log_callback:
                try:
                    await log_callback(
                        "⚠️ live screenshot timeout(재시도): page.screenshot timed out"
                    )
                except Exception:
                    pass
            await asyncio.sleep(0.4)
        except Exception as e:
            page = None
            if log_callback:
                try:
                    await log_callback(f"⚠️ live screenshot error(재시도): {e}")
                except Exception:
                    pass
            await asyncio.sleep(0.3)


# ============================================================
# ✅ HTML 이미지 URL 추출(기존 유지)
# ============================================================
_IMG_SRC_RE = re.compile(r"""<img[^>]+src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_OG_IMAGE_RE = re.compile(
    r"""<meta[^>]+property\s*=\s*["']og:image["'][^>]+content\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_A_HREF_RE = re.compile(r"""<a[^>]+href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_IMG_EXT_RE = re.compile(r"""\.(?:png|jpe?g|gif|webp)(?:\?.*)?$""", re.IGNORECASE)


def _dedup_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for x in items:
        s = (x or "").strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


async def _fetch_html(url: str, timeout_sec: float = 10.0) -> str:
    if not url:
        return ""
    url = _normalize_url(url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout_sec
        ) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return r.text or ""
    except Exception as e:
        logger.warning("[BrowserService] HTML fetch failed url=%s err=%s", url, e)
        return ""


def _extract_image_urls_from_html(html: str, base_url: str, limit: int = 30) -> List[str]:
    if not html:
        return []
    found: List[str] = []

    for m in _OG_IMAGE_RE.finditer(html):
        found.append(urljoin(base_url, (m.group(1) or "").strip()))

    for m in _IMG_SRC_RE.finditer(html):
        src = (m.group(1) or "").strip()
        if not src:
            continue
        if src.lower().startswith("data:"):
            continue
        found.append(urljoin(base_url, src))

    for m in _A_HREF_RE.finditer(html):
        href = (m.group(1) or "").strip()
        if not href:
            continue
        if href.lower().startswith("data:"):
            continue
        abs_url = urljoin(base_url, href)
        if _IMG_EXT_RE.search(abs_url):
            found.append(abs_url)

    found = _dedup_keep_order(found)
    return found[: max(0, limit)]


async def _enrich_image_urls_via_related_pages(
    entry_url: str,
    base_image_urls: List[str],
    max_image_urls: int = 30,
    max_related_pages: int = 3,
) -> List[str]:
    if not entry_url:
        return _dedup_keep_order(base_image_urls)[:max_image_urls]

    urls: List[str] = list(base_image_urls or [])

    html = await _fetch_html(entry_url, timeout_sec=10.0)
    urls.extend(_extract_image_urls_from_html(html, entry_url, limit=max_image_urls))

    candidates: List[str] = []
    for m in _A_HREF_RE.finditer(html or ""):
        href = (m.group(1) or "").strip()
        if not href:
            continue
        if href.lower().startswith("javascript:"):
            continue
        abs_url = urljoin(entry_url, href)

        if _IMG_EXT_RE.search(abs_url):
            candidates.append(abs_url)
            continue

        low = abs_url.lower()
        if any(
            k in low
            for k in (
                "amode=view",
                "view",
                "preview",
                "viewer",
                "attach",
                "download",
                "file",
                "atch",
                "origin",
            )
        ):
            candidates.append(abs_url)

    candidates = _dedup_keep_order(candidates)[: max_related_pages]

    for u in candidates:
        if _IMG_EXT_RE.search(u):
            urls.append(u)
            continue
        sub_html = await _fetch_html(u, timeout_sec=10.0)
        urls.extend(_extract_image_urls_from_html(sub_html, u, limit=max_image_urls))

    return _dedup_keep_order(urls)[:max_image_urls]


# ============================================================
# ✅ 후처리(Validation + Repair) 유틸 (기존 유지)
# ============================================================
_PHONE_RE = re.compile(r"(?:\+82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}")
_LIKELY_ADDRESS_RE = re.compile(
    r"(?:\b(?:도로|로|길)\s*\d+\b)|(?:\b\d+\s*번지\b)|(?:\b(?:읍|면|동|리)\b)|(?:\b(?:시|군|구)\b)"
)
_FILE_EXT_RE = re.compile(
    r".+\.(?:hwp|hwpx|pdf|docx?|xlsx?|pptx?|zip|png|jpg|jpeg)$", re.IGNORECASE
)
_AGE_HINT_RE = re.compile(
    r"(만\s*\d{1,2}\s*세\s*(?:이상|이하))"
    r"|(만\s*\d{1,2}\s*세\s*~\s*만\s*\d{1,2}\s*세)"
    r"|(\d{1,2}\s*세\s*(?:이상|이하))"
)
NONE_VALUES: Set[str] = {"없음", "없습니다", "해당 없음", "해당없음", "무관", "미해당", "-", "x", "X"}


def _norm_none_or_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _normalize_none_value(value: Any, default: str = "제한 없음") -> str:
    s = (_norm_none_or_str(value) or "").strip()
    if not s:
        return default
    if s.lower() in ("none", "n/a"):
        return default
    return default if s in NONE_VALUES else s


def _extract_field_line(evidence_text: str, field_name: str) -> Optional[str]:
    if not evidence_text:
        return None
    m = re.search(rf"{re.escape(field_name)}\s*\n\s*([^\n]+)", evidence_text)
    if m:
        return m.group(1).strip()
    m2 = re.search(rf"{re.escape(field_name)}\s*[:\-]?\s*([^\n]+)", evidence_text)
    if m2:
        return m2.group(1).strip()
    return None


def _merge_region_from_evidence(criteria_region: Optional[str], evidence_text: str) -> Optional[str]:
    ev = _extract_field_line(evidence_text, "지역기준")
    if not ev:
        return criteria_region
    cur = (criteria_region or "").strip()
    if not cur or _normalize_none_value(cur) == "제한 없음":
        return ev
    if ("상관없음" in ev) and ("상관없음" not in cur):
        return ev
    if ("|" in ev) and ("|" not in cur):
        return ev
    return criteria_region


def _clean_required_documents(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for raw in items:
        s = _norm_none_or_str(raw)
        if not s:
            continue
        if ("대표전화" in s) or ("대표 전화" in s) or ("전화" in s) or ("TEL" in s.upper()):
            if not _FILE_EXT_RE.match(s):
                continue
        if _PHONE_RE.search(s) and not _FILE_EXT_RE.match(s):
            continue
        if _LIKELY_ADDRESS_RE.search(s) and not _FILE_EXT_RE.match(s):
            continue
        if (
            _FILE_EXT_RE.match(s)
            or ("신청서" in s)
            or ("제출" in s)
            or ("서류" in s)
            or ("증명" in s)
            or ("공고" in s)
        ):
            out.append(s)

    dedup: List[str] = []
    seen: Set[str] = set()
    for x in out:
        if x not in seen:
            seen.add(x)
            dedup.append(x)
    return dedup


def _infer_age_from_evidence(evidence_text: str) -> Optional[str]:
    if not evidence_text:
        return None
    m = _AGE_HINT_RE.search(evidence_text)
    return m.group(0).strip() if m else None


def _normalize_apply_channel(v: Any) -> Optional[str]:
    s = _norm_none_or_str(v)
    if not s:
        return None
    s2 = s.replace(" ", "")
    has_online = "온라인" in s2
    has_visit = "방문" in s2
    has_mail = "우편" in s2
    kinds = sum([has_online, has_visit, has_mail])
    if kinds >= 2:
        return "혼합"
    if has_online:
        return "온라인"
    if has_visit:
        return "방문"
    if has_mail:
        return "우편"
    return s


def _clean_documents(result: Dict[str, Any]) -> Dict[str, Any]:
    result["required_documents"] = _clean_required_documents(result.get("required_documents"))
    return result


def _fix_criteria_mapping(result: Dict[str, Any]) -> Dict[str, Any]:
    criteria = result.get("criteria") or {}
    if not isinstance(criteria, dict):
        criteria = {}
    evidence = _norm_none_or_str(result.get("evidence_text")) or ""

    age = _norm_none_or_str(criteria.get("age"))
    region = _norm_none_or_str(criteria.get("region"))

    if age and (("거주" in age) or ("관외" in age) or ("지역" in age) or ("주소" in age)):
        if not region or _normalize_none_value(region) == "제한 없음":
            criteria["region"] = age
        criteria["age"] = "제한 없음"

    inferred_age = _infer_age_from_evidence(evidence)
    if inferred_age:
        cur_age = _norm_none_or_str(criteria.get("age"))
        if not cur_age or _normalize_none_value(cur_age) == "제한 없음":
            criteria["age"] = inferred_age

    merged_region = _merge_region_from_evidence(_norm_none_or_str(criteria.get("region")), evidence)
    if merged_region:
        criteria["region"] = merged_region.strip()

    criteria["age"] = _normalize_none_value(criteria.get("age"))
    criteria["region"] = _normalize_none_value(criteria.get("region"))
    criteria["income"] = _normalize_none_value(criteria.get("income"))
    criteria["employment"] = _normalize_none_value(criteria.get("employment"))
    criteria["other"] = _normalize_none_value(criteria.get("other"), default="없음")

    result["criteria"] = criteria
    return result


def _normalize_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    result["apply_channel"] = _normalize_apply_channel(result.get("apply_channel"))
    return result


def _enrich_contact(result: Dict[str, Any]) -> Dict[str, Any]:
    evidence = _norm_none_or_str(result.get("evidence_text")) or ""
    contact = result.get("contact") or {}
    if not isinstance(contact, dict):
        contact = {}
    if not _norm_none_or_str(contact.get("tel")):
        m = _PHONE_RE.search(evidence)
        if m:
            contact["tel"] = m.group(0)
    result["contact"] = contact
    return result


def _repair_result(result: Dict[str, Any]) -> Dict[str, Any]:
    result = _clean_documents(result)
    result = _fix_criteria_mapping(result)
    result = _normalize_fields(result)
    result = _enrich_contact(result)
    return result


def _list_files_safe(dirpath: str) -> Set[str]:
    try:
        return set(os.listdir(dirpath))
    except Exception:
        return set()


class BrowserService:
    """
    browser-use + Gemini를 사용해서
    실제 브라우저를 돌려 정책 자격 요건을 검증하는 서비스.
    """

    @staticmethod
    async def _run_agent(
        task: str,
        entry_url: Optional[str] = None,
        log_callback: AsyncLogCallback = None,
        screenshot_callback: AsyncScreenshotCallback = None,
    ) -> Dict[str, Any]:
        # ✅ 이벤트루프/정책 확인(디버깅용)
        try:
            policy_name = type(asyncio.get_event_loop_policy()).__name__
            logger.info("[BrowserService] EVENT LOOP POLICY = %s", policy_name)
            if log_callback:
                await log_callback(f"EVENT LOOP POLICY = {policy_name}")
        except Exception as e:
            logger.info("[BrowserService] event loop policy check failed: %s", e)

        loop = None
        loop_name = "(unknown)"
        try:
            loop = asyncio.get_running_loop()
            loop_name = type(loop).__name__
            logger.info("[BrowserService] RUNNING LOOP = %s", loop_name)
            if log_callback:
                await log_callback(f"RUNNING LOOP = {loop_name}")
        except Exception as e:
            logger.info("[BrowserService] running loop check failed: %s", e)

        # ============================================================
        # ✅ Windows + Selector loop이면: browser-use를 별도 스레드(Proactor)로 우회
        # ============================================================
        if _IS_WINDOWS and "SelectorEventLoop" in (loop_name or ""):
            main_loop = loop  # type: ignore[assignment]

            async def _call_log(msg: str) -> None:
                if not log_callback:
                    return
                fut = asyncio.run_coroutine_threadsafe(log_callback(msg), main_loop)  # type: ignore[arg-type]
                await asyncio.wrap_future(fut)

            async def _call_shot(b64: str) -> None:
                if not screenshot_callback:
                    return
                fut = asyncio.run_coroutine_threadsafe(screenshot_callback(b64), main_loop)  # type: ignore[arg-type]
                await asyncio.wrap_future(fut)

            if log_callback:
                await log_callback(
                    "⚠️ Windows Selector loop 감지: browser-use 실행을 별도 스레드(Proactor loop)로 우회합니다."
                )

            async def _agent_core() -> Dict[str, Any]:
                return await BrowserService._run_agent(
                    task=task,
                    entry_url=entry_url,
                    log_callback=_call_log,
                    screenshot_callback=_call_shot,
                )

            def _thread_entry() -> Dict[str, Any]:
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                except Exception:
                    pass
                return asyncio.run(_agent_core())

            return await asyncio.to_thread(_thread_entry)

        # ============================================================
        # ✅ URL 정규화
        # ============================================================
        if entry_url:
            entry_url = _normalize_url(entry_url)
        if log_callback and entry_url:
            await log_callback(f"시작 URL 정규화: {entry_url}")
        if log_callback:
            await log_callback("브라우저 세션 준비 중...")

        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        downloads_dir = ensure_download_dir()
        logger.info("[BrowserService] Using downloads_dir=%s", downloads_dir)

        # ============================================================
        # ✅ 서버 안정성: Linux 서버에서 DISPLAY 없으면 headless 강제
        # ============================================================
        headless_env = _env_flag("BROWSER_HEADLESS", "true")
        headless = _should_force_headless(headless_env)

        # keep_open: 서버에선 기본 false가 안정적. (env로만 true 권장)
        keep_open_default = "false" if _IS_LINUX else "false"
        keep_open = _env_flag("BROWSER_KEEP_OPEN", keep_open_default)
        if _IS_LINUX and keep_open:
            logger.warning("[BrowserService] BROWSER_KEEP_OPEN=true on Linux server is not recommended (may leak processes).")
            if log_callback:
                await log_callback("⚠️ 서버(Linux)에서는 BROWSER_KEEP_OPEN=true 비추천(크롬 프로세스 누수 위험). false 권장")
        debug_ui = _env_flag("BROWSER_DEBUG_UI", "false")
        slowmo_ms = _env_int("BROWSER_SLOWMO_MS", 0 if _IS_LINUX else 250)

        collect_images = _env_flag("BROWSER_COLLECT_IMAGE_URLS", "true")
        max_image_urls = _env_int("BROWSER_MAX_IMAGE_URLS", 30)
        follow_related = _env_flag("BROWSER_IMAGE_FOLLOW_RELATED_PAGES", "true")
        max_related_pages = _env_int("BROWSER_IMAGE_MAX_RELATED_PAGES", 3)

        max_snapshot_failures = _env_int("BROWSER_MAX_SNAPSHOT_FAILURES", 2)
        snapshot_failures = 0

        max_actions = _env_int("BROWSER_AGENT_MAX_ACTIONS", 20)
        max_time_sec = float(os.getenv("BROWSER_MAX_TIME_SEC", os.getenv("BROWSER_AGENT_MAX_TIME_SEC", "300")))

        chromium_sandbox = _env_flag("BROWSER_CHROMIUM_SANDBOX", "false")

        allowed_domains_raw = (os.getenv("BROWSER_ALLOWED_DOMAINS", "") or "").strip()
        allowed_domains = [d.strip() for d in allowed_domains_raw.split(",") if d.strip()] or None

        # debug_ui는 로컬에서만 의미가 있고, 서버에선 DISPLAY 없어서 깨짐 → 무시(혹은 headless 강제 유지)
        if debug_ui and _has_display():
            headless = False
            keep_open = True
            slowmo_ms = max(slowmo_ms, 150)
        elif debug_ui and not _has_display():
            if log_callback:
                await log_callback("⚠️ DEBUG_UI가 켜져있지만 서버에 DISPLAY가 없어 headless로 강제합니다.")
            headless = True

        max_retries = int(os.getenv("BROWSER_LLM_MAX_RETRIES", "3"))
        base_backoff = float(os.getenv("BROWSER_LLM_BACKOFF_SEC", "2.0"))

        logger.info(
            "[BrowserService] headless=%s keep_open=%s max_retries=%s backoff=%s max_actions=%s max_time=%s allowed_domains=%s",
            headless,
            keep_open,
            max_retries,
            base_backoff,
            max_actions,
            max_time_sec,
            allowed_domains or "(none)",
        )
        if log_callback and _IS_LINUX:
            await log_callback(f"🐧 Linux detected: DISPLAY={'yes' if _has_display() else 'no'} → headless={headless}")

        # ============================================================
        # ✅ Browser 생성 함수 (실패 시 fallback/retry 용)
        # ============================================================
        async def _create_browser(headless_value: bool) -> Any:
            try:
                default_pw_chrome = "/home/ubuntu/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome"
                browser_exec_path = (os.getenv("BROWSER_EXECUTABLE_PATH", "") or "").strip() or default_pw_chrome

                server_args = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--disable-features=TranslateUI",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-breakpad",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]

                desired_kwargs: Dict[str, Any] = {
                    "headless": headless_value,
                    "downloads_path": downloads_dir,
                    "slow_mo": slowmo_ms if slowmo_ms > 0 else None,
                    "executable_path": browser_exec_path,
                    "args": server_args,
                    "chromium_sandbox": chromium_sandbox,
                    "keep_alive": keep_open,
                }

                init_kwargs = _build_kwargs_for_callable(Browser.__init__, desired_kwargs)
                b = Browser(**init_kwargs)

                logger.info("[BrowserService] Using browser executable: %s", browser_exec_path)
                if log_callback:
                    await log_callback(f"✅ browser executable_path: {browser_exec_path}")
                    await log_callback(f"✅ headless={headless_value} chromium_sandbox={chromium_sandbox} keep_alive={keep_open}")
                return b
            except Exception as e:
                logger.warning("[BrowserService] Browser init fallback due to: %s", e)
                if log_callback:
                    await log_callback(f"⚠️ Browser init fallback: {e}")
                try:
                    return Browser(headless=headless_value, downloads_path=downloads_dir)
                except Exception:
                    return Browser(headless=headless_value)

        browser = await _create_browser(headless)

        llm = ChatGoogle(model="gemini-2.5-pro")

        controller = None
        if Controller is not None:
            try:
                controller = Controller(use_web_search=False)  # type: ignore[call-arg]
            except Exception:
                controller = None

        agent_kwargs: Dict[str, Any] = dict(
            task=_normalize_text_for_windows(task),
            llm=llm,
            browser=browser,
        )
        if controller is not None:
            agent_kwargs["controller"] = controller

        agent_kwargs["max_actions"] = max_actions
        agent_kwargs["max_time"] = max_time_sec
        if allowed_domains:
            agent_kwargs["allowed_domains"] = allowed_domains

        try:
            agent = Agent(**agent_kwargs)
        except TypeError:
            agent = Agent(task=_normalize_text_for_windows(task), llm=llm, browser=browser)

        run_started_at = datetime.now(timezone.utc)
        pre_files = _list_files_safe(downloads_dir)

        if log_callback:
            await log_callback("에이전트 실행 시작...")

        # ============================================================
        # ✅ (추가) Agent/BrowserSession/tools 로그를 WS로 스트리밍
        # ============================================================
        ws_log_queue: "asyncio.Queue[str]" = asyncio.Queue()
        ws_log_handler: Optional[_WSQueueLogHandler] = None
        ws_log_pump_task: Optional[asyncio.Task] = None
        old_stdout: Optional[Any] = None
        old_stderr: Optional[Any] = None
        attached_logger_names: List[str] = []
        saved_logger_handlers: Dict[str, List[logging.Handler]] = {}
        saved_logger_propagate: Dict[str, bool] = {}

        def _make_console_single_source(logger_names: List[str]) -> None:
            for lname in logger_names:
                lg = logging.getLogger(lname)
                saved_logger_handlers[lname] = list(lg.handlers)
                saved_logger_propagate[lname] = bool(lg.propagate)
                lg.handlers = []
                lg.propagate = True

        async def _pump_ws_logs() -> None:
            if not log_callback:
                return
            while True:
                try:
                    line = await ws_log_queue.get()
                    await log_callback(line)
                except asyncio.CancelledError:
                    return
                except Exception:
                    await asyncio.sleep(0.05)

        if log_callback:
            try:
                loop2 = asyncio.get_running_loop()
                ws_log_handler = _WSQueueLogHandler(loop2, ws_log_queue)
                ws_log_handler.setLevel(logging.INFO)
                ws_log_handler.setFormatter(logging.Formatter("%(message)s"))

                attach_root = _env_flag("BROWSER_WS_ATTACH_ROOT_LOGGER", "true")
                capture_stdio = _env_flag("BROWSER_WS_CAPTURE_STDIO", "false")

                lib_logger_names = [
                    "Agent",
                    "BrowserSession",
                    "tools",
                    "cdp_use.client",
                    "browser_use",
                    "browser_use.agent",
                    "browser_use.browser",
                    "cdp_use",
                    "bubus",
                ]
                if _env_flag("BROWSER_CONSOLE_DEDUP", "true"):
                    _make_console_single_source(lib_logger_names)

                target_logger_names = [""] if attach_root else (lib_logger_names + ["app.services.browser_service"])

                for lname in target_logger_names:
                    lg = logging.getLogger(lname)
                    lg.addHandler(ws_log_handler)
                    lg.propagate = True
                    if lg.level == 0 or lg.level > logging.INFO:
                        lg.setLevel(logging.INFO)
                    attached_logger_names.append(lname)

                ws_log_pump_task = asyncio.create_task(_pump_ws_logs())
                if capture_stdio:
                    try:
                        old_stdout = sys.stdout
                        old_stderr = sys.stderr
                        sys.stdout = _WSStream(loop2, ws_log_queue, prefix="")
                        sys.stderr = _WSStream(loop2, ws_log_queue, prefix="[stderr] ")
                    except Exception as e:
                        await log_callback(f"⚠️ stdout/stderr 캡처 설정 실패: {e}")
            except Exception as e:
                await log_callback(f"⚠️ WS 로그 브릿지 설정 실패: {e}")

        # ============================================================
        # ✅ agent.run() (BrowserStart/CDP 실패 시 headless로 1회 자동 재시도)
        # ============================================================
        history = None
        last_err: Optional[Exception] = None

        screenshot_task_live: Optional[asyncio.Task] = None
        if screenshot_callback:
            interval_sec = float(os.getenv("BROWSER_LIVE_SHOT_INTERVAL_SEC", "0.5"))
            jpeg_quality = int(os.getenv("BROWSER_LIVE_SHOT_JPEG_QUALITY", "55"))
            max_bytes = int(os.getenv("BROWSER_LIVE_SHOT_MAX_BYTES", "900000"))
            screenshot_task_live = asyncio.create_task(
                _pump_live_screenshots(
                    browser=browser,
                    screenshot_callback=screenshot_callback,
                    log_callback=log_callback,
                    interval_sec=interval_sec,
                    jpeg_quality=jpeg_quality,
                    max_bytes=max_bytes,
                )
            )
            if log_callback:
                await log_callback(
                    f"[live-shot] enabled interval={interval_sec}s quality={jpeg_quality} max_bytes={max_bytes}"
                )

        async def _stop_live_shot() -> None:
            nonlocal screenshot_task_live
            if screenshot_task_live:
                screenshot_task_live.cancel()
                try:
                    await screenshot_task_live
                except Exception:
                    pass
                screenshot_task_live = None

        try:
            for attempt in range(0, max_retries + 1):
                try:
                    if attempt > 0 and log_callback:
                        await log_callback(f"LLM 오버로드 재시도 중... (attempt={attempt}/{max_retries})")

                    history = await asyncio.wait_for(agent.run(), timeout=max_time_sec)
                    if history is None:
                        raise RuntimeError("Agent returned None")

                    last_err = None
                    break
                except Exception as e:
                    # ✅ screenshot/DOM watchdog timeout
                    if _is_browser_snapshot_timeout(e):
                        snapshot_failures += 1
                        logger.warning(
                            "[BrowserService] snapshot timeout detected (%s/%s): %s",
                            snapshot_failures,
                            max_snapshot_failures,
                            e,
                        )
                        if snapshot_failures >= max_snapshot_failures:
                            await _stop_live_shot()
                            return {
                                "matched": None,
                                "matched_title": None,
                                "source_url": entry_url,
                                "criteria": {},
                                "required_documents": [],
                                "apply_steps": [],
                                "apply_channel": None,
                                "apply_period": None,
                                "contact": {},
                                "evidence_text": "",
                                "navigation_path": [],
                                "error_message": "Browser snapshot (screenshot/DOM) timeouts occurred repeatedly. Manual review needed.",
                                "downloaded_files": [],
                                "downloads_dir": downloads_dir,
                                "image_urls": [],
                                "confidence": 0.0,
                                "needs_review": True,
                            }

                    # ✅ AWS에서 터진 케이스: BrowserStart/CDP 포트 연결 실패 → headless 재시도
                    if _IS_LINUX and (not headless) and _is_browser_start_timeout(e):
                        if log_callback:
                            await log_callback("⚠️ BrowserStart/CDP 실패 감지: 서버에서 headful 실행이 불안정 → headless로 1회 재시도합니다.")
                        try:
                            await _stop_live_shot()
                            try:
                                await browser.close()  # type: ignore[attr-defined]
                            except Exception:
                                pass

                            headless = True
                            browser = await _create_browser(headless)
                            agent_kwargs["browser"] = browser

                            try:
                                agent = Agent(**agent_kwargs)
                            except TypeError:
                                agent = Agent(task=_normalize_text_for_windows(task), llm=llm, browser=browser)

                            if screenshot_callback:
                                interval_sec = float(os.getenv("BROWSER_LIVE_SHOT_INTERVAL_SEC", "0.5"))
                                jpeg_quality = int(os.getenv("BROWSER_LIVE_SHOT_JPEG_QUALITY", "55"))
                                max_bytes = int(os.getenv("BROWSER_LIVE_SHOT_MAX_BYTES", "900000"))
                                screenshot_task_live = asyncio.create_task(
                                    _pump_live_screenshots(
                                        browser=browser,
                                        screenshot_callback=screenshot_callback,
                                        log_callback=log_callback,
                                        interval_sec=interval_sec,
                                        jpeg_quality=jpeg_quality,
                                        max_bytes=max_bytes,
                                    )
                                )
                            # ✅ 재시도는 한 번만
                            continue
                        except Exception as e2:
                            if log_callback:
                                await log_callback(f"❌ headless 재시도 준비 중 실패: {e2}")

                    last_err = e
                    if _is_overload_error(e) and attempt < max_retries:
                        sleep_s = base_backoff * (2 ** attempt)
                        logger.warning("[BrowserService] LLM overload detected. retry in %.1fs: %s", sleep_s, e)
                        await asyncio.sleep(sleep_s)
                        continue
                    raise

            await _stop_live_shot()

            if history is None:
                raise last_err or RuntimeError("Agent run failed with unknown error")

        except asyncio.TimeoutError as e:
            logger.error("[BrowserService] Agent timeout (%.1fs): %s", max_time_sec, e)
            return {
                "matched": None,
                "matched_title": None,
                "source_url": entry_url,
                "criteria": {},
                "required_documents": [],
                "apply_steps": [],
                "apply_channel": None,
                "apply_period": None,
                "contact": {},
                "evidence_text": "",
                "navigation_path": [],
                "navigation_path_warning": "Agent timed out before producing navigation 기록",
                "error_message": f"Agent exceeded {max_time_sec:.0f}s timeout",
                "downloaded_files": [],
                "downloads_dir": downloads_dir,
                "image_urls": [],
                "confidence": 0.0,
                "needs_review": True,
            }
        except Exception as e:
            logger.exception("[BrowserService] Agent failed: %s", e)
            return {
                "matched": None,
                "matched_title": None,
                "source_url": entry_url,
                "criteria": {},
                "required_documents": [],
                "apply_steps": [],
                "apply_channel": None,
                "apply_period": None,
                "contact": {},
                "evidence_text": "",
                "navigation_path": [],
                "navigation_path_warning": "Agent failed before producing navigation 기록",
                "error_message": f"Agent execution failed: {str(e)}",
                "downloaded_files": [],
                "downloads_dir": downloads_dir,
                "image_urls": [],
                "confidence": 0.0,
                "needs_review": True,
            }
        finally:
            # ✅ (추가) WS 로그 브릿지 정리
            try:
                if old_stdout is not None:
                    try:
                        sys.stdout.flush()
                    except Exception:
                        pass
                    sys.stdout = old_stdout
                if old_stderr is not None:
                    try:
                        sys.stderr.flush()
                    except Exception:
                        pass
                    sys.stderr = old_stderr
            except Exception:
                pass

            if ws_log_pump_task:
                ws_log_pump_task.cancel()
                try:
                    await ws_log_pump_task
                except Exception:
                    pass

            if ws_log_handler:
                for lname in attached_logger_names:
                    try:
                        logging.getLogger(lname).removeHandler(ws_log_handler)
                    except Exception:
                        pass
                try:
                    ws_log_handler.close()
                except Exception:
                    pass

            if saved_logger_handlers:
                for lname, handlers in saved_logger_handlers.items():
                    try:
                        lg = logging.getLogger(lname)
                        lg.handlers = handlers
                        lg.propagate = saved_logger_propagate.get(lname, True)
                    except Exception:
                        pass

            if not keep_open:
                try:
                    await browser.close()  # type: ignore[attr-defined]
                except Exception:
                    pass

        # ============================================================
        # ✅ 다운로드 파일 리스트
        # ============================================================
        post_files = _list_files_safe(downloads_dir)
        new_files = sorted(list(post_files - pre_files))

        downloaded_files: List[str] = []
        for fn in new_files:
            full = os.path.join(downloads_dir, fn)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(full), tz=timezone.utc)
                if mtime >= run_started_at:
                    downloaded_files.append(fn)
                else:
                    downloaded_files.append(fn)
            except Exception:
                downloaded_files.append(fn)

        if log_callback:
            await log_callback("에이전트 실행 완료, 결과 파싱 중...")

        try:
            final_text = history.final_result()  # type: ignore[attr-defined]
        except Exception:
            final_text = str(history)

        final_text = _normalize_text_for_windows(final_text)
        logger.info("[BrowserService] final_result text snippet: %s", final_text[:500])

        parsed = BrowserService._safe_json_loads(final_text)

        if "raw" in parsed and not isinstance(parsed.get("matched"), (bool, str)):
            parsed = {
                "matched": None,
                "matched_title": None,
                "source_url": None,
                "criteria": {},
                "required_documents": [],
                "apply_steps": [],
                "apply_channel": None,
                "apply_period": None,
                "contact": {},
                "evidence_text": final_text,
                "navigation_path": [],
                "error_message": "JSON parsing failed - manual review needed. raw text stored in evidence_text.",
                "image_urls": [],
                "confidence": 0.0,
                "needs_review": True,
            }

        result: Dict[str, Any] = {
            "matched": parsed.get("matched") if "matched" in parsed else None,
            "matched_title": parsed.get("matched_title"),
            "source_url": parsed.get("source_url")
            or parsed.get("final_url")
            or parsed.get("url")
            or entry_url
            or None,
            "criteria": parsed.get("criteria") or {},
            "required_documents": parsed.get("required_documents") or [],
            "apply_steps": parsed.get("apply_steps") or [],
            "apply_channel": parsed.get("apply_channel"),
            "apply_period": parsed.get("apply_period"),
            "contact": parsed.get("contact") or {},
            "evidence_text": parsed.get("evidence_text") or parsed.get("evidence") or final_text,
            "navigation_path": parsed.get("navigation_path") or [],
            "error_message": parsed.get("error_message"),
            "downloaded_files": downloaded_files,
            "downloads_dir": downloads_dir,
            "image_urls": parsed.get("image_urls") or [],
            "confidence": float(parsed.get("confidence") or 0.0),
            "needs_review": bool(parsed.get("needs_review")) if "needs_review" in parsed else False,
        }

        if not isinstance(result["navigation_path"], list):
            result["navigation_path"] = []
        if len(result["navigation_path"]) == 0:
            result["navigation_path_warning"] = "Agent did not record any navigation_path (empty list)"
            if entry_url:
                result["navigation_path"] = [{"action": "open", "label": "start", "url": entry_url, "note": "entry"}]

        result = _repair_result(result)

        try:
            if collect_images:
                cur = result.get("image_urls")
                if not isinstance(cur, list):
                    cur = []
                cur = [str(x).strip() for x in cur if str(x).strip()]

                html_url = _norm_none_or_str(result.get("source_url")) or entry_url or ""
                if html_url:
                    if log_callback:
                        await log_callback("이미지 URL 수집(URL 방식: HTML 파싱) 시도 중...")

                    if follow_related:
                        result["image_urls"] = await _enrich_image_urls_via_related_pages(
                            entry_url=_normalize_url(html_url),
                            base_image_urls=cur,
                            max_image_urls=max_image_urls,
                            max_related_pages=max_related_pages,
                        )
                    else:
                        html_url2 = _normalize_url(html_url)
                        html = await _fetch_html(html_url2, timeout_sec=10.0)
                        merged = cur + _extract_image_urls_from_html(html, html_url2, limit=max_image_urls)
                        result["image_urls"] = _dedup_keep_order(merged)[:max_image_urls]
                else:
                    result["image_urls"] = _dedup_keep_order(cur)[:max_image_urls]
        except Exception as e:
            logger.warning("[BrowserService] image url enrichment failed: %s", e)

        if result.get("required_documents") and not result.get("downloaded_files"):
            result["error_message"] = (
                (result.get("error_message") or "")
                + " NOTE: required_documents에 파일명이 있어도 실제 다운로드는 수행되지 않았을 수 있습니다."
            ).strip()

        return result

    @staticmethod
    def _safe_json_loads(text: str) -> Dict[str, Any]:
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {"raw": text}
        except Exception:
            pass

        low = (text or "").lower()
        if any(h in low for h in _NOT_FOUND_HINTS) or any(h.lower() in low for h in _JUDGE_FAIL_HINTS):
            return {
                "matched": False,
                "matched_title": None,
                "source_url": None,
                "criteria": {
                    "age": "제한 없음",
                    "region": "제한 없음",
                    "income": "제한 없음",
                    "employment": "제한 없음",
                    "other": "없음",
                },
                "required_documents": [],
                "apply_steps": [],
                "apply_channel": None,
                "apply_period": None,
                "contact": {},
                "contact": {"org": "", "tel": "", "site": ""},
                "evidence_text": text,
                "navigation_path": [],
                "error_message": "POLICY_NOT_FOUND",
                "image_urls": [],
                "confidence": 0.0,
                "needs_review": False,
            }

        m = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
        if m:
            candidate = m.group(1)
            try:
                obj = json.loads(candidate)
                return obj if isinstance(obj, dict) else {"raw": text}
            except Exception:
                pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                obj = json.loads(candidate)
                return obj if isinstance(obj, dict) else {"raw": text}
            except Exception:
                pass

        return {"raw": text}

    @staticmethod
    async def verify_policy_with_agent(
        policy: Policy,
        log_callback: AsyncLogCallback = None,
        screenshot_callback: AsyncScreenshotCallback = None,
    ) -> Dict[str, Any]:
        title = policy.title or ""
        url = _normalize_url(policy.target_url or "")
        if not url:
            raise ValueError("policy.target_url is empty")
        if log_callback:
            await log_callback(f"정규화된 target_url: {url}")

        anti_loop_rules = """
✅ 실패/루프 방지 규칙(매우 중요):
- 같은 유형의 행동(예: 스크롤만 반복, 같은 메뉴 클릭, 드롭다운 선택)을 2번 연속 실패하면 즉시 중단하고 다른 전략으로 전환한다.
- 페이지 하단의 'Family Site' / 외부 이동용 드롭다운(<select>)은 사용하지 마라. (timeout을 유발하고 정책 검색에 도움되지 않음)
- 정책을 찾기 위해서는 반드시 '사이트 내부 검색창/통합검색/공지/게시판/과정검색' 등 내부 기능만 사용해라.
- 5번 이상 스크롤해도 정책 단서(정책명/공고명/상세링크/검색창)가 안 보이면, 상단 메뉴로 이동해 다른 메뉴(공지/모집/과정검색 등)를 탐색한다.
- 10번 액션(클릭/검색/스크롤 포함) 안에 정책 단서를 못 찾으면 matched=false로 종료한다.
        """.strip()

        stop_after_extract_rules = """
✅ 종료 규칙(매우 중요):
- '이용안내/소개/가이드' 페이지라도, 도민리포터(청년 리포터) 모집/운영/선발/지원 관련 정보가 확인되면 그 페이지를 '최선의 공식 안내'로 간주하고 더 탐색하지 말고 즉시 JSON을 완성해 종료해라.
- extract(페이지 텍스트 추출)를 한 번 성공했고, 그 텍스트에 아래 중 2개 이상이 포함되면 종료해라:
  1) 도민리포터 또는 청년 리포터
  2) 모집/선발/운영/활동/지원/신청/접수 중 하나 이상
  3) 문의/담당/연락처/전화 중 하나 이상
- 위 조건을 만족하지 못하면 계속 탐색하되, 후보 페이지는 최대 5개까지만 열어라.
        """.strip()

        task = f"""
너는 대한민국 청년정책을 분석하는 전문 에이전트야.

아래 정책의 공식 안내 페이지에 접속해서,
특히 '지원대상', '신청자격', '선정기준', '신청방법', '제출서류', '접수처/문의'를 찾아서 정리해야 한다.

- 정책 제목: {title}
- 접속해야 할 URL: {url}

🚫 절대 규칙(외부 검색 금지):
- DuckDuckGo/Google/Bing/Naver 등 "외부 검색엔진" 사용 금지.
- 사이트 내부에서만 탐색/검색/메뉴 이동으로 해결해라.
- 외부 검색이 필요해 보이면, 사이트의 "통합검색/검색/공지/게시판" 같은 내부 메뉴를 대신 찾아라.

✅ 가장 중요한 규칙(정책 일치 검증):
- 지금 보고 있는 페이지의 정책명/공고명/제목이 '{title}'과 일치(또는 매우 유사)해야만 추출한다.
- 일치하지 않으면 그 페이지에서 추출하지 말고, 뒤로가기/검색/다음 결과로 이동해서 다시 시도한다.
- 최대 5개의 후보 페이지(검색 결과/상세)를 열어보고, 가장 잘 맞는 1개를 선택한다.
- 결국 맞는 정책을 못 찾으면 matched=false로 반환한다.

{anti_loop_rules}

{stop_after_extract_rules}

추가 지시(파일 다운로드/이미지 URL):
- 공고문/첨부파일/신청서 다운로드 버튼이 있으면 클릭해서 실제로 파일 다운로드를 시도해라.
- 다운로드가 발생하면 그 파일명(확장자 포함)을 required_documents에 포함해라.
- (중요) 포스터/카드뉴스/본문 이미지가 있으면 "다운로드하지 말고" 이미지 URL(src/og:image/a href의 jpg/png 등)만 찾아 image_urls에 담아라.

작업 단계:
1. 지정된 URL로 이동한다.
2. 팝업/알림 등이 뜨면 모두 닫는다.
3. 사이트 내 검색창/통합검색/정책검색이 있으면 '{title}'로 검색한다.
4. 후보 결과를 열어보며 정책명이 '{title}'과 맞는지 확인한다.
5. 맞는 정책(가장 유사한 정책)을 찾으면 아래 항목을 추출한다:
    - 지원대상/신청자격/선정기준/지원내용
    - 신청방법/신청절차/접수방법/신청기간
    - 제출서류/필수서류/구비서류
    - 문의처/담당기관/전화번호/홈페이지
6. 섹션을 찾기 위해 클릭/탭 이동을 하면, 그 경로를 navigation_path에 기록한다.
7. 수집한 텍스트를 기반으로 아래 JSON 형식으로만 최종 답변을 출력한다.

반드시 아래 JSON 형식만 출력해라. (추가 설명/문장 금지)

{{
  "source_url": "실제로 정보를 추출한 페이지 URL (없으면 null)",
  "matched_title": "현재 페이지에서 확인한 정책명/공고명/제목 (없으면 null)",
  "matched": true,
  "criteria": {{
    "age": "연령 요건을 한국어로 간단 요약. 없으면 '제한 없음'이라고 적기.",
    "region": "거주지/주소 요건이 있으면 요약, 없으면 '제한 없음'.",
    "income": "소득/재산 기준이 있으면 요약, 없으면 '제한 없음'.",
    "employment": "재직/구직/창업 등 고용 상태 기준이 있으면 요약, 없으면 '제한 없음'.",
    "other": "기타 주요 자격요건을 한 줄로 정리. 없으면 '없음'."
  }},
  "required_documents": ["제출서류를 항목 리스트로", "..."],
  "apply_steps": [
    {{"step": 1, "title": "단계 제목", "detail": "무엇을 하는지", "url": "해당 페이지가 있으면"}},
    {{"step": 2, "title": "단계 제목", "detail": "무엇을 하는지", "url": null}}
  ],
  "apply_channel": "온라인/방문/우편/혼합 중 하나로 요약",
  "apply_period": "신청기간/상시/마감일 등 원문 기반 요약",
  "contact": {{"org": "기관명", "tel": "전화", "site": "홈페이지 URL"}},
  "evidence_text": "위 기준을 판단하는 근거가 된 원문 문장을 한국어로 여러 줄 이어서 붙여넣기.",
  "navigation_path": [
    {{"action":"open","label":"시작 URL","url":"{url}","note":"entry"}},
    {{"action":"click","label":"클릭한 탭/버튼","url":"이동한 URL","note":"왜 클릭했는지"}}
  ],
  "error_message": null,
  "image_urls": ["이미지 URL(포스터/본문) 있으면", "..."],
  "confidence": 0.0,
  "needs_review": false
}}
        """.strip()

        return await BrowserService._run_agent(
            task,
            entry_url=url,
            log_callback=log_callback,
            screenshot_callback=screenshot_callback,
        )

    @staticmethod
    async def verify_policy_with_playwright_shortcut(
        policy: Policy,
        navigation_path: List[Dict[str, Any]],
        log_callback: AsyncLogCallback = None,
        screenshot_callback: AsyncScreenshotCallback = None,
    ) -> Dict[str, Any]:
        title = policy.title or ""
        url = _normalize_url(policy.target_url or "")
        if not url:
            raise ValueError("policy.target_url is empty")
        if log_callback:
            await log_callback(f"정규화된 target_url: {url}")

        anti_loop_rules = """
✅ 실패/루프 방지 규칙(매우 중요):
- 같은 유형의 행동(예: 스크롤만 반복, 같은 메뉴 클릭, 드롭다운 선택)을 2번 연속 실패하면 즉시 중단하고 다른 전략으로 전환한다.
- 페이지 하단의 'Family Site' / 외부 이동용 드롭다운(<select>)은 사용하지 마라. (timeout을 유발하고 정책 검색에 도움되지 않음)
- 정책을 찾기 위해서는 반드시 '사이트 내부 검색창/통합검색/공지/게시판/과정검색' 등 내부 기능만 사용해라.
- 5번 이상 스크롤해도 정책 단서(정책명/공고명/상세링크/검색창)가 안 보이면, 상단 메뉴로 이동해 다른 메뉴(공지/모집/과정검색 등)를 탐색한다.
- 10번 액션(클릭/검색/스크롤 포함) 안에 정책 단서를 못 찾으면 matched=false로 종료한다.
        """.strip()

        stop_after_extract_rules = """
✅ 종료 규칙(매우 중요):
- 힌트 경로를 따라가서 '이용안내/소개/가이드' 성격 페이지에 도달하더라도,
  도민리포터(청년 리포터) 모집/운영/선발/신청/문의 정보가 확인되면 그 페이지에서 추출하고 즉시 JSON을 완성해 종료해라.
- extract를 한 번 성공했고, 텍스트에 (도민리포터/청년리포터) + (신청/접수/모집/선발/운영/활동) 중 1개 이상이 있으면 종료해라.
        """.strip()

        path_hint = json.dumps(navigation_path, ensure_ascii=False)

        task = f"""
너는 대한민국 청년정책을 분석하는 전문 에이전트야.

아래 정책의 공식 안내 페이지에 접속해서,
'지원대상', '신청자격', '선정기준' 섹션을 빠르게 찾아야 한다.

- 정책 제목: {title}
- 접속해야 할 URL: {url}

이전 실행에서 사용했던 네비게이션 경로 힌트:
{path_hint}

🚫 절대 규칙(외부 검색 금지):
- 외부 검색엔진 사용 금지. 사이트 내부에서만 해결.

✅ 가장 중요한 규칙(정책 일치 검증):
- 지금 보고 있는 상세 페이지의 정책명/공고명/제목이 '{title}'과 일치(또는 매우 유사)해야만 추출한다.
- 일치하지 않으면 그 페이지에서 추출하지 말고, 뒤로가기/다른 결과로 이동해서 다시 시도한다.
- 최대 5개의 후보 페이지를 확인하고도 못 찾으면 matched=false로 반환한다.

{anti_loop_rules}

{stop_after_extract_rules}

추가 지시(파일 다운로드/이미지 URL):
- 공고문/첨부파일/신청서 다운로드 버튼이 있으면 클릭해서 실제로 파일 다운로드를 시도해라.
- 다운로드가 발생하면 그 파일명(확장자 포함)을 required_documents에 포함해라.
- ✅ (중요) 포스터/카드뉴스/본문 이미지가 있으면 "다운로드하지 말고" 이미지 URL(src/og:image/a href의 jpg/png 등)만 찾아 image_urls에 담아라.

작업 단계:
1. URL로 이동한다.
2. 팝업/알림이 뜨면 닫는다.
3. 힌트 경로를 참고해 유사한 버튼/탭/링크를 클릭해본다.
4. 안 보이면 '{title}'을(를) 사이트 내부에서 검색하거나 관련 텍스트를 찾아 탐색한다.
5. 정책명/공고명이 '{title}'과 일치하는지 확인한다.
6. 관련 섹션 텍스트를 수집한 뒤 아래 JSON 형식으로만 결과를 출력한다.

반드시 아래 JSON 형식만 출력해라. (추가 설명/문장 금지)

{{
  "source_url": "실제로 정보를 추출한 페이지 URL (없으면 null)",
  "matched_title": "현재 페이지에서 확인한 정책명/공고명/제목 (없으면 null)",
  "matched": true,
  "criteria": {{
    "age": "연령 요건 요약 또는 '제한 없음'.",
    "region": "거주지 요건 요약 또는 '제한 없음'.",
    "income": "소득/재산 기준 요약 또는 '제한 없음'.",
    "employment": "고용 상태 기준 요약 또는 '제한 없음'.",
    "other": "기타 주요 자격 요건 한 줄 또는 '없음'."
  }},
  "required_documents": ["제출서류를 항목 리스트로", "..."],
  "apply_steps": [
    {{"step": 1, "title": "단계 제목", "detail": "무엇을 하는지", "url": "해당 페이지가 있으면"}},
    {{"step": 2, "title": "단계 제목", "detail": "무엇을 하는지", "url": null}}
  ],
  "apply_channel": "온라인/방문/우편/혼합 중 하나로 요약",
  "apply_period": "신청기간/상시/마감일 등 원문 기반 요약",
  "contact": {{"org": "기관명", "tel": "전화", "site": "홈페이지 URL"}},
  "evidence_text": "근거가 된 원문 텍스트를 한국어로 여러 줄 이어서 붙여넣기.",
  "navigation_path": [
    {{"action":"open","label":"시작 URL","url":"{url}","note":"entry"}},
    {{"action":"click","label":"클릭한 탭/버튼","url":"이동한 URL","note":"왜 클릭했는지"}}
  ],
  "error_message": null,
  "image_urls": ["이미지 URL(포스터/본문) 있으면", "..."],
  "confidence": 0.0,
  "needs_review": false
}}
        """.strip()

        if log_callback:
            await log_callback("Playwright 지름길(힌트 기반) 모드로 검증 시작...")

        return await BrowserService._run_agent(
            task,
            entry_url=url,
            log_callback=log_callback,
            screenshot_callback=screenshot_callback,
        )

    @staticmethod
    def verify_policy_sync(
        policy: Policy,
        navigation_path: Optional[List[Dict[str, Any]]] = None,
        log_callback: Optional[Callable[[str], Any]] = None,
    ) -> Dict[str, Any]:
        async def _runner() -> Dict[str, Any]:
            usable_hint = False
            if navigation_path and isinstance(navigation_path, list):
                if len(navigation_path) >= 2:
                    usable_hint = True
                elif len(navigation_path) == 1:
                    a0 = navigation_path[0] or {}
                    if (a0.get("action") != "open") or (a0.get("note") != "auto-injected"):
                        usable_hint = True

            if usable_hint:
                return await BrowserService.verify_policy_with_playwright_shortcut(
                    policy,
                    navigation_path,
                    None,
                    None,
                )
            return await BrowserService.verify_policy_with_agent(policy, None, None)

        return asyncio.run(_runner())

    @staticmethod
    async def search_policy_pages_async(
        query: str,
        filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        logger.info(
            "[BrowserService] search_policy_pages_async called query=%s, filters=%s",
            query,
            filters,
        )
        return []
