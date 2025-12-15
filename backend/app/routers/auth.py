#app/routers/auth.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas import UserCreate, UserRead, Token, LoginRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserRead)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    회원가입: email / password / full_name으로 User 생성
    """
    user = AuthService.register(db, user_in)
    return user


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    로그인: JSON으로 email / password를 받아서 토큰만 돌려줌.
    이후 인증은 이 토큰만 있으면 됨.
    """
    token = AuthService.login(db, body.email, body.password)
    return Token(access_token=token)
