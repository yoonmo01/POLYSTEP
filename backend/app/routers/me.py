# app/routers/me.py
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta, timezone
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
    RecommendationSessionsResponse,
    ViewCreateRequest,
    ViewListResponse,
    ViewItemOut,
    BadgeStatus,
    PolicyVerificationStatusEnum,
)

router = APIRouter()

# ✅ KST 변환 유틸 (응답에서만 KST로 보여주기)
KST = timezone(timedelta(hours=9))

def to_kst_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    # DB가 timestamp without time zone이면 tzinfo=None로 들어올 가능성이 큼
    # "UTC로 저장된 값"이라고 가정하고 UTC를 붙인 다음 KST로 변환
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).isoformat(timespec="seconds")


@router.get("", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user)):
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
    recent_dup = (
        db.query(RecommendationSession)
        .filter(
            RecommendationSession.user_id == user.id,
            RecommendationSession.created_at >= datetime.utcnow() - timedelta(seconds=15),
        )
        .order_by(RecommendationSession.created_at.desc())
        .first()
    )

    if recent_dup and (recent_dup.conditions or {}) == (body.conditions or {}):
        incoming_schs = body.scholarships or []

        # 1) scholarships는 항상 최신으로 덮어쓰기
        recent_dup.scholarships = incoming_schs
        db.add(recent_dup)

        # 2) items 업데이트: 기존 삭제 후 다시 저장(항상 최신 top5 유지)
        db.query(RecommendationItem).filter(
            RecommendationItem.session_id == recent_dup.id
        ).delete(synchronize_session=False)

        new_items = []
        for r in body.results:
            new_items.append(
                RecommendationItem(
                    session_id=recent_dup.id,
                    policy_id=r.policy_id,
                    badge_status=(r.badge_status.value if r.badge_status else None),
                    score=r.score,
                )
            )
        db.add_all(new_items)
        db.commit()
        return {"ok": True, "session_id": recent_dup.id, "deduped": True, "updated": True}

    sess = RecommendationSession(
        user_id=user.id,
        conditions=body.conditions or {},
        scholarships=body.scholarships or [],
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = (
        db.query(RecommendationSession)
        .filter(RecommendationSession.user_id == user.id)
        .order_by(RecommendationSession.created_at.desc())
        .first()
    )
    if not sess:
        return RecommendationSessionResponse(created_at=None, conditions=None, items=[], scholarships=[])

    q = (
        db.query(RecommendationItem, Policy)
        .join(Policy, Policy.id == RecommendationItem.policy_id)
        .filter(RecommendationItem.session_id == sess.id)
        .order_by(RecommendationItem.id.asc())
    )

    items_out: List[RecommendationItemOut] = []
    for item, policy in q.all():
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
        created_at=to_kst_iso(sess.created_at),   # ✅ KST ISO 문자열
        conditions=sess.conditions,
        items=items_out,
        scholarships=sess.scholarships or [],
    )


@router.get("/recommendations/history", response_model=RecommendationSessionsResponse)
def get_recommendation_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sessions = (
        db.query(RecommendationSession)
        .filter(RecommendationSession.user_id == user.id)
        .order_by(RecommendationSession.created_at.desc())
        .limit(limit)
        .all()
    )
    if not sessions:
        return RecommendationSessionsResponse(sessions=[])

    out_sessions: List[RecommendationSessionResponse] = []

    for sess in sessions:
        q = (
            db.query(RecommendationItem, Policy)
            .join(Policy, Policy.id == RecommendationItem.policy_id)
            .filter(RecommendationItem.session_id == sess.id)
            .order_by(RecommendationItem.id.asc())
        )

        items_out: List[RecommendationItemOut] = []
        for item, policy in q.all():
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

        out_sessions.append(
            RecommendationSessionResponse(
                created_at=to_kst_iso(sess.created_at),  # ✅ KST ISO 문자열
                conditions=sess.conditions,
                items=items_out,
                scholarships=sess.scholarships or [],
            )
        )

    return RecommendationSessionsResponse(sessions=out_sessions)


@router.post("/views")
def create_view(
    body: ViewCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recent = (
        db.query(PolicyView)
        .filter(
            PolicyView.user_id == user.id,
            PolicyView.policy_id == body.policy_id,
            PolicyView.viewed_at >= datetime.utcnow() - timedelta(minutes=3),
        )
        .order_by(PolicyView.viewed_at.desc())
        .first()
    )
    if recent:
        if body.scholarship:
            recent.scholarship = body.scholarship
            db.add(recent)
            db.commit()
        return {"ok": True, "view_id": recent.id}

    v = PolicyView(
        user_id=user.id,
        policy_id=body.policy_id,
        verification_id=body.verification_id,
        scholarship=body.scholarship or None,
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
    views = (
        db.query(PolicyView)
        .filter(PolicyView.user_id == user.id)
        .order_by(PolicyView.viewed_at.desc())
        .limit(limit)
        .all()
    )
    if not views:
        return ViewListResponse(items=[])

    policy_ids = [x.policy_id for x in views]
    policies = db.query(Policy).filter(Policy.id.in_(policy_ids)).all()
    policy_map = {p.id: p for p in policies}

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

    items_out: List[ViewItemOut] = []
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
                viewed_at=to_kst_iso(x.viewed_at),  # ✅ KST ISO 문자열
                verification_status=PolicyVerificationStatusEnum(st) if st else None,
                scholarship=getattr(x, "scholarship", None),
            )
        )

    return ViewListResponse(items=items_out)
