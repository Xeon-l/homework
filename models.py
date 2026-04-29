import sqlite3
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        detail TEXT DEFAULT '',
        script_path TEXT NOT NULL,
        accept_path TEXT NOT NULL,
        assignee TEXT NOT NULL,
        design TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        log TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_bindings():
    return load_config().get('bindings', [])


def verify_password(password):
    return load_config().get('password', '') == password
