# MySQL Migration Guide — Musaid Portal (منصة مساعد)

How to move the Musaid Portal from its default **SQLite** database to **MySQL / MariaDB**
without losing any data, and how to switch the running app over to it.

> **Design choice:** the app keeps using its existing raw-SQL routes. A thin
> dual-driver layer (`db.py`) lets the *same* code talk to either SQLite or
> MySQL — chosen entirely by environment variables. There is **no ORM rewrite**,
> so behavior on SQLite is byte-for-byte unchanged. MySQL is strictly opt-in.

---

## 0. What you get

| File | Purpose |
|---|---|
| `db.py` | Dual-driver layer: picks SQLite or MySQL from env; translates `?`→`%s`; wraps rows so `row[0]` **and** `row['col']` both work. |
| `schema_mysql.sql` | MySQL DDL for all 6 tables (InnoDB + utf8mb4), mirroring the SQLite schema. |
| `export_sqlite_data.py` | Dumps every row to a portable, human-readable JSON backup. |
| `migrate_sqlite_to_mysql.py` | Reads SQLite → creates schema → loads all rows into MySQL (FK-safe, preserves IDs, transactional, idempotent). |
| `musaid_ist.backup.db` | A copy of the original SQLite DB, kept as the safety net. |

---

## 1. Prerequisites

```bash
# Python drivers (already pinned in requirements.txt)
pip install SQLAlchemy==2.0.50 PyMySQL==1.2.0

# A running MySQL 8+ or MariaDB 10.4+ server
sudo apt install -y mysql-server        # Ubuntu/Debian (example)
```

Create the database and a dedicated user:

```sql
-- run as MySQL root:
CREATE DATABASE musaid_portal
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'musaid'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON musaid_portal.* TO 'musaid'@'localhost';
FLUSH PRIVILEGES;
```

> `utf8mb4` is required for full Arabic (and emoji) support. Don't use plain `utf8`.

---

## 2. Back up first (always)

```bash
# A) Keep the SQLite file itself (already done: musaid_ist.backup.db)
cp musaid_ist.db musaid_ist.backup.db

# B) Portable JSON snapshot of every table
python export_sqlite_data.py
#  -> data_export_<timestamp>.json   (181 rows across 6 tables)
```

The migration **never writes to the SQLite file** — it is read-only — so the
original always remains a valid backup.

---

## 3. Point the tools/app at MySQL (environment)

Set **either** a full URL …

```bash
# Linux/macOS
export DATABASE_URL="mysql+pymysql://musaid:your_strong_password@localhost/musaid_portal"
```
```bat
:: Windows (cmd)
set DATABASE_URL=mysql+pymysql://musaid:your_strong_password@localhost/musaid_portal
```

… **or** the discrete parts (used only when `DATABASE_URL` is empty):

```bash
export MUSAID_DB_BACKEND=mysql
export MYSQL_USER=musaid
export MYSQL_PASSWORD=your_strong_password
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DB=musaid_portal
```

Or put any of these in your `.env` (see `.env.example`) — they load automatically.

**Backend selection rule** (in `db.py`):
`DATABASE_URL` starting with `mysql` **or** `MUSAID_DB_BACKEND=mysql|mariadb` → MySQL.
Otherwise → SQLite (the default; zero behavior change).

---

## 4. Run the migration

```bash
# Dry run first — reads SQLite, validates, writes nothing:
python migrate_sqlite_to_mysql.py --dry-run

# Real migration (creates schema if missing, loads all rows):
python migrate_sqlite_to_mysql.py
```

What it does, in order:
1. Reads every row from `musaid_ist.db` (read-only).
2. Executes `schema_mysql.sql` (`CREATE TABLE IF NOT EXISTS`).
3. Inserts rows in **FK-safe order** — departments → subjects → teachers →
   course_structure → handouts → notes — **preserving the original `id`s** so
   every foreign key stays valid. Uses `INSERT IGNORE` so re-running is safe.
4. Re-syncs each table's `AUTO_INCREMENT` to `MAX(id)+1`.
5. Prints a row-count comparison (MySQL vs. SQLite) for every table and fails
   loudly if any count doesn't match.

Useful flags:
- `--truncate` — empty the MySQL tables before loading (clean re-import).
- `--dry-run` — read + validate only, no writes.
- A custom SQLite path can be passed as the first positional argument.

Expected tail of a successful run:
```
🔎 التحقق من الأعداد في MySQL:
   ✓ departments        MySQL=   2  SQLite=   2
   ✓ subjects           MySQL=  69  SQLite=  69
   ✓ teachers           MySQL=  26  SQLite=  26
   ✓ course_structure   MySQL=  75  SQLite=  75
   ✓ handouts           MySQL=   8  SQLite=   8
   ✓ notes              MySQL=   1  SQLite=   1
✅ اكتمل الترحيل بنجاح — تطابقت كل الأعداد. لم تُفقد أي بيانات.
```

---

## 5. Start the app on MySQL

With the same env vars set (step 3), just start the app as usual:

```bash
# development
python app.py

# production
gunicorn -c gunicorn.conf.py app:app
```

On startup the app calls `ensure_schema()`, which is backend-aware: on MySQL it
checks `information_schema.COLUMNS` and adds `view_count` / `download_count` if
they're missing (they already exist from `schema_mysql.sql`). The admin bootstrap
block also runs through the same layer and inserts the default admin only if absent.

---

## 6. Post-migration verification checklist

- [ ] Home page `/` loads and shows stats.
- [ ] Search `/search?q=...` returns results.
- [ ] A teacher can log in; an existing **plaintext** password still works and is
      transparently re-hashed on that first login (lazy migration preserved).
- [ ] Admin (`admin@musaid.edu.ly`) can log in and open `/admin`,
      `/admin/subjects`, `/admin/monitor`, `/admin/reports`.
- [ ] Upload a file as a teacher → a new `handouts` row appears.
- [ ] Open a handout (`/download/<file>`) → `view_count` increments;
      `/download/<file>?dl=1` → `download_count` increments.
- [ ] Counts render on the home/results/teacher cards.
- [ ] CSRF tokens present on all POST forms; rate-limiting/lockout still active.

Quick DB sanity check:

```bash
mysql -u musaid -p musaid_portal -e "
  SELECT 'departments' t, COUNT(*) n FROM departments UNION ALL
  SELECT 'subjects', COUNT(*) FROM subjects UNION ALL
  SELECT 'teachers', COUNT(*) FROM teachers UNION ALL
  SELECT 'course_structure', COUNT(*) FROM course_structure UNION ALL
  SELECT 'handouts', COUNT(*) FROM handouts UNION ALL
  SELECT 'notes', COUNT(*) FROM notes;"
```

---

## 7. Rollback (back to SQLite)

Because nothing touched the SQLite file, rollback is just **unsetting the env**:

```bash
unset DATABASE_URL MUSAID_DB_BACKEND MYSQL_USER MYSQL_PASSWORD MYSQL_HOST MYSQL_PORT MYSQL_DB
# (and remove/comment the same lines in .env)
python app.py     # back on musaid_ist.db, unchanged
```

Keep `musaid_ist.backup.db` until you've run on MySQL in production for a while.

---

## 8. Schema mapping reference (SQLite → MySQL)

| SQLite | MySQL | Why |
|---|---|---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `INT AUTO_INCREMENT PRIMARY KEY` | Native auto-increment |
| `TEXT … UNIQUE` (dept_name, subject_name, email) | `VARCHAR(255)` + `UNIQUE KEY` | MySQL can't index unbounded `TEXT` |
| other `TEXT` (title, notes, file_path …) | `TEXT` | Free-form bodies |
| `BOOLEAN DEFAULT 0` (is_shared) | `TINYINT(1) DEFAULT 0` | MySQL boolean |
| `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` | `DATETIME DEFAULT CURRENT_TIMESTAMP` | Stable default |
| `notes.semester TEXT` | `VARCHAR(50)` | Legacy table; kept as-is to preserve data |
| (engine/charset) | `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` | FK support + full Arabic |

All foreign keys (`course_structure`, `handouts`) are recreated in MySQL.

---

## 9. Production notes

- **Connection pooling** is handled by SQLAlchemy in `db.py`
  (`pool_pre_ping=True` to drop dead connections, `pool_recycle=3600`).
- For backups on MySQL, switch the `BACKUP_RECOVERY.md` procedure from
  `sqlite3 .backup` to `mysqldump --single-transaction --routines musaid_portal`.
- The in-memory login lockout is still per-process — unchanged by this migration;
  it remains a "move to Redis before running multiple Gunicorn workers" item.
- Store the DB password only in `.env` / a secrets manager — never in code or VCS.
