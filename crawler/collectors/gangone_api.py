import requests
from datetime import datetime
import math

API_KEY = "d2e69355-5099-48f6-9682-31e434a89efa"
BASE_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"

# ✅ 강원특별자치도 시/도 코드(법정시군구코드 5자리 기준)
GANGWON_SIDO_ZIP = "51000"  # 강원특별자치도


def build_params(page_num: int = 1, page_size: int = 100):
    """
    ✅ 강원도(강원특별자치도)만 API에서 바로 필터링해서 가져오기
    """
    return {
        "apiKeyNm": API_KEY,
        "pageNum": page_num,
        "pageSize": page_size,
        "rtnType": "json",
        "zipCd": GANGWON_SIDO_ZIP,  # ✅ 핵심: 강원만 서버에서 걸러서 내려줌
    }


def fetch_page(page_num: int = 1, page_size: int = 100):
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
    ✅ 마감 제외(대략):
    - bizPrdEndYmd(사업기간 종료일)가 오늘 이전이면 제외
    - 종료일 없으면 포함
    """
    end = (p.get("bizPrdEndYmd") or "").strip()
    if not end or not end.isdigit():
        return True

    today_int = int(datetime.today().strftime("%Y%m%d"))
    return int(end) >= today_int


def fetch_all_gangwon(exclude_closed: bool = True):
    page_size = 100
    first_page, tot_count = fetch_page(page_num=1, page_size=page_size)

    print(f"🔎 강원(51000) 정책 수(totCount): {tot_count}")
    if not first_page and tot_count == 0:
        print("⚠ 강원 정책이 0개로 조회됨. (zipCd=51000이 먹는지 확인 필요)")
        return []

    all_policies = []
    all_policies.extend(first_page)

    total_pages = math.ceil(tot_count / page_size) if tot_count else 1
    print(f"📄 총 페이지 수: {total_pages}")

    for page_num in range(2, total_pages + 1):
        policies, _ = fetch_page(page_num=page_num, page_size=page_size)
        if not policies:
            print(f"⚠ {page_num}페이지에 데이터 없음, 중단")
            break
        all_policies.extend(policies)

    print(f"\n✅ 강원 원본 수집 완료: {len(all_policies)}개")

    if exclude_closed:
        alive_policies = [p for p in all_policies if is_not_closed(p)]
        print(f"⏱ 마감 제외 후 남은 정책 수: {len(alive_policies)}개")
    else:
        alive_policies = all_policies

    print("\n=== 샘플 5개 (강원 + 마감제외) ===")
    for p in alive_policies[:5]:
        print("plcyNo:", p.get("plcyNo"))
        print("plcyNm:", p.get("plcyNm"))
        print("zipCd:", p.get("zipCd"))
        print("설명:", (p.get("plcyExplnCn") or "").split("\n")[0])
        print("사업기간:", p.get("bizPrdBgngYmd"), "~", p.get("bizPrdEndYmd"))
        print("-" * 60)

    return alive_policies


if __name__ == "__main__":
    gangwon_policies = fetch_all_gangwon(exclude_closed=True)

    # CSV 저장
    try:
        import pandas as pd

        df = pd.DataFrame(gangwon_policies)
        df.to_csv("youth_policies_gangwon_alive.csv", encoding="utf-8-sig", index=False)
        print("\n💾 youth_policies_gangwon_alive.csv 로 저장 완료")
    except ImportError:
        print("\n(pandas가 없으면 `pip install pandas` 후 CSV 저장 가능)")
