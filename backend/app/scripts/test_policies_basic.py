# backend/app/scripts/test_policies_basic.py

from app.db import SessionLocal
from app.models import Policy


def main():
    session = SessionLocal()

    try:
        total = session.query(Policy).count()
        print(f"📊 총 Policy 레코드 수: {total}")

        print("\n=== 상위 5개 정책 ===")
        policies = (
            session.query(Policy)
            .order_by(Policy.id.asc())
            .limit(5)
            .all()
        )

        for p in policies:
            print("-" * 60)
            print(f"id           : {p.id}")
            print(f"policy_id    : {p.policy_id}")
            print(f"title        : {p.title}")
            print(f"category     : {p.category} / {p.category_l} / {p.category_m}")
            print(f"region       : {p.region} ({p.region_zip_first})")
            print(f"age_min~max  : {p.age_min} ~ {p.age_max}")
            print(f"apply_type   : {p.apply_period_type}")
            print(f"biz_start/end: {p.biz_start} ~ {p.biz_end}")
            print(f"target_url   : {p.target_url}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
