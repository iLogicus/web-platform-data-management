"""Super Admin: user accounts & roles, permission matrix, system logs, global settings."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, RolePermission, User
from ..permissions import PERMISSIONS, ROLES
from ..schemas import AdminUserCreateIn, AdminUserUpdateIn, RolePermissionsIn, SettingsIn
from ..security import get_role_permissions, hash_password, require_permissions
from ..serializers import iso, user_private
from ..utils import DEFAULT_SETTINGS, audit, escape_like, get_settings, paginate, save_settings

router = APIRouter(prefix="/api/admin", tags=["admin: system"])


# ---------------------------------------------------------------- users


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    role: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("users.manage")),
):
    stmt = select(User).order_by(User.created_at.desc(), User.id.desc())
    if q:
        pattern = f"%{escape_like(q)}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                User.full_name.ilike(pattern, escape="\\"),
            )
        )
    if role:
        stmt = stmt.where(User.role == role)
    users, meta = paginate(db, stmt, page, size)
    return {"items": [user_private(u) for u in users], **meta}


@router.post("/users", status_code=201)
def create_user(
    body: AdminUserCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permissions("users.manage")),
):
    clash = db.scalar(
        select(User.id).where(
            or_(func.lower(User.username) == body.username.lower(), func.lower(User.email) == body.email.lower())
        )
    )
    if clash:
        raise HTTPException(409, "Username or email is already taken")
    user = User(
        username=body.username,
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.flush()
    audit(db, admin, "user.create", "user", user.id, {"username": user.username, "role": user.role}, request)
    db.commit()
    return user_private(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: AdminUserUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permissions("users.manage")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (
        (body.role is not None and body.role != admin.role) or body.is_active is False
    ):
        raise HTTPException(400, "You cannot change your own role or deactivate yourself")
    changes = body.model_dump(exclude_none=True, exclude={"password"})
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.password:
        user.password_hash = hash_password(body.password)
        changes["password"] = "reset"
    audit(db, admin, "user.update", "user", user.id, {"username": user.username, **changes}, request)
    db.commit()
    return user_private(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permissions("users.manage")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    audit(db, admin, "user.delete", "user", user.id, {"username": user.username}, request)
    db.delete(user)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- permissions


@router.get("/permissions")
def get_permission_matrix(db: Session = Depends(get_db), _user: User = Depends(require_permissions("users.manage"))):
    return {
        "permissions": PERMISSIONS,
        "roles": ROLES,
        "matrix": {role: sorted(get_role_permissions(db, role)) for role in ROLES},
    }


@router.put("/permissions/{role}")
def set_role_permissions(
    role: str,
    body: RolePermissionsIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permissions("permissions.manage")),
):
    if role not in ROLES:
        raise HTTPException(404, "Unknown role")
    if role == "super_admin":
        raise HTTPException(400, "Super Admin always has every permission")
    unknown = set(body.permissions) - set(PERMISSIONS)
    if unknown:
        raise HTTPException(422, f"Unknown permissions: {', '.join(sorted(unknown))}")
    db.execute(delete(RolePermission).where(RolePermission.role == role))
    for perm in sorted(set(body.permissions)):
        db.add(RolePermission(role=role, permission=perm))
    audit(db, admin, "permissions.update", "role", None, {"role": role, "permissions": sorted(set(body.permissions))}, request)
    db.commit()
    return {"role": role, "permissions": sorted(get_role_permissions(db, role))}


# ---------------------------------------------------------------- system logs


@router.get("/logs")
def list_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, max_length=64),
    actor: str | None = Query(None, max_length=32),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("logs.view")),
):
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{escape_like(action)}%", escape="\\"))
    if actor:
        stmt = stmt.where(AuditLog.actor_username == actor)
    logs, meta = paginate(db, stmt, page, size)
    items = [
        {
            "id": log.id,
            "actor": log.actor_username or None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "timestamp": iso(log.timestamp),
        }
        for log in logs
    ]
    return {"items": items, **meta}


# ---------------------------------------------------------------- global settings


@router.get("/settings")
def admin_get_settings(db: Session = Depends(get_db), _user: User = Depends(require_permissions("settings.manage"))):
    values = get_settings(db)
    return {key: values[key] for key in DEFAULT_SETTINGS}


@router.put("/settings")
def admin_update_settings(
    body: SettingsIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permissions("settings.manage")),
):
    updates = body.model_dump(exclude_none=True)
    save_settings(db, updates)
    audit(db, admin, "settings.update", "settings", None, updates, request)
    db.commit()
    values = get_settings(db)
    return {key: values[key] for key in DEFAULT_SETTINGS}
