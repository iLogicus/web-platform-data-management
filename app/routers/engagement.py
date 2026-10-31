"""User engagement: comments (with @mention tagging), likes, ratings, reports."""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Comment, CommentMention, Document, DocumentLike, Rating, Report, User, utcnow
from ..schemas import CommentIn, RatingIn, ReportIn
from ..security import get_current_user, get_current_user_optional, get_role_permissions
from ..serializers import COMMENT_LOAD_OPTIONS, comment_out, iso, user_public
from ..utils import audit, get_settings, paginate

router = APIRouter(prefix="/api", tags=["engagement"])

MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{3,32})")


def _published_document(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.status != "published":
        raise HTTPException(404, "Article not found")
    return doc


# ---------------------------------------------------------------- comments


@router.get("/documents/{doc_id}/comments")
def list_comments(
    doc_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    visible = Comment.status == "visible"
    if user:  # authors also see their own comments that are still awaiting review
        visible = or_(visible, and_(Comment.user_id == user.id, Comment.status == "pending"))
    stmt = select(Comment).where(Comment.document_id == doc_id, visible).order_by(Comment.created_at.desc())
    comments, meta = paginate(db, stmt, page, size, COMMENT_LOAD_OPTIONS)
    return {"items": [comment_out(c) for c in comments], **meta}


@router.post("/documents/{doc_id}/comments", status_code=201)
def create_comment(
    doc_id: int,
    body: CommentIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _published_document(db, doc_id)
    settings = get_settings(db)
    if not settings["comments_enabled"]:
        raise HTTPException(403, "Comments are currently disabled")
    if user.is_muted:
        raise HTTPException(403, "Your account has been muted by a moderator")

    limit = int(settings["max_comments_per_minute"])
    if limit > 0:
        recent = db.scalar(
            select(func.count(Comment.id)).where(
                Comment.user_id == user.id, Comment.created_at >= utcnow() - timedelta(minutes=1)
            )
        )
        if recent >= limit:
            raise HTTPException(429, "You are commenting too fast. Please wait a minute.")

    text = body.content.strip()
    if not text:
        raise HTTPException(422, "Comment cannot be empty")

    lowered = text.lower()
    status = "visible"
    if any(w.strip() and w.strip().lower() in lowered for w in settings["banned_words"]):
        status = "spam"
        audit(db, user, "spam.auto_flag", "document", doc_id, {"excerpt": text[:120]}, request)
    elif settings["comments_require_approval"]:
        status = "pending"

    comment = Comment(document_id=doc_id, user_id=user.id, content=text, status=status)
    db.add(comment)
    db.flush()

    usernames = {name.lower() for name in MENTION_RE.findall(text)}
    if usernames:
        mentioned = db.scalars(
            select(User).where(func.lower(User.username).in_(usernames), User.id != user.id, User.is_active.is_(True))
        )
        for target in mentioned:
            db.add(CommentMention(comment_id=comment.id, user_id=target.id))
    db.commit()

    comment = db.scalar(select(Comment).where(Comment.id == comment.id).options(*COMMENT_LOAD_OPTIONS))
    return comment_out(comment)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(404, "Comment not found")
    is_owner = comment.user_id == user.id
    if not is_owner and "comments.moderate" not in get_role_permissions(db, user.role):
        raise HTTPException(403, "You can only delete your own comments")
    if not is_owner:
        audit(db, user, "comment.delete", "comment", comment.id, {"excerpt": comment.content[:120]}, request)
    db.delete(comment)
    db.commit()
    return {"ok": True}


@router.post("/comments/{comment_id}/report", status_code=201)
def report_comment(
    comment_id: int, body: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    comment = db.get(Comment, comment_id)
    if comment is None or comment.status != "visible":
        raise HTTPException(404, "Comment not found")
    if comment.user_id == user.id:
        raise HTTPException(400, "You cannot report your own comment")
    duplicate = db.scalar(
        select(Report.id).where(
            Report.comment_id == comment_id, Report.reporter_id == user.id, Report.status == "open"
        )
    )
    if duplicate:
        raise HTTPException(409, "You have already reported this comment")
    report = Report(comment_id=comment_id, reporter_id=user.id, reason=body.reason.strip())
    db.add(report)
    db.commit()
    return {"id": report.id, "status": report.status}


# ---------------------------------------------------------------- likes & ratings


@router.post("/documents/{doc_id}/like")
def toggle_like(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _published_document(db, doc_id)
    existing = db.scalar(select(DocumentLike).where(DocumentLike.document_id == doc_id, DocumentLike.user_id == user.id))
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(DocumentLike(document_id=doc_id, user_id=user.id))
        liked = True
    db.flush()
    doc.likes_count = db.scalar(select(func.count(DocumentLike.id)).where(DocumentLike.document_id == doc_id))
    db.commit()
    return {"liked": liked, "likes_count": doc.likes_count}


@router.put("/documents/{doc_id}/rating")
def rate_document(doc_id: int, body: RatingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _published_document(db, doc_id)
    rating = db.scalar(select(Rating).where(Rating.document_id == doc_id, Rating.user_id == user.id))
    if rating:
        rating.score = body.score
    else:
        db.add(Rating(document_id=doc_id, user_id=user.id, score=body.score))
    db.flush()
    total, count = db.execute(
        select(func.coalesce(func.sum(Rating.score), 0), func.count(Rating.id)).where(Rating.document_id == doc_id)
    ).one()
    doc.rating_sum, doc.rating_count = int(total), int(count)
    db.commit()
    return {
        "my_rating": body.score,
        "rating_avg": round(doc.rating_sum / doc.rating_count, 2) if doc.rating_count else None,
        "rating_count": doc.rating_count,
    }


# ---------------------------------------------------------------- "me" feeds


@router.get("/me/mentions")
def my_mentions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(CommentMention)
        .join(Comment, Comment.id == CommentMention.comment_id)
        .where(CommentMention.user_id == user.id, Comment.status == "visible")
        .order_by(CommentMention.created_at.desc())
    )
    options = (
        selectinload(CommentMention.comment).selectinload(Comment.user),
        selectinload(CommentMention.comment).selectinload(Comment.document),
    )
    mentions, meta = paginate(db, stmt, page, size, options)
    items = [
        {
            "id": m.id,
            "is_read": m.is_read,
            "created_at": iso(m.created_at),
            "by": user_public(m.comment.user),
            "comment": m.comment.content,
            "document": {"id": m.comment.document.id, "title": m.comment.document.title, "slug": m.comment.document.slug},
        }
        for m in mentions
    ]
    unread = db.scalar(
        select(func.count(CommentMention.id))
        .join(Comment, Comment.id == CommentMention.comment_id)
        .where(CommentMention.user_id == user.id, CommentMention.is_read.is_(False), Comment.status == "visible")
    )
    return {"items": items, **meta, "unread": unread}


@router.post("/me/mentions/read")
def mark_mentions_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for mention in db.scalars(
        select(CommentMention).where(CommentMention.user_id == user.id, CommentMention.is_read.is_(False))
    ):
        mention.is_read = True
    db.commit()
    return {"ok": True}


@router.get("/me/comments")
def my_comments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Comment).where(Comment.user_id == user.id).order_by(Comment.created_at.desc())
    comments, meta = paginate(db, stmt, page, size, (*COMMENT_LOAD_OPTIONS, selectinload(Comment.document)))
    return {"items": [comment_out(c, include_document=True) for c in comments], **meta}
