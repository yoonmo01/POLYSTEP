# app/services/parsing_service.py
from typing import List, Dict, Any

from app.schemas import PolicyStructuredOut
from app.services.llm_service import GeminiService


class ParsingService:
    @staticmethod
    def pages_to_structured(
        pages: List[Dict[str, Any]],
    ) -> List[PolicyStructuredOut]:
        if not pages:
            return []

        aggregated = ""
        for i, p in enumerate(pages, start=1):
            aggregated += (
                f"\n[정책{i}]\n"
                f"URL: {p.get('url', '')}\n"
                f"TITLE: {p.get('title', '')}\n"
                "CONTENT:\n"
                f"{(p.get('raw_text') or '')[:8000]}\n"
            )

        prompt = (
            "다음은 여러 개의 청년정책 관련 페이지에서 추출한 텍스트입니다.\n"
            "각 정책마다 하나의 JSON 객체로 구조화해 주세요.\n\n"
            "각 정책 JSON 스키마:\n"
            "- title: 문자열\n"
            "- url: 문자열\n"
            "- age_min: 정수 또는 null\n"
            "- age_max: 정수 또는 null\n"
            "- region: 문자열 또는 null\n"
            "- income_limit: 숫자 또는 null\n"
            "- target_status: 문자열 또는 null\n"
            "- category: 문자열 또는 null\n"
            "- summary: 정책 전체 요약 (길게)\n"
            "- benefit: 지원 내용/혜택 설명\n"
            "- important_requirements: 필수 자격 요건들 문장으로 정리\n\n"
            "반환 형식은 JSON 배열만 출력하세요.\n\n"
            "[원문 텍스트]\n"
            f"{aggregated}\n"
        )

        parsed = GeminiService.generate_json(prompt)

        structured_list: List[PolicyStructuredOut] = []
        for item in parsed:
            structured_list.append(
                PolicyStructuredOut(
                    id=0,
                    source_id=0,
                    title=item.get("title", "제목 없음"),
                    url=item.get("url", ""),
                    age_min=item.get("age_min"),
                    age_max=item.get("age_max"),
                    region=item.get("region"),
                    income_limit=item.get("income_limit"),
                    target_status=item.get("target_status"),
                    category=item.get("category"),
                    summary=item.get("summary"),
                    benefit=item.get("benefit"),
                    important_requirements=item.get("important_requirements"),
                )
            )

        return structured_list
