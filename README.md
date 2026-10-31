# Lumen Magazine: Web Platform & Data Management (Phase 1)

A full-stack **News & Digital Magazine Portal** with complete CRUD, JWT authentication and
role-based access control (RBAC). It also includes a **Document Store** and a standardized
**Search & Click Log**, which Phase 2 needs for its search engine (tokenization,
inverted index, BM25 / TF-IDF ranking).

| Layer | Technology |
|---|---|
| Backend | Python **FastAPI** (REST), SQLAlchemy 2 ORM, JWT (PyJWT), PBKDF2 password hashing |
| Database | **PostgreSQL** (via `DATABASE_URL`) or SQLite (zero-setup default), using the same schema |
| Frontend | Responsive single-page app in plain **HTML / CSS / JavaScript** (ES modules), served by FastAPI |
| Tests | pytest + FastAPI TestClient (12 end-to-end API tests) |

---

## 1. Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m seed.seed                    # creates tables + loads demo data (resets the DB)
uvicorn app.main:app --reload          # http://127.0.0.1:8000
```

* Web UI: <http://127.0.0.1:8000>
* Interactive API docs (Swagger): <http://127.0.0.1:8000/docs>
* Run the tests: `pytest -q` (the tests use a throw-away SQLite database)

### Using PostgreSQL

```bash
createdb newsportal
cp .env.example .env     # then set:
# DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/newsportal
python -m seed.seed
uvicorn app.main:app --reload
```

### Demo accounts

| Role | Username | Password |
|---|---|---|
| Super Admin | `superadmin` | `Admin@123` |
| Content Manager | `editor` (also `minh_tran`, `james_ward`) | `Editor@123` |
| Moderator | `moderator` | `Moderator@123` |
| Data & SEO Specialist | `seo` | `Seo@123` |
| Registered users | `alice`, `bob`, `chloe`, `david`, `emma`, `felix`, `grace`, `henry`, `ivy`, `jack` | `User@123` |

---

## 2. Functional requirements: where each one is implemented

### A. Client / user interface

| Requirement | Implementation |
|---|---|
| Home & directory with pagination and summaries | `#/`, a featured article plus a paginated card grid with summary snippets. API: `GET /api/documents?page=&size=` |
| Detail view (full content, image, author, date, views, category, tags) | `#/article/<slug>`. Each visit increments `views_count` and writes a `document_views` row |
| Registration, login, profile management | `#/register`, `#/login`, `#/profile` (edit name, email, avatar, bio, change password) |
| Commenting | Comment thread on every article; users can delete their own comments |
| Rating / liking | Like toggle and 1–5 star ratings (one per user, can be changed); averages are kept on the document |
| User tagging | `@username` mentions in comments, with autocomplete. Mentioned users get a **Mentions** inbox with an unread badge |
| Keyword search (LIKE) | Header search box. Every term must match title, summary or body (`ILIKE`); matches are highlighted |
| Filters | Category, tag, date range (from/to), author and sort (newest, oldest, most viewed, top rated) |
| Reporting | Readers can flag a comment for moderators |

### B. Admin interface (RBAC)

The dashboard (`#/admin`) only shows the sections the signed-in role is allowed to use.
The API enforces the same permissions on every endpoint (see `app/security.py`).

| Role | What they can do in the dashboard |
|---|---|
| **Super Admin** | Users & roles (create, change role, activate/deactivate, reset password, delete); **permission matrix** editor; system logs; global settings (site name, tagline, page size, registration and comments on/off, announcement banner); plus everything below |
| **Content Manager** | Article CRUD with an HTML editor; publish/unpublish; categories CRUD; tags CRUD |
| **Moderator** | Comment queue (approve / hide / mark spam / delete); reports queue (dismiss, hide comment, delete comment, hide and mute author); spam control (banned words, rate limit, hold-for-approval, muted users) |
| **Data & SEO Specialist** | SEO metadata editor (title, meta description, keywords, image alt text) with completeness checks and a search-result preview; analytics dashboard; raw search/click logs; Phase 2 data exports |

#### Default permission matrix (editable at runtime in *Permissions*)

| Permission | Super Admin | Content Mgr | Moderator | SEO | User |
|---|:-:|:-:|:-:|:-:|:-:|
| `users.manage`, `permissions.manage`, `logs.view`, `settings.manage` | ✔ | | | | |
| `content.manage`, `content.publish`, `taxonomy.manage` | ✔ | ✔ | | | |
| `comments.moderate`, `reports.handle`, `spam.manage` | ✔ | | ✔ | | |
| `seo.manage` | ✔ | | | ✔ | |
| `analytics.view` | ✔ | ✔ | | ✔ | |

The Super Admin always has every permission, so the matrix cannot lock everyone out.

### Security notes

* Passwords are hashed with PBKDF2-SHA256 (120k iterations, per-user salt). Sessions use signed JWT bearer tokens.
* Article HTML goes through a **whitelist sanitizer**, which removes `<script>`, event handlers and `javascript:` URLs. Comments are always rendered as escaped text.
* The following actions are written to `audit_logs`: logins, failed logins, every admin action, and spam auto-flags.
* Spam control: a banned-word filter, a per-user comment rate limit, optional pre-moderation, and muting of users.

---

## 3. Data schema

```
users ──< documents >── categories          documents >──< tags   (document_tags)
  │           │
  │           ├──< comments ──< comment_mentions >── users
  │           │        └──< reports
  │           ├──< document_likes, ratings, document_views
  │           └──< search_logs (clicked_doc_id)
  └──< search_logs (user_id)                audit_logs, settings, role_permissions
```

### Documents (the Document Store): `documents`

| Field | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `title` | varchar(300) | |
| `slug` | varchar(320), unique | SEO-friendly URL |
| `content` | text | **HTML** used for display (sanitized) |
| `content_text` | text | **Plain text** extracted from `content`, ready for tokenization |
| `summary` | text | Generated from the content when left empty |
| `category_id` | FK → `categories` | |
| tags | M:N via `document_tags` | |
| `author_id` | FK → `users` | API also returns a resolved `author` name |
| `created_at`, `updated_at`, `published_at` | timestamp (UTC) | |
| `views_count`, `likes_count`, `rating_sum`, `rating_count` | int | Denormalized counters |
| `status` | `draft` \| `published` | |
| `image_url`, `image_alt`, `seo_title`, `seo_description`, `seo_keywords` | varchar | SEO / media metadata |

### Search & Click Log: `search_logs`

| Field | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK → users, nullable | `NULL` for anonymous visitors |
| `query_string` | varchar(500) | |
| `clicked_doc_id` | FK → documents, nullable | `NULL` on a plain search event |
| `timestamp` | timestamp (UTC) | |
| `event_type` | `search` \| `click` | Each query logs a `search` event; each opened result logs a `click` event |
| `results_count` | int | Number of results for the query (helps find zero-result queries) |
| `position` | int | Rank of the clicked result (1-based), useful for click models / learning-to-rank |
| `session_id` | varchar(64) | Anonymous browser session that groups a search with its clicks |

Other tables: `users`, `categories`, `tags`, `document_tags`, `comments`, `comment_mentions`,
`document_likes`, `ratings`, `reports`, `document_views`, `audit_logs`, `settings`, `role_permissions`.
The full definitions are in `app/models.py`.

### Seed data (`python -m seed.seed`)

* **60 original, hand-written articles** (no Lorem Ipsum). There are 6 in each of 10 categories:
  Technology, Science, Business & Economy, Health, Environment, Arts & Culture, Sports, Education, Travel and Food.
  56 are published and 4 are drafts. Together they use 149 tags (`seed/articles_a.py`, `seed/articles_b.py`).
* 16 users across all roles, about 125 comments (some with @mentions, plus spam and pending examples), 4 open reports,
  about 300 likes, about 175 ratings, about 1,200 view events and **450 search events with about 240 clicks**. Each click carries a
  realistic rank position, so Phase 2 has click data from day one.

---

## 4. Phase 2 readiness

* `documents.content_text` already holds clean plain text with paragraph breaks, ready for the tokenizer and inverted index.
* `GET /api/admin/export/documents.jsonl` exports the corpus (`id, title, summary, content, category, tags, author, created_at, views_count`).
* `GET /api/admin/export/search_logs.csv` exports the full interaction log for CTR, query analysis and learning-to-rank.
* Search currently goes through `GET /api/documents?q=` (in `app/routers/public.py`). Phase 2 can swap the `LIKE`
  filter for BM25 scoring without touching the frontend: the response shape and the click logging stay the same.

---

## 5. API overview

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET/PUT /api/auth/me`, `PUT /api/auth/me/password` |
| Public | `GET /api/documents` (page, size, q, category, tag, author, date_from, date_to, sort), `GET /api/documents/{id or slug}`, `GET /api/categories`, `GET /api/tags`, `GET /api/settings/public`, `POST /api/search/click` |
| Engagement | `GET/POST /api/documents/{id}/comments`, `DELETE /api/comments/{id}`, `POST /api/comments/{id}/report`, `POST /api/documents/{id}/like`, `PUT /api/documents/{id}/rating`, `GET /api/me/mentions`, `POST /api/me/mentions/read`, `GET /api/me/comments`, `GET /api/users/lookup` |
| Content Manager | `GET/POST /api/admin/documents`, `GET/PUT/DELETE /api/admin/documents/{id}`, `PATCH /api/admin/documents/{id}/status`, CRUD `/api/admin/categories`, CRUD `/api/admin/tags` |
| Moderator | `GET /api/admin/comments`, `PATCH /api/admin/comments/{id}`, `GET /api/admin/reports`, `PATCH /api/admin/reports/{id}`, `GET/PUT /api/admin/spam/settings`, `GET /api/admin/spam/muted-users`, `PATCH /api/admin/users/{id}/mute` |
| SEO & Data | `GET /api/admin/seo/documents`, `PUT /api/admin/seo/documents/{id}`, `GET /api/admin/analytics`, `GET /api/admin/search-logs`, `GET /api/admin/export/documents.jsonl`, `GET /api/admin/export/search_logs.csv` |
| Super Admin | CRUD `/api/admin/users`, `GET /api/admin/permissions`, `PUT /api/admin/permissions/{role}`, `GET /api/admin/logs`, `GET/PUT /api/admin/settings` |

Full request and response schemas are at `/docs`.

---

## 6. Project structure

```
app/
  main.py              FastAPI app, router registration, static file serving
  config.py            Environment configuration (.env supported)
  database.py          Engine/session (PostgreSQL or SQLite)
  models.py            SQLAlchemy schema
  permissions.py       Permission catalogue + default role matrix
  security.py          Password hashing, JWT, RBAC dependencies
  schemas.py           Pydantic request models
  serializers.py       Model → JSON
  utils.py             Slugs, HTML sanitizer, text extraction, settings, audit log, pagination
  routers/             auth, public, engagement, admin_content, admin_moderation, admin_seo, admin_system
seed/                  seed.py + 60 hand-written articles
static/                index.html, css/styles.css, js/{core,app,admin}.js
tests/                 End-to-end API tests
```
