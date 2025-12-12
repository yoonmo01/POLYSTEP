#app/services/policy_service.py
from typing import List
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Policy, PolicyVerification
from app.schemas import (
    PolicySearchRequest,
    PolicySearchResult,
    BadgeStatus,
)
from app.services.llm_service import LLMService


class PolicyService:
    @staticmethod
    def _rag_search_policies(
        db: Session,
        req: PolicySearchRequest,
    ) -> List[Policy]:
        """
        실제로는 벡터 DB/RAG를 써야 하지만,
        지금은:
        - title: 공백 제거해서 부분 검색 (청년수당 == 청년 수당)
        - category: 부분 매칭 (소득 -> 소득·생활)
        - region: 부분 매칭 (서울 -> 서울특별시 등도 나중에 확장 가능)
        - age: age_min / age_max 범위 체크
        """
        q = db.query(Policy)

        # --- 제목 검색: 공백 제거 후 부분 매칭 ---
        if req.query:
            # 사용자 입력에서 공백 제거 (청년 수당 -> 청년수당)
            normalized_query = req.query.replace(" ", "")
            # title에서 공백 제거해서 비교 (서울 청년 수당 -> 서울청년수당)
            title_no_space = func.replace(Policy.title, " ", "")
            q = q.filter(title_no_space.ilike(f"%{normalized_query}%"))

        # --- 지역: 부분 매칭 ---
        if req.region:
            q = q.filter(Policy.region.ilike(f"%{req.region}%"))

        # --- 카테고리: 부분 매칭 (소득 -> 소득·생활) ---
        if req.category:
            q = q.filter(Policy.category.ilike(f"%{req.category}%"))

        # --- 나이: age_min / age_max 범위에 들어가는지 체크 ---
        if req.age is not None:
            q = q.filter(
                (Policy.age_min.is_(None) | (Policy.age_min <= req.age)),
                (Policy.age_max.is_(None) | (Policy.age_max >= req.age)),
            )

        # 일단 상위 20개만
        return q.limit(20).all()

    @staticmethod
    def search_policies(
        db: Session,
        req: PolicySearchRequest,
    ) -> List[PolicySearchResult]:
        candidates = PolicyService._rag_search_policies(db, req)

        results: List[PolicySearchResult] = []
        for p in candidates:
            # Fast Track Eligibility (LLM 호출)
            llm_result = LLMService.evaluate_eligibility(req, p)
            badge_status_str = llm_result.get("badge_status", "WARNING")
            try:
                badge_status = BadgeStatus(badge_status_str)
            except ValueError:
                badge_status = BadgeStatus.WARNING

            short_summary = llm_result.get("short_summary", p.title)

            # 최신 PolicyVerification 캐시 조회
            v = (
                db.query(PolicyVerification)
                .filter(PolicyVerification.policy_id == p.id)
                .order_by(PolicyVerification.last_verified_at.desc().nullslast())
                .first()
            )

            results.append(
                PolicySearchResult(
                    policy_id=p.id,
                    title=p.title,
                    badge_status=badge_status,
                    short_summary=short_summary,
                    has_verification_cache=bool(v and v.status == "SUCCESS"),
                    last_verified_at=v.last_verified_at if v else None,
                    category=p.category,
                    category_l=p.category_l,
                    category_m=p.category_m,
                    region=p.region,
                    age_min=p.age_min,
                    age_max=p.age_max,
                    apply_period_type=p.apply_period_type,
                    biz_end=p.biz_end,
                )
            )
        return results
