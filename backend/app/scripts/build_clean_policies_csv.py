import pandas as pd
import re

INPUT_FILE = "youth_policies_ui_clean.csv"
OUTPUT_FILE = "policies_cleaned_final.csv"


# 모집기간 코드 → 한글 라벨 매핑
APPLY_PERIOD_MAP = {
    "57001": "기간모집",   # (예: 특정 기간)
    "57002": "상시모집",   # 상시 모집
}

# 혼인 상태 코드 → 한글 라벨 매핑
MARRIAGE_MAP = {
    "55001": "미혼",
    "55002": "기혼",
    "55003": "제한없음|기혼|미혼",
}


def clean_str(x):
    """NaN, float 등을 안전하게 문자열로 변환"""
    if pd.isna(x):
        return ""
    return str(x).strip()


def make_raw_snippet(row, max_len: int = 180) -> str:
    """
    plcyExplnCn / plcySprtCn을 이용해서
    한 줄짜리 요약(raw_snippet) 생성 (LLM 없이 규칙 기반)
    """
    expl = clean_str(row.get("plcyExplnCn"))
    sprt = clean_str(row.get("plcySprtCn"))

    text = expl if expl else sprt
    if not text:
        # 둘 다 없으면 정책명이라도 넣기
        return clean_str(row.get("plcyNm"))

    # 개행 정리
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # 아주 단순한 문장 분리: '다.' 기준 → 그래도 없으면 '.'
    sentences = re.split(r"다\.\s*", text)
    if len(sentences) > 1:
        first = sentences[0] + "다."
        second = sentences[1].strip()
        snippet = first if not second else (first + " " + second + "다.")
    else:
        sentences = re.split(r"\.\s*", text)
        first = sentences[0]
        snippet = first

    snippet = snippet.strip()

    # 길이 제한
    if len(snippet) > max_len:
        snippet = snippet[:max_len].rstrip() + "..."

    return snippet


def normalize_number(value):
    """숫자(나이/금액 등) 처리: 0, NaN → None"""
    try:
        if pd.isna(value):
            return None
        v = float(value)
        if v <= 0:
            return None
        return int(v)
    except Exception:
        return None


def build_clean_df(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in df.iterrows():
        policy_id = clean_str(row.get("plcyNo"))
        title = clean_str(row.get("plcyNm"))
        keywords = clean_str(row.get("plcyKywdNm"))

        category = clean_str(row.get("category"))
        category_l = clean_str(row.get("lclsfNm"))
        category_m = clean_str(row.get("mclsfNm"))

        sido_name = clean_str(row.get("sido_name"))
        zip_first = clean_str(row.get("zip_first"))

        # 나이
        age_min_num = normalize_number(row.get("sprtTrgtMinAge"))
        age_max_num = normalize_number(row.get("sprtTrgtMaxAge"))
        age_min = "" if age_min_num is None else str(age_min_num)
        age_max = "" if age_max_num is None else str(age_max_num)
        age_limit_yn = clean_str(row.get("sprtTrgtAgeLmtYn"))

        # 혼인 상태 코드 → 라벨 매핑
        m_code_raw = clean_str(row.get("mrgSttsCd"))
        m_code_digits = re.sub(r"\D", "", m_code_raw)  # 숫자만 추출
        marriage_label = MARRIAGE_MAP.get(m_code_digits, m_code_raw)

        # 소득 조건
        earn_min_num = normalize_number(row.get("earnMinAmt"))
        earn_max_num = normalize_number(row.get("earnMaxAmt"))
        earn_etc = clean_str(row.get("earnEtcCn"))

        if earn_min_num is not None or earn_max_num is not None:
            parts = []
            if earn_min_num is not None:
                parts.append(f"최소 {earn_min_num}")
            if earn_max_num is not None:
                parts.append(f"최대 {earn_max_num}")
            income_condition = ", ".join(parts)
        else:
            income_condition = earn_etc

        # 모집 유형 코드 → 라벨 매핑
        aply_cd_raw = clean_str(row.get("aplyPrdSeCd"))
        aply_cd_digits = re.sub(r"\D", "", aply_cd_raw)
        apply_period_type = APPLY_PERIOD_MAP.get(aply_cd_digits, aply_cd_raw)

        apply_period_raw = clean_str(row.get("aplyYmd"))
        biz_start = clean_str(row.get("bizPrdBgngYmd"))
        biz_end = clean_str(row.get("bizPrdEndYmd"))

        provider_main = clean_str(row.get("sprvsnInstCdNm"))
        provider_operator = clean_str(row.get("operInstCdNm"))

        # URL: apply_url이 없으면 ref1 → ref2 순으로 채워 넣는 것도 가능
        aply_url = clean_str(row.get("aplyUrlAddr"))
        ref1 = clean_str(row.get("refUrlAddr1"))
        ref2 = clean_str(row.get("refUrlAddr2"))

        if not aply_url:
            aply_url = ref1 or ref2

        raw_expln = clean_str(row.get("plcyExplnCn"))
        raw_support = clean_str(row.get("plcySprtCn"))
        raw_snippet = make_raw_snippet(row)

        notes = clean_str(row.get("etcMttrCn"))

        created_at = clean_str(row.get("frstRegDt"))
        updated_at = clean_str(row.get("lastMdfcnDt"))

        rows.append(
            {
                "policy_id": policy_id,
                "title": title,
                "keywords": keywords,
                "category": category,
                "category_l": category_l,
                "category_m": category_m,
                "region_sido": sido_name,
                "region_zip_first": zip_first,
                "age_min": age_min,
                "age_max": age_max,
                "age_limit_yn": age_limit_yn,
                "income_condition": income_condition,
                "marriage_code": marriage_label,  # ← 이제 라벨(제한없음|기혼|미혼 등)
                "apply_period_type": apply_period_type,  # ← 기간모집 / 상시모집 등
                "apply_period_raw": apply_period_raw,
                "biz_start": biz_start,
                "biz_end": biz_end,
                "provider_main": provider_main,
                "provider_operator": provider_operator,
                "apply_url": aply_url,
                "ref_url_1": ref1,
                "ref_url_2": ref2,
                "raw_expln": raw_expln,
                "raw_support": raw_support,
                "raw_snippet": raw_snippet,
                "notes": notes,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

    clean_df = pd.DataFrame(rows)
    return clean_df


def main():
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

    clean_df = build_clean_df(df)

    clean_df.to_csv(OUTPUT_FILE, encoding="utf-8-sig", index=False)
    print(f"✅ 정제 CSV 저장 완료: {OUTPUT_FILE}")
    print(f"   - 행 개수: {len(clean_df)}")
    print(f"   - 열 개수: {len(clean_df.columns)}")


if __name__ == "__main__":
    main()
