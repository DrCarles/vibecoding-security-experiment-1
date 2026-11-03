# Security Gap Analysis: Chirp vs. Software Security Requirements Baseline

| | |
|---|---|
| **System assessed** | Chirp microblog, commit `c1b20f2` ([DrCarles/vibecoding-security-experiment-1](https://github.com/DrCarles/vibecoding-security-experiment-1)) |
| **Baseline** | [DrCarles/SoftwareSecurityReqs-Baseline](https://github.com/DrCarles/SoftwareSecurityReqs-Baseline), commit `02a65f5`: 31 functional requirements in 6 domains |
| **Date** | 2026-11-03 |
| **Method** | Code review of the backend, frontend and Docker setup, plus tests against the running Docker Compose stack (results are cited in each finding) |

## 1. Executive summary

> ### 31 requirements · 35% compliance score
> ✅ **5** Met  ·  🟡 **12** Partial  ·  ❌ **14** Not met
>
> 🟩🟩🟩🟩🟩🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟨🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥
>
> 🚨 **8** requirements are P1 (fix before production)

| | Domain | Requirements (one square each) | ✅ | 🟡 | ❌ | Score |
|:-:|---|---|:-:|:-:|:-:|:-:|
| 🔑 | **Authentication** (AUT) | 🟩🟩🟩🟨🟨🟨🟨🟨🟥🟥🟥🟥🟥 | 3 | 5 | 5 | 🟡 42% |
| 🛡️ | **Authorization** (AUZ) | 🟩🟨🟨🟨🟥🟥 | 1 | 3 | 2 | 🟡 42% |
| 🧹 | **Data Sanitization** (DSN) | 🟩🟨 | 1 | 1 | · | 🟢 75% |
| 💾 | **Data at Rest** (DAR) | 🟨🟥🟥 | · | 1 | 2 | 🔴 17% |
| 🔒 | **Data in Transit** (DIT) | 🟨🟥🟥 | · | 1 | 2 | 🔴 17% |
| 🕵️ | **Privacy** (PRV) | 🟨🟥🟥🟥 | · | 1 | 3 | 🔴 13% |
| | **Total** | **31** | **5** | **12** | **14** | 🔴 **35%** |

**Score** = (Met + ½ × Partial) ÷ total requirements · 🟢 70% or more · 🟡 40–69% · 🔴 below 40% · 🟩 Met · 🟨 Partial · 🟥 Not met

**Strengths.** The core web-application controls are solid:
- Passwords are salted and hashed (Argon2id).
- Each API endpoint checks ownership.
- Changing a password revokes all other sessions.
- Database queries are parameterized.
- The frontend never inserts user content as HTML, and a strict Content-Security-Policy is in place.
- Uploaded images are validated and re-encoded, which strips metadata.
- The database and API are isolated on an internal Docker network.

**Main gaps.** Most gaps fall into four themes:

1. **No audit trail.** Account changes and access decisions are not logged (AUT-008, AUZ-006, AUT-006).
2. **Session lifecycle.** Sessions are stateless, last 7 days and survive logout, and there is no inactivity timeout (AUT-007, AUT-011).
3. **Privacy and data protection.** Users can't delete their account, private fields can't be set to empty, nothing is retained or deleted on a schedule, and personal data isn't encrypted at the application level (PRV-001 to PRV-004, DAR-001).
4. **Infrastructure hardening.** The site has no TLS of its own, the app uses a database superuser, there are no backups, and the API docs are public (DIT-002, DAR-002, DAR-003, DIT-001).

**Must fix before production:** DIT-002 (TLS), AUT-011 and AUT-007 (sessions), DAR-002 (database superuser). All P1 items are listed in the [scorecard](#2-scorecard).

### Status legend

| Status | Meaning |
|---|---|
| ✅ Met | All "must" specifications are satisfied |
| 🟡 Partial | The intent is partly addressed, or some specifications are unmet |
| ❌ Not met | Not implemented |

Priority: **P1** = fix before production · **P2** = fix in the next release · **P3** = planned improvement.

---

## 2. Scorecard

| ID | Requirement (short) | Status | Priority |
|---|---|:-:|:-:|
| FR-APP-AUT-001 | Unique, never-reused user ID (GUID) | 🟡 | P3 |
| FR-APP-AUT-002 | All accounts manageable (edit, delete, password) | ❌ | P2 |
| FR-APP-AUT-003 | Password policy (NIST 800-63B) | 🟡 | P2 |
| FR-APP-AUT-004 | Secure password storage | 🟡 | P3 |
| FR-APP-AUT-005 | Two-factor authentication *(should)* | ❌ | P3 |
| FR-APP-AUT-006 | Brute-force protection (5 attempts → 5 min lock) | 🟡 | P2 |
| FR-APP-AUT-007 | Automatic log-off after inactivity (10 min) | ❌ | P1 |
| FR-APP-AUT-008 | Log user-management activity | ❌ | P1 |
| FR-APP-AUT-009 | User enumeration protection | 🟡 | P2 |
| FR-APP-AUT-010 | Shoulder-surfing protection | ✅ | – |
| FR-APP-AUT-011 | Server-side session invalidation on logout | ❌ | P1 |
| FR-APP-AUT-012 | Re-authentication for sensitive actions | ✅ | – |
| FR-APP-AUT-013 | Invalidate all sessions on password change | ✅ | – |
| FR-APP-AUZ-001 | Authorization enforced in business logic | ✅ | – |
| FR-APP-AUZ-002 | Deny by default | 🟡 | P2 |
| FR-APP-AUZ-003 | Clearly defined permissions | 🟡 | P3 |
| FR-APP-AUZ-004 | Role-based access control *(should)* | ❌ | P3 |
| FR-APP-AUZ-005 | Least privilege and separation of duties by default | 🟡 | P1 |
| FR-APP-AUZ-006 | Log all authorization decisions | ❌ | P2 |
| FR-APP-DAR-001 | Encrypt sensitive data at rest | ❌ | P2 |
| FR-APP-DAR-002 | Least-privilege data access | 🟡 | P1 |
| FR-APP-DAR-003 | Backup and restore | ❌ | P2 |
| FR-APP-DIT-001 | Restrict exposed endpoints | 🟡 | P1 |
| FR-APP-DIT-002 | Secure external channels (TLS) | ❌ | P1 |
| FR-APP-DIT-003 | Secure internal channels *(should)* | ❌ | P3 |
| FR-APP-DSN-001 | Input validation | 🟡 | P2 |
| FR-APP-DSN-002 | Output sanitization | ✅ | – |
| FR-APP-PRV-001 | Data minimization | 🟡 | P2 |
| FR-APP-PRV-002 | Data lifecycle and retention | ❌ | P2 |
| FR-APP-PRV-003 | Right to erasure | ❌ | P1 |
| FR-APP-PRV-004 | Secure data disposal | ❌ | P3 |

---

## 3. Detailed findings

### 3.1 Authentication

#### FR-APP-AUT-001: Unique, never-reused user identifier · 🟡 Partial · P3

| Specification | Status | Evidence |
|---|:-:|---|
| ID never reused after deletion | ✅ | `users.id` is a PostgreSQL `IDENTITY` column; sequences never hand out a value twice. |
| ID must be a GUID | ❌ | `BIGINT` IDs ([models.py](../backend/app/models.py), [0001_initial.py](../backend/alembic/versions/0001_initial.py)). |
| ID randomly generated | ❌ | IDs are sequential, so they reveal the number of users and sign-up order. |

**Gap.** IDs are sequential integers that can be guessed. Exposure is limited, because every endpoint checks ownership and IDOR (accessing records by guessing their IDs) is already prevented (see AUZ-001). The spec still explicitly requires random GUIDs.

#### FR-APP-AUT-002: All user accounts manageable · ❌ Not met · P2

| Specification | Status | Evidence |
|---|:-:|---|
| No hidden or hard-coded accounts | ✅ | No seed or default accounts exist. |
| Each account editable | 🟡 | Users can edit only their display name. Name, age, address and email can't be changed after sign-up. |
| Each account deletable | ❌ | No endpoint deletes an account. |
| Each account's password editable | 🟡 | Users can change their own password. There is no admin reset or self-service "forgot password". |
| Admin interface lists all accounts | ❌ | No admin role or interface (see AUZ-004). |

#### FR-APP-AUT-003: Password policy · 🟡 Partial · P2

| Specification | Status | Evidence |
|---|:-:|---|
| Minimum 8 characters (15 recommended) | ✅ / 🟡 | Minimum is 8 ([schemas.py](../backend/app/schemas.py)). 15 is not used. |
| Maximum length of at least 64 | ✅ | Maximum is 128. |
| Accept printable ASCII, spaces and Unicode | ✅ | Any string is accepted. |
| *Should not* impose composition rules | ❌ | `_check_password_strength` requires a letter **and** a digit ([schemas.py:20](../backend/app/schemas.py#L20)). It rejected the passphrase `correct horse battery staple` in testing. |
| No periodic expiry; force a change on compromise | 🟡 | No expiry ✅. There is no way to force a password change ❌. |
| No hints or security questions | ✅ | None exist. |
| Verify the entire password (no truncation) | ✅ | Argon2 has no 72-byte limit, unlike bcrypt. |
| Check against a blocklist of common or breached passwords | ❌ | Not implemented. |
| Same policy on every password path | ✅ | Sign-up and password change share one validator; no other paths exist. |

#### FR-APP-AUT-004: Secure password storage · 🟡 Partial · P3

| Specification | Status | Evidence |
|---|:-:|---|
| Not stored in cleartext; non-reversible | ✅ | Argon2id via `argon2-cffi` ([security.py](../backend/app/security.py)). All stored hashes start with `$argon2`, confirmed by the integrity check. |
| Salted (same password gives a different hash) | ✅ | A random salt is generated for each hash. |
| NIST-approved hashing function (SP 800-140C) | ❌ | Argon2id is the [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) first choice, but it is **not** a NIST/FIPS-approved function. |

**Gap.** This is a compliance gap, not a weakness: Argon2id is stronger than the NIST-approved options.

#### FR-APP-AUT-005: Two-factor authentication *(should)* · ❌ Not met · P3

There is no second authentication factor.

#### FR-APP-AUT-006: Brute-force protection · 🟡 Partial · P2

| Specification | Status | Evidence |
|---|:-:|---|
| Lock a **user** for 5 minutes after 5 failures | ❌ | No per-account counter. A distributed attack on one account is unlimited. |
| Lock an **IP** for 5 minutes after 5 failures | 🟡 | `slowapi` allows 10 login attempts per minute per IP ([auth.py](../backend/app/routers/auth.py)). Counters are kept separately in each of the 2 workers, so roughly 20 attempts per minute get through in practice (seen in testing). It is a rolling window, not a 5-minute lockout. |
| Log and notify on lockouts | ❌ | Nothing is logged except the HTTP 429 access-log line. |

#### FR-APP-AUT-007: Automatic log-off after inactivity · ❌ Not met · P1

| Specification | Status | Evidence |
|---|:-:|---|
| Log off after inactivity | ❌ | Sessions have an **absolute 7-day** lifetime (`session_ttl_minutes = 60*24*7`, [config.py:13](../backend/app/config.py#L13)). Activity does not extend or shorten them. |
| Default timeout of 10 minutes | ❌ | – |
| Timeout configurable | 🟡 | `SESSION_TTL_MINUTES` exists, but it is an absolute lifetime, not an inactivity timeout, and Docker Compose doesn't pass it through. |

#### FR-APP-AUT-008: Log user-management activity · ❌ Not met · P1

| Event | Logged? |
|---|:-:|
| User creation | ❌ |
| User deletion | ❌ (feature missing) |
| Password change | ❌ |
| Password reset | ❌ (feature missing) |
| Lockout / unlock | ❌ (feature missing) |

The only logs are the HTTP access logs from Uvicorn and morgan. They show method, path, status and client IP, but not *who* did what.

#### FR-APP-AUT-009: User enumeration protection · 🟡 Partial · P2

| Specification | Status | Evidence |
|---|:-:|---|
| Generic login error | ✅ | Unknown user and wrong password both return `"Wrong username/email or password"`. |
| Consistent login response time | ✅ | For an unknown user, the password is checked against a dummy Argon2 hash ([security.py:19](../backend/app/security.py#L19)), so both cases take about the same time. |
| *(Other paths)* sign-up | ❌ | Sign-up returns **`"An account with this email already exists"`** ([auth.py:18](../backend/app/routers/auth.py#L18)), confirmed in testing. This is a reliable email-enumeration oracle, limited only by the 10-per-hour rate limit. |

Usernames are deliberately public (profile pages at `/u/<name>`), so username enumeration is accepted by design. Email addresses are private.

#### FR-APP-AUT-010: Shoulder-surfing protection · ✅ Met

Every password field uses `type="password"`: login, sign-up (two fields) and settings (three fields) in [app.js](../frontend/public/app.js). Passwords are never shown back in the UI.

#### FR-APP-AUT-011: Server-side session invalidation on logout · ❌ Not met · P1

**Evidence.** `POST /api/auth/logout` only deletes the browser cookie ([auth.py:57](../backend/app/routers/auth.py#L57)). In testing, a captured session token **still returned HTTP 200 from `/api/users/me` after logout**. It stays valid for up to 7 days. The requirement's own note says stateless JWTs need short lifetimes, and 7 days is not short.

#### FR-APP-AUT-012: Re-authentication for sensitive actions · ✅ Met

Changing the password requires the current password ([users.py](../backend/app/routers/users.py)). No other security-sensitive actions exist yet: there is no email change, account deletion, API key or 2FA setup. Each of these **must** require the current password when it is added.

#### FR-APP-AUT-013: Invalidate sessions on password change · ✅ Met

A password change increments `users.token_version`. Every session token carries a `ver` claim that is checked on each request ([deps.py](../backend/app/deps.py)), so all existing sessions stop working. The current session gets a fresh cookie. This is covered by the test `test_password_change_revokes_other_sessions`.

---

### 3.2 Authorization

#### FR-APP-AUZ-001: Authorization enforced in business logic · ✅ Met

All checks happen on the server, in the API layer:
- `/users/me/*` endpoints act only on the user identified by the session cookie. No user ID is taken from the request.
- `DELETE /api/posts/{id}` checks `post.author_id == user.id` and returns 403 otherwise. This is tested in `test_delete_only_own_posts`.

Hiding the delete button in the UI is cosmetic only.

#### FR-APP-AUZ-002: Deny by default · 🟡 Partial · P2

**Evidence.** Each endpoint opts into authentication by adding the `CurrentUser` dependency. A **new endpoint is public unless the developer remembers to add it**: allow by default at the framework level. The current public endpoints are intentional (feed, public profiles, health), but `/api/docs` and `/api/openapi.json` are public too (see DIT-001). Denied requests are not logged.

#### FR-APP-AUZ-003: Clearly defined permissions · 🟡 Partial · P3

Permissions exist only as ownership checks scattered through the endpoints, with no central definition of "action X on asset Y". This is acceptable for the current single-role design, but it can't be reviewed or audited as a model.

#### FR-APP-AUZ-004: Role-based access control *(should)* · ❌ Not met · P3

There are no roles; every account is equal. The platform therefore has no way to moderate content or administer users, as AUT-002 requires.

#### FR-APP-AUZ-005: Least privilege and separation of duties by default · 🟡 Partial · P1

- **Application layer ✅:** new users can only create content and manage their own data.
- **Platform layer ❌:**
  - The API and the migration job both connect to Postgres as `chirp`. That role is a **superuser** (`rolsuper = t`, confirmed), because the official Postgres image grants it by default.
  - The account that changes the schema is the same one that serves traffic, so there is no separation of duties.
- **Insecure defaults:** `COOKIE_SECURE=false` and public API docs are the out-of-the-box settings.

#### FR-APP-AUZ-006: Log all authorization decisions · ❌ Not met · P2

Neither allowed nor denied decisions are logged with user, action, asset and timestamp. A 403 on post deletion shows up only as an access-log line without the user ID.

---

### 3.3 Data at rest

#### FR-APP-DAR-001: Encrypt sensitive data at rest · ❌ Not met · P2

| Specification | Status | Evidence |
|---|:-:|---|
| Encrypt sensitive data | ❌ | `email`, `first_name`, `last_name`, `age` and `address` are stored as plaintext columns. |
| Use NIST-approved algorithms | ❌ | No encryption at all. |
| Cover databases, logs and backups | ❌ | The Docker volumes (`pgdata`, `media`) are unencrypted; there are no backups to encrypt. |
| Key management | ❌ | No keys exist. `JWT_SECRET` sits in a plaintext `.env` file. |

#### FR-APP-DAR-002: Least-privilege data access · 🟡 Partial · P1

| Control | Status |
|---|:-:|
| Containers run as non-root (`app` UID 10001, `node`) | ✅ |
| Database not reachable from outside Docker (internal network) | ✅ |
| Least-privilege database role for the app | ❌ The superuser `chirp` is used for everything |
| Separate migration role | ❌ |

#### FR-APP-DAR-003: Backup and restore · ❌ Not met · P2

There is no backup mechanism; the README only says "back up the volumes".

---

### 3.4 Data in transit

#### FR-APP-DIT-001: Restrict exposed endpoints · 🟡 Partial · P1

| Control | Status |
|---|:-:|
| Postgres and the API not published to the host (internal network) | ✅ |
| Only the frontend port is published | ✅ |
| No debug or admin interfaces exposed | ❌ Swagger UI `/api/docs` and the full API schema `/api/openapi.json` are **public** (HTTP 200, confirmed) |
| Health endpoint minimal | 🟡 `/api/health` is public. It reveals only DB reachability, which is acceptable, but it could be limited to the internal network. |

#### FR-APP-DIT-002: Secure external channels · ❌ Not met · P1

| Specification | Status | Evidence |
|---|:-:|---|
| Supported TLS version, old versions disabled | ❌ | The stack serves **plain HTTP on port 8080**. TLS is left to an external reverse proxy that is documented in the README but not shipped. |
| Hardened cipher suites | ❌ | – |
| Valid server certificate | ❌ | – |
| Mutual TLS *(where feasible)* | N/A | Public consumer web app. |

Helmet does send an HSTS header, but browsers ignore it over HTTP. `COOKIE_SECURE` defaults to `false`, so the session cookie travels in cleartext.

#### FR-APP-DIT-003: Secure internal channels *(should)* · ❌ Not met · P3

Frontend to backend is plain HTTP. Backend to Postgres is unencrypted (`SHOW ssl` → `off`), and the connection string has no `sslmode`. The risk is reduced by the isolated internal network on one host, but not removed.

---

### 3.5 Data sanitization

#### FR-APP-DSN-001: Input validation · 🟡 Partial · P2

| Specification | Status | Evidence |
|---|:-:|---|
| Server-side validation | ✅ | Pydantic schemas set types, lengths and ranges. Usernames use an allow-list pattern (`^[A-Za-z0-9_]{3,30}$`), emails are validated with `email-validator`, and age must be 13–130. Posts are capped at 280 characters. Images are checked by decoding them, with a format allow-list, size limit and decompression-bomb guard. The request body size is capped. Query parameters are typed. |
| Client-side validation | ✅ | HTML5 `required`, `minlength`, `maxlength`, `pattern`, `min`/`max`, plus a file type and size check in [app.js](../frontend/public/app.js). |
| Strict format checks | 🟡 | Free-text fields (`display_name`, `first_name`, `last_name`, `address`, post `body`) accept **any** Unicode: control characters, zero-width characters and bidirectional overrides (U+202E). Those allow display-name spoofing and log injection through `\n`. |
| Block-list dangerous characters | ❌ | No block-list. *Note:* the design relies on allow-lists, parameterized SQL (SQLAlchemy) and context-aware output encoding, which OWASP prefers to block-lists. Record this as a justified deviation. |

#### FR-APP-DSN-002: Output sanitization · ✅ Met

- The SPA builds all DOM with `textContent` or `setAttribute` and never uses `innerHTML` with data ([app.js](../frontend/public/app.js)).
- The Content-Security-Policy `script-src 'self'; script-src-attr 'none'; object-src 'none'` blocks inline scripts as a second layer.
- The API returns `application/json` with `X-Content-Type-Options: nosniff`.
- Uploaded images are re-encoded to WebP, so users' raw bytes are never served.

The spec's "escape block-listed characters" is met in effect: everything is encoded for the place it's displayed.
*Caveat:* the API returns raw (unescaped) user text in JSON. Any future consumer, such as email templates or a mobile app, must encode it for its own context.

---

### 3.6 Privacy

#### FR-APP-PRV-001: Data minimization · 🟡 Partial · P2

| Specification | Status | Evidence |
|---|:-:|---|
| Collect only necessary data | ❌ | The product brief required **age and full postal address** at sign-up, but no feature uses them. Age only needs a "13 or older" check, and the address serves no purpose. |
| Discard unneeded data at input | ✅ | Unknown JSON fields are ignored and never stored. Image EXIF data, including GPS, is stripped. |
| Mask discarded sensitive data in logs | 🟡 | Request bodies aren't logged ✅. Access logs from Express (morgan `combined`) and Uvicorn record **client IP addresses and user agents** (personal data under GDPR) with no retention limit. |

#### FR-APP-PRV-002: Data lifecycle management · ❌ Not met · P2

There is no retention policy or purge job. Accounts, posts, images and Docker logs are kept forever, and Docker's default `json-file` log driver has no size or age limit.

#### FR-APP-PRV-003: Right to erasure · ❌ Not met · P1

| Specification | Status | Evidence |
|---|:-:|---|
| Users can request deletion | ❌ | No account-deletion feature. |
| PII not used as primary key | ✅ | The primary key is the surrogate `id`. |
| PII not used as foreign key | ✅ | `posts.author_id` references `users.id`. |
| PII columns nullable | ❌ | `email`, `first_name`, `last_name`, `age` and `address` are all `NOT NULL` (confirmed in the schema), so a user's data can't be anonymised while keeping the row. |
| No PII in logs | ❌ | Access logs contain IPs, and usernames in URLs (`/api/users/<username>`, `?author=<username>`). Usernames are public handles, but they can identify a person. |

#### FR-APP-PRV-004: Secure data disposal · ❌ Not met · P3

Deleting a post or avatar calls `unlink()` on the file ([media.py](../backend/app/media.py)) and deletes the database row. File contents stay on disk until overwritten. Deleted database rows stay in dead tuples until `VACUUM`, and in the WAL and future backups.
