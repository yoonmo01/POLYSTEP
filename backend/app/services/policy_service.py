#app/services/policy_service.py
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Policy, PolicyVerification
from app.schemas import (
    PolicySearchRequest,
    PolicySearchResult,
    BadgeStatus,
    SimilarPoliciesResponse,
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
        """
        기존 검색: 단순히 조건에 맞는 정책 리스트를 반환.
        (프론트에서 일반 리스트 뷰로 쓰고 싶을 때를 위해 그대로 유지)
        """
        candidates = PolicyService._rag_search_policies(db, req)

        results: List[PolicySearchResult] = []
        for p in candidates:
            results.append(
                PolicyService._build_policy_result(db=db, policy=p, req=req)
            )
        return results

    # ===== 공통: Policy + LLM 결과 → PolicySearchResult 변환 =====
    @staticmethod
    def _build_policy_result(
        db: Session,
        policy: Policy,
        req: PolicySearchRequest,
    ) -> PolicySearchResult:
        """
        하나의 Policy에 대해:
        - Fast Track LLM 평가 호출
        - 최신 검증 캐시 조회
        를 수행하고 PolicySearchResult로 묶어주는 공통 유틸.
        """
        # Fast Track Eligibility (LLM 호출)
        llm_result = LLMService.evaluate_eligibility(req, policy)
        badge_status_str = llm_result.get("badge_status", "WARNING")
        try:
            badge_status = BadgeStatus(badge_status_str)
        except ValueError:
            badge_status = BadgeStatus.WARNING

        short_summary = llm_result.get("short_summary", policy.title)

        # 최신 PolicyVerification 캐시 조회
        v = (
            db.query(PolicyVerification)
            .filter(PolicyVerification.policy_id == policy.id)
            .order_by(PolicyVerification.last_verified_at.desc().nullslast())
            .first()
        )

        return PolicySearchResult(
            policy_id=policy.id,
            title=policy.title,
            badge_status=badge_status,
            short_summary=short_summary,
            has_verification_cache=bool(v and v.status == "SUCCESS"),
            last_verified_at=v.last_verified_at if v else None,
            category=policy.category,
            category_l=policy.category_l,
            category_m=policy.category_m,
            region=policy.region,
            age_min=policy.age_min,
            age_max=policy.age_max,
            apply_period_type=policy.apply_period_type,
            biz_end=policy.biz_end,
        )

    # ===== 기준 정책 + 유사 정책 5개 찾기 =====
    @staticmethod
    def _find_similar_policies(
        db: Session,
        base: Policy,
        req: PolicySearchRequest,
        limit: int = 5,
    ) -> List[Policy]:
        """
        첫 버전: 규칙 기반 유사도
        - 같은 category / category_l / category_m 에 점수 가산
        - 사용자 region이 정책 region에 포함되면 가산
        - 사용자 age가 정책 age 범위에 들어가면 가산
        """
        q = db.query(Policy).filter(Policy.id != base.id)

        # 같은 대분류(category) 우선 필터 (너무 좁으면 주석 처리해서 완화 가능)
        if base.category:
            q = q.filter(Policy.category == base.category)

        candidates = q.all()

        user_age = req.age
        user_region = (req.region or "").strip()
        base_cat = (base.category or "").strip()
        base_cat_l = (getattr(base, "category_l", "") or "").strip()
        base_cat_m = (getattr(base, "category_m", "") or "").strip()

        def calc_score(p: Policy) -> int:
            score = 0

            # 카테고리 유사도
            if (p.category or "").strip() == base_cat:
                score += 3
            if (getattr(p, "category_l", "") or "").strip() == base_cat_l and base_cat_l:
                score += 2
            if (getattr(p, "category_m", "") or "").strip() == base_cat_m and base_cat_m:
                score += 1

            # 지역 유사도
            if user_region and p.region and user_region in p.region:
                score += 2

            # 연령대 유사도 (사용자 나이가 정책 범위에 들어가면 가산)
            if user_age is not None:
                if (
                    (p.age_min is None or p.age_min <= user_age)
                    and (p.age_max is None or p.age_max >= user_age)
                ):
                    score += 2

            return score

        scored: List[tuple[int, Policy]] = [
            (calc_score(p), p) for p in candidates
        ]
        # 점수 높은 순, 동일 점수면 id 오름차순
        scored.sort(key=lambda x: (-x[0], x[1].id))

        # 점수 > 0 인 것들 위주로 limit 만큼 자르기
        similars: List[Policy] = [p for s, p in scored if s > 0][:limit]

        # 만약 너무 적게 나왔으면, 점수 0짜리도 채워서 limit까지 맞추기
        if len(similars) < limit:
            extra = [
                p for s, p in scored
                if p not in similars
            ][: max(0, limit - len(similars))]
            similars.extend(extra)

        return similars

    @staticmethod
    def get_policy_with_similars(
        db: Session,
        policy_id: int,
        req: PolicySearchRequest,
    ) -> Optional[SimilarPoliciesResponse]:
        """
        기준 정책 1개 + 유사 정책 N개(기본 5개)를
        PolicySearchResult 형태로 묶어서 반환.
        - 기준 정책/유사 정책 모두 Fast Track LLM 평가를 적용한다.
        """
        base = db.get(Policy, policy_id)
        if not base:
            return None

        base_result = PolicyService._build_policy_result(db=db, policy=base, req=req)
        similar_policies = PolicyService._find_similar_policies(
            db=db,
            base=base,
            req=req,
            limit=5,
        )

        similar_results: List[PolicySearchResult] = [
            PolicyService._build_policy_result(db=db, policy=p, req=req)
            for p in similar_policies
        ]

        return SimilarPoliciesResponse(
            base_policy=base_result,
            similar_policies=similar_results,
        )
    @staticmethod
    def search_policies_with_similars(
        db: Session,
        req: PolicySearchRequest,
    ) -> Optional[SimilarPoliciesResponse]:
        """
        ✅ 사용자가 처음 검색했을 때:
        - 검색 조건에 맞는 정책들 중에서 '기준 정책'을 하나 고르고
        - 그 기준 정책과 유사한 정책 5개를 함께 반환.

        기준 정책 선택 로직(1차 버전):
        - _rag_search_policies 결과의 첫 번째 정책을 기준으로 사용.
          (나중에 점수 기반으로 고도화 가능)
        """
        candidates = PolicyService._rag_search_policies(db, req)
        if not candidates:
            return None

        base = candidates[0]

        base_result = PolicyService._build_policy_result(
            db=db,
            policy=base,
            req=req,
        )

        similar_policies = PolicyService._find_similar_policies(
            db=db,
            base=base,
            req=req,
            limit=5,
        )

        similar_results: List[PolicySearchResult] = [
            PolicyService._build_policy_result(db=db, policy=p, req=req)
            for p in similar_policies
        ]

        return SimilarPoliciesResponse(
            base_policy=base_result,
            similar_policies=similar_results,
        )