# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# 🔥 pydantic AnyUrl -> str로 변환해서 넘기기
engine = create_engine(
    str(settings.database_url),
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

Base = declarative_base()


# ✅ FastAPI Depends()에서 쓰는 DB 세션 의존성 추가
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
