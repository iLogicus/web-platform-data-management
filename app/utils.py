"""Shared helpers: slugs, HTML sanitising / text extraction, settings, audit logging, pagination."""
import html
import json
import math
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AuditLog, Setting, User

# ---------------------------------------------------------------- slugs


def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:200] or "item"


def unique_slug(db: Session, model, text: str, exclude_id: int | None = None) -> str:
    base = slugify(text)
    slug, n = base, 2
    while True:
        stmt = select(model.id).where(model.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if db.scalar(stmt) is None:
            return slug
        slug, n = f"{base}-{n}", n + 1


# ---------------------------------------------------------------- HTML

_ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "a", "ul", "ol", "li",
    "blockquote", "img", "figure", "figcaption", "code", "pre", "span",
}
_ALLOWED_ATTRS = {"a": {"href", "title"}, "img": {"src", "alt", "title"}}
_VOID_TAGS = {"br", "hr", "img"}
_DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "template"}
_BLOCK_TAGS = {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "div", "pre", "figcaption", "tr"}


def _is_safe_url(url: str) -> bool:
    url = url.strip().lower()
    if re.match(r"^[a-z][a-z0-9+.\-]*:", url):
        return url.startswith(("http://", "https://", "mailto:"))
    return True


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_WITH_CONTENT:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in _ALLOWED_TAGS:
            return
        parts = [tag]
        for name, value in attrs:
            if value is None or name not in _ALLOWED_ATTRS.get(tag, ()):
                continue
            if name in ("href", "src") and not _is_safe_url(value):
                continue
            parts.append(f'{name}="{html.escape(value, quote=True)}"')
        if tag == "a":
            parts.append('rel="noopener nofollow"')
        self.out.append("<" + " ".join(parts) + ">")

    def handle_startendtag(self, tag, attrs):
        if tag not in _DROP_WITH_CONTENT:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _DROP_WITH_CONTENT:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth or tag not in _ALLOWED_TAGS or tag in _VOID_TAGS:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(html.escape(data, quote=False))


def sanitize_html(raw: str) -> str:
    """Whitelist-based sanitiser for article HTML (removes scripts, event handlers, js: URLs)."""
    parser = _Sanitizer()
    parser.feed(raw or "")
    parser.close()
    return "".join(parser.out).strip()


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_WITH_CONTENT:
            self.skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in _DROP_WITH_CONTENT:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.chunks.append(data)


def html_to_text(raw: str) -> str:
    """Plain-text version of an article; paragraphs separated by newlines (input for Phase 2 indexing)."""
    parser = _TextExtractor()
    parser.feed(raw or "")
    parser.close()
    lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(parser.chunks).split("\n"))
    return "\n".join(line for line in lines if line)


def make_summary(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------- settings

DEFAULT_SETTINGS: dict[str, Any] = {
    "site_name": "Lumen Magazine",
    "site_tagline": "Clear reporting on technology, science, culture and everyday life",
    "items_per_page": 9,
    "allow_registration": True,
    "comments_enabled": True,
    "comments_require_approval": False,
    "max_comments_per_minute": 3,
    "banned_words": ["casino bonus", "free money", "click here to win", "cheap pills", "crypto giveaway"],
    "announcement": "",
}
PUBLIC_SETTING_KEYS = ("site_name", "site_tagline", "items_per_page", "allow_registration", "comments_enabled", "announcement")


def get_settings(db: Session) -> dict[str, Any]:
    values = dict(DEFAULT_SETTINGS)
    for row in db.scalars(select(Setting)):
        try:
            values[row.key] = json.loads(row.value)
        except json.JSONDecodeError:
            values[row.key] = row.value
    return values


def save_settings(db: Session, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=json.dumps(value)))
        else:
            row.value = json.dumps(value)


# ---------------------------------------------------------------- audit log


def audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str = "",
    entity_id: int | None = None,
    details: dict | str | None = None,
    request: Request | None = None,
) -> None:
    """Queue an audit-log row; it is written when the caller commits."""
    if isinstance(details, dict):
        details = json.dumps(details, ensure_ascii=False, default=str)
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_username=actor.username if actor else "",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or "",
            ip_address=(request.client.host if request and request.client else ""),
        )
    )


# ---------------------------------------------------------------- pagination


def paginate(db: Session, stmt, page: int, size: int, options: tuple = ()) -> tuple[list, dict]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = list(db.scalars(stmt.options(*options).offset((page - 1) * size).limit(size)).unique())
    meta = {"total": total, "page": page, "size": size, "pages": max(1, math.ceil(total / size))}
    return rows, meta
