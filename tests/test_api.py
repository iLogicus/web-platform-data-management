"""End-to-end API tests against a freshly seeded SQLite database."""


# ---------------------------------------------------------------- public / listing / search


def test_listing_is_paginated_and_published_only(client):
    res = client.get("/api/documents", params={"page": 1, "size": 10})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 56 and data["pages"] == 6 and len(data["items"]) == 10
    assert all(item["status"] == "published" for item in data["items"])
    assert data["items"][0]["summary"]
    dates = [i["published_at"] for i in data["items"]]
    assert dates == sorted(dates, reverse=True)


def test_keyword_search_filters_and_logs(client, tokens):
    res = client.get("/api/documents", params={"q": "heat pump"}, headers={"X-Session-Id": "t1"})
    items = res.json()["items"]
    assert any("Heat Pumps" in i["title"] for i in items)

    res = client.get("/api/documents", params={"category": "health"})
    assert {i["category"]["slug"] for i in res.json()["items"]} == {"health"}

    res = client.get("/api/documents", params={"tag": "sleep"})
    assert all(any(t["slug"] == "sleep" for t in i["tags"]) for i in res.json()["items"])

    res = client.get("/api/documents", params={"date_from": "2000-01-01", "date_to": "2000-01-31"})
    assert res.json()["total"] == 0

    doc_id = items[0]["id"]
    assert client.post("/api/search/click", json={"query": "heat pump", "doc_id": doc_id, "position": 1}).status_code == 201
    logs = client.get("/api/admin/search-logs", headers=tokens["seo"]).json()["items"]
    assert logs[0]["event_type"] == "click" and logs[0]["clicked_doc_id"] == doc_id
    assert any(l["query_string"] == "heat pump" and l["event_type"] == "search" for l in logs)


def test_detail_increments_views_and_hides_drafts(client, tokens):
    first = client.get("/api/documents").json()["items"][0]
    a = client.get(f"/api/documents/{first['slug']}").json()
    b = client.get(f"/api/documents/{first['id']}").json()
    assert b["views_count"] == a["views_count"] + 1
    assert a["content"] and a["author"] and a["category"] and isinstance(a["related"], list)

    draft = client.get("/api/admin/documents", params={"status": "draft"}, headers=tokens["editor"]).json()["items"][0]
    assert client.get(f"/api/documents/{draft['id']}").status_code == 404
    assert client.get(f"/api/documents/{draft['id']}", headers=tokens["editor"]).status_code == 200


# ---------------------------------------------------------------- auth & profile


def test_register_login_profile(client):
    res = client.post("/api/auth/register", json={"username": "newbie", "email": "newbie@x.io", "password": "secret1"})
    assert res.status_code == 201
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.post("/api/auth/register", json={"username": "newbie", "email": "n2@x.io", "password": "secret1"}).status_code == 409
    assert client.post("/api/auth/login", json={"login": "newbie", "password": "wrong"}).status_code == 401

    res = client.put("/api/auth/me", json={"full_name": "New Reader", "bio": "Hello"}, headers=headers)
    assert res.json()["user"]["full_name"] == "New Reader"
    assert client.put("/api/auth/me/password", json={"current_password": "secret1", "new_password": "secret2"}, headers=headers).status_code == 200
    assert client.post("/api/auth/login", json={"login": "newbie@x.io", "password": "secret2"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------- engagement


def test_comments_mentions_likes_ratings_reports(client, tokens):
    doc = client.get("/api/documents").json()["items"][1]
    res = client.post(f"/api/documents/{doc['id']}/comments", json={"content": "Great read @bob!"}, headers=tokens["alice"])
    assert res.status_code == 201 and res.json()["status"] == "visible"
    comment_id = res.json()["id"]

    mentions = client.get("/api/me/mentions", headers=tokens["bob"]).json()
    assert mentions["items"][0]["comment"] == "Great read @bob!" and mentions["unread"] >= 1

    first = client.post(f"/api/documents/{doc['id']}/like", headers=tokens["alice"]).json()
    second = client.post(f"/api/documents/{doc['id']}/like", headers=tokens["alice"]).json()
    assert first["liked"] != second["liked"]
    assert abs(first["likes_count"] - second["likes_count"]) == 1

    rated = client.put(f"/api/documents/{doc['id']}/rating", json={"score": 5}, headers=tokens["alice"]).json()
    assert rated["my_rating"] == 5 and rated["rating_count"] >= 1

    assert client.post(f"/api/comments/{comment_id}/report", json={"reason": "test report"}, headers=tokens["bob"]).status_code == 201
    assert client.post(f"/api/comments/{comment_id}/report", json={"reason": "again"}, headers=tokens["bob"]).status_code == 409
    assert client.post(f"/api/documents/{doc['id']}/comments", json={"content": "x"}).status_code == 401


def test_banned_words_mark_comment_as_spam(client, tokens):
    doc = client.get("/api/documents").json()["items"][2]
    res = client.post(f"/api/documents/{doc['id']}/comments", json={"content": "Get FREE MONEY now"}, headers=tokens["bob"])
    assert res.json()["status"] == "spam"
    visible = client.get(f"/api/documents/{doc['id']}/comments").json()["items"]
    assert all(c["id"] != res.json()["id"] for c in visible)


# ---------------------------------------------------------------- RBAC


def test_rbac_matrix(client, tokens):
    assert client.get("/api/admin/users", headers=tokens["admin"]).status_code == 200
    for role in ("editor", "moderator", "seo", "alice"):
        assert client.get("/api/admin/users", headers=tokens[role]).status_code == 403
    assert client.get("/api/admin/documents", headers=tokens["moderator"]).status_code == 403
    assert client.get("/api/admin/comments", headers=tokens["editor"]).status_code == 403
    assert client.get("/api/admin/comments", headers=tokens["moderator"]).status_code == 200
    assert client.get("/api/admin/seo/documents", headers=tokens["seo"]).status_code == 200
    assert client.get("/api/admin/analytics", headers=tokens["seo"]).status_code == 200
    assert client.get("/api/admin/analytics", headers=tokens["moderator"]).status_code == 403
    assert client.get("/api/admin/logs", headers=tokens["admin"]).status_code == 200
    assert client.get("/api/admin/documents").status_code == 401


def test_content_manager_crud_and_sanitising(client, tokens):
    cat = client.post("/api/admin/categories", json={"name": "Opinion"}, headers=tokens["editor"]).json()
    body = {
        "title": "Test Article About Libraries",
        "content": '<p onclick="x()">Hello <script>alert(1)</script><a href="javascript:evil()">link</a></p>',
        "category_id": cat["id"],
        "tags": ["Books", "Community", "books"],
        "status": "draft",
    }
    created = client.post("/api/admin/documents", json=body, headers=tokens["editor"]).json()
    assert "script" not in created["content"] and "onclick" not in created["content"] and "javascript" not in created["content"]
    assert sorted(t["name"] for t in created["tags"]) == ["Books", "Community"]
    assert created["summary"].startswith("Hello")

    published = client.patch(f"/api/admin/documents/{created['id']}/status", json={"status": "published"}, headers=tokens["editor"]).json()
    assert published["status"] == "published" and published["published_at"]
    assert client.get(f"/api/documents/{created['slug']}").status_code == 200

    body["title"] = "Updated Article About Libraries"
    assert client.put(f"/api/admin/documents/{created['id']}", json={**body, "status": "published"}, headers=tokens["editor"]).json()["title"] == body["title"]
    assert client.delete(f"/api/admin/documents/{created['id']}", headers=tokens["editor"]).status_code == 200
    assert client.get(f"/api/documents/{created['id']}").status_code == 404


def test_permission_matrix_is_editable(client, tokens):
    # Remove publish rights from content managers, then restore them.
    original = client.get("/api/admin/permissions", headers=tokens["admin"]).json()["matrix"]["content_manager"]
    reduced = [p for p in original if p != "content.publish"]
    assert client.put("/api/admin/permissions/content_manager", json={"permissions": reduced}, headers=tokens["admin"]).status_code == 200
    doc = client.get("/api/admin/documents", headers=tokens["editor"]).json()["items"][0]
    assert client.patch(f"/api/admin/documents/{doc['id']}/status", json={"status": "draft"}, headers=tokens["editor"]).status_code == 403
    client.put("/api/admin/permissions/content_manager", json={"permissions": original}, headers=tokens["admin"])
    assert client.put("/api/admin/permissions/super_admin", json={"permissions": []}, headers=tokens["admin"]).status_code == 400


def test_moderation_reports_and_mute(client, tokens):
    reports = client.get("/api/admin/reports", headers=tokens["moderator"]).json()
    assert reports["open_count"] >= 1
    report = reports["items"][0]
    res = client.patch(f"/api/admin/reports/{report['id']}", json={"status": "resolved", "action": "hide_comment"}, headers=tokens["moderator"])
    assert res.status_code == 200
    hidden = client.get("/api/admin/comments", params={"status": "hidden"}, headers=tokens["moderator"]).json()["items"]
    assert any(c["id"] == report["comment"]["id"] for c in hidden)

    bob_id = client.get("/api/auth/me", headers=tokens["bob"]).json()["user"]["id"]
    assert client.patch(f"/api/admin/users/{bob_id}/mute", json={"muted": True}, headers=tokens["moderator"]).status_code == 200
    doc = client.get("/api/documents").json()["items"][0]
    assert client.post(f"/api/documents/{doc['id']}/comments", json={"content": "hi"}, headers=tokens["bob"]).status_code == 403
    client.patch(f"/api/admin/users/{bob_id}/mute", json={"muted": False}, headers=tokens["moderator"])


def test_seo_and_analytics(client, tokens):
    seo = client.get("/api/admin/seo/documents", params={"missing_only": True}, headers=tokens["seo"]).json()
    assert seo["incomplete_count"] > 0 and seo["items"][0]["issues"]
    doc_id = seo["items"][0]["id"]
    res = client.put(
        f"/api/admin/seo/documents/{doc_id}",
        json={"seo_title": "Short title", "seo_description": "A" * 80, "seo_keywords": "a, b ,c", "image_alt": "alt"},
        headers=tokens["seo"],
    ).json()
    assert res["seo_keywords"] == "a, b, c" and res["issues"] == []

    stats = client.get("/api/admin/analytics", headers=tokens["seo"]).json()
    assert stats["totals"]["published"] >= 56 and stats["top_queries"] and len(stats["views_per_day"]) == 15
    export = client.get("/api/admin/export/documents.jsonl", headers=tokens["seo"])
    assert export.status_code == 200 and export.text.count("\n") >= 56


def test_super_admin_users_settings_logs(client, tokens):
    created = client.post(
        "/api/admin/users",
        json={"username": "mod2", "email": "mod2@x.io", "password": "secret1", "role": "moderator"},
        headers=tokens["admin"],
    ).json()
    assert created["role"] == "moderator"
    assert client.patch(f"/api/admin/users/{created['id']}", json={"is_active": False}, headers=tokens["admin"]).json()["is_active"] is False
    assert client.post("/api/auth/login", json={"login": "mod2", "password": "secret1"}).status_code == 403

    me = client.get("/api/auth/me", headers=tokens["admin"]).json()["user"]
    assert client.patch(f"/api/admin/users/{me['id']}", json={"role": "user"}, headers=tokens["admin"]).status_code == 400

    res = client.put("/api/admin/settings", json={"site_name": "Lumen Test", "items_per_page": 12}, headers=tokens["admin"])
    assert res.json()["site_name"] == "Lumen Test"
    assert client.get("/api/settings/public").json()["items_per_page"] == 12
    assert len(client.get("/api/documents").json()["items"]) == 12

    logs = client.get("/api/admin/logs", params={"action": "settings"}, headers=tokens["admin"]).json()["items"]
    assert logs and logs[0]["action"] == "settings.update"
