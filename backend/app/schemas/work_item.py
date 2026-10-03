import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.models.work_item import WorkItemStatus, WorkItemPriority

class WorkItemCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: WorkItemPriority = WorkItemPriority.MEDIUM
    team_id: int
    assignee_id: Optional[int] = None
    due_date: Optional[datetime.datetime] = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Title cannot be blank or whitespace only")
        if len(cleaned) > 255:
            raise ValueError("Title cannot exceed 255 characters")
        return cleaned

class WorkItemUpdate(BaseModel):
    version: int = Field(..., description="Expected version for optimistic concurrency control")
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[WorkItemStatus] = None
    priority: Optional[WorkItemPriority] = None
    due_date: Optional[datetime.datetime] = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Title cannot be blank or whitespace only")
        if len(cleaned) > 255:
            raise ValueError("Title cannot exceed 255 characters")
        return cleaned

class WorkItemClaim(BaseModel):
    version: Optional[int] = Field(None, description="Optional expected version for optimistic concurrency control")

class WorkItemAssign(BaseModel):
    version: int = Field(..., description="Expected version for optimistic concurrency control")
    assignee_id: Optional[int] = Field(None, description="User ID to assign to, or null to unassign")

class WorkItemResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    team_id: int
    team_name: str
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    created_by: int
    creator_name: str
    due_date: Optional[datetime.datetime] = None
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class WorkItemListResponse(BaseModel):
    items: List[WorkItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class DashboardStatsResponse(BaseModel):
    open_count: int
    in_progress_count: int
    urgent_count: int
    blocked_count: int
    my_assigned_count: int
    my_assigned_items: List[WorkItemResponse] = []
    urgent_items: List[WorkItemResponse] = []
    recent_items: List[WorkItemResponse] = []
