# import pandas as pd
# from datetime import datetime

# INPUT_FILE = "youth_policies_enriched.csv"
# OUTPUT_FILE = "youth_policies_ui_clean.csv"  # 👈 여기로 407개짜리 CSV 저장

# def is_ui_active(row):
#     """
#     온통청년 UI 기준과 비슷하게 '현재 모집 중인 정책'인지 판단
#     """

#     # 1) 상시 모집
#     aply_cd = str(row.get("aplyPrdSeCd", "")).strip()
#     if aply_cd == "상시":
#         return True

#     # 2) 종료일 기반 (마감 제외)
#     end = str(row.get("bizPrdEndYmd", "")).strip()

#     if end.isdigit():
#         today = int(datetime.today().strftime("%Y%m%d"))
#         end_i = int(end)

#         if end_i >= today:
#             return True

#     # 3) 종료일/상태 정보 없으면 UI에서는 대부분 포함된다고 보고 포함
#     if end in ("", "0", None):
#         return True

#     return False


# def main():
#     df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

#     # ---- 1) 지역 필터 (서울 + 경기) ----
#     df_region = df[(df["is_seoul"]) | (df["is_gyeonggi"])]

#     # ---- 2) UI식 모집중 상태 필터 ----
#     df_active = df_region[df_region.apply(is_ui_active, axis=1)]

#     # ---- 3) 중복 정책 제거 (plcyNm 기준) ----
#     # 같은 정책명이 여러 zipCd를 커버할 경우 하나로 묶기
#     unique_by_name = df_active.drop_duplicates(subset=["plcyNm"]).copy()

#     print("\n=== 정책 개수 계산 결과 ===")
#     print(f"전체 정책 수(서울+경기, 마감제외+UI 기준): {len(df_active)}")
#     print(f"UI 기준 중복 제거 후 정책 수(plcyNm 기준): {len(unique_by_name)}")

#     print("\n상위 10개 샘플:")
#     print(unique_by_name[["plcyNo", "plcyNm", "sido_name"]].head(10))

#     # ---- 4) CSV로 저장 ----
#     unique_by_name.to_csv(OUTPUT_FILE, encoding="utf-8-sig", index=False)
#     print(f"\n💾 CSV 저장 완료: {OUTPUT_FILE}")
#     print("   - 열 개수:", len(unique_by_name.columns))
#     print("   - 행 개수:", len(unique_by_name))


# if __name__ == "__main__":
#     main()

import pandas as pd
from datetime import datetime
import re

INPUT_FILE = "C:/POLYSTEP/youth_policies_gangwon_enriched.csv"
OUTPUT_FILE = "C:/POLYSTEP/youth_policies_gangwon_only_ui_clean.csv"

# 온통청년 신청기간 구분 코드: 숫자만 뽑으면 57002 / 57001 같은 형태가 됨
ALWAYS_OPEN_DIGITS = {"57002"}  # 상시모집

def is_ui_active(row) -> bool:
    """
    온통청년 UI 기준과 비슷하게 '현재 모집 중'인지 판단 (코드 기반)
    """
    # 1) 상시 모집(코드)
    aply_cd_raw = str(row.get("aplyPrdSeCd", "")).strip()
    aply_digits = re.sub(r"\D", "", aply_cd_raw)
    if aply_digits in ALWAYS_OPEN_DIGITS:
        return True

    # 2) 종료일 기반 (마감 제외)
    end = str(row.get("bizPrdEndYmd", "")).strip()
    if end.isdigit():
        today = int(datetime.today().strftime("%Y%m%d"))
        if int(end) >= today:
            return True

    # 3) 정보 없으면 포함
    if end in ("", "0", "None"):
        return True

    return False


def main():
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

    # ---- 1) 강원 전용만 ----
    if "is_gangwon_only" not in df.columns:
        raise RuntimeError("is_gangwon_only 컬럼이 없습니다. normalize_policies.py를 먼저 실행하세요.")

    df_region = df[df["is_gangwon_only"] == True]

    # ---- 2) UI식 모집중 상태 필터 ----
    df_active = df_region[df_region.apply(is_ui_active, axis=1)]

    # ---- 3) 중복 제거 ----
    # ✅ 정책명은 겹칠 수 있어서 plcyNo 기준 권장
    unique_by_id = df_active.drop_duplicates(subset=["plcyNo"]).copy()

    print("\n=== 정책 개수 계산 결과 ===")
    print(f"강원 전용 정책 수(전체): {len(df_region)}")
    print(f"강원 전용 + UI 모집중: {len(df_active)}")
    print(f"plcyNo 기준 중복 제거 후: {len(unique_by_id)}")

    print("\n상위 10개 샘플:")
    cols = [c for c in ["plcyNo", "plcyNm", "sido_set", "category"] if c in unique_by_id.columns]
    print(unique_by_id[cols].head(10))

    # ---- 4) CSV 저장 ----
    unique_by_id.to_csv(OUTPUT_FILE, encoding="utf-8-sig", index=False)
    print(f"\n💾 CSV 저장 완료: {OUTPUT_FILE}")
    print("   - 열 개수:", len(unique_by_id.columns))
    print("   - 행 개수:", len(unique_by_id))


if __name__ == "__main__":
    main()
