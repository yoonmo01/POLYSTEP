import pandas as pd
import re

FILE = "policies_cleaned_final.csv"

MARRIAGE_MAP = {
    "55001": "미혼",
    "55002": "기혼",
    "55003": "제한없음|기혼|미혼",
}


def normalize_marriage(code_raw):
    """55003.0 → '제한없음|기혼|미혼' 같은 라벨로 변경"""
    if pd.isna(code_raw):
        return ""
    s = str(code_raw).strip()
    digits = re.sub(r"\D", "", s)  # 숫자만 추출 (55003.0 → 55003)
    if not digits:
        return s
    return MARRIAGE_MAP.get(digits, s)


def normalize_number_str(v):
    """
    18.0 → '18', 20250201.0 → '20250201'
    NaN, 빈값 → ''
    """
    if pd.isna(v):
        return ""
    s = str(v).strip()
    # 소수점 있으면 앞부분만 사용
    if "." in s:
        s = s.split(".", 1)[0]
    # 전부 숫자인 경우만 리턴, 아니면 원문 그대로
    if s.isdigit():
        return s
    return s


def main():
    df = pd.read_csv(FILE, encoding="utf-8-sig")

    # 1) marriage_code → 한글 라벨로 교체
    if "marriage_code" in df.columns:
        df["marriage_code"] = df["marriage_code"].apply(normalize_marriage)
    else:
        print("⚠ marriage_code 컬럼이 없습니다.")

    # 2) 숫자 문자열로 정리할 컬럼들
    num_cols = ["age_min", "age_max", "biz_start", "biz_end"]
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(normalize_number_str)

    df.to_csv(FILE, encoding="utf-8-sig", index=False)

    print("✅ 패치 완료! 상위 5개 확인:")
    cols_to_show = [
        c
        for c in ["policy_id", "age_min", "age_max", "biz_start", "biz_end", "marriage_code"]
        if c in df.columns
    ]
    print(df[cols_to_show].head())


if __name__ == "__main__":
    main()
