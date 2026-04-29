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


def init_db():
    try:
        conn = get_db()
        conn.execute('''CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            detail TEXT DEFAULT '',
            script_path TEXT NOT NULL,
            accept_path TEXT NOT NULL,
            assignee TEXT NOT NULL,
            design TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
                CHECK(status IN ('Pending','Running','Success','Failed')),
            log TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
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


def create_task(name, detail, script_path, accept_path, assignee, design):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO task (name, detail, script_path, accept_path, assignee, design, status, log, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (name, detail, script_path, accept_path, assignee, design, 'Pending', '', now, now)
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_tasks(status=None):
    conn = get_db()
    if status:
        rows = conn.execute('SELECT * FROM task WHERE status = ? ORDER BY id DESC', (status,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM task ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM task WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_task(task_id, **kwargs):
    if not kwargs:
        return
    sets = ', '.join(f'{k} = ?' for k in kwargs)
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
    rows = conn.execute('SELECT * FROM task WHERE updated_at > ? ORDER BY id DESC', (timestamp,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_status_counts():
    conn = get_db()
    counts = {}
    for s in ['Pending', 'Running', 'Success', 'Failed']:
        counts[s] = conn.execute('SELECT COUNT(*) FROM task WHERE status = ?', (s,)).fetchone()[0]
    conn.close()
    return counts
