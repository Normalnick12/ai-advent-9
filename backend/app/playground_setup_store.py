"""Durable creation choices, not an operation journal."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Literal

from app.memory_store import strict_json
from app.profiles import FrozenModel, Identity, ProfileFields, ActiveProfileBinding
from app.playground_coding import CodingTaskConfiguration
from app.playground_models import PlaygroundError

DDL = "CREATE TABLE setups (task_id TEXT PRIMARY KEY NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','ready')), record TEXT NOT NULL)"


class SetupRecord(FrozenModel):
    version: Literal["playground-setup-v1"] = "playground-setup-v1"
    machine_id: Literal["checkout-v2"] = "checkout-v2"
    configuration: CodingTaskConfiguration
    profile_fields: ProfileFields
    profile_version: Literal["profiles-v1"] = "profiles-v1"
    owner_id: Identity
    task_id: Identity
    session_id: Identity
    previous_snapshot: str | None
    previous_profile_binding: ActiveProfileBinding
    status: Literal["pending", "ready"] = "pending"


class PlaygroundSetupStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=1)
        try:
            self.db.execute("PRAGMA synchronous=FULL")
            with self.access(write=True) as db:
                tables = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if not tables and version == 0:
                    db.execute(DDL)
                    db.execute("PRAGMA user_version=15")
                elif tables != {"setups": DDL} or version != 15:
                    raise PlaygroundError("setup_schema_invalid", 500)
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise PlaygroundError("setup_storage_error", 500)
                for row in db.execute("SELECT * FROM setups"):
                    self.decode(row)
                self.pending()
        except BaseException:
            self.close()
            raise

    @contextmanager
    def access(self, write=False):
        try:
            if write:
                self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
                if write:
                    self.db.execute("COMMIT")
            except BaseException:
                if write and self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise
        except sqlite3.Error:
            raise PlaygroundError("setup_storage_error", 500) from None

    @staticmethod
    def decode(row):
        try:
            record = SetupRecord.model_validate(strict_json(row[2]))
            if (record.task_id, record.status) != row[:2] or record.previous_profile_binding.owner_id != record.owner_id:
                raise ValueError("inconsistent setup")
            return record
        except (ValueError, TypeError):
            raise PlaygroundError("setup_record_invalid", 500) from None

    def read(self, task_id):
        with self.access() as db:
            row = db.execute("SELECT * FROM setups WHERE task_id=?", (task_id,)).fetchone()
            return self.decode(row) if row else None

    def pending(self):
        with self.access() as db:
            rows = db.execute("SELECT * FROM setups WHERE status='pending'").fetchall()
            if len(rows) > 1:
                raise PlaygroundError("setup_record_invalid", 500)
            return self.decode(rows[0]) if rows else None

    def create(self, record):
        with self.access(write=True) as db:
            if self.pending() or self.read(record.task_id):
                raise PlaygroundError("setup_conflict")
            db.execute("INSERT INTO setups VALUES (?,?,?)",
                       (record.task_id, record.status, record.model_dump_json()))
        return record

    def ready(self, record):
        with self.access(write=True) as db:
            old = self.read(record.task_id)
            if old is None or old.model_copy(update={"status": record.status}) != record:
                raise PlaygroundError("setup_conflict")
            ready = record.model_copy(update={"status": "ready"})
            db.execute("UPDATE setups SET status='ready',record=? WHERE task_id=?",
                       (ready.model_dump_json(), record.task_id))
        return ready

    def close(self):
        self.db.close()
