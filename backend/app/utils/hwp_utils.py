# backend/app/utils/hwp_utils.py
from typing import Optional

# TODO: 실제 pyhwpx 또는 hwp5txt 로직으로 교체
# 현재는 스켈레톤만 제공


def extract_text_from_hwp(path: str) -> Optional[str]:
    """
    HWP 파일에서 텍스트를 추출하는 함수.

    초기에는 단순히 NotImplemented로 두고,
    나중에 pyhwpx / hwp5txt / win32com 등
    원하는 방식으로 구현하면 됨.
    """
    # 예시:
    # from pyhwpx import HwpDocument
    # doc = HwpDocument(path)
    # return doc.text

    return None
