# app/services/final_guidance_service.py

import os
import json
import re
import logging
from typing import Any, Dict, Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {"raw": text}
    except Exception:
        pass

    m = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else {"raw": text}
        except Exception:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else {"raw": text}
        except Exception:
            pass

    return {"raw": text}


class FinalGuidanceService:
    """
    번들 텍스트를 바탕으로 사용자에게 보여줄 “최종 신청 안내(step-by-step + 서류 + 기간 + 링크)” 생성.
    MVP: DB/브라우저/첨부/이미지 내용을 한 번에 종합 요약.
    """

    @staticmethod
    def _ensure_gemini_configured() -> None:
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=key)

    @staticmethod
    def generate_final_guidance(
        policy_title: str,
        policy_url: str,
        bundle_text: str,
        model_name: str = "gemini-2.5-flash-lite",
    ) -> Dict[str, Any]:
        FinalGuidanceService._ensure_gemini_configured()

        prompt = f"""
너는 대한민국 청년정책 “신청 안내서”를 만들어주는 전문 어시스턴트다.

입력으로 주어진 텍스트는 다음 정보를 합쳐둔 것이다:
- DB에 저장된 정책 기본정보
- browser-use로 검증/탐색해서 얻은 공식 근거(evidence_text)와 요약값(criteria/apply_steps/required_documents/contact)
- 다운로드된 첨부파일(zip/pdf/png/jpg/hwp/hwpx 등)에서 추출한 텍스트(가능한 경우)
- 본문 이미지 URL에서 OCR로 추출한 텍스트(가능한 경우)

목표:
사용자에게 “이 정책을 실제로 신청하기 위해” 필요한 정보를
step-by-step으로 매우 명확하게 정리해라.

중요 규칙:
- 반드시 아래 JSON 형식으로만 출력한다(추가 설명/문장 금지).
- 근거가 불충분하거나 확실하지 않으면 needs_review=true로 두고, why_review에 이유를 적어라.
- 제출서류는 “서식/첨부파일명”이 있으면 최대한 파일명 그대로 반영해라.
- 기간/접수처/링크가 발견되면 최대한 포함해라(없으면 null).
- 과장 금지: 텍스트에 근거가 없는 내용은 “추정”하지 말고 unknown 처리.

정책:
- title: {policy_title}
- url: {policy_url}

[번들 텍스트]
{bundle_text}

반드시 아래 JSON 형식만 출력:

{{
  "policy_title": "{policy_title}",
  "source_url": "{policy_url}",
  "summary": "정책 한줄 요약",
  "eligibility": {{
    "age": "연령 요건 요약 또는 '제한 없음' 또는 'unknown'",
    "region": "지역/거주 요건 요약 또는 '제한 없음' 또는 'unknown'",
    "income": "소득/재산 요건 요약 또는 '제한 없음' 또는 'unknown'",
    "employment": "고용/재직/구직/창업 요건 요약 또는 '제한 없음' 또는 'unknown'",
    "other": "기타 요건 요약 또는 '없음' 또는 'unknown'"
  }},
  "apply_overview": {{
    "apply_channel": "온라인/방문/우편/혼합/unknown",
    "apply_period": "신청기간 요약 또는 'unknown'",
    "where_to_apply": "접수처/사이트/포털 안내(있으면 URL 포함) 또는 null"
  }},
  "final_required_documents": [
    {{
      "name": "서류/서식명",
      "required": true,
      "note": "설명/발급처/대체서류 등(없으면 null)"
    }}
  ],
  "final_apply_steps": [
    {{
      "step": 1,
      "title": "단계 제목",
      "detail": "사용자가 해야 할 행동을 구체적으로",
      "url": "해당 링크가 있으면, 없으면 null"
    }}
  ],
  "contact": {{
    "org": "기관명 또는 unknown",
    "tel": "전화 또는 null",
    "site": "홈페이지 URL 또는 null"
  }},
  "warnings": [
    "놓치기 쉬운 조건/서류/기간 관련 주의사항"
  ],
  "faq": [
    {{
      "q": "자주 묻는 질문",
      "a": "답변"
    }}
  ],
  "confidence": 0.0,
  "needs_review": false,
  "why_review": null
}}
""".strip()

        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(prompt)
        text = resp.text or ""

        parsed = _safe_json_loads(text)
        if "raw" in parsed:
            # JSON 실패 시 최소 구조 반환
            return {
                "policy_title": policy_title,
                "source_url": policy_url,
                "summary": "생성 실패",
                "eligibility": {
                    "age": "unknown",
                    "region": "unknown",
                    "income": "unknown",
                    "employment": "unknown",
                    "other": "unknown",
                },
                "apply_overview": {
                    "apply_channel": "unknown",
                    "apply_period": "unknown",
                    "where_to_apply": None,
                },
                "final_required_documents": [],
                "final_apply_steps": [],
                "contact": {"org": "unknown", "tel": None, "site": None},
                "warnings": ["LLM JSON 파싱 실패 - 수동 확인 필요"],
                "faq": [],
                "confidence": 0.0,
                "needs_review": True,
                "why_review": "LLM did not return JSON",
                "raw_output": parsed.get("raw"),
            }

        # 기본값 보강
        parsed.setdefault("confidence", 0.0)
        parsed.setdefault("needs_review", False)
        parsed.setdefault("why_review", None)
        return parsed
