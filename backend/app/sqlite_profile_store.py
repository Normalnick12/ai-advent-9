"""SQLite adapter for ProfileStore; does not know where Memory is stored."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.profiles import ActiveProfileBinding, AgentProfile, ProfileError, ProfileFields, canonical_id


DDL = (
    "CREATE TABLE profiles (owner_id TEXT NOT NULL, profile_id TEXT PRIMARY KEY NOT NULL, data TEXT NOT NULL, UNIQUE(owner_id,profile_id))",
    "CREATE TABLE profile_bindings (owner_id TEXT PRIMARY KEY NOT NULL, active_profile_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1), FOREIGN KEY(owner_id,active_profile_id) REFERENCES profiles(owner_id,profile_id))",
)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


class SQLiteProfileStore:
    def __init__(self, path: Path):
        self._connection = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(path, isolation_level=None, timeout=1)
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA synchronous=FULL")
            with self._access(write=True) as db:
                tables = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if not tables and version == 0:
                    for statement in DDL:
                        db.execute(statement)
                    db.execute("PRAGMA user_version=1")
                elif tables != {s.split()[2]: s for s in DDL} or version != 1:
                    raise ProfileError("profile_schema_invalid", 500)
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("invalid database")
                if db.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("invalid references")
                for row in db.execute("SELECT owner_id,profile_id,data FROM profiles"):
                    self._decode(row)
                for owner, in db.execute("SELECT owner_id FROM profile_bindings"):
                    self.read_binding(owner)
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _access(self, *, write=False):
        if self._connection is None:
            raise ProfileError("profile_storage_error", 500)
        db = self._connection
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
            raise ProfileError("profile_storage_error", 500) from None

    @staticmethod
    def _decode(row):
        owner, pid, data = row
        profile = AgentProfile.model_validate(json.loads(data, object_pairs_hook=_unique))
        if profile.owner_id != owner or profile.profile_id != pid:
            raise ValueError("inconsistent identity")
        return profile

    def read(self, owner_id, profile_id):
        with self._access() as db:
            row = db.execute("SELECT owner_id,profile_id,data FROM profiles WHERE owner_id=? AND profile_id=?",
                             (owner_id, profile_id)).fetchone()
            if row is None:
                raise ProfileError("profile_not_found", 404)
            return self._decode(row)

    def list(self, owner_id):
        with self._access() as db:
            canonical_id(owner_id)
            return tuple(self._decode(row) for row in db.execute(
                "SELECT owner_id,profile_id,data FROM profiles WHERE owner_id=? ORDER BY profile_id", (owner_id,)))

    def create(self, owner_id, fields: ProfileFields):
        profile = AgentProfile(**fields.model_dump(), owner_id=owner_id, profile_id=str(uuid4()), revision=0)
        with self._access(write=True) as db:
            db.execute("INSERT INTO profiles VALUES (?,?,?)",
                       (owner_id, profile.profile_id, profile.model_dump_json()))
        return profile

    def edit(self, owner_id, profile_id, expected_revision, fields: ProfileFields):
        with self._access(write=True) as db:
            old = self.read(owner_id, profile_id)
            if old.revision != expected_revision:
                raise ProfileError("stale_profile")
            if all(getattr(old, k) == getattr(fields, k) for k in ProfileFields.model_fields):
                return old
            profile = AgentProfile(**fields.model_dump(), owner_id=owner_id,
                                   profile_id=profile_id, revision=old.revision + 1)
            db.execute("UPDATE profiles SET data=? WHERE owner_id=? AND profile_id=?",
                       (profile.model_dump_json(), owner_id, profile_id))
        return profile

    def read_binding(self, owner_id):
        with self._access() as db:
            row = db.execute("SELECT active_profile_id,revision FROM profile_bindings WHERE owner_id=?",
                             (owner_id,)).fetchone()
            if row is None:
                return ActiveProfileBinding(owner_id=owner_id)
            pid, revision = row
            binding = ActiveProfileBinding(owner_id=owner_id, active_profile_id=pid, revision=revision)
            if revision < 1 or db.execute("SELECT 1 FROM profiles WHERE owner_id=? AND profile_id=?",
                                          (owner_id, pid)).fetchone() is None:
                raise ValueError("invalid binding")
            return binding

    def select(self, owner_id, profile_id, expected_profile_revision, expected_binding_revision):
        with self._access(write=True) as db:
            profile = self.read(owner_id, profile_id)
            binding = self.read_binding(owner_id)
            if profile.revision != expected_profile_revision or binding.revision != expected_binding_revision:
                raise ProfileError("stale_profile_binding")
            if binding.active_profile_id == profile_id:
                return binding
            binding = ActiveProfileBinding(owner_id=owner_id, active_profile_id=profile_id,
                                           revision=binding.revision + 1)
            db.execute("INSERT INTO profile_bindings VALUES (?,?,?) ON CONFLICT(owner_id) DO UPDATE SET "
                       "active_profile_id=excluded.active_profile_id,revision=excluded.revision",
                       (owner_id, profile_id, binding.revision))
        return binding

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
