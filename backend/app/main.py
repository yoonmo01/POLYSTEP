# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, policies

app = FastAPI(
    title="PoliStep Backend",
    version="0.1.0",
)

# CORS 설정 (필요에 맞게 수정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 배포 시에는 프론트 도메인만 허용하도록 수정
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "PoliStep API is running"}


# 라우터 등록
app.include_router(auth.router)
app.include_router(policies.router)
