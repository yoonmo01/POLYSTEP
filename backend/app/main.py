# app/main.py
import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
print("EVENT LOOP POLICY =", type(asyncio.get_event_loop_policy()).__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, policies, scholarships, me

# ✅ 여기 추가
from app.db import Base, engine
from app import models  # noqa: F401  # 모델 import 해서 Base에 모두 등록되도록

def create_app() -> FastAPI:
    # ✅ 서버 시작할 때 테이블 자동 생성 (없으면 만들고, 있으면 무시)
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title=settings.app_name)

    # CORS 설정
    origins: list[str] = []
    if settings.frontend_origin:
        origins.append(settings.frontend_origin)
    origins.append("http://localhost:5173")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(policies.router, prefix="/policies", tags=["Policies"])
    app.include_router(scholarships.router, prefix="/scholarships", tags=["Scholarships"])
    app.include_router(me.router, prefix="/me", tags=["me"])
    return app


app = create_app()
