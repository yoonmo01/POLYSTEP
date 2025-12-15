import pandas as pd

# === 파일 경로만 네 환경에 맞게 수정 ===
FILE_GANGWON_ONLY = "C:/POLYSTEP/policies_cleaned_final_gangwon_only.csv"
FILE_MAIN = "C:/POLYSTEP/policies_cleaned_final.csv"  # (서울/경기 등 기존 파일)

def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")

def main():
    df_gw = load_csv(FILE_GANGWON_ONLY)
    df_main = load_csv(FILE_MAIN)

    # ---------------------------
    # 1) 컬럼(헤더) 이름 검증
    # ---------------------------
    cols_gw = list(df_gw.columns)
    cols_main = list(df_main.columns)

    set_gw = set(cols_gw)
    set_main = set(cols_main)

    only_in_gw = sorted(set_gw - set_main)
    only_in_main = sorted(set_main - set_gw)

    print("=== 1) 컬럼 비교 ===")
    print(f"- gangwon_only cols: {len(cols_gw)}")
    print(f"- main cols       : {len(cols_main)}")

    if not only_in_gw and not only_in_main:
        print("✅ 컬럼 이름 세트는 동일합니다. (순서만 다를 수 있음)")
    else:
        print("⚠ 컬럼 이름 차이가 있습니다.")
        if only_in_gw:
            print("  - gangwon_only에만 있는 컬럼:", only_in_gw)
        if only_in_main:
            print("  - main에만 있는 컬럼:", only_in_main)

    # 순서까지 완전 동일한지
    if cols_gw == cols_main:
        print("✅ 컬럼 순서까지 완전 동일합니다.")
    else:
        print("ℹ 컬럼 순서가 다릅니다. (DB insert 전에 순서 맞추면 됨)")

    # ---------------------------
    # 2) policy_id 고유성(중복) 자체 체크
    # ---------------------------
    print("\n=== 2) 각 파일 내부 policy_id 유니크 체크 ===")
    print(f"- gangwon_only rows: {len(df_gw)}, unique policy_id: {df_gw['policy_id'].nunique()}")
    print(f"- main        rows: {len(df_main)}, unique policy_id: {df_main['policy_id'].nunique()}")

    # ---------------------------
    # 3) 두 파일 간 중복 정책(policy_id) 비교
    # ---------------------------
    print("\n=== 3) 두 파일 간 중복(policy_id) 비교 ===")
    gw_ids = set(df_gw["policy_id"].astype(str).str.strip())
    main_ids = set(df_main["policy_id"].astype(str).str.strip())

    dup_ids = sorted(gw_ids & main_ids)
    print(f"- 중복 policy_id 개수: {len(dup_ids)}")

    # 강원_only에서 제거 대상(= main에도 이미 존재)
    print(f"- gangwon_only에서 빼야 하는 건수: {len(dup_ids)}개")
    print(f"- main에서 빼야 하는 건수(반대로 빼고 싶다면): {len(dup_ids)}개")

    # 중복 샘플 10개 출력(정책명 같이)
    if dup_ids:
        print("\n--- 중복 샘플 10개 (policy_id, gangwon_title, main_title) ---")
        gw_map = df_gw.set_index(df_gw["policy_id"].astype(str).str.strip())["title"].to_dict()
        main_map = df_main.set_index(df_main["policy_id"].astype(str).str.strip())["title"].to_dict()

        for pid in dup_ids[:10]:
            print(f"{pid} | GW: {gw_map.get(pid, '')} | MAIN: {main_map.get(pid, '')}")

    # ---------------------------
    # 4) (선택) 중복 제거 후 병합 파일 만들기
    #    - 기본 전략: MAIN을 기준으로 유지하고, GW_ONLY에서 중복 제거 후 append
    # ---------------------------
    print("\n=== 4) (선택) 중복 제거 후 병합 미리보기 ===")
    df_gw["policy_id_norm"] = df_gw["policy_id"].astype(str).str.strip()
    df_main["policy_id_norm"] = df_main["policy_id"].astype(str).str.strip()

    df_gw_dedup = df_gw[~df_gw["policy_id_norm"].isin(df_main["policy_id_norm"])].copy()
    merged = pd.concat([df_main.drop(columns=["policy_id_norm"]), df_gw_dedup.drop(columns=["policy_id_norm"])], ignore_index=True)

    print(f"- gangwon_only 원본: {len(df_gw)}")
    print(f"- gangwon_only 중복 제거 후 추가 가능한 수: {len(df_gw_dedup)}")
    print(f"- merged 총 행 수: {len(merged)} (main {len(df_main)} + add {len(df_gw_dedup)})")

    # 필요하면 저장 (원하면 주석 해제)
    # OUT_PATH = "C:/POLYSTEP/policies_cleaned_final_merged_dedup.csv"
    # merged.to_csv(OUT_PATH, encoding="utf-8-sig", index=False)
    # print(f"💾 저장 완료: {OUT_PATH}")

if __name__ == "__main__":
    main()
