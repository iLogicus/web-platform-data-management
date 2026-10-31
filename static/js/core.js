// Shared state, API client and small DOM helpers.

const TOKEN_KEY = "lumen_token";
const SESSION_KEY = "lumen_session";

export const state = { user: null, permissions: [], settings: {}, unread: 0 };

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export function sessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).slice(0, 64);
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function errorMessage(data, status) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => `${(e.loc || []).slice(1).join(".") || "input"}: ${e.msg}`).join("; ");
  }
  return `Request failed (${status})`;
}

export async function api(path, { method = "GET", body, params, raw = false } = {}) {
  const url = new URL(path, location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  }
  const headers = { "X-Session-Id": sessionId() };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  if (res.status === 401 && token && !path.startsWith("/api/auth/login")) {
    clearSession();
    location.hash = `#/login?next=${encodeURIComponent(location.hash.slice(1))}`;
    throw new ApiError("Your session has expired. Please log in again.", 401);
  }
  if (raw) {
    if (!res.ok) throw new ApiError(`Request failed (${res.status})`, res.status);
    return res;
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status);
  return data;
}

// ---------------------------------------------------------------- session

export function setSession(payload) {
  localStorage.setItem(TOKEN_KEY, payload.access_token);
  state.user = payload.user;
  state.permissions = payload.permissions || [];
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  state.user = null;
  state.permissions = [];
  state.unread = 0;
}

export async function loadSession() {
  if (!localStorage.getItem(TOKEN_KEY)) return;
  try {
    const me = await api("/api/auth/me");
    state.user = me.user;
    state.permissions = me.permissions;
  } catch {
    clearSession();
  }
}

export const can = (perm) => state.permissions.includes(perm);

// ---------------------------------------------------------------- formatting

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

export function fmtDate(iso, withTime = false) {
  if (!iso) return "—";
  const opts = { year: "numeric", month: "short", day: "numeric" };
  if (withTime) Object.assign(opts, { hour: "2-digit", minute: "2-digit" });
  return new Date(iso).toLocaleString(undefined, opts);
}

export const fmtNum = (n) => Number(n || 0).toLocaleString();

export function avatar(user, cls = "") {
  if (!user) return `<span class="avatar ${cls}">?</span>`;
  if (user.avatar_url) return `<img class="avatar ${cls}" src="${esc(user.avatar_url)}" alt="">`;
  const initials = (user.full_name || user.username).split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return `<span class="avatar ${cls}" aria-hidden="true">${esc(initials)}</span>`;
}

export const displayName = (user) => (user ? user.full_name || user.username : "Deleted user");

export function highlight(text, query) {
  const safe = esc(text);
  const terms = (query || "").split(/\s+/).filter((t) => t.length > 1).map((t) => esc(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!terms.length) return safe;
  return safe.replace(new RegExp(`(${terms.join("|")})`, "gi"), "<mark>$1</mark>");
}

// ---------------------------------------------------------------- UI helpers

let toastTimer;
export function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast${isError ? " error" : ""}`;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3500);
}

export function go(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
  const target = `#${path}${qs.toString() ? `?${qs}` : ""}`;
  if (location.hash === target) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = target;
}

export function debounce(fn, ms = 250) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

/** Pagination markup; wire it up with bindPagination(container, onPage). */
export function pagination(meta) {
  if (!meta || meta.pages <= 1) return "";
  const { page, pages } = meta;
  const nums = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages));
  const sorted = [...nums].sort((a, b) => a - b);
  let html = `<nav class="pagination" aria-label="Pagination">`;
  html += `<button class="btn btn-sm" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹ Prev</button>`;
  let prev = 0;
  for (const n of sorted) {
    if (n - prev > 1) html += `<span class="muted">…</span>`;
    html += `<button class="btn btn-sm ${n === page ? "active" : ""}" data-page="${n}" ${n === page ? 'aria-current="page"' : ""}>${n}</button>`;
    prev = n;
  }
  html += `<button class="btn btn-sm" data-page="${page + 1}" ${page >= pages ? "disabled" : ""}>Next ›</button></nav>`;
  return html;
}

export function bindPagination(root, onPage) {
  root.querySelectorAll(".pagination [data-page]").forEach((b) =>
    b.addEventListener("click", () => onPage(Number(b.dataset.page)))
  );
}

/** Opens a modal <dialog>. `onSubmit(form)` may return false (or throw) to keep it open. */
export function modal({ title, body, submitLabel = "Save", onSubmit, wide = false }) {
  const dlg = document.createElement("dialog");
  if (wide) dlg.style.width = "min(980px, 96vw)";
  dlg.innerHTML = `
    <form method="dialog" novalidate>
      <div class="dlg-head"><h3>${esc(title)}</h3><button type="button" class="close-x" aria-label="Close">×</button></div>
      <div class="dlg-body">${body}<p class="error-text" data-error hidden></p></div>
      <div class="dlg-foot">
        <button type="button" class="btn" data-cancel>Cancel</button>
        ${onSubmit ? `<button type="submit" class="btn btn-primary">${esc(submitLabel)}</button>` : ""}
      </div>
    </form>`;
  document.body.appendChild(dlg);
  const close = () => {
    dlg.close();
    dlg.remove();
  };
  dlg.querySelector(".close-x").onclick = close;
  dlg.querySelector("[data-cancel]").onclick = close;
  dlg.addEventListener("cancel", (e) => {
    e.preventDefault();
    close();
  });
  const form = dlg.querySelector("form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!onSubmit) return close();
    const errEl = dlg.querySelector("[data-error]");
    errEl.hidden = true;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const result = await onSubmit(form);
      if (result !== false) close();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
    } finally {
      btn.disabled = false;
    }
  });
  dlg.showModal();
  return dlg;
}

export function confirmAction(message, onConfirm, label = "Confirm") {
  modal({ title: "Please confirm", body: `<p>${esc(message)}</p>`, submitLabel: label, onSubmit: onConfirm });
}

export async function downloadFile(path, filename) {
  const res = await api(path, { raw: true });
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
