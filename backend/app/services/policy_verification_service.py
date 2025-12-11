# app/services/policy_verification_service.py

from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Policy, PolicyVerification, PolicyVerificationStatus
from app.services.browser_service import BrowserService


class PolicyVerificationService:
    @staticmethod
    def get_or_create_verification(db: Session, policy_id: int) -> PolicyVerification:
        """
        해당 정책에 대한 최신 검증 레코드가 있으면 리턴,
        없으면 새로 하나 만들어서 리턴.
        """
        v = (
            db.query(PolicyVerification)
            .filter(PolicyVerification.policy_id == policy_id)
            .order_by(PolicyVerification.created_at.desc())
            .first()
        )
        if v:
            return v

        v = PolicyVerification(
            policy_id=policy_id,
            status=PolicyVerificationStatus.PENDING.value,
            created_at=datetime.utcnow(),
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        return v

    @staticmethod
    def run_verification_job_sync(
        verification_id: int,
        log_callback: Optional[Callable[[str], Any]] = None,
    ) -> None:
        """
        ⚙️ BackgroundTasks 에서 호출될 동기 함수.
        - 여기서 SessionLocal()로 DB 세션을 새로 열고
        - Policy / PolicyVerification 로드
        - BrowserService.verify_policy_sync() 호출
        - 결과를 PolicyVerification에 업데이트
        """
        db = SessionLocal()
        try:
            v = db.get(PolicyVerification, verification_id)
            if not v:
                return

            policy = db.get(Policy, v.policy_id)
            if not policy:
                v.status = PolicyVerificationStatus.FAILED.value
                v.error_message = "Policy not found"
                v.last_verified_at = datetime.utcnow()
                db.commit()
                return

            if log_callback:
                log_callback(f"[BG] 검증 시작 (policy_id={policy.id}, verification_id={v.id})")
            print(f"[BG] 검증 시작 (policy_id={policy.id}, verification_id={v.id})")

            # 🔥 지금은 테스트용 더미 구현을 사용 (browser_use 나중에 교체)
            result = BrowserService.verify_policy_sync(
                policy,
                v.navigation_path,
                log_callback,
            )

            v.status = PolicyVerificationStatus.SUCCESS.value
            v.extracted_criteria = result.get("criteria")
            v.evidence_text = result.get("evidence_text")
            v.navigation_path = result.get("navigation_path")
            v.last_verified_at = datetime.utcnow()
            v.error_message = None

            db.add(v)
            db.commit()

            print(f"[BG] 검증 완료 (verification_id={v.id})")
            if log_callback:
                log_callback("[BG] 검증 완료 (SUCCESS)")
        except Exception as e:
            print(f"[BG] 검증 실패 (verification_id={verification_id}): {e}")
            try:
                v = db.get(PolicyVerification, verification_id)
                if v:
                    v.status = PolicyVerificationStatus.FAILED.value
                    v.error_message = str(e)
                    v.last_verified_at = datetime.utcnow()
                    db.add(v)
                    db.commit()
            finally:
                if log_callback:
                    log_callback(f"[BG] 검증 실패: {e}")
        finally:
            db.close()
