# app/routers/policies.py
import asyncio
from datetime import datetime  # 🔥 추가
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.schemas import (
    PolicySearchRequest,
    PolicySearchResult,
    PolicyVerificationRequest,
    PolicyVerificationStatusResponse,
    PolicyVerificationResponse,
    PolicyVerificationStatusEnum,
    PolicyDetailResponse,          # 🔥 추가
    SimilarPoliciesResponse,
    UserGuideRequest,
    UserGuideResponse,
)
from app.models import Policy, PolicyVerification, PolicyVerificationStatus
from app.services.policy_service import PolicyService
from app.services.policy_verification_service import PolicyVerificationService
from app.services.llm_service import LLMService

router = APIRouter()


# ===== Fast Track: 검색 & Eligibility =====
@router.get("/search", response_model=List[PolicySearchResult])
def search_policies(
    req: PolicySearchRequest = Depends(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return PolicyService.search_policies(db, req)

# ✅ 검색 → 기준 + 유사 5개 한 번에 받기
@router.get("/search_with_similar", response_model=SimilarPoliciesResponse)
def search_policies_with_similar(
    req: PolicySearchRequest = Depends(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    사용자가 처음 검색했을 때 쓰는 엔드포인트.

    - query / age / region / category 로 검색
    - 가장 잘 맞는 기준 정책 1개 + 그와 유사한 정책 5개를 한 번에 반환
    """
    result = PolicyService.search_policies_with_similars(db, req)
    if result is None:
        raise HTTPException(status_code=404, detail="No policies found")
    return result

@router.get("/{policy_id}", response_model=PolicyDetailResponse)
def get_policy_detail(
    policy_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    v = (
        db.query(PolicyVerification)
        .filter(PolicyVerification.policy_id == policy_id)
        .order_by(PolicyVerification.last_verified_at.desc().nullslast())
        .first()
    )

    # 🔥 여기서 그냥 ORM 객체를 반환해도 됨
    # PolicyRead / PolicyVerificationResponse 둘 다 from_attributes=True라
    # Pydantic이 알아서 변환해준다.
    return {
        "policy": policy,
        "verification": v,
    }



# ===== Fast Track: 기준 정책 + 유사 정책 5개 =====
@router.get("/{policy_id}/similar", response_model=SimilarPoliciesResponse)
def get_similar_policies(
    policy_id: int,
    age: Optional[int] = None,
    region: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    기준이 되는 정책(policy_id) 하나와,
    그와 유사한 정책 5개 정도를 함께 반환한다.

    - age, region, category는 사용자의 조건(검색 조건)을 그대로 받아서
      Fast Track LLM 평가에 다시 사용한다.
    """
    req = PolicySearchRequest(
        query=None,
        age=age,
        region=region,
        category=category,
    )

    result = PolicyService.get_policy_with_similars(db, policy_id, req)
    if result is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    return result

# ===== Deep Track: REST + BackgroundTasks =====
@router.post("/{policy_id}/verify", response_model=PolicyVerificationStatusResponse)
def request_verification(
    policy_id: int,
    body: PolicyVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # 현재 최신 검증 레코드
    v = (
        db.query(PolicyVerification)
        .filter(PolicyVerification.policy_id == policy_id)
        .order_by(PolicyVerification.created_at.desc())
        .first()
    )

    if v and v.status == PolicyVerificationStatus.PENDING.value and not body.force:
        return PolicyVerificationStatusResponse(
            status=PolicyVerificationStatusEnum.PENDING,
            message="이미 검증이 진행 중입니다.",
            verification_id=v.id,
            cached=False,
            last_verified_at=v.last_verified_at,
        )

    # 새로운 검증 레코드 준비 (또는 기존거 재사용)
    v = PolicyVerificationService.get_or_create_verification(db, policy_id)
    v.status = PolicyVerificationStatus.PENDING.value
    v.error_message = None
    db.add(v)
    db.commit()
    db.refresh(v)

    # 🔥 여기서는 "id만" 넘긴다!
    background_tasks.add_task(
        PolicyVerificationService.run_verification_job_sync,
        v.id,
    )

    return PolicyVerificationStatusResponse(
        status=PolicyVerificationStatusEnum.PENDING,
        message="검증 작업이 시작되었습니다.",
        verification_id=v.id,
        cached=False,
        last_verified_at=v.last_verified_at,
    )


@router.get("/{policy_id}/verification", response_model=PolicyVerificationResponse)
def get_verification_result(
    policy_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    v = (
        db.query(PolicyVerification)
        .filter(PolicyVerification.policy_id == policy_id)
        .order_by(PolicyVerification.created_at.desc())
        .first()
    )
    if not v:
        raise HTTPException(status_code=404, detail="Verification not found")

    return PolicyVerificationResponse(
        policy_id=policy_id,
        verification_id=v.id,
        status=PolicyVerificationStatusEnum(v.status),
        last_verified_at=v.last_verified_at,
        evidence_text=v.evidence_text,
        extracted_criteria=v.extracted_criteria,
        navigation_path=v.navigation_path,
        error_message=v.error_message,
    )


# ===== Deep Track: WebSocket (실시간 로그) =====
@router.websocket("/ws/{policy_id}/verify")
async def ws_verify(websocket: WebSocket, policy_id: int):
    await websocket.accept()

    from app.db import SessionLocal
    db = SessionLocal()

    try:
        policy = db.get(Policy, policy_id)
        if not policy:
            await websocket.send_json(
                {"type": "error", "message": "Policy not found"}
            )
            await websocket.close()
            return

        v = PolicyVerificationService.get_or_create_verification(db, policy_id)
        v.status = PolicyVerificationStatus.PENDING.value
        v.error_message = None
        db.add(v)
        db.commit()
        db.refresh(v)

        async def log_callback(msg: str):
            await websocket.send_json({"type": "log", "message": msg})

        async def job():
            from app.services.browser_service import BrowserService

            try:
                await log_callback("WebSocket 검증 작업 시작")

                async def runner():
                    navigation_path = v.navigation_path
                    if navigation_path:
                        return await BrowserService.verify_policy_with_playwright_shortcut(
                            policy, navigation_path, log_callback
                        )
                    return await BrowserService.verify_policy_with_agent(
                        policy, log_callback
                    )

                result = await runner()

                v.status = PolicyVerificationStatus.SUCCESS.value
                v.extracted_criteria = {
                    "criteria": result.get("criteria") or {},
                    "required_documents": result.get("required_documents") or [],
                    "apply_steps": result.get("apply_steps") or [],
                    "apply_channel": result.get("apply_channel"),
                    "apply_period": result.get("apply_period"),
                    "contact": result.get("contact") or {},
                }
                v.evidence_text = result.get("evidence_text")
                v.navigation_path = result.get("navigation_path")
                v.last_verified_at = datetime.utcnow()
                v.error_message = None

                db.merge(v)
                db.commit()

                await websocket.send_json(
                    {
                        "type": "done",
                        "status": "SUCCESS",
                        "verification_id": v.id,
                        "extracted_criteria": v.extracted_criteria,
                        "evidence_text": v.evidence_text,
                        "navigation_path": v.navigation_path,
                    }
                )
            except Exception as e:
                v.status = PolicyVerificationStatus.FAILED.value
                v.error_message = str(e)
                v.last_verified_at = datetime.utcnow()
                db.merge(v)
                db.commit()

                await websocket.send_json(
                    {
                        "type": "done",
                        "status": "FAILED",
                        "error": str(e),
                    }
                )
            finally:
                await websocket.close()
                db.close()

        asyncio.create_task(job())
    except WebSocketDisconnect:
        db.close()
