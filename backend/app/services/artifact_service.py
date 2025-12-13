# app/services/artifact_service.py

import os
import re
import json
import zipfile
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---- optional deps ----
try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None  # type: ignore


_TEXT_EXTS = {".txt", ".md", ".csv", ".log"}
_IMG_EXTS = {".png", ".jpg", ".jpeg"}
_PDF_EXTS = {".pdf"}
_ZIP_EXTS = {".zip"}
_HWP_EXTS = {".hwp", ".hwpx"}  # MVP: 변환 미구현(추후 LibreOffice로)


def _safe_read_text_file(path: str, max_chars: int = 200_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception:
        try:
            with open(path, "r", encoding="cp949", errors="ignore") as f:
                return f.read(max_chars)
        except Exception as e:
            logger.warning("[ArtifactService] text read failed: %s (%s)", path, e)
            return ""


def _clean_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u00a0", " ").replace("\u200b", " ")
    # 과도한 공백/줄바꿈 정리
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _extract_pdf_text(path: str, max_pages: int = 50, max_chars: int = 300_000) -> Tuple[str, Dict[str, Any]]:
    meta: Dict[str, Any] = {"engine": "pypdf" if PdfReader else None}

    if PdfReader is None:
        meta["error"] = "pypdf not installed"
        return "", meta

    try:
        reader = PdfReader(path)
        num_pages = len(reader.pages)
        meta["pages"] = num_pages

        texts: List[str] = []
        for i, page in enumerate(reader.pages[:max_pages]):
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
        text = _clean_text("\n".join(texts))
        if len(text) > max_chars:
            text = text[:max_chars]
            meta["truncated"] = True

        # 텍스트가 거의 없다면 스캔 PDF 가능성
        if len(text) < 50:
            meta["warning"] = "very low text extracted (may be scanned PDF). OCR not implemented in MVP."
        return text, meta
    except Exception as e:
        meta["error"] = str(e)
        return "", meta


def _extract_image_ocr(path: str, max_chars: int = 120_000) -> Tuple[str, Dict[str, Any]]:
    meta: Dict[str, Any] = {"engine": "pytesseract" if pytesseract else None}

    if Image is None:
        meta["error"] = "Pillow not installed"
        return "", meta
    if pytesseract is None:
        meta["error"] = "pytesseract not installed (OCR skipped)"
        return "", meta

    try:
        img = Image.open(path)
        # 한국어 OCR 시도. 환경에 kor traineddata 없으면 실패할 수 있음.
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
class ExtractedArtifact:
    source_type: str  # file / image / pdf / text / zip / hwp
    name: str
    path: str
    text: str
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # text는 너무 길 수 있으니 meta에 길이도 남김
        d["meta"] = dict(self.meta or {})
        d["meta"]["text_len"] = len(self.text or "")
        return d


class ArtifactService:
    """
    MVP: downloads_dir + downloaded_files를 기반으로
    zip 해제 + 파일타입별 텍스트 추출(pdf/text/img ocr) + (hwp/hwpx는 보류)
    """

    @staticmethod
    def _ensure_extract_dir(downloads_dir: str, verification_id: int) -> str:
        out_dir = os.path.join(downloads_dir, "_extracted", str(verification_id))
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    @staticmethod
    def _unzip(path: str, out_dir: str) -> List[str]:
        extracted_paths: List[str] = []
        try:
            with zipfile.ZipFile(path, "r") as z:
                z.extractall(out_dir)
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    extracted_paths.append(os.path.join(out_dir, info.filename))
        except Exception as e:
            logger.warning("[ArtifactService] unzip failed: %s (%s)", path, e)
        return extracted_paths

    @staticmethod
    def _walk_files(root: str) -> List[str]:
        files: List[str] = []
        for base, _, names in os.walk(root):
            for n in names:
                files.append(os.path.join(base, n))
        return files

    @staticmethod
    def extract_from_downloads(
        downloads_dir: str,
        downloaded_files: List[str],
        verification_id: int,
        max_files: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        반환: ExtractedArtifact.to_dict() 리스트
        """
        results: List[ExtractedArtifact] = []

        extract_dir = ArtifactService._ensure_extract_dir(downloads_dir, verification_id)

        # 1) 원본 파일 경로 목록
        paths: List[str] = []
        for fn in downloaded_files[:max_files]:
            p = os.path.join(downloads_dir, fn)
            if os.path.isfile(p):
                paths.append(p)

        # 2) zip은 풀어서 내부 파일도 포함
        expanded: List[str] = []
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in _ZIP_EXTS:
                inner = ArtifactService._unzip(p, extract_dir)
                expanded.extend(inner)

        all_paths = paths + expanded

        # zip 풀린 폴더 내 전체 walk도 보강(중첩 zip/경로 이슈 방지)
        all_paths = list(dict.fromkeys(all_paths + ArtifactService._walk_files(extract_dir)))

        # 3) 타입별 추출
        for p in all_paths[: max_files * 2]:
            name = os.path.basename(p)
            ext = os.path.splitext(name)[1].lower()

            if ext in _TEXT_EXTS:
                text = _clean_text(_safe_read_text_file(p))
                results.append(ExtractedArtifact("text", name, p, text, {"ext": ext}))
                continue

            if ext in _PDF_EXTS:
                text, meta = _extract_pdf_text(p)
                results.append(ExtractedArtifact("pdf", name, p, text, {"ext": ext, **meta}))
                continue

            if ext in _IMG_EXTS:
                text, meta = _extract_image_ocr(p)
                results.append(ExtractedArtifact("image", name, p, text, {"ext": ext, **meta}))
                continue

            if ext in _HWP_EXTS:
                # MVP에서는 변환 미구현 (나중에 LibreOffice headless로 pdf 변환 파이프라인 추가)
                results.append(
                    ExtractedArtifact(
                        "hwp",
                        name,
                        p,
                        "",
                        {"ext": ext, "warning": "HWP/HWPX convert not implemented in MVP"},
                    )
                )
                continue

            # 나머지는 스킵(필요 시 확장)
            results.append(
                ExtractedArtifact(
                    "file",
                    name,
                    p,
                    "",
                    {"ext": ext, "note": "unsupported type (skipped text extraction)"},
                )
            )

        return [r.to_dict() for r in results]
