# app/services/image_url_service.py

import os
import re
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None  # type: ignore


def _clean_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u00a0", " ").replace("\u200b", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _safe_filename_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        base = os.path.basename(path) or "image"
        # 확장자 없으면 png로
        if "." not in base:
            base += ".png"
        return re.sub(r"[^0-9A-Za-z._-]+", "_", base)
    except Exception:
        return "image.png"


def _ocr_image_file(path: str, max_chars: int = 120_000) -> Tuple[str, Dict[str, Any]]:
    meta: Dict[str, Any] = {"engine": "pytesseract" if pytesseract else None}

    if Image is None:
        meta["error"] = "Pillow not installed"
        return "", meta
    if pytesseract is None:
        meta["error"] = "pytesseract not installed (OCR skipped)"
        return "", meta

    try:
        img = Image.open(path)
        try:
            text = pytesseract.image_to_string(img, lang="kor+eng")
        except Exception:
            text = pytesseract.image_to_string(img)
        text = _clean_text(text)
        if len(text) > max_chars:
            text = text[:max_chars]
            meta["truncated"] = True
        return text, meta
    except Exception as e:
        meta["error"] = str(e)
        return "", meta


@dataclass
class ExtractedImageURL:
    url: str
    saved_path: Optional[str]
    text: str
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["meta"] = dict(self.meta or {})
        d["meta"]["text_len"] = len(self.text or "")
        return d


class ImageURLService:
    """
    image_urls를 다운로드해 OCR 텍스트화 (MVP)
    """

    @staticmethod
    async def ocr_from_urls(
        image_urls: List[str],
        downloads_dir: str,
        verification_id: int,
        timeout_sec: float = 12.0,
        max_urls: int = 15,
    ) -> List[Dict[str, Any]]:
        if not image_urls:
            return []

        out_dir = os.path.join(downloads_dir, "_image_urls", str(verification_id))
        os.makedirs(out_dir, exist_ok=True)

        results: List[ExtractedImageURL] = []

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout_sec, headers={"User-Agent": "Mozilla/5.0"}
        ) as client:
            for url in image_urls[:max_urls]:
                url = (url or "").strip()
                if not url:
                    continue

                fn = _safe_filename_from_url(url)
                save_path = os.path.join(out_dir, fn)

                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    with open(save_path, "wb") as f:
                        f.write(r.content)

                    text, meta = _ocr_image_file(save_path)
                    results.append(
                        ExtractedImageURL(
                            url=url,
                            saved_path=save_path,
                            text=text,
                            meta={"downloaded": True, **meta},
                        )
                    )
                except Exception as e:
                    logger.warning("[ImageURLService] download/ocr failed url=%s err=%s", url, e)
                    results.append(
                        ExtractedImageURL(
                            url=url,
                            saved_path=None,
                            text="",
                            meta={"downloaded": False, "error": str(e)},
                        )
                    )

        return [r.to_dict() for r in results]
