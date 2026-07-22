# 📦 Final Deployment Bundle — Musaid Portal (منصة مساعد)

A single master document for taking the Musaid Portal to production. It contains
all six guides inline and links to the deeper companion docs already in the repo.

| # | Section | Companion file (full detail) |
|---|---|---|
| 1 | [Deployment Guide](#1-deployment-guide) | `DEPLOYMENT_UBUNTU.md`, `SSL_SETUP.md` |
| 2 | [MySQL Migration Guide](#2-mysql-migration-guide) | `MYSQL_MIGRATION_GUIDE.md` |
| 3 | [Environment Configuration Guide](#3-environment-configuration-guide) | `.env.example` |
| 4 | [Backup Guide](#4-backup-guide) | `BACKUP_RECOVERY.md` |
| 5 | [Recovery Guide](#5-recovery-guide) | `BACKUP_RECOVERY.md` |
| 6 | [Go-Live Checklist](#6-go-live-checklist) | `DEPLOYMENT_CHECKLIST.md` |
| — | [Production-Readiness Verdict](#production-readiness-verdict) | this document |

**Stack:** Flask 3.1 (raw SQL, no ORM) · SQLite by default / MySQL optional ·
Gunicorn + systemd + Nginx + Let's Encrypt · Bootstrap 5.3 RTL.

**Conventions:** app path `/opt/musaid/Musaid_Portal` · service user `musaid` ·
domain `musaid.example.ly` (replace with yours).

---

## 1. Deployment Guide

End-to-end on **Ubuntu 22.04 / 24.04 LTS**. Full version: `DEPLOYMENT_UBUNTU.md`.

### 1.1 Provision
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng ufw fail2ban
```
> Tesseract `ara`+`eng` packs power the handout OCR/summary feature.

### 1.2 Service user + code
```bash
sudo useradd --system --create-home --home-dir /home/musaid --shell /usr/sbin/nologin musaid
sudo mkdir -p /opt/musaid && sudo chown musaid:www-data /opt/musaid
sudo -u musaid git clone <your-repo-url> /opt/musaid/Musaid_Portal
sudo chown -R musaid:www-data /opt/musaid/Musaid_Portal
```

### 1.3 Virtualenv + dependencies
```bash
cd /opt/musaid/Musaid_Portal
sudo -u musaid python3 -m venv .venv
sudo -u musaid .venv/bin/pip install --upgrade pip
sudo -u musaid .venv/bin/pip install -r requirements.txt
```

### 1.4 Configure environment
```bash
sudo -u musaid cp .env.example .env
sudo -u musaid .venv/bin/python -c "import secrets; print('MUSAID_SECRET_KEY=' + secrets.token_hex(32))"
sudo -u musaid nano .env          # paste secret; MUSAID_ENV=production; MUSAID_COOKIE_SECURE=1
sudo chmod 600 .env
# Sanity check — must print DEBUG = False:
sudo -u musaid .venv/bin/python -c "import app; print('DEBUG =', app.DEBUG, '| ENV =', app.ENV)"
```
(See [Section 3](#3-environment-configuration-guide) for every variable.)

### 1.5 Run under Gunicorn + systemd
```bash
sudo mkdir -p /var/log/musaid && sudo chown musaid:www-data /var/log/musaid
sudo cp deploy/musaid.service /etc/systemd/system/musaid.service
sudo nano /etc/systemd/system/musaid.service     # review paths/user
sudo systemctl daemon-reload
sudo systemctl enable --now musaid
sudo systemctl status musaid --no-pager
```
App listens on the UNIX socket `/run/musaid/musaid.sock`.

### 1.6 Nginx reverse proxy
```bash
sudo cp deploy/nginx-musaid.conf /etc/nginx/sites-available/musaid
sudo nano /etc/nginx/sites-available/musaid       # set server_name + /static/ alias
sudo ln -s /etc/nginx/sites-available/musaid /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 1.7 HTTPS (Let's Encrypt) — full version `SSL_SETUP.md`
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d musaid.example.ly -d www.musaid.example.ly   # choose Redirect
```

### 1.8 Firewall
```bash
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
```

### 1.9 First-login hardening
1. Log in as `admin@musaid.edu.ly`, then immediately change the default password at `/change_password`.
2. Have each teacher log in once (lazy-migrates their legacy plaintext password to a hash), or run a reset campaign.

### 1.10 Redeploy
```bash
cd /opt/musaid/Musaid_Portal && sudo -u musaid git pull
sudo -u musaid .venv/bin/pip install -r requirements.txt
sudo systemctl restart musaid
```

---

## 2. MySQL Migration Guide

SQLite is the **default and fully supported** backend — MySQL is **optional**.
Full runbook: `MYSQL_MIGRATION_GUIDE.md`. Condensed path:

### 2.1 Create the database (utf8mb4 required for Arabic)
```sql
CREATE DATABASE musaid_portal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'musaid'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON musaid_portal.* TO 'musaid'@'localhost';
FLUSH PRIVILEGES;
```

### 2.2 Back up SQLite first
```bash
cp musaid_ist.db musaid_ist.backup.db
python export_sqlite_data.py            # -> data_export_<timestamp>.json (181 rows)
```

### 2.3 Point the env at MySQL
```bash
export DATABASE_URL="mysql+pymysql://musaid:your_strong_password@localhost/musaid_portal"
```

### 2.4 Migrate (read-only on SQLite; FK-safe; preserves IDs; idempotent)
```bash
python migrate_sqlite_to_mysql.py --dry-run     # validate, write nothing
python migrate_sqlite_to_mysql.py               # create schema + load all rows
```
It prints a row-count comparison and fails loudly on any mismatch. Expected:
`departments 2 · subjects 69 · teachers 26 · course_structure 75 · handouts 8 · notes 1 = 181`.

### 2.5 Run the app on MySQL
With the same env set, `gunicorn -c gunicorn.conf.py app:app`. The app's
backend-aware `ensure_schema()` confirms the counter columns on startup.

### 2.6 Rollback
Nothing touched the SQLite file — just unset the MySQL env vars and restart; the
app is back on `musaid_ist.db`. Keep `musaid_ist.backup.db` until MySQL is proven.

---

## 3. Environment Configuration Guide

All configuration is environment-driven (no code edits). Put values in `.env`
(auto-loaded via python-dotenv) or export them in the systemd unit. Template: `.env.example`.

### 3.1 Core / security

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `MUSAID_ENV` | rec. | `production` | `production` or `development`. Drives all prod defaults. |
| `MUSAID_SECRET_KEY` | **yes (prod)** | auto `.secret_key` file | Flask session-signing key. Generate: `python -c "import secrets;print(secrets.token_hex(32))"`. |
| `MUSAID_COOKIE_SECURE` | rec. | `1` in prod / `0` in dev | `Secure` cookie flag. Must be `1` behind HTTPS; `0` only for local HTTP. |
| `MUSAID_DEBUG` | no | `0` | Dev-only. **Ignored in production** — DEBUG can never be True in prod. |
| `MUSAID_HOST` | no | `127.0.0.1` | Bind host for the **built-in dev server only** (Gunicorn uses the socket). |
| `MUSAID_PORT` | no | `5000` | Bind port for the built-in dev server only. |

### 3.2 Database backend (SQLite default; MySQL opt-in)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Full SQLAlchemy URL, e.g. `mysql+pymysql://user:pass@localhost/musaid_portal`. If it starts with `mysql`, MySQL is used. |
| `MUSAID_DB_BACKEND` | Set to `mysql`/`mariadb` to force MySQL when not using `DATABASE_URL`. |
| `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_DB` | Discrete parts used only when `DATABASE_URL` is empty. |

> **Selection rule:** `DATABASE_URL` starting with `mysql` **or** `MUSAID_DB_BACKEND=mysql|mariadb` → MySQL. Otherwise → SQLite (zero behavior change).

### 3.3 Minimal production `.env`
```ini
MUSAID_ENV=production
MUSAID_SECRET_KEY=<64-hex-char-secret>
MUSAID_COOKIE_SECURE=1
# MySQL (optional — omit to stay on SQLite):
# DATABASE_URL=mysql+pymysql://musaid:your_password@localhost/musaid_portal
```

### 3.4 Behavior guarantees
- `DEBUG` is **forced False** in production even if `MUSAID_DEBUG=1` (verified).
- Cookies in prod are `HttpOnly` + `SameSite=Lax` + `Secure`; session lifetime 8h; upload cap 50 MB.
- `chmod 600 .env` and `.secret_key`; both are git-ignored.

---

## 4. Backup Guide

What to protect and how to snapshot it consistently. Full version: `BACKUP_RECOVERY.md`.

### 4.1 What constitutes app state
| Item | Path | Priority |
|---|---|---|
| Database | `musaid_ist.db` (SQLite) **or** the MySQL `musaid_portal` schema | **critical** |
| Uploaded files | `uploads/` | **critical** (DB rows reference these) |
| Secret key | `.secret_key` | high (loss = forced re-login) |
| Environment | `.env` | high (store securely) |
| Audit log | `logs/auth.log` | optional (forensics) |

> Code is recoverable from version control; **DB + uploads are not** — prioritize them.

### 4.2 Consistent DB snapshot
**SQLite** (online-safe — do *not* plain-`cp` a live DB):
```bash
sudo -u musaid sqlite3 /opt/musaid/Musaid_Portal/musaid_ist.db \
  ".backup '/var/backups/musaid/db-$(date +%F_%H%M).sqlite'"
```
**MySQL:**
```bash
mysqldump --single-transaction --routines --default-character-set=utf8mb4 \
  musaid_portal > /var/backups/musaid/db-$(date +%F_%H%M).sql
```

### 4.3 Full backup script + schedule
Use `/usr/local/bin/musaid-backup.sh` (in `BACKUP_RECOVERY.md`): consistent DB
snapshot + `tar` of `uploads .secret_key .env`, with 14-day retention. Schedule daily:
```bash
sudo crontab -e
30 2 * * * /usr/local/bin/musaid-backup.sh >> /var/log/musaid/backup.log 2>&1
```
**Keep at least one off-site copy** (e.g. `rclone copy /var/backups/musaid remote:musaid-backups`).

### 4.4 Verify a backup
```bash
sqlite3 db-<STAMP>.sqlite "PRAGMA integrity_check;"   # expect: ok
```

---

## 5. Recovery Guide

Restoring service from a backup. Full version: `BACKUP_RECOVERY.md`.

### 5.1 SQLite restore
```bash
sudo systemctl stop musaid
sudo -u musaid cp /var/backups/musaid/db-<STAMP>.sqlite \
                  /opt/musaid/Musaid_Portal/musaid_ist.db
sudo -u musaid tar -xzf /var/backups/musaid/files-<STAMP>.tar.gz \
                  -C /opt/musaid/Musaid_Portal           # uploads (+ .secret_key/.env)
sudo chown -R musaid:www-data /opt/musaid/Musaid_Portal
sudo systemctl start musaid && sudo systemctl status musaid --no-pager
```

### 5.2 MySQL restore
```bash
sudo systemctl stop musaid
mysql musaid_portal < /var/backups/musaid/db-<STAMP>.sql
sudo -u musaid tar -xzf /var/backups/musaid/files-<STAMP>.tar.gz -C /opt/musaid/Musaid_Portal
sudo systemctl start musaid
```

### 5.3 Post-restore verification
- [ ] Log in as admin.
- [ ] Teacher count + a few handouts open/preview correctly (DB ↔ uploads consistency).
- [ ] `logs/auth.log` is being written again.
- [ ] `PRAGMA integrity_check;` (SQLite) → `ok`.

### 5.4 Disaster-recovery hygiene
- Test a restore on staging periodically — **an untested backup is not a backup**.
- Keep `.env` / `.secret_key` backups encrypted or access-restricted.
- Document the retention window (default 14 days local + off-site).

---

## 6. Go-Live Checklist

Condensed from `DEPLOYMENT_CHECKLIST.md`. Work top to bottom.

### Secrets & config
- [ ] `MUSAID_SECRET_KEY` set via env (not relying on the auto `.secret_key`).
- [ ] `MUSAID_COOKIE_SECURE` unset or `1`.
- [ ] `.env`, `.secret_key`, `logs/`, `*.db`, `uploads/` excluded from VCS.
- [ ] Production DB backed up before first deploy.

### Transport / HTTPS
- [ ] Served **only** over HTTPS with a valid cert (Secure cookies require it).
- [ ] TLS terminated at Nginx; security headers present (HSTS, CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).

### Run as production server
- [ ] No `debug=True`; Gunicorn via systemd (`app:app`).
- [ ] **Single worker** OR move rate-limit/lockout to Redis (in-memory state is per-process).
- [ ] Proxy sets a trusted `X-Forwarded-For`.

### Filesystem & permissions
- [ ] `uploads/` writable by `musaid`, not executable by the web server.
- [ ] `logs/` writable; log rotation configured for `auth.log`.
- [ ] `.secret_key` and `.env` are `chmod 600`.

### Accounts & data
- [ ] Default admin password changed immediately after first login.
- [ ] Legacy plaintext passwords migrated (each teacher logs in once / reset campaign).
- [ ] Tesseract `ara+eng` installed if OCR summaries are needed.
- [ ] `requirements.txt` fully installed.

### Smoke test (post-deploy)
- [ ] `GET /` renders (light + dark, mobile + desktop).
- [ ] Admin + teacher login over HTTPS; logout clears session.
- [ ] POST without a CSRF token → 400.
- [ ] 6 failed logins from one IP → temporary lockout.
- [ ] `/change_password` works; old password rejected after change.
- [ ] Admin add/edit/reset/delete teacher succeed; reset shows the new password once.
- [ ] Upload + preview/download works; view/download counters increment.
- [ ] `logs/auth.log` receiving entries.

### Monitoring & maintenance
- [ ] DB backups scheduled (+ off-site).
- [ ] Periodic review of `auth.log` for `login_failure` / `csrf_failure` spikes.
- [ ] Track Flask/Werkzeug security updates.

### Recommended VPS
| Tier | Specs | Suits |
|---|---|---|
| Minimum | 1 vCPU · 1 GB RAM · 25 GB SSD | small dept, light traffic, SQLite |
| Recommended | 2 vCPU · 2–4 GB RAM · 40–80 GB SSD | typical college, OCR enabled |
| With MySQL | +1–2 GB RAM (DB), or a managed MySQL instance | multi-dept / higher concurrency |

---

## Production-Readiness Verdict

**Status: ✅ Production-ready** for its intended scope (a department/college Arabic
handouts portal behind HTTPS), once the Go-Live Checklist is completed on the host.

### Ready and verified
- **Auth/security:** PBKDF2-SHA256 password hashing with transparent on-login migration of legacy plaintext; custom CSRF on all POST forms; per-IP login rate-limiting + temporary lockout; auth audit logging; session-fixation defense; `Secure`/`HttpOnly`/`SameSite` cookies; secret key from env.
- **Production config:** `DEBUG` can never be True in production (verified); env-based config separation; WSGI entry `app:app`; Gunicorn + systemd + Nginx + Let's Encrypt artifacts all generated.
- **Data layer:** SQLite default unchanged; optional MySQL via a dual-driver layer with a tested, data-preserving migration (181 rows, FK-safe, IDs preserved). All routes verified through the abstraction (login, admin pages, upload, download, counters).
- **Ops:** backup/recovery procedures + scripts for both SQLite and MySQL; integrity checks; retention + off-site guidance.

### Conditions to satisfy at deploy time (not code gaps — environment setup)
1. Serve over HTTPS with a valid certificate (Secure cookies require it).
2. Set a strong `MUSAID_SECRET_KEY` in the environment.
3. Change the default admin password immediately after first login.
4. Run a single Gunicorn worker **or** migrate the in-memory rate-limit/lockout to Redis before scaling to multiple workers/hosts.
5. Configure log rotation for `logs/auth.log`.
6. Schedule backups with at least one off-site copy.

### Known limitations (documented, by-design or deferred — see `SECURITY_REPORT.md`)
- State-changing **GET** routes (delete/reset via SweetAlert redirects) are session-authenticated but not CSRF-protected — converting to POST is a frontend change deferred to avoid behavior risk.
- Rate-limit/lockout is in-memory per-process (Redis needed for multi-worker).
- Legacy passwords remain plaintext until the owner's first login (lazy migration by design).
- No email-based self-service password reset (no SMTP configured).
- Admin identity is the email string `admin@musaid.edu.ly`, not a dedicated role column.
- App-layer security headers/HSTS/CSP are applied at the Nginx proxy, not in Flask.

**Bottom line:** the application code is production-grade and safe to deploy. Remaining
items are standard environment/operational setup (TLS, secrets, backups, the single-worker
or Redis decision) plus a short list of explicitly documented, low-risk limitations — none
of which block a go-live for the intended user base.
