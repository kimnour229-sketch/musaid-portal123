# -*- coding: utf-8 -*-
"""
ترحيل بيانات منصة مساعد من SQLite إلى MySQL دون فقدان أي بيانات.

Migrate the Musaid Portal data from SQLite to MySQL/MariaDB.

What it does (idempotent + transactional, FK-safe):
  1. Reads every row from the SQLite database (default: musaid_ist.db).
  2. Creates the MySQL schema from schema_mysql.sql (CREATE TABLE IF NOT EXISTS).
  3. Inserts all rows in foreign-key-safe order, PRESERVING the original
     primary-key ids so every FK reference stays valid.
  4. Wraps the data load in a single transaction — all-or-nothing.
  5. Re-syncs AUTO_INCREMENT so new inserts continue after the max id.

Connection target is taken from the environment, exactly like the app:
    DATABASE_URL=mysql+pymysql://user:password@localhost/musaid_portal
  or the discrete MYSQL_USER / MYSQL_PASSWORD / MYSQL_HOST / MYSQL_PORT / MYSQL_DB
(see db.database_url()).

Usage:
    # configure env first, e.g.:
    set DATABASE_URL=mysql+pymysql://musaid:secret@localhost/musaid_portal   (Windows)
    export DATABASE_URL=mysql+pymysql://musaid:secret@localhost/musaid_portal (Linux)

    python migrate_sqlite_to_mysql.py [path/to/musaid_ist.db]

Options:
    --truncate   empty the MySQL tables before loading (clean re-run)
    --dry-run    read SQLite + validate, but do not write to MySQL

The original SQLite file is never modified (read-only) and remains the backup.
"""
import os
import sys
import sqlite3

# اجعل المخرجات بترميز UTF-8 على كل المنصّات (يتفادى أخطاء cp1252 على ويندوز)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# FK-safe insertion order: parents before children
TABLE_ORDER = ['departments', 'subjects', 'teachers',
               'course_structure', 'handouts', 'notes']

# Explicit column lists (stable order; ids included to preserve references)
COLUMNS = {
    'departments':      ['id', 'dept_name'],
    'subjects':         ['id', 'subject_name', 'is_shared'],
    'teachers':         ['id', 'full_name', 'email', 'password'],
    'course_structure': ['id', 'dept_id', 'subject_id', 'semester'],
    'handouts':         ['id', 'teacher_id', 'subject_id', 'dept_id', 'semester',
                         'title', 'notes', 'file_path', 'upload_date',
                         'view_count', 'download_count'],
    'notes':            ['id', 'title', 'subject_name', 'teacher_name',
                         'file_path', 'dept_id', 'semester'],
}


def read_sqlite(db_path):
    """يقرأ كل الصفوف من SQLite إلى قاموس {table: [rows...]}"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    data = {}
    for table in TABLE_ORDER:
        cols = COLUMNS[table]
        rows = []
        for r in conn.execute(f'SELECT {", ".join(cols)} FROM {table}'):
            rows.append(tuple(r[c] for c in cols))
        data[table] = rows
    conn.close()
    return data


def load_schema_sql():
    path = os.path.join(BASE_DIR, 'schema_mysql.sql')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def split_statements(sql_text):
    """تقسيم بسيط لعبارات SQL على ';' مع تجاهل التعليقات والفراغات."""
    stmts = []
    for raw in sql_text.split(';'):
        line = '\n'.join(
            ln for ln in raw.splitlines()
            if ln.strip() and not ln.strip().startswith('--')
        ).strip()
        if line:
            stmts.append(line)
    return stmts


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    truncate = '--truncate' in args
    positional = [a for a in args if not a.startswith('--')]
    db_path = positional[0] if positional else os.path.join(BASE_DIR, 'musaid_ist.db')

    if not os.path.exists(db_path):
        print(f'❌ لم يُعثر على قاعدة SQLite: {db_path}')
        sys.exit(1)

    print(f'📥 قراءة البيانات من SQLite: {db_path}')
    data = read_sqlite(db_path)
    total = sum(len(v) for v in data.values())
    for t in TABLE_ORDER:
        print(f'  • {t:<18} {len(data[t]):>4} صف')
    print(f'  المجموع: {total} صف\n')

    if dry_run:
        print('🧪 وضع التجربة (--dry-run): لن تتم أي كتابة إلى MySQL. تم التحقق من القراءة بنجاح.')
        return

    # استيراد طبقة قاعدة البيانات للحصول على عنوان MySQL والمحرّك
    import db as dblayer
    if not dblayer.is_mysql():
        print('❌ لم يُضبط هدف MySQL في البيئة.')
        print('   اضبط DATABASE_URL=mysql+pymysql://user:pass@host/dbname  (أو متغيرات MYSQL_*)')
        print('   ثم أعد التشغيل. تفاصيل في MYSQL_MIGRATION_GUIDE.md')
        sys.exit(2)

    from sqlalchemy import text
    engine = dblayer.get_engine()
    print(f'🛢️  هدف MySQL: {dblayer.database_url().split("@")[-1]}')

    # 1) إنشاء المخطط
    print('🏗️  إنشاء المخطط (CREATE TABLE IF NOT EXISTS) ...')
    schema_stmts = split_statements(load_schema_sql())
    with engine.begin() as conn:
        for stmt in schema_stmts:
            conn.execute(text(stmt))
    print('   ✓ المخطط جاهز.')

    # 2) تحميل البيانات داخل معاملة واحدة (الكل أو لا شيء)
    print('⬇️  تحميل البيانات ...')
    with engine.begin() as conn:
        conn.execute(text('SET FOREIGN_KEY_CHECKS = 0'))

        if truncate:
            for t in reversed(TABLE_ORDER):
                conn.execute(text(f'TRUNCATE TABLE {t}'))
            print('   ✓ تم تفريغ الجداول (--truncate).')

        for t in TABLE_ORDER:
            cols = COLUMNS[t]
            rows = data[t]
            if not rows:
                continue
            placeholders = ', '.join(f':{c}' for c in cols)
            collist = ', '.join(cols)
            # INSERT IGNORE يجعل العملية idempotent على المفاتيح المكررة
            sql = text(f'INSERT IGNORE INTO {t} ({collist}) VALUES ({placeholders})')
            params = [dict(zip(cols, row)) for row in rows]
            conn.execute(sql, params)
            print(f'   ✓ {t:<18} {len(rows):>4} صف')

        # 3) إعادة ضبط AUTO_INCREMENT بعد أكبر معرّف
        for t in TABLE_ORDER:
            res = conn.execute(text(f'SELECT COALESCE(MAX(id), 0) AS m FROM {t}'))
            max_id = list(res)[0][0]
            conn.execute(text(f'ALTER TABLE {t} AUTO_INCREMENT = {max_id + 1}'))

        conn.execute(text('SET FOREIGN_KEY_CHECKS = 1'))

    # 4) التحقق من الأعداد
    print('\n🔎 التحقق من الأعداد في MySQL:')
    ok = True
    with engine.connect() as conn:
        for t in TABLE_ORDER:
            got = list(conn.execute(text(f'SELECT COUNT(*) FROM {t}')))[0][0]
            want = len(data[t])
            mark = '✓' if got == want else '✗'
            if got != want:
                ok = False
            print(f'   {mark} {t:<18} MySQL={got:>4}  SQLite={want:>4}')

    if ok:
        print('\n✅ اكتمل الترحيل بنجاح — تطابقت كل الأعداد. لم تُفقد أي بيانات.')
        print('   ملف SQLite الأصلي لم يُعدَّل ويبقى نسخة احتياطية.')
    else:
        print('\n⚠️  تحذير: بعض الأعداد غير متطابقة. راجع السجل أعلاه.')
        sys.exit(3)


if __name__ == '__main__':
    main()
