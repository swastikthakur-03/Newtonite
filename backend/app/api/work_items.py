import math
import re
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, Query, HTTPException, status as http_status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, case
from app.core.database import get_db
from app.models.user import User
from app.models.work_item import WorkItem, WorkItemStatus, WorkItemPriority
from app.models.comment import Comment
from app.models.activity import ActivityLog
from app.schemas.work_item import (
    WorkItemCreate,
    WorkItemUpdate,
    WorkItemClaim,
    WorkItemAssign,
    WorkItemResponse,
    WorkItemListResponse,
    DashboardStatsResponse,
)
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.activity import ActivityLogResponse
from app.api.deps import (
    get_current_user,
    get_work_item_and_verify_access,
    verify_team_access,
    is_global_admin,
)
from app.services.work_item_service import (
    create_work_item,
    update_work_item,
    claim_work_item,
    assign_work_item,
)
from app.services.activity_service import log_activity

router = APIRouter(tags=["Work Items"])

ALLOWED_SORT_FIELDS = {"updated_at", "created_at", "status", "due_date", "title", "priority"}

def escape_like_string(value: str) -> str:
    """Escapes SQL LIKE wildcard characters (%, _, \\)."""
    return re.sub(r"([%_\\])", r"\\\1", value)

def build_work_item_response(item: WorkItem) -> WorkItemResponse:
    return WorkItemResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        status=item.status,
        priority=item.priority,
        team_id=item.team_id,
        team_name=item.team.name if item.team else "",
        assignee_id=item.assignee_id,
        assignee_name=item.assignee.name if item.assignee else None,
        created_by=item.created_by,
        creator_name=item.creator.name if item.creator else "",
        due_date=item.due_date,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns dashboard overview answering: 'What needs my attention?'
    Calculates operational metrics across teams accessible to the current user.
    """
    user_team_ids = [m.team_id for m in current_user.team_memberships]
    base_query = db.query(WorkItem)
    if not is_global_admin(current_user):
        base_query = base_query.filter(WorkItem.team_id.in_(user_team_ids))

    open_count = base_query.filter(WorkItem.status == WorkItemStatus.OPEN.value).count()
    in_progress_count = base_query.filter(WorkItem.status == WorkItemStatus.IN_PROGRESS.value).count()
    urgent_count = base_query.filter(
        WorkItem.priority == WorkItemPriority.URGENT.value,
        WorkItem.status.in_([WorkItemStatus.OPEN.value, WorkItemStatus.IN_PROGRESS.value, WorkItemStatus.BLOCKED.value])
    ).count()
    blocked_count = base_query.filter(WorkItem.status == WorkItemStatus.BLOCKED.value).count()
    
    my_assigned_query = base_query.filter(
        WorkItem.assignee_id == current_user.id,
        WorkItem.status.in_([WorkItemStatus.OPEN.value, WorkItemStatus.IN_PROGRESS.value, WorkItemStatus.BLOCKED.value])
    )
    my_assigned_count = my_assigned_query.count()

    # Retrieve lists for immediate operational action
    my_assigned_items = (
        my_assigned_query
        .options(joinedload(WorkItem.team), joinedload(WorkItem.assignee), joinedload(WorkItem.creator))
        .order_by(
            desc(WorkItem.priority == WorkItemPriority.URGENT.value),
            desc(WorkItem.updated_at)
        )
        .limit(5)
        .all()
    )

    urgent_items = (
        base_query.filter(
            WorkItem.priority == WorkItemPriority.URGENT.value,
            WorkItem.status.in_([WorkItemStatus.OPEN.value, WorkItemStatus.IN_PROGRESS.value, WorkItemStatus.BLOCKED.value])
        )
        .options(joinedload(WorkItem.team), joinedload(WorkItem.assignee), joinedload(WorkItem.creator))
        .order_by(desc(WorkItem.updated_at))
        .limit(5)
        .all()
    )

    recent_items = (
        base_query
        .options(joinedload(WorkItem.team), joinedload(WorkItem.assignee), joinedload(WorkItem.creator))
        .order_by(desc(WorkItem.updated_at))
        .limit(5)
        .all()
    )

    return DashboardStatsResponse(
        open_count=open_count,
        in_progress_count=in_progress_count,
        urgent_count=urgent_count,
        blocked_count=blocked_count,
        my_assigned_count=my_assigned_count,
        my_assigned_items=[build_work_item_response(i) for i in my_assigned_items],
        urgent_items=[build_work_item_response(i) for i in urgent_items],
        recent_items=[build_work_item_response(i) for i in recent_items],
    )

@router.get("/work-items", response_model=WorkItemListResponse)
def list_work_items(
    search: Optional[str] = Query(None, description="Search term for title or description"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    team_id: Optional[int] = Query(None, description="Filter by team"),
    assignee_id: Optional[int] = Query(None, description="Filter by assignee"),
    unassigned_only: Optional[bool] = Query(False, description="Filter only unassigned items"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("updated_at", description="Field to sort by: updated_at, created_at, status, due_date, title, priority"),
    sort_order: str = Query("desc", description="Sort direction: asc or desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists work items with server-side filtering, sorting, and pagination.
    Strictly enforces resource boundaries: non-admins cannot query items outside their teams.
    """
    # Validation
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_SORT_FIELD", "message": f"sort_by must be one of {sorted(list(ALLOWED_SORT_FIELDS))}"}
        )
    if sort_order.lower() not in {"asc", "desc"}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_SORT_ORDER", "message": "sort_order must be 'asc' or 'desc'"}
        )
    if status is not None:
        try:
            WorkItemStatus(status.upper())
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_STATUS_FILTER", "message": f"Invalid status: {status}"}
            )
    if priority is not None:
        try:
            WorkItemPriority(priority.upper())
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_PRIORITY_FILTER", "message": f"Invalid priority: {priority}"}
            )

    user_team_ids = [m.team_id for m in current_user.team_memberships]

    query = db.query(WorkItem).options(
        joinedload(WorkItem.team),
        joinedload(WorkItem.assignee),
        joinedload(WorkItem.creator)
    )

    # Multi-tenant / team boundary enforcement
    if not is_global_admin(current_user):
        if team_id is not None:
            if team_id not in user_team_ids:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"code": "TEAM_ACCESS_DENIED", "message": "You cannot access work items for this team."}
                )
            query = query.filter(WorkItem.team_id == team_id)
        else:
            query = query.filter(WorkItem.team_id.in_(user_team_ids))
    else:
        if team_id is not None:
            query = query.filter(WorkItem.team_id == team_id)

    # Filters
    if status:
        query = query.filter(WorkItem.status == status.upper())
    if priority:
        query = query.filter(WorkItem.priority == priority.upper())
    if unassigned_only:
        query = query.filter(WorkItem.assignee_id.is_(None))
    elif assignee_id is not None:
        query = query.filter(WorkItem.assignee_id == assignee_id)
    if search:
        escaped_search = escape_like_string(search)
        search_pattern = f"%{escaped_search}%"
        query = query.filter(
            or_(
                WorkItem.title.ilike(search_pattern, escape="\\"),
                WorkItem.description.ilike(search_pattern, escape="\\")
            )
        )

    # Sorting with stable tiebreaker (id)
    is_asc = sort_order.lower() == "asc"
    if sort_by == "priority":
        # Severity ordering: URGENT(4) > HIGH(3) > MEDIUM(2) > LOW(1)
        priority_weight = case(
            (WorkItem.priority == WorkItemPriority.URGENT.value, 4),
            (WorkItem.priority == WorkItemPriority.HIGH.value, 3),
            (WorkItem.priority == WorkItemPriority.MEDIUM.value, 2),
            (WorkItem.priority == WorkItemPriority.LOW.value, 1),
            else_=0
        )
        if is_asc:
            query = query.order_by(asc(priority_weight), asc(WorkItem.id))
        else:
            query = query.order_by(desc(priority_weight), desc(WorkItem.id))
    else:
        sort_col = getattr(WorkItem, sort_by, WorkItem.updated_at)
        if is_asc:
            query = query.order_by(asc(sort_col), asc(WorkItem.id))
        else:
            query = query.order_by(desc(sort_col), desc(WorkItem.id))

    total = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return WorkItemListResponse(
        items=[build_work_item_response(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.post("/work-items", response_model=WorkItemResponse, status_code=http_status.HTTP_201_CREATED)
def create_new_work_item(
    item_in: WorkItemCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new work item.
    Supports idempotent retries via the `Idempotency-Key` header.
    Automatically generates audit activity record in the same transaction.
    """
    item, _ = create_work_item(db, item_in, current_user, idempotency_key=idempotency_key)
    return build_work_item_response(item)

@router.get("/work-items/{work_item_id}", response_model=WorkItemResponse)
def get_work_item(
    work_item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches a work item and verifies the caller has team-level authorization."""
    item = get_work_item_and_verify_access(work_item_id, current_user, db)
    return build_work_item_response(item)

@router.patch("/work-items/{work_item_id}", response_model=WorkItemResponse)
def update_work_item_endpoint(
    work_item_id: int,
    update_in: WorkItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates a work item using optimistic concurrency control.
    Requires `version` in payload. Returns 409 Conflict if stale.
    """
    item = get_work_item_and_verify_access(work_item_id, current_user, db)
    updated = update_work_item(db, item, update_in, current_user)
    return build_work_item_response(updated)

@router.post("/work-items/{work_item_id}/claim", response_model=WorkItemResponse)
def claim_work_item_endpoint(
    work_item_id: int,
    claim_in: WorkItemClaim,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atomically claims an unassigned work item.
    Guarantees that race conditions between multiple users result in exactly one claimer.
    """
    item = get_work_item_and_verify_access(work_item_id, current_user, db)
    claimed = claim_work_item(db, item, claim_in, current_user)
    return build_work_item_response(claimed)

@router.post("/work-items/{work_item_id}/assign", response_model=WorkItemResponse)
def assign_work_item_endpoint(
    work_item_id: int,
    assign_in: WorkItemAssign,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assigns or unassigns a work item.
    Only team MANAGER or ADMIN can reassign items.
    """
    item = get_work_item_and_verify_access(work_item_id, current_user, db)
    assigned = assign_work_item(db, item, assign_in, current_user)
    return build_work_item_response(assigned)

@router.get("/work-items/{work_item_id}/comments", response_model=List[CommentResponse])
def get_comments(
    work_item_id: int,
    limit: int = Query(200, ge=1, le=500, description="Max comments to return"),
    offset: int = Query(0, ge=0, description="Offset for comments"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves comments for a work item in chronological order with limit and offset."""
    get_work_item_and_verify_access(work_item_id, current_user, db)
    comments = (
        db.query(Comment)
        .options(joinedload(Comment.author))
        .filter(Comment.work_item_id == work_item_id)
        .order_by(asc(Comment.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        CommentResponse(
            id=c.id,
            work_item_id=c.work_item_id,
            author_id=c.author_id,
            author_name=c.author.name if c.author else "",
            content=c.content,
            created_at=c.created_at,
            updated_at=c.updated_at
        )
        for c in comments
    ]

@router.post("/work-items/{work_item_id}/comments", response_model=CommentResponse, status_code=http_status.HTTP_201_CREATED)
def add_comment(
    work_item_id: int,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Adds a new comment to a work item. Comment and audit row commit in ONE transaction."""
    get_work_item_and_verify_access(work_item_id, current_user, db)
    
    comment = Comment(
        work_item_id=work_item_id,
        author_id=current_user.id,
        content=comment_in.content
    )
    db.add(comment)

    # Log activity record in the same transaction
    log_activity(
        db,
        work_item_id=work_item_id,
        actor_id=current_user.id,
        action="COMMENTED",
        old_value=None,
        new_value=comment_in.content[:50] + ("..." if len(comment_in.content) > 50 else "")
    )
    # Commit both comment and activity row together
    db.commit()
    db.refresh(comment)

    return CommentResponse(
        id=comment.id,
        work_item_id=comment.work_item_id,
        author_id=comment.author_id,
        author_name=current_user.name,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at
    )

@router.get("/work-items/{work_item_id}/activity", response_model=List[ActivityLogResponse])
def get_activity_log(
    work_item_id: int,
    limit: int = Query(100, ge=1, le=500, description="Max activity logs to return"),
    offset: int = Query(0, ge=0, description="Offset for activity logs"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves full audit history for the work item ordered newest first with limit and offset."""
    get_work_item_and_verify_access(work_item_id, current_user, db)
    logs = (
        db.query(ActivityLog)
        .options(joinedload(ActivityLog.actor))
        .filter(ActivityLog.work_item_id == work_item_id)
        .order_by(desc(ActivityLog.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        ActivityLogResponse(
            id=log.id,
            work_item_id=log.work_item_id,
            actor_id=log.actor_id,
            actor_name=log.actor.name if log.actor else "",
            action=log.action,
            old_value=log.old_value,
            new_value=log.new_value,
            created_at=log.created_at
        )
        for log in logs
    ]
