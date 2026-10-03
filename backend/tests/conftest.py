import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.team import Team, TeamMember, TeamRole
from app.models.work_item import WorkItem, WorkItemStatus, WorkItemPriority
from app.main import app

# Target the dedicated PostgreSQL test database
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres@localhost:5433/newtonite_test_db"
)

engine = create_engine(TEST_DB_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Initializes tables in the test database once per session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Note: Table contents are truncated per function test; keep schema intact

@pytest.fixture(scope="function")
def db_session():
    """Provides a fresh database session for each test, truncating all tables afterwards."""
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()

    # Clean truncate across all tables for pristine test isolation
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE idempotency_records, activity_logs, comments, work_items, team_members, teams, users RESTART IDENTITY CASCADE;"))
        conn.commit()

@pytest.fixture(scope="function")
def client(db_session):
    """Provides a TestClient with database session overridden using dedicated sessions per request."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def seed_data(db_session):
    """Seeds two isolated teams with an Admin, Manager, and Members."""
    pwd = hash_password("testpass123")

    # Users
    admin = User(name="Global Admin", email="admin@test.com", password_hash=pwd, is_admin=True)
    mgr_a = User(name="Manager Alpha", email="manager_a@test.com", password_hash=pwd, is_admin=False)
    mem_a1 = User(name="Member Alpha 1", email="member_a1@test.com", password_hash=pwd, is_admin=False)
    mem_a2 = User(name="Member Alpha 2", email="member_a2@test.com", password_hash=pwd, is_admin=False)
    mem_b = User(name="Member Beta", email="member_b@test.com", password_hash=pwd, is_admin=False)

    db_session.add_all([admin, mgr_a, mem_a1, mem_a2, mem_b])
    db_session.commit()

    # Teams
    team_a = Team(name="Alpha Operations")
    team_b = Team(name="Beta Security")
    db_session.add_all([team_a, team_b])
    db_session.commit()

    # Memberships (Admin has no team rows; global admin is derived from is_admin=True)
    memberships = [
        TeamMember(team_id=team_a.id, user_id=mgr_a.id, role=TeamRole.MANAGER.value),
        TeamMember(team_id=team_a.id, user_id=mem_a1.id, role=TeamRole.MEMBER.value),
        TeamMember(team_id=team_a.id, user_id=mem_a2.id, role=TeamRole.MEMBER.value),
        TeamMember(team_id=team_b.id, user_id=mem_b.id, role=TeamRole.MEMBER.value),
    ]
    db_session.add_all(memberships)
    db_session.commit()

    # Create unassigned work item in Team A
    item_a_unassigned = WorkItem(
        title="Unassigned Alpha Task",
        description="Task waiting for someone to claim",
        status=WorkItemStatus.OPEN.value,
        priority=WorkItemPriority.MEDIUM.value,
        team_id=team_a.id,
        assignee_id=None,
        created_by=mgr_a.id,
        version=1
    )
    # Create assigned work item in Team B
    item_b_assigned = WorkItem(
        title="Beta Confidential Incident",
        description="Security vulnerability investigation in Beta",
        status=WorkItemStatus.IN_PROGRESS.value,
        priority=WorkItemPriority.URGENT.value,
        team_id=team_b.id,
        assignee_id=mem_b.id,
        created_by=mem_b.id,
        version=1
    )
    db_session.add_all([item_a_unassigned, item_b_assigned])
    db_session.commit()

    return {
        "admin": admin,
        "mgr_a": mgr_a,
        "mem_a1": mem_a1,
        "mem_a2": mem_a2,
        "mem_b": mem_b,
        "team_a": team_a,
        "team_b": team_b,
        "item_a_unassigned": item_a_unassigned,
        "item_b_assigned": item_b_assigned,
        "tokens": {
            "admin": create_access_token(admin.id),
            "mgr_a": create_access_token(mgr_a.id),
            "mem_a1": create_access_token(mem_a1.id),
            "mem_a2": create_access_token(mem_a2.id),
            "mem_b": create_access_token(mem_b.id),
        }
    }
