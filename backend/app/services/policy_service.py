# backend/app/services/policy_service.py
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from ..schemas import PolicySearchRequest, PolicySearchResponse
from ..models import User
from .browser_service import search_policy_pages
from .parsing_service import extract_texts_from_files
from .llm_service import summarize_policy_and_make_steps


async def run_search_pipeline(
    req: PolicySearchRequest,
    user: User,
    db: Session,
) -> PolicySearchResponse:
    """
    전체 플로우 (3~8 단계) 오케스트레이션:

    3. 사용자가 카테고리/조건 선택 (req)
    4. 검색 버튼 클릭
    5. browser-use(+Gemini)로 실시간 검색 + 내용 수집 + 파일 다운로드
    6. 파일 텍스트 처리
    7. Gemini로 요약 + step-by-step 생성
    8. 결과 응답으로 반환
    """
    # 5. browser-use로 실시간 검색
    filters_dict: Dict[str, Any] | None = None
    if req.filters:
        filters_dict = req.filters.model_dump()

    pages: List[Dict[str, Any]] = search_policy_pages(
        query=req.query,
        filters=filters_dict,
    )

    # pages 안의 downloaded_files를 모아서 텍스트 추출
    all_file_paths: List[str] = []
    for p in pages:
        files = p.get("downloaded_files") or []
        all_file_paths.extend(files)

    extra_texts = extract_texts_from_files(all_file_paths)

    # 7. Gemini로 요약 + step-by-step
    result: PolicySearchResponse = summarize_policy_and_make_steps(
        req=req,
        pages=pages,
        extra_texts=extra_texts,
    )

    return result