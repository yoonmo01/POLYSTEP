# backend/app/services/parsing_service.py
import os
from typing import List

import pdfplumber
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract

from ..utils.hwp_utils import extract_text_from_hwp


def extract_texts_from_files(file_paths: List[str]) -> List[str]:
    """
    HWP, PDF, 이미지(PNG/JPG 등)를 텍스트로 변환.
    """
    texts: List[str] = []

    for path in file_paths:
        if not os.path.exists(path):
            continue

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".hwp":
                text = extract_text_from_hwp(path)
                if text:
                    texts.append(text)

            elif ext == ".pdf":
                # 간단히 pdfplumber 사용 (필요시 PyPDF2로 변경)
                with pdfplumber.open(path) as pdf:
                    pages_text = "\n".join(
                        [page.extract_text() or "" for page in pdf.pages]
                    )
                if pages_text.strip():
                    texts.append(pages_text)

            elif ext in [".png", ".jpg", ".jpeg"]:
                img = Image.open(path)
                text = pytesseract.image_to_string(img, lang="kor+eng")
                if text.strip():
                    texts.append(text)

            else:
                # 기타 파일은 일단 무시하거나, 나중에 로직 추가
                continue

        except Exception:
            # 추출 실패 시 무시 (로그는 나중에 추가)
            continue

    return texts