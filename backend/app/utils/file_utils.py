# backend/app/utils/file_utils.py
import os

from ..config import settings


def get_download_dir() -> str:
    """
    browser-use가 파일을 다운로드할 기본 폴더.
    """
    path = settings.download_dir
    os.makedirs(path, exist_ok=True)
    return path
