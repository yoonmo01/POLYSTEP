# backend/app/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    searches = relationship("PolicySearchLog", back_populates="user")


class PolicySearchLog(Base):
    __tablename__ = "policy_search_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query = Column(String(512), nullable=False)
    category = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 요약 결과 저장 (선택)
    summary_title = Column(String(512), nullable=True)
    summary_text = Column(Text, nullable=True)
    steps_json = Column(Text, nullable=True)  # Step-by-step JSON 문자열

    user = relationship("User", back_populates="searches")
