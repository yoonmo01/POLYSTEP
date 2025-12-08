# backend/app/security.py
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import settings

# ✅ bcrypt 대신 pbkdf2_sha256 사용 (bcrypt 72바이트 문제 회피)
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24시간


class TokenData(BaseModel):
    id: int | None = None
    email: str | None = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    data 안에는 보통 {"sub": user.email} 이런 식으로 들어온다고 가정.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    JWT를 디코딩해서 TokenData(id=..., email=...) 형태로 반환.
    유효하지 않으면 None 리턴.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[ALGORITHM],
        )

        # 지금 토큰 구조랑 맞춰서 꺼내기
        user_id = payload.get("sub_id")
        email = payload.get("sub_email") or payload.get("email") or payload.get("sub")

        if email is None:
            return None

        return TokenData(id=user_id, email=email)
    except JWTError:
        return None
