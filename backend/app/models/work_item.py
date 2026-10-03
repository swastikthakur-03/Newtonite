import enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Index, func
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class WorkItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

class WorkItemPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"

class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default=WorkItemStatus.OPEN.value, index=True)
    priority = Column(String(20), nullable=False, default=WorkItemPriority.MEDIUM.value, index=True)
    
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    due_date = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_work_items_team_status", "team_id", "status"),
        Index("ix_work_items_assignee_status", "assignee_id", "status"),
        Index("ix_work_items_team_created", "team_id", "created_at"),
        Index("ix_work_items_team_updated", "team_id", "updated_at"),
    )

    # Relationships
    team = relationship("Team", back_populates="work_items")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_work_items")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_work_items")
    comments = relationship("Comment", back_populates="work_item", cascade="all, delete-orphan", order_by="Comment.created_at.asc()")
    activity_logs = relationship("ActivityLog", back_populates="work_item", cascade="all, delete-orphan", order_by="ActivityLog.created_at.desc()")
