from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.team import Team, TeamMember, TeamRole
from app.models.user import User
from app.schemas.team import (
    TeamResponse,
    TeamDetailResponse,
    TeamMemberResponse,
    TeamCreateRequest,
    AddTeamMemberRequest,
)
from app.api.deps import (
    get_current_user,
    verify_team_access,
    is_global_admin,
    require_global_admin,
)

router = APIRouter(prefix="/teams", tags=["Teams"])

@router.get("", response_model=List[TeamResponse])
def get_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns teams accessible to the current user.
    Admins see all teams; members see teams they belong to.
    Computes member_count via a single grouped query to eliminate N+1 queries.
    """
    if is_global_admin(current_user):
        teams = db.query(Team).order_by(Team.name.asc()).all()
    else:
        team_ids = [m.team_id for m in current_user.team_memberships]
        teams = db.query(Team).filter(Team.id.in_(team_ids)).order_by(Team.name.asc()).all()

    # Single grouped count query to prevent N+1
    counts_map = dict(
        db.query(TeamMember.team_id, func.count(TeamMember.id))
        .group_by(TeamMember.team_id)
        .all()
    )

    return [
        TeamResponse(
            id=t.id,
            name=t.name,
            created_at=t.created_at,
            member_count=counts_map.get(t.id, 0)
        )
        for t in teams
    ]

@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    team_in: TeamCreateRequest,
    current_user: User = Depends(require_global_admin),
    db: Session = Depends(get_db)
):
    """Creates a new team. Only system administrators can create teams."""
    clean_name = team_in.name.strip()
    existing = db.query(Team).filter(func.lower(Team.name) == clean_name.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_TEAM_NAME", "message": f"Team with name '{clean_name}' already exists."}
        )

    try:
        new_team = Team(name=clean_name)
        db.add(new_team)
        db.commit()
        db.refresh(new_team)
        return TeamResponse(
            id=new_team.id,
            name=new_team.name,
            created_at=new_team.created_at,
            member_count=0
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_TEAM_NAME", "message": f"Team with name '{clean_name}' already exists."}
        )

@router.get("/{team_id}", response_model=TeamDetailResponse)
def get_team_detail(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns details and member roster of a team. Enforces team access."""
    verify_team_access(current_user, team_id)
    team = (
        db.query(Team)
        .options(joinedload(Team.members).joinedload(TeamMember.user))
        .filter(Team.id == team_id)
        .first()
    )
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TEAM_NOT_FOUND", "message": "Team not found."}
        )
    
    members_resp = [
        TeamMemberResponse(
            id=m.id,
            user_id=m.user_id,
            team_id=m.team_id,
            user_name=m.user.name,
            user_email=m.user.email,
            role=m.role,
            created_at=m.created_at
        )
        for m in team.members
    ]
    return TeamDetailResponse(
        id=team.id,
        name=team.name,
        created_at=team.created_at,
        members=members_resp
    )

@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
def get_team_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the member list for a team (useful for assignee dropdowns)."""
    verify_team_access(current_user, team_id)
    members = (
        db.query(TeamMember)
        .options(joinedload(TeamMember.user))
        .filter(TeamMember.team_id == team_id)
        .all()
    )
    return [
        TeamMemberResponse(
            id=m.id,
            user_id=m.user_id,
            team_id=m.team_id,
            user_name=m.user.name,
            user_email=m.user.email,
            role=m.role,
            created_at=m.created_at
        )
        for m in members
    ]

@router.post("/{team_id}/members", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
def add_team_member(
    team_id: int,
    req: AddTeamMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Adds a user to a team by user_id or email. Only team MANAGER or system ADMIN can perform this action."""
    verify_team_access(current_user, team_id, required_roles=[TeamRole.MANAGER.value])
    
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TEAM_NOT_FOUND", "message": "Team not found."}
        )

    # Locate target user by ID or by Email
    target_user = None
    if req.user_id is not None:
        target_user = db.query(User).filter(User.id == req.user_id).first()
    elif req.email:
        clean_email = str(req.email).strip().lower()
        target_user = db.query(User).filter(User.email == clean_email).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Target user could not be found."}
        )
    
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == target_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_MEMBER", "message": f"{target_user.name} is already a member of this team."}
        )
    
    membership = TeamMember(
        team_id=team_id,
        user_id=target_user.id,
        role=req.role.value
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    
    return TeamMemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        team_id=membership.team_id,
        user_name=target_user.name,
        user_email=target_user.email,
        role=membership.role,
        created_at=membership.created_at
    )
