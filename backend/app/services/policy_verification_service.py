# app/services/policy_verification_service.py

from datetime import datetime
from typing import Any, Callable, Optional, Dict, List

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Policy, PolicyVerification, PolicyVerificationStatus
from app.services.browser_service import BrowserService

# ✅ 추가
from app.services.artifact_service import ArtifactService
from app.services.image_url_service import ImageURLService
from app.services.text_bundle_service import TextBundleService
from app.services.final_guidance_service import FinalGuidanceService


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
        BackgroundTasks 에서 호출될 동기 함수.
        - Policy / PolicyVerification 로드
        - BrowserService.verify_policy_sync() 호출
        - (MVP) 다운로드 파일+이미지URL 텍스트화 후, 최종 안내 JSON 생성
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

            # 1) browser-use 검증
            result = BrowserService.verify_policy_sync(
                policy,
                v.navigation_path,
                log_callback,
            )

            # 2) 다운로드/이미지URL 텍스트화 (MVP)
            downloads_dir = result.get("downloads_dir") or ""
            downloaded_files = result.get("downloaded_files") or []
            image_urls = result.get("image_urls") or []

            if log_callback:
                log_callback(f"[BG] 첨부파일 텍스트 추출 시작 (files={len(downloaded_files)})")

            artifacts: List[Dict[str, Any]] = []
            if downloads_dir and isinstance(downloaded_files, list) and downloaded_files:
                artifacts = ArtifactService.extract_from_downloads(
                    downloads_dir=downloads_dir,
                    downloaded_files=downloaded_files,
                    verification_id=v.id,
                )

            if log_callback:
                log_callback(f"[BG] 이미지 URL OCR 시작 (urls={len(image_urls)})")

            image_url_texts: List[Dict[str, Any]] = []
            if downloads_dir and isinstance(image_urls, list) and image_urls:
                # ImageURLService는 async -> 여기서는 동기로 돌리기 위해 asyncio.run 사용
                import asyncio as _asyncio

                image_url_texts = _asyncio.run(
                    ImageURLService.ocr_from_urls(
                        image_urls=image_urls,
                        downloads_dir=downloads_dir,
                        verification_id=v.id,
                    )
                )

            # 3) 번들 만들기
            if log_callback:
                log_callback("[BG] 번들 텍스트 생성 중...")

            bundle = TextBundleService.build_bundle(
                policy=policy,
                browser_result=result,
                artifacts=artifacts,
                image_url_texts=image_url_texts,
            )
            bundle_text = bundle.get("bundle_text") or ""

            # 4) 최종 사용자 안내 생성(Gemini)
            if log_callback:
                log_callback("[BG] 최종 신청 안내 생성(Gemini) 중...")

            final_guidance = FinalGuidanceService.generate_final_guidance(
                policy_title=policy.title or "",
                policy_url=result.get("source_url") or policy.target_url or "",
                bundle_text=bundle_text,
            )

            # 5) DB 저장(마이그레이션 최소화: extracted_criteria에 통째로 넣기)
            v.status = PolicyVerificationStatus.SUCCESS.value

            v.extracted_criteria = {
                # ✅ 기존 Deep Track facts
                "criteria": result.get("criteria") or {},
                "required_documents": result.get("required_documents") or [],
                "apply_steps": result.get("apply_steps") or [],
                "apply_channel": result.get("apply_channel"),
                "apply_period": result.get("apply_period"),
                "contact": result.get("contact") or {},

                # ✅ MVP 확장 결과
                "downloaded_files": downloaded_files,
                "image_urls": image_urls,
                "artifacts_extracted": artifacts,          # 파일별 추출 결과(텍스트 포함)
                "image_url_texts": image_url_texts,        # URL OCR 결과
                "bundle_stats": bundle.get("stats") or {}, # 번들 통계
                "final_guidance": final_guidance,          # 사용자에게 보여줄 최종 JSON
            }

            v.evidence_text = result.get("evidence_text")
            # navigation_path는 “주입 제거”했을 수 있으니 그대로 저장
            v.navigation_path = result.get("navigation_path")
            v.last_verified_at = datetime.utcnow()
            v.error_message = result.get("error_message")

            db.add(v)
            db.commit()

            print(f"[BG] 검증+요약 완료 (verification_id={v.id})")
            if log_callback:
                log_callback("[BG] 검증+요약 완료 (SUCCESS)")
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
