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

    # 온통청년 원본 정책 ID (plcyNo)
    policy_id = Column(String(32), unique=True, index=True, nullable=True)

    # 기본 정보
    title = Column(String(512), nullable=False)

    # 브라우저 검증에 사용할 대표 URL
    target_url = Column(String(1024), nullable=True)

    # 검색/요약용 원문 텍스트 (snippet + expln + support 등을 합친 것)
    raw_text = Column(Text, nullable=True)

    # ===== 메타데이터/필터 필드들 =====

    # 키워드 ("," 구분 문자열)
    keywords = Column(Text, nullable=True)

    # 카테고리
    category = Column(String(64), nullable=True)      # 예: 취업·일자리
    category_l = Column(String(64), nullable=True)    # 예: 일자리, 주거, 복지문화
    category_m = Column(String(64), nullable=True)    # 예: 취업, 창업, 문화활동 등

    # 지역
    region = Column(String(64), nullable=True)        # 시도 이름 (서울특별시 등)
    region_zip_first = Column(String(8), nullable=True)  # 5자리 법정동 앞자리 (11110 등)

    # 연령/소득/혼인
    age_min = Column(Integer, nullable=True)
    age_max = Column(Integer, nullable=True)
    age_limit_yn = Column(Boolean, nullable=True)         # Y/N → True/False
    income_condition = Column(Text, nullable=True)        # 소득 조건 원문
    marriage_code = Column(String(32), nullable=True)     # '상관없음', '기혼', '미혼' 등

    # 모집/사업 기간
    apply_period_type = Column(String(20), nullable=True)  # 상시모집 / 기간모집
    apply_period_raw = Column(String(100), nullable=True)  # "20250314 ~ 20251113"
    biz_start = Column(String(8), nullable=True)           # YYYYMMDD
    biz_end = Column(String(8), nullable=True)             # YYYYMMDD

    # 기관 정보
    provider_main = Column(String(255), nullable=True)
    provider_operator = Column(String(255), nullable=True)

    # URL들
    apply_url = Column(String(1024), nullable=True)
    ref_url_1 = Column(String(1024), nullable=True)
    ref_url_2 = Column(String(1024), nullable=True)

    # 설명 원문
    raw_expln = Column(Text, nullable=True)
    raw_support = Column(Text, nullable=True)
    raw_snippet = Column(Text, nullable=True)

    # 기타 메모
    notes = Column(Text, nullable=True)

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
