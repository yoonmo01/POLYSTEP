# app/schemas.py
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Dict

from pydantic import BaseModel, EmailStr


# ===== Auth =====
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str
    full_name: Optional[str] = None


class UserRead(UserBase):
    id: int
    full_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ===== Policy / Search (Fast Track) =====
class BadgeStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class PolicyBase(BaseModel):
    title: str
    target_url: Optional[str] = None
    raw_text: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    region: Optional[str] = None
    category: Optional[str] = None


class PolicyRead(PolicyBase):
    id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True  # 🔥 SQLAlchemy ORM → Pydantic 변환 허용


class PolicySearchRequest(BaseModel):
    query: Optional[str] = None
    age: Optional[int] = None
    region: Optional[str] = None
    category: Optional[str] = None


class PolicySearchResult(BaseModel):
    policy_id: int
    title: str
    badge_status: BadgeStatus
    short_summary: str
    has_verification_cache: bool
    last_verified_at: Optional[datetime] = None
    # 🔥 카드에 바로 쓸 메타 데이터들
    category: Optional[str] = None         # ex) "취업·일자리"
    category_l: Optional[str] = None       # ex) "일자리"
    category_m: Optional[str] = None       # ex) "창업"
    region: Optional[str] = None           # ex) "경기도"
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    apply_period_type: Optional[str] = None    # "상시모집" / "기간모집"
    biz_end: Optional[str] = None              # "YYYYMMDD" 문자열

class SimilarPoliciesResponse(BaseModel):
    """
    기준 정책 하나 + 유사 정책들 5개 정도를 한 번에 내려주는 응답 스키마.
    카드 UI 재사용을 위해 PolicySearchResult를 그대로 사용한다.
    """
    base_policy: PolicySearchResult
    similar_policies: List[PolicySearchResult]


# ===== Policy Verification (Deep Track) =====
class PolicyVerificationStatusEnum(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PolicyVerificationResponse(BaseModel):
    status: PolicyVerificationStatusEnum
    last_verified_at: Optional[datetime] = None
    evidence_text: Optional[str] = None
    extracted_criteria: Optional[Dict[str, Any]] = None
    navigation_path: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None

    # 🔥 ORM(PolicyVerification)에서 바로 변환 가능하게
    class Config:
        from_attributes = True


class PolicyVerificationRequest(BaseModel):
    force: bool = False  # 실패/오래된 캐시라도 강제 재검증 여부


class PolicyVerificationStatusResponse(BaseModel):
    status: PolicyVerificationStatusEnum
    message: str
    verification_id: Optional[int] = None
    cached: bool = False
    last_verified_at: Optional[datetime] = None


# ===== Policy 상세 + 검증정보 묶음 =====
class PolicyDetailResponse(BaseModel):
    policy: PolicyRead
    verification: Optional[PolicyVerificationResponse] = None

# ===== User Guide (B안: Deep Track facts + 사용자정보 → 최종 안내서) =====
class UserGuideRequest(BaseModel):
    age: Optional[int] = None
    region: Optional[str] = None
    # 필요하면 status(학생/취업/구직 등) 추가해도 됨


class UserGuideResponse(BaseModel):
    badge_status: BadgeStatus
    can_apply: bool
    summary: str
    required_documents: List[str] = []
    apply_steps: List[Dict[str, Any]] = []
    apply_channel: Optional[str] = None
    apply_period: Optional[str] = None
    contact: Dict[str, Any] = {}
    missing_info: List[str] = []
    evidence_text: Optional[str] = None