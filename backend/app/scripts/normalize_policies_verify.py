# import pandas as pd

# FILE_PATH = "C:/POLYSTEP/youth_policies_enriched.csv"

# def main():
#     print("🔍 Loading file...")
#     df = pd.read_csv(FILE_PATH, encoding="utf-8-sig")

#     print("\n=== 1) 전체 데이터 개수 ===")
#     print(len(df))

#     print("\n=== 2) 컬럼 존재 여부 체크 ===")
#     required_cols = [
#         "zip_first",
#         "sido_name",
#         "is_seoul",
#         "is_gyeonggi",
#         "category_raw_l",
#         "category_raw_m",
#         "category",
#     ]

#     for col in required_cols:
#         print(f"{col:20} → {'OK' if col in df.columns else '❌ MISSING'}")

#     print("\n=== 3) 지역 매핑 샘플 확인 (상위 5개) ===")
#     print(df[["zipCd", "zip_first", "sido_name", "is_seoul", "is_gyeonggi"]].head())

#     print("\n=== 4) 시도별 정책 개수 (Top 10) ===")
#     print(df["sido_name"].value_counts().head(10))

#     print("\n=== 5) 서울/경기 정책 개수 ===")
#     seoul_cnt = df["is_seoul"].sum()
#     gyeonggi_cnt = df["is_gyeonggi"].sum()
#     print(f"서울 정책 수: {seoul_cnt}")
#     print(f"경기 정책 수: {gyeonggi_cnt}")
#     print(f"서울+경기 합계: {seoul_cnt + gyeonggi_cnt}")

#     print("\n=== 6) 카테고리 분포 확인 ===")
#     print(df["category"].value_counts())

#     print("\n=== 7) 카테고리 + 지역 조합 확인 (서울/경기만) ===")
#     seoul_gg = df[df["is_seoul"] | df["is_gyeonggi"]]
#     print(seoul_gg["category"].value_counts())

#     print("\n=== 8) 샘플 10개 자세히 보기 ===")
#     print(df[["plcyNo", "plcyNm", "sido_name", "category"]].head(10))

#     print("\n🎉 검증 완료! 문제가 있어 보이는 부분은 위 출력에서 확인해줘.")


# if __name__ == "__main__":
#     main()


# import pandas as pd

# df = pd.read_csv("youth_policies_enriched.csv", encoding="utf-8-sig")

# print("전체 행 수:", len(df))

# # plcyNo 기준으로 유니크 개수
# unique_plcy = df["plcyNo"].nunique()
# print("고유 plcyNo 개수:", unique_plcy)

# if unique_plcy == len(df):
#     print("✅ plcyNo 기준으로 완전히 유니크 → 1549 = 1549개 정책")
# else:
#     print("⚠ plcyNo 중복 있음!")
#     dup = df[df.duplicated("plcyNo", keep=False)].sort_values("plcyNo")
#     print("중복 정책 번호 예시:")
#     print(dup[["plcyNo", "plcyNm", "sido_name"]].head(20))

import pandas as pd

FILE_PATH = "C:/POLYSTEP/youth_policies_gangwon_enriched.csv"

def main():
    print("🔍 Loading file...")
    df = pd.read_csv(FILE_PATH, encoding="utf-8-sig")

    print("\n=== 1) 전체 데이터 개수 ===")
    print(len(df))

    print("\n=== 2) 컬럼 존재 여부 체크 ===")
    required_cols = [
        "zip_first",
        "sido_name",
        "sido_set",
        "has_gangwon",
        "is_gangwon_only",
        "category_raw_l",
        "category_raw_m",
        "category",
    ]
    for col in required_cols:
        print(f"{col:20} → {'OK' if col in df.columns else '❌ MISSING'}")

    print("\n=== 3) 지역 매핑 샘플 확인 (상위 8개) ===")
    print(df[["zipCd", "zip_first", "sido_name", "sido_set", "has_gangwon", "is_gangwon_only"]].head(8))

    print("\n=== 4) (참고) 대표 sido_name 기준 분포 (Top 10) ===")
    print(df["sido_name"].value_counts().head(10))

    print("\n=== 5) 강원 포함/전용 개수 ===")
    has_cnt = int(df["has_gangwon"].sum())
    only_cnt = int(df["is_gangwon_only"].sum())
    print(f"강원 포함(has_gangwon=True): {has_cnt}")
    print(f"강원 전용(is_gangwon_only=True): {only_cnt}")
    print(f"강원 포함이지만 전용은 아닌 정책: {has_cnt - only_cnt}")

    print("\n=== 6) 카테고리 분포 확인 ===")
    print(df["category"].value_counts())

    print("\n=== 7) 강원 전용만 카테고리 분포 ===")
    only_df = df[df["is_gangwon_only"] == True]
    print(only_df["category"].value_counts())

    print("\n=== 8) plcyNo 중복 체크 ===")
    unique_plcy = df["plcyNo"].nunique()
    print("전체 행 수:", len(df))
    print("고유 plcyNo 개수:", unique_plcy)

    if unique_plcy == len(df):
        print("✅ plcyNo 기준으로 완전히 유니크")
    else:
        print("⚠ plcyNo 중복 있음!")
        dup = df[df.duplicated("plcyNo", keep=False)].sort_values("plcyNo")
        print("중복 정책 번호 예시:")
        print(dup[["plcyNo", "plcyNm", "sido_name", "sido_set"]].head(20))

    print("\n🎉 검증 완료!")


if __name__ == "__main__":
    main()
