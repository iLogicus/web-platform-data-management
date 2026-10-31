// Admin dashboard. Every tab is gated by an RBAC permission (the API enforces the same rules).
import {
  api, bindPagination, can, confirmAction, downloadFile, esc, fmtDate, fmtNum, go,
  modal, pagination, state, toast,
} from "./core.js";

const ROLE_LABELS = {
  super_admin: "Super Admin",
  content_manager: "Content Manager",
  moderator: "Moderator",
  seo_specialist: "Data & SEO Specialist",
  user: "Registered User",
};

const TABS = [
  { key: "dashboard", label: "Analytics", perm: "analytics.view", render: renderDashboard },
  { key: "content", label: "Articles", perm: "content.manage", render: renderContent },
  { key: "taxonomy", label: "Categories & tags", perm: "taxonomy.manage", render: renderTaxonomy },
  { key: "comments", label: "Comments", perm: "comments.moderate", render: renderComments },
  { key: "reports", label: "Reports", perm: "reports.handle", render: renderReports },
  { key: "spam", label: "Spam control", perm: "spam.manage", render: renderSpam },
  { key: "seo", label: "SEO metadata", perm: "seo.manage", render: renderSeo },
  { key: "search-logs", label: "Search logs", perm: "analytics.view", render: renderSearchLogs },
  { key: "users", label: "Users & roles", perm: "users.manage", render: renderUsers },
  { key: "permissions", label: "Permissions", perm: "users.manage", render: renderPermissions },
  { key: "settings", label: "Global settings", perm: "settings.manage", render: renderSettings },
  { key: "logs", label: "System logs", perm: "logs.view", render: renderLogs },
];

export async function renderAdmin(app, tabKey) {
  if (!state.user) return go("/login", { next: "/admin" });
  const tabs = TABS.filter((t) => can(t.perm));
  if (!tabs.length) {
    app.innerHTML = `<div class="card empty"><h2>Access denied</h2><p>Your account (${esc(ROLE_LABELS[state.user.role])}) has no administrative permissions.</p></div>`;
    return;
  }
  const tab = tabs.find((t) => t.key === tabKey) || tabs[0];
  document.title = `${tab.label} · Dashboard`;
  app.innerHTML = `
    <div class="admin">
      <nav class="card admin-nav" aria-label="Dashboard sections">
        <div class="role">Signed in as <strong>@${esc(state.user.username)}</strong><br>${esc(ROLE_LABELS[state.user.role])}</div>
        ${tabs.map((t) => `<a href="#/admin/${t.key}" class="${t === tab ? "active" : ""}">${t.label}</a>`).join("")}
      </nav>
      <div class="admin-main" id="admin-main"></div>
    </div>`;
  await tab.render(document.getElementById("admin-main"));
}

const pill = (value, label) => `<span class="pill ${esc(value)}">${esc(label || value)}</span>`;
const fail = (err) => toast(err.message, true);
const val = (form, name) => form.elements[name].value.trim();

// ================================================================ analytics

function barChart(points, unit) {
  const W = 640, H = 200, padL = 44, padB = 24, padT = 8;
  const max = Math.max(1, ...points.map((p) => p.count));
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  const niceMax = Math.ceil(max / step) * step;
  const plotW = W - padL, plotH = H - padB - padT;
  const slot = plotW / points.length;
  const barW = Math.max(2, slot - 2); // 2px gap between adjacent bars
  const ticks = [0, niceMax / 2, niceMax];
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Bar chart of ${unit} per day">`;
  for (const t of ticks) {
    const y = padT + plotH - (t / niceMax) * plotH;
    svg += `<line class="gridline" x1="${padL}" x2="${W}" y1="${y}" y2="${y}"/>`;
    svg += `<text class="axis-label" x="${padL - 6}" y="${y + 3}" text-anchor="end">${fmtNum(t)}</text>`;
  }
  const labelEvery = Math.ceil(points.length / 8);
  points.forEach((p, i) => {
    const h = (p.count / niceMax) * plotH;
    const x = padL + i * slot + 1;
    const y = padT + plotH - h;
    const r = Math.min(4, barW / 2, h);
    if (h > 0) {
      // bar anchored to the baseline, rounded only at the data end
      svg += `<path class="bar" d="M${x},${padT + plotH} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${padT + plotH} Z"/>`;
    }
    const label = new Date(`${p.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    svg += `<rect x="${padL + i * slot}" y="${padT}" width="${slot}" height="${plotH}" fill="transparent" data-tip="${esc(label)}: ${fmtNum(p.count)} ${unit}"/>`;
    if (i % labelEvery === 0) svg += `<text class="axis-label" x="${x + barW / 2}" y="${H - 6}" text-anchor="middle">${esc(label)}</text>`;
  });
  return `<div class="chart" style="position:relative">${svg}</svg><div class="chart-tip" hidden></div></div>`;
}

function bindChartTips(root) {
  root.querySelectorAll(".chart").forEach((chart) => {
    const tip = chart.querySelector(".chart-tip");
    Object.assign(tip.style, {
      position: "absolute", pointerEvents: "none", background: "var(--ink)", color: "#fff",
      padding: ".25rem .5rem", borderRadius: "6px", fontSize: ".8rem", whiteSpace: "nowrap",
    });
    chart.querySelectorAll("[data-tip]").forEach((hit) => {
      hit.addEventListener("mouseenter", () => {
        tip.textContent = hit.dataset.tip;
        tip.hidden = false;
      });
      hit.addEventListener("mousemove", (e) => {
        const box = chart.getBoundingClientRect();
        tip.style.left = `${Math.min(e.clientX - box.left + 10, box.width - 140)}px`;
        tip.style.top = `${e.clientY - box.top - 30}px`;
      });
      hit.addEventListener("mouseleave", () => (tip.hidden = true));
    });
  });
}

async function renderDashboard(main) {
  const a = await api("/api/admin/analytics", { params: { days: 14 } });
  const t = a.totals;
  const kpi = (label, value) => `<div class="card kpi"><div class="label">${label}</div><div class="value">${value}</div></div>`;
  const maxCat = Math.max(1, ...a.category_views.map((c) => c.views));
  main.innerHTML = `
    <h1>Analytics</h1>
    <div class="kpis">
      ${kpi("Published", fmtNum(t.published))}${kpi("Drafts", fmtNum(t.drafts))}${kpi("Total views", fmtNum(t.views))}
      ${kpi("Users", fmtNum(t.users))}${kpi("Comments", fmtNum(t.comments))}${kpi("Likes", fmtNum(t.likes))}
      ${kpi("Searches", fmtNum(t.searches))}${kpi("Search CTR", `${(t.ctr * 100).toFixed(1)}%`)}
    </div>
    <div class="chart-grid">
      <div class="card chart-card"><h3>Article views per day</h3><div class="sub">Last 14 days</div>${barChart(a.views_per_day, "views")}</div>
      <div class="card chart-card"><h3>Searches per day</h3><div class="sub">Last 14 days</div>${barChart(a.searches_per_day, "searches")}</div>
    </div>
    <div class="chart-grid">
      <div class="card chart-card"><h3>Views by category</h3><div class="sub">All-time views of published articles</div>
        ${a.category_views.map((c) => `<div class="hbar-row" title="${esc(c.category)}: ${fmtNum(c.views)} views across ${c.documents} articles">
            <span>${esc(c.category)}</span><div class="hbar-track"><div class="hbar-fill" style="width:${(c.views / maxCat) * 100}%"></div></div><span class="num">${fmtNum(c.views)}</span></div>`).join("")}
      </div>
      <div class="card chart-card"><h3>Most viewed articles</h3><div class="sub">Top 10</div>
        <div class="table-wrap"><table class="data"><thead><tr><th>Article</th><th class="num">Views</th><th class="num">Likes</th></tr></thead><tbody>
        ${a.top_documents.map((d) => `<tr><td><a href="#/article/${encodeURIComponent(d.slug)}">${esc(d.title)}</a></td><td class="num">${fmtNum(d.views_count)}</td><td class="num">${fmtNum(d.likes_count)}</td></tr>`).join("")}
        </tbody></table></div>
      </div>
    </div>
    <div class="chart-grid">
      <div class="card chart-card"><h3>Top search queries</h3><div class="sub">Searches, clicks and click-through rate</div>
        <div class="table-wrap"><table class="data"><thead><tr><th>Query</th><th class="num">Searches</th><th class="num">Clicks</th><th class="num">CTR</th></tr></thead><tbody>
        ${a.top_queries.map((q) => `<tr><td><a href="#/?q=${encodeURIComponent(q.query)}">${esc(q.query)}</a></td><td class="num">${q.searches}</td><td class="num">${q.clicks}</td><td class="num">${q.searches ? ((q.clicks / q.searches) * 100).toFixed(0) : 0}%</td></tr>`).join("")}
        </tbody></table></div>
      </div>
      <div class="card chart-card"><h3>Queries with no results</h3><div class="sub">Content gaps worth covering</div>
        ${a.zero_result_queries.length
          ? `<div class="table-wrap"><table class="data"><thead><tr><th>Query</th><th class="num">Searches</th></tr></thead><tbody>
             ${a.zero_result_queries.map((q) => `<tr><td>${esc(q.query)}</td><td class="num">${q.searches}</td></tr>`).join("")}</tbody></table></div>`
          : `<p class="muted">Every query returned at least one result.</p>`}
      </div>
    </div>`;
  bindChartTips(main);
}

async function renderSearchLogs(main) {
  let page = 1, eventType = "";
  main.innerHTML = `
    <h1>Search &amp; click logs</h1>
    <p class="muted">Raw interaction log (user_id, query_string, clicked_doc_id, timestamp) collected for the Phase 2 ranking engine.</p>
    <div class="card">
      <div class="toolbar">
        <select id="sl-type"><option value="">All events</option><option value="search">Searches</option><option value="click">Clicks</option></select>
        <span class="spacer"></span>
        <button class="btn" id="exp-docs">Export documents.jsonl</button>
        <button class="btn" id="exp-logs">Export search_logs.csv</button>
      </div>
      <div id="sl-body"></div>
    </div>`;
  const body = main.querySelector("#sl-body");
  const load = async () => {
    const res = await api("/api/admin/search-logs", { params: { page, size: 50, event_type: eventType } });
    body.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr>
        <th>Time</th><th>Event</th><th>Query</th><th class="num">Results</th><th class="num">Clicked doc</th><th class="num">Position</th><th>User</th><th>Session</th></tr></thead><tbody>
        ${res.items.map((l) => `<tr><td>${fmtDate(l.timestamp, true)}</td><td>${pill(l.event_type === "click" ? "published" : "draft", l.event_type)}</td>
          <td>${esc(l.query_string)}</td><td class="num">${l.results_count ?? ""}</td>
          <td class="num">${l.clicked_doc_id ? `<a href="#/article/${l.clicked_doc_id}">#${l.clicked_doc_id}</a>` : ""}</td>
          <td class="num">${l.position ?? ""}</td><td>${l.user_id ?? "anon"}</td><td class="muted small">${esc((l.session_id || "").slice(0, 12))}</td></tr>`).join("")}
        </tbody></table></div>${pagination(res)}<p class="muted small">${fmtNum(res.total)} events</p>`;
    bindPagination(body, (p) => { page = p; load(); });
  };
  main.querySelector("#sl-type").onchange = (e) => { eventType = e.target.value; page = 1; load(); };
  main.querySelector("#exp-docs").onclick = () => downloadFile("/api/admin/export/documents.jsonl", "documents.jsonl").catch(fail);
  main.querySelector("#exp-logs").onclick = () => downloadFile("/api/admin/export/search_logs.csv", "search_logs.csv").catch(fail);
  await load();
}

// ================================================================ content

async function renderContent(main) {
  let page = 1;
  const filters = { q: "", status: "", category_id: "" };
  const categories = await api("/api/admin/categories");
  main.innerHTML = `
    <h1>Articles</h1>
    <div class="card">
      <div class="toolbar">
        <input type="search" id="c-q" placeholder="Search title or summary…">
        <select id="c-status"><option value="">Any status</option><option value="published">Published</option><option value="draft">Draft</option></select>
        <select id="c-cat"><option value="">Any category</option>${categories.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select>
        <span class="spacer"></span>
        <button class="btn btn-primary" id="c-new">+ New article</button>
      </div>
      <div id="c-body"></div>
    </div>`;
  const body = main.querySelector("#c-body");

  const load = async () => {
    const res = await api("/api/admin/documents", { params: { ...filters, page, size: 15 } });
    body.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr>
      <th>Title</th><th>Category</th><th>Status</th><th>Author</th><th>Updated</th><th class="num">Views</th><th>Actions</th></tr></thead><tbody>
      ${res.items.map((d) => `<tr>
        <td class="clip"><a href="#/article/${encodeURIComponent(d.slug)}">${esc(d.title)}</a></td>
        <td>${esc(d.category ? d.category.name : "—")}</td>
        <td>${pill(d.status)}</td><td>${esc(d.author)}</td><td>${fmtDate(d.updated_at)}</td><td class="num">${fmtNum(d.views_count)}</td>
        <td><div class="actions">
          <button class="btn btn-sm" data-edit="${d.id}">Edit</button>
          ${can("content.publish") ? `<button class="btn btn-sm" data-status="${d.id}" data-to="${d.status === "published" ? "draft" : "published"}">${d.status === "published" ? "Unpublish" : "Publish"}</button>` : ""}
          <button class="btn btn-sm btn-danger" data-del="${d.id}" data-title="${esc(d.title)}">Delete</button>
        </div></td></tr>`).join("") || `<tr><td colspan="7" class="muted">No articles match.</td></tr>`}
      </tbody></table></div>${pagination(res)}<p class="muted small">${fmtNum(res.total)} articles</p>`;
    bindPagination(body, (p) => { page = p; load(); });
  };

  body.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.edit) openEditor(Number(b.dataset.edit));
    if (b.dataset.status) {
      try {
        await api(`/api/admin/documents/${b.dataset.status}/status`, { method: "PATCH", body: { status: b.dataset.to } });
        toast(b.dataset.to === "published" ? "Article published." : "Article unpublished.");
        load();
      } catch (err) { fail(err); }
    }
    if (b.dataset.del) {
      confirmAction(`Delete “${b.dataset.title}”? This also removes its comments, likes and ratings.`, async () => {
        await api(`/api/admin/documents/${b.dataset.del}`, { method: "DELETE" });
        toast("Article deleted.");
        load();
      }, "Delete");
    }
  });

  const openEditor = async (id) => {
    const d = id ? await api(`/api/admin/documents/${id}`) : { title: "", summary: "", content: "", tags: [], status: "draft", image_url: "", image_alt: "", category_id: null };
    modal({
      title: id ? "Edit article" : "New article",
      wide: true,
      submitLabel: id ? "Save changes" : "Create article",
      body: `
        <div class="field"><label for="e-title">Title</label><input id="e-title" name="title" required minlength="3" maxlength="300" value="${esc(d.title)}"></div>
        <div class="field"><label for="e-summary">Summary <span class="hint">leave empty to generate from the content</span></label><textarea id="e-summary" name="summary" maxlength="1000" rows="2">${esc(d.summary)}</textarea></div>
        <div class="field"><label for="e-content">Content <span class="hint">HTML allowed: p, h2, h3, strong, em, a, ul/ol, blockquote, img, figure. Scripts are stripped.</span></label>
          <textarea id="e-content" name="content" rows="14" required style="font-family:ui-monospace,Consolas,monospace;font-size:.85rem">${esc(d.content)}</textarea></div>
        <div class="form-row">
          <div class="field"><label for="e-cat">Category</label><select id="e-cat" name="category_id"><option value="">— None —</option>
            ${categories.map((c) => `<option value="${c.id}" ${c.id === d.category_id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
          <div class="field"><label for="e-status">Status</label><select id="e-status" name="status">
            <option value="draft" ${d.status === "draft" ? "selected" : ""}>Draft</option>
            <option value="published" ${d.status === "published" ? "selected" : ""} ${can("content.publish") ? "" : "disabled"}>Published</option></select></div>
        </div>
        <div class="field"><label for="e-tags">Tags <span class="hint">comma separated; new tags are created automatically</span></label><input id="e-tags" name="tags" value="${esc(d.tags.map((t) => t.name).join(", "))}"></div>
        <div class="form-row">
          <div class="field"><label for="e-img">Image URL</label><input id="e-img" name="image_url" value="${esc(d.image_url)}"></div>
          <div class="field"><label for="e-alt">Image alt text</label><input id="e-alt" name="image_alt" value="${esc(d.image_alt)}"></div>
        </div>`,
      onSubmit: async (form) => {
        const payload = {
          title: val(form, "title"),
          summary: val(form, "summary"),
          content: form.elements.content.value,
          category_id: form.elements.category_id.value ? Number(form.elements.category_id.value) : null,
          status: form.elements.status.value,
          tags: val(form, "tags").split(",").map((t) => t.trim()).filter(Boolean),
          image_url: val(form, "image_url"),
          image_alt: val(form, "image_alt"),
        };
        await api(id ? `/api/admin/documents/${id}` : "/api/admin/documents", { method: id ? "PUT" : "POST", body: payload });
        toast(id ? "Article saved." : "Article created.");
        load();
      },
    });
  };

  const reload = () => { page = 1; load(); };
  main.querySelector("#c-q").addEventListener("change", (e) => { filters.q = e.target.value.trim(); reload(); });
  main.querySelector("#c-status").onchange = (e) => { filters.status = e.target.value; reload(); };
  main.querySelector("#c-cat").onchange = (e) => { filters.category_id = e.target.value; reload(); };
  main.querySelector("#c-new").onclick = () => openEditor(null);
  await load();
}

async function renderTaxonomy(main) {
  main.innerHTML = `<h1>Categories &amp; tags</h1><div class="card" id="cat-card"></div><div class="card" id="tag-card"></div>`;

  const loadCategories = async () => {
    const cats = await api("/api/admin/categories");
    const card = main.querySelector("#cat-card");
    card.innerHTML = `<div class="toolbar"><h2 style="margin:0">Categories</h2><span class="spacer"></span><button class="btn btn-primary" id="cat-new">+ New category</button></div>
      <div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Slug</th><th>Description</th><th class="num">Articles</th><th>Actions</th></tr></thead><tbody>
      ${cats.map((c) => `<tr><td><strong>${esc(c.name)}</strong></td><td class="muted">${esc(c.slug)}</td><td class="clip">${esc(c.description)}</td><td class="num">${c.document_count}</td>
        <td><div class="actions"><button class="btn btn-sm" data-edit="${c.id}">Edit</button><button class="btn btn-sm btn-danger" data-del="${c.id}">Delete</button></div></td></tr>`).join("")}
      </tbody></table></div>`;
    const edit = (c) => modal({
      title: c ? "Edit category" : "New category",
      body: `<div class="field"><label for="cat-name">Name</label><input id="cat-name" name="name" required value="${esc(c ? c.name : "")}"></div>
             <div class="field"><label for="cat-desc">Description</label><textarea id="cat-desc" name="description">${esc(c ? c.description : "")}</textarea></div>`,
      onSubmit: async (form) => {
        const payload = { name: val(form, "name"), description: val(form, "description") };
        await api(c ? `/api/admin/categories/${c.id}` : "/api/admin/categories", { method: c ? "PUT" : "POST", body: payload });
        toast("Category saved.");
        loadCategories();
      },
    });
    card.querySelector("#cat-new").onclick = () => edit(null);
    card.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => edit(cats.find((c) => c.id === Number(b.dataset.edit)))));
    card.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => {
      const c = cats.find((x) => x.id === Number(b.dataset.del));
      confirmAction(`Delete category “${c.name}”? Its ${c.document_count} articles will become uncategorised.`, async () => {
        await api(`/api/admin/categories/${c.id}`, { method: "DELETE" });
        toast("Category deleted.");
        loadCategories();
      }, "Delete");
    }));
  };

  const loadTags = async (q = "") => {
    const tags = await api("/api/admin/tags", { params: { q } });
    const card = main.querySelector("#tag-card");
    card.innerHTML = `<div class="toolbar"><h2 style="margin:0">Tags</h2><input type="search" id="tag-q" placeholder="Filter tags…" value="${esc(q)}">
        <span class="spacer"></span><form id="tag-form" class="actions"><input name="name" placeholder="New tag name" required maxlength="60"><button class="btn btn-primary">Add tag</button></form></div>
      <div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Slug</th><th class="num">Articles</th><th>Actions</th></tr></thead><tbody>
      ${tags.map((t) => `<tr><td>${esc(t.name)}</td><td class="muted">${esc(t.slug)}</td><td class="num">${t.document_count}</td>
        <td><div class="actions"><button class="btn btn-sm" data-ren="${t.id}" data-name="${esc(t.name)}">Rename</button><button class="btn btn-sm btn-danger" data-del="${t.id}" data-name="${esc(t.name)}">Delete</button></div></td></tr>`).join("")}
      </tbody></table></div><p class="muted small">${tags.length} tags</p>`;
    card.querySelector("#tag-q").addEventListener("change", (e) => loadTags(e.target.value.trim()));
    card.querySelector("#tag-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/admin/tags", { method: "POST", body: { name: e.target.name.value.trim() } });
        toast("Tag created.");
        loadTags(q);
      } catch (err) { fail(err); }
    });
    card.querySelectorAll("[data-ren]").forEach((b) => (b.onclick = () => modal({
      title: "Rename tag",
      body: `<div class="field"><label for="tag-name">Name</label><input id="tag-name" name="name" required value="${esc(b.dataset.name)}"></div>`,
      onSubmit: async (form) => {
        await api(`/api/admin/tags/${b.dataset.ren}`, { method: "PUT", body: { name: val(form, "name") } });
        toast("Tag renamed.");
        loadTags(q);
      },
    })));
    card.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () =>
      confirmAction(`Delete tag “${b.dataset.name}”? It will be removed from all articles.`, async () => {
        await api(`/api/admin/tags/${b.dataset.del}`, { method: "DELETE" });
        toast("Tag deleted.");
        loadTags(q);
      }, "Delete")));
  };

  await Promise.all([loadCategories(), loadTags()]);
}

// ================================================================ moderation

async function renderComments(main) {
  let page = 1, status = "", q = "";
  main.innerHTML = `<h1>Comment moderation</h1><div class="card"><div class="toolbar" id="cm-filters"></div><div id="cm-body"></div></div>`;
  const body = main.querySelector("#cm-body");
  const load = async () => {
    const res = await api("/api/admin/comments", { params: { page, size: 20, status, q } });
    const counts = res.status_counts;
    const filterBtn = (value, label) => `<button class="btn btn-sm ${status === value ? "active" : ""}" data-filter="${value}">${label}${value ? ` (${counts[value] || 0})` : ""}</button>`;
    main.querySelector("#cm-filters").innerHTML = `${filterBtn("", "All")}${filterBtn("pending", "Pending")}${filterBtn("visible", "Visible")}${filterBtn("spam", "Spam")}${filterBtn("hidden", "Hidden")}
      <span class="spacer"></span><input type="search" id="cm-q" placeholder="Search comment text…" value="${esc(q)}">`;
    main.querySelectorAll("[data-filter]").forEach((b) => (b.onclick = () => { status = b.dataset.filter; page = 1; load(); }));
    main.querySelector("#cm-q").onchange = (e) => { q = e.target.value.trim(); page = 1; load(); };

    const action = (c, to, label) => (c.status === to ? "" : `<button class="btn btn-sm" data-id="${c.id}" data-to="${to}">${label}</button>`);
    body.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th>Comment</th><th>Author</th><th>Article</th><th>Date</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      ${res.items.map((c) => `<tr>
        <td style="max-width:340px">${esc(c.content)}</td>
        <td>@${esc(c.user ? c.user.username : "?")}</td>
        <td class="clip"><a href="#/article/${encodeURIComponent(c.document.slug)}">${esc(c.document.title)}</a></td>
        <td>${fmtDate(c.created_at, true)}</td><td>${pill(c.status)}</td>
        <td><div class="actions">${action(c, "visible", "Approve")}${action(c, "hidden", "Hide")}${action(c, "spam", "Spam")}
          <button class="btn btn-sm btn-danger" data-del="${c.id}">Delete</button></div></td></tr>`).join("") || `<tr><td colspan="6" class="muted">No comments here.</td></tr>`}
      </tbody></table></div>${pagination(res)}`;
    bindPagination(body, (p) => { page = p; load(); });
  };
  body.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    try {
      if (b.dataset.to) {
        await api(`/api/admin/comments/${b.dataset.id}`, { method: "PATCH", body: { status: b.dataset.to } });
        toast(`Comment marked as ${b.dataset.to}.`);
        load();
      } else if (b.dataset.del) {
        confirmAction("Delete this comment permanently?", async () => {
          await api(`/api/comments/${b.dataset.del}`, { method: "DELETE" });
          toast("Comment deleted.");
          load();
        }, "Delete");
      }
    } catch (err) { fail(err); }
  });
  await load();
}

async function renderReports(main) {
  let page = 1, status = "open";
  main.innerHTML = `<h1>Reports &amp; flags</h1><div class="card"><div class="toolbar" id="rp-filters"></div><div id="rp-body"></div></div>`;
  const body = main.querySelector("#rp-body");
  const load = async () => {
    const res = await api("/api/admin/reports", { params: { page, size: 20, status } });
    main.querySelector("#rp-filters").innerHTML = ["open", "resolved", "dismissed"]
      .map((s) => `<button class="btn btn-sm ${s === status ? "active" : ""}" data-f="${s}">${s[0].toUpperCase() + s.slice(1)}${s === "open" ? ` (${res.open_count})` : ""}</button>`).join("");
    main.querySelectorAll("[data-f]").forEach((b) => (b.onclick = () => { status = b.dataset.f; page = 1; load(); }));
    body.innerHTML = res.items.length
      ? `<div class="table-wrap"><table class="data"><thead><tr><th>Reported comment</th><th>Reason</th><th>Reporter</th><th>Date</th><th>${status === "open" ? "Actions" : "Outcome"}</th></tr></thead><tbody>
        ${res.items.map((r) => `<tr>
          <td style="max-width:320px"><div>${esc(r.comment.content)}</div><div class="muted small">by @${esc(r.comment.user ? r.comment.user.username : "?")} on <a href="#/article/${encodeURIComponent(r.comment.document.slug)}">${esc(r.comment.document.title)}</a> · ${pill(r.comment.status)}</div></td>
          <td>${esc(r.reason)}</td><td>@${esc(r.reporter ? r.reporter.username : "?")}</td><td>${fmtDate(r.created_at, true)}</td>
          <td>${status === "open"
            ? `<div class="actions"><button class="btn btn-sm" data-r="${r.id}" data-s="dismissed" data-a="none">Dismiss</button>
               <button class="btn btn-sm" data-r="${r.id}" data-s="resolved" data-a="hide_comment">Hide comment</button>
               <button class="btn btn-sm" data-r="${r.id}" data-s="resolved" data-a="mute_user">Hide &amp; mute author</button>
               <button class="btn btn-sm btn-danger" data-r="${r.id}" data-s="resolved" data-a="delete_comment">Delete comment</button></div>`
            : `${pill(r.status)} <span class="muted small">by @${esc(r.handled_by ? r.handled_by.username : "?")} ${fmtDate(r.handled_at)}${r.resolution_note ? ` — ${esc(r.resolution_note)}` : ""}</span>`}</td></tr>`).join("")}
        </tbody></table></div>${pagination(res)}`
      : `<p class="muted">No ${status} reports.</p>`;
    bindPagination(body, (p) => { page = p; load(); });
  };
  body.addEventListener("click", (e) => {
    const b = e.target.closest("[data-r]");
    if (!b) return;
    modal({
      title: "Handle report",
      submitLabel: "Confirm",
      body: `<p>Action: <strong>${esc(b.textContent)}</strong></p><div class="field"><label for="rp-note">Note <span class="hint">optional, stored with the report</span></label><input id="rp-note" name="note" maxlength="500"></div>`,
      onSubmit: async (form) => {
        await api(`/api/admin/reports/${b.dataset.r}`, { method: "PATCH", body: { status: b.dataset.s, action: b.dataset.a, note: val(form, "note") } });
        toast("Report handled.");
        load();
      },
    });
  });
  await load();
}

async function renderSpam(main) {
  const [s, muted] = await Promise.all([api("/api/admin/spam/settings"), api("/api/admin/spam/muted-users")]);
  main.innerHTML = `
    <h1>Spam control</h1>
    <div class="card"><form id="spam-form" style="max-width:640px">
      <div class="field"><label for="sp-words">Banned words &amp; phrases <span class="hint">one per line; matching comments go straight to the spam queue</span></label>
        <textarea id="sp-words" name="banned_words" rows="8">${esc(s.banned_words.join("\n"))}</textarea></div>
      <div class="form-row">
        <div class="field"><label for="sp-rate">Max comments per user per minute <span class="hint">0 = unlimited</span></label><input id="sp-rate" name="max" type="number" min="0" max="100" value="${s.max_comments_per_minute}"></div>
        <div class="field"><label><input type="checkbox" name="approval" ${s.comments_require_approval ? "checked" : ""}> Hold all new comments for approval</label></div>
      </div>
      <button class="btn btn-primary">Save spam settings</button>
    </form></div>
    <div class="card"><h2>Muted users</h2>
      ${muted.length ? `<table class="data"><tbody>${muted.map((u) => `<tr><td>@${esc(u.username)}</td><td>${esc(u.full_name)}</td><td><button class="btn btn-sm" data-unmute="${u.id}">Unmute</button></td></tr>`).join("")}</tbody></table>`
        : `<p class="muted">No muted users. Authors can be muted from the Reports queue.</p>`}
    </div>`;
  main.querySelector("#spam-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      await api("/api/admin/spam/settings", {
        method: "PUT",
        body: {
          banned_words: f.banned_words.value.split("\n").map((w) => w.trim()).filter(Boolean),
          max_comments_per_minute: Number(f.max.value),
          comments_require_approval: f.approval.checked,
        },
      });
      toast("Spam settings saved.");
    } catch (err) { fail(err); }
  });
  main.querySelectorAll("[data-unmute]").forEach((b) => (b.onclick = async () => {
    try {
      await api(`/api/admin/users/${b.dataset.unmute}/mute`, { method: "PATCH", body: { muted: false } });
      toast("User unmuted.");
      renderSpam(main);
    } catch (err) { fail(err); }
  }));
}

// ================================================================ SEO

async function renderSeo(main) {
  let page = 1, q = "", missing = false;
  main.innerHTML = `<h1>SEO metadata</h1>
    <div class="card"><div class="toolbar">
      <input type="search" id="seo-q" placeholder="Search titles…">
      <label style="margin:0;font-weight:500"><input type="checkbox" id="seo-missing"> Only incomplete</label>
      <span class="spacer"></span><span class="muted small" id="seo-count"></span></div>
      <div id="seo-body"></div></div>`;
  const body = main.querySelector("#seo-body");
  let items = [];
  const load = async () => {
    const res = await api("/api/admin/seo/documents", { params: { page, size: 15, q, missing_only: missing } });
    items = res.items;
    main.querySelector("#seo-count").textContent = `${res.incomplete_count} articles with incomplete metadata`;
    body.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th>Article</th><th>SEO title</th><th class="num">Desc. length</th><th>Keywords</th><th>Issues</th><th></th></tr></thead><tbody>
      ${items.map((d) => `<tr><td class="clip"><a href="#/article/${encodeURIComponent(d.slug)}">${esc(d.title)}</a><div class="muted small">${esc(d.category || "")} · ${pill(d.status)}</div></td>
        <td class="clip">${esc(d.seo_title) || '<span class="muted">—</span>'}</td><td class="num">${d.seo_description.length}</td>
        <td class="clip">${esc(d.seo_keywords) || '<span class="muted">—</span>'}</td>
        <td>${d.issues.length ? `<ul class="issues">${d.issues.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : pill("published", "OK")}</td>
        <td><button class="btn btn-sm" data-seo="${d.id}">Edit</button></td></tr>`).join("")}
      </tbody></table></div>${pagination(res)}`;
    bindPagination(body, (p) => { page = p; load(); });
  };
  body.addEventListener("click", (e) => {
    const b = e.target.closest("[data-seo]");
    if (!b) return;
    const d = items.find((x) => x.id === Number(b.dataset.seo));
    const dlg = modal({
      title: `SEO: ${d.title}`,
      wide: true,
      body: `
        <div class="field"><label for="s-title">SEO title <span class="hint" id="s-title-n"></span></label><input id="s-title" name="seo_title" maxlength="300" value="${esc(d.seo_title)}" placeholder="${esc(d.title)}"></div>
        <div class="field"><label for="s-desc">Meta description <span class="hint" id="s-desc-n"></span></label><textarea id="s-desc" name="seo_description" rows="3" maxlength="500" placeholder="${esc(d.summary)}">${esc(d.seo_description)}</textarea></div>
        <div class="field"><label for="s-kw">Keywords <span class="hint">comma separated</span></label><input id="s-kw" name="seo_keywords" maxlength="500" value="${esc(d.seo_keywords)}"></div>
        <div class="field"><label for="s-alt">Image alt text</label><input id="s-alt" name="image_alt" maxlength="300" value="${esc(d.image_alt)}"></div>
        <div class="field"><label>Search result preview</label>
          <div class="card panel" style="box-shadow:none"><div id="pv-title" style="color:#1a0dab;font-size:1.1rem"></div>
          <div style="color:#006621;font-size:.85rem">${esc(location.origin)}/#/article/${esc(d.slug)}</div><div id="pv-desc" class="small"></div></div></div>`,
      onSubmit: async (form) => {
        await api(`/api/admin/seo/documents/${d.id}`, {
          method: "PUT",
          body: { seo_title: val(form, "seo_title"), seo_description: val(form, "seo_description"), seo_keywords: val(form, "seo_keywords"), image_alt: val(form, "image_alt") },
        });
        toast("SEO metadata saved.");
        load();
      },
    });
    const f = dlg.querySelector("form");
    const refresh = () => {
      const t = f.seo_title.value || d.title, ds = f.seo_description.value || d.summary;
      dlg.querySelector("#s-title-n").textContent = `${f.seo_title.value.length}/60 recommended`;
      dlg.querySelector("#s-desc-n").textContent = `${f.seo_description.value.length} chars (50–160 recommended)`;
      dlg.querySelector("#pv-title").textContent = t.length > 60 ? `${t.slice(0, 57)}…` : t;
      dlg.querySelector("#pv-desc").textContent = ds.length > 160 ? `${ds.slice(0, 157)}…` : ds;
    };
    f.addEventListener("input", refresh);
    refresh();
  });
  main.querySelector("#seo-q").onchange = (e) => { q = e.target.value.trim(); page = 1; load(); };
  main.querySelector("#seo-missing").onchange = (e) => { missing = e.target.checked; page = 1; load(); };
  await load();
}

// ================================================================ super admin

async function renderUsers(main) {
  let page = 1, q = "", role = "";
  const roleOptions = (current) => Object.entries(ROLE_LABELS).map(([k, v]) => `<option value="${k}" ${k === current ? "selected" : ""}>${v}</option>`).join("");
  main.innerHTML = `<h1>Users &amp; roles</h1>
    <div class="card"><div class="toolbar">
      <input type="search" id="u-q" placeholder="Search username, email, name…">
      <select id="u-role"><option value="">All roles</option>${roleOptions("")}</select>
      <span class="spacer"></span><button class="btn btn-primary" id="u-new">+ New user</button></div>
      <div id="u-body"></div></div>`;
  const body = main.querySelector("#u-body");
  const load = async () => {
    const res = await api("/api/admin/users", { params: { page, size: 20, q, role } });
    body.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th><th>Joined</th><th>Last login</th><th>Actions</th></tr></thead><tbody>
      ${res.items.map((u) => {
        const self = u.id === state.user.id;
        return `<tr><td><strong>@${esc(u.username)}</strong><div class="muted small">${esc(u.full_name)}</div></td><td>${esc(u.email)}</td>
          <td><select data-role="${u.id}" ${self ? "disabled" : ""} aria-label="Role for ${esc(u.username)}">${roleOptions(u.role)}</select></td>
          <td>${pill(u.is_active ? "active" : "inactive", u.is_active ? "active" : "inactive")} ${u.is_muted ? pill("muted") : ""}</td>
          <td>${fmtDate(u.created_at)}</td><td>${fmtDate(u.last_login_at, true)}</td>
          <td><div class="actions">${self ? '<span class="muted small">you</span>' : `
            <button class="btn btn-sm" data-active="${u.id}" data-to="${!u.is_active}">${u.is_active ? "Deactivate" : "Activate"}</button>
            <button class="btn btn-sm" data-pw="${u.id}" data-name="${esc(u.username)}">Reset password</button>
            <button class="btn btn-sm btn-danger" data-del="${u.id}" data-name="${esc(u.username)}">Delete</button>`}</div></td></tr>`;
      }).join("")}
      </tbody></table></div>${pagination(res)}<p class="muted small">${fmtNum(res.total)} users</p>`;
    bindPagination(body, (p) => { page = p; load(); });
    body.querySelectorAll("[data-role]").forEach((sel) => (sel.onchange = async () => {
      try {
        await api(`/api/admin/users/${sel.dataset.role}`, { method: "PATCH", body: { role: sel.value } });
        toast(`Role changed to ${ROLE_LABELS[sel.value]}.`);
      } catch (err) { fail(err); load(); }
    }));
  };
  body.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.active) {
      try {
        await api(`/api/admin/users/${b.dataset.active}`, { method: "PATCH", body: { is_active: b.dataset.to === "true" } });
        toast("Account updated.");
        load();
      } catch (err) { fail(err); }
    } else if (b.dataset.pw) {
      modal({
        title: `Reset password for @${b.dataset.name}`,
        body: `<div class="field"><label for="u-pw">New password</label><input id="u-pw" name="password" type="password" minlength="6" required autocomplete="new-password"></div>`,
        onSubmit: async (form) => {
          await api(`/api/admin/users/${b.dataset.pw}`, { method: "PATCH", body: { password: form.password.value } });
          toast("Password reset.");
        },
      });
    } else if (b.dataset.del) {
      confirmAction(`Delete @${b.dataset.name}? Their comments, likes and ratings are removed too.`, async () => {
        await api(`/api/admin/users/${b.dataset.del}`, { method: "DELETE" });
        toast("User deleted.");
        load();
      }, "Delete");
    }
  });
  main.querySelector("#u-q").onchange = (e) => { q = e.target.value.trim(); page = 1; load(); };
  main.querySelector("#u-role").onchange = (e) => { role = e.target.value; page = 1; load(); };
  main.querySelector("#u-new").onclick = () => modal({
    title: "New user",
    body: `<div class="form-row">
        <div class="field"><label for="n-user">Username</label><input id="n-user" name="username" required pattern="[A-Za-z0-9_]{3,32}"></div>
        <div class="field"><label for="n-name">Full name</label><input id="n-name" name="full_name"></div></div>
      <div class="form-row">
        <div class="field"><label for="n-email">Email</label><input id="n-email" name="email" type="email" required></div>
        <div class="field"><label for="n-pw">Password</label><input id="n-pw" name="password" type="password" minlength="6" required autocomplete="new-password"></div></div>
      <div class="field"><label for="n-role">Role</label><select id="n-role" name="role">${roleOptions("user")}</select></div>`,
    onSubmit: async (form) => {
      const data = Object.fromEntries(new FormData(form));
      await api("/api/admin/users", { method: "POST", body: data });
      toast("User created.");
      load();
    },
  });
  await load();
}

async function renderPermissions(main) {
  const data = await api("/api/admin/permissions");
  const editable = can("permissions.manage");
  const roles = Object.keys(data.roles);
  main.innerHTML = `<h1>Role permissions</h1>
    <p class="muted">Super Admin always holds every permission. ${editable ? "Tick the boxes and save to change what each role can do." : "You can view but not change this matrix."}</p>
    <div class="card"><div class="table-wrap"><table class="data matrix"><thead><tr><th>Permission</th>${roles.map((r) => `<th>${esc(data.roles[r])}</th>`).join("")}</tr></thead><tbody>
      ${Object.entries(data.permissions).map(([perm, desc]) => `<tr><td><code>${esc(perm)}</code><div class="muted small">${esc(desc)}</div></td>
        ${roles.map((r) => `<td><input type="checkbox" data-role="${r}" data-perm="${perm}" aria-label="${esc(perm)} for ${esc(data.roles[r])}"
          ${data.matrix[r].includes(perm) ? "checked" : ""} ${!editable || r === "super_admin" ? "disabled" : ""}></td>`).join("")}</tr>`).join("")}
      </tbody></table></div>
      ${editable ? `<div class="actions" style="margin-top:1rem"><button class="btn btn-primary" id="perm-save">Save permissions</button></div>` : ""}</div>`;
  const save = main.querySelector("#perm-save");
  if (save) {
    save.onclick = async () => {
      try {
        for (const r of roles.filter((x) => x !== "super_admin")) {
          const perms = [...main.querySelectorAll(`input[data-role="${r}"]:checked`)].map((i) => i.dataset.perm);
          await api(`/api/admin/permissions/${r}`, { method: "PUT", body: { permissions: perms } });
        }
        toast("Permissions saved.");
      } catch (err) { fail(err); }
    };
  }
}

async function renderSettings(main) {
  const s = await api("/api/admin/settings");
  main.innerHTML = `<h1>Global settings</h1>
    <div class="card"><form id="set-form" style="max-width:640px">
      <div class="field"><label for="st-name">Site name</label><input id="st-name" name="site_name" required maxlength="100" value="${esc(s.site_name)}"></div>
      <div class="field"><label for="st-tag">Tagline</label><input id="st-tag" name="site_tagline" maxlength="300" value="${esc(s.site_tagline)}"></div>
      <div class="field"><label for="st-ann">Announcement banner <span class="hint">shown at the top of every page; leave empty to hide</span></label><input id="st-ann" name="announcement" maxlength="500" value="${esc(s.announcement)}"></div>
      <div class="field"><label for="st-pp">Articles per page</label><input id="st-pp" name="items_per_page" type="number" min="3" max="50" value="${s.items_per_page}"></div>
      <div class="field"><label><input type="checkbox" name="allow_registration" ${s.allow_registration ? "checked" : ""}> Allow new user registration</label></div>
      <div class="field"><label><input type="checkbox" name="comments_enabled" ${s.comments_enabled ? "checked" : ""}> Enable comments site-wide</label></div>
      <button class="btn btn-primary">Save settings</button>
    </form></div>`;
  main.querySelector("#set-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      const saved = await api("/api/admin/settings", {
        method: "PUT",
        body: {
          site_name: f.site_name.value.trim(),
          site_tagline: f.site_tagline.value.trim(),
          announcement: f.announcement.value.trim(),
          items_per_page: Number(f.items_per_page.value),
          allow_registration: f.allow_registration.checked,
          comments_enabled: f.comments_enabled.checked,
        },
      });
      Object.assign(state.settings, saved);
      document.getElementById("brand").textContent = saved.site_name;
      const banner = document.getElementById("announcement");
      banner.textContent = saved.announcement;
      banner.hidden = !saved.announcement;
      toast("Settings saved.");
    } catch (err) { fail(err); }
  });
}

async function renderLogs(main) {
  let page = 1, action = "", actor = "";
  main.innerHTML = `<h1>System logs</h1>
    <div class="card"><div class="toolbar">
      <select id="lg-action"><option value="">All actions</option>
        ${["auth", "document", "category", "tag", "comment", "report", "spam", "user", "permissions", "settings", "seo"].map((a) => `<option value="${a}">${a}.*</option>`).join("")}</select>
      <input id="lg-actor" placeholder="Actor username"></div>
      <div id="lg-body"></div></div>`;
  const body = main.querySelector("#lg-body");
  const load = async () => {
    const res = await api("/api/admin/logs", { params: { page, size: 50, action, actor } });
    body.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Details</th><th>IP</th></tr></thead><tbody>
      ${res.items.map((l) => `<tr><td>${fmtDate(l.timestamp, true)}</td><td>${l.actor ? `@${esc(l.actor)}` : '<span class="muted">anonymous</span>'}</td>
        <td><code>${esc(l.action)}</code></td><td>${esc(l.entity_type)}${l.entity_id ? ` #${l.entity_id}` : ""}</td>
        <td class="small" style="max-width:340px;word-break:break-word">${esc(l.details)}</td><td class="muted small">${esc(l.ip_address)}</td></tr>`).join("") || `<tr><td colspan="6" class="muted">No log entries.</td></tr>`}
      </tbody></table></div>${pagination(res)}<p class="muted small">${fmtNum(res.total)} entries</p>`;
    bindPagination(body, (p) => { page = p; load(); });
  };
  main.querySelector("#lg-action").onchange = (e) => { action = e.target.value; page = 1; load(); };
  main.querySelector("#lg-actor").onchange = (e) => { actor = e.target.value.trim(); page = 1; load(); };
  await load();
}
