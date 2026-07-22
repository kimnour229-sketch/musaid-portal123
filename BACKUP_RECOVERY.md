# Backup & Recovery Procedures — Musaid Portal

What to protect, how to back it up consistently, and how to restore.

## What constitutes the application state

| Item | Path | Notes |
|---|---|---|
| **Database** | `/opt/musaid/Musaid_Portal/musaid_ist.db` | SQLite — the single source of truth (users, subjects, handouts metadata, counters) |
| **Uploaded files** | `/opt/musaid/Musaid_Portal/uploads/` | The actual handout files; DB rows reference these by filename |
| **Secret key** | `/opt/musaid/Musaid_Portal/.secret_key` | Losing it invalidates all active sessions (users must log in again) — not catastrophic, but back it up |
| **Environment** | `/opt/musaid/Musaid_Portal/.env` | Secrets/config; store securely |
| **Audit log** | `/opt/musaid/Musaid_Portal/logs/auth.log` | For forensics/compliance (optional) |

> Code is recoverable from version control; **the DB + uploads are not** — prioritize them.

---

## 1. Consistent database backup (online-safe)

Do **not** just `cp` the live SQLite file under load — use the SQLite backup API / `.backup`, which is safe while the app is running:

```bash
sudo -u musaid sqlite3 /opt/musaid/Musaid_Portal/musaid_ist.db \
  ".backup '/var/backups/musaid/db-$(date +%F_%H%M).sqlite'"
```

(`.dump` to SQL text is also fine: `sqlite3 musaid_ist.db .dump > backup.sql`.)

---

## 2. Full backup script

Create `/usr/local/bin/musaid-backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
APP=/opt/musaid/Musaid_Portal
DEST=/var/backups/musaid
STAMP=$(date +%F_%H%M%S)
mkdir -p "$DEST"

# 1) Consistent DB snapshot
sudo -u musaid sqlite3 "$APP/musaid_ist.db" ".backup '$DEST/db-$STAMP.sqlite'"

# 2) Uploads + secret + env (compressed)
tar -czf "$DEST/files-$STAMP.tar.gz" -C "$APP" uploads .secret_key .env 2>/dev/null || true

# 3) Retention: keep last 14 days
find "$DEST" -type f -mtime +14 -delete

echo "Backup complete: $DEST (db-$STAMP.sqlite, files-$STAMP.tar.gz)"
```

```bash
sudo install -m 0750 /usr/local/bin/musaid-backup.sh /usr/local/bin/musaid-backup.sh
sudo mkdir -p /var/backups/musaid
```

---

## 3. Schedule (daily at 02:30)

```bash
sudo crontab -e
# add:
30 2 * * * /usr/local/bin/musaid-backup.sh >> /var/log/musaid/backup.log 2>&1
```

**Off-site copy (strongly recommended):** sync `/var/backups/musaid` to object storage
or another host, e.g.:

```bash
# example with rclone to any S3-compatible bucket
0 3 * * * rclone copy /var/backups/musaid remote:musaid-backups >> /var/log/musaid/backup.log 2>&1
```

---

## 4. Restore procedure

```bash
# 1) Stop the app to avoid writes during restore
sudo systemctl stop musaid

# 2) Restore the database
sudo -u musaid cp /var/backups/musaid/db-<STAMP>.sqlite \
                  /opt/musaid/Musaid_Portal/musaid_ist.db

# 3) Restore uploads (and optionally .secret_key / .env)
sudo -u musaid tar -xzf /var/backups/musaid/files-<STAMP>.tar.gz \
                  -C /opt/musaid/Musaid_Portal

# 4) Fix ownership and restart
sudo chown -R musaid:www-data /opt/musaid/Musaid_Portal
sudo systemctl start musaid
sudo systemctl status musaid --no-pager
```

**Verify after restore:**
- Log in as admin.
- Confirm teacher count and a few handouts open/preview correctly (DB ↔ uploads consistency).
- Check `logs/auth.log` is being written again.

---

## 5. Integrity & DR checklist

- [ ] Backups run on schedule (check `/var/log/musaid/backup.log`).
- [ ] At least one **off-site** copy exists.
- [ ] Periodically **test a restore** on a staging box — an untested backup is not a backup.
- [ ] Verify a snapshot opens cleanly: `sqlite3 db-<STAMP>.sqlite "PRAGMA integrity_check;"` → `ok`.
- [ ] Document the retention window (default here: 14 days local).
- [ ] Keep `.env` / `.secret_key` backups encrypted or access-restricted.

---

## 6. Quick periodic DB integrity check

```bash
sudo -u musaid sqlite3 /opt/musaid/Musaid_Portal/musaid_ist.db "PRAGMA integrity_check;"
# expected output: ok
```
