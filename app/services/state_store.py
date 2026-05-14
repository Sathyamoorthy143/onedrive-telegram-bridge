import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings, ROOT_DIR


class StateStore:
    def __init__(self, db_url: str | None = None):
        resolved = db_url or settings.database_url
        self.db_path = self._extract_sqlite_path(resolved)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @staticmethod
    def _extract_sqlite_path(db_url: str) -> str:
        if db_url.startswith('sqlite:///'):
            return db_url.replace('sqlite:///', '', 1)
        return str(ROOT_DIR / 'data' / 'app.db')

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self.connection() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT,
                    channel TEXT NOT NULL,
                    sender_id TEXT,
                    chat_id TEXT,
                    message_id TEXT,
                    text TEXT,
                    created_at TEXT,
                    metadata_json TEXT
                );

                CREATE TABLE IF NOT EXISTS command_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT,
                    channel TEXT,
                    command_name TEXT,
                    result_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS file_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    chat_id TEXT,
                    correlation_id TEXT,
                    item_index INTEGER,
                    item_id TEXT,
                    item_name TEXT,
                    item_path TEXT,
                    item_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def save_event(self, event) -> None:
        with self.connection() as conn:
            conn.execute(
                '''
                INSERT INTO events (correlation_id, channel, sender_id, chat_id, message_id, text, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    event.correlation_id,
                    event.channel,
                    event.sender_id,
                    event.chat_id,
                    event.message_id,
                    event.text,
                    event.timestamp.isoformat(),
                    json.dumps(event.metadata or {}),
                ),
            )

    def save_command_result(self, correlation_id: str, channel: str, command_name: str, result: Dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                '''
                INSERT INTO command_results (correlation_id, channel, command_name, result_json)
                VALUES (?, ?, ?, ?)
                ''',
                (correlation_id, channel, command_name, json.dumps(result)),
            )

    def cache_result_items(self, channel: str, chat_id: str, correlation_id: str, items: List[Dict[str, Any]]) -> None:
        with self.connection() as conn:
            conn.execute('DELETE FROM file_cache WHERE channel = ? AND chat_id = ?', (channel, chat_id))
            conn.executemany(
                '''
                INSERT INTO file_cache (channel, chat_id, correlation_id, item_index, item_id, item_name, item_path, item_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    (
                        channel,
                        chat_id,
                        correlation_id,
                        idx,
                        item.get('id', ''),
                        item.get('name', ''),
                        item.get('path', ''),
                        item.get('type', ''),
                    )
                    for idx, item in enumerate(items, start=1)
                ],
            )

    def get_cached_item(self, channel: str, chat_id: str, key: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            if key.isdigit():
                row = conn.execute(
                    'SELECT * FROM file_cache WHERE channel = ? AND chat_id = ? AND item_index = ?',
                    (channel, chat_id, int(key)),
                ).fetchone()
            else:
                row = conn.execute(
                    'SELECT * FROM file_cache WHERE channel = ? AND chat_id = ? AND item_id = ?',
                    (channel, chat_id, key),
                ).fetchone()
        return dict(row) if row else None

    def recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(r) for r in rows]