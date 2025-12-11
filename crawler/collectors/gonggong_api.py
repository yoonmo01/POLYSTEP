import requests
from pprint import pprint
from datetime import datetime
import math

API_KEY = "d2e69355-5099-48f6-9682-31e434a89efa"  # ← 나중엔 .env로 빼도 됨
BASE_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"


def build_params(page_num: int = 1, page_size: int = 100):
    """
    지금은 필터 없이 '전체 정책'을 다 가져온 다음,
    파이썬에서 서울/경기 + 마감제외를 필터링하는 방식으로 간다.
    (zipCd, lclsfNm 같은 서버 필터는 나중에 필요하면 추가)
    """
    return {
        "apiKeyNm": API_KEY,
        "pageNum": page_num,
        "pageSize": page_size,
        "rtnType": "json",
    }


def fetch_page(page_num: int = 1, page_size: int = 100):
    """
    온통청년 정책 목록 한 페이지 불러오기 (필터 X, 원본 그대로)
    """
    params = build_params(page_num=page_num, page_size=page_size)
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()

    data = resp.json()

    if data.get("resultCode") != 200:
        print("⚠ API 에러:", data.get("resultMessage"))
        return [], 0

    result = data.get("result", {})
    pagging = result.get("pagging", {})
    tot_count = pagging.get("totCount", 0)

    policies = result.get("youthPolicyList", [])
    if not isinstance(policies, list):
        print("⚠ youthPolicyList 형식이 리스트가 아님:", type(policies))
        return [], tot_count

    return policies, tot_count


def is_not_closed(p: dict) -> bool:
    """
    마감 제외 필터:
    - bizPrdEndYmd(사업기간 종료일)가 오늘 이전이면 '마감'으로 보고 제외
    - 0, 공백, 이상한 값이면 '마감 여부 불명' → 일단 포함
    """
    end = (p.get("bizPrdEndYmd") or "").strip()
    if not end or not end.isdigit():
        return True  # 종료일 정보 없으면 일단 포함

    today_int = int(datetime.today().strftime("%Y%m%d"))
    end_int = int(end)
    return end_int >= today_int  # 오늘 이후면 살아있는 사업


def belongs_to_seoul_gyeonggi(p: dict) -> bool:
    """
    지역 필터:
    - zipCd: "11110,11140,..." 처럼 법정동 코드들이 콤마로 들어있을 수 있음
    - 규칙:
      * 11xxx  → 서울특별시
      * 41xxx  → 경기도
    - zipCd 안에 11xxx, 41xxx 코드가 하나라도 있으면 '서울/경기 대상 정책'으로 간주
    """
    zip_cd_str = p.get("zipCd") or ""
    codes = [c.strip() for c in zip_cd_str.split(",") if c.strip()]

    if not codes:
        # zipCd 없는 전국 정책 등은, UI에서 어떻게 취급하는지 애매해서
        # 일단 서울/경기 필터에서는 제외해두자 (원하면 여기 로직 조정 가능)
        return False

    for code in codes:
        # 5자리 숫자라고 가정
        if len(code) == 5 and code.isdigit():
            if code.startswith("11") or code.startswith("41"):
                return True

    return False


def fetch_all_and_filter_seoul_gyeonggi(exclude_closed: bool = True):
    """
    1) 전체 정책(4,300개)을 페이지 돌면서 다 가져온 뒤
    2) 마감제외 + 서울/경기 필터를 적용한다.
    """

    page_size = 100
    first_page, tot_count = fetch_page(page_num=1, page_size=page_size)

    print(f"🔎 API 전체 정책 수(totCount): {tot_count}")
    if not first_page:
        print("⚠ 첫 페이지에서 데이터를 못 가져왔음.")
        return []

    all_policies = []
    all_policies.extend(first_page)

    total_pages = math.ceil(tot_count / page_size)
    print(f"📄 총 페이지 수: {total_pages}")

    # 2페이지부터 끝까지
    for page_num in range(2, total_pages + 1):
        policies, _ = fetch_page(page_num=page_num, page_size=page_size)
        if not policies:
            print(f"⚠ {page_num}페이지에 데이터 없음, 중단")
            break
        all_policies.extend(policies)

    print(f"\n✅ 원본 전체 수집 완료: {len(all_policies)}개 (API totCount={tot_count})")

    # ----- 마감 제외 필터 -----
    if exclude_closed:
        alive_policies = [p for p in all_policies if is_not_closed(p)]
    else:
        alive_policies = all_policies

    print(f"⏱ 마감 제외 후 남은 정책 수: {len(alive_policies)}개")

    # ----- 서울/경기 필터 -----
    seoul_gg_policies = [p for p in alive_policies if belongs_to_seoul_gyeonggi(p)]
    print(f"📌 서울+경기 대상 정책 수: {len(seoul_gg_policies)}개")

    # 샘플 5개 정도 찍어보기
    print("\n=== 샘플 5개 (서울/경기 + 마감제외) ===")
    for p in seoul_gg_policies[:5]:
        print("plcyNo:", p.get("plcyNo"))
        print("plcyNm:", p.get("plcyNm"))
        print("zipCd:", p.get("zipCd"))
        print("설명:", (p.get("plcyExplnCn") or "").split("\n")[0])
        print("사업기간:", p.get("bizPrdBgngYmd"), "~", p.get("bizPrdEndYmd"))
        print("-" * 60)

    return seoul_gg_policies


if __name__ == "__main__":
    seoul_gg_policies = fetch_all_and_filter_seoul_gyeonggi(exclude_closed=True)

    # 원하면 CSV로 저장해서 엑셀로 직접 비교도 가능
    try:
        import pandas as pd

        df = pd.DataFrame(seoul_gg_policies)
        df.to_csv("youth_policies_seoul_gyeonggi_alive.csv", encoding="utf-8-sig", index=False)
        print("\n💾 youth_policies_seoul_gyeonggi_alive.csv 로 저장 완료")
    except ImportError:
        print("\n(pandas가 없으면 `pip install pandas` 후 CSV 저장 가능)")
