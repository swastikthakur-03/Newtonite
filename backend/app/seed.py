import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.core.security import hash_password
from app.models.user import User
from app.models.team import Team, TeamMember, TeamRole
from app.models.work_item import WorkItem, WorkItemStatus, WorkItemPriority
from app.models.comment import Comment
from app.models.activity import ActivityLog

def seed_database():
    print("--- Initializing database session ---")
    db: Session = SessionLocal()

    try:
        # Check if users already seeded
        if db.query(User).first():
            print("Database already contains data. Skipping initial seeding.")
            return

        print("--- Seeding Users ---")
        common_password = hash_password("password123")
        
        admin_user = User(
            name="Alex Mercer (Admin)",
            email="admin@newtonite.internal",
            password_hash=common_password,
            is_admin=True,
        )
        priya_mgr = User(
            name="Priya Sharma (Manager)",
            email="priya.manager@newtonite.internal",
            password_hash=common_password,
            is_admin=False,
        )
        rahul_member = User(
            name="Rahul Verma (Member)",
            email="rahul.member@newtonite.internal",
            password_hash=common_password,
            is_admin=False,
        )
        swastik_mgr = User(
            name="Swastik Roy (Manager)",
            email="swastik.ops@newtonite.internal",
            password_hash=common_password,
            is_admin=False,
        )
        ananya_member = User(
            name="Ananya Patel (Member)",
            email="ananya.fraud@newtonite.internal",
            password_hash=common_password,
            is_admin=False,
        )

        db.add_all([admin_user, priya_mgr, rahul_member, swastik_mgr, ananya_member])
        db.flush()

        print("--- Seeding Teams ---")
        eng_team = Team(name="Engineering Core")
        ops_team = Team(name="Customer Operations")
        fraud_team = Team(name="Payments & Fraud")

        db.add_all([eng_team, ops_team, fraud_team])
        db.flush()

        print("--- Seeding Team Memberships ---")
        memberships = [
            # System admin has no team rows; global admin is derived from is_admin=True

            # Priya is MANAGER in Engineering, MEMBER in Operations
            TeamMember(team_id=eng_team.id, user_id=priya_mgr.id, role=TeamRole.MANAGER.value),
            TeamMember(team_id=ops_team.id, user_id=priya_mgr.id, role=TeamRole.MEMBER.value),

            # Rahul is MEMBER in Engineering
            TeamMember(team_id=eng_team.id, user_id=rahul_member.id, role=TeamRole.MEMBER.value),

            # Swastik is MANAGER in Customer Operations
            TeamMember(team_id=ops_team.id, user_id=swastik_mgr.id, role=TeamRole.MANAGER.value),

            # Ananya is MEMBER in Payments & Fraud (isolated from Eng)
            TeamMember(team_id=fraud_team.id, user_id=ananya_member.id, role=TeamRole.MEMBER.value),
        ]
        db.add_all(memberships)
        db.flush()

        print("--- Seeding Work Items & Transactional Logs ---")
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Urgent production incident (Assigned to Rahul)
        wi1 = WorkItem(
            title="Production Latency Spike in Payment Webhook",
            description="P99 response latency exceeded 2500ms on the main ingress. Requires immediate root-cause trace.",
            status=WorkItemStatus.IN_PROGRESS.value,
            priority=WorkItemPriority.URGENT.value,
            team_id=eng_team.id,
            assignee_id=rahul_member.id,
            created_by=priya_mgr.id,
            due_date=now + datetime.timedelta(days=1),
            version=2
        )
        db.add(wi1)
        db.flush()

        db.add(ActivityLog(
            work_item_id=wi1.id,
            actor_id=priya_mgr.id,
            action="CREATED",
            old_value=None,
            new_value=wi1.title,
            created_at=now - datetime.timedelta(hours=4)
        ))
        db.add(ActivityLog(
            work_item_id=wi1.id,
            actor_id=priya_mgr.id,
            action="ASSIGNED",
            old_value="Unassigned",
            new_value=rahul_member.name,
            created_at=now - datetime.timedelta(hours=3)
        ))
        db.add(ActivityLog(
            work_item_id=wi1.id,
            actor_id=rahul_member.id,
            action="STATUS_CHANGED",
            old_value="OPEN",
            new_value="IN_PROGRESS",
            created_at=now - datetime.timedelta(hours=2)
        ))
        db.add(Comment(
            work_item_id=wi1.id,
            author_id=rahul_member.id,
            content="Isolated the bottleneck to connection pooling timeouts in replica DB. Implementing fix.",
            created_at=now - datetime.timedelta(hours=1)
        ))

        # 2. Unassigned High priority work item (Ready to be claimed)
        wi2 = WorkItem(
            title="Database Read Replica Provisioning",
            description="Provision secondary read replica for the EU reporting cluster ahead of traffic expansion.",
            status=WorkItemStatus.OPEN.value,
            priority=WorkItemPriority.HIGH.value,
            team_id=eng_team.id,
            assignee_id=None,
            created_by=priya_mgr.id,
            due_date=now + datetime.timedelta(days=3),
            version=1
        )
        db.add(wi2)
        db.flush()
        db.add(ActivityLog(
            work_item_id=wi2.id,
            actor_id=priya_mgr.id,
            action="CREATED",
            old_value=None,
            new_value=wi2.title,
            created_at=now - datetime.timedelta(hours=6)
        ))

        # 3. Blocked work item in Ops
        wi3 = WorkItem(
            title="Enterprise Customer KYC Compliance Review",
            description="Client verification pending proof of beneficial ownership documents from legal counsel.",
            status=WorkItemStatus.BLOCKED.value,
            priority=WorkItemPriority.HIGH.value,
            team_id=ops_team.id,
            assignee_id=swastik_mgr.id,
            created_by=swastik_mgr.id,
            due_date=now + datetime.timedelta(days=2),
            version=2
        )
        db.add(wi3)
        db.flush()
        db.add(ActivityLog(
            work_item_id=wi3.id,
            actor_id=swastik_mgr.id,
            action="CREATED",
            old_value=None,
            new_value=wi3.title,
            created_at=now - datetime.timedelta(hours=8)
        ))
        db.add(ActivityLog(
            work_item_id=wi3.id,
            actor_id=swastik_mgr.id,
            action="STATUS_CHANGED",
            old_value="OPEN",
            new_value="BLOCKED",
            created_at=now - datetime.timedelta(hours=5)
        ))
        db.add(Comment(
            work_item_id=wi3.id,
            author_id=swastik_mgr.id,
            content="Waiting for corporate registrar certificates from EU notary.",
            created_at=now - datetime.timedelta(hours=4)
        ))

        # 4. Payments & Fraud work item (for team isolation testing)
        wi4 = WorkItem(
            title="Card Chargeback Discrepancy Investigation",
            description="Flagged cluster of dispute notices from card scheme on merchant settlement batch 8941.",
            status=WorkItemStatus.IN_PROGRESS.value,
            priority=WorkItemPriority.URGENT.value,
            team_id=fraud_team.id,
            assignee_id=ananya_member.id,
            created_by=ananya_member.id,
            due_date=now + datetime.timedelta(days=1),
            version=1
        )
        db.add(wi4)
        db.flush()
        db.add(ActivityLog(
            work_item_id=wi4.id,
            actor_id=ananya_member.id,
            action="CREATED",
            old_value=None,
            new_value=wi4.title,
            created_at=now - datetime.timedelta(hours=10)
        ))

        # 5. Resolved operational task
        wi5 = WorkItem(
            title="Quarterly Access Audit for Cloud Console",
            description="Revoked dormant developer tokens and rotated production IAM roles.",
            status=WorkItemStatus.RESOLVED.value,
            priority=WorkItemPriority.MEDIUM.value,
            team_id=eng_team.id,
            assignee_id=admin_user.id,
            created_by=admin_user.id,
            due_date=now - datetime.timedelta(days=1),
            version=2
        )
        db.add(wi5)
        db.flush()
        db.add(ActivityLog(
            work_item_id=wi5.id,
            actor_id=admin_user.id,
            action="CREATED",
            old_value=None,
            new_value=wi5.title,
            created_at=now - datetime.timedelta(days=3)
        ))
        db.add(ActivityLog(
            work_item_id=wi5.id,
            actor_id=admin_user.id,
            action="STATUS_CHANGED",
            old_value="OPEN",
            new_value="RESOLVED",
            created_at=now - datetime.timedelta(days=1)
        ))

        db.commit()
        print("--- Database seeding completed successfully! ---")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
