"""Moderator: comment review, flag/report handling, spam control."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Comment, Report, User, utcnow
from ..schemas import CommentStatusIn, MuteIn, ReportHandleIn, SpamSettingsIn
from ..security import require_permissions
from ..serializers import COMMENT_LOAD_OPTIONS, comment_out, iso, user_public
from ..utils import audit, escape_like, get_settings, paginate, save_settings

router = APIRouter(prefix="/api/admin", tags=["admin: moderation"])


# ---------------------------------------------------------------- comments


@router.get("/comments")
def admin_list_comments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(visible|pending|hidden|spam)$"),
    q: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("comments.moderate")),
):
    stmt = select(Comment).order_by(Comment.created_at.desc())
    if status:
        stmt = stmt.where(Comment.status == status)
    if q:
        stmt = stmt.where(Comment.content.ilike(f"%{escape_like(q)}%", escape="\\"))
    comments, meta = paginate(db, stmt, page, size, (*COMMENT_LOAD_OPTIONS, selectinload(Comment.document)))
    counts = dict(db.execute(select(Comment.status, func.count(Comment.id)).group_by(Comment.status)).all())
    return {"items": [comment_out(c, include_document=True) for c in comments], **meta, "status_counts": counts}


@router.patch("/comments/{comment_id}")
def moderate_comment(
    comment_id: int,
    body: CommentStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("comments.moderate")),
):
    comment = db.scalar(select(Comment).where(Comment.id == comment_id).options(*COMMENT_LOAD_OPTIONS))
    if comment is None:
        raise HTTPException(404, "Comment not found")
    old = comment.status
    comment.status = body.status
    audit(db, user, "comment.moderate", "comment", comment.id, {"from": old, "to": body.status}, request)
    db.commit()
    return comment_out(comment)


# ---------------------------------------------------------------- reports


def _report_out(report: Report) -> dict:
    comment = report.comment
    return {
        "id": report.id,
        "reason": report.reason,
        "status": report.status,
        "resolution_note": report.resolution_note,
        "created_at": iso(report.created_at),
        "handled_at": iso(report.handled_at),
        "reporter": user_public(report.reporter),
        "handled_by": user_public(report.handled_by),
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "status": comment.status,
            "user": user_public(comment.user),
            "document": {"id": comment.document.id, "title": comment.document.title, "slug": comment.document.slug},
        },
    }


@router.get("/reports")
def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query("open", pattern="^(open|resolved|dismissed)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("reports.handle")),
):
    stmt = select(Report).order_by(Report.created_at.desc())
    if status:
        stmt = stmt.where(Report.status == status)
    options = (
        selectinload(Report.comment).selectinload(Comment.user),
        selectinload(Report.comment).selectinload(Comment.document),
        selectinload(Report.reporter),
        selectinload(Report.handled_by),
    )
    reports, meta = paginate(db, stmt, page, size, options)
    open_count = db.scalar(select(func.count(Report.id)).where(Report.status == "open"))
    return {"items": [_report_out(r) for r in reports], **meta, "open_count": open_count}


@router.patch("/reports/{report_id}")
def handle_report(
    report_id: int,
    body: ReportHandleIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("reports.handle")),
):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    comment = report.comment
    details = {"status": body.status, "action": body.action, "comment_id": comment.id}

    if body.action == "hide_comment":
        comment.status = "hidden"
    elif body.action == "mute_user":
        comment.status = "hidden"
        comment.user.is_muted = True

    # Every open report on the same comment is closed with the same decision.
    for other in db.scalars(select(Report).where(Report.comment_id == comment.id, Report.status == "open")):
        other.status = body.status
        other.resolution_note = body.note.strip()
        other.handled_by_id = user.id
        other.handled_at = utcnow()

    if body.action == "delete_comment":
        db.delete(comment)  # cascades to its reports
    audit(db, user, "report.handle", "report", report_id, details, request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- spam control


@router.get("/spam/settings")
def get_spam_settings(db: Session = Depends(get_db), _user: User = Depends(require_permissions("spam.manage"))):
    s = get_settings(db)
    return {
        "banned_words": s["banned_words"],
        "max_comments_per_minute": s["max_comments_per_minute"],
        "comments_require_approval": s["comments_require_approval"],
    }


@router.put("/spam/settings")
def update_spam_settings(
    body: SpamSettingsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("spam.manage")),
):
    words = sorted({w.strip().lower() for w in body.banned_words if w.strip()})
    values = {
        "banned_words": words,
        "max_comments_per_minute": body.max_comments_per_minute,
        "comments_require_approval": body.comments_require_approval,
    }
    save_settings(db, values)
    audit(db, user, "spam.settings_update", "settings", None, values, request)
    db.commit()
    return values


@router.get("/spam/muted-users")
def list_muted_users(db: Session = Depends(get_db), _user: User = Depends(require_permissions("spam.manage"))):
    return [user_public(u) for u in db.scalars(select(User).where(User.is_muted.is_(True)).order_by(User.username))]


@router.patch("/users/{user_id}/mute")
def mute_user(
    user_id: int,
    body: MuteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("spam.manage")),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    if target.role != "user":
        raise HTTPException(400, "Only regular users can be muted")
    target.is_muted = body.muted
    audit(db, user, "user.mute" if body.muted else "user.unmute", "user", target.id, {"username": target.username}, request)
    db.commit()
    return {"id": target.id, "is_muted": target.is_muted}
