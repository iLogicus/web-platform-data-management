"""FastAPI entry point: `uvicorn app.main:app --reload`."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import STATIC_DIR
from .database import Base, SessionLocal, engine
from .models import RolePermission
from .permissions import DEFAULT_ROLE_PERMISSIONS
from .routers import admin_content, admin_moderation, admin_seo, admin_system, auth, engagement, public


def ensure_defaults(db: Session) -> None:
    """Install the default permission matrix the first time the database is used."""
    if db.scalar(select(RolePermission).limit(1)) is None:
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            if role == "super_admin":
                continue  # implicit: always every permission
            for perm in perms:
                db.add(RolePermission(role=role, permission=perm))
        db.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_defaults(db)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Lumen Magazine API",
    description="News & Digital Magazine Portal — CRUD, authentication, RBAC, document store and search/click logging.",
    version="1.0.0",
    lifespan=lifespan,
)

for module in (auth, public, engagement, admin_content, admin_moderation, admin_seo, admin_system):
    app.include_router(module.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
