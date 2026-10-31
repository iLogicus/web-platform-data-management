"""Request bodies (validated with Pydantic)."""
from typing import Literal

from pydantic import BaseModel, Field

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ---- auth / profile
class RegisterIn(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field("", max_length=120)


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=255, description="Username or email")
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=255, pattern=EMAIL_PATTERN)
    bio: str | None = Field(None, max_length=1000)
    avatar_url: str | None = Field(None, max_length=500)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ---- engagement
class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class RatingIn(BaseModel):
    score: int = Field(ge=1, le=5)


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SearchClickIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    doc_id: int
    position: int | None = Field(None, ge=1)


# ---- content management
class DocumentIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    summary: str = Field("", max_length=1000)
    content: str = Field(min_length=1)
    category_id: int | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["draft", "published"] = "draft"
    image_url: str = Field("", max_length=500)
    image_alt: str = Field("", max_length=300)


class StatusIn(BaseModel):
    status: Literal["draft", "published"]


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field("", max_length=1000)


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


# ---- moderation
class CommentStatusIn(BaseModel):
    status: Literal["visible", "pending", "hidden", "spam"]


class ReportHandleIn(BaseModel):
    status: Literal["resolved", "dismissed"]
    action: Literal["none", "hide_comment", "delete_comment", "mute_user"] = "none"
    note: str = Field("", max_length=500)


class SpamSettingsIn(BaseModel):
    banned_words: list[str] = Field(default_factory=list, max_length=500)
    max_comments_per_minute: int = Field(ge=0, le=100)
    comments_require_approval: bool


class MuteIn(BaseModel):
    muted: bool


# ---- SEO
class SeoUpdateIn(BaseModel):
    seo_title: str = Field("", max_length=300)
    seo_description: str = Field("", max_length=500)
    seo_keywords: str = Field("", max_length=500)
    image_alt: str = Field("", max_length=300)


# ---- super admin
Role = Literal["super_admin", "content_manager", "moderator", "seo_specialist", "user"]


class AdminUserCreateIn(RegisterIn):
    role: Role = "user"


class AdminUserUpdateIn(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    full_name: str | None = Field(None, max_length=120)
    password: str | None = Field(None, min_length=6, max_length=128)


class RolePermissionsIn(BaseModel):
    permissions: list[str]


class SettingsIn(BaseModel):
    site_name: str | None = Field(None, min_length=1, max_length=100)
    site_tagline: str | None = Field(None, max_length=300)
    items_per_page: int | None = Field(None, ge=3, le=50)
    allow_registration: bool | None = None
    comments_enabled: bool | None = None
    announcement: str | None = Field(None, max_length=500)
