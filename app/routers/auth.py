"""Registration, login and profile management."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, utcnow
from ..schemas import LoginIn, PasswordChangeIn, ProfileUpdateIn, RegisterIn
from ..security import (
    create_access_token,
    get_current_user,
    get_role_permissions,
    hash_password,
    verify_password,
)
from ..serializers import user_private
from ..utils import audit, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session_payload(db: Session, user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user_private(user),
        "permissions": sorted(get_role_permissions(db, user.role)),
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if not get_settings(db)["allow_registration"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is currently closed")
    exists = db.scalar(
        select(User.id).where(
            or_(func.lower(User.username) == body.username.lower(), func.lower(User.email) == body.email.lower())
        )
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or email is already taken")
    user = User(
        username=body.username,
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role="user",
        last_login_at=utcnow(),
    )
    db.add(user)
    db.flush()
    audit(db, user, "auth.register", "user", user.id, request=request)
    db.commit()
    return _session_payload(db, user)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ident = body.login.strip().lower()
    user = db.scalar(select(User).where(or_(func.lower(User.username) == ident, User.email == ident)))
    if not user or not verify_password(body.password, user.password_hash):
        audit(db, None, "auth.login_failed", "user", user.id if user else None, {"login": body.login}, request)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username/email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    user.last_login_at = utcnow()
    audit(db, user, "auth.login", "user", user.id, request=request)
    db.commit()
    return _session_payload(db, user)


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"user": user_private(user), "permissions": sorted(get_role_permissions(db, user.role))}


@router.put("/me")
def update_profile(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.email is not None and body.email.lower() != user.email:
        taken = db.scalar(select(User.id).where(User.email == body.email.lower(), User.id != user.id))
        if taken:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already in use")
        user.email = body.email.lower()
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.bio is not None:
        user.bio = body.bio.strip()
    if body.avatar_url is not None:
        url = body.avatar_url.strip()
        if url and not url.startswith(("http://", "https://")):
            raise HTTPException(422, "Avatar URL must start with http:// or https://")
        user.avatar_url = url
    db.commit()
    return {"user": user_private(user)}


@router.put("/me/password")
def change_password(
    body: PasswordChangeIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "auth.password_change", "user", user.id, request=request)
    db.commit()
    return {"ok": True}
