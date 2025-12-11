import pandas as pd

# 1️⃣ 시도 코드 → 시도 이름 매핑 테이블
SIDO_CODE_MAP = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "42": "강원도",         # 강원특별자치도지만 이름은 필요에 따라 조정 가능
    "43": "충청북도",
    "44": "충청남도",
    "45": "전라북도",       # 전북특별자치도
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
}


def extract_first_zip(zip_cd_str: str | float | None) -> str | None:
    """
    zipCd에서 맨 첫 번째 5자리 코드만 대표로 뽑는다.
    예) "11000,11110,11140" → "11000"
    """
    if not isinstance(zip_cd_str, str):
        return None
    parts = [p.strip() for p in zip_cd_str.split(",") if p.strip()]
    if not parts:
        return None
    first = parts[0]
    if len(first) >= 5:
        return first[:5]
    return None


def map_sido_code(zip_first: str | None) -> str | None:
    """
    첫 zip 코드에서 앞 2자리 시도코드를 뽑아 시도 이름으로 매핑
    """
    if not zip_first or len(zip_first) < 2:
        return None
    sido_code = zip_first[:2]
    return SIDO_CODE_MAP.get(sido_code)


# 2️⃣ 카테고리 매핑 로직

def map_category(lclsf, mclsf) -> str:
    """
    온통청년 대분류(lclsfNm) / 중분류(mclsfNm)를
    우리 서비스용 카테고리로 매핑한다.
    """
    # NaN, float 등 처리
    if not isinstance(lclsf, str):
        lclsf = ""
    if not isinstance(mclsf, str):
        mclsf = ""

    l = lclsf.strip()
    m = mclsf.strip()
    text = f"{l} {m}"

    # 1) 주거관련
    if "주거" in text or "월세" in text or "전월세" in text or "임차" in text or "임대" in text:
        return "주거지원"

    # 2) 일자리/취업 관련
    if "일자리" in text or "취업" in text or "고용" in text or "인턴" in text or "근로" in text or "알바" in text:
        return "취업·일자리"

    # 3) 창업 관련
    if "창업" in text or "창업지원" in text or "스타트업" in text or "사업화" in text:
        return "창업지원"

    # 4) 교육/훈련 관련
    if "교육" in text or "훈련" in text or "강좌" in text or "강의" in text or "캠프" in text or "스쿨" in text or "멘토링" in text:
        return "교육·훈련"

    # 5) 복지/생활비/문화 관련 → 소득·생활
    if "복지" in text or "생활" in text or "문화" in text or "수당" in text or "교통비" in text or "지원금" in text:
        return "소득·생활"

    # 6) 그 밖에 다 기타
    return "기타"



def main():
    # 0. 원본 데이터 읽기 (파일명은 네 파일명에 맞게 변경)
    input_path = "C:/POLYSTEP/youth_policies_seoul_gyeonggi_alive.csv"
    output_path = "C:/POLYSTEP/youth_policies_enriched.csv"

    df = pd.read_csv(input_path, encoding="utf-8-sig")

    # ---- 1단계: 지역 정규화 ----
    # zipCd에서 대표 코드, 시도 이름 뽑기
    df["zip_first"] = df["zipCd"].apply(extract_first_zip)
    df["sido_name"] = df["zip_first"].apply(map_sido_code)
    df["lclsfNm"] = df["lclsfNm"].fillna("").astype(str)
    df["mclsfNm"] = df["mclsfNm"].fillna("").astype(str)
    # 서울/경기 플래그
    df["is_seoul"] = df["sido_name"] == "서울특별시"
    df["is_gyeonggi"] = df["sido_name"] == "경기도"

    # ---- 2단계: 카테고리 재분류 ----
    # 온통청년 원본 대분류/중분류를 보존
    # lclsfNm, mclsfNm 컬럼 이름이 다르면 여기만 수정
    df["category_raw_l"] = df.get("lclsfNm")
    df["category_raw_m"] = df.get("mclsfNm")

    df["category"] = df.apply(
        lambda row: map_category(row.get("lclsfNm"), row.get("mclsfNm")),
        axis=1,
    )

    # 결과 저장
    df.to_csv(output_path, encoding="utf-8-sig", index=False)
    print(f"✅ 완료: {output_path} 저장")
    print("   - 컬럼 추가: zip_first, sido_name, is_seoul, is_gyeonggi, category")


if __name__ == "__main__":
    main()
