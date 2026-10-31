"""Model -> JSON dict converters. Timestamps are emitted as ISO-8601 UTC ('Z' suffix)."""
from datetime import datetime

from sqlalchemy.orm import selectinload

from .models import Comment, Document, User


def iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def user_public(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "username": user.username, "full_name": user.full_name, "avatar_url": user.avatar_url}


def user_private(user: User) -> dict:
    return {
        **user_public(user),
        "email": user.email,
        "bio": user.bio,
        "role": user.role,
        "is_active": user.is_active,
        "is_muted": user.is_muted,
        "created_at": iso(user.created_at),
        "last_login_at": iso(user.last_login_at),
    }


def category_out(category) -> dict | None:
    if category is None:
        return None
    return {"id": category.id, "name": category.name, "slug": category.slug, "description": category.description}


def tag_out(tag) -> dict:
    return {"id": tag.id, "name": tag.name, "slug": tag.slug}


DOCUMENT_LOAD_OPTIONS = (
    selectinload(Document.category),
    selectinload(Document.tags),
    selectinload(Document.author),
)


def document_card(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "slug": doc.slug,
        "summary": doc.summary,
        "category": category_out(doc.category),
        "category_id": doc.category_id,
        "tags": [tag_out(t) for t in doc.tags],
        "author": doc.author_name,
        "author_user": user_public(doc.author),
        "status": doc.status,
        "image_url": doc.image_url,
        "image_alt": doc.image_alt,
        "views_count": doc.views_count,
        "likes_count": doc.likes_count,
        "rating_avg": round(doc.rating_sum / doc.rating_count, 2) if doc.rating_count else None,
        "rating_count": doc.rating_count,
        "created_at": iso(doc.created_at),
        "updated_at": iso(doc.updated_at),
        "published_at": iso(doc.published_at),
    }


def document_full(doc: Document) -> dict:
    return {
        **document_card(doc),
        "content": doc.content,
        "seo_title": doc.seo_title,
        "seo_description": doc.seo_description,
        "seo_keywords": doc.seo_keywords,
    }


COMMENT_LOAD_OPTIONS = (
    selectinload(Comment.user),
    selectinload(Comment.mentions),
)


def comment_out(comment: Comment, include_document: bool = False) -> dict:
    data = {
        "id": comment.id,
        "document_id": comment.document_id,
        "user": user_public(comment.user),
        "content": comment.content,
        "status": comment.status,
        "mentions": [m.user_id for m in comment.mentions],
        "created_at": iso(comment.created_at),
        "updated_at": iso(comment.updated_at),
    }
    if include_document and comment.document is not None:
        data["document"] = {"id": comment.document.id, "title": comment.document.title, "slug": comment.document.slug}
    return data
