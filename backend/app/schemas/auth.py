import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Email cannot be blank")
        return cleaned

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank or whitespace only")
        if len(cleaned) > 100:
            raise ValueError("Name cannot exceed 100 characters")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        return str(v).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        encoded = v.encode("utf-8")
        if len(encoded) < 8:
            raise ValueError("Password must be at least 8 bytes")
        if len(encoded) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v

class TeamMembershipInfo(BaseModel):
    team_id: int
    team_name: str
    role: str

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool = False
    created_at: datetime.datetime
    memberships: List[TeamMembershipInfo] = []

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
