"""SQLite meeting metadata; private media and results live beside the database."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


class Store:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database = root / "meetings.sqlite3"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                status TEXT NOT NULL, stage TEXT, error TEXT)""")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=15)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, meeting_id, title):
        with self.connect() as db:
            db.execute("INSERT INTO meetings VALUES (?,?,?,?,NULL,NULL)",
                       (meeting_id, title, datetime.now(timezone.utc).isoformat(), "queued"))
        return self.get(meeting_id)

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(zip(("id", "title", "created_at", "status", "stage", "error"), row))
        result["error"] = json.loads(result["error"]) if result["error"] else None
        return result

    def get(self, meeting_id):
        with self.connect() as db:
            return self.decode(db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone())

    def list(self):
        with self.connect() as db:
            return [self.decode(row) for row in db.execute("SELECT * FROM meetings ORDER BY created_at DESC")]

    def update(self, meeting_id, status, stage=None, error=None):
        with self.connect() as db:
            db.execute("UPDATE meetings SET status=?,stage=?,error=? WHERE id=?",
                       (status, stage, json.dumps(error, ensure_ascii=False) if error else None, meeting_id))

    def recover(self):
        error = json.dumps({"code": "interrupted", "message": "Сервер был остановлен. Загрузите запись повторно."}, ensure_ascii=False)
        with self.connect() as db:
            db.execute("UPDATE meetings SET status='failed',stage=NULL,error=? WHERE status IN ('queued','processing')", (error,))
