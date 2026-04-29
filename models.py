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
