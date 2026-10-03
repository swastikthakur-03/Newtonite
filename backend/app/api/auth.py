from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    TeamMembershipInfo,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Constant dummy bcrypt hash for equal-time verification when user does not exist
DUMMY_BCRYPT_HASH = "$2b$12$K9CohnGYo1IOFP87TGENrus3O0mrA1PlC1ViGEoWe8TPTaU/V0yjm"

def build_user_response(user: User) -> UserResponse:
    memberships = [
        TeamMembershipInfo(
            team_id=m.team_id,
            team_name=m.team.name if m.team else "",
            role=m.role
        )
        for m in (user.team_memberships or [])
    ]
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        is_admin=bool(user.is_admin),
        created_at=user.created_at,
        memberships=memberships
    )

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(reg_data: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user account with email/password. New users start with no team access."""
    if not settings.ALLOW_SELF_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "REGISTRATION_DISABLED", "message": "Self-registration is currently disabled."}
        )

    clean_email = reg_data.email.strip().lower()
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "An account with this email address already exists."}
        )

    try:
        new_user = User(
            name=reg_data.name.strip(),
            email=clean_email,
            password_hash=hash_password(reg_data.password),
            is_admin=False,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "An account with this email address already exists."}
        )

    access_token = create_access_token(subject=new_user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=build_user_response(new_user)
    )

@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates user with email and password and returns JWT token."""
    clean_email = login_data.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user:
        # Spend equal bcrypt verification time to defend against user enumeration timing attacks
        verify_password(login_data.password, DUMMY_BCRYPT_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}
        )

    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=build_user_response(user)
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user profile, admin status, and team memberships."""
    return build_user_response(current_user)
