"""Data & SEO Specialist: SEO metadata, analytics dashboard, search-log access and Phase 2 data exports."""
import csv
import io
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Comment, Document, DocumentLike, DocumentView, SearchLog, User, utcnow
from ..schemas import SeoUpdateIn
from ..security import require_permissions
from ..serializers import DOCUMENT_LOAD_OPTIONS, iso
from ..utils import audit, escape_like, paginate

router = APIRouter(prefix="/api/admin", tags=["admin: seo & analytics"])


def seo_issues(doc: Document) -> list[str]:
    issues = []
    if not doc.seo_title:
        issues.append("Missing SEO title")
    elif len(doc.seo_title) > 60:
        issues.append("SEO title longer than 60 characters")
    if not doc.seo_description:
        issues.append("Missing meta description")
    elif not 50 <= len(doc.seo_description) <= 160:
        issues.append("Meta description should be 50–160 characters")
    if not doc.seo_keywords:
        issues.append("Missing keywords")
    if doc.image_url and not doc.image_alt:
        issues.append("Image is missing alt text")
    return issues


def _seo_out(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "slug": doc.slug,
        "status": doc.status,
        "summary": doc.summary,
        "category": doc.category.name if doc.category else None,
        "image_url": doc.image_url,
        "image_alt": doc.image_alt,
        "seo_title": doc.seo_title,
        "seo_description": doc.seo_description,
        "seo_keywords": doc.seo_keywords,
        "views_count": doc.views_count,
        "issues": seo_issues(doc),
    }


@router.get("/seo/documents")
def seo_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    missing_only: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("seo.manage")),
):
    stmt = select(Document).order_by(Document.views_count.desc(), Document.id)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    if missing_only:
        stmt = stmt.where(
            or_(
                Document.seo_title == "",
                Document.seo_description == "",
                Document.seo_keywords == "",
                (Document.image_url != "") & (Document.image_alt == ""),
            )
        )
    docs, meta = paginate(db, stmt, page, size, DOCUMENT_LOAD_OPTIONS)
    incomplete = db.scalar(
        select(func.count(Document.id)).where(
            or_(Document.seo_title == "", Document.seo_description == "", Document.seo_keywords == "")
        )
    )
    return {"items": [_seo_out(d) for d in docs], **meta, "incomplete_count": incomplete}


@router.put("/seo/documents/{doc_id}")
def seo_update(
    doc_id: int,
    body: SeoUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("seo.manage")),
):
    doc = db.scalar(select(Document).where(Document.id == doc_id).options(*DOCUMENT_LOAD_OPTIONS))
    if doc is None:
        raise HTTPException(404, "Article not found")
    doc.seo_title = body.seo_title.strip()
    doc.seo_description = body.seo_description.strip()
    doc.seo_keywords = ", ".join(k.strip() for k in body.seo_keywords.split(",") if k.strip())
    doc.image_alt = body.image_alt.strip()
    audit(db, user, "seo.update", "document", doc.id, {"title": doc.title}, request)
    db.commit()
    return _seo_out(doc)


# ---------------------------------------------------------------- analytics


@router.get("/analytics")
def analytics(
    days: int = Query(14, ge=1, le=365),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("analytics.view")),
):
    since = utcnow() - timedelta(days=days)
    searches = db.scalar(select(func.count(SearchLog.id)).where(SearchLog.event_type == "search")) or 0
    clicks = db.scalar(select(func.count(SearchLog.id)).where(SearchLog.event_type == "click")) or 0

    totals = {
        "published": db.scalar(select(func.count(Document.id)).where(Document.status == "published")),
        "drafts": db.scalar(select(func.count(Document.id)).where(Document.status == "draft")),
        "users": db.scalar(select(func.count(User.id))),
        "comments": db.scalar(select(func.count(Comment.id)).where(Comment.status == "visible")),
        "views": db.scalar(select(func.coalesce(func.sum(Document.views_count), 0))),
        "likes": db.scalar(select(func.count(DocumentLike.id))),
        "searches": searches,
        "clicks": clicks,
        "ctr": round(clicks / searches, 3) if searches else 0,
    }

    top_documents = [
        {"id": d.id, "title": d.title, "slug": d.slug, "views_count": d.views_count, "likes_count": d.likes_count}
        for d in db.scalars(
            select(Document).where(Document.status == "published").order_by(Document.views_count.desc()).limit(10)
        )
    ]

    click_counts = dict(
        db.execute(
            select(func.lower(SearchLog.query_string), func.count(SearchLog.id))
            .where(SearchLog.event_type == "click")
            .group_by(func.lower(SearchLog.query_string))
        ).all()
    )
    query_rows = db.execute(
        select(func.lower(SearchLog.query_string).label("q"), func.count(SearchLog.id).label("n"))
        .where(SearchLog.event_type == "search")
        .group_by(func.lower(SearchLog.query_string))
        .order_by(func.count(SearchLog.id).desc())
        .limit(10)
    ).all()
    top_queries = [{"query": q, "searches": n, "clicks": click_counts.get(q, 0)} for q, n in query_rows]

    zero_result_queries = [
        {"query": q, "searches": n}
        for q, n in db.execute(
            select(func.lower(SearchLog.query_string), func.count(SearchLog.id))
            .where(SearchLog.event_type == "search", SearchLog.results_count == 0)
            .group_by(func.lower(SearchLog.query_string))
            .order_by(func.count(SearchLog.id).desc())
            .limit(10)
        ).all()
    ]

    def daily(column, *where):
        day = func.date(column)  # works on both SQLite and PostgreSQL
        rows = db.execute(select(day, func.count()).where(column >= since, *where).group_by(day).order_by(day)).all()
        by_day = {str(d): n for d, n in rows}
        start = since.date()
        return [
            {"date": str(start + timedelta(days=i)), "count": by_day.get(str(start + timedelta(days=i)), 0)}
            for i in range(days + 1)
        ]

    category_views = [
        {"category": name, "views": int(views or 0), "documents": n}
        for name, views, n in db.execute(
            select(Category.name, func.sum(Document.views_count), func.count(Document.id))
            .join(Document, Document.category_id == Category.id)
            .where(Document.status == "published")
            .group_by(Category.name)
            .order_by(func.sum(Document.views_count).desc())
        ).all()
    ]

    return {
        "totals": totals,
        "top_documents": top_documents,
        "top_queries": top_queries,
        "zero_result_queries": zero_result_queries,
        "views_per_day": daily(DocumentView.timestamp),
        "searches_per_day": daily(SearchLog.timestamp, SearchLog.event_type == "search"),
        "category_views": category_views,
    }


@router.get("/search-logs")
def list_search_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    event_type: str | None = Query(None, pattern="^(search|click)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("analytics.view")),
):
    stmt = select(SearchLog).order_by(SearchLog.timestamp.desc(), SearchLog.id.desc())
    if event_type:
        stmt = stmt.where(SearchLog.event_type == event_type)
    logs, meta = paginate(db, stmt, page, size)
    items = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "session_id": log.session_id,
            "query_string": log.query_string,
            "clicked_doc_id": log.clicked_doc_id,
            "event_type": log.event_type,
            "results_count": log.results_count,
            "position": log.position,
            "timestamp": iso(log.timestamp),
        }
        for log in logs
    ]
    return {"items": items, **meta}


# ---------------------------------------------------------------- Phase 2 exports


@router.get("/export/documents.jsonl")
def export_documents(
    db: Session = Depends(get_db), _user: User = Depends(require_permissions("analytics.view"))
):
    """One JSON object per line: the corpus the Phase 2 indexer will tokenize."""
    stmt = select(Document).where(Document.status == "published").order_by(Document.id).options(*DOCUMENT_LOAD_OPTIONS)
    lines = [
        json.dumps(
            {
                "id": doc.id,
                "title": doc.title,
                "summary": doc.summary,
                "content": doc.content_text,
                "category_id": doc.category_id,
                "category": doc.category.name if doc.category else None,
                "tags": [t.name for t in doc.tags],
                "author": doc.author_name,
                "created_at": iso(doc.created_at),
                "views_count": doc.views_count,
            },
            ensure_ascii=False,
        )
        + "\n"
        for doc in db.scalars(stmt)
    ]
    return StreamingResponse(
        iter(lines),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=documents.jsonl"},
    )


@router.get("/export/search_logs.csv")
def export_search_logs(
    db: Session = Depends(get_db), _user: User = Depends(require_permissions("analytics.view"))
):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "user_id", "session_id", "query_string", "clicked_doc_id", "event_type", "results_count", "position", "timestamp"])
    for log in db.scalars(select(SearchLog).order_by(SearchLog.id)):
        writer.writerow([
            log.id, log.user_id, log.session_id, log.query_string, log.clicked_doc_id,
            log.event_type, log.results_count, log.position, iso(log.timestamp),
        ])
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=search_logs.csv"},
    )
