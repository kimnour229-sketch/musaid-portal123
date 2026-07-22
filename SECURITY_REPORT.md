# Security Report — Musaid Portal

**Application:** منصة المذكرات الرقمية — المعهد العالي للعلوم والتقنية أمساعد
**Stack:** Flask 3.1 + raw `sqlite3` (`musaid_ist.db`), Bootstrap 5.3 RTL
**Last updated:** 2026-06-04 (Phase 5 — Session & Request Hardening)

---

## 1. Executive Summary

Across Phases 4–5 the portal moved from storing **plaintext passwords shown in the admin UI** and a **predictable hardcoded session key** to a hardened authentication stack: salted password hashing with on-login migration, environment-driven secret key, hardened session cookies, CSRF protection on every state-changing form, brute-force rate limiting with temporary lockout, an authentication audit trail, and server-side input validation.

All changes are **backward-compatible and additive** — no routes, roles, permissions, or business logic were changed. Existing users keep access; legacy plaintext passwords upgrade transparently on first login.

**Verification:** 24/24 regression + security checks passed, plus 18/18 render/responsive/dark-mode checks, on a throwaway copy of the production database.

---

## 2. Security Improvements Delivered

### Phase 4 — Password Security
| Area | Before | After |
|---|---|---|
| Password storage | Plaintext in `teachers.password` | Werkzeug **PBKDF2-SHA256**, per-user 16-byte salt |
| Admin UI | Plaintext password column with reveal toggle | Column removed; admin "reset" shows a strong password **once** via flash |
| Legacy accounts | — | **Lazy migration**: verified plaintext is re-hashed on first successful login (no lockout, no forced reset) |
| New/changed passwords | Stored as typed | Always hashed (`add`/`edit`/`reset`/`change` paths) |
| Policy | None | `validate_password()` — ≥8 chars, ≥1 letter, ≥1 digit (server-side) + client strength meter |
| Boot behavior | `UPDATE admin SET password='33557799'` on **every** restart (would clobber hashes) | INSERT-if-missing with a hashed default only |
| Self-service | None | `/change_password` requires current-password verification |

### Phase 5 — Session & Request Hardening
| # | Control | Implementation |
|---|---|---|
| 1 | **Secret key from environment** | `MUSAID_SECRET_KEY` env var; otherwise a 256-bit key is generated once and persisted to `.secret_key` (gitignored) so sessions survive restarts. The old hardcoded `'musaid_secret_key'` is gone. |
| 2 | **Hardened session cookies** | `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`, `SESSION_COOKIE_SECURE=True` (toggle via `MUSAID_COOKIE_SECURE=0` for local HTTP dev), `PERMANENT_SESSION_LIFETIME=8h`. |
| 3 | **CSRF protection** | Session-bound token injected into all 6 POST forms via `{{ csrf_token() }}`; `before_request` rejects any POST/PUT/PATCH/DELETE with a missing/mismatched token (`abort 400`). Timing-safe comparison. |
| 4 | **Login rate limiting** | Per-IP failure counter over a 5-minute window (`RATE_LIMIT_MAX_FAILS=5`). |
| 5 | **Temporary lockout** | After the threshold, the source IP is locked out for 15 minutes — correct credentials are also refused during lockout. |
| 6 | **Authentication audit log** | `logs/auth.log` records `login_success/failure/locked`, `logout`, `password_change_*`, `password_reset`, `teacher_add/edit/delete`, and `csrf_failure` — with timestamp, IP, and user id. **Passwords are never logged.** |
| 7 | **Input validation** | Email format + length validation, name length caps, and `MAX_CONTENT_LENGTH=50MB` upload guard. |
| + | **Session-fixation defense** | Session id is rotated (cleared + re-issued) on successful login. |

### Pre-existing strengths retained
- All DB access uses **parameterized queries** (no string-built SQL) → SQL injection safe.
- Uploaded filenames pass through `secure_filename()`.
- Authorization checks (`session['role']`) unchanged on every protected route.

---

## 3. Remaining Vulnerabilities / Limitations

| Severity | Issue | Notes |
|---|---|---|
| Medium | **State-changing GET routes** | `delete_teacher`, `reset_password`, `delete_subject`, `delete_handout` use GET links (driven by SweetAlert redirects). They are session-auth protected but not CSRF-protected. Converting to POST would require frontend rework — deferred to avoid breaking the UI. |
| Medium | **Rate-limit/lockout is in-memory & per-process** | Resets on restart and is not shared across workers. Single-process deployments are fine; multi-worker/horizontal scaling needs a shared store (Redis). |
| Medium | **Legacy passwords remain plaintext until first login** | Inherent to migrate-on-login. A DB compromise before a given user logs in still exposes their plaintext. Mitigation: force-reset campaign (see recommendations). |
| Medium | **No email-based self-service reset** | No SMTP configured; a locked-out user still depends on an admin reset. |
| Low | **Admin identity is email-string based** | `admin@musaid.edu.ly` rather than a dedicated role column — works, but fragile to misconfiguration. |
| Low | **`debug=True` in `app.run`** | Must be disabled in production (see deployment checklist) — the Werkzeug debugger is an RCE vector if exposed. |
| Low | **No security headers / HTTPS enforcement at app layer** | CSP, HSTS, X-Frame-Options, etc. should be set at the reverse proxy or via Flask-Talisman. |
| Low | **`X-Forwarded-For` trusted for client IP** | Only meaningful behind a trusted proxy that sets it; otherwise spoofable. Acceptable for audit/rate-limit best-effort. |

---

## 4. Recommended Future Enhancements

1. **Run behind HTTPS + a hardened reverse proxy** (Nginx/Caddy) and add security headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options) — e.g. via **Flask-Talisman**.
2. **Disable `debug` and use a WSGI server** (gunicorn/waitress) — never `app.run(debug=True)` in production.
3. **Move rate-limit/lockout state to Redis** (or adopt **Flask-Limiter**) for multi-worker correctness.
4. **Force-reset campaign** to eliminate the remaining plaintext window: flag all not-yet-migrated accounts to reset on next login.
5. **Email-based password reset** with single-use, time-limited signed tokens once SMTP is available.
6. **Promote CSRF coverage to the GET action routes** by converting them to POST + confirmation forms.
7. **Real `role` column** on `teachers`, replacing the email-string admin check.
8. **Log rotation** (`RotatingFileHandler`) and optional SIEM/export for `auth.log`; consider an `argon2` upgrade for password hashing.
9. **Account-level lockout** in addition to IP-level, to resist distributed brute force.

---

## 5. Verification Evidence

- **Regression + security suite:** 24/24 passed — CSRF enforcement (missing token → 400), legacy plaintext login + migration, teacher login/logout, wrong-password rejection, password-change (wrong-current/weak/valid), admin add/edit/reset/delete teacher, invalid-email rejection, rate-limit lockout (blocks even correct credentials), cookie flags, non-default secret key, audit log written.
- **Render / responsive / dark-mode audit:** 18/18 passed — all public + auth + admin pages return 200 with `viewport` meta, `data-bs-theme` hook, `app.js` theme toggle, CSRF tokens present, and `app.css` retains dark-mode rules + `@media` queries.
- All tests ran against `_test_phase5.db` (throwaway copy); production DB untouched; temp artifacts removed.
