# backend/app/services/llm_service.py
from typing import List, Dict, Any
import json

import google.generativeai as genai

from ..config import settings
from ..schemas import PolicySummary, Step, PolicySearchRequest, PolicySearchResponse

# Gemini 초기 설정
if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


def _clean_json_text(text: str) -> str:
    """
    혹시라도 Gemini가 ```json ... ``` 같은 코드펜스로 감싸서 줄 경우를 대비해
    앞뒤 코드펜스를 제거하는 함수.
    (프롬프트에서는 코드펜스를 쓰지 않았지만, 모델이 스스로 붙일 수도 있음)
    """
    t = text.strip()

    # 코드펜스가 없으면 그대로
    if "```" not in t:
        return t

    # 첫 번째 ``` 이후 내용만 사용
    first = t.find("```")
    t = t[first + 3 :].strip()

    # 다시 ```가 있으면 그 전까지만 사용
    if "```" in t:
        second = t.find("```")
        t = t[:second].strip()

    return t


def summarize_policy_and_make_steps(
    req: PolicySearchRequest,
    pages: List[Dict[str, Any]],
    extra_texts: List[str],
) -> PolicySearchResponse:
    """
    browser-use가 모은 텍스트(pages + 파일텍스트)를 하나로 묶고,
    Gemini로 요약 + Step-by-step 절차 생성.
    """
    # pages의 raw_text + extra_texts 모두 합치기
    page_texts = [p.get("raw_text") or "" for p in pages]
    all_text = "\n\n---PAGE---\n\n".join(page_texts + extra_texts)

    source_urls = [p.get("url") for p in pages if p.get("url")]

    filters = req.filters

    prompt = f"""
너는 한국 청년 정책/장학금 안내 도우미다.
아래는 한 사용자가 찾고자 하는 정책과 그와 관련된 웹페이지/첨부파일에서 추출한 내용이다.

[사용자 요청]
- 검색어: {req.query}
- 카테고리: {filters.category if filters else "없음"}
- 지역: {filters.region if filters else "없음"}
- 나이: {filters.age if filters else "없음"}
- 상태: {filters.status if filters else "없음"}

[수집된 원문 텍스트]
{all_text}

위 정보를 바탕으로:

1. 사용자가 궁금해할만한 '핵심 정책정보 요약'을 작성하라.
2. 제목(정책명)을 1줄로 정리하라.
3. 대상, 지원내용, 지원금액, 기간, 담당 기관/링크를 정리하라.
4. 실제 신청 과정에서 따라야 할 절차를 'Step 1, Step 2, ...' 형태로 구체적으로 작성하라.
   - 단, 너무 추상적이지 않게 실제 사용자가 따라할 수 있는 수준으로 작성할 것.

반환 형식은 반드시 JSON만 출력하라. 예시는 다음과 같다.

{
  "summary": {
    "title": "정책 이름 또는 최종 제목",
    "category": "카테고리(모르면 null)",
    "region": "지역(모르면 null)",
    "summary": "정책 내용을 한글로 요약한 문단",
    "support_amount": "지원금액 또는 혜택 요약(모르면 null)",
    "duration": "기간/신청기간 요약(모르면 null)",
    "link": "가장 대표적인 안내 페이지 링크(모르면 null)"
  },
  "steps": [
    {
      "order": 1,
      "title": "Step 제목",
      "description": "이 단계에서 사용자가 해야 할 일을 구체적으로 적기"
    }
  ]
}

반드시 위 JSON 형식과 동일한 키 구조를 사용하고,
추가적인 설명 문장이나 주석은 전혀 출력하지 마라.
JSON 하나만 출력하라.
"""

    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    resp = model.generate_content(prompt)

    # 응답 텍스트 꺼내기
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        try:
            parts = resp.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") for p in parts)
        except Exception:
            text = ""

    if not text:
        summary = PolicySummary(
            title=req.query,
            category=filters.category if filters else None,
            region=filters.region if filters else None,
            summary="정책 요약을 생성하지 못했습니다.",
        )
        return PolicySearchResponse(
            query=req.query,
            filters=filters,
            summary=summary,
            steps=[],
            source_urls=source_urls,
        )

    cleaned = _clean_json_text(text)

    try:
        data = json.loads(cleaned)
    except Exception:
        # 실패 시 기본값으로 떨어뜨리기
        summary = PolicySummary(
            title=req.query,
            category=filters.category if filters else None,
            region=filters.region if filters else None,
            summary="정책 요약을 생성하지 못했습니다.",
        )
        return PolicySearchResponse(
            query=req.query,
            filters=filters,
            summary=summary,
            steps=[],
            source_urls=source_urls,
        )

    summary_data = data.get("summary", {})
    steps_data = data.get("steps", [])

    summary = PolicySummary(
        title=summary_data.get("title") or req.query,
        category=summary_data.get("category"),
        region=summary_data.get("region"),
        summary=summary_data.get("summary") or "",
        support_amount=summary_data.get("support_amount"),
        duration=summary_data.get("duration"),
        link=summary_data.get("link"),
    )

    steps: List[Step] = []
    for s in steps_data:
        try:
            steps.append(
                Step(
                    order=int(s.get("order", len(steps) + 1)),
                    title=s.get("title") or f"Step {len(steps) + 1}",
                    description=s.get("description") or "",
                )
            )
        except Exception:
            # JSON 안에 이상한 값이 섞여 있어도 전체가 깨지지 않도록 skip
            continue

    return PolicySearchResponse(
        query=req.query,
        filters=filters,
        summary=summary,
        steps=steps,
        source_urls=source_urls,
    )
