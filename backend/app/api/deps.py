from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.team import TeamMember, TeamRole
from app.models.work_item import WorkItem

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    """Authenticates the user from the Bearer JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Authentication required. Please log in."}
        )
    
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired authentication token."}
        )
    
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Malformed token subject."}
        )
    
    user = (
        db.query(User)
        .options(joinedload(User.team_memberships).joinedload(TeamMember.team))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User associated with this token does not exist."}
        )
    return user

def is_global_admin(user: User) -> bool:
    """Checks if user is a system administrator. The ONLY source of global admin is users.is_admin."""
    return bool(user.is_admin)

def require_global_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforces that the current authenticated user has system administrator privileges."""
    if not is_global_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_PERMISSIONS", "message": "System administrator privileges required."}
        )
    return current_user

def get_user_role_in_team(user: User, team_id: int) -> Optional[str]:
    """Returns the effective role of the user within the specific team, or virtual 'ADMIN' if system admin."""
    if is_global_admin(user):
        return "ADMIN"
        
    for membership in user.team_memberships:
        if membership.team_id == team_id:
            return membership.role
    return None

def verify_team_access(user: User, team_id: int, required_roles: Optional[list] = None) -> str:
    """
    Enforces resource-level team authorization.
    Verifies that the user belongs to the specified team and possesses any of the required roles.
    Raises 403 Forbidden if not authorized.
    """
    if is_global_admin(user):
        return "ADMIN"

    role = get_user_role_in_team(user, team_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TEAM_ACCESS_DENIED",
                "message": f"You do not have access to resources for team {team_id}."
            }
        )
    
    if required_roles and role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INSUFFICIENT_PERMISSIONS",
                "message": f"Action requires one of [{', '.join(required_roles)}] role, but you are {role}."
            }
        )
    return role

def get_work_item_and_verify_access(
    work_item_id: int,
    user: User,
    db: Session,
    required_roles: Optional[list] = None
) -> WorkItem:
    """
    Fetches a work item and verifies the user has team-level access to it.
    Prevents cross-team unauthorized access.
    """
    work_item = (
        db.query(WorkItem)
        .options(
            joinedload(WorkItem.team),
            joinedload(WorkItem.assignee),
            joinedload(WorkItem.creator)
        )
        .filter(WorkItem.id == work_item_id)
        .first()
    )
    if not work_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORK_ITEM_NOT_FOUND", "message": f"Work item {work_item_id} not found."}
        )
    
    # Resource-level access check
    verify_team_access(user, work_item.team_id, required_roles=required_roles)
    return work_item
