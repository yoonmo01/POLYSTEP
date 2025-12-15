# backend/app/scripts/import_scholarships_from_csv.py
import csv
from pathlib import Path
from typing import Optional

from app.db import SessionLocal
from app.models import Scholarship

# ✅ CSV 파일 경로 (프로젝트에 맞게 바꿔도 됨)
CSV_PATH = Path("C:/POLYSTEP/scholarship.csv")

# ✅ 출처 URL(원하면 나중에 Scholarship 테이블에 저장됨)
SOURCE_URL = "https://www.hallym.ac.kr/hallym/1112/subview.do"


def guess_category(name: str) -> Optional[str]:
    n = name.replace(" ", "")
    if "SW" in n or "소프트웨어" in n:
        return "SW"
    if "복지" in n:
        return "복지"
    if "근로" in n:
        return "근로"
    if "국제" in n or "해외" in n or "교환학생" in n:
        return "국제"
    if "특기" in n or "체육" in n:
        return "특기"
    if "성적" in n:
        return "성적"
    return "기타"


def open_csv_text(path: Path) -> str:
    """
    윈도우/엑셀 저장 때문에 인코딩이 섞일 수 있어서
    UTF-8-sig -> UTF-8 -> CP949 순으로 시도
    """
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # 여기까지 왔으면 인코딩이 특이한 케이스
    return path.read_text(errors="replace")


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV 파일이 없습니다: {CSV_PATH.resolve()}")

    csv_text = open_csv_text(CSV_PATH)

    db = SessionLocal()
    created = 0
    updated = 0
    skipped = 0

    try:
        reader = csv.DictReader(csv_text.splitlines())

        required_cols = {"장학금 명칭", "선발기준", "유지조건", "지급액"}
        headers = set(reader.fieldnames or [])
        if not required_cols.issubset(headers):
            raise RuntimeError(
                f"CSV 헤더가 예상과 다릅니다.\n"
                f"필요: {sorted(required_cols)}\n"
                f"현재: {sorted(headers)}"
            )

        for row in reader:
            name = (row.get("장학금 명칭") or "").strip()
            if not name:
                skipped += 1
                continue

            selection_criteria = (row.get("선발기준") or "").strip() or None
            retention_condition = (row.get("유지조건") or "").strip() or None
            benefit = (row.get("지급액") or "").strip() or None

            category = guess_category(name)

            obj = db.query(Scholarship).filter(Scholarship.name == name).first()
            if obj is None:
                obj = Scholarship(
                    name=name,
                    category=category,
                    selection_criteria=selection_criteria,
                    retention_condition=retention_condition,
                    benefit=benefit,
                    source_url=SOURCE_URL,
                )
                db.add(obj)
                created += 1
            else:
                obj.category = category
                obj.selection_criteria = selection_criteria
                obj.retention_condition = retention_condition
                obj.benefit = benefit
                obj.source_url = SOURCE_URL
                updated += 1

        db.commit()
        print(f"✅ Import 완료: created={created}, updated={updated}, skipped={skipped}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
