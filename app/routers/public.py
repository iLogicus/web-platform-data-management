"""Public read API: listing with keyword search & filters, article detail, taxonomy, search-click logging."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Category,
    Comment,
    Document,
    DocumentLike,
    DocumentView,
    Rating,
    SearchLog,
    Tag,
    User,
    document_tags,
)
from ..schemas import SearchClickIn
from ..security import get_current_user, get_current_user_optional, get_role_permissions
from ..serializers import DOCUMENT_LOAD_OPTIONS, category_out, document_card, document_full, user_public
from ..utils import PUBLIC_SETTING_KEYS, escape_like, get_settings, paginate

router = APIRouter(prefix="/api", tags=["public"])

SORTS = {
    "latest": (Document.published_at.desc(), Document.id.desc()),
    "oldest": (Document.published_at.asc(), Document.id.asc()),
    "popular": (Document.views_count.desc(), Document.id.desc()),
    "top_rated": (
        (Document.rating_sum * 1.0 / func.nullif(Document.rating_count, 0)).desc().nulls_last(),
        Document.rating_count.desc(),
    ),
}


def _session_id(request: Request) -> str | None:
    value = request.headers.get("X-Session-Id")
    return value[:64] if value else None


@router.get("/settings/public")
def public_settings(db: Session = Depends(get_db)):
    values = get_settings(db)
    return {key: values[key] for key in PUBLIC_SETTING_KEYS}


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Category, func.count(Document.id))
        .outerjoin(Document, and_(Document.category_id == Category.id, Document.status == "published"))
        .group_by(Category.id)
        .order_by(Category.name)
    ).all()
    return [{**category_out(c), "document_count": n} for c, n in rows]


@router.get("/tags")
def list_tags(limit: int = Query(40, ge=1, le=500), db: Session = Depends(get_db)):
    count = func.count(Document.id)
    rows = db.execute(
        select(Tag, count)
        .join(document_tags, document_tags.c.tag_id == Tag.id)
        .join(Document, and_(Document.id == document_tags.c.document_id, Document.status == "published"))
        .group_by(Tag.id)
        .order_by(count.desc(), Tag.name)
        .limit(limit)
    ).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug, "document_count": n} for t, n in rows]


@router.get("/documents")
def list_documents(
    request: Request,
    page: int = Query(1, ge=1),
    size: int | None = Query(None, ge=1, le=50),
    q: str | None = Query(None, max_length=200, description="Keyword search (SQL LIKE on title/summary/content)"),
    category: str | None = Query(None, description="Category slug"),
    tag: str | None = Query(None, description="Tag slug"),
    author: str | None = Query(None, description="Author username"),
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = Query("latest", pattern="^(latest|oldest|popular|top_rated)$"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    size = size or int(get_settings(db)["items_per_page"])
    stmt = select(Document).where(Document.status == "published")

    query = (q or "").strip()
    if query:
        # Phase 1 placeholder: every term must appear (case-insensitive LIKE) in title, summary or body.
        for term in query.split()[:8]:
            pattern = f"%{escape_like(term)}%"
            stmt = stmt.where(
                or_(
                    Document.title.ilike(pattern, escape="\\"),
                    Document.summary.ilike(pattern, escape="\\"),
                    Document.content_text.ilike(pattern, escape="\\"),
                )
            )
    if category:
        stmt = stmt.where(Document.category.has(Category.slug == category))
    if tag:
        stmt = stmt.where(Document.tags.any(Tag.slug == tag))
    if author:
        stmt = stmt.where(Document.author.has(User.username == author))
    if date_from:
        stmt = stmt.where(Document.published_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(Document.published_at < datetime.combine(date_to + timedelta(days=1), time.min))

    docs, meta = paginate(db, stmt.order_by(*SORTS[sort]), page, size, DOCUMENT_LOAD_OPTIONS)

    if query and page == 1:
        db.add(
            SearchLog(
                user_id=user.id if user else None,
                session_id=_session_id(request),
                query_string=query,
                event_type="search",
                results_count=meta["total"],
            )
        )
        db.commit()

    return {"items": [document_card(d) for d in docs], **meta, "query": query}


@router.get("/documents/{key}")
def get_document(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Detail view by numeric id or slug. Counts a view for published articles."""
    lookup = Document.id == int(key) if key.isdigit() else Document.slug == key
    doc = db.scalar(select(Document).where(lookup).options(*DOCUMENT_LOAD_OPTIONS))
    if doc is None:
        raise HTTPException(404, "Article not found")

    if doc.status != "published":
        perms = get_role_permissions(db, user.role) if user else set()
        if not perms & {"content.manage", "seo.manage"}:
            raise HTTPException(404, "Article not found")
    else:
        db.execute(update(Document).where(Document.id == doc.id).values(views_count=Document.views_count + 1))
        db.add(DocumentView(document_id=doc.id, user_id=user.id if user else None, session_id=_session_id(request)))
        db.commit()
        db.refresh(doc, ["views_count"])

    data = document_full(doc)
    data["comments_count"] = db.scalar(
        select(func.count(Comment.id)).where(Comment.document_id == doc.id, Comment.status == "visible")
    )
    data["my_like"] = False
    data["my_rating"] = None
    if user:
        data["my_like"] = (
            db.scalar(select(DocumentLike.id).where(DocumentLike.document_id == doc.id, DocumentLike.user_id == user.id))
            is not None
        )
        data["my_rating"] = db.scalar(
            select(Rating.score).where(Rating.document_id == doc.id, Rating.user_id == user.id)
        )

    related_stmt = (
        select(Document)
        .where(Document.status == "published", Document.id != doc.id)
        .order_by(Document.published_at.desc())
        .limit(4)
        .options(*DOCUMENT_LOAD_OPTIONS)
    )
    if doc.category_id:
        related_stmt = related_stmt.where(Document.category_id == doc.category_id)
    data["related"] = [document_card(d) for d in db.scalars(related_stmt)]
    return data


@router.post("/search/click", status_code=201)
def log_search_click(
    body: SearchClickIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Records which result a user opened for a query (training signal for Phase 2 ranking)."""
    if db.get(Document, body.doc_id) is None:
        raise HTTPException(404, "Article not found")
    log = SearchLog(
        user_id=user.id if user else None,
        session_id=_session_id(request),
        query_string=body.query.strip(),
        clicked_doc_id=body.doc_id,
        event_type="click",
        position=body.position,
    )
    db.add(log)
    db.commit()
    return {"id": log.id}


@router.get("/users/lookup")
def lookup_users(
    q: str = Query(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Username autocomplete for @mentions."""
    rows = db.scalars(
        select(User)
        .where(User.is_active.is_(True), User.username.ilike(f"{escape_like(q)}%", escape="\\"))
        .order_by(User.username)
        .limit(8)
    )
    return [user_public(u) for u in rows]
