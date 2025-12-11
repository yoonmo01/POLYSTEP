#app/models.py
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db import Base


class PolicyVerificationStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    target_url = Column(String(1024), nullable=True)
    raw_text = Column(Text, nullable=True)

    # 간단한 필터용 필드들
    age_min = Column(Integer, nullable=True)
    age_max = Column(Integer, nullable=True)
    region = Column(String(64), nullable=True)
    category = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    verifications = relationship(
        "PolicyVerification",
        back_populates="policy",
        cascade="all, delete-orphan",
    )


class PolicyVerification(Base):
    __tablename__ = "policy_verifications"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)

    status = Column(
        String(16),
        default=PolicyVerificationStatus.PENDING.value,
        index=True,
    )

    extracted_criteria = Column(JSON, nullable=True)
    evidence_text = Column(Text, nullable=True)
    navigation_path = Column(JSON, nullable=True)

    last_verified_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    policy = relationship("Policy", back_populates="verifications")
