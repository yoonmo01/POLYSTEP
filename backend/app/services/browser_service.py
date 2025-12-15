# app/services/browser_service.py

import asyncio
import json
import logging
import time
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv, find_dotenv

from browser_use import Agent, Browser, ChatGoogle

# ✅ browser-use 버전에 따라 Controller가 없을 수 있음
try:
    from browser_use import Controller  # type: ignore
except Exception:
    Controller = None  # type: ignore

from app.utils.file_utils import ensure_download_dir
from app.models import Policy

logger = logging.getLogger(__name__)

# ✅ .env 로딩을 "확실하게"
# - 실행 cwd가 backend/app 여도 상위로 올라가며 .env를 찾도록
# - override 여부는 환경변수로 제어 가능
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

_SCREENSHOT_TIMEOUT_RE = re.compile(r"ScreenshotWatchdog\.on_ScreenshotEvent.*timed out", re.IGNORECASE)
_DOMWATCHDOG_SCREENSHOT_FAIL_RE = re.compile(r"Clean screenshot failed", re.IGNORECASE)

def _is_browser_snapshot_timeout(e: Exception) -> bool:
    msg = f"{type(e).__name__}: {e}"
    return bool(_SCREENSHOT_TIMEOUT_RE.search(msg) or _DOMWATCHDOG_SCREENSHOT_FAIL_RE.search(msg))


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _is_overload_error(e: Exception) -> bool:
    """
    Gemini/Provider 503(오버로드) 류를 문자열 기반으로 감지.
    (라이브러리 예외 타입이 버전마다 달라서 안전하게 문자열로 체크)
    """
    msg = f"{type(e).__name__}: {e}"
    return (
        ("503" in msg)
        or ("UNAVAILABLE" in msg)
        or ("overload" in msg.lower())
        or ("overloaded" in msg.lower())
    )


def _normalize_text_for_windows(text: str) -> str:
    """
    Windows 콘솔(cp949)에서 터지는 문자(특히 NBSP \\xa0 등)를 완화.
    """
    return (text or "").replace("\u00a0", " ").replace("\u200b", " ").strip()


_IMG_SRC_RE = re.compile(r"""<img[^>]+src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_OG_IMAGE_RE = re.compile(
    r"""<meta[^>]+property\s*=\s*["']og:image["'][^>]+content\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_A_HREF_RE = re.compile(r"""<a[^>]+href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

# 이미지 URL로 볼 확장자 (첨부/바로보기 링크가 jpg로 직접 걸린 케이스 대응)
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

    # og:image 우선
    for m in _OG_IMAGE_RE.finditer(html):
        found.append(urljoin(base_url, (m.group(1) or "").strip()))

    # img src
    for m in _IMG_SRC_RE.finditer(html):
        src = (m.group(1) or "").strip()
        if not src:
            continue
        # data:는 너무 크고 OCR 대상일 때도 처리 난이도 ↑ → 제외
        if src.lower().startswith("data:"):
            continue
        found.append(urljoin(base_url, src))
    # ✅ a href 로 직접 걸린 이미지(첨부 jpg / 카드뉴스 파일 링크)도 수집
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
    """
    ✅ "바로보기/원문보기/첨부"처럼 별도 뷰어 페이지를 여는 사이트 대응:
    - entry_url HTML에서 이미지 URL을 수집하고,
    - 추가로 '관련 링크' 몇 개를 골라(fetch) 그 안의 이미지 URL도 수집
    - 최종적으로 URL만 반환 (이미지 파일 다운로드는 여기서 하지 않음)
    """
    if not entry_url:
        return _dedup_keep_order(base_image_urls)[:max_image_urls]

    urls: List[str] = list(base_image_urls or [])

    html = await _fetch_html(entry_url, timeout_sec=10.0)
    urls.extend(_extract_image_urls_from_html(html, entry_url, limit=max_image_urls))

    # 관련 페이지 후보 링크 수집 (가볍게: a href 전체 중 "view/첨부/원문/바로보기" 느낌 URL)
    candidates: List[str] = []
    for m in _A_HREF_RE.finditer(html or ""):
        href = (m.group(1) or "").strip()
        if not href:
            continue
        if href.lower().startswith("javascript:"):
            continue
        abs_url = urljoin(entry_url, href)

        # 이미지는 바로 후보로
        if _IMG_EXT_RE.search(abs_url):
            candidates.append(abs_url)
            continue

        # "바로보기/원문보기/첨부/다운로드" 류로 보이는 링크만 소량 추려서 재-fetch
        low = abs_url.lower()
        if any(k in low for k in ("amode=view", "view", "preview", "viewer", "attach", "download", "file", "atch", "origin")):
            candidates.append(abs_url)

    candidates = _dedup_keep_order(candidates)
    # 너무 많이 돌면 비용/시간 증가 → 상위 N개만
    candidates = candidates[: max_related_pages]

    for u in candidates:
        # 링크 자체가 이미지면 추가
        if _IMG_EXT_RE.search(u):
            urls.append(u)
            continue
        sub_html = await _fetch_html(u, timeout_sec=10.0)
        urls.extend(_extract_image_urls_from_html(sub_html, u, limit=max_image_urls))

    return _dedup_keep_order(urls)[:max_image_urls]

# ============================================================
# ✅ 후처리(Validation + Repair) 유틸
#   - required_documents: 주소/대표전화 제거 + 파일/서류만 남김
#   - criteria.age에 지역조건 들어가면 region으로 이동 + age는 evidence에서 보강 시도
#   - '없음'류를 '제한 없음'으로 통일
#   - apply_channel 정규화(혼합/온라인/방문/우편)
#   - contact.tel이 비면 evidence에서 보강
# ============================================================

_PHONE_RE = re.compile(r"(?:\+82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}")

# 주소로 “너무 쉽게” 오판하지 않도록, 대표적인 패턴 위주로만
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

# none/없음 계열 정규화용
NONE_VALUES: Set[str] = {
    "상관없음",
    "없음",
    "없습니다",
    "해당 없음",
    "해당없음",
    "무관",
    "미해당",
    "-",
    "x",
    "X",
}


def _norm_none_or_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _normalize_none_value(value: Any, default: str = "제한 없음") -> str:
    """
    공백/None/없음류 -> default 로 통일
    """
    s = (_norm_none_or_str(value) or "").strip()
    if not s:
        return default
    if s.lower() in ("none", "n/a"):
        return default
    return default if s in NONE_VALUES else s


def _extract_field_line(evidence_text: str, field_name: str) -> Optional[str]:
    """
    evidence_text에서 예:
      지역기준
      제주시 전체 | 서귀포시 전체 | 상관없음
    처럼 "필드명" 다음 줄 값을 뽑아준다.
    """
    if not evidence_text:
        return None

    # 1) "필드명\n값" 패턴
    m = re.search(rf"{re.escape(field_name)}\s*\n\s*([^\n]+)", evidence_text)
    if m:
        return m.group(1).strip()

    # 2) "필드명 값" 같은 한 줄 패턴(혹시 모를 변형)
    m2 = re.search(rf"{re.escape(field_name)}\s*[:\-]?\s*([^\n]+)", evidence_text)
    if m2:
        return m2.group(1).strip()
    return None


def _merge_region_from_evidence(criteria_region: Optional[str], evidence_text: str) -> Optional[str]:
    """
    ✅ 이번 케이스 해결:
    evidence에는 '제주시 전체 | 서귀포시 전체 | 상관없음' 이 있는데
    LLM이 criteria.region에서 '상관없음'을 누락하는 경우가 있음.
    -> evidence의 지역기준 라인을 우선 신뢰해 보강.
    """
    ev = _extract_field_line(evidence_text, "지역기준")
    if not ev:
        return criteria_region

    cur = (criteria_region or "").strip()
    # criteria가 비었으면 evidence로 채움
    if not cur or _normalize_none_value(cur) == "제한 없음":
        return ev

    # evidence에 상관없음이 있는데 criteria에 없으면 보강
    if ("상관없음" in ev) and ("상관없음" not in cur):
        return ev

    # evidence가 더 구체적(파이프 구분)인데 criteria가 축약돼 있으면 evidence로
    if ("|" in ev) and ("|" not in cur):
        return ev

    return criteria_region


def _clean_required_documents(items: Any) -> List[str]:
    """
    required_documents에서 '주소/대표전화' 같은 잡음을 제거하고
    파일명/서식/서류로 보이는 것만 최대한 남긴다.
    """
    if not isinstance(items, list):
        return []

    out: List[str] = []
    for raw in items:
        s = _norm_none_or_str(raw)
        if not s:
            continue

        # 전화/주소 오염 제거
        if ("대표전화" in s) or ("대표 전화" in s) or ("전화" in s) or ("TEL" in s.upper()):
            if not _FILE_EXT_RE.match(s):
                continue
        if _PHONE_RE.search(s) and not _FILE_EXT_RE.match(s):
            continue
        if _LIKELY_ADDRESS_RE.search(s) and not _FILE_EXT_RE.match(s):
            continue

        # 서류처럼 보이는 것만 통과
        if (
            _FILE_EXT_RE.match(s)
            or ("신청서" in s)
            or ("제출" in s)
            or ("서류" in s)
            or ("증명" in s)
            or ("공고" in s)
        ):
            out.append(s)

    # 중복 제거(순서 유지)
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
    if not m:
        return None
    return m.group(0).strip()


def _normalize_apply_channel(v: Any) -> Optional[str]:
    """
    스키마가 '온라인/방문/우편/혼합' 중 하나를 원할 때, 흔한 출력 흔들림을 정리.
    """
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


# --------- repair 분리(단일 책임) ---------

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

    # criteria.age에 지역 조건이 들어간 흔한 실수 교정
    if age and (("거주" in age) or ("관외" in age) or ("지역" in age) or ("주소" in age)):
        if not region or _normalize_none_value(region) == "제한 없음":
            criteria["region"] = age
        criteria["age"] = "제한 없음"

    # evidence에서 연령 힌트가 있으면 보강
    inferred_age = _infer_age_from_evidence(evidence)
    if inferred_age:
        cur_age = _norm_none_or_str(criteria.get("age"))
        if not cur_age or _normalize_none_value(cur_age) == "제한 없음":
            criteria["age"] = inferred_age

    # region은 evidence 기반으로 한 번 더 보강(상관없음 누락 등 교정)
    merged_region = _merge_region_from_evidence(_norm_none_or_str(criteria.get("region")), evidence)
    if merged_region:
        criteria["region"] = merged_region.strip()

    # none 값 통일
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
    """
    LLM이 자주 틀리는 매핑/오염을 정규식 기반으로 교정.
    (단일 책임 함수로 분리하여 호출)
    """
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
    - REST Deep Track: verify_policy_sync() (BackgroundTasks 에서 호출)
    - WebSocket Deep Track: verify_policy_with_agent / verify_policy_with_playwright_shortcut
    """

    # ======================
    # 공통: Agent 실행 헬퍼
    # ======================
    @staticmethod
    async def _run_agent(
        task: str,
        entry_url: Optional[str] = None,
        log_callback: AsyncLogCallback = None,
    ) -> Dict[str, Any]:
        """
        browser-use Agent 한 번 실행하고
        최종 결과를 JSON 형태로 파싱해서 리턴.
        """
        if log_callback:
            await log_callback("브라우저 세션 준비 중...")

        # ✅ Windows에서 UTF-8 강제 (cp949 이슈 완화)
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        downloads_dir = ensure_download_dir()
        logger.info("[BrowserService] Using downloads_dir=%s", downloads_dir)

        headless = _env_flag("BROWSER_HEADLESS", "true")
        keep_open = _env_flag("BROWSER_KEEP_OPEN", "false")
        debug_ui = _env_flag("BROWSER_DEBUG_UI", "false")
        # ✅ 클릭/드롭다운 안정화(Windows/동적 DOM 사이트에서 특히 유효)
        # 필요하면 .env에서 0으로 끌 수 있음
        slowmo_ms = _env_int("BROWSER_SLOWMO_MS", 250)

        collect_images = _env_flag("BROWSER_COLLECT_IMAGE_URLS", "true")
        max_image_urls = _env_int("BROWSER_MAX_IMAGE_URLS", 30)
        # ✅ 바로보기/첨부 뷰어까지 따라가서 URL 수집할지 (기본 true)
        follow_related = _env_flag("BROWSER_IMAGE_FOLLOW_RELATED_PAGES", "true")
        max_related_pages = _env_int("BROWSER_IMAGE_MAX_RELATED_PAGES", 3)

        # ✅ 스냅샷 타임아웃이 너무 자주 나면 조기 종료(루프/클릭 깨짐 방지)
        #   - browser-use 쪽에서 Clean screenshot timeout이 누적되면 stale node 클릭이 연쇄로 발생함
        #   - 이 값은 상황 따라 조절 가능
        max_snapshot_failures = _env_int("BROWSER_MAX_SNAPSHOT_FAILURES", 2)
        snapshot_failures = 0

        # ✅ runaway 방지 옵션
        max_actions = _env_int("BROWSER_AGENT_MAX_ACTIONS", 20)
        # ✅ env 이름 혼선 방지: BROWSER_MAX_TIME_SEC 우선, 없으면 기존값 fallback
        max_time_sec = float(
            os.getenv(
                "BROWSER_MAX_TIME_SEC",
                os.getenv("BROWSER_AGENT_MAX_TIME_SEC", "300"),
            )
        )

        # ✅ (옵션) 허용 도메인 제한 (버전에 따라 미지원일 수 있어 try로 처리)
        allowed_domains_raw = (os.getenv("BROWSER_ALLOWED_DOMAINS", "") or "").strip()
        allowed_domains = [d.strip() for d in allowed_domains_raw.split(",") if d.strip()] or None

        # ✅ debug_ui가 켜져있으면 무조건 창 보이게 강제
        if debug_ui:
            headless = False
            keep_open = True

        # ✅ 오버로드(503) 자동 재시도 옵션
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

        # 🔥 중요: downloads_path 로 써야 함 (download_path 아님!)
        # ✅ browser-use 버전에 따라 slow_mo 인자 유무가 달라서 안전하게 처리
        try:
            browser = Browser(
                headless=headless,
                downloads_path=downloads_dir,
                slow_mo=slowmo_ms if slowmo_ms > 0 else None,
            )
        except TypeError:
            browser = Browser(headless=headless, downloads_path=downloads_dir)

        # Gemini (Google API 키는 .env 의 GOOGLE_API_KEY 사용)
        llm = ChatGoogle(model="gemini-2.5-pro")

        # ✅ 외부 검색 금지: 프롬프트만으로는 부족 → Controller로 차단(가능한 버전에서)
        controller = None
        if Controller is not None:
            try:
                controller = Controller(use_web_search=False)  # type: ignore[call-arg]
            except Exception:
                controller = None

        # ✅ Agent 생성 (버전별 인자 차이를 고려해 단계적으로 시도)
        agent_kwargs: Dict[str, Any] = dict(
            task=_normalize_text_for_windows(task),
            llm=llm,
            browser=browser,
        )
        if controller is not None:
            agent_kwargs["controller"] = controller

        # 이 옵션들은 버전에 따라 미지원일 수 있음 -> kwargs로 넣고 TypeError 시 fallback
        agent_kwargs["max_actions"] = max_actions
        agent_kwargs["max_time"] = max_time_sec
        if allowed_domains:
            agent_kwargs["allowed_domains"] = allowed_domains

        try:
            agent = Agent(**agent_kwargs)
        except TypeError:
            # fallback: 최소 인자만
            agent = Agent(
                task=_normalize_text_for_windows(task),
                llm=llm,
                browser=browser,
            )

        # ✅ 다운로드 스냅샷: 실행 전/후 diff로 “진짜 다운로드 됐는지” 확인
        run_started_at = datetime.now(timezone.utc)
        pre_files = _list_files_safe(downloads_dir)

        if log_callback:
            await log_callback("에이전트 실행 시작...")

        try:
            history = None
            last_err: Optional[Exception] = None

            for attempt in range(0, max_retries + 1):
                try:
                    if attempt > 0 and log_callback:
                        await log_callback(
                            f"LLM 오버로드 재시도 중... (attempt={attempt}/{max_retries})"
                        )

                    # ✅ max_time_sec 강제(Agent 옵션이 무시될 수 있으니 wait_for로 2중 안전장치)
                    history = await asyncio.wait_for(agent.run(), timeout=max_time_sec)
                    if history is None:
                        raise RuntimeError("Agent returned None")

                    last_err = None
                    break
                except Exception as e:
                    # ✅ screenshot/dom snapshot timeout 누적 감지 → 더 끌면 클릭이 계속 깨짐
                    #    (browser-use 내부 watchdog 이슈로 상태 인식이 무너지기 시작했다는 신호)
                    if _is_browser_snapshot_timeout(e):
                        snapshot_failures += 1
                        logger.warning(
                            "[BrowserService] snapshot timeout detected (%s/%s): %s",
                            snapshot_failures,
                            max_snapshot_failures,
                            e,
                        )
                        if snapshot_failures >= max_snapshot_failures:
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
                            
                    last_err = e
                    if _is_overload_error(e) and attempt < max_retries:
                        sleep_s = base_backoff * (2 ** attempt)
                        logger.warning(
                            "[BrowserService] LLM overload detected. retry in %.1fs: %s",
                            sleep_s,
                            e,
                        )
                        await asyncio.sleep(sleep_s)
                        continue
                    raise

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
            # ✅ GUI로 디버깅/관찰하고 싶으면 창을 닫지 않도록 옵션 제공
            if not keep_open:
                try:
                    await browser.close()  # type: ignore[attr-defined]
                except Exception:
                    pass

        # ✅ 다운로드 diff 계산
        post_files = _list_files_safe(downloads_dir)
        new_files = sorted(list(post_files - pre_files))

        # mtime 기반으로도 한번 더 거르기(기존 파일이 이름만 바뀌는 등 방지)
        downloaded_files: List[str] = []
        for fn in new_files:
            full = os.path.join(downloads_dir, fn)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(full), tz=timezone.utc)
                if mtime >= run_started_at:
                    downloaded_files.append(fn)
                else:
                    downloaded_files.append(fn)  # 이름 diff면 일단 포함(보수적으로)
            except Exception:
                downloaded_files.append(fn)

        if log_callback:
            await log_callback("에이전트 실행 완료, 결과 파싱 중...")

        # browser-use history 에 final_result()가 있다고 가정
        try:
            final_text = history.final_result()  # type: ignore[attr-defined]
        except Exception:
            final_text = str(history)

        final_text = _normalize_text_for_windows(final_text)
        logger.info("[BrowserService] final_result text snippet: %s", final_text[:500])

        parsed = BrowserService._safe_json_loads(final_text)

        # ✅ JSON 파싱 실패(=raw만 있음)면 "False"가 아니라 "알 수 없음(None)"으로 분리
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
            # ✅ True/False/None(알 수 없음) 그대로 유지
            "matched": parsed.get("matched") if "matched" in parsed else None,
            "matched_title": parsed.get("matched_title"),
            "source_url": parsed.get("source_url")
            or parsed.get("final_url")
            or parsed.get("url")
            or None,
            "criteria": parsed.get("criteria") or {},
            "required_documents": parsed.get("required_documents") or [],
            "apply_steps": parsed.get("apply_steps") or [],
            "apply_channel": parsed.get("apply_channel"),
            "apply_period": parsed.get("apply_period"),
            "contact": parsed.get("contact") or {},
            "evidence_text": parsed.get("evidence_text")
            or parsed.get("evidence")
            or final_text,
            "navigation_path": parsed.get("navigation_path") or [],
            "error_message": parsed.get("error_message"),
            # ✅ 실제 다운로드된 파일 목록(진짜로 downloads_dir에 생긴 것)
            "downloaded_files": downloaded_files,
            "downloads_dir": downloads_dir,
            # ✅ 포스터/본문 이미지 URL(텍스트/OCR은 다음 단계에서)
            "image_urls": parsed.get("image_urls") or [],
            # ✅ 사람이 확인해야 하는지 플래그(기본값)
            "confidence": float(parsed.get("confidence") or 0.0),
            "needs_review": bool(parsed.get("needs_review"))
            if "needs_review" in parsed
            else False,
        }

        # ✅ navigation_path 자동 주입 제거: “한 것처럼 보이는” 부작용 방지
        if not isinstance(result["navigation_path"], list):
            result["navigation_path"] = []
        if len(result["navigation_path"]) == 0:
            result["navigation_path_warning"] = (
                "Agent did not record any navigation_path (empty list)"
            )

        # ✅ 여기서 후처리(교정) 한번 돌리고 반환
        result = _repair_result(result)

        # ✅ image_urls 보강: "사진은 무조건 URL 방식"
        # - LLM 출력이 있든 없든, 최종 source_url/entry_url 기준으로 HTML 파싱을 항상 수행해 보강한다.
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
                            entry_url=html_url,
                            base_image_urls=cur,
                            max_image_urls=max_image_urls,
                            max_related_pages=max_related_pages,
                        )
                    else:
                        html = await _fetch_html(html_url, timeout_sec=10.0)
                        merged = cur + _extract_image_urls_from_html(html, html_url, limit=max_image_urls)
                        result["image_urls"] = _dedup_keep_order(merged)[:max_image_urls]
                else:
                    result["image_urls"] = _dedup_keep_order(cur)[:max_image_urls]
        except Exception as e:
            logger.warning("[BrowserService] image url enrichment failed: %s", e)

        # 다운로드가 실제로 없으면, required_documents에 파일명이 있어도 “미다운로드”일 수 있다는 힌트
        if result.get("required_documents") and not result.get("downloaded_files"):
            result["error_message"] = (
                (result.get("error_message") or "")
                + " NOTE: required_documents에 파일명이 있어도 실제 다운로드는 수행되지 않았을 수 있습니다."
            ).strip()

        return result

    @staticmethod
    def _safe_json_loads(text: str) -> Dict[str, Any]:
        """
        LLM이 JSON 앞뒤에 설명/코드펜스를 붙여도 최대한 JSON만 뽑아 파싱한다.
        """
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {"raw": text}
        except Exception:
            pass

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

    # ======================
    # 1차: 탐색형 Agent 모드
    # ======================
    @staticmethod
    async def verify_policy_with_agent(
        policy: Policy,
        log_callback: AsyncLogCallback = None,
    ) -> Dict[str, Any]:
        title = policy.title or ""
        url = policy.target_url or ""

        # ✅ 루프 방지/샛길 방지 규칙(드롭다운/FamilySite로 빠지면 timeout 루프가 잦음)
        anti_loop_rules = """
✅ 실패/루프 방지 규칙(매우 중요):
- 같은 유형의 행동(예: 스크롤만 반복, 같은 메뉴 클릭, 드롭다운 선택)을 2번 연속 실패하면 즉시 중단하고 다른 전략으로 전환한다.
- 페이지 하단의 'Family Site' / 외부 이동용 드롭다운(<select>)은 사용하지 마라. (timeout을 유발하고 정책 검색에 도움되지 않음)
- 정책을 찾기 위해서는 반드시 '사이트 내부 검색창/통합검색/공지/게시판/과정검색' 등 내부 기능만 사용해라.
- 5번 이상 스크롤해도 정책 단서(정책명/공고명/상세링크/검색창)가 안 보이면, 상단 메뉴로 이동해 다른 메뉴(공지/모집/과정검색 등)를 탐색한다.
- 10번 액션(클릭/검색/스크롤 포함) 안에 정책 단서를 못 찾으면 matched=false로 종료한다.
        """.strip()

        # ✅ "들어갔다가 딴짓" 방지: extract로 충분한 텍스트를 얻었으면 즉시 JSON 출력하고 종료
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

        return await BrowserService._run_agent(task, entry_url=url, log_callback=log_callback)

    # =================================
    # 2차: navigation_path 재사용 모드
    # =================================
    @staticmethod
    async def verify_policy_with_playwright_shortcut(
        policy: Policy,
        navigation_path: List[Dict[str, Any]],
        log_callback: AsyncLogCallback = None,
    ) -> Dict[str, Any]:
        title = policy.title or ""
        url = policy.target_url or ""

        # ✅ 루프 방지/샛길 방지 규칙(드롭다운/FamilySite로 빠지면 timeout 루프가 잦음)
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

        return await BrowserService._run_agent(task, entry_url=url, log_callback=log_callback)

    # =========================================
    # REST Deep Track용: 동기 wrapper (필수!)
    # =========================================
    @staticmethod
    def verify_policy_sync(
        policy: Policy,
        navigation_path: Optional[List[Dict[str, Any]]] = None,
        log_callback: Optional[Callable[[str], Any]] = None,
    ) -> Dict[str, Any]:
        """
        PolicyVerificationService.run_verification_job_sync() 에서 호출되는 동기 함수.
        내부에서 asyncio.run()으로 위의 async 함수들을 실행한다.
        """

        async def _runner() -> Dict[str, Any]:
            # ✅ navigation_path가 있어도 "auto-injected open만 있는 빈 힌트"면 shortcut 의미 없음
            # (이 경우 shortcut 모드가 오히려 샛길로 빠질 수 있음)
            usable_hint = False
            if navigation_path and isinstance(navigation_path, list):
                # open 1개짜리(시작 URL만)면 실질 힌트로 보지 않음
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
                )
            return await BrowserService.verify_policy_with_agent(policy, None)

        return asyncio.run(_runner())

    # =================================
    # (옵션) 나중용: 검색용 더미 함수
    # =================================
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
