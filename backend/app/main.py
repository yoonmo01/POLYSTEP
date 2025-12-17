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
    origins: list[str] = [
        "http://localhost:5173",
        "http://13.125.63.208:5173",  # ✅ 외부 운영 테스트용 프론트
    ]

    # settings.frontend_origin 이 있으면 추가 (중복 허용 안 됨)
    if settings.frontend_origin and settings.frontend_origin not in origins:
        origins.append(settings.frontend_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )

    # 라우터 등록
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(policies.router, prefix="/policies", tags=["Policies"])
    app.include_router(scholarships.router, prefix="/scholarships", tags=["Scholarships"])
    app.include_router(me.router, prefix="/me", tags=["me"])
    return app


app = create_app()
