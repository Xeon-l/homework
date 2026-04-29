import sqlite3
import json
import os
import sys
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

# check_same_thread=False is intentional — models are called from both
# Flask request threads and background ThreadPoolExecutor workers.
# WAL mode ensures safe concurrent reads during writes.


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate(conn):
    cols = {row[1] for row in conn.execute('PRAGMA table_info(task)').fetchall()}
    if 'user' not in cols and 'assignee' in cols:
        conn.execute('ALTER TABLE task RENAME COLUMN assignee TO user')
    if 'start_date' not in cols:
        conn.execute('ALTER TABLE task ADD COLUMN start_date TEXT DEFAULT ""')
    if 'end_date' not in cols:
        conn.execute('ALTER TABLE task ADD COLUMN end_date TEXT DEFAULT ""')


def init_db():
    try:
        conn = get_db()
        conn.execute('''CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            detail TEXT DEFAULT '',
            script_path TEXT DEFAULT '',
            accept_path TEXT DEFAULT '',
            "user" TEXT NOT NULL DEFAULT '',
            design TEXT NOT NULL,
            status TEXT DEFAULT 'Running'
                CHECK(status IN ('Pending','Running','Success','Failed')),
            log TEXT DEFAULT '',
            start_date TEXT DEFAULT '',
            end_date TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        _migrate(conn)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        sys.exit(f'Failed to init database: {e}')


def load_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.exit(f'Failed to load config.json: {e}')


def get_bindings():
    return load_config().get('bindings', [])


def verify_password(password):
    return load_config().get('password', '') == password


def create_task(name, detail, script_path, accept_path, user, design,
                start_date='', end_date=''):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO task (name, detail, script_path, accept_path, "user", design,'
        ' status, log, start_date, end_date, created_at, updated_at)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (name, detail, script_path, accept_path, user, design,
         'Running', '', start_date, end_date, now, now)
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_tasks(status=None):
    conn = get_db()
    if status:
        rows = conn.execute(
            'SELECT * FROM task WHERE status = ? ORDER BY id DESC', (status,)
        ).fetchall()
    else:
        rows = conn.execute('SELECT * FROM task ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM task WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


_TASK_COLUMNS = {'name', 'detail', 'script_path', 'accept_path',
                  'user', 'design', 'status', 'log',
                  'start_date', 'end_date', 'updated_at'}


def update_task(task_id, **kwargs):
    if not kwargs:
        return
    bad = set(kwargs) - _TASK_COLUMNS
    if bad:
        raise ValueError(f'Invalid columns: {bad}')
    # quote "user" since it's a reserved word
    sets = ', '.join(
        f'"{k}" = ?' if k == 'user' else f'{k} = ?' for k in kwargs
    )
    vals = list(kwargs.values()) + [task_id]
    conn = get_db()
    conn.execute(f'UPDATE task SET {sets} WHERE id = ?', vals)
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_db()
    conn.execute('DELETE FROM task WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()


def get_tasks_since(timestamp):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM task WHERE updated_at > ? ORDER BY id DESC', (timestamp,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_status_counts():
    conn = get_db()
    counts = {}
    for s in ['Pending', 'Running', 'Success', 'Failed']:
        counts[s] = conn.execute(
            'SELECT COUNT(*) FROM task WHERE status = ?', (s,)
        ).fetchone()[0]
    conn.close()
    return counts
