from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User
from app.security import verify_token

# 🔥 HTTP Bearer 토큰 방식 (Swagger에서 "토큰만" 넣는 UI)
bearer_scheme = HTTPBearer(auto_error=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Authorization: Bearer <토큰>
    형태의 헤더에서 토큰만 떼어 와서 검증하는 의존성.
    Swagger /docs에서도 Authorize 눌러서 토큰만 넣으면 됨.
    """
    token = credentials.credentials  # "Bearer " 빼고 실제 토큰만

    try:
        token_data = verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.get(User, token_data.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
