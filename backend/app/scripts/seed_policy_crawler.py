# backend/scripts/seed_policy_crawler.py

"""
초기 정책 데이터를 자동으로 수집하는 스크립트 (강원도 전용 테스트 버전).

browser-use + ChatGoogle 기반 자동 검색
JSON 파싱 안정화 (Final Result + 기타 텍스트 제거)
검색 실패 시 자동 재시도

실행:
    (.venv) python -m scripts.seed_policy_crawler
"""

import asyncio
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatGoogle

load_dotenv()

# ==========================
# 설정
# ==========================

YOUTHCENTER_SEARCH_URL = "https://www.youthcenter.go.kr/youthPolicy/ythPlcyTotalSearch.do"

SEARCH_CONFIGS = [
    {"query": "청년", "region": "강원도"},
    {"query": "생활", "region": "강원도"},
    {"query": "주거", "region": "강원도"},
    {"query": "일자리", "region": "강원도"},
    {"query": "창업", "region": "강원도"},
    {"query": "교육", "region": "강원도"},
]

MAX_TOTAL_POLICIES = 10  # 테스트용

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "data" / "seed_policies.csv"


# ==========================
# JSON 파싱 헬퍼
# ==========================

def extract_json_array(text: str) -> str | None:
    """
    browser-use 출력물에서 JSON 배열만 추출하는 함수.
    예: 'Final Result:\n[ {...}, ... ]\nAgentHistoryList(...)'
    """
    start = text.find("[{")
    end = text.rfind("}]")

    if start == -1 or end == -1:
        return None

    return text[start : end + 2]


# ==========================
# 크롤링 함수
# ==========================

async def fetch_policies_from_youthcenter(query: str, region: str, retry: int = 2) -> List[Dict[str, Any]]:
    """
    browser-use Agent를 사용해서 정책 목록을 가져온다.
    JSON 파싱 실패 시 문자열에서 JSON 배열만 추출해 재파싱한다.
    """

    task = f"""
    너는 웹 브라우저를 조작해서 청년 정책 목록을 수집하는 봇이야.

    1. "{YOUTHCENTER_SEARCH_URL}" 로 이동한다.
    2. 팝업이 있다면 닫는다.
    3. 검색창에 "{query}" 입력.
    4. 지역/시도 필터에서 "{region}" 선택.
    5. 검색 버튼 클릭.
    6. 첫 페이지에서 최대 10개의 정책 정보를 수집:
        - title
        - url
        - region
        - raw_snippet
    7. 반드시 아래 JSON 배열만 출력:
        [
          {{
            "title": "...",
            "url": "https://....",
            "region": "...",
            "raw_snippet": "..."
          }}
        ]
    8. 다른 텍스트 절대 출력하지 마라.
    """

    llm = ChatGoogle(model="gemini-flash-latest")
    browser = Browser(headless=True)

    for attempt in range(1, retry + 1):
        try:
            agent = Agent(task=task, llm=llm, browser=browser)
            result = await agent.run()

            raw_output = result.output if hasattr(result, "output") else str(result)

            # --- 1차: 바로 JSON 파싱 시도 ---
            try:
                data = json.loads(raw_output)
            except Exception:
                # --- 2차: JSON 배열만 추출해서 재파싱 ---
                json_str = extract_json_array(raw_output)
                if not json_str:
                    raise ValueError("JSON 배열을 결과에서 찾지 못함")

                data = json.loads(json_str)

            if not isinstance(data, list):
                return []

            # -------- 정제 -------
            cleaned = []
            for item in data:
                if not isinstance(item, dict):
                    continue

                title = item.get("title")
                url = item.get("url") or item.get("link")
                snippet = item.get("raw_snippet") or item.get("snippet")
                region_val = item.get("region") or region

                if not title or not url:
                    continue

                cleaned.append(
                    {
                        "title": title.strip(),
                        "target_url": url.strip(),
                        "region": region_val.strip(),
                        "raw_snippet": (snippet or "").strip(),
                    }
                )

            return cleaned

        except Exception as e:
            print(f"[ERROR] (시도 {attempt}/{retry}) fetch 실패: {e}")

            if attempt == retry:
                print("[ERROR] 모든 재시도 실패 → 빈 배열 반환")
                return []

            print("[INFO] 1초 후 재시도…")
            await asyncio.sleep(1)


# ==========================
# 수집 loop
# ==========================

async def collect_seed_policies() -> List[Dict[str, Any]]:
    all_items: Dict[str, Dict[str, Any]] = {}

    for cfg in SEARCH_CONFIGS:
        query = cfg["query"]
        region = cfg["region"]
        print(f"\n===== 검색 시작: query='{query}', region='{region}' =====")

        items = await fetch_policies_from_youthcenter(query, region)

        print(f"[INFO]  -> {len(items)}개 수집")

        for item in items:
            url = item["target_url"]
            if url not in all_items:
                all_items[url] = item

            if len(all_items) >= MAX_TOTAL_POLICIES:
                print(f"[INFO] 최대 {MAX_TOTAL_POLICIES}개 도달 → 중단")
                return list(all_items.values())

    return list(all_items.values())


# ==========================
# CSV 저장
# ==========================

def save_to_csv(policies: List[Dict[str, Any]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["title", "target_url", "region", "raw_snippet"]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in policies:
            writer.writerow(p)

    print(f"[INFO] CSV 저장 완료: {OUTPUT_PATH} (총 {len(policies)}개)")


# ==========================
# 실행
# ==========================

async def async_main():
    policies = await collect_seed_policies()
    print(f"\n[INFO] 최종 수집 개수: {len(policies)}개\n")
    save_to_csv(policies)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
