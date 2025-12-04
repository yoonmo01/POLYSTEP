# backend/app/services/browser_service.py
import asyncio
import json
from typing import Any, Dict, List

from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatGoogle

from ..utils.file_utils import get_download_dir

load_dotenv()


async def _search_policy_pages_async(
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

    # 프롬프트 안에는 ``` 같은 코드펜스 사용하지 않음
    task = f"""
너는 한국 청년 정책/장학금 정보를 찾는 브라우저 에이전트다.

[사용자 조건]
- 검색어: "{query}"
- 추가 조건: {filter_desc if filter_desc else "명시된 추가 조건 없음"}

[요구사항]
1. 정책/장학금 관련 공공 사이트(정부, 지자체, 공공기관, 대학교)를 우선적으로 방문하라.
2. 검색 엔진(네이버, 구글 등)을 활용해서 관련된 정책 공고 페이지를 최대 3개까지 찾으라.
3. 각 페이지에 대해 다음 정보를 수집하라.
   - 정책 이름 또는 페이지 제목: title
   - 페이지 URL: url
   - 본문에서 정책 내용을 최대한 많이 추출한 텍스트: raw_text
   - 첨부파일(HWP, PDF, 이미지 등)이 있다면 모두 다운로드하고, 로컬 경로를 downloaded_files에 기록하라.

4. 최종 결과는 아래 JSON 배열 형식으로만 출력하라.

예시:
[
  {{
    "title": "정책 또는 페이지 제목",
    "url": "페이지 URL",
    "raw_text": "페이지 본문에서 추출한 텍스트",
    "downloaded_files": ["다운로드된 파일의 로컬 경로 1", "로컬 경로 2"]
  }}
]

5. 아무 페이지도 찾지 못하면 빈 배열([])만 그대로 출력하라.
추가 설명이나 자연어 문장은 절대 출력하지 마라. JSON만 출력하라.
"""

    download_dir = get_download_dir()

    browser = Browser(
        headless=True,
        accept_downloads=True,
        downloads_path=download_dir,
    )

    # browser-use에서 제공하는 Gemini 래퍼
    llm = ChatGoogle(model="gemini-flash-latest")

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    history = await agent.run(max_steps=50)
    final_text = history.final_result()

    try:
        data = json.loads(final_text)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        # 파싱 실패 시 안전하게 빈 리스트 반환
        return []


def search_policy_pages(
    query: str,
    filters: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    동기 코드(FastAPI 서비스 등)에서 호출하기 위한 wrapper.
    FastAPI 엔드포인트가 async이면 가능하면 아래 비동기 함수를 직접 await 하는 게 더 좋다.
    """
    return asyncio.run(_search_policy_pages_async(query, filters))
