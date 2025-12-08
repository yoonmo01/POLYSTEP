# backend/app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

SQLALCHEMY_DATABASE_URL = settings.database_url
print("🔍 DB URL:", SQLALCHEMY_DATABASE_URL)  # 디버깅용

# ✅ PostgreSQL용 엔진 (sqlite 체크 제거)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # 연결 살아있는지 체크 (옵션이지만 있으면 좋음)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
