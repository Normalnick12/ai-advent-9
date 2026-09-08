from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from app.conversation_store import ConversationStorageError, SessionNotFound, StoredConversation
from app.llm_client import ConversationMessage


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / ".local" / "agent" / "conversations.sqlite3"


class SQLiteConversationStore:
    """One connection, owned by the single backend event-loop thread."""

    def __init__(self, path: Path) -> None:
        self._connection: sqlite3.Connection | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            options = {"isolation_level": None, "timeout": 1.0}
            if hasattr(sqlite3, "LEGACY_TRANSACTION_CONTROL"):
                options["autocommit"] = sqlite3.LEGACY_TRANSACTION_CONTROL
            self._connection = sqlite3.connect(path, **options)
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            with self._transaction() as db:
                db.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY NOT NULL)")
                db.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        session_id TEXT NOT NULL,
                        position INTEGER NOT NULL CHECK(position >= 0),
                        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        PRIMARY KEY(session_id, position),
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                    )
                """)
                self._check_schema(db)
        except (OSError, sqlite3.Error, ConversationStorageError):
            self.close()
            raise ConversationStorageError from None

    @staticmethod
    def _check_schema(db: sqlite3.Connection) -> None:
        expected = {
            "sessions": [("session_id", "TEXT", 1, 1)],
            "messages": [("session_id", "TEXT", 1, 1), ("position", "INTEGER", 1, 2),
                         ("role", "TEXT", 1, 0), ("content", "TEXT", 1, 0)],
        }
        for table, columns in expected.items():
            actual = [(row[1], row[2], row[3], row[5]) for row in db.execute(f"PRAGMA table_info({table})")]
            if actual != columns:
                raise ConversationStorageError
        keys = list(db.execute("PRAGMA foreign_key_list(messages)"))
        if len(keys) != 1 or keys[0][2:5] != ("sessions", "session_id", "session_id") or keys[0][6] != "CASCADE":
            raise ConversationStorageError

    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ConversationStorageError
        return self._connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = self._db()
        try:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                try:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                except sqlite3.Error:
                    self.close()
                raise
        except sqlite3.Error:
            raise ConversationStorageError from None

    def create_session(self, session_id: str) -> None:
        with self._transaction() as db:
            db.execute("INSERT INTO sessions(session_id) VALUES (?)", (session_id,))

    def load_session(self, session_id: str) -> StoredConversation | None:
        try:
            db = self._db()
            if db.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone() is None:
                return None
            rows = db.execute(
                "SELECT position, role, content FROM messages WHERE session_id=? ORDER BY position", (session_id,),
            ).fetchall()
        except sqlite3.Error:
            raise ConversationStorageError from None
        if len(rows) % 2:
            raise ConversationStorageError
        history = []
        for position, (saved_position, role, content) in enumerate(rows):
            expected_role = "user" if position % 2 == 0 else "assistant"
            if saved_position != position or role != expected_role or not isinstance(content, str):
                raise ConversationStorageError
            history.append(ConversationMessage(expected_role, content))
        return StoredConversation(session_id, tuple(history))

    def append_turn(
        self, session_id: str, user: ConversationMessage, assistant: ConversationMessage,
    ) -> None:
        if user.role != "user" or assistant.role != "assistant":
            raise ConversationStorageError
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone() is None:
                raise SessionNotFound
            position = db.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM messages WHERE session_id=?", (session_id,),
            ).fetchone()[0]
            db.executemany(
                "INSERT INTO messages(session_id, position, role, content) VALUES (?, ?, ?, ?)",
                [(session_id, position, user.role, user.content),
                 (session_id, position + 1, assistant.role, assistant.content)],
            )

    def delete_session(self, session_id: str) -> None:
        with self._transaction() as db:
            db.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()
