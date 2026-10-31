"""Content Manager: article CRUD, publication status, taxonomy (categories & tags)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Document, Tag, User, document_tags, utcnow
from ..schemas import CategoryIn, DocumentIn, StatusIn, TagIn
from ..security import get_role_permissions, require_any_permission, require_permissions
from ..serializers import DOCUMENT_LOAD_OPTIONS, category_out, document_card, document_full
from ..utils import audit, escape_like, html_to_text, make_summary, paginate, sanitize_html, slugify, unique_slug

router = APIRouter(prefix="/api/admin", tags=["admin: content"])


def resolve_tags(db: Session, names: list[str]) -> list[Tag]:
    """Look tags up by slug, creating missing ones."""
    tags: dict[str, Tag] = {}
    for raw in names:
        name = raw.strip()[:60]
        if not name:
            continue
        slug = slugify(name)
        if slug in tags:
            continue
        tag = db.scalar(select(Tag).where(Tag.slug == slug))
        if tag is None:
            tag = Tag(name=name, slug=slug)
            db.add(tag)
            db.flush()
        tags[slug] = tag
    return list(tags.values())


def _set_status(db: Session, user: User, doc: Document, new_status: str) -> None:
    if new_status == doc.status:
        return
    if "content.publish" not in get_role_permissions(db, user.role):
        raise HTTPException(403, "You do not have permission to change publication status")
    doc.status = new_status
    if new_status == "published" and doc.published_at is None:
        doc.published_at = utcnow()


def _apply(db: Session, user: User, doc: Document, body: DocumentIn) -> None:
    if body.category_id is not None and db.get(Category, body.category_id) is None:
        raise HTTPException(422, "Category does not exist")
    doc.title = body.title.strip()
    doc.content = sanitize_html(body.content)
    doc.content_text = html_to_text(doc.content)
    doc.summary = body.summary.strip() or make_summary(doc.content_text)
    doc.category_id = body.category_id
    doc.tags = resolve_tags(db, body.tags)
    doc.image_url = body.image_url.strip()
    doc.image_alt = body.image_alt.strip()
    _set_status(db, user, doc, body.status)


def _get_document(db: Session, doc_id: int) -> Document:
    doc = db.scalar(select(Document).where(Document.id == doc_id).options(*DOCUMENT_LOAD_OPTIONS))
    if doc is None:
        raise HTTPException(404, "Article not found")
    return doc


# ---------------------------------------------------------------- documents


@router.get("/documents")
def admin_list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, pattern="^(draft|published)$"),
    category_id: int | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("content.manage")),
):
    stmt = select(Document).order_by(Document.updated_at.desc(), Document.id.desc())
    if q:
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(or_(Document.title.ilike(pattern, escape="\\"), Document.summary.ilike(pattern, escape="\\")))
    if status:
        stmt = stmt.where(Document.status == status)
    if category_id:
        stmt = stmt.where(Document.category_id == category_id)
    docs, meta = paginate(db, stmt, page, size, DOCUMENT_LOAD_OPTIONS)
    return {"items": [document_card(d) for d in docs], **meta}


@router.get("/documents/{doc_id}")
def admin_get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_permission("content.manage", "seo.manage")),
):
    return document_full(_get_document(db, doc_id))


@router.post("/documents", status_code=201)
def create_document(
    body: DocumentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("content.manage")),
):
    doc = Document(author_id=user.id, status="draft", slug=unique_slug(db, Document, body.title))
    _apply(db, user, doc, body)
    db.add(doc)
    db.flush()
    audit(db, user, "document.create", "document", doc.id, {"title": doc.title, "status": doc.status}, request)
    db.commit()
    return document_full(_get_document(db, doc.id))


@router.put("/documents/{doc_id}")
def update_document(
    doc_id: int,
    body: DocumentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("content.manage")),
):
    doc = _get_document(db, doc_id)
    _apply(db, user, doc, body)
    doc.updated_at = utcnow()
    audit(db, user, "document.update", "document", doc.id, {"title": doc.title, "status": doc.status}, request)
    db.commit()
    return document_full(_get_document(db, doc.id))


@router.patch("/documents/{doc_id}/status")
def change_document_status(
    doc_id: int,
    body: StatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("content.publish")),
):
    doc = _get_document(db, doc_id)
    _set_status(db, user, doc, body.status)
    action = "document.publish" if body.status == "published" else "document.unpublish"
    audit(db, user, action, "document", doc.id, {"title": doc.title}, request)
    db.commit()
    return document_card(doc)


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("content.manage")),
):
    doc = _get_document(db, doc_id)
    audit(db, user, "document.delete", "document", doc.id, {"title": doc.title}, request)
    db.delete(doc)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- categories


@router.get("/categories")
def admin_list_categories(
    db: Session = Depends(get_db), _user: User = Depends(require_any_permission("taxonomy.manage", "content.manage"))
):
    rows = db.execute(
        select(Category, func.count(Document.id))
        .outerjoin(Document, Document.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name)
    ).all()
    return [{**category_out(c), "document_count": n} for c, n in rows]


@router.post("/categories", status_code=201)
def create_category(
    body: CategoryIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("taxonomy.manage")),
):
    name = body.name.strip()
    if db.scalar(select(Category.id).where(func.lower(Category.name) == name.lower())):
        raise HTTPException(409, "A category with this name already exists")
    category = Category(name=name, slug=unique_slug(db, Category, name), description=body.description.strip())
    db.add(category)
    db.flush()
    audit(db, user, "category.create", "category", category.id, {"name": name}, request)
    db.commit()
    return category_out(category)


@router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    body: CategoryIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("taxonomy.manage")),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    name = body.name.strip()
    clash = db.scalar(select(Category.id).where(func.lower(Category.name) == name.lower(), Category.id != category_id))
    if clash:
        raise HTTPException(409, "A category with this name already exists")
    if name != category.name:
        category.slug = unique_slug(db, Category, name, exclude_id=category_id)
    category.name = name
    category.description = body.description.strip()
    audit(db, user, "category.update", "category", category.id, {"name": name}, request)
    db.commit()
    return category_out(category)


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("taxonomy.manage")),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    audit(db, user, "category.delete", "category", category.id, {"name": category.name}, request)
    db.delete(category)  # articles keep existing with category_id = NULL
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- tags


@router.get("/tags")
def admin_list_tags(
    q: str | None = Query(None, max_length=60),
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_permission("taxonomy.manage", "content.manage")),
):
    count = func.count(document_tags.c.document_id)
    stmt = (
        select(Tag, count)
        .outerjoin(document_tags, document_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{escape_like(q)}%", escape="\\"))
    return [{"id": t.id, "name": t.name, "slug": t.slug, "document_count": n} for t, n in db.execute(stmt).all()]


@router.post("/tags", status_code=201)
def create_tag(
    body: TagIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("taxonomy.manage")),
):
    slug = slugify(body.name)
    if db.scalar(select(Tag.id).where(Tag.slug == slug)):
        raise HTTPException(409, "This tag already exists")
    tag = Tag(name=body.name.strip(), slug=slug)
    db.add(tag)
    db.flush()
    audit(db, user, "tag.create", "tag", tag.id, {"name": tag.name}, request)
    db.commit()
    return {"id": tag.id, "name": tag.name, "slug": tag.slug}


@router.put("/tags/{tag_id}")
def update_tag(
    tag_id: int,
    body: TagIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("taxonomy.manage")),
):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Tag not found")
    slug = slugify(body.name)
    if db.scalar(select(Tag.id).where(Tag.slug == slug, Tag.id != tag_id)):
        raise HTTPException(409, "Another tag already uses this name")
    tag.name, tag.slug = body.name.strip(), slug
    audit(db, user, "tag.update", "tag", tag.id, {"name": tag.name}, request)
    db.commit()
    return {"id": tag.id, "name": tag.name, "slug": tag.slug}


@router.delete("/tags/{tag_id}")
def delete_tag(
    tag_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("taxonomy.manage")),
):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Tag not found")
    audit(db, user, "tag.delete", "tag", tag.id, {"name": tag.name}, request)
    db.delete(tag)
    db.commit()
    return {"ok": True}
