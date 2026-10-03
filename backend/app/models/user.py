import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    team_memberships = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    assigned_work_items = relationship("WorkItem", back_populates="assignee", foreign_keys="WorkItem.assignee_id")
    created_work_items = relationship("WorkItem", back_populates="creator", foreign_keys="WorkItem.created_by")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="actor", cascade="all, delete-orphan")
