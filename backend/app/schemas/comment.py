import datetime
from pydantic import BaseModel, Field, field_validator

class CommentCreate(BaseModel):
    content: str = Field(..., description="Comment content cannot be empty")

    @field_validator("content")
    @classmethod
    def clean_content(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Comment content cannot be blank or whitespace only")
        return cleaned

class CommentResponse(BaseModel):
    id: int
    work_item_id: int
    author_id: int
    author_name: str
    content: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
