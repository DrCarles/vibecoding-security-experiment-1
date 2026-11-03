// Chirp single-page app. No build step: plain ES modules, DOM built with textContent
// only (never innerHTML with user data), so posts can't inject markup.

const MAX_POST = 280;
const MAX_IMAGE_MB = 5;

const $app = document.getElementById("app");
const $nav = document.getElementById("nav");
const $toast = document.getElementById("toast");

let me = null;

// ---------------------------------------------------------------- utilities

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : String(c));
  }
  return el;
}

const FIELD_LABELS = {
  email: "Email",
  username: "Username",
  password: "Password",
  first_name: "First name",
  last_name: "Last name",
  age: "Age",
  address: "Address",
  display_name: "Display name",
  current_password: "Current password",
  new_password: "New password",
  login: "Username or email",
};

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function describeError(data, status) {
  const detail = data?.detail ?? data?.error;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = (e.loc || []).filter((x) => x !== "body").at(-1);
        const msg = String(e.msg || "is invalid").replace(/^Value error, /, "");
        return field ? `${FIELD_LABELS[field] || field}: ${msg}` : msg;
      })
      .join("\n");
  }
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status === 413) return `That file is too large (max ${MAX_IMAGE_MB} MB).`;
  return `Something went wrong (HTTP ${status}).`;
}

async function api(path, { method = "GET", json, form } = {}) {
  const headers = { "X-Requested-With": "fetch", Accept: "application/json" };
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Network error. Check your connection.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, describeError(data, res.status));
  return data;
}

let toastTimer;
function toast(message, kind = "info") {
  $toast.textContent = message;
  $toast.className = `show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($toast.className = ""), 3500);
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
function timeAgo(iso) {
  const date = new Date(iso);
  const secs = Math.round((date.getTime() - Date.now()) / 1000);
  const abs = Math.abs(secs);
  if (abs < 45) return "just now";
  if (abs < 3600) return rtf.format(Math.round(secs / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(secs / 3600), "hour");
  if (abs < 604800) return rtf.format(Math.round(secs / 86400), "day");
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function initials(name) {
  return (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function avatar(user, size = "md") {
  if (user.avatar_url) {
    return h("img", { class: `avatar ${size}`, src: user.avatar_url, alt: "", loading: "lazy" });
  }
  return h("span", { class: `avatar ${size} placeholder`, "aria-hidden": "true" }, initials(user.display_name));
}

function link(href, attrs, ...children) {
  return h("a", { href, "data-link": true, ...attrs }, ...children);
}

function field(label, input, hint) {
  const id = input.id || `f-${Math.random().toString(36).slice(2, 9)}`;
  input.id = id;
  return h("div", { class: "field" }, h("label", { for: id }, label), input, hint && h("small", { class: "hint" }, hint));
}

function errorBox() {
  return h("div", { class: "form-error", role: "alert", hidden: true });
}

function showError(box, err) {
  box.textContent = err?.message || String(err);
  box.hidden = false;
}

async function withBusy(button, fn) {
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Please wait…";
  try {
    return await fn();
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function checkImage(file) {
  if (!file) return null;
  if (!/^image\/(jpeg|png|webp|gif)$/.test(file.type)) return "Please choose a JPEG, PNG, WebP or GIF image.";
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) return `Images must be ${MAX_IMAGE_MB} MB or smaller.`;
  return null;
}

// ---------------------------------------------------------------- router

function navigate(path, { replace = false } = {}) {
  if (replace) history.replaceState(null, "", path);
  else history.pushState(null, "", path);
  render();
}

document.addEventListener("click", (e) => {
  const a = e.target.closest("a[data-link]");
  if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
  e.preventDefault();
  navigate(a.getAttribute("href"));
});
window.addEventListener("popstate", render);

const routes = [
  [/^\/$/, viewHome],
  [/^\/login$/, viewLogin],
  [/^\/register$/, viewRegister],
  [/^\/settings$/, viewSettings],
  [/^\/u\/([A-Za-z0-9_]{1,30})$/, viewUser],
];

let renderSeq = 0;
async function render() {
  const seq = ++renderSeq;
  renderNav();
  const path = location.pathname;
  const match = routes.map(([re, view]) => [path.match(re), view]).find(([m]) => m);
  const view = match ? match[1] : viewNotFound;
  const node = await view(...(match ? match[0].slice(1) : [])).catch((err) =>
    h("div", { class: "card" }, h("p", { class: "form-error" }, err.message)),
  );
  if (seq !== renderSeq) return; // a newer navigation won
  $app.replaceChildren(node);
  window.scrollTo(0, 0);
}

function renderNav() {
  const here = location.pathname;
  const navLink = (href, text) => link(href, { class: here === href ? "active" : null }, text);
  if (me) {
    $nav.replaceChildren(
      navLink("/", "Home"),
      link(`/u/${me.username}`, { class: `nav-me ${here === `/u/${me.username}` ? "active" : ""}` }, avatar(me, "xs"), h("span", {}, me.display_name)),
      navLink("/settings", "Settings"),
      h("button", { class: "btn ghost small", type: "button", onclick: logout }, "Log out"),
    );
  } else {
    $nav.replaceChildren(navLink("/login", "Log in"), link("/register", { class: "btn primary small" }, "Sign up"));
  }
}

async function logout() {
  await api("/auth/logout", { method: "POST" }).catch(() => {});
  me = null;
  toast("Signed out");
  navigate("/");
}

// ---------------------------------------------------------------- posts

function postCard(post, onDelete) {
  const mine = me && me.id === post.author.id;
  const profile = `/u/${post.author.username}`;
  const card = h(
    "article",
    { class: "post" },
    link(profile, { class: "post-avatar", "aria-label": post.author.display_name }, avatar(post.author)),
    h(
      "div",
      { class: "post-main" },
      h(
        "header",
        { class: "post-head" },
        link(profile, { class: "post-name" }, post.author.display_name),
        h("span", { class: "muted" }, `@${post.author.username}`),
        h("span", { class: "muted" }, "·"),
        h("time", { class: "muted", datetime: post.created_at, title: new Date(post.created_at).toLocaleString() }, timeAgo(post.created_at)),
        mine &&
          h(
            "button",
            {
              class: "icon-btn",
              type: "button",
              title: "Delete post",
              "aria-label": "Delete post",
              onclick: async (e) => {
                if (!confirm("Delete this post?")) return;
                try {
                  await api(`/posts/${post.id}`, { method: "DELETE" });
                  card.remove();
                  onDelete?.();
                  toast("Post deleted");
                } catch (err) {
                  toast(err.message, "error");
                }
                e.target.blur();
              },
            },
            "✕",
          ),
      ),
      post.body && h("p", { class: "post-body" }, post.body),
      post.image_url &&
        h("a", { href: post.image_url, target: "_blank", rel: "noopener", class: "post-image" }, h("img", { src: post.image_url, alt: "Attached image", loading: "lazy" })),
    ),
  );
  return card;
}

function composer(onPosted) {
  const textarea = h("textarea", { name: "body", rows: 3, maxlength: MAX_POST, placeholder: "What's happening?", "aria-label": "Post text" });
  const counter = h("span", { class: "counter muted" }, `${MAX_POST}`);
  const fileInput = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp,image/gif", hidden: true });
  const preview = h("div", { class: "compose-preview", hidden: true });
  const submit = h("button", { class: "btn primary", type: "submit", disabled: true }, "Post");
  const err = errorBox();
  let file = null;
  let previewUrl = null;

  const update = () => {
    const left = MAX_POST - textarea.value.length;
    counter.textContent = String(left);
    counter.classList.toggle("warn", left < 20);
    submit.disabled = !(textarea.value.trim() || file);
  };
  const setFile = (f) => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    file = f;
    previewUrl = f ? URL.createObjectURL(f) : null;
    preview.replaceChildren();
    preview.hidden = !f;
    if (f) {
      preview.append(
        h("img", { src: previewUrl, alt: "Selected image preview" }),
        h("button", { type: "button", class: "icon-btn overlay", "aria-label": "Remove image", onclick: () => setFile(null) }, "✕"),
      );
    }
    fileInput.value = "";
    update();
  };

  textarea.addEventListener("input", update);
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    const problem = checkImage(f);
    if (problem) {
      toast(problem, "error");
      fileInput.value = "";
      return;
    }
    setFile(f);
  });

  const form = h(
    "form",
    {
      class: "card composer",
      onsubmit: async (e) => {
        e.preventDefault();
        err.hidden = true;
        const data = new FormData();
        data.append("body", textarea.value);
        if (file) data.append("image", file);
        try {
          const post = await withBusy(submit, () => api("/posts", { method: "POST", form: data }));
          textarea.value = "";
          setFile(null);
          onPosted(post);
        } catch (ex) {
          showError(err, ex);
        }
        update();
      },
    },
    h(
      "div",
      { class: "composer-row" },
      avatar(me),
      h("div", { class: "composer-main" }, textarea, preview, err),
    ),
    h(
      "div",
      { class: "composer-actions" },
      h("button", { type: "button", class: "btn ghost small", onclick: () => fileInput.click() }, "🖼 Add image"),
      fileInput,
      h("div", { class: "spacer" }),
      counter,
      submit,
    ),
  );
  return form;
}

function postList({ author } = {}) {
  const list = h("div", { class: "posts" });
  const empty = h("p", { class: "muted center empty" }, author ? "No posts yet." : "No posts yet. Be the first to chirp!");
  const more = h("button", { class: "btn ghost block", type: "button", hidden: true }, "Load more");
  let cursor = null;

  const refreshEmpty = () => {
    empty.hidden = list.querySelector(".post") !== null;
  };

  async function load() {
    const params = new URLSearchParams({ limit: "20" });
    if (cursor) params.set("before", String(cursor));
    if (author) params.set("author", author);
    const page = await withBusy(more, () => api(`/posts?${params}`));
    for (const p of page.items) list.append(postCard(p, refreshEmpty));
    cursor = page.next_cursor;
    more.hidden = !cursor;
    refreshEmpty();
  }
  more.addEventListener("click", () => load().catch((e) => toast(e.message, "error")));

  return {
    el: h("section", {}, empty, list, more),
    load,
    prepend(post) {
      list.prepend(postCard(post, refreshEmpty));
      refreshEmpty();
    },
  };
}

// ---------------------------------------------------------------- views

async function viewHome() {
  const feed = postList();
  await feed.load();
  return h(
    "div",
    { class: "stack" },
    h("h1", { class: "page-title" }, "Home"),
    me
      ? composer((post) => {
          feed.prepend(post);
          toast("Posted!");
        })
      : h(
          "div",
          { class: "card welcome" },
          h("h2", {}, "Welcome to Chirp"),
          h("p", { class: "muted" }, "Join to share short messages and pictures with everyone."),
          h("div", { class: "row" }, link("/register", { class: "btn primary" }, "Create account"), link("/login", { class: "btn ghost" }, "Log in")),
        ),
    feed.el,
  );
}

async function viewUser(username) {
  let user;
  try {
    user = await api(`/users/${encodeURIComponent(username)}`);
  } catch (e) {
    if (e.status === 404) return viewNotFound("That user doesn't exist.");
    throw e;
  }
  const feed = postList({ author: user.username });
  await feed.load();
  const joined = new Date(user.created_at).toLocaleDateString(undefined, { month: "long", year: "numeric" });
  return h(
    "div",
    { class: "stack" },
    h(
      "div",
      { class: "card profile-head" },
      avatar(user, "xl"),
      h(
        "div",
        {},
        h("h1", {}, user.display_name),
        h("p", { class: "muted" }, `@${user.username} · Joined ${joined}`),
        me?.id === user.id && link("/settings", { class: "btn ghost small" }, "Edit profile"),
      ),
    ),
    feed.el,
  );
}

function authCard(title, subtitle, form, footer) {
  return h("div", { class: "auth" }, h("div", { class: "card" }, h("h1", {}, title), subtitle && h("p", { class: "muted" }, subtitle), form, footer && h("p", { class: "muted center footer" }, footer)));
}

async function viewLogin() {
  if (me) return redirect("/");
  const login = h("input", { name: "login", required: true, autocomplete: "username", autofocus: true });
  const password = h("input", { name: "password", type: "password", required: true, autocomplete: "current-password" });
  const submit = h("button", { class: "btn primary block", type: "submit" }, "Log in");
  const err = errorBox();
  const form = h(
    "form",
    {
      onsubmit: async (e) => {
        e.preventDefault();
        err.hidden = true;
        try {
          me = await withBusy(submit, () => api("/auth/login", { method: "POST", json: { login: login.value, password: password.value } }));
          toast(`Welcome back, ${me.display_name}!`);
          navigate("/");
        } catch (ex) {
          showError(err, ex);
        }
      },
    },
    field("Username or email", login),
    field("Password", password),
    err,
    submit,
  );
  return authCard("Log in to Chirp", null, form, ["New here? ", link("/register", {}, "Create an account")]);
}

async function viewRegister() {
  if (me) return redirect("/");
  const inp = (name, attrs = {}) => h("input", { name, required: true, ...attrs });
  const f = {
    first_name: inp("first_name", { autocomplete: "given-name", maxlength: 100 }),
    last_name: inp("last_name", { autocomplete: "family-name", maxlength: 100 }),
    age: inp("age", { type: "number", min: 13, max: 130, inputmode: "numeric" }),
    address: h("textarea", { name: "address", required: true, rows: 2, minlength: 5, maxlength: 500, autocomplete: "street-address" }),
    email: inp("email", { type: "email", autocomplete: "email", maxlength: 254 }),
    username: inp("username", { autocomplete: "username", pattern: "[A-Za-z0-9_]{3,30}", maxlength: 30 }),
    password: inp("password", { type: "password", autocomplete: "new-password", minlength: 8, maxlength: 128 }),
    confirm: inp("confirm", { type: "password", autocomplete: "new-password" }),
  };
  const submit = h("button", { class: "btn primary block", type: "submit" }, "Create account");
  const err = errorBox();

  const form = h(
    "form",
    {
      onsubmit: async (e) => {
        e.preventDefault();
        err.hidden = true;
        if (f.password.value !== f.confirm.value) return showError(err, "Passwords don't match.");
        const payload = {
          first_name: f.first_name.value,
          last_name: f.last_name.value,
          age: Number(f.age.value),
          address: f.address.value,
          email: f.email.value,
          username: f.username.value,
          password: f.password.value,
        };
        try {
          me = await withBusy(submit, () => api("/auth/register", { method: "POST", json: payload }));
          toast(`Welcome to Chirp, ${me.display_name}!`);
          navigate("/");
        } catch (ex) {
          showError(err, ex);
        }
      },
    },
    h("fieldset", {}, h("legend", {}, "About you"), h("div", { class: "grid-2" }, field("First name", f.first_name), field("Last name", f.last_name)), field("Age", f.age, "You must be at least 13."), field("Address", f.address)),
    h(
      "fieldset",
      {},
      h("legend", {}, "Account"),
      field("Email", f.email),
      field("Username", f.username, "3–30 letters, numbers or underscores."),
      h("div", { class: "grid-2" }, field("Password", f.password, "At least 8 characters, with a letter and a number."), field("Confirm password", f.confirm)),
    ),
    err,
    submit,
  );
  return authCard("Create your account", "Your name, age and address stay private. Only your display name and avatar are public.", form, ["Already have an account? ", link("/login", {}, "Log in")]);
}

async function viewSettings() {
  if (!me) return redirect("/login");

  // Display name
  const nameInput = h("input", { name: "display_name", required: true, maxlength: 50, value: me.display_name });
  const nameBtn = h("button", { class: "btn primary", type: "submit" }, "Save");
  const nameErr = errorBox();
  const nameForm = h(
    "form",
    {
      class: "card",
      onsubmit: async (e) => {
        e.preventDefault();
        nameErr.hidden = true;
        try {
          me = await withBusy(nameBtn, () => api("/users/me", { method: "PATCH", json: { display_name: nameInput.value } }));
          nameInput.value = me.display_name;
          renderNav();
          toast("Display name updated");
        } catch (ex) {
          showError(nameErr, ex);
        }
      },
    },
    h("h2", {}, "Display name"),
    h("p", { class: "muted" }, "Shown next to your posts."),
    field("Display name", nameInput),
    nameErr,
    h("div", { class: "row end" }, nameBtn),
  );

  // Avatar
  const avatarSlot = h("div", { class: "avatar-slot" });
  const avatarFile = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp,image/gif", hidden: true });
  const uploadBtn = h("button", { class: "btn primary", type: "button", onclick: () => avatarFile.click() }, "Upload new");
  const removeBtn = h("button", { class: "btn ghost", type: "button" }, "Remove");
  const avatarErr = errorBox();
  const refreshAvatar = () => {
    avatarSlot.replaceChildren(avatar(me, "xl"));
    removeBtn.hidden = !me.avatar_url;
    renderNav();
  };
  avatarFile.addEventListener("change", async () => {
    const file = avatarFile.files[0];
    avatarFile.value = "";
    if (!file) return;
    avatarErr.hidden = true;
    const problem = checkImage(file);
    if (problem) return showError(avatarErr, problem);
    const form = new FormData();
    form.append("file", file);
    try {
      me = await withBusy(uploadBtn, () => api("/users/me/avatar", { method: "PUT", form }));
      refreshAvatar();
      toast("Avatar updated");
    } catch (ex) {
      showError(avatarErr, ex);
    }
  });
  removeBtn.addEventListener("click", async () => {
    try {
      me = await withBusy(removeBtn, () => api("/users/me/avatar", { method: "DELETE" }));
      refreshAvatar();
      toast("Avatar removed");
    } catch (ex) {
      showError(avatarErr, ex);
    }
  });
  const avatarCard = h(
    "section",
    { class: "card" },
    h("h2", {}, "Avatar"),
    h("p", { class: "muted" }, `JPEG, PNG, WebP or GIF up to ${MAX_IMAGE_MB} MB. It will be cropped to a square.`),
    h("div", { class: "avatar-row" }, avatarSlot, h("div", { class: "row" }, uploadBtn, removeBtn, avatarFile)),
    avatarErr,
  );
  refreshAvatar();

  // Password
  const cur = h("input", { type: "password", required: true, autocomplete: "current-password" });
  const next = h("input", { type: "password", required: true, minlength: 8, maxlength: 128, autocomplete: "new-password" });
  const confirmPw = h("input", { type: "password", required: true, autocomplete: "new-password" });
  const pwBtn = h("button", { class: "btn primary", type: "submit" }, "Change password");
  const pwErr = errorBox();
  const pwForm = h(
    "form",
    {
      class: "card",
      onsubmit: async (e) => {
        e.preventDefault();
        pwErr.hidden = true;
        if (next.value !== confirmPw.value) return showError(pwErr, "New passwords don't match.");
        try {
          await withBusy(pwBtn, () => api("/users/me/password", { method: "PUT", json: { current_password: cur.value, new_password: next.value } }));
          pwForm.reset();
          toast("Password changed. Other devices have been signed out.");
        } catch (ex) {
          showError(pwErr, ex);
        }
      },
    },
    h("h2", {}, "Password"),
    h("p", { class: "muted" }, "Changing your password signs you out everywhere else."),
    field("Current password", cur),
    h("div", { class: "grid-2" }, field("New password", next, "At least 8 characters, with a letter and a number."), field("Confirm new password", confirmPw)),
    pwErr,
    h("div", { class: "row end" }, pwBtn),
  );

  // Read-only registration details
  const dl = h(
    "dl",
    { class: "details" },
    [
      ["Name", `${me.first_name} ${me.last_name}`],
      ["Age", me.age],
      ["Address", me.address],
      ["Email", me.email],
      ["Username", `@${me.username}`],
    ].map(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]),
  );
  const details = h("section", { class: "card" }, h("h2", {}, "Account details"), h("p", { class: "muted" }, "Private: only you can see these."), dl);

  return h("div", { class: "stack" }, h("h1", { class: "page-title" }, "Settings"), nameForm, avatarCard, pwForm, details);
}

function viewNotFound(message = "We couldn't find that page.") {
  return h("div", { class: "card center" }, h("h1", {}, "Not found"), h("p", { class: "muted" }, message), link("/", { class: "btn primary" }, "Go home"));
}

function redirect(path) {
  queueMicrotask(() => navigate(path, { replace: true }));
  return h("p", { class: "muted center" }, "Redirecting…");
}

// ---------------------------------------------------------------- boot

(async function boot() {
  try {
    me = await api("/users/me");
  } catch {
    me = null;
  }
  render();
})();
