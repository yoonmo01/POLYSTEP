# backend/app/scripts/import_policies_from_csv.py

import pandas as pd
from datetime import datetime
from typing import Any, Optional
from app.db import SessionLocal
from app.models import Policy

CSV_PATH = "C:/POLYSTEP/policies_cleaned_final.csv"  # 🔥 필요하면 경로 수정


def clean_ymd(value: Any) -> Optional[str]:
    """
    CSV에서 읽어온 날짜(biz_start, biz_end)를
    DB 컬럼(varchar(8))에 맞는 'YYYYMMDD' 형태로 정리.

    - 20250201.0 -> 20250201
    - 2025-02-01 -> 20250201 (대시 제거)
    - NaN / "" -> None
    """
    if pd.isna(value):
        return None

    s = str(value).strip()
    if not s:
        return None

    # float 형태 '20250201.0' 처리
    if "." in s:
        s = s.split(".")[0]

    # '2025-02-01' 같은 경우 '-' 제거
    s = s.replace("-", "")

    # 맨 앞 8자리만 사용 (YYYYMMDD)
    if len(s) >= 8:
        s = s[:8]

    # 최종적으로 숫자 8자리만 남도록 체크
    if not s.isdigit() or len(s) != 8:
        return None

    return s

def to_str(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def to_int(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and pd.isna(v):
            return None
        # "18.0" 같은 것도 들어올 수 있어서 한 번 float 후 int
        return int(float(v))
    except Exception:
        return None


def to_bool_from_yn(v):
    s = to_str(v)
    if s is None:
        return None
    return s.upper() == "Y"


def to_datetime(v):
    """
    '2025-11-24 21:10:16' 같은 문자열 -> datetime
    """
    s = to_str(v)
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main():
    print(f"📥 CSV 읽는 중... ({CSV_PATH})")
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

    session = SessionLocal()
    created = 0
    updated = 0

    try:
        for _, row in df.iterrows():
            policy_id = to_str(row.get("policy_id"))
            if not policy_id:
                continue

            # 이미 있는지 확인 (policy_id 기준)
            policy = (
                session.query(Policy)
                .filter(Policy.policy_id == policy_id)
                .first()
            )

            if policy:
                updated += 1
            else:
                policy = Policy(policy_id=policy_id)
                session.add(policy)
                created += 1

            # ===== 기본 필드 =====
            policy.title = to_str(row.get("title")) or policy.title

            # 카테고리
            policy.category = to_str(row.get("category"))
            policy.category_l = to_str(row.get("category_l"))
            policy.category_m = to_str(row.get("category_m"))

            # 키워드
            policy.keywords = to_str(row.get("keywords"))

            # 지역
            policy.region = to_str(row.get("region_sido"))
            policy.region_zip_first = to_str(row.get("region_zip_first"))

            # 연령 관련
            policy.age_min = to_int(row.get("age_min"))
            policy.age_max = to_int(row.get("age_max"))
            policy.age_limit_yn = to_bool_from_yn(row.get("age_limit_yn"))

            # 소득 / 혼인
            policy.income_condition = to_str(row.get("income_condition"))
            policy.marriage_code = to_str(row.get("marriage_code"))

            # 모집/사업 기간
            policy.apply_period_type = to_str(row.get("apply_period_type"))
            policy.apply_period_raw = to_str(row.get("apply_period_raw"))
            #biz_start / biz_end는 varchar(8)이라 'YYYYMMDD'로 정리해서 저장
            policy.biz_start = clean_ymd(row.get("biz_start"))
            policy.biz_end = clean_ymd(row.get("biz_end"))

            # 기관
            policy.provider_main = to_str(row.get("provider_main"))
            policy.provider_operator = to_str(row.get("provider_operator"))

            # URL들
            apply_url = to_str(row.get("apply_url"))
            ref_url_1 = to_str(row.get("ref_url_1"))
            ref_url_2 = to_str(row.get("ref_url_2"))

            policy.apply_url = apply_url
            policy.ref_url_1 = ref_url_1
            policy.ref_url_2 = ref_url_2

            # Deep Track에서 쓸 대표 URL
            policy.target_url = apply_url or ref_url_1 or ref_url_2 or policy.target_url

            # 원문 텍스트
            policy.raw_expln = to_str(row.get("raw_expln"))
            policy.raw_support = to_str(row.get("raw_support"))
            policy.raw_snippet = to_str(row.get("raw_snippet"))
            policy.notes = to_str(row.get("notes"))

            # raw_text는 snippet + expln + support를 합쳐서 구성
            pieces = [
                policy.raw_snippet,
                policy.raw_expln,
                policy.raw_support,
            ]
            combined_text = " ".join(p for p in pieces if p)
            if combined_text:
                policy.raw_text = combined_text

            # created_at / updated_at (가능하면 CSV 기준으로 세팅, 아니면 기존 값 유지)
            created_at = to_datetime(row.get("created_at"))
            updated_at_dt = to_datetime(row.get("updated_at"))
            if created_at:
                policy.created_at = created_at
            if updated_at_dt:
                policy.updated_at = updated_at_dt

        session.commit()
        print("✅ Import 완료")
        print(f"   새로 생성: {created}개")
        print(f"   업데이트: {updated}개")

    except Exception as e:
        session.rollback()
        print("❌ Import 중 에러 발생:", e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
