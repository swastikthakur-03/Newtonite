from typing import Optional
from sqlalchemy.orm import Session
from app.models.activity import ActivityLog

def log_activity(
    db: Session,
    work_item_id: int,
    actor_id: int,
    action: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
) -> ActivityLog:
    """
    Appends an activity entry to the database within the current session/transaction.
    This ensures atomic updates where work item mutations and audit history succeed or fail together.
    """
    log_entry = ActivityLog(
        work_item_id=work_item_id,
        actor_id=actor_id,
        action=action,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None
    )
    db.add(log_entry)
    return log_entry
