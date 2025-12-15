# app/services/text_bundle_service.py

import re
from typing import Any, Dict, List, Optional


def _clean_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u00a0", " ").replace("\u200b", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _limit(text: str, max_chars: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else (text[:max_chars] + "\n\n[...TRUNCATED...]")


class TextBundleService:
    """
    DB 정책정보 + browser 결과 + 첨부/이미지 OCR 텍스트를 “한 덩어리 번들”로 만드는 서비스
    (MVP에서는 chunk 요약 없이 길이만 제한)
    """

    @staticmethod
    def build_bundle(
        policy: Any,
        browser_result: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
        image_url_texts: List[Dict[str, Any]],
        max_total_chars: int = 220_000,
    ) -> Dict[str, Any]:
        policy_title = getattr(policy, "title", "") or ""
        policy_url = getattr(policy, "target_url", "") or ""
        policy_raw = getattr(policy, "raw_text", "") or ""

        criteria = (browser_result.get("criteria") or {}) if isinstance(browser_result, dict) else {}
        required_docs = browser_result.get("required_documents") or []
        apply_steps = browser_result.get("apply_steps") or []
        contact = browser_result.get("contact") or {}
        evidence_text = browser_result.get("evidence_text") or ""

        parts: List[str] = []

        parts.append("## [DB:정책기본정보]")
        parts.append(f"- title: {policy_title}")
        parts.append(f"- target_url: {policy_url}")
        parts.append(_clean_text(str(policy_raw))[:20_000])

        parts.append("\n## [Browser-Use:검증결과 요약]")
        parts.append(f"- criteria: {criteria}")
        parts.append(f"- required_documents: {required_docs}")
        parts.append(f"- apply_steps: {apply_steps}")
        parts.append(f"- contact: {contact}")

        parts.append("\n## [Browser-Use:근거원문(evidence_text)]")
        parts.append(_clean_text(str(evidence_text))[:45_000])

        parts.append("\n## [첨부파일/다운로드 텍스트 추출]")
        for a in artifacts[:30]:
            name = a.get("name") or a.get("path") or "artifact"
            st = a.get("source_type") or "file"
            meta = a.get("meta") or {}
            txt = _clean_text(a.get("text") or "")
            if not txt:
                parts.append(f"- ({st}) {name}: [NO_TEXT] meta={meta}")
            else:
                parts.append(f"\n### ({st}) {name}\n{_limit(txt, 25_000)}")

        parts.append("\n## [이미지 URL OCR 추출]")
        for it in image_url_texts[:20]:
            url = it.get("url") or ""
            meta = it.get("meta") or {}
            txt = _clean_text(it.get("text") or "")
            if not txt:
                parts.append(f"- (url) {url}: [NO_TEXT] meta={meta}")
            else:
                parts.append(f"\n### (url) {url}\n{_limit(txt, 18_000)}")

        bundle_text = "\n".join(parts)
        bundle_text = _clean_text(bundle_text)
        bundle_text = _limit(bundle_text, max_total_chars)

        return {
            "bundle_text": bundle_text,
            "stats": {
                "bundle_len": len(bundle_text),
                "artifacts_count": len(artifacts),
                "image_urls_count": len(image_url_texts),
            },
        }
