# app/routers/policies.py
import asyncio
from datetime import datetime
from typing import List, Optional
import base64
from typing import Awaitable, Callable, Optional as Opt
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
    Query,
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
logger = logging.getLogger(__name__)

# ===== Fast Track: 검색 & Eligibility =====
@router.get("/search", response_model=List[PolicySearchResult])
def search_policies(
    query: Optional[str] = Query(None),
    age: Optional[int] = Query(None),
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = PolicySearchRequest(
        query=query,
        age=age,
        region=region,
        category=category,
    )
    return PolicyService.search_policies(db, req)

# ✅ 검색 → 기준 + 유사 5개 한 번에 받기
@router.get("/search_with_similar", response_model=SimilarPoliciesResponse)
def search_policies_with_similar(
    query: Optional[str] = Query(None),
    age: Optional[int] = Query(None),
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    사용자가 처음 검색했을 때 쓰는 엔드포인트.

    - query / age / region / category 로 검색
    - 가장 잘 맞는 기준 정책 1개 + 그와 유사한 정책 5개를 한 번에 반환
    """
    req = PolicySearchRequest(
        query=query,
        age=age,
        region=region,
        category=category,
    )

    # 🔥 디버깅용 (한 번만 찍어보고 확인)
    logger.info("[search_with_similar] req=%s", req.model_dump())

    result = PolicyService.search_policies_with_similars(db, req)
    if result is None:
        return SimilarPoliciesResponse(base_policy=None, similar_policies=[])
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

    verification_payload = None
    if v:
        verification_payload = {
            "policy_id": policy_id,
            "verification_id": v.id,  # ✅ 핵심: 스키마가 요구하는 이름으로 매핑
            "status": PolicyVerificationStatusEnum(v.status),
            "last_verified_at": v.last_verified_at,
            "evidence_text": v.evidence_text,
            "extracted_criteria": v.extracted_criteria,
            "navigation_path": v.navigation_path,
            "error_message": v.error_message,
        }

    return {
        "policy": policy,
        "verification": verification_payload,
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

# ===== Deep Track: WebSocket (실시간 로그 + 스크린샷) =====
@router.websocket("/ws/{policy_id}/verify")
async def ws_verify(websocket: WebSocket, policy_id: int):
    await websocket.accept()

    done_event = asyncio.Event()

    # ✅ 안전 송신(끊긴 뒤 send로 터지는 것 방지)
    async def safe_send(payload: dict) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except Exception:
            return False

    async def log_callback(msg: str):
        ok = await safe_send({"type": "log", "message": msg})
        if not ok:
            raise WebSocketDisconnect()

    async def screenshot_callback(b64: str):
        # ✅ 프론트/백엔드 키 불일치 방지: 둘 다 전송
        ok = await safe_send({"type": "screenshot", "image": b64, "image_b64": b64})
        if not ok:
            raise WebSocketDisconnect()

    async def job():
        from app.db import SessionLocal
        from app.services.browser_service import BrowserService

        db = SessionLocal()
        try:
            policy = db.get(Policy, policy_id)
            if not policy:
                await safe_send({"type": "error", "message": "Policy not found"})
                return

            v = PolicyVerificationService.get_or_create_verification(db, policy_id)
            v.status = PolicyVerificationStatus.PENDING.value
            v.error_message = None
            db.add(v)
            db.commit()
            db.refresh(v)

            await log_callback("WebSocket 검증 작업 시작")  # ✅ 이게 프론트에 떠야 정상

            navigation_path = v.navigation_path
            if navigation_path:
                result = await BrowserService.verify_policy_with_playwright_shortcut(
                    policy, navigation_path, log_callback, screenshot_callback
                )
            else:
                result = await BrowserService.verify_policy_with_agent(
                    policy, log_callback, screenshot_callback
                )

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

            await safe_send(
                {
                    "type": "done",
                    "status": "SUCCESS",
                    "verification_id": v.id,
                    "extracted_criteria": v.extracted_criteria,
                    "evidence_text": v.evidence_text,
                    "navigation_path": v.navigation_path,
                    "final_url": result.get("final_url")
                    or result.get("source_url")
                    or result.get("target_url"),
                }
            )

        except WebSocketDisconnect:
            # 프론트가 끊은 경우 조용히 종료
            return
        except Exception as e:
            # ✅ 여기서 에러를 프론트에도 보내고, DB에도 기록
            try:
                v = PolicyVerificationService.get_or_create_verification(db, policy_id)
                v.status = PolicyVerificationStatus.FAILED.value
                v.error_message = str(e)
                v.last_verified_at = datetime.utcnow()
                db.merge(v)
                db.commit()
            except Exception:
                pass
            await safe_send({"type": "done", "status": "FAILED", "error": str(e)})
        finally:
            db.close()
            done_event.set()

    task = asyncio.create_task(job())

    # ✅ task에서 터진 예외를 서버 로그로 강제 출력(중요!)
    def _on_done(t: asyncio.Task):
        try:
            exc = t.exception()
            if exc:
                logger.exception("[ws_verify] job task crashed: %s", exc)
        except Exception:
            pass

    task.add_done_callback(_on_done)

    try:
        # ✅ ws 핸들러가 끝나면 연결도 끝나버릴 수 있음 → 끝날 때까지 대기
        await done_event.wait()
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass