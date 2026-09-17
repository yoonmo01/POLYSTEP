import pandas as pd
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
FILE = str(DATA_DIR / "policies_cleaned_final_gangwon_only.csv")

MARRIAGE_MAP = {
    "55001": "미혼",
    "55002": "기혼",
    "55003": "결혼 여부 상관없음",  # 서비스용 라벨
}


def normalize_marriage(code_raw):
    """55003.0 → '결혼 여부 상관없음' 으로 바꾸기"""
    if pd.isna(code_raw):
        return ""
    s = str(code_raw).strip()

    # 1) 숫자 형태면 float→int→str 로 안정적으로 변환
    try:
        num = int(float(s))        # 예: "55003.0" → 55003
        key = str(num)             # "55003"
    except ValueError:
        # 2) 숫자 변환이 안 되면, 숫자만 뽑아서 시도
        import re
        digits = re.sub(r"\D", "", s)
        key = digits if digits else s

    return MARRIAGE_MAP.get(key, s)


def main():
    df = pd.read_csv(FILE, encoding="utf-8-sig")

    if "marriage_code" not in df.columns:
        print("⚠ marriage_code 컬럼이 없습니다. 헤더 이름을 확인해주세요.")
        print("현재 컬럼들:", df.columns.tolist())
        return

    print("=== 패치 전 상위 5개 ===")
    print(df[["policy_id", "marriage_code"]].head())

    # 🔥 여기서 실제 변환
    df["marriage_code"] = df["marriage_code"].apply(normalize_marriage)

    print("\n=== 패치 후 상위 5개 ===")
    print(df[["policy_id", "marriage_code"]].head())

    df.to_csv(FILE, encoding="utf-8-sig", index=False)
    print(f"\n✅ 저장 완료: {FILE}")


if __name__ == "__main__":
    main()
