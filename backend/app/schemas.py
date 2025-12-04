# backend/app/schemas.py
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr


# ---- Auth ----

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None


# ---- Policy Search ----

class PolicySearchFilters(BaseModel):
    category: Optional[str] = None  # 예: "주거", "일자리"
    region: Optional[str] = None    # 예: "강원", "전국"
    age: Optional[int] = None
    status: Optional[str] = None    # 예: "대학생", "취준생"


class PolicySearchRequest(BaseModel):
    query: str
    filters: Optional[PolicySearchFilters] = None


class Step(BaseModel):
    order: int
    title: str
    description: str


class PolicySummary(BaseModel):
    title: str
    category: Optional[str] = None
    region: Optional[str] = None
    summary: str
    support_amount: Optional[str] = None
    duration: Optional[str] = None
    link: Optional[str] = None


class PolicySearchResponse(BaseModel):
    query: str
    filters: Optional[PolicySearchFilters] = None
    summary: PolicySummary
    steps: List[Step]
    source_urls: List[str] = []
