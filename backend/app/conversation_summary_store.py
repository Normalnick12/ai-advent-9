from dataclasses import dataclass
import sqlite3
from typing import Protocol

from app.conversation_store import ConversationStorageError
from app.llm_client import ConversationMessage


class SummaryStateError(Exception):
    def __init__(self, code="summary_state_invalid"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SummaryState:
    session_id: str
    summary_text: str
    covered_through_position: int
    config_version: str


def validate_summary(summary, history, version):
    if len(history) % 2 or any(m.role != ("user" if i % 2 == 0 else "assistant")
                              or not isinstance(m.content, str) for i, m in enumerate(history)):
        raise SummaryStateError()
    if summary is None:
        return
    if summary.config_version != version:
        raise SummaryStateError("summary_config_mismatch")
    b = summary.covered_through_position
    if (not isinstance(summary.summary_text, str) or not summary.summary_text.strip()
            or type(b) is not int or b < 1 or b % 2 != 1 or b >= max(0, len(history)-4)):
        raise SummaryStateError()


class ConversationSummaryStore(Protocol):
    def load(self, session_id: str, history: tuple[ConversationMessage, ...]) -> SummaryState | None: ...
    def save(self, summary: SummaryState, history: tuple[ConversationMessage, ...],
             previous: SummaryState | None) -> None: ...


class SQLiteConversationSummaryStore:
    """Narrow adapter; the raw store owns the shared connection and transactions."""
    def __init__(self, connection, transaction, version):
        self._connection = connection
        self._transaction = transaction
        self.version = version
        with transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS conversation_summaries (
                session_id TEXT PRIMARY KEY NOT NULL,
                summary_text TEXT NOT NULL,
                covered_through_position INTEGER NOT NULL,
                config_version TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE)""")
            expected = [("session_id", "TEXT", 1, 1), ("summary_text", "TEXT", 1, 0),
                        ("covered_through_position", "INTEGER", 1, 0), ("config_version", "TEXT", 1, 0)]
            actual = [(r[1], r[2], r[3], r[5]) for r in db.execute("PRAGMA table_info(conversation_summaries)")]
            keys = list(db.execute("PRAGMA foreign_key_list(conversation_summaries)"))
            if actual != expected or len(keys) != 1 or keys[0][2:5] != (
                    "sessions", "session_id", "session_id") or keys[0][6] != "CASCADE":
                raise ConversationStorageError

    def load(self, session_id, history):
        try:
            row = self._connection().execute(
                "SELECT session_id, summary_text, covered_through_position, config_version "
                "FROM conversation_summaries WHERE session_id=?", (session_id,)).fetchone()
        except sqlite3.Error:
            raise ConversationStorageError from None
        state = SummaryState(*row) if row else None
        validate_summary(state, history, self.version)
        return state

    def save(self, summary, history, previous):
        validate_summary(summary, history, self.version)
        with self._transaction() as db:
            if self.load(summary.session_id, history) != previous:
                raise SummaryStateError()
            db.execute("""INSERT INTO conversation_summaries VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET summary_text=excluded.summary_text,
                covered_through_position=excluded.covered_through_position,
                config_version=excluded.config_version""",
                (summary.session_id, summary.summary_text, summary.covered_through_position,
                 summary.config_version))
