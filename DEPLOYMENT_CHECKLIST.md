# Deployment Checklist — Musaid Portal

Production go-live checklist after Phase 5 hardening. Work top-to-bottom; nothing here changes application behavior — it configures the environment around it.

---

## 1. Secrets & Configuration (required)

- [ ] **Set a strong secret key via environment** — do **not** rely on the auto-generated `.secret_key` file in production:
  ```bash
  export MUSAID_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
  ```
- [ ] Confirm `MUSAID_COOKIE_SECURE` is **unset or `1`** in production (secure cookies ON). Only set `MUSAID_COOKIE_SECURE=0` for local HTTP development.
- [ ] Ensure `.secret_key`, `logs/`, `*.db`, and `uploads/` are **excluded from version control** (see `.gitignore`).
- [ ] Back up the production database (`musaid_ist.db`) before first deploy.

## 2. HTTPS / Transport (required — cookies are Secure)

- [ ] Serve the app **only over HTTPS** (valid TLS cert). With `SESSION_COOKIE_SECURE=True`, login will not work over plain HTTP.
- [ ] Terminate TLS at a reverse proxy (Nginx / Caddy / Apache) in front of the app.
- [ ] Add security headers at the proxy (or via Flask-Talisman):
  - [ ] `Strict-Transport-Security` (HSTS)
  - [ ] `Content-Security-Policy`
  - [ ] `X-Content-Type-Options: nosniff`
  - [ ] `X-Frame-Options: DENY` (or CSP `frame-ancestors`)
  - [ ] `Referrer-Policy: strict-origin-when-cross-origin`

## 3. Run as a Production Server (required)

- [ ] **Disable debug mode** — never run `app.run(debug=True)` in production. Use a WSGI server:
  ```bash
  # Windows-friendly:
  pip install waitress
  waitress-serve --listen=127.0.0.1:5000 app:app
  # or Linux:
  pip install gunicorn
  gunicorn -w 1 -b 127.0.0.1:5000 app:app
  ```
- [ ] **Use a single worker (`-w 1`) OR migrate rate-limit/lockout state to Redis** — the in-memory lockout is per-process and won't be shared across multiple workers.
- [ ] If behind a proxy, ensure it sets a **trusted** `X-Forwarded-For` (used for audit/rate-limit IP) and consider `ProxyFix`.

## 4. Filesystem & Permissions

- [ ] `uploads/` is writable by the app user and **not directly executable** by the web server.
- [ ] `logs/` is writable; set up **log rotation** for `logs/auth.log` (e.g. logrotate or switch to `RotatingFileHandler`).
- [ ] `.secret_key` is readable only by the app user (`chmod 600` on Linux).
- [ ] Verify `MAX_CONTENT_LENGTH` (50 MB) suits expected handout sizes; adjust if needed.

## 5. Accounts & Data

- [ ] **Change the default admin password** (`admin@musaid.edu.ly`) immediately after first login via `/change_password`.
- [ ] (Recommended) Run a **force-reset campaign** so remaining legacy plaintext passwords migrate — or have each teacher log in once to trigger migration.
- [ ] Confirm `Tesseract` + language packs (`ara+eng`) are installed if OCR summaries are needed (`pytesseract`).
- [ ] Confirm all `requirements` are installed: Flask, werkzeug, pypdf, pytesseract, python-docx, python-pptx, Pillow, PyMuPDF (fitz).

## 6. Smoke Test (post-deploy)

- [ ] `GET /` renders (light + dark, mobile + desktop).
- [ ] Login works over HTTPS for admin and a teacher; logout clears session.
- [ ] A POST form **without** a CSRF token is rejected (400).
- [ ] 6 failed logins from one IP trigger the temporary lockout message.
- [ ] `/change_password` updates the password; old password no longer works.
- [ ] Admin add / edit / reset / delete teacher all succeed; reset shows the new password once.
- [ ] File upload + preview/download works; counters increment.
- [ ] `logs/auth.log` is receiving entries (login_success, etc.).

## 7. Monitoring & Maintenance

- [ ] Schedule regular DB backups.
- [ ] Periodically review `logs/auth.log` for repeated `login_failure` / `csrf_failure` spikes.
- [ ] Track dependency security updates (Flask/Werkzeug especially).

---

### Environment variables summary

| Variable | Purpose | Production value |
|---|---|---|
| `MUSAID_SECRET_KEY` | Flask session signing key | strong 64-hex-char secret (required) |
| `MUSAID_COOKIE_SECURE` | Toggle `Secure` cookie flag | unset or `1` (set `0` only for local HTTP) |
