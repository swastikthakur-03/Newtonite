import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from app.models.team import TeamRole

class TeamCreateRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Team name cannot be blank or whitespace only")
        if len(cleaned) > 100:
            raise ValueError("Team name cannot exceed 100 characters")
        return cleaned

class TeamMemberResponse(BaseModel):
    id: int
    user_id: int
    team_id: int
    user_name: str
    user_email: str
    role: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class TeamResponse(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime
    member_count: Optional[int] = None

    class Config:
        from_attributes = True

class TeamDetailResponse(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime
    members: List[TeamMemberResponse] = []

    class Config:
        from_attributes = True

class AddTeamMemberRequest(BaseModel):
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None
    role: TeamRole = TeamRole.MEMBER

    @model_validator(mode="after")
    def check_user_identifier(self):
        if self.user_id is None and not self.email:
            raise ValueError("Either user_id or email must be provided")
        return self
