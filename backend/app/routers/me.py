# app/routers/me.py
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models import (
    User,
    Policy,
    PolicyVerification,
    RecommendationSession,
    RecommendationItem,
    PolicyView,
)
from app.schemas import (
    MeResponse,
    RecommendationCreateRequest,
    RecommendationSessionResponse,
    RecommendationItemOut,
    ViewCreateRequest,
    ViewListResponse,
    ViewItemOut,
    BadgeStatus,
    PolicyVerificationStatusEnum,
)

router = APIRouter()


@router.get("", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user)):
    # User 모델에는 full_name만 있어서 name으로 매핑
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.full_name,
        age=getattr(user, "age", None),
        region=getattr(user, "region", None),
        is_student=user.is_student,
        academic_status=user.academic_status,
        major=user.major,
        grade=user.grade,
        gpa=user.gpa,
        created_at=user.created_at,
    )


@router.post("/recommendations")
def create_recommendation_session(
    body: RecommendationCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 1) 세션 생성
    sess = RecommendationSession(
        user_id=user.id,
        conditions=body.conditions or {},
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    # 2) 아이템 생성 (Top5)
    items = []
    for r in body.results:
        items.append(
            RecommendationItem(
                session_id=sess.id,
                policy_id=r.policy_id,
                badge_status=(r.badge_status.value if r.badge_status else None),
                score=r.score,
            )
        )
    db.add_all(items)
    db.commit()

    return {"ok": True, "session_id": sess.id}


@router.get("/recommendations", response_model=RecommendationSessionResponse)
def get_recent_recommendations(
    limit: int = Query(1, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 최신 세션 1개만 프론트에서 쓰는 형태(기본)
    sess = (
        db.query(RecommendationSession)
        .filter(RecommendationSession.user_id == user.id)
        .order_by(RecommendationSession.created_at.desc())
        .first()
    )
    if not sess:
        return RecommendationSessionResponse(created_at=None, conditions=None, items=[])

    # 세션 아이템들 + 정책 join
    q = (
        db.query(RecommendationItem, Policy)
        .join(Policy, Policy.id == RecommendationItem.policy_id)
        .filter(RecommendationItem.session_id == sess.id)
        .order_by(RecommendationItem.id.asc())
    )

    items_out = []
    for item, policy in q.all():
        # ✅ 추천 저장 시점의 badge_status를 그대로 사용
        items_out.append(
            RecommendationItemOut(
                policy_id=policy.id,
                title=policy.title,
                category=policy.category,
                category_l=policy.category_l,
                category_m=policy.category_m,
                region=policy.region,
                badge_status=BadgeStatus(item.badge_status) if item.badge_status else None,
                score=item.score,
            )
        )

    return RecommendationSessionResponse(
        created_at=sess.created_at,
        conditions=sess.conditions,
        items=items_out,
    )


@router.post("/views")
def create_view(
    body: ViewCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = PolicyView(
        user_id=user.id,
        policy_id=body.policy_id,
        verification_id=body.verification_id,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"ok": True, "view_id": v.id}


@router.get("/views", response_model=ViewListResponse)
def get_views(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 최근 본 정책 = "검증하기 눌러서 기록된 것"
    views = (
        db.query(PolicyView)
        .filter(PolicyView.user_id == user.id)
        .order_by(PolicyView.viewed_at.desc())
        .limit(limit)
        .all()
    )
    if not views:
        return ViewListResponse(items=[])

    # policy join
    policy_ids = [x.policy_id for x in views]
    policies = (
        db.query(Policy)
        .filter(Policy.id.in_(policy_ids))
        .all()
    )
    policy_map = {p.id: p for p in policies}

    # 각 policy의 최신 verification status도 같이 보여주고 싶으면:
    # (정교하게 하려면 subquery로 최신만 뽑아야 하지만, 일단 간단히)
    ver_map = {}
    for pid in policy_ids:
        pv = (
            db.query(PolicyVerification)
            .filter(PolicyVerification.policy_id == pid)
            .order_by(PolicyVerification.created_at.desc())
            .first()
        )
        if pv:
            ver_map[pid] = pv.status

    items_out = []
    for x in views:
        p = policy_map.get(x.policy_id)
        if not p:
            continue

        st = ver_map.get(x.policy_id)
        items_out.append(
            ViewItemOut(
                policy_id=p.id,
                title=p.title,
                category=p.category,
                category_l=p.category_l,
                category_m=p.category_m,
                region=p.region,
                viewed_at=x.viewed_at,
                verification_status=PolicyVerificationStatusEnum(st) if st else None,
            )
        )

    return ViewListResponse(items=items_out)
