"""SQLite: отдельная свинка каждому игроку, действия в атомарной транзакции."""

import json
import sqlite3
import time
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from .game import Pet


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS pets (user_id TEXT PRIMARY KEY, state TEXT NOT NULL)"
            )

    def access(self, user_id: str, action: str | None = None) -> dict:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM pets WHERE user_id = ?", (user_id,)).fetchone()
            now = time.time()
            pet = Pet(**json.loads(row[0])) if row else Pet(updated_at=now)
            if action:
                pet.act(action, now)
            result = pet.snapshot(now)
            db.execute(
                "INSERT INTO pets VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state",
                (user_id, json.dumps(asdict(pet))),
            )
            return result
