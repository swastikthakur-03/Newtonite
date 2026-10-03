import json
import hashlib
from typing import Optional, Tuple, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError
from app.models.work_item import WorkItem, WorkItemStatus, WorkItemPriority
from app.models.user import User
from app.models.team import Team, TeamMember, TeamRole
from app.models.idempotency import IdempotencyRecord
from app.schemas.work_item import WorkItemCreate, WorkItemUpdate, WorkItemClaim, WorkItemAssign
from app.services.activity_service import log_activity
from app.api.deps import verify_team_access, is_global_admin, get_user_role_in_team

ALLOWED_TRANSITIONS = {
    WorkItemStatus.OPEN.value: {WorkItemStatus.IN_PROGRESS.value, WorkItemStatus.BLOCKED.value, WorkItemStatus.CLOSED.value},
    WorkItemStatus.IN_PROGRESS.value: {WorkItemStatus.OPEN.value, WorkItemStatus.BLOCKED.value, WorkItemStatus.RESOLVED.value},
    WorkItemStatus.BLOCKED.value: {WorkItemStatus.OPEN.value, WorkItemStatus.IN_PROGRESS.value},
    WorkItemStatus.RESOLVED.value: {WorkItemStatus.IN_PROGRESS.value, WorkItemStatus.CLOSED.value},
    WorkItemStatus.CLOSED.value: {WorkItemStatus.OPEN.value},
}

def serialize_work_item(item: WorkItem) -> dict:
    """Helper to convert WorkItem model to dictionary matching WorkItemResponse schema."""
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "priority": item.priority,
        "team_id": item.team_id,
        "team_name": item.team.name if item.team else "",
        "assignee_id": item.assignee_id,
        "assignee_name": item.assignee.name if item.assignee else None,
        "created_by": item.created_by,
        "creator_name": item.creator.name if item.creator else "",
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "version": item.version,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }

def create_work_item(
    db: Session,
    item_in: WorkItemCreate,
    current_user: User,
    idempotency_key: Optional[str] = None
) -> Tuple[WorkItem, bool]:
    """
    Creates a new WorkItem with idempotency protection and transactional audit logging.
    Returns (work_item, is_cached).
    """
    # Compute sha256 request hash
    request_payload_bytes = item_in.model_dump_json().encode("utf-8")
    request_hash = hashlib.sha256(request_payload_bytes).hexdigest()

    # 1. Check idempotency if key provided
    if idempotency_key:
        cached_record = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.user_id == current_user.id,
                IdempotencyRecord.key == idempotency_key
            )
            .first()
        )
        if cached_record:
            if cached_record.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "IDEMPOTENCY_KEY_REUSED",
                        "message": "Idempotency key has already been used with a different request payload."
                    }
                )
            payload = json.loads(cached_record.response_body)
            # Re-check team access on replay
            verify_team_access(current_user, payload["team_id"])
            item = (
                db.query(WorkItem)
                .options(
                    joinedload(WorkItem.team),
                    joinedload(WorkItem.assignee),
                    joinedload(WorkItem.creator)
                )
                .filter(WorkItem.id == payload["id"])
                .first()
            )
            if item:
                return item, True

    # 2. Verify team existence and authorization
    target_team = db.query(Team).filter(Team.id == item_in.team_id).first()
    if not target_team:
        if not is_global_admin(current_user):
            user_team_ids = [m.team_id for m in current_user.team_memberships]
            if item_in.team_id not in user_team_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "TEAM_ACCESS_DENIED", "message": f"You do not have access to resources for team {item_in.team_id}."}
                )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TEAM_NOT_FOUND", "message": f"Team {item_in.team_id} does not exist."}
        )

    verify_team_access(current_user, item_in.team_id)

    # 3. If assigning directly on creation, check permissions & membership
    if item_in.assignee_id:
        assignee_role = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == item_in.team_id,
                TeamMember.user_id == item_in.assignee_id
            )
            .first()
        )
        if not assignee_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_ASSIGNEE", "message": "Assignee must be a member of the selected team."}
            )
        
        # If assigning to someone else, user must be MANAGER or system ADMIN
        if item_in.assignee_id != current_user.id:
            verify_team_access(current_user, item_in.team_id, required_roles=[TeamRole.MANAGER.value])

    # 4. Transactional creation: WorkItem + ActivityLog + IdempotencyRecord
    try:
        new_item = WorkItem(
            title=item_in.title,
            description=item_in.description,
            status=WorkItemStatus.OPEN.value,
            priority=item_in.priority.value,
            team_id=item_in.team_id,
            assignee_id=item_in.assignee_id,
            created_by=current_user.id,
            due_date=item_in.due_date,
            version=1
        )
        db.add(new_item)
        db.flush()

        # Audit log: CREATED
        log_activity(
            db,
            work_item_id=new_item.id,
            actor_id=current_user.id,
            action="CREATED",
            old_value=None,
            new_value=new_item.title
        )

        if new_item.assignee_id:
            assignee = db.query(User).filter(User.id == new_item.assignee_id).first()
            log_activity(
                db,
                work_item_id=new_item.id,
                actor_id=current_user.id,
                action="ASSIGNED",
                old_value="Unassigned",
                new_value=assignee.name if assignee else str(new_item.assignee_id)
            )

        # Hydrate relationships
        db.flush()
        item_with_rels = (
            db.query(WorkItem)
            .options(
                joinedload(WorkItem.team),
                joinedload(WorkItem.assignee),
                joinedload(WorkItem.creator)
            )
            .filter(WorkItem.id == new_item.id)
            .first()
        )

        if idempotency_key:
            serialized_payload = json.dumps(serialize_work_item(item_with_rels))
            idemp_rec = IdempotencyRecord(
                key=idempotency_key,
                user_id=current_user.id,
                request_path="/api/work-items",
                request_hash=request_hash,
                status_code=status.HTTP_201_CREATED,
                response_body=serialized_payload
            )
            db.add(idemp_rec)

        db.commit()
        return item_with_rels, False

    except IntegrityError:
        db.rollback()
        # Handle concurrent same-key idempotency race
        if idempotency_key:
            winner_rec = (
                db.query(IdempotencyRecord)
                .filter(
                    IdempotencyRecord.user_id == current_user.id,
                    IdempotencyRecord.key == idempotency_key
                )
                .first()
            )
            if winner_rec:
                if winner_rec.request_hash != request_hash:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "IDEMPOTENCY_KEY_REUSED",
                            "message": "Idempotency key has already been used with a different request payload."
                        }
                    )
                winner_payload = json.loads(winner_rec.response_body)
                verify_team_access(current_user, winner_payload["team_id"])
                item = (
                    db.query(WorkItem)
                    .options(
                        joinedload(WorkItem.team),
                        joinedload(WorkItem.assignee),
                        joinedload(WorkItem.creator)
                    )
                    .filter(WorkItem.id == winner_payload["id"])
                    .first()
                )
                if item:
                    return item, True
        raise

def update_work_item(
    db: Session,
    work_item: WorkItem,
    update_in: WorkItemUpdate,
    current_user: User
) -> WorkItem:
    """
    Updates a WorkItem enforcing state transitions, ownership permissions, and optimistic concurrency.
    """
    verify_team_access(current_user, work_item.team_id)

    user_role = get_user_role_in_team(current_user, work_item.team_id)
    is_mgr_or_admin = (user_role in [TeamRole.MANAGER.value, "ADMIN"] or is_global_admin(current_user))
    is_assignee = (work_item.assignee_id == current_user.id)
    is_creator = (work_item.created_by == current_user.id)

    # 1. Priority change: manager/admin only
    if update_in.priority is not None and update_in.priority.value != work_item.priority:
        if not is_mgr_or_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "INSUFFICIENT_PERMISSIONS", "message": "Only team managers or administrators can change priority."}
            )

    # 2. Details update (title, description, due_date): assignee, creator, or manager/admin only
    details_modified = (
        ("title" in update_in.model_fields_set and update_in.title is not None and update_in.title != work_item.title) or
        ("description" in update_in.model_fields_set and update_in.description != work_item.description) or
        ("due_date" in update_in.model_fields_set and update_in.due_date != work_item.due_date)
    )
    if details_modified and not (is_mgr_or_admin or is_assignee or is_creator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_PERMISSIONS", "message": "Only the assignee, creator, or a team manager can edit work item details."}
        )

    # 3. Status transitions & ownership
    new_status = work_item.status
    if update_in.status is not None and update_in.status.value != work_item.status:
        target_status = update_in.status.value
        old_status = work_item.status

        # Transition validation
        allowed = ALLOWED_TRANSITIONS.get(old_status, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_TRANSITION",
                    "message": f"Illegal status transition from {old_status} to {target_status}."
                }
            )

        # Closing or reopening: manager or admin only
        if target_status == WorkItemStatus.CLOSED.value or (old_status == WorkItemStatus.CLOSED.value and target_status == WorkItemStatus.OPEN.value):
            if not is_mgr_or_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "INSUFFICIENT_PERMISSIONS", "message": "Only team managers or administrators may close or reopen work items."}
                )

        # Member status changes: only allowed on items assigned to them
        if not is_mgr_or_admin and not is_assignee:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "NOT_ASSIGNEE", "message": "Members may only change the status of work items assigned to them."}
            )

        # IN_PROGRESS requires an assignee
        if target_status == WorkItemStatus.IN_PROGRESS.value and work_item.assignee_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ASSIGNEE_REQUIRED", "message": "Work item must have an assignee before moving to IN_PROGRESS."}
            )

        new_status = target_status

    old_status = work_item.status
    old_priority = work_item.priority
    old_title = work_item.title
    old_description = work_item.description

    # Prepare values using model_fields_set so explicit None clears description/due_date
    new_title = update_in.title if ("title" in update_in.model_fields_set and update_in.title is not None) else work_item.title
    new_description = update_in.description if "description" in update_in.model_fields_set else work_item.description
    new_due_date = update_in.due_date if "due_date" in update_in.model_fields_set else work_item.due_date
    new_priority = update_in.priority.value if update_in.priority is not None else work_item.priority

    item_id = work_item.id

    # Atomic optimistic locking update
    stmt = text("""
        UPDATE work_items
        SET title = :title,
            description = :description,
            status = :status,
            priority = :priority,
            due_date = :due_date,
            version = version + 1,
            updated_at = NOW()
        WHERE id = :id
          AND version = :expected_version
    """)

    result = db.execute(
        stmt,
        {
            "title": new_title,
            "description": new_description,
            "status": new_status,
            "priority": new_priority,
            "due_date": new_due_date,
            "id": item_id,
            "expected_version": update_in.version,
        }
    )

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "VERSION_CONFLICT",
                "message": "This work item was modified by another user. Please refresh before making changes."
            }
        )

    # In the same transaction, record audit events for changes
    if new_status != old_status:
        log_activity(
            db,
            work_item_id=item_id,
            actor_id=current_user.id,
            action="STATUS_CHANGED",
            old_value=old_status,
            new_value=new_status
        )

    if new_priority != old_priority:
        log_activity(
            db,
            work_item_id=item_id,
            actor_id=current_user.id,
            action="PRIORITY_CHANGED",
            old_value=old_priority,
            new_value=new_priority
        )

    if details_modified:
        log_activity(
            db,
            work_item_id=item_id,
            actor_id=current_user.id,
            action="DETAILS_UPDATED",
            old_value="Previous title/description",
            new_value="Updated title/description"
        )

    db.commit()

    updated_item = (
        db.query(WorkItem)
        .options(
            joinedload(WorkItem.team),
            joinedload(WorkItem.assignee),
            joinedload(WorkItem.creator)
        )
        .filter(WorkItem.id == item_id)
        .first()
    )
    return updated_item

def claim_work_item(
    db: Session,
    work_item: WorkItem,
    claim_in: WorkItemClaim,
    current_user: User
) -> WorkItem:
    """
    Safely claims an unassigned work item.
    Guard is a single atomic update:
      UPDATE work_items SET assignee_id = :user_id, version = version + 1
      WHERE id = :id AND assignee_id IS NULL AND status NOT IN ('RESOLVED','CLOSED')
    Version check is optional.
    """
    item_id = work_item.id

    if claim_in.version is not None:
        stmt = text("""
            UPDATE work_items
            SET assignee_id = :user_id,
                version = version + 1,
                updated_at = NOW()
            WHERE id = :id
              AND assignee_id IS NULL
              AND status NOT IN ('RESOLVED', 'CLOSED')
              AND version = :version
        """)
        params = {"user_id": current_user.id, "id": item_id, "version": claim_in.version}
    else:
        stmt = text("""
            UPDATE work_items
            SET assignee_id = :user_id,
                version = version + 1,
                updated_at = NOW()
            WHERE id = :id
              AND assignee_id IS NULL
              AND status NOT IN ('RESOLVED', 'CLOSED')
        """)
        params = {"user_id": current_user.id, "id": item_id}

    result = db.execute(stmt, params)

    if result.rowcount == 0:
        # Re-read with populate_existing so the error diagnosis is exact and fresh
        fresh = (
            db.query(WorkItem)
            .populate_existing()
            .options(joinedload(WorkItem.assignee))
            .filter(WorkItem.id == item_id)
            .first()
        )
        if fresh:
            if fresh.assignee_id is not None:
                assignee_name = fresh.assignee.name if fresh.assignee else "another user"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "ALREADY_ASSIGNED",
                        "message": f"This work item was already claimed by {assignee_name}. Please refresh to see the updated state."
                    }
                )
            if fresh.status in [WorkItemStatus.RESOLVED.value, WorkItemStatus.CLOSED.value]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "ITEM_NOT_CLAIMABLE",
                        "message": f"Cannot claim a work item that is {fresh.status}."
                    }
                )
            if claim_in.version is not None and fresh.version != claim_in.version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "VERSION_CONFLICT",
                        "message": "This work item was modified by another user. Please refresh before claiming."
                    }
                )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CLAIM_CONFLICT",
                "message": "Work item could not be claimed due to a state conflict."
            }
        )

    log_activity(
        db,
        work_item_id=item_id,
        actor_id=current_user.id,
        action="CLAIMED",
        old_value="Unassigned",
        new_value=current_user.name
    )
    db.commit()

    fresh_item = (
        db.query(WorkItem)
        .options(
            joinedload(WorkItem.team),
            joinedload(WorkItem.assignee),
            joinedload(WorkItem.creator)
        )
        .filter(WorkItem.id == item_id)
        .first()
    )
    return fresh_item

def assign_work_item(
    db: Session,
    work_item: WorkItem,
    assign_in: WorkItemAssign,
    current_user: User
) -> WorkItem:
    """
    Assigns or unassigns a work item.
    Enforces MANAGER or system ADMIN role in the item's team.
    Assigning a CLOSED item is rejected.
    Unassigning an IN_PROGRESS item returns it to OPEN within the same transaction.
    """
    verify_team_access(current_user, work_item.team_id, required_roles=[TeamRole.MANAGER.value])

    if work_item.status == WorkItemStatus.CLOSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ITEM_CLOSED", "message": "Cannot assign or unassign a closed work item."}
        )

    old_assignee_name = work_item.assignee.name if work_item.assignee else "Unassigned"
    new_assignee_name = "Unassigned"

    if assign_in.assignee_id is not None:
        target_user = db.query(User).filter(User.id == assign_in.assignee_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "USER_NOT_FOUND", "message": "Target assignee does not exist."}
            )
        target_membership = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == work_item.team_id,
                TeamMember.user_id == assign_in.assignee_id
            )
            .first()
        )
        if not target_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NOT_TEAM_MEMBER", "message": "Assignee must be a member of the work item's team."}
            )
        new_assignee_name = target_user.name

    # Check unassigning IN_PROGRESS item -> transition to OPEN
    revert_to_open = (assign_in.assignee_id is None and work_item.status == WorkItemStatus.IN_PROGRESS.value)
    new_status = WorkItemStatus.OPEN.value if revert_to_open else work_item.status

    item_id = work_item.id

    stmt = text("""
        UPDATE work_items
        SET assignee_id = :assignee_id,
            status = :status,
            version = version + 1,
            updated_at = NOW()
        WHERE id = :id
          AND version = :version
    """)

    result = db.execute(
        stmt,
        {
            "assignee_id": assign_in.assignee_id,
            "status": new_status,
            "id": item_id,
            "version": assign_in.version,
        }
    )

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "VERSION_CONFLICT",
                "message": "This work item was modified by another user. Please refresh before assigning."
            }
        )

    log_activity(
        db,
        work_item_id=item_id,
        actor_id=current_user.id,
        action="ASSIGNED" if assign_in.assignee_id is not None else "UNASSIGNED",
        old_value=old_assignee_name,
        new_value=new_assignee_name
    )

    if revert_to_open:
        log_activity(
            db,
            work_item_id=item_id,
            actor_id=current_user.id,
            action="STATUS_CHANGED",
            old_value=WorkItemStatus.IN_PROGRESS.value,
            new_value=WorkItemStatus.OPEN.value
        )

    db.commit()

    fresh_item = (
        db.query(WorkItem)
        .options(
            joinedload(WorkItem.team),
            joinedload(WorkItem.assignee),
            joinedload(WorkItem.creator)
        )
        .filter(WorkItem.id == item_id)
        .first()
    )
    return fresh_item
