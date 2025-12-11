import pandas as pd
from datetime import datetime

INPUT_FILE = "youth_policies_enriched.csv"
OUTPUT_FILE = "youth_policies_ui_clean.csv"  # 👈 여기로 407개짜리 CSV 저장

def is_ui_active(row):
    """
    온통청년 UI 기준과 비슷하게 '현재 모집 중인 정책'인지 판단
    """

    # 1) 상시 모집
    aply_cd = str(row.get("aplyPrdSeCd", "")).strip()
    if aply_cd == "상시":
        return True

    # 2) 종료일 기반 (마감 제외)
    end = str(row.get("bizPrdEndYmd", "")).strip()

    if end.isdigit():
        today = int(datetime.today().strftime("%Y%m%d"))
        end_i = int(end)

        if end_i >= today:
            return True

    # 3) 종료일/상태 정보 없으면 UI에서는 대부분 포함된다고 보고 포함
    if end in ("", "0", None):
        return True

    return False


def main():
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

    # ---- 1) 지역 필터 (서울 + 경기) ----
    df_region = df[(df["is_seoul"]) | (df["is_gyeonggi"])]

    # ---- 2) UI식 모집중 상태 필터 ----
    df_active = df_region[df_region.apply(is_ui_active, axis=1)]

    # ---- 3) 중복 정책 제거 (plcyNm 기준) ----
    # 같은 정책명이 여러 zipCd를 커버할 경우 하나로 묶기
    unique_by_name = df_active.drop_duplicates(subset=["plcyNm"]).copy()

    print("\n=== 정책 개수 계산 결과 ===")
    print(f"전체 정책 수(서울+경기, 마감제외+UI 기준): {len(df_active)}")
    print(f"UI 기준 중복 제거 후 정책 수(plcyNm 기준): {len(unique_by_name)}")

    print("\n상위 10개 샘플:")
    print(unique_by_name[["plcyNo", "plcyNm", "sido_name"]].head(10))

    # ---- 4) CSV로 저장 ----
    unique_by_name.to_csv(OUTPUT_FILE, encoding="utf-8-sig", index=False)
    print(f"\n💾 CSV 저장 완료: {OUTPUT_FILE}")
    print("   - 열 개수:", len(unique_by_name.columns))
    print("   - 행 개수:", len(unique_by_name))


if __name__ == "__main__":
    main()
