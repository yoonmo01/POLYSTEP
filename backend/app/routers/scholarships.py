# app/routers/scholarships.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db import get_db
from app.models import Scholarship, ScholarshipCommonRule
from app.schemas import (
    ScholarshipCreate,
    ScholarshipRead,
    ScholarshipUpdate,
    ScholarshipBundleResponse,
    ScholarshipCommonRuleRead,
)

router = APIRouter()


@router.get("", response_model=List[ScholarshipRead])
def list_scholarships(
    query: Optional[str] = Query(None, description="name/criteria/condition/benefit 부분검색"),
    category: Optional[str] = Query(None, description="성적/복지/근로/SW/국제/기타"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Scholarship)

    if category:
        q = q.filter(Scholarship.category == category)

    if query:
        like = f"%{query}%"
        q = q.filter(
            or_(
                Scholarship.name.ilike(like),
                Scholarship.selection_criteria.ilike(like),
                Scholarship.retention_condition.ilike(like),
                Scholarship.benefit.ilike(like),
            )
        )

    return q.order_by(Scholarship.id.asc()).offset(offset).limit(limit).all()


# ✅ 고정 라우트들은 동적 라우트("/{scholarship_id}")보다 위에!
@router.get("/bundle", response_model=ScholarshipBundleResponse)
def get_bundle(
    db: Session = Depends(get_db),
):
    scholarships = db.query(Scholarship).order_by(Scholarship.id.asc()).all()
    rules = (
        db.query(ScholarshipCommonRule)
        .order_by(ScholarshipCommonRule.id.asc())
        .all()
    )
    return ScholarshipBundleResponse(
        scholarships=scholarships,
        common_rules=rules,
    )


# ✅ 422 방지: "/common-rules"를 "/{scholarship_id}"보다 위로 이동
@router.get("/common-rules", response_model=List[ScholarshipCommonRuleRead])
def list_common_rules(db: Session = Depends(get_db)):
    return (
        db.query(ScholarshipCommonRule)
        .order_by(ScholarshipCommonRule.id.asc())
        .all()
    )


@router.get("/{scholarship_id}", response_model=ScholarshipRead)
def get_scholarship(
    scholarship_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(Scholarship).filter(Scholarship.id == scholarship_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return row


@router.post("", response_model=ScholarshipRead)
def create_scholarship(
    payload: ScholarshipCreate,
    db: Session = Depends(get_db),
):
    exists = db.query(Scholarship).filter(Scholarship.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=409, detail="Scholarship name already exists")

    row = Scholarship(
        name=payload.name,
        category=payload.category,
        selection_criteria=payload.selection_criteria,
        retention_condition=payload.retention_condition,
        benefit=payload.benefit,
        source_url=payload.source_url,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{scholarship_id}", response_model=ScholarshipRead)
def update_scholarship(
    scholarship_id: int,
    payload: ScholarshipUpdate,
    db: Session = Depends(get_db),
):
    row = db.query(Scholarship).filter(Scholarship.id == scholarship_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Scholarship not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{scholarship_id}")
def delete_scholarship(
    scholarship_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(Scholarship).filter(Scholarship.id == scholarship_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
