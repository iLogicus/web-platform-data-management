// Router + public pages: home/listing & search, article detail, auth, profile.
import {
  api, avatar, bindPagination, can, clearSession, debounce, displayName, esc, fmtDate, fmtNum,
  go, highlight, loadSession, modal, pagination, setSession, state, toast,
} from "./core.js";

const app = document.getElementById("app");
let taxonomyCache = null;

// ---------------------------------------------------------------- router

const routes = [
  [/^\/$/, renderHome],
  [/^\/article\/([^/]+)$/, renderArticle],
  [/^\/login$/, renderLogin],
  [/^\/register$/, renderRegister],
  [/^\/profile(?:\/(\w+))?$/, renderProfile],
  [/^\/admin(?:\/([\w-]+))?$/, async (m, query) => (await import("./admin.js")).renderAdmin(app, m[1], query)],
];

function parseHash() {
  const [path, qs = ""] = (location.hash.slice(1) || "/").split("?");
  return { path: path || "/", query: new URLSearchParams(qs) };
}

async function router() {
  const { path, query } = parseHash();
  document.getElementById("main-nav").classList.remove("open");
  document.querySelectorAll("dialog").forEach((d) => d.remove());
  document.getElementById("search-input").value = path === "/" ? query.get("q") || "" : "";
  setTitle();
  renderNav();
  for (const [pattern, handler] of routes) {
    const match = path.match(pattern);
    if (match) {
      app.innerHTML = `<p class="loading">Loading…</p>`;
      try {
        await handler(match, query);
      } catch (err) {
        app.innerHTML = `<div class="empty"><h2>Something went wrong</h2><p>${esc(err.message)}</p><a class="btn" href="#/">Back to home</a></div>`;
      }
      window.scrollTo(0, 0);
      return;
    }
  }
  app.innerHTML = `<div class="empty"><h2>Page not found</h2><a class="btn" href="#/">Back to home</a></div>`;
}

function setTitle(title, description) {
  const site = state.settings.site_name || "Lumen Magazine";
  document.title = title ? `${title} · ${site}` : site;
  document.querySelector('meta[name="description"]').content = description || state.settings.site_tagline || "";
}

function renderNav() {
  const { path } = parseHash();
  const isAdmin = state.permissions.length > 0;
  const link = (href, label, active) => `<a href="${href}" class="${active ? "active" : ""}">${label}</a>`;
  let html = link("#/", "Home", path === "/");
  if (isAdmin) html += link("#/admin", "Dashboard", path.startsWith("/admin"));
  if (state.user) {
    const badge = state.unread ? ` <span class="badge" title="Unread mentions">${state.unread}</span>` : "";
    html += link("#/profile", `@${esc(state.user.username)}${badge}`, path.startsWith("/profile"));
    html += `<button class="btn btn-sm" id="logout-btn">Log out</button>`;
  } else {
    html += link(`#/login?next=${encodeURIComponent(location.hash.slice(1))}`, "Log in", path === "/login");
    if (state.settings.allow_registration !== false) html += `<a href="#/register" class="btn btn-primary btn-sm">Register</a>`;
  }
  const nav = document.getElementById("main-nav");
  nav.innerHTML = html;
  const logout = document.getElementById("logout-btn");
  if (logout) {
    logout.onclick = () => {
      clearSession();
      toast("You have been logged out.");
      go("/");
    };
  }
}

async function refreshUnread() {
  if (!state.user) return;
  try {
    state.unread = (await api("/api/me/mentions", { params: { size: 1 } })).unread;
  } catch {
    state.unread = 0;
  }
  renderNav();
}

async function taxonomy() {
  if (!taxonomyCache) {
    const [categories, tags] = await Promise.all([api("/api/categories"), api("/api/tags", { params: { limit: 30 } })]);
    taxonomyCache = { categories, tags };
  }
  return taxonomyCache;
}

// ---------------------------------------------------------------- home / directory / search

function cardMeta(d) {
  const rating = d.rating_avg ? `<span title="Average rating">★ ${d.rating_avg.toFixed(1)}</span>` : "";
  return `<div class="meta">
      <span>${esc(d.author)}</span><span>${fmtDate(d.published_at)}</span>
      <span title="Views">👁 ${fmtNum(d.views_count)}</span><span title="Likes">♥ ${fmtNum(d.likes_count)}</span>${rating}
    </div>`;
}

function articleCard(d, q, position) {
  const href = `#/article/${encodeURIComponent(d.slug)}`;
  const img = d.image_url
    ? `<a href="${href}" data-doc="${d.id}" data-pos="${position}" tabindex="-1"><img class="thumb" src="${esc(d.image_url)}" alt="${esc(d.image_alt)}" loading="lazy"></a>`
    : "";
  return `<article class="card article-card">
      ${img}
      <div class="body">
        ${d.category ? `<a class="kicker" href="#/?category=${d.category.slug}">${esc(d.category.name)}</a>` : ""}
        <h3><a href="${href}" data-doc="${d.id}" data-pos="${position}">${highlight(d.title, q)}</a></h3>
        <p>${highlight(d.summary, q)}</p>
        ${cardMeta(d)}
      </div>
    </article>`;
}

function featuredCard(d) {
  const href = `#/article/${encodeURIComponent(d.slug)}`;
  return `<article class="card featured">
      ${d.image_url ? `<a href="${href}" tabindex="-1"><img class="thumb" src="${esc(d.image_url)}" alt="${esc(d.image_alt)}"></a>` : "<div></div>"}
      <div class="body">
        <span class="kicker">Latest${d.category ? ` · ${esc(d.category.name)}` : ""}</span>
        <h2><a href="${href}">${esc(d.title)}</a></h2>
        <p class="muted">${esc(d.summary)}</p>
        <div class="chips">${d.tags.map((t) => `<a class="chip" href="#/?tag=${t.slug}">${esc(t.name)}</a>`).join("")}</div>
        ${cardMeta(d)}
      </div>
    </article>`;
}

async function renderHome(_m, query) {
  const filters = {
    q: query.get("q") || "",
    category: query.get("category") || "",
    tag: query.get("tag") || "",
    date_from: query.get("date_from") || "",
    date_to: query.get("date_to") || "",
    sort: query.get("sort") || "latest",
    author: query.get("author") || "",
  };
  const page = Math.max(1, Number(query.get("page")) || 1);
  const [list, tax] = await Promise.all([api("/api/documents", { params: { ...filters, page } }), taxonomy()]);
  const filtered = Object.entries(filters).some(([k, v]) => v && !(k === "sort" && v === "latest"));
  const items = [...list.items];
  const featured = !filtered && page === 1 && items.length ? items.shift() : null;
  const offset = (page - 1) * list.size;

  const category = tax.categories.find((c) => c.slug === filters.category);
  let heading = "Latest stories";
  if (filters.q) heading = `Results for “${esc(filters.q)}”`;
  else if (category) heading = esc(category.name);
  else if (filters.tag) heading = `Tagged “${esc(filters.tag)}”`;
  else if (filters.author) heading = `Articles by @${esc(filters.author)}`;

  setTitle(filters.q ? `Search: ${filters.q}` : category ? category.name : "");

  const option = (value, label, current) => `<option value="${esc(value)}" ${value === current ? "selected" : ""}>${esc(label)}</option>`;
  app.innerHTML = `
    ${featured ? featuredCard(featured) : ""}
    <div class="layout">
      <section>
        <div class="card filters">
          <form id="filter-form">
            <div><label for="f-category">Category</label>
              <select id="f-category" name="category">${option("", "All categories", filters.category)}${tax.categories.map((c) => option(c.slug, c.name, filters.category)).join("")}</select></div>
            <div><label for="f-tag">Tag</label>
              <select id="f-tag" name="tag">${option("", "All tags", filters.tag)}${tax.tags.map((t) => option(t.slug, t.name, filters.tag)).join("")}${filters.tag && !tax.tags.some((t) => t.slug === filters.tag) ? option(filters.tag, filters.tag, filters.tag) : ""}</select></div>
            <div><label for="f-from">From</label><input type="date" id="f-from" name="date_from" value="${esc(filters.date_from)}"></div>
            <div><label for="f-to">To</label><input type="date" id="f-to" name="date_to" value="${esc(filters.date_to)}"></div>
            <div><label for="f-sort">Sort by</label>
              <select id="f-sort" name="sort">${option("latest", "Newest", filters.sort)}${option("oldest", "Oldest", filters.sort)}${option("popular", "Most viewed", filters.sort)}${option("top_rated", "Top rated", filters.sort)}</select></div>
            <div class="actions"><button class="btn btn-primary" type="submit">Apply</button>${filtered ? `<a class="btn" href="#/">Reset</a>` : ""}</div>
          </form>
        </div>
        <div class="result-head">
          <h2>${heading}</h2>
          <span class="muted small">${fmtNum(list.total)} article${list.total === 1 ? "" : "s"} · page ${list.page} of ${list.pages}</span>
        </div>
        ${items.length || featured
          ? `<div class="grid" id="grid">${items.map((d, i) => articleCard(d, filters.q, offset + i + 1 + (featured ? 1 : 0))).join("")}</div>`
          : `<div class="card empty"><h3>No articles found</h3><p>Try different keywords or remove some filters.</p></div>`}
        ${pagination(list)}
      </section>
      <aside class="sidebar">
        <div class="card panel">
          <h3>Categories</h3>
          <ul class="cat-list">${tax.categories.map((c) => `<li><a href="#/?category=${c.slug}" class="${c.slug === filters.category ? "active" : ""}"><span>${esc(c.name)}</span><span class="muted">${c.document_count}</span></a></li>`).join("")}</ul>
        </div>
        <div class="card panel">
          <h3>Popular tags</h3>
          <div class="chips">${tax.tags.map((t) => `<a class="chip ${t.slug === filters.tag ? "active" : ""}" href="#/?tag=${t.slug}">${esc(t.name)}</a>`).join("")}</div>
        </div>
      </aside>
    </div>`;

  document.getElementById("filter-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    go("/", { q: filters.q, author: filters.author, ...data, sort: data.sort === "latest" ? "" : data.sort });
  });
  bindPagination(app, (p) => go("/", { ...filters, sort: filters.sort === "latest" ? "" : filters.sort, page: p }));

  // Click logging for Phase 2: which result (and at what rank) was opened for a query.
  if (filters.q) {
    app.querySelectorAll("[data-doc]").forEach((a) =>
      a.addEventListener("click", () => {
        api("/api/search/click", {
          method: "POST",
          body: { query: filters.q, doc_id: Number(a.dataset.doc), position: Number(a.dataset.pos) },
        }).catch(() => {});
      })
    );
  }
}

// ---------------------------------------------------------------- article detail

function renderCommentText(text) {
  return esc(text).replace(/(^|[^\w@])@([A-Za-z0-9_]{3,32})/g, '$1<span class="mention">@$2</span>');
}

function commentHtml(c) {
  const own = state.user && c.user && state.user.id === c.user.id;
  const actions = [];
  if (state.user && !own && c.status === "visible") actions.push(`<button class="btn btn-sm" data-report="${c.id}">Report</button>`);
  if (can("comments.moderate") && !own) actions.push(`<button class="btn btn-sm" data-hide="${c.id}">Hide</button>`);
  if (own || can("comments.moderate")) actions.push(`<button class="btn btn-sm btn-danger" data-delete="${c.id}">Delete</button>`);
  return `<div class="comment" id="comment-${c.id}">
      <div class="comment-head">${avatar(c.user)}<strong>${esc(displayName(c.user))}</strong>
        <span class="muted">@${esc(c.user ? c.user.username : "")} · ${fmtDate(c.created_at, true)}</span>
        ${c.status !== "visible" ? `<span class="pill ${c.status}">${c.status === "pending" ? "Awaiting review" : esc(c.status)}</span>` : ""}
      </div>
      <p class="comment-body">${renderCommentText(c.content)}</p>
      ${actions.length ? `<div class="actions" style="margin-top:.4rem">${actions.join("")}</div>` : ""}
    </div>`;
}

function setupMentionAutocomplete(textarea) {
  const list = document.createElement("ul");
  list.className = "suggest";
  list.hidden = true;
  textarea.parentElement.appendChild(list);
  let items = [];
  let selected = 0;

  const currentToken = () => {
    const before = textarea.value.slice(0, textarea.selectionStart);
    const m = before.match(/(?:^|\s)@([A-Za-z0-9_]{1,32})$/);
    return m ? m[1] : null;
  };
  const choose = (username) => {
    const pos = textarea.selectionStart;
    const before = textarea.value.slice(0, pos).replace(/@([A-Za-z0-9_]{1,32})$/, `@${username} `);
    textarea.value = before + textarea.value.slice(pos);
    textarea.setSelectionRange(before.length, before.length);
    list.hidden = true;
    textarea.focus();
  };
  const draw = () => {
    list.innerHTML = items
      .map((u, i) => `<li data-u="${esc(u.username)}" class="${i === selected ? "sel" : ""}"><strong>@${esc(u.username)}</strong> <span class="muted small">${esc(u.full_name)}</span></li>`)
      .join("");
    list.hidden = !items.length;
    list.style.top = `${textarea.offsetTop + textarea.offsetHeight}px`;
    list.querySelectorAll("li").forEach((li) => li.addEventListener("mousedown", (e) => {
      e.preventDefault();
      choose(li.dataset.u);
    }));
  };
  const lookup = debounce(async (token) => {
    items = await api("/api/users/lookup", { params: { q: token } }).catch(() => []);
    selected = 0;
    draw();
  }, 200);

  textarea.addEventListener("input", () => {
    const token = currentToken();
    if (token) lookup(token);
    else list.hidden = true;
  });
  textarea.addEventListener("keydown", (e) => {
    if (list.hidden || !items.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      selected = (selected + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length;
      draw();
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      choose(items[selected].username);
    } else if (e.key === "Escape") {
      list.hidden = true;
    }
  });
  textarea.addEventListener("blur", () => setTimeout(() => (list.hidden = true), 150));
}

async function renderArticle(m) {
  const d = await api(`/api/documents/${encodeURIComponent(decodeURIComponent(m[1]))}`);
  setTitle(d.seo_title || d.title, d.seo_description || d.summary);
  const loginHref = `#/login?next=${encodeURIComponent(location.hash.slice(1))}`;

  const stars = (current) =>
    [1, 2, 3, 4, 5].map((n) => `<button type="button" data-star="${n}" class="${current && n <= current ? "on" : ""}" aria-label="Rate ${n} of 5" ${state.user ? "" : "disabled"}>★</button>`).join("");

  app.innerHTML = `
    <div class="layout">
      <article class="article">
        ${d.status !== "published" ? `<div class="draft-banner">Draft preview: this article is not visible to readers.</div>` : ""}
        <header>
          ${d.category ? `<a class="kicker" href="#/?category=${d.category.slug}">${esc(d.category.name)}</a>` : ""}
          <h1>${esc(d.title)}</h1>
          <p class="lede">${esc(d.summary)}</p>
          <div class="meta">
            <span>By <a href="#/?author=${esc(d.author_user ? d.author_user.username : "")}">${esc(d.author)}</a></span>
            <span>${fmtDate(d.published_at || d.created_at)}</span>
            <span>👁 ${fmtNum(d.views_count)} views</span>
            <span>💬 ${fmtNum(d.comments_count)} comment${d.comments_count === 1 ? "" : "s"}</span>
          </div>
        </header>
        <div class="article-content">${d.content}</div>
        <div class="chips" style="margin-top:1.5rem">${d.tags.map((t) => `<a class="chip" href="#/?tag=${t.slug}">#${esc(t.name)}</a>`).join("")}</div>

        <div class="engage">
          <button class="btn ${d.my_like ? "active" : ""}" id="like-btn" aria-pressed="${d.my_like}">♥ <span id="like-count">${fmtNum(d.likes_count)}</span></button>
          <div><span class="stars" id="stars">${stars(d.my_rating)}</span>
            <span class="muted small" id="rating-info">${d.rating_avg ? `${d.rating_avg.toFixed(1)} / 5 from ${d.rating_count} rating${d.rating_count === 1 ? "" : "s"}` : "No ratings yet"}</span></div>
          ${state.user ? "" : `<span class="muted small"><a href="${loginHref}">Log in</a> to like, rate and comment.</span>`}
        </div>

        <section id="comments">
          <h2>Comments</h2>
          ${state.user
            ? `<form id="comment-form" class="composer">
                 <label for="comment-text" class="sr-only">Your comment</label>
                 <textarea id="comment-text" maxlength="2000" placeholder="Share your thoughts… Type @ to tag another reader." required></textarea>
                 <div class="actions" style="margin-top:.5rem"><button class="btn btn-primary" type="submit">Post comment</button><span class="muted small">Be respectful. Comments may be reviewed by moderators.</span></div>
               </form>`
            : `<p class="muted"><a href="${loginHref}">Log in</a> to join the discussion.</p>`}
          <div id="comment-list"></div>
          <div id="comment-more"></div>
        </section>
      </article>
      <aside class="sidebar">
        <div class="card panel">
          <h3>About the author</h3>
          <div class="comment-head">${avatar(d.author_user)}<strong>${esc(d.author)}</strong></div>
        </div>
        ${d.related.length ? `<div class="card panel"><h3>Related articles</h3><ul class="cat-list">${d.related.map((r) => `<li><a href="#/article/${encodeURIComponent(r.slug)}">${esc(r.title)}</a></li>`).join("")}</ul></div>` : ""}
      </aside>
    </div>`;

  // likes
  document.getElementById("like-btn").onclick = async (e) => {
    if (!state.user) return go("/login", { next: location.hash.slice(1) });
    try {
      const res = await api(`/api/documents/${d.id}/like`, { method: "POST" });
      e.currentTarget.classList.toggle("active", res.liked);
      e.currentTarget.setAttribute("aria-pressed", res.liked);
      document.getElementById("like-count").textContent = fmtNum(res.likes_count);
    } catch (err) {
      toast(err.message, true);
    }
  };

  // ratings (event delegation, so re-rendering the stars keeps working)
  document.getElementById("stars").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-star]");
    if (!btn || !state.user) return;
    try {
      const res = await api(`/api/documents/${d.id}/rating`, { method: "PUT", body: { score: Number(btn.dataset.star) } });
      document.getElementById("stars").innerHTML = stars(res.my_rating);
      document.getElementById("rating-info").textContent =
        `${res.rating_avg.toFixed(1)} / 5 from ${res.rating_count} rating${res.rating_count === 1 ? "" : "s"}`;
      toast("Thanks for rating!");
    } catch (err) {
      toast(err.message, true);
    }
  });

  // comments
  const listEl = document.getElementById("comment-list");
  const moreEl = document.getElementById("comment-more");
  let commentPage = 0;
  const loadComments = async () => {
    commentPage += 1;
    const res = await api(`/api/documents/${d.id}/comments`, { params: { page: commentPage, size: 10 } });
    if (commentPage === 1 && !res.items.length) listEl.innerHTML = `<p class="muted" data-empty>No comments yet. Start the conversation!</p>`;
    listEl.insertAdjacentHTML("beforeend", res.items.map(commentHtml).join(""));
    moreEl.innerHTML = res.page < res.pages ? `<button class="btn" id="more-comments">Load more comments</button>` : "";
    const more = document.getElementById("more-comments");
    if (more) more.onclick = loadComments;
  };
  await loadComments();

  listEl.addEventListener("click", async (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.delete) {
      if (!confirm("Delete this comment?")) return;
      try {
        await api(`/api/comments/${t.dataset.delete}`, { method: "DELETE" });
        document.getElementById(`comment-${t.dataset.delete}`).remove();
        toast("Comment deleted.");
      } catch (err) {
        toast(err.message, true);
      }
    } else if (t.dataset.hide) {
      try {
        await api(`/api/admin/comments/${t.dataset.hide}`, { method: "PATCH", body: { status: "hidden" } });
        document.getElementById(`comment-${t.dataset.hide}`).remove();
        toast("Comment hidden.");
      } catch (err) {
        toast(err.message, true);
      }
    } else if (t.dataset.report) {
      modal({
        title: "Report comment",
        submitLabel: "Send report",
        body: `<div class="field"><label for="report-reason">Why are you reporting this comment?</label>
               <select id="report-reason" name="reason">
                 <option>Spam or advertising</option><option>Harassment or hate speech</option>
                 <option>Off-topic</option><option>Misinformation</option><option>Other</option>
               </select></div>
               <div class="field"><label for="report-detail">Details <span class="hint">(optional)</span></label><textarea id="report-detail" name="detail" maxlength="400"></textarea></div>`,
        onSubmit: async (form) => {
          const reason = [form.reason.value, form.detail.value.trim()].filter(Boolean).join(": ");
          await api(`/api/comments/${t.dataset.report}/report`, { method: "POST", body: { reason } });
          toast("Thanks — a moderator will review this comment.");
        },
      });
    }
  });

  const form = document.getElementById("comment-form");
  if (form) {
    const textarea = document.getElementById("comment-text");
    setupMentionAutocomplete(textarea);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const content = textarea.value.trim();
      if (!content) return;
      const btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      try {
        const c = await api(`/api/documents/${d.id}/comments`, { method: "POST", body: { content } });
        textarea.value = "";
        listEl.querySelector("[data-empty]")?.remove();
        if (c.status === "spam") toast("Your comment was flagged by the spam filter and is hidden.", true);
        else {
          listEl.insertAdjacentHTML("afterbegin", commentHtml(c));
          toast(c.status === "pending" ? "Comment submitted for review." : "Comment posted.");
        }
      } catch (err) {
        toast(err.message, true);
      } finally {
        btn.disabled = false;
      }
    });
  }
}

// ---------------------------------------------------------------- auth

function nextTarget(query) {
  const next = query.get("next");
  return next && next.startsWith("/") && !next.startsWith("/login") && !next.startsWith("/register") ? next : "/";
}

async function renderLogin(_m, query) {
  setTitle("Log in");
  if (state.user) return go(nextTarget(query));
  app.innerHTML = `
    <div class="card auth-box">
      <h1>Welcome back</h1>
      <form id="login-form">
        <div class="field"><label for="login">Username or email</label><input id="login" name="login" required autocomplete="username"></div>
        <div class="field"><label for="password">Password</label><input id="password" name="password" type="password" required autocomplete="current-password"></div>
        <p class="error-text" id="login-error" hidden></p>
        <button class="btn btn-primary" type="submit" style="width:100%;justify-content:center">Log in</button>
      </form>
      <p class="muted small">No account? <a href="#/register">Register</a></p>
      <details class="demo-accounts">
        <summary>Demo accounts</summary>
        <table class="data">
          <tr><th>Role</th><th>Username</th><th>Password</th></tr>
          <tr><td>Super Admin</td><td>superadmin</td><td>Admin@123</td></tr>
          <tr><td>Content Manager</td><td>editor</td><td>Editor@123</td></tr>
          <tr><td>Moderator</td><td>moderator</td><td>Moderator@123</td></tr>
          <tr><td>Data &amp; SEO</td><td>seo</td><td>Seo@123</td></tr>
          <tr><td>Reader</td><td>alice</td><td>User@123</td></tr>
        </table>
      </details>
    </div>`;
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("login-error");
    err.hidden = true;
    try {
      const data = Object.fromEntries(new FormData(e.target));
      setSession(await api("/api/auth/login", { method: "POST", body: data }));
      toast(`Welcome, ${displayName(state.user)}!`);
      refreshUnread();
      go(nextTarget(query));
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  });
}

async function renderRegister(_m, query) {
  setTitle("Register");
  if (state.user) return go("/");
  if (state.settings.allow_registration === false) {
    app.innerHTML = `<div class="card auth-box"><h1>Registration closed</h1><p class="muted">New sign-ups are currently disabled by the site administrator.</p></div>`;
    return;
  }
  app.innerHTML = `
    <div class="card auth-box">
      <h1>Create an account</h1>
      <form id="register-form">
        <div class="field"><label for="r-username">Username <span class="hint">3–32 letters, numbers or _</span></label><input id="r-username" name="username" required pattern="[A-Za-z0-9_]{3,32}" autocomplete="username"></div>
        <div class="field"><label for="r-name">Full name</label><input id="r-name" name="full_name" maxlength="120" autocomplete="name"></div>
        <div class="field"><label for="r-email">Email</label><input id="r-email" name="email" type="email" required autocomplete="email"></div>
        <div class="field"><label for="r-password">Password <span class="hint">at least 6 characters</span></label><input id="r-password" name="password" type="password" minlength="6" required autocomplete="new-password"></div>
        <p class="error-text" id="register-error" hidden></p>
        <button class="btn btn-primary" type="submit" style="width:100%;justify-content:center">Create account</button>
      </form>
      <p class="muted small">Already registered? <a href="#/login">Log in</a></p>
    </div>`;
  document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("register-error");
    err.hidden = true;
    try {
      const data = Object.fromEntries(new FormData(e.target));
      setSession(await api("/api/auth/register", { method: "POST", body: data }));
      toast("Account created. Welcome!");
      go(nextTarget(query));
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  });
}

// ---------------------------------------------------------------- profile

async function renderProfile(m) {
  if (!state.user) return go("/login", { next: "/profile" });
  const tab = m[1] || "profile";
  const u = state.user;
  setTitle("My profile");
  const tabs = [["profile", "Profile"], ["password", "Password"], ["mentions", `Mentions${state.unread ? ` <span class="badge">${state.unread}</span>` : ""}`], ["comments", "My comments"]];
  app.innerHTML = `
    <div class="profile-head">${avatar(u, "lg")}<div><h1 style="margin:0">${esc(displayName(u))}</h1>
      <span class="muted">@${esc(u.username)} · joined ${fmtDate(u.created_at)} · <span class="pill">${esc(u.role.replace("_", " "))}</span></span></div></div>
    <nav class="tabs">${tabs.map(([k, label]) => `<a href="#/profile/${k}" class="${k === tab ? "active" : ""}">${label}</a>`).join("")}</nav>
    <div id="tab-body" class="card panel"></div>`;
  const body = document.getElementById("tab-body");

  if (tab === "profile") {
    body.innerHTML = `<form id="profile-form" style="max-width:560px">
        <div class="field"><label for="p-name">Full name</label><input id="p-name" name="full_name" value="${esc(u.full_name)}" maxlength="120"></div>
        <div class="field"><label for="p-email">Email</label><input id="p-email" name="email" type="email" value="${esc(u.email)}" required></div>
        <div class="field"><label for="p-avatar">Avatar URL <span class="hint">optional, https://…</span></label><input id="p-avatar" name="avatar_url" value="${esc(u.avatar_url)}"></div>
        <div class="field"><label for="p-bio">Bio</label><textarea id="p-bio" name="bio" maxlength="1000">${esc(u.bio)}</textarea></div>
        <button class="btn btn-primary" type="submit">Save changes</button>
      </form>`;
    document.getElementById("profile-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const res = await api("/api/auth/me", { method: "PUT", body: Object.fromEntries(new FormData(e.target)) });
        state.user = res.user;
        toast("Profile updated.");
        renderProfile(m);
      } catch (err) {
        toast(err.message, true);
      }
    });
  } else if (tab === "password") {
    body.innerHTML = `<form id="pw-form" style="max-width:420px">
        <div class="field"><label for="pw-current">Current password</label><input id="pw-current" name="current_password" type="password" required autocomplete="current-password"></div>
        <div class="field"><label for="pw-new">New password</label><input id="pw-new" name="new_password" type="password" minlength="6" required autocomplete="new-password"></div>
        <button class="btn btn-primary" type="submit">Change password</button>
      </form>`;
    document.getElementById("pw-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/auth/me/password", { method: "PUT", body: Object.fromEntries(new FormData(e.target)) });
        e.target.reset();
        toast("Password changed.");
      } catch (err) {
        toast(err.message, true);
      }
    });
  } else if (tab === "mentions") {
    const res = await api("/api/me/mentions", { params: { size: 50 } });
    body.innerHTML = res.items.length
      ? res.items.map((x) => `<div class="comment">
          <div class="comment-head">${avatar(x.by)}<strong>${esc(displayName(x.by))}</strong>
            <span class="muted">mentioned you on <a href="#/article/${encodeURIComponent(x.document.slug)}">${esc(x.document.title)}</a> · ${fmtDate(x.created_at, true)}</span>
            ${x.is_read ? "" : `<span class="pill open">new</span>`}</div>
          <p class="comment-body">${renderCommentText(x.comment)}</p></div>`).join("")
      : `<p class="muted">Nobody has mentioned you yet. Readers can tag you in comments with @${esc(u.username)}.</p>`;
    if (res.unread) {
      await api("/api/me/mentions/read", { method: "POST" });
      state.unread = 0;
      renderNav();
    }
  } else if (tab === "comments") {
    const res = await api("/api/me/comments", { params: { size: 50 } });
    body.innerHTML = res.items.length
      ? res.items.map((c) => `<div class="comment"><div class="comment-head">
            <span class="muted">On <a href="#/article/${encodeURIComponent(c.document.slug)}">${esc(c.document.title)}</a> · ${fmtDate(c.created_at, true)}</span>
            <span class="pill ${c.status}">${esc(c.status)}</span></div>
            <p class="comment-body">${renderCommentText(c.content)}</p></div>`).join("")
      : `<p class="muted">You have not written any comments yet.</p>`;
  }
}

// ---------------------------------------------------------------- boot

document.getElementById("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  go("/", { q: document.getElementById("search-input").value.trim() });
});
document.getElementById("menu-toggle").addEventListener("click", (e) => {
  const nav = document.getElementById("main-nav");
  nav.classList.toggle("open");
  e.currentTarget.setAttribute("aria-expanded", nav.classList.contains("open"));
});

async function boot() {
  const [settings] = await Promise.all([api("/api/settings/public").catch(() => ({})), loadSession()]);
  state.settings = settings;
  document.getElementById("brand").textContent = settings.site_name || "Lumen Magazine";
  document.getElementById("footer-name").textContent = settings.site_name || "Lumen Magazine";
  document.getElementById("footer-tagline").textContent = settings.site_tagline || "";
  const banner = document.getElementById("announcement");
  banner.textContent = settings.announcement || "";
  banner.hidden = !settings.announcement;
  window.addEventListener("hashchange", router);
  await router();
  refreshUnread();
}

boot();
