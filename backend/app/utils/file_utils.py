#app/utils/file_utils.py
from pathlib import Path


def ensure_download_dir() -> str:
    base = Path(__file__).resolve().parents[2]  # backend/ 기준
    download_dir = base / "data" / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    return str(download_dir)
