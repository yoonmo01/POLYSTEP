#app/services/llm_service.py
from typing import Any, Dict, List, Optional
import logging
import re
import google.generativeai as genai
import json

from app.config import settings
from app.schemas import BadgeStatus, PolicySearchRequest
from app.models import Policy, Scholarship, ScholarshipLLMCache, User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


class LLMService:
    # =========================
    # ✅ Scholarships: very-light personalization (no LLM)
    # =========================
    @staticmethod
    def evaluate_scholarship_user_fit(
        user: User,
        scholarship: Scholarship,
        card_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        장학금 개인맞춤을 "빡빡하지 않게" 판단.
        - PASS: 사용자 정보로 봤을 때 긍정 시그널이 있고, 명백한 충돌이 없음
        - FAIL: 거의 없음(명백한 충돌일 때만)  ← 기본은 WARNING
        - WARNING: 정보 부족/애매

        반환:
        {
          "user_fit": "PASS"|"WARNING"|"FAIL",
          "user_fit_reason": str|None,
          "missing_info": [str, ...]
        }
        """
        missing: List[str] = []
        reasons: List[str] = []

        # 1) 학생 여부: 장학금은 기본적으로 학생 대상이 많으니,
        #    is_student가 False면 WARNING(또는 특정 케이스면 FAIL) 정도로만.
        if user.is_student is None:
            missing.append("학생 여부")
        elif user.is_student is False:
            # "재학생" 전용이라고 명백히 쓰인 경우만 FAIL로 만들고,
            # 나머지는 WARNING로 둔다(빡빡하게 안 가기).
            text = " ".join(
                [
                    scholarship.selection_criteria or "",
                    scholarship.retention_condition or "",
                    (card_json or {}).get("one_liner") or "",
                    " ".join((card_json or {}).get("eligibility_bullets") or []),
                ]
            )
            if any(k in text for k in ["재학생", "재학", "재학 중", "재학자"]):
                return {
                    "user_fit": "FAIL",
                    "user_fit_reason": "재학생 대상 장학금으로 보이는데, 현재 학생이 아닌 것으로 설정되어 있어요.",
                    "missing_info": [],
                }
            reasons.append("학생이 아니어도 지원 가능한지 확인이 필요해요")

        # 2) 전공/학년: 있으면 이유에만 반영(매칭을 빡빡하게 하지 않음)
        if not user.major:
            missing.append("전공")
        else:
            reasons.append("전공 정보를 참고했어요")

        if user.grade is None:
            missing.append("학년")
        else:
            reasons.append("학년 정보를 참고했어요")

        # 3) 학점(GPA): 카드에서 gpa_min이 있을 때만 비교
        gpa_min = None
        if isinstance(card_json, dict):
            gm = card_json.get("gpa_min")
            if isinstance(gm, (int, float)):
                gpa_min = float(gm)

        if user.gpa is None:
            if gpa_min is not None:
                missing.append("평점(GPA)")
        else:
            # gpa_min이 있으면 비교하되, 미달이라고 FAIL까지는 잘 안 내림(빡빡하지 않게)
            if gpa_min is not None:
                if float(user.gpa) >= gpa_min:
                    reasons.append(f"평점({user.gpa})이 최소 기준({gpa_min}) 이상이에요")
                else:
                    reasons.append(f"평점({user.gpa})이 최소 기준({gpa_min})에 못 미칠 수 있어요")

        # 4) 최종 user_fit 결정 (의도에 맞게 정리)
        # - FAIL은 위에서 이미 return
        # - missing_info가 있으면 WARNING
        # - 명백한 충돌은 없고, 긍정 시그널이 있으며 missing이 없을 때만 PASS

        if missing:
            user_fit = "WARNING"
        elif reasons:
            user_fit = "PASS"
        else:
            user_fit = "WARNING"

        return {
            "user_fit": user_fit,
            "user_fit_reason": " · ".join(reasons) if reasons else None,
            "missing_info": missing,
        }
    @staticmethod
    def _fallback_summary(
        req: PolicySearchRequest,
        policy: Policy,
    ) -> Dict[str, Any]:
        """
        GOOGLE_API_KEY 미설정 / LLM 오류 시 사용하는 규칙 기반 요약.
        - region / category / age 범위를 조합해서 한 줄 요약 문장을 만든다.
        - 뱃지는 일단 WARNING으로 고정 (나중에 룰을 바꿔도 됨).
        """
        parts: list[str] = []

        # 지역
        if policy.region:
            parts.append(policy.region)

        # 대분류(취업·일자리 / 소득·생활 등)
        if policy.category:
            parts.append(policy.category)

        # 나이 범위
        age_str = None
        if policy.age_min is not None and policy.age_max is not None:
            age_str = f"{policy.age_min}~{policy.age_max}세"
        elif policy.age_min is not None:
            age_str = f"{policy.age_min}세 이상"
        elif policy.age_max is not None:
            age_str = f"{policy.age_max}세 이하"

        if age_str:
            parts.append(age_str)

        meta = " · ".join(parts) if parts else "청년 정책"

        short_summary = f"{meta} 대상의 '{policy.title}' 지원사업입니다."

        return {
            "badge_status": BadgeStatus.WARNING.value,
            "short_summary": short_summary,
            "reason": "LLM 비활성화 상태 또는 호출 실패 (룰 기반 요약)",
            "missing_criteria": [],
        }
    @staticmethod
    def _postprocess_badge(
        parsed: Dict[str, Any],
        policy: Policy,
        req: PolicySearchRequest,
    ) -> Dict[str, Any]:
        """
        Gemini가 준 badge_status를 그대로 쓰지 않고,
        사람이 보기 더 자연스럽게 한 번 보정하는 단계.

        - FAIL인데 '정보 부족 / 판단 불가' 계열이면 WARNING으로 완화
        - 강한 부정 문구가 전혀 없는데 FAIL이면 WARNING으로 완화
        """
        badge = (parsed.get("badge_status") or "").upper()
        reason = (parsed.get("reason") or "").strip()
        summary = (parsed.get("short_summary") or "").strip()

        # 🔎 1) 정보 부족 / 판단 불가 패턴들
        info_lack_keywords = [
            "판단할 수 없",
            "판단하기 어렵",
            "판단할 수 없어",
            "정보가 없어",
            "정보가 부족",
            "부족하여",
            "추가 정보",
        ]

        # 🔎 2) 진짜 '완전 탈락' 느낌의 강한 부정 패턴들
        strong_fail_keywords = [
            "신청할 수 없",
            "신청할 수 없습니다",
            "대상이 아닙니다",
            "지원 대상이 아닙니다",
            "해당되지 않습니다",
            "제외됩니다",
        ]

        # ❶ FAIL인 경우 → 정보 부족이면 WARNING으로 완화
        if badge == "FAIL":
            # (1) 정보 부족 계열이면 → WARNING으로 완화
            if any(k in reason for k in info_lack_keywords):
                parsed["badge_status"] = BadgeStatus.WARNING.value
                return parsed

            # (2) 강한 부정 문구가 하나도 없으면 → WARNING으로 완화
            if not any(k in reason for k in strong_fail_keywords):
                parsed["badge_status"] = BadgeStatus.WARNING.value
                return parsed

        # ❷ WARNING인데, 문구가 너무 강하게 "완전 탈락"이면 → FAIL로 격상
        if badge == "WARNING":
            text_for_check = reason + " " + summary
            if any(k in text_for_check for k in strong_fail_keywords):
                parsed["badge_status"] = BadgeStatus.FAIL.value
                return parsed
        # 나머지는 그대로 반환
        return parsed
    @staticmethod
    def _build_fast_track_prompt(
        req: PolicySearchRequest,
        policy: Policy,
    ) -> str:
        age_part = f"{req.age}세" if req.age is not None else "나이 정보 없음"
        region_part = req.region or "지역 정보 없음"

        # 정책 원문 텍스트 구성:
        # 1순위: policy.raw_text
        # 2순위: raw_snippet + raw_expln + raw_support 조합
        text_source = policy.raw_text

        if not text_source:
            pieces: list[str] = []
            for attr in ("raw_snippet", "raw_expln", "raw_support"):
                v = getattr(policy, attr, None)
                if v:
                    pieces.append(str(v))
            text_source = " ".join(pieces)

        text = text_source or ""
        if len(text) > 6000:
            text = text[:6000]

        prompt = (
            "다음은 대한민국 청년 지원 정책의 원문 일부이다.\n"
            "주어진 사용자의 나이와 지역 정보를 기준으로 이 정책의 신청 가능성을 평가하라.\n\n"
            "⚠️ 판단 원칙(매우 중요):\n"
            "1. 정책 원문 또는 메타 정보에 **명시적으로 대상이 아님**이 드러나지 않는 한 FAIL로 판단하지 말 것.\n"
            "2. 정보가 부족하거나 조건이 애매한 경우에는 반드시 WARNING으로 판단할 것.\n"
            "3. 정책 원문에 자격 요건이 없을 경우, 아래 제공된 정책 메타 정보(age/region)를 근거로 가능성을 추정할 것.\n"
            "4. FAIL은 다음과 같은 경우에만 사용한다:\n"
            "   - 연령 초과/미달이 명확함\n"
            "   - 거주 지역이 명확히 불일치함\n"
            "   - 정책 원문에 '지원 대상이 아님', '신청 불가'가 명시됨\n\n"
            "응답 형식은 반드시 JSON 한 줄로만 출력한다.\n"
            '{\n'
            '  "badge_status": "PASS" | "WARNING" | "FAIL",\n'
            '  "short_summary": "사용자 관점의 한 문장 요약",\n'
            '  "reason": "판단 근거를 간단히 설명",\n'
            '  "missing_criteria": ["부족한 조건이 있다면 나열"]\n'
            "}\n\n"
            f"[사용자 정보]\n"
            f"- 나이: {age_part}\n"
            f"- 지역: {region_part}\n\n"
            f"[정책 메타 정보]\n"
            f"- 정책 지역(meta): {policy.region}\n"
            f"- 연령 범위(meta): {policy.age_min} ~ {policy.age_max}\n"
            f"- 정책 분야(meta): {policy.category}\n\n"
            f"[정책 제목]\n"
            f"{policy.title}\n\n"
            f"[정책 원문 일부]\n"
            f"{text}\n"
        )
        return prompt

    @staticmethod
    def _parse_fast_track_result(raw: str) -> Dict[str, Any]:
        import json
        # 0) 원본 문자열 정리
        s = raw.strip()

        # 1) ```json ... ``` 같은 마크다운 코드블록이면 벗겨내기
        if s.startswith("```"):
            # 첫 줄(예: ```json) 제거
            first_newline = s.find("\n")
            if first_newline != -1:
                s = s[first_newline + 1 :]
            # 마지막의 ``` 제거
            if s.endswith("```"):
                s = s[:-3]
            s = s.strip()

        # 2) 혹시 앞뒤에 다른 텍스트가 섞여 있어도,
        #    가장 바깥 쪽의 { ... } 범위만 잘라내기
        if "{" in s and "}" in s:
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                s = s[start : end + 1]

        try:
            return json.loads(s)
        except Exception as e:
            # 🔥 여기서 LLM이 보낸(정리된) 원문 일부를 로그로 찍어보자
            logger.warning(
                "[LLMService] FastTrack JSON 파싱 실패 (%s): raw=%r",
                e.__class__.__name__,
                s[:300],  # 너무 길면 잘라서
            )
            return {
                "badge_status": "WARNING",
                "short_summary": "정책 요약에 실패했습니다.",
                "reason": "LLM 응답 파싱 실패",
                "missing_criteria": [],
            }

    @staticmethod
    def evaluate_eligibility(
        req: PolicySearchRequest,
        policy: Policy,
    ) -> Dict[str, Any]:
        """
        Fast Track에서 각 정책별로 PASS/WARNING/FAIL 뱃지와 요약을 만드는 함수.
        - GOOGLE_API_KEY 없으면: 바로 더미 결과
        - LLM 호출 중 에러 나면: 더미 결과 + 에러 정보 살짝 포함
        """
        # 1) 키가 아예 없으면: 규칙 기반 간단 요약
        if not settings.google_api_key:
            logger.warning("[LLMService] GOOGLE_API_KEY 미설정 → fallback 사용")
            return LLMService._fallback_summary(req, policy)

        prompt = LLMService._build_fast_track_prompt(req, policy)

        try:
            # 🔁 여기 모델 이름은 환경에 맞게 나중에 조정 가능
            logger.info("[LLMService] Gemini FastTrack 호출 시작 (policy_id=%s)", policy.id)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(prompt)
            raw_text = response.text or ""
            logger.debug("[LLMService] Gemini raw 응답 일부: %r", raw_text[:200])

            parsed = LLMService._parse_fast_track_result(raw_text)
            # 🔧 LLM이 준 badge를 사람이 보기 좋게 한 번 후처리
            parsed = LLMService._postprocess_badge(parsed, policy, req)

            # 🔥 파싱은 됐는데, 여전히 우리가 정의한 '실패 메시지'면 → fallback으로 대체
            if parsed.get("short_summary") == "정책 요약에 실패했습니다.":
                logger.info(
                    "[LLMService] LLM 파싱 결과가 실패 기본값 → fallback 요약 사용 (policy_id=%s)",
                    policy.id,
                )
                return LLMService._fallback_summary(req, policy)

            return parsed

        except Exception as e:
            # LLM 호출 실패해도 FastAPI는 500 안 내고, 규칙 기반 요약 사용
            logger.error(
                "[LLMService] Gemini 호출 예외 발생 → fallback 사용 (%s: %s)",
                e.__class__.__name__,
                str(e),
            )
            fallback = LLMService._fallback_summary(req, policy)
            fallback["reason"] = f"LLM 호출 실패: {e.__class__.__name__}"
            return fallback

    # ===== Deep Track에서 사용할 추출용 =====
    @staticmethod
    def build_deep_track_prompt(page_texts: List[str]) -> str:
        combined = "\n\n---\n\n".join(page_texts)
        if len(combined) > 12000:
            combined = combined[:12000]

        prompt = (
            "다음은 특정 청년 정책 페이지에서 수집한 텍스트이다.\n"
            "이 텍스트를 바탕으로 신청 자격/대상/기간/필수 서류 등 중요한 조건을 구조화해라.\n\n"
            "응답 형식은 반드시 JSON 한 줄로만 출력한다.\n"
            "{\n"
            '  "criteria": {\n'
            '    "age": "예: 만 19~34세",\n'
            '    "region": "예: 서울 거주",\n'
            '    "employment": "예: 미취업 또는 프리랜서",\n'
            '    "others": ["기타 조건1", "기타 조건2", ...]\n'
            "  },\n"
            '  "evidence_text": "가장 핵심적인 부분만 발췌한 요약 텍스트"\n'
            "}\n\n"
            "다음은 수집된 원문이다:\n"
            f"{combined}\n"
        )
        return prompt

    @staticmethod
    def extract_verification_info(page_texts: List[str]) -> Dict[str, Any]:
        """
        Deep Track에서 browser-use/Playwright가 수집한 텍스트들을 기반으로
        자격 조건/증빙 텍스트를 구조화.
        """
        if not settings.google_api_key:
            return {
                "criteria": {
                    "age": "정보 없음",
                    "region": "정보 없음",
                    "employment": "정보 없음",
                    "others": [],
                },
                "evidence_text": "LLM 비활성화 상태 (더미 데이터)",
            }

        prompt = LLMService.build_deep_track_prompt(page_texts)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        raw = response.text or ""

        import json

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "criteria": {
                    "age": "파싱 실패",
                    "region": "파싱 실패",
                    "employment": "파싱 실패",
                    "others": [],
                },
                "evidence_text": "LLM 응답 파싱 실패",
            }
        return parsed

    # ===== Deep Track(B안): facts + 사용자정보 + DB 정책정보 → 최종 안내서(JSON) =====
    @staticmethod
    def make_user_guide(
        age: Optional[int],
        region: Optional[str],
        policy: Policy,
        deep_facts: Dict[str, Any],
        evidence_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deep Track 결과(facts) + 사용자 정보 + 정책(DB)을 합쳐
        '신청 가능 여부 / 필요 서류 / 신청 절차'를 구조화된 JSON으로 생성한다.
        (B안: 백엔드에서 완성형 안내서 생성)
        """
        # 1) LLM 비활성화면: facts 기반으로 최소 안내서 생성 (판단은 WARNING)
        if not settings.google_api_key:
            return {
                "badge_status": BadgeStatus.WARNING.value,
                "can_apply": False,
                "summary": f"'{policy.title}' 안내를 생성했습니다. (LLM 비활성화로 자동 판단은 보류)",
                "required_documents": (deep_facts or {}).get("required_documents") or [],
                "apply_steps": (deep_facts or {}).get("apply_steps") or [],
                "apply_channel": (deep_facts or {}).get("apply_channel"),
                "apply_period": (deep_facts or {}).get("apply_period"),
                "contact": (deep_facts or {}).get("contact") or {},
                "missing_info": ["LLM 비활성화 상태로 신청 가능 여부 자동 판단 불가"],
                "evidence_text": evidence_text,
            }

        user_age = f"{age}세" if age is not None else "나이 정보 없음"
        user_region = region or "지역 정보 없음"

        facts_json = json.dumps(deep_facts or {}, ensure_ascii=False)

        prompt = f"""
너는 대한민국 청년정책 신청 안내를 만드는 전문가야.

아래 사용자 정보 + 정책 DB 정보 + Deep Track으로 추출한 최신 원문 facts를 종합해서,
사용자에게 보여줄 "최종 안내서"를 JSON으로 만들어라.

요구사항:
- eligibility 판단은 deep_facts.criteria를 근거로 하되, 정보가 부족하면 WARNING 처리하고 missing_info에 무엇이 부족한지 적어라.
- required_documents/apply_steps/contact 등은 deep_facts를 최대한 그대로 활용하되, 표현은 사용자 친화적으로 다듬어라.
- 반드시 JSON만 출력. 추가 문장 금지.

출력 JSON 스키마:
{{
  "badge_status": "PASS" | "WARNING" | "FAIL",
  "can_apply": true|false,
  "summary": "사용자에게 보여줄 한 단락 요약",
  "required_documents": ["...", "..."],
  "apply_steps": [{{"step": 1, "title": "...", "detail": "...", "url": "..."}}],
  "apply_channel": "온라인/방문/우편/혼합" | null,
  "apply_period": "..." | null,
  "contact": {{"org":"...", "tel":"...", "site":"..."}},
  "missing_info": ["판단에 필요한 추가 정보...", "..."],
  "evidence_text": "핵심 근거 발췌"
}}

사용자 정보:
- 나이: {user_age}
- 지역: {user_region}

정책(DB) 메타:
- title: {policy.title}
- category: {policy.category}
- region(meta): {policy.region}
- age_min~age_max(meta): {policy.age_min}~{policy.age_max}
- apply_period_raw(meta): {policy.apply_period_raw}
- apply_url(meta): {policy.apply_url}
- target_url(meta): {policy.target_url}

Deep facts(JSON):
{facts_json}

원문 근거(evidence_text):
{evidence_text or ""}
        """.strip()

        try:
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(prompt)
            raw = (response.text or "").strip()
            parsed = LLMService._parse_fast_track_result(raw)
        except Exception as e:
            logger.error("[LLMService] make_user_guide 실패 (%s: %s)", e.__class__.__name__, str(e))
            return {
                "badge_status": BadgeStatus.WARNING.value,
                "can_apply": False,
                "summary": "안내서 생성 중 오류가 발생했습니다.",
                "required_documents": (deep_facts or {}).get("required_documents") or [],
                "apply_steps": (deep_facts or {}).get("apply_steps") or [],
                "apply_channel": (deep_facts or {}).get("apply_channel"),
                "apply_period": (deep_facts or {}).get("apply_period"),
                "contact": (deep_facts or {}).get("contact") or {},
                "missing_info": [f"LLM 호출 실패: {e.__class__.__name__}"],
                "evidence_text": evidence_text,
            }

        # 2) 최소 필드 보정 + Enum 문자열 정규화
        badge = (parsed.get("badge_status") or "WARNING").upper()
        if badge not in ("PASS", "WARNING", "FAIL"):
            badge = "WARNING"

        parsed["badge_status"] = badge
        parsed.setdefault("can_apply", False)
        parsed.setdefault("summary", "")
        parsed.setdefault("required_documents", [])
        parsed.setdefault("apply_steps", [])
        parsed.setdefault("apply_channel", None)
        parsed.setdefault("apply_period", None)
        parsed.setdefault("contact", {})
        parsed.setdefault("missing_info", [])
        parsed.setdefault("evidence_text", evidence_text)

        return parsed
    
    # =========================
    # ✅ Scholarships (B안): 카드형 요약 + 캐시
    # =========================
    SCHOLARSHIP_PROMPT_VERSION = 1

    @staticmethod
    def _build_scholarship_card_prompt(
        scholarship: Scholarship,
    ) -> str:
        """
        장학금 원문(선발/유지/지급액)을 카드형으로 '정리'하는 프롬프트.
        - 사용자 맞춤 추천(스코어링)은 라우터/서비스에서 따로 해도 되고
        여기서는 일단 "정리"에 집중(캐시 재사용 극대화).
        """
        selection = (scholarship.selection_criteria or "").strip()
        retention = (scholarship.retention_condition or "").strip()
        benefit = (scholarship.benefit or "").strip()
        notes = (scholarship.notes or "").strip()

        # 너무 길면 자르기(LLM 비용/실패 방지)
        def _clip(s: str, n: int = 6000) -> str:
            if len(s) <= n:
                return s
            return s[:n]

        selection = _clip(selection, 5000)
        retention = _clip(retention, 4000)
        benefit = _clip(benefit, 2000)
        notes = _clip(notes, 1500)

        prompt = f"""
너는 대학교 장학금 안내 페이지를 "카드 UI"용으로 요약/정리하는 전문가다.

아래 장학금 원문을 읽고, 사용자가 한눈에 이해할 수 있도록 "카드형 JSON"만 출력해라.
⚠️ 규칙:
- 반드시 JSON만 출력(추가 문장/설명 금지)
- 모르면 추측하지 말고 null/빈 배열로 둬라
- eligibility_bullets/retention_bullets/notes_bullets는 각 3~6개 이내, 짧은 문장으로
- gpa_min은 원문에 명시된 최소평점이 있을 때만 숫자(예: 3.5)로 추출

출력 스키마(JSON):
{{
    "one_liner": "장학금 핵심 한 줄 요약",
    "benefit_summary": "지급/감면 요약(짧게)" | null,
    "eligibility_bullets": ["선발/지원 대상 핵심", "..."],
    "retention_bullets": ["유지 조건 핵심", "..."],
    "notes_bullets": ["예외/주의/산정 기준", "..."],
    "gpa_min": 3.5 | null,
    "keywords": ["키워드1","키워드2","키워드3"]
}}

[장학금 메타]
- name: {scholarship.name}
- category: {scholarship.category}
- source_url: {scholarship.source_url}

[선발기준 원문]
{selection}

[유지조건 원문]
{retention}

[지급액/혜택 원문]
{benefit}

[기타 메모]
{notes}
        """.strip()
        return prompt

    @staticmethod
    def _parse_scholarship_card(raw: str) -> Dict[str, Any]:
        """
        기존 _parse_fast_track_result는 policy용 키가 섞일 수 있어서,
        scholarship card는 별도 파서로 '최소 필드 보정'까지 수행.
        """
        parsed = LLMService._parse_fast_track_result(raw)

        # 최소 필드 보정
        out: Dict[str, Any] = {}
        out["one_liner"] = (parsed.get("one_liner") or "").strip() or "장학금 요약"
        out["benefit_summary"] = (parsed.get("benefit_summary") or None)

        def _as_list(v):
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return [str(v).strip()] if str(v).strip() else []

        out["eligibility_bullets"] = _as_list(parsed.get("eligibility_bullets"))
        out["retention_bullets"] = _as_list(parsed.get("retention_bullets"))
        out["notes_bullets"] = _as_list(parsed.get("notes_bullets"))
        out["keywords"] = _as_list(parsed.get("keywords"))[:8]

        # gpa_min 정규화
        gpa_min = parsed.get("gpa_min")
        try:
            out["gpa_min"] = float(gpa_min) if gpa_min is not None else None
        except Exception:
            out["gpa_min"] = None

        return out

    @staticmethod
    def get_or_make_scholarship_card(
        db: Session,
        scholarship: Scholarship,
        prompt_version: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        scholarship_id  prompt_version 캐시 우선.
        없으면 LLM 호출 → DB 저장 → 반환.
        """
        pv = prompt_version or LLMService.SCHOLARSHIP_PROMPT_VERSION

        cache = (
            db.query(ScholarshipLLMCache)
            .filter(
                ScholarshipLLMCache.scholarship_id == scholarship.id,
                ScholarshipLLMCache.prompt_version == pv,
            )
            .first()
        )

        if cache and not force:
            return cache.card_json

        # LLM 비활성화면: 간단 fallback(캐시 저장은 선택)
        if not settings.google_api_key:
            fallback = {
                "one_liner": f"{scholarship.name} 장학금",
                "benefit_summary": (scholarship.benefit or None),
                "eligibility_bullets": [],
                "retention_bullets": [],
                "notes_bullets": [],
                "gpa_min": None,
                "keywords": [],
            }
            if not cache:
                cache = ScholarshipLLMCache(
                    scholarship_id=scholarship.id,
                    prompt_version=pv,
                    card_json=fallback,
                )
                db.add(cache)
                db.commit()
                db.refresh(cache)
            else:
                cache.card_json = fallback
                db.add(cache)
                db.commit()
            return fallback

        prompt = LLMService._build_scholarship_card_prompt(scholarship)

        try:
            logger.info("[LLMService] Scholarship card 호출 (scholarship_id=%s)", scholarship.id)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(prompt)
            raw_text = (response.text or "").strip()
            card = LLMService._parse_scholarship_card(raw_text)
        except Exception as e:
            logger.error(
                "[LLMService] Scholarship card 실패 (%s: %s)",
                e.__class__.__name__,
                str(e),
            )
            card = {
                "one_liner": f"{scholarship.name} 장학금",
                "benefit_summary": (scholarship.benefit or None),
                "eligibility_bullets": [],
                "retention_bullets": [],
                "notes_bullets": [f"LLM 호출 실패: {e.__class__.__name__}"],
                "gpa_min": None,
                "keywords": [],
            }

        # upsert cache
        if not cache:
            cache = ScholarshipLLMCache(
                scholarship_id=scholarship.id,
                prompt_version=pv,
                card_json=card,
            )
        else:
            cache.card_json = card

        db.add(cache)
        db.commit()
        db.refresh(cache)
        return card