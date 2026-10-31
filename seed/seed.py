"""Reset the database and populate it with realistic demo data.

Usage:  python -m seed.seed
"""
import html
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.main import ensure_defaults
from app.models import (
    Category,
    Comment,
    CommentMention,
    Document,
    DocumentLike,
    DocumentView,
    Rating,
    Report,
    SearchLog,
    Tag,
    User,
    utcnow,
)
from app.security import hash_password
from app.utils import DEFAULT_SETTINGS, audit, html_to_text, save_settings, slugify

from .articles_a import ARTICLES_A
from .articles_b import ARTICLES_B

rng = random.Random(42)
NOW = utcnow()

STAFF = [
    # username, full name, role, password
    ("superadmin", "Site Administrator", "super_admin", "Admin@123"),
    ("editor", "Elena Park", "content_manager", "Editor@123"),
    ("minh_tran", "Minh Tran", "content_manager", "Editor@123"),
    ("james_ward", "James Ward", "content_manager", "Editor@123"),
    ("moderator", "Sam Reyes", "moderator", "Moderator@123"),
    ("seo", "Priya Shah", "seo_specialist", "Seo@123"),
]
READERS = [
    ("alice", "Alice Nguyen"), ("bob", "Bob Martin"), ("chloe", "Chloe Tran"), ("david", "David Kim"),
    ("emma", "Emma Lopez"), ("felix", "Felix Wagner"), ("grace", "Grace Le"), ("henry", "Henry Brooks"),
    ("ivy", "Ivy Pham"), ("jack", "Jack Wilson"),
]
READER_PASSWORD = "User@123"

CATEGORIES = {
    "Technology": "Software, devices, the internet and the ideas shaping digital life.",
    "Science": "Discoveries and explainers from physics, biology, space and beyond.",
    "Business & Economy": "Markets, work, entrepreneurship and personal finance.",
    "Health": "Evidence-based guidance on fitness, nutrition, sleep and wellbeing.",
    "Environment": "Climate, energy, cities and the natural world.",
    "Arts & Culture": "Books, music, theatre, museums and creative communities.",
    "Sports": "Training, tactics, and the business and science of sport.",
    "Education": "How we learn, teach and think in the information age.",
    "Travel": "Practical trip planning and thoughtful ways to see the world.",
    "Food": "Cooking, food science and culinary traditions.",
}

COMMENT_TEMPLATES = [
    "Really clear explanation. I finally understand the basics of {tag}.",
    "Saved this to share with my team. The section on {tag} was especially useful.",
    "Would love a follow-up article that goes deeper into {tag}.",
    "I tried this approach myself last month and can confirm the advice works.",
    "Good overview, though I think the article could say more about costs.",
    "Thanks for avoiding jargon. My parents could read this too.",
    "Interesting read. Does anyone have recommendations for further reading on {tag}?",
    "I disagree slightly with the conclusion, but the evidence is presented fairly.",
    "Bookmarked. The examples make the topic much easier to follow.",
    "Great timing, we were discussing {tag} in class this week.",
    "The second paragraph surprised me. I had always assumed the opposite.",
    "Clear and balanced. More articles like this, please.",
]
MENTION_TEMPLATES = [
    "@{user} this is the article I mentioned yesterday.",
    "@{user} you might find the part about {tag} helpful for your project.",
    "Agree with @{user}, the practical tips are the best part.",
]
SPAM_COMMENTS = [
    "Click here to win free money!!! Limited offer, message me now.",
    "Best casino bonus offers this week only, check my profile.",
]
REPORT_REASONS = ["Off-topic", "Rude tone toward another reader", "Looks like advertising", "Misleading claim"]
ZERO_RESULT_QUERIES = ["blockchain voting", "mars colony", "quantum teleportation recipe", "cryptocurrency mining rig"]


def build_html(paragraphs: list[str], image_url: str, alt: str) -> str:
    parts = [f'<figure><img src="{image_url}" alt="{html.escape(alt)}"></figure>']
    for p in paragraphs:
        if p.startswith("## "):
            parts.append(f"<h2>{html.escape(p[3:], quote=False)}</h2>")
        else:
            parts.append(f"<p>{html.escape(p, quote=False)}</p>")
    return "\n".join(parts)


def matches(doc: Document, query: str) -> bool:
    haystack = f"{doc.title} {doc.summary} {doc.content_text}".lower()
    return all(term.lower() in haystack for term in query.split())


def seed(db: Session) -> None:
    save_settings(db, DEFAULT_SETTINGS)

    # ---- users
    users: dict[str, User] = {}
    for username, name, role, password in STAFF:
        users[username] = User(
            username=username, email=f"{username}@lumen.example", full_name=name, role=role,
            password_hash=hash_password(password), created_at=NOW - timedelta(days=200),
            bio=f"{name} works on the Lumen Magazine team.",
        )
    for username, name in READERS:
        users[username] = User(
            username=username, email=f"{username}@mail.example", full_name=name, role="user",
            password_hash=hash_password(READER_PASSWORD),
            created_at=NOW - timedelta(days=rng.randint(20, 180)),
        )
    db.add_all(users.values())
    db.flush()
    readers = [users[u] for u, _ in READERS]
    authors = [users["editor"], users["minh_tran"], users["james_ward"]]

    # ---- taxonomy
    categories = {name: Category(name=name, slug=slugify(name), description=desc) for name, desc in CATEGORIES.items()}
    db.add_all(categories.values())
    tags: dict[str, Tag] = {}

    def tag(name: str) -> Tag:
        slug = slugify(name)
        if slug not in tags:
            tags[slug] = Tag(name=name, slug=slug)
            db.add(tags[slug])
        return tags[slug]

    # ---- documents (spread over the last ~150 days)
    articles = ARTICLES_A + ARTICLES_B
    rng.shuffle(articles)
    draft_indexes = set(rng.sample(range(len(articles)), 4))
    documents: list[Document] = []
    for i, art in enumerate(articles):
        slug = slugify(art["title"])
        published = NOW - timedelta(days=int(150 * i / len(articles)) + rng.randint(0, 2), hours=rng.randint(0, 20))
        image_url = f"https://picsum.photos/seed/{slug}/1200/630"
        alt = f"Illustration for the article: {art['title']}"
        content = build_html(art["body"], image_url, alt)
        is_draft = i in draft_indexes
        has_seo = rng.random() < 0.6
        doc = Document(
            title=art["title"],
            slug=slug,
            summary=art["summary"],
            content=content,
            content_text=html_to_text(content),
            category=categories[art["category"]],
            author=rng.choice(authors),
            status="draft" if is_draft else "published",
            image_url=image_url,
            image_alt=alt if rng.random() < 0.85 else "",
            seo_title=art["title"][:60] if has_seo else "",
            seo_description=(art["summary"][:155] if has_seo else ""),
            seo_keywords=(", ".join(t.lower() for t in art["tags"]) if has_seo else ""),
            created_at=published - timedelta(hours=rng.randint(2, 48)),
            updated_at=published,
            published_at=None if is_draft else published,
        )
        doc.tags = [tag(t) for t in art["tags"]]
        documents.append(doc)
    db.add_all(documents)
    db.flush()
    published_docs = [d for d in documents if d.status == "published"]

    # ---- views: aggregate counter + recent view events for the analytics chart
    for doc in published_docs:
        age_days = max(1, (NOW - doc.published_at).days)
        recent = rng.randint(5, 40)
        for _ in range(recent):
            db.add(DocumentView(
                document_id=doc.id,
                user_id=rng.choice(readers).id if rng.random() < 0.4 else None,
                timestamp=NOW - timedelta(days=rng.randint(0, min(age_days, 30)), minutes=rng.randint(0, 1400)),
            ))
        doc.views_count = recent + rng.randint(40, 25 * age_days + 200)

    # ---- likes & ratings
    for doc in published_docs:
        likers = rng.sample(readers, rng.randint(0, len(readers)))
        for u in likers:
            db.add(DocumentLike(document_id=doc.id, user_id=u.id, created_at=doc.published_at + timedelta(hours=rng.randint(1, 300))))
        doc.likes_count = len(likers)
        raters = rng.sample(readers, rng.randint(0, 6))
        scores = [rng.choices([2, 3, 4, 5], weights=[1, 3, 6, 5])[0] for _ in raters]
        for u, s in zip(raters, scores):
            db.add(Rating(document_id=doc.id, user_id=u.id, score=s))
        doc.rating_sum, doc.rating_count = sum(scores), len(scores)

    # ---- comments, mentions, spam, reports
    visible_comments: list[Comment] = []
    for doc in published_docs:
        for _ in range(rng.randint(0, 4)):
            author = rng.choice(readers)
            tag_name = rng.choice(doc.tags).name.lower() if doc.tags else "this topic"
            mentioned = None
            if rng.random() < 0.15:
                mentioned = rng.choice([r for r in readers if r is not author])
                text = rng.choice(MENTION_TEMPLATES).format(user=mentioned.username, tag=tag_name)
            else:
                text = rng.choice(COMMENT_TEMPLATES).format(tag=tag_name)
            created = min(NOW, doc.published_at + timedelta(hours=rng.randint(1, 400)))
            comment = Comment(document_id=doc.id, user_id=author.id, content=text, created_at=created, updated_at=created)
            if mentioned:
                comment.mentions = [CommentMention(user_id=mentioned.id, created_at=created)]
            db.add(comment)
            visible_comments.append(comment)
    for text in SPAM_COMMENTS:
        db.add(Comment(document_id=rng.choice(published_docs).id, user_id=users["jack"].id, content=text, status="spam"))
    db.add(Comment(
        document_id=published_docs[0].id, user_id=users["felix"].id, status="pending",
        content="Is there a printable version of this guide? It would be handy for our community group.",
    ))
    db.flush()
    for comment in rng.sample(visible_comments, 4):
        reporter = rng.choice([r for r in readers if r.id != comment.user_id])
        db.add(Report(comment_id=comment.id, reporter_id=reporter.id, reason=rng.choice(REPORT_REASONS)))

    # ---- search & click logs (Phase 2 training data)
    query_pool = sorted({t.name.lower() for t in tags.values()})
    for doc in published_docs:
        words = [w.strip(":,?.'").lower() for w in doc.title.split() if len(w) > 5]
        query_pool.extend(words[:2])
    ordered = sorted(published_docs, key=lambda d: d.published_at, reverse=True)
    for _ in range(450):
        user = rng.choice(readers) if rng.random() < 0.55 else None
        session = f"seed-{rng.randint(1000, 9999)}"
        when = NOW - timedelta(days=rng.randint(0, 30), minutes=rng.randint(0, 1400))
        query = rng.choice(ZERO_RESULT_QUERIES) if rng.random() < 0.05 else rng.choice(query_pool)
        results = [d for d in ordered if matches(d, query)]
        db.add(SearchLog(user_id=user.id if user else None, session_id=session, query_string=query,
                         event_type="search", results_count=len(results), timestamp=when))
        if results and rng.random() < 0.7:
            position = min(len(results), rng.choices([1, 2, 3, 4, 5], weights=[50, 20, 12, 10, 8])[0])
            db.add(SearchLog(user_id=user.id if user else None, session_id=session, query_string=query,
                             clicked_doc_id=results[position - 1].id, event_type="click", position=position,
                             timestamp=when + timedelta(seconds=rng.randint(3, 40))))

    audit(db, users["superadmin"], "system.seed", "database", None, {"documents": len(documents), "users": len(users)})
    db.commit()
    print(f"Seeded {len(documents)} documents ({len(published_docs)} published), {len(users)} users, "
          f"{len(categories)} categories, {len(tags)} tags.")


def main() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_defaults(db)
        seed(db)


if __name__ == "__main__":
    main()
