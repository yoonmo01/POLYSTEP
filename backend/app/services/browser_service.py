# backend/app/services/browser_service.py
import asyncio
import json
from typing import Any, Dict, List

from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatGoogle

from ..utils.file_utils import get_download_dir

load_dotenv()


async def search_policy_pages_async(
    query: str,
    filters: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    browser-use + ChatGoogle(Gemini)를 사용해서
    정책 관련 페이지를 탐색하고,
    title / url / raw_text / downloaded_files 리스트를 반환.
    """
    filter_desc = ""
    if filters:
        if filters.get("category"):
            filter_desc += f' 분야: {filters["category"]}.'
        if filters.get("region"):
            filter_desc += f' 지역: {filters["region"]}.'
        if filters.get("age"):
            filter_desc += f' 나이: {filters["age"]}세.'
        if filters.get("status"):
            filter_desc += f' 상태: {filters["status"]}.'

    task = f"""
너는 한국 청년 정책/장학금 정보를 찾는 브라우저 에이전트다.

[사용자 조건]
- 검색어: "{query}"
- 추가 조건: {filter_desc if filter_desc else "명시된 추가 조건 없음"}

[중요 규칙 — 반드시 아래를 지켜라]
1. 반드시 이 웹사이트만 사용하라:
   ▶ https://www.youthcenter.go.kr

2. 네이버, 구글, 다음 등 외부 검색 엔진은 절대 사용하지 마라.
3. 새로운 탭을 열어도 반드시 https://www.youthcenter.go.kr 내부에서만 탐색하라.
4. 외부 링크가 뜨면 클릭하지 말고 무시하라.

[요구사항]
1. https://www.youthcenter.go.kr 사이트 내부 검색 기능을 사용하여 관련 정책 공고 페이지를 최대 3개 찾으라.
2. 각 정책 상세 페이지에서 다음 정보를 추출하라:
   - 정책 이름 또는 페이지 제목: title
   - 페이지 URL: url
   - 본문에서 정책 내용을 최대한 많이 추출한 텍스트: raw_text
   - 첨부파일(HWP, PDF, 이미지 등)이 있다면 다운로드하고 downloaded_files에 저장 경로를 기록하라.

3. 최종 출력은 아래 JSON 배열 형식 ONLY:

예시:
[
  {{
    "title": "정책 또는 페이지 제목",
    "url": "페이지 URL",
    "raw_text": "본문 텍스트",
    "downloaded_files": ["파일경로1", "파일경로2"]
  }}
]

4. 아무 페이지도 찾지 못하면 빈 배열([])만 출력하라.
5. 자연어 설명, 불필요한 문장, JSON 외 형식은 절대 출력하지 마라. JSON ONLY.
"""

    download_dir = get_download_dir()

    # ✅ Browser-Use Cloud 사용 (로컬 크롬 띄우는 대신 클라우드 브라우저 사용)
    browser = Browser(
        use_cloud=True,           # 🔴 기존: cloud=True (오류) → ✅ 정답: use_cloud=True
        accept_downloads=True,
        downloads_path=download_dir,
        # profile_id는 UUID 형식이 아니라서 클라우드에서 422 에러 나므로 지정하지 않음
    )

    # ✅ Gemini(Google) LLM 사용
    llm = ChatGoogle(model="gemini-flash-latest")

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    # 에이전트 실행
    history = await agent.run(max_steps=50)
    final_text = history.final_result()

    # 에이전트가 최종적으로 출력한 JSON 파싱
    try:
        data = json.loads(final_text)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        # JSON 형식이 아니면 일단 빈 리스트 반환
        return []
