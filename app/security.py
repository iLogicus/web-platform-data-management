"""Password hashing, JWT tokens and RBAC dependencies."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_EXPIRE_MINUTES
from .database import get_db
from .models import RolePermission, User
from .permissions import PERMISSIONS

_PBKDF2_ITERATIONS = 120_000
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User | None:
    """Returns the logged-in user, or None for anonymous / invalid tokens (public endpoints)."""
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    if not user or not user.is_active:
        return None
    return user


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return user


def get_role_permissions(db: Session, role: str) -> set[str]:
    if role == "super_admin":
        return set(PERMISSIONS)
    return set(db.scalars(select(RolePermission.permission).where(RolePermission.role == role)))


def require_permissions(*required: str):
    """Dependency factory: the user must hold ALL listed permissions."""

    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not set(required) <= get_role_permissions(db, user.role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return user

    return dependency


def require_any_permission(*required: str):
    """Dependency factory: the user must hold AT LEAST ONE of the listed permissions."""

    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not set(required) & get_role_permissions(db, user.role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return user

    return dependency
