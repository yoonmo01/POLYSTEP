# app/services/browser_service.py

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable

from dotenv import load_dotenv

from browser_use import Agent, Browser, ChatGoogle

from app.utils.file_utils import ensure_download_dir
from app.models import Policy

load_dotenv()
logger = logging.getLogger(__name__)

# WebSocket 쪽에서는 async 콜백을 쓸 수 있으니까 이렇게 타입 정의
AsyncLogCallback = Optional[Callable[[str], Awaitable[None]]]


class BrowserService:
    """
    browser-use + Gemini를 사용해서
    실제 브라우저를 돌려 정책 자격 요건을 검증하는 서비스.
    - REST Deep Track: verify_policy_sync() (BackgroundTasks 에서 호출)
    - WebSocket Deep Track: verify_policy_with_agent / verify_policy_with_playwright_shortcut
    """

    # ======================
    # 공통: Agent 실행 헬퍼
    # ======================
    @staticmethod
    async def _run_agent(
        task: str,
        log_callback: AsyncLogCallback = None,
    ) -> Dict[str, Any]:
        """
        browser-use Agent 한 번 실행하고
        최종 결과를 JSON 형태로 파싱해서 리턴.
        """
        if log_callback:
            await log_callback("브라우저 세션 준비 중...")

        downloads_dir = ensure_download_dir()
        logger.info(f"[BrowserService] Using downloads_dir={downloads_dir}")

        # 🔥 중요: downloads_path 로 써야 함 (download_path 아님!)
        browser = Browser(
            headless=False,
            downloads_path=downloads_dir,
        )

        # Gemini (Google API 키는 .env 의 GOOGLE_API_KEY 사용)
        llm = ChatGoogle(model="gemini-2.5-flash-lite")

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
        )

        if log_callback:
            await log_callback("에이전트 실행 시작...")

        history = await agent.run()

        if log_callback:
            await log_callback("에이전트 실행 완료, 결과 파싱 중...")

        # browser-use history 에 final_result()가 있다고 가정
        try:
            final_text = history.final_result()  # type: ignore[attr-defined]
        except Exception:
            final_text = str(history)

        logger.info(f"[BrowserService] final_result text snippet: {final_text[:500]}")

        try:
            parsed = json.loads(final_text)
        except Exception:
            # JSON 포맷이 아니면 raw 텍스트로라도 돌려주기
            parsed = {"raw": final_text}

        criteria = (
            parsed.get("criteria")
            or parsed.get("extracted_criteria")
            or {}
        )
        evidence_text = (
            parsed.get("evidence_text")
            or parsed.get("evidence")
            or final_text
        )
        navigation_path = parsed.get("navigation_path") or []

        return {
            "criteria": criteria,
            "evidence_text": evidence_text,
            "navigation_path": navigation_path,
        }

    # ======================
    # 1차: 탐색형 Agent 모드
    # ======================
    @staticmethod
    async def verify_policy_with_agent(
        policy: Policy,
        log_callback: AsyncLogCallback = None,
    ) -> Dict[str, Any]:
        """
        navigation_path 없이 처음부터 페이지를 탐색하면서
        '지원대상/신청자격/선정기준'을 찾아 자격 요건을 추출하는 모드.
        """
        title = policy.title or ""
        url = policy.target_url or ""

        task = f"""
너는 대한민국 청년정책을 분석하는 전문 에이전트야.

아래 정책의 공식 안내 페이지에 접속해서,
특히 '지원대상', '신청자격', '선정기준'을 찾아서 정리해야 한다.

- 정책 제목: {title}
- 접속해야 할 URL: {url}

작업 단계:
1. 지정된 URL로 이동한다.
2. 팝업/알림 등이 뜨면 모두 닫는다.
3. 페이지에서 '지원대상', '신청자격', '선정기준', '지원내용' 과 관련된 섹션을 찾는다.
4. 해당 섹션의 텍스트를 최대한 많이 수집한다.
5. 수집한 텍스트를 기반으로 아래 JSON 형식으로만 최종 답변을 출력한다.

반드시 아래 JSON 형식만 출력해라. (추가 설명/문장 금지)

{{
  "criteria": {{
    "age": "연령 요건을 한국어로 간단 요약. 없으면 '제한 없음'이라고 적기.",
    "region": "거주지/주소 요건이 있으면 요약, 없으면 '제한 없음'.",
    "income": "소득/재산 기준이 있으면 요약, 없으면 '제한 없음'.",
    "employment": "재직/구직/창업 등 고용 상태 기준이 있으면 요약, 없으면 '제한 없음'.",
    "other": "기타 주요 자격요건을 한 줄로 정리. 없으면 '없음'."
  }},
  "evidence_text": "위 기준을 판단하는 근거가 된 원문 문장을 한국어로 여러 줄 이어서 붙여넣기.",
  "navigation_path": []
}}
        """.strip()

        return await BrowserService._run_agent(task, log_callback)

    # =================================
    # 2차: navigation_path 재사용 모드
    # =================================
    @staticmethod
    async def verify_policy_with_playwright_shortcut(
        policy: Policy,
        navigation_path: List[Dict[str, Any]],
        log_callback: AsyncLogCallback = None,
    ) -> Dict[str, Any]:
        """
        이전 실행에서 저장한 navigation_path 정보를 힌트로 줘서
        더 빠르게 자격 요건 섹션에 도달하려는 모드.
        (지금은 '힌트 기반 Agent' 정도로만 구현해두고,
         나중에 진짜 Playwright 액션 재생으로 바꿔도 됨)
        """
        title = policy.title or ""
        url = policy.target_url or ""

        path_hint = json.dumps(navigation_path, ensure_ascii=False)

        task = f"""
너는 대한민국 청년정책을 분석하는 전문 에이전트야.

아래 정책의 공식 안내 페이지에 접속해서,
'지원대상', '신청자격', '선정기준' 섹션을 빠르게 찾아야 한다.

- 정책 제목: {title}
- 접속해야 할 URL: {url}

이전 실행에서 사용했던 네비게이션 경로 힌트가 있다.  
가능하면 이 힌트를 참고해서 비슷한 경로로 빠르게 이동하되,
페이지 구조가 바뀌었으면 유연하게 다시 탐색해라.

이전 navigation_path 힌트:
{path_hint}

작업 단계:
1. URL로 이동한다.
2. 팝업/알림이 뜨면 닫는다.
3. 힌트에 있는 경로를 참고해서 비슷한 버튼/탭/링크를 클릭해본다.
4. 그래도 안 보이면 직접 '지원대상', '신청자격', '선정기준'과 비슷한 텍스트를 찾아 스크롤/검색한다.
5. 관련 섹션 텍스트를 수집한 뒤 아래 JSON 형식으로만 결과를 출력한다.

반드시 아래 JSON 형식만 출력해라. (추가 설명/문장 금지)

{{
  "criteria": {{
    "age": "연령 요건 요약 또는 '제한 없음'.",
    "region": "거주지 요건 요약 또는 '제한 없음'.",
    "income": "소득/재산 기준 요약 또는 '제한 없음'.",
    "employment": "고용 상태 기준 요약 또는 '제한 없음'.",
    "other": "기타 주요 자격 요건 한 줄 또는 '없음'."
  }},
  "evidence_text": "근거가 된 원문 텍스트를 한국어로 여러 줄 이어서 붙여넣기.",
  "navigation_path": []
}}
        """.strip()

        if log_callback:
            await log_callback("Playwright 지름길(힌트 기반) 모드로 검증 시작...")

        return await BrowserService._run_agent(task, log_callback)

    # =========================================
    # REST Deep Track용: 동기 wrapper (필수!)
    # =========================================
    @staticmethod
    def verify_policy_sync(
        policy: Policy,
        navigation_path: Optional[List[Dict[str, Any]]] = None,
        log_callback: Optional[Callable[[str], Any]] = None,
    ) -> Dict[str, Any]:
        """
        PolicyVerificationService.run_verification_job_sync() 에서 호출되는 동기 함수.
        내부에서 asyncio.run()으로 위의 async 함수들을 실행한다.
        (BackgroundTasks는 sync 함수도 잘 실행시켜 주므로 이 형태가 편함)
        """

        async def _runner() -> Dict[str, Any]:
            # REST BackgroundTask에서는 WebSocket처럼 async 콜백이 없으니
            # 여기서는 log_callback은 그냥 무시하거나 print만 써도 된다.
            if navigation_path:
                return await BrowserService.verify_policy_with_playwright_shortcut(
                    policy,
                    navigation_path,
                    None,
                )
            return await BrowserService.verify_policy_with_agent(policy, None)

        # BackgroundTasks 내에서는 asyncio.run() 사용해도 됨 (별도 context)
        return asyncio.run(_runner())

    # =================================
    # (옵션) 나중용: 검색용 더미 함수
    # =================================
    @staticmethod
    async def search_policy_pages_async(
        query: str,
        filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        나중에 온통청년 통합검색 같은 곳을 browser-use로 돌릴 때 사용할 자리.
        지금은 Deep Track 검증에 집중하므로 더미 구현으로 둔다.
        """
        logger.info(
            f"[BrowserService] search_policy_pages_async called query={query}, filters={filters}"
        )
        return []
