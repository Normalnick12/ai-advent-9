"""A single Day 25 atomic boundary built on the existing SQLite transaction primitive."""
import json
import sqlite3
from uuid import uuid4

from app.conversation_store import ConversationStorageError
from app.grounded_rag.core import GroundedResponse, abstention
from app.sqlite_conversation_store import SQLiteConversationStore
from .models import ChatError, TaskMemory, strict_json

DDL = (
    'CREATE TABLE chat_state (session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE, schema_version INTEGER NOT NULL, revision INTEGER NOT NULL CHECK(revision>=0), memory TEXT NOT NULL)',
    'CREATE TABLE chat_turns (session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE, turn INTEGER NOT NULL CHECK(turn>0), turn_id TEXT NOT NULL UNIQUE, grounded TEXT NOT NULL, memory_update_status TEXT NOT NULL, PRIMARY KEY(session_id,turn))',
)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Day25Store:
    def __init__(self, path):
        self.raw = SQLiteConversationStore(path)
        try:
            db = self.raw._db()
            tables = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
            extra = {k: v for k, v in tables.items() if k not in ('sessions', 'messages')}
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if not extra and version == 0 and not db.execute('SELECT 1 FROM sessions').fetchone():
                with self.raw._transaction() as tx:
                    for sql in DDL:
                        tx.execute(sql)
                    tx.execute('PRAGMA user_version=25')
            elif version != 25 or extra != {s.split()[2]: s for s in DDL}:
                raise ConversationStorageError
        except BaseException:
            self.close()
            raise

    def close(self):
        self.raw.close()

    def create(self):
        sid = str(uuid4())
        with self.raw._transaction() as db:
            db.execute('INSERT INTO sessions VALUES (?)', (sid,))
            db.execute('INSERT INTO chat_state VALUES (?,25,0,?)',
                       (sid, encode(TaskMemory().model_dump())))
        return self.read(sid)

    def read(self, sid):
        try:
            db = self.raw._db()
            if list(db.execute('PRAGMA foreign_key_check')):
                raise ValueError('invalid_references')
            conversation = self.raw.load_session(sid)
            if conversation is None:
                raise ChatError('session_not_found', 404)
            state = db.execute('SELECT schema_version,revision,memory FROM chat_state WHERE session_id=?', (sid,)).fetchone()
            if state is None or state[0] != 25 or type(state[1]) is not int:
                raise ValueError('invalid_state')
            saved_memory = strict_json(state[2])
            if not isinstance(saved_memory, dict) or set(saved_memory) != set(TaskMemory.model_fields):
                raise ValueError('missing_memory_fields')
            memory = TaskMemory.model_validate(saved_memory)
            history = [dict(position=i, role=m.role, content=m.content)
                       for i, m in enumerate(conversation.history)]
            turns = []
            for number, tid, raw, update in db.execute(
                    'SELECT turn,turn_id,grounded,memory_update_status FROM chat_turns WHERE session_id=? ORDER BY turn', (sid,)):
                grounded = GroundedResponse.model_validate(strict_json(raw)).model_dump()
                if (number != len(turns) + 1 or number * 2 > len(history)
                        or grounded['answer'] != history[number * 2 - 1]['content']
                        or update not in ('applied', 'unchanged', 'skipped_runtime_gate', 'skipped_model_abstention')):
                    raise ValueError('invalid_turn')
                if grounded['status'] == 'insufficient_context':
                    if grounded != abstention() or not update.startswith('skipped_'):
                        raise ValueError('invalid_abstention')
                elif not grounded['sources'] or not grounded['citations'] or update.startswith('skipped_'):
                    raise ValueError('invalid_answer')
                turns.append(dict(turn=number, turn_id=tid, user=history[number * 2 - 2]['content'],
                                  grounded=grounded, memory_update_status=update))
            if len(turns) != state[1] or len(history) != state[1] * 2:
                raise ValueError('invalid_revision')
            for _, items in memory.groups():
                for item in items:
                    if item.source_user_turn > state[1]:
                        raise ValueError('invalid_provenance')
                    user = history[(item.source_user_turn - 1) * 2]['content']
                    if user[item.source_start:item.source_end] != item.text:
                        raise ValueError('invalid_provenance')
            return dict(session_id=sid, revision=state[1], history_turn_count=state[1],
                        memory=memory.model_dump(), history=history, turns=turns)
        except (ValueError, TypeError, KeyError, sqlite3.Error):
            raise ConversationStorageError from None

    def commit_turn(self, sid, expected_revision, user, grounded, memory, update_status, turn_id):
        with self.raw._transaction() as db:
            before = self.read(sid)
            if before['revision'] != expected_revision:
                raise ChatError('stale_revision')
            memory = TaskMemory.model_validate(memory).model_dump()
            grounded = GroundedResponse.model_validate(grounded).model_dump()
            pos = expected_revision * 2
            db.executemany('INSERT INTO messages VALUES (?,?,?,?)',
                           [(sid, pos, 'user', user), (sid, pos + 1, 'assistant', grounded['answer'])])
            db.execute('INSERT INTO chat_turns VALUES (?,?,?,?,?)',
                       (sid, expected_revision + 1, turn_id, encode(grounded), update_status))
            db.execute('UPDATE chat_state SET revision=?,memory=? WHERE session_id=?',
                       (expected_revision + 1, encode(memory), sid))
            # Decode and check the complete candidate before COMMIT; no half-state publication.
            after = self.read(sid)
        return after

    def delete(self, sid):
        self.raw.delete_session(sid)
