"""One Day 11 SQLite namespace; ordinary pairs still use ConversationStore."""
import hashlib
import json
import sqlite3
from uuid import UUID, uuid4
from app.sqlite_conversation_store import SQLiteConversationStore
from app.conversation_store import ConversationStorageError
from app.memory_models import MemoryError, WorkingMemory, LongTermMemory

DDL = (
    "CREATE TABLE memory_owners (owner_id TEXT PRIMARY KEY NOT NULL, slot INTEGER NOT NULL UNIQUE CHECK(slot=1))",
    "CREATE TABLE working_memory (task_id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL REFERENCES memory_owners(owner_id), data TEXT NOT NULL)",
    "CREATE TABLE long_term_memory (owner_id TEXT PRIMARY KEY NOT NULL REFERENCES memory_owners(owner_id), data TEXT NOT NULL)",
    "CREATE TABLE session_tasks (session_id TEXT PRIMARY KEY NOT NULL REFERENCES sessions(session_id), task_id TEXT NOT NULL REFERENCES working_memory(task_id))",
    "CREATE TABLE memory_bindings (owner_id TEXT PRIMARY KEY NOT NULL REFERENCES memory_owners(owner_id), current_task_id TEXT NOT NULL REFERENCES working_memory(task_id), current_session_id TEXT NOT NULL REFERENCES session_tasks(session_id), revision INTEGER NOT NULL CHECK(revision>=0))",
)


def strict_json(text):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("duplicate key")
            data[key] = value
        return data
    return json.loads(text, object_pairs_hook=unique)


class WorkingMemoryStore:
    def __init__(self, raw):
        self.raw = raw

    def load(self, task_id, owner_id):
        row = self.raw._db().execute(
            "SELECT data FROM working_memory WHERE task_id=? AND owner_id=?", (task_id, owner_id)
        ).fetchone()
        if row is None:
            raise ValueError("missing working")
        return WorkingMemory.model_validate(strict_json(row[0])).model_dump(exclude_unset=True)

    def save(self, db, task_id, data):
        checked = WorkingMemory.model_validate(data).model_dump(exclude_unset=True)
        db.execute("UPDATE working_memory SET data=? WHERE task_id=?",
                   (json.dumps(checked, ensure_ascii=False), task_id))


class LongTermMemoryStore:
    def __init__(self, raw):
        self.raw = raw

    def load(self, owner_id):
        row = self.raw._db().execute(
            "SELECT data FROM long_term_memory WHERE owner_id=?", (owner_id,)
        ).fetchone()
        if row is None:
            raise ValueError("missing long-term")
        return LongTermMemory.model_validate(strict_json(row[0])).model_dump(exclude_unset=True)

    def save(self, db, owner_id, data):
        checked = LongTermMemory.model_validate(data).model_dump(exclude_unset=True)
        db.execute("UPDATE long_term_memory SET data=? WHERE owner_id=?",
                   (json.dumps(checked, ensure_ascii=False), owner_id))


class MemoryStore:
    def __init__(self, path):
        self.raw = SQLiteConversationStore(path)
        try:
            db = self.raw._db()
            tables = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
            extra = {k: v for k, v in tables.items() if k not in ("sessions", "messages")}
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if not extra and version == 0 and not db.execute("SELECT 1 FROM sessions").fetchone():
                with self.raw._transaction() as tx:
                    for statement in DDL:
                        tx.execute(statement)
                    tx.execute("PRAGMA user_version=11")
            elif version != 11 or extra != {s.split()[2]: s for s in DDL}:
                raise MemoryError("storage_schema_invalid", 500)
            self.working = WorkingMemoryStore(self.raw)
            self.long_term = LongTermMemoryStore(self.raw)
            self.read()
        except BaseException:
            self.close()
            raise

    def close(self):
        self.raw.close()

    def read(self):
        try:
            db = self.raw._db()
            if list(db.execute("PRAGMA foreign_key_check")):
                raise ValueError("invalid references")
            owner = db.execute("SELECT owner_id FROM memory_owners WHERE slot=1").fetchone()
            if owner is None:
                if any(db.execute("SELECT 1 FROM " + table).fetchone()
                       for table in ("working_memory", "long_term_memory", "memory_bindings", "sessions", "session_tasks")):
                    raise ValueError("orphan state")
                return None
            owner_id = owner[0]
            row = db.execute(
                "SELECT current_task_id,current_session_id,revision FROM memory_bindings WHERE owner_id=?",
                (owner_id,),
            ).fetchone()
            if row is None:
                raise ValueError("missing binding")
            task_id, session_id, revision = row
            for identity in (owner_id, task_id, session_id):
                if str(UUID(identity)) != identity:
                    raise ValueError("invalid identity")
            association = db.execute(
                "SELECT task_id FROM session_tasks WHERE session_id=?", (session_id,)
            ).fetchone()
            if association != (task_id,) or type(revision) is not int or revision < 0:
                raise ValueError("invalid binding")
            if db.execute("SELECT count(*) FROM sessions").fetchone()[0] != db.execute(
                "SELECT count(*) FROM session_tasks"
            ).fetchone()[0]:
                raise ValueError("unassociated session")
            conversation = self.raw.load_session(session_id)
            if conversation is None:
                raise ValueError("missing conversation")
            data = {
                "memory_owner_id": owner_id, "task_id": task_id, "session_id": session_id,
                "revision": revision, "working": self.working.load(task_id, owner_id),
                "long_term": self.long_term.load(owner_id),
                "short_term": [{"role": m.role, "content": m.content, "position": i}
                               for i, m in enumerate(conversation.history)],
            }
            data["snapshot_id"] = hashlib.sha256(
                json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest()
            data["inactive_tasks"] = [r[0] for r in db.execute(
                "SELECT task_id FROM working_memory WHERE owner_id=? AND task_id<>? ORDER BY task_id",
                (owner_id, task_id))]
            data["inactive_sessions"] = [{"session_id": r[0], "task_id": r[1]} for r in db.execute(
                "SELECT s.session_id,s.task_id FROM session_tasks s JOIN working_memory w ON w.task_id=s.task_id "
                "WHERE w.owner_id=? AND s.session_id<>? ORDER BY s.session_id", (owner_id, session_id))]
            return data
        except (ValueError, TypeError, sqlite3.Error, ConversationStorageError):
            raise MemoryError("memory_state_invalid", 500) from None

    def require(self, snapshot_id):
        state = self.read()
        if state is None:
            raise MemoryError("not_initialized", 404)
        if state["snapshot_id"] != snapshot_id:
            raise MemoryError("stale_snapshot")
        return state

    @staticmethod
    def _session(db, task_id, session_id=None):
        session_id = session_id or str(uuid4())
        # Same sessions schema, within the caller's transaction, with no runtime publication.
        db.execute("INSERT INTO sessions VALUES (?)", (session_id,))
        db.execute("INSERT INTO session_tasks VALUES (?,?)", (session_id, task_id))
        return session_id

    def initialize(self):
        with self.raw._transaction() as db:
            if self.read() is None:
                owner_id, task_id = str(uuid4()), str(uuid4())
                db.execute("INSERT INTO memory_owners VALUES (?,1)", (owner_id,))
                db.execute("INSERT INTO long_term_memory VALUES (?, '{}')", (owner_id,))
                db.execute("INSERT INTO working_memory VALUES (?,?,'{}')", (task_id, owner_id))
                session_id = self._session(db, task_id)
                db.execute("INSERT INTO memory_bindings VALUES (?,?,?,0)", (owner_id, task_id, session_id))
        return self.read()

    def create_reserved(self, *, owner_id, task_id, session_id, expected_snapshot):
        """Materialize reviewed identities atomically; repeat only the exact current binding."""
        for identity in (owner_id, task_id, session_id):
            if str(UUID(identity)) != identity:
                raise MemoryError("invalid_reserved_identity", 422)
        with self.raw._transaction() as db:
            state = self.read()
            if state and (state["memory_owner_id"], state["task_id"], state["session_id"]) == (
                    owner_id, task_id, session_id):
                return state
            if (state["snapshot_id"] if state else None) != expected_snapshot:
                raise MemoryError("stale_snapshot")
            if state is None:
                db.execute("INSERT INTO memory_owners VALUES (?,1)", (owner_id,))
                db.execute("INSERT INTO long_term_memory VALUES (?, '{}')", (owner_id,))
            elif state["memory_owner_id"] != owner_id:
                raise MemoryError("reserved_owner_mismatch")
            db.execute("INSERT INTO working_memory VALUES (?,?,'{}')", (task_id, owner_id))
            self._session(db, task_id, session_id)
            if state is None:
                db.execute("INSERT INTO memory_bindings VALUES (?,?,?,0)", (owner_id, task_id, session_id))
            else:
                db.execute("UPDATE memory_bindings SET current_task_id=?,current_session_id=?,revision=revision+1 WHERE owner_id=?",
                           (task_id, session_id, owner_id))
        return self.read()

    def transition(self, action, snapshot_id):
        if action not in ("new-conversation", "new-task", "clear-long-term"):
            raise MemoryError("invalid_action", 422)
        with self.raw._transaction() as db:
            state = self.require(snapshot_id)
            owner_id, task_id, session_id = (state[k] for k in ("memory_owner_id", "task_id", "session_id"))
            if action == "clear-long-term":
                if not state["long_term"]:
                    return state
                self.long_term.save(db, owner_id, {})
            else:
                if action == "new-task":
                    task_id = str(uuid4())
                    db.execute("INSERT INTO working_memory VALUES (?,?,'{}')", (task_id, owner_id))
                session_id = self._session(db, task_id)
            db.execute(
                "UPDATE memory_bindings SET current_task_id=?,current_session_id=?,revision=revision+1 WHERE owner_id=?",
                (task_id, session_id, owner_id))
        return self.read()

    def mutate(self, request):
        with self.raw._transaction() as db:
            state = self.require(request.snapshot_id)
            key = "working" if request.layer == "WORKING" else "long_term"
            candidate = dict(state[key])
            if request.operation == "set":
                candidate[request.key] = request.value
            else:
                candidate.pop(request.key, None)
            if candidate == state[key]:
                return state
            if key == "working":
                self.working.save(db, state["task_id"], candidate)
            else:
                self.long_term.save(db, state["memory_owner_id"], candidate)
            db.execute("UPDATE memory_bindings SET revision=revision+1 WHERE owner_id=?", (state["memory_owner_id"],))
        return self.read()
