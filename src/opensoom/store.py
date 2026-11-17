"""Small durable state store; CSE remains the device/resource evidence source."""
import json
import sqlite3
import threading
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,key));
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def put(self, kind, key, data):
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,key) DO UPDATE SET data=excluded.data", (kind, key, json.dumps(data)))
        return data

    def get(self, kind, key, default=None):
        with self.lock, self.connect() as db:
            row = db.execute("SELECT data FROM records WHERE kind=? AND key=?", (kind, key)).fetchone()
        return json.loads(row[0]) if row else default

    def list(self, kind):
        with self.lock, self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM records WHERE kind=? ORDER BY rowid", (kind,))]

    def delete(self, kind, key):
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM records WHERE kind=? AND key=?", (kind, key))

    def event(self, data):
        with self.lock, self.connect() as db:
            result = db.execute("INSERT INTO events(data) VALUES (?)", (json.dumps(data),))
            return {**data, "id": result.lastrowid}

    def events(self, limit=150):
        with self.lock, self.connect() as db:
            return [{**json.loads(row[1]), "id": row[0]} for row in db.execute("SELECT seq,data FROM events ORDER BY seq DESC LIMIT ?", (limit,))][::-1]
