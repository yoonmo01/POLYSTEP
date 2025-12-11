from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# 🔥 pydantic AnyUrl -> str로 변환해서 넘기기
engine = create_engine(
    str(settings.database_url),  # 여기 str() 추가
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
