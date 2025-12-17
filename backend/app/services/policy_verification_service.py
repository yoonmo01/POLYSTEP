# app/services/policy_verification_service.py

from datetime import datetime
from typing import Any, Callable, Optional, Dict, List
import os

import traceback
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
    def _decide_status_from_browser_result(result: Dict[str, Any]) -> tuple[str, str]:
        """
        browser_service 결과를 보고 SUCCESS/FAILED를 결정.
        - matched != True 이거나 needs_review=True 이거나 error_message가 있으면 FAILED로 둔다.
        (지금은 enum에 NEEDS_REVIEW가 없다고 가정 → FAILED로 통일)
        """
        matched = result.get("matched")
        needs_review = bool(result.get("needs_review"))
        err = (result.get("error_message") or "").strip()

        # ✅ (추가) browser_service 휴리스틱으로 '정책 못 찾음'이 들어온 케이스
        if err == "POLICY_NOT_FOUND":
            return (PolicyVerificationStatus.FAILED.value, "policy not found on the provided site (POLICY_NOT_FOUND)")

        # ✅ 명시적 성공 조건: matched == True AND needs_review == False AND error 없음
        if matched is True and (not needs_review) and (not err):
            return (PolicyVerificationStatus.SUCCESS.value, "")

        # ✅ 실패/검토 필요 사유를 사람이 보기 좋게 정리
        reasons: List[str] = []
        if matched is not True:
            reasons.append(f"matched={matched!r}")
        if needs_review:
            reasons.append("needs_review=True")
        if err:
            reasons.append(f"error_message={err}")

        reason_text = " | ".join(reasons) if reasons else "verification not successful"
        return (PolicyVerificationStatus.FAILED.value, reason_text)

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

            # ✅ 시작 시점에 상태를 RUNNING처럼 보이게(없으면 PENDING 유지해도 OK)
            # enum에 RUNNING이 없을 수 있으니 건드리지 않음
            # v.status = PolicyVerificationStatus.PENDING.value
            if log_callback:
                log_callback(f"[BG] 검증 시작 (policy_id={policy.id}, verification_id={v.id})")
            print(f"[BG] 검증 시작 (policy_id={policy.id}, verification_id={v.id})")

            # 1) browser-use 검증
            result = BrowserService.verify_policy_sync(
                policy,
                v.navigation_path,
                log_callback,
            )

            # ✅ 여기서 먼저 상태 판정(타임아웃인데 SUCCESS로 저장되는 문제 방지)
            decided_status, status_reason = PolicyVerificationService._decide_status_from_browser_result(result)
            if log_callback:
                log_callback(f"[BG] browser_result status: {decided_status} ({status_reason})")
 
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

            # ✅ 변경: "사진은 무조건 URL 방식"
            # - 기본은 OCR/다운로드를 하지 않는다. (카드뉴스/바로보기 이미지는 URL만 저장해서 프론트에서 바로 보여주기)
            # - 필요할 때만 ENABLE_IMAGE_OCR=true 로 켤 수 있게 게이트를 둔다.
            enable_image_ocr = os.getenv("ENABLE_IMAGE_OCR", "false").lower() in ("1", "true", "yes", "y", "on")
            image_url_texts: List[Dict[str, Any]] = []
            if enable_image_ocr and downloads_dir and isinstance(image_urls, list) and image_urls:
                if log_callback:
                    log_callback(f"[BG] 이미지 URL OCR 시작 (urls={len(image_urls)})")
                import asyncio as _asyncio
                image_url_texts = _asyncio.run(
                    ImageURLService.ocr_from_urls(
                        image_urls=image_urls,
                        downloads_dir=downloads_dir,
                        verification_id=v.id,
                    )
                )
            else:
                if log_callback:
                    log_callback(f"[BG] 이미지 OCR 스킵(URL만 저장) (urls={len(image_urls)})")

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
            v.status = decided_status

            v.extracted_criteria = {
                # ✅ UI에서 쓰는 식별자: id는 빼고 policy_id / verification_id만 유지
                "policy_id": policy.id,
                "verification_id": v.id,
                
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
                # ✅ 상태 판정 근거(디버깅용)
                "verification_status_reason": status_reason,
            }

            v.evidence_text = result.get("evidence_text")
            # navigation_path는 “주입 제거”했을 수 있으니 그대로 저장
            v.navigation_path = result.get("navigation_path")
            v.last_verified_at = datetime.utcnow()
            # ✅ error_message 덮어쓰기 방지:
            # - browser_service의 error_message가 있으면 우선 사용
            # - 없으면 status_reason(FAILED 사유)을 사용
            browser_err = (result.get("error_message") or "").strip()
            final_err = browser_err or (status_reason or "").strip()
            v.error_message = final_err if final_err else None

            db.add(v)
            db.commit()

            print(f"[BG] 검증+요약 완료 (verification_id={v.id})")
            if log_callback:
                log_callback(f"[BG] 검증+요약 완료 ({v.status})")
        except Exception as e:
            print(f"[BG] 검증 실패 (verification_id={verification_id}): {e}")
            try:
                v = db.get(PolicyVerification, verification_id)
                if v:
                    v.status = PolicyVerificationStatus.FAILED.value
                    v.error_message = f"{e}\n{traceback.format_exc()}"
                    v.last_verified_at = datetime.utcnow()
                    db.add(v)
                    db.commit()
            finally:
                if log_callback:
                    log_callback(f"[BG] 검증 실패: {e}")
        finally:
            db.close()
