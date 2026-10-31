"""RBAC definitions: the permission catalogue and the default role -> permission matrix.

The live matrix is stored in the `role_permissions` table so a Super Admin can change it
at runtime. `super_admin` always holds every permission (prevents locking everyone out).
"""

PERMISSIONS: dict[str, str] = {
    "users.manage": "Manage user accounts and assign roles",
    "permissions.manage": "Assign permissions to roles",
    "logs.view": "View system / audit logs",
    "settings.manage": "Configure global site settings",
    "content.manage": "Create, edit and delete articles",
    "content.publish": "Publish and unpublish articles",
    "taxonomy.manage": "Manage categories and tags",
    "comments.moderate": "Review, approve, hide and delete comments",
    "reports.handle": "Handle user flags / reports",
    "spam.manage": "Spam control: banned words, rate limits, muting users",
    "seo.manage": "Edit SEO metadata (titles, descriptions, keywords, alt text)",
    "analytics.view": "View analytics dashboards and search logs",
}

ROLES: dict[str, str] = {
    "super_admin": "Super Admin",
    "content_manager": "Content Manager",
    "moderator": "Moderator",
    "seo_specialist": "Data & SEO Specialist",
    "user": "Registered User",
}

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "super_admin": list(PERMISSIONS),
    "content_manager": ["content.manage", "content.publish", "taxonomy.manage", "analytics.view"],
    "moderator": ["comments.moderate", "reports.handle", "spam.manage"],
    "seo_specialist": ["seo.manage", "analytics.view"],
    "user": [],
}
