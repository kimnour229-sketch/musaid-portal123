# -*- coding: utf-8 -*-
"""
تصدير كامل بيانات SQLite إلى ملف JSON محمول (نسخة احتياطية قابلة للقراءة).

Export every row of the Musaid Portal SQLite database to a portable JSON file.
This serves two purposes:
  1. A human-readable, driver-independent backup of all data.
  2. The intermediate format used by `migrate_sqlite_to_mysql.py` is NOT this
     file — that script reads SQLite directly — but this export is handy for
     auditing exactly what will be migrated and for archival.

Usage:
    python export_sqlite_data.py [path/to/musaid_ist.db] [path/to/output.json]

Defaults: musaid_ist.db  ->  data_export_<timestamp>.json
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

# اجعل المخرجات بترميز UTF-8 على كل المنصّات (يتفادى أخطاء cp1252 على ويندوز)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# نفس ترتيب الجداول الآمن للمفاتيح الأجنبية (parents first)
TABLES = ['departments', 'subjects', 'teachers',
          'course_structure', 'handouts', 'notes']

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def export(db_path, out_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    payload = {
        '_meta': {
            'source': os.path.abspath(db_path),
            'exported_at': datetime.now().isoformat(timespec='seconds'),
            'tables': TABLES,
        }
    }
    total = 0
    for table in TABLES:
        rows = [dict(r) for r in conn.execute(f'SELECT * FROM {table}')]
        payload[table] = rows
        total += len(rows)
        print(f'  • {table:<18} {len(rows):>4} صف')
    conn.close()

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f'\n✅ تم تصدير {total} صفاً إلى:\n   {os.path.abspath(out_path)}')
    return total


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, 'musaid_ist.db')
    if len(sys.argv) > 2:
        out_path = sys.argv[2]
    else:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(BASE_DIR, f'data_export_{stamp}.json')

    if not os.path.exists(db_path):
        print(f'❌ لم يُعثر على قاعدة البيانات: {db_path}')
        sys.exit(1)

    print(f'📤 تصدير من: {db_path}\n')
    export(db_path, out_path)


if __name__ == '__main__':
    main()
