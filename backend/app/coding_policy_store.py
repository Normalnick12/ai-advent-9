"""Immutable task coding policy persistence; independent of other stores and providers."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID

from pydantic import field_validator

from app.coding_invariants import CodingModel, CodingPolicy
from app.invariants import RuleSource

POLICY_ID = "checkout-coding"
DEFINITION_VERSION = "coding-v1"
DDL = "CREATE TABLE task_policies (task_id TEXT PRIMARY KEY NOT NULL, record TEXT NOT NULL)"


class PolicyError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)


class TaskCodingPolicy(CodingModel):
    task_id: str
    policy_id: str = POLICY_ID
    definition_version: str = DEFINITION_VERSION
    values: CodingPolicy

    @field_validator("task_id")
    @classmethod
    def canonical(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("noncanonical identity")
        return value

    def supported(self):
        if self.policy_id != POLICY_ID or self.definition_version != DEFINITION_VERSION:
            raise PolicyError("policy_version_incompatible")

    @property
    def fingerprint(self):
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    def canonical_json(self):
        return json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    @property
    def source(self):
        return RuleSource("task", self.task_id, self.definition_version)

    def view(self):
        return {**self.model_dump(), "snapshot_id": self.fingerprint}


class CodingPolicyStore:
    def __init__(self, path: Path):
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
                    db.execute("PRAGMA user_version=14")
                elif tables != {"task_policies": DDL} or version != 14:
                    raise PolicyError("policy_schema_invalid", 500)
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise PolicyError("policy_storage_error", 500)
                for row in db.execute("SELECT task_id,record FROM task_policies"):
                    self._decode(row)
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _access(self, *, write=False):
        db = self._connection
        if db is None:
            raise PolicyError("policy_storage_error", 500)
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
        except sqlite3.Error:
            raise PolicyError("policy_storage_error", 500) from None

    @staticmethod
    def _decode(row):
        try:
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate")
                    result[key] = value
                return result
            record = TaskCodingPolicy.model_validate(json.loads(row[1], object_pairs_hook=unique))
            if row[0] != record.task_id:
                raise ValueError("identity mismatch")
        except (ValueError, TypeError):
            raise PolicyError("policy_record_invalid", 500) from None
        record.supported()
        return record

    def read(self, task_id: str):
        with self._access() as db:
            row = db.execute("SELECT task_id,record FROM task_policies WHERE task_id=?", (task_id,)).fetchone()
            return self._decode(row) if row else None

    def create(self, record: TaskCodingPolicy):
        record.supported()
        with self._access(write=True) as db:
            old = self.read(record.task_id)
            if old is not None:
                if old != record:
                    raise PolicyError("policy_immutable")
                return old
            db.execute("INSERT INTO task_policies VALUES (?,?)", (record.task_id, record.canonical_json()))
        return record

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
