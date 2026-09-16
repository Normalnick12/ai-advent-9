"""SQLite current-state adapter. Definition is supplied, never imported from a lab."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.task_state import TaskState, TaskStateDefinition, TaskStateError, canonical_task_id

DDL = ("CREATE TABLE task_states (task_id TEXT PRIMARY KEY NOT NULL, machine_id TEXT NOT NULL, "
       "state_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ACTIVE','PAUSED')), "
       "revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=0))")


class SQLiteTaskStateStore:
    def __init__(self, path: Path, definition: TaskStateDefinition):
        self.definition = definition
        self._connection = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(path, isolation_level=None, timeout=1)
            self._connection.execute("PRAGMA synchronous=FULL")
            with self._access(write=True) as db:
                tables = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if not tables and version == 0:
                    db.execute(DDL)
                    db.execute("PRAGMA user_version=1")
                elif tables != {"task_states": DDL} or version != 1:
                    raise TaskStateError("task_state_schema_invalid", 500)
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise TaskStateError("task_state_storage_error", 500)
                for row in db.execute("SELECT * FROM task_states"):
                    self._decode(row)
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _access(self, *, write=False):
        db = self._connection
        if db is None:
            raise TaskStateError("task_state_storage_error", 500)
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                if write:
                    db.execute("COMMIT")
            except BaseException:
                if write and db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        except (sqlite3.Error, ValueError, TypeError):
            raise TaskStateError("task_state_storage_error", 500) from None

    def _decode(self, row):
        try:
            state = TaskState.model_validate(dict(zip(TaskState.model_fields, row)))
        except (ValueError, TypeError):
            raise TaskStateError("task_state_invalid", 500) from None
        self.definition.validate_state(state)
        return state

    def read(self, task_id):
        canonical_task_id(task_id)
        with self._access() as db:
            row = db.execute("SELECT * FROM task_states WHERE task_id=?", (task_id,)).fetchone()
            return self._decode(row) if row else None

    def create_initial(self, task_id):
        initial = self.definition.initial(task_id)
        with self._access(write=True) as db:
            old = self.read(task_id)
            if old is not None:
                return old
            db.execute("INSERT INTO task_states VALUES (?,?,?,?,?)", tuple(initial.model_dump().values()))
        return initial

    def compare_and_set(self, expected_revision, next_state):
        if type(expected_revision) is not int or expected_revision < 0:
            raise TaskStateError("invalid_state_revision", 422)
        self.definition.validate_state(next_state)
        with self._access(write=True) as db:
            old = self.read(next_state.task_id)
            if old is None:
                raise TaskStateError("task_state_missing", 404)
            if old.revision != expected_revision:
                raise TaskStateError("stale_task_state")
            if next_state.machine_id != old.machine_id or next_state.revision != old.revision + 1:
                raise TaskStateError("invalid_state_update", 422)
            changed = db.execute("UPDATE task_states SET state_id=?,status=?,revision=? "
                "WHERE task_id=? AND machine_id=? AND revision=?",
                (next_state.state_id, next_state.status, next_state.revision,
                 old.task_id, old.machine_id, expected_revision)).rowcount
            if changed != 1:
                raise TaskStateError("stale_task_state")
        return next_state

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
