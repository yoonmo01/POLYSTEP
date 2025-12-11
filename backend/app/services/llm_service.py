#app/services/llm_service.py
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from app.config import settings
from app.schemas import BadgeStatus, PolicySearchRequest
from app.models import Policy

if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


class LLMService:
    @staticmethod
    def _build_fast_track_prompt(
        req: PolicySearchRequest,
        policy: Policy,
    ) -> str:
        age_part = f"{req.age}세" if req.age is not None else "나이 정보 없음"
        region_part = req.region or "지역 정보 없음"

        text = policy.raw_text or ""
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

        try:
            return json.loads(raw)
        except Exception:
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
        # 1) 키가 아예 없으면: LLM 없이 더미
        if not settings.google_api_key:
            return {
                "badge_status": BadgeStatus.PASS.value,
                "short_summary": f"{policy.title} (LLM 비활성화 더미)",
                "reason": "GOOGLE_API_KEY 미설정",
                "missing_criteria": [],
            }

        prompt = LLMService._build_fast_track_prompt(req, policy)

        try:
            # 🔁 여기 모델 이름은 환경에 맞게 나중에 조정 가능
            #    일단 404가 나도 except에서 처리하므로 서비스는 안 죽음
            model = genai.GenerativeModel("gemini-1.5-flash-001")
            response = model.generate_content(prompt)
            raw_text = response.text or ""
            parsed = LLMService._parse_fast_track_result(raw_text)
            return parsed

        except Exception as e:
            # LLM 호출 실패해도 FastAPI는 500 안 내고, 뱃지/요약만 더미로
            return {
                "badge_status": BadgeStatus.WARNING.value,
                "short_summary": f"{policy.title} (LLM 오류로 간단 요약)",
                "reason": f"LLM 호출 실패: {e.__class__.__name__}",
                "missing_criteria": [],
            }

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
