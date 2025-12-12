#app/services/llm_service.py
from typing import Any, Dict, List, Optional
import logging

import google.generativeai as genai

from app.config import settings
from app.schemas import BadgeStatus, PolicySearchRequest
from app.models import Policy

logger = logging.getLogger(__name__)

if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


class LLMService:
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
            "다음은 청년 지원 정책의 원문 일부이다.\n"
            "주어진 사용자의 나이/지역을 기준으로 이 정책의 신청 가능성을 평가해라.\n\n"
            "응답 형식은 반드시 JSON 한 줄로만 출력한다.\n"
            '{\n'
            '  "badge_status": "PASS" | "WARNING" | "FAIL",\n'
            '  "short_summary": "한 문장 요약",\n'
            '  "reason": "판단 근거",\n'
            '  "missing_criteria": ["부족한 조건1", ...]\n'
            "}\n\n"
            f"사용자 나이: {age_part}\n"
            f"사용자 지역: {region_part}\n\n"
            f"정책 제목: {policy.title}\n"
            f"정책 원문(일부):\n{text}\n"
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
