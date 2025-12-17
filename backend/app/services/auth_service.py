#app/services/auth_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import User
from app.schemas import UserCreate
from app.security import get_password_hash, verify_password, create_access_token


class AuthService:
    @staticmethod
    def register(db: Session, user_in: UserCreate) -> User:
        existing = db.query(User).filter(User.email == user_in.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = get_password_hash(user_in.password)
        user = User(
            email=user_in.email,
            hashed_password=hashed,
            full_name=user_in.full_name,
            age=user_in.age,
            region=user_in.region,
            is_student=user_in.is_student,
            academic_status=user_in.academic_status,
            major=user_in.major,
            grade=user_in.grade,
            gpa=user_in.gpa,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, email: str, password: str) -> str:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        return create_access_token(user_id=user.id)
