"""Small durable state store; CSE remains the device/resource evidence source."""
import json
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self._transaction = threading.local()
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,key));
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS air_samples (
                seq INTEGER PRIMARY KEY, command_id TEXT NOT NULL, cin_ri TEXT NOT NULL, data TEXT NOT NULL,
                UNIQUE (command_id, cin_ri)
            );
            CREATE INDEX IF NOT EXISTS air_samples_command_seq ON air_samples(command_id, seq);
            """)

    @contextmanager
    def connect(self):
        active = getattr(self._transaction, "db", None)
        if active is not None:
            yield active
        else:
            with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
                yield db

    @contextmanager
    def transaction(self):
        """Commit the triggering observation, decision and pending CSE event together."""
        with self.lock, self.connect() as db:
            if getattr(self._transaction, "db", None) is not None:
                yield
                return
            db.execute("BEGIN IMMEDIATE")
            self._transaction.db = db
            try:
                yield
            finally:
                del self._transaction.db


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

    def append_air_sample(self, command_id, event):
        with self.lock, self.connect() as db:
            row = db.execute("INSERT INTO air_samples(command_id,cin_ri,data) VALUES(?,?,?) "
                             "ON CONFLICT(command_id,cin_ri) DO NOTHING RETURNING seq",
                             (command_id, event["cin_ri"], json.dumps(event))).fetchone()
            return row[0] if row else None

    def air_samples(self, command_id, after, limit):
        with self.lock, self.connect() as db:
            rows = db.execute("SELECT seq,data FROM air_samples WHERE command_id=? AND seq>? ORDER BY seq LIMIT ?",
                              (command_id, after, limit))
            return [{**json.loads(data), "sequence": seq} for seq, data in rows]
