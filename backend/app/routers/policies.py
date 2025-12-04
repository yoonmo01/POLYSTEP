# backend/app/routers/policies.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import get_current_user
from ..models import PolicySearchLog, User
from ..services.policy_service import run_search_pipeline

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/search", response_model=schemas.PolicySearchResponse)
async def search_policies(
    req: schemas.PolicySearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    3~8 단계 전체를 수행:
    - browser-use + Gemini로 실시간 검색/수집
    - 파일 텍스트 처리
    - Gemini로 요약 + step-by-step 생성
    """
    result = await run_search_pipeline(req, current_user, db)

    # 검색 로그 저장 (간단 버전)
    log = PolicySearchLog(
        user_id=current_user.id,
        query=req.query,
        category=req.filters.category if req.filters else None,
        region=req.filters.region if req.filters else None,
        summary_title=result.summary.title,
        summary_text=result.summary.summary,
        # steps_json은 나중에 필요하면 직렬화해서 저장
    )
    db.add(log)
    db.commit()

    return result
