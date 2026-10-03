import datetime
from typing import Optional
from pydantic import BaseModel

class ActivityLogResponse(BaseModel):
    id: int
    work_item_id: int
    actor_id: int
    actor_name: str
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True
