"""Isolated Day 10 durable state. Evaluation outputs are not conversation sources."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sqlite3
from uuid import uuid4

from app.context_strategies_models import VERSION, SCENARIO, Fact, LabError, strict_json
from app.context_strategies_scenario import FIXTURES, target_for
from app.fact_extractor import user_assertions

DDL = (
    "CREATE TABLE runs (run_id TEXT PRIMARY KEY, strategy TEXT NOT NULL CHECK(strategy IN ('window','facts','branches')), config_version TEXT NOT NULL, scenario_version TEXT NOT NULL, revision INTEGER NOT NULL)",
    "CREATE TABLE streams (run_id TEXT NOT NULL REFERENCES runs ON DELETE CASCADE, label TEXT NOT NULL CHECK(label IN ('root','A','B')), PRIMARY KEY(run_id,label))",
    "CREATE TABLE messages (message_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stream TEXT NOT NULL, position INTEGER NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL, UNIQUE(run_id,stream,position), FOREIGN KEY(run_id,stream) REFERENCES streams(run_id,label) ON DELETE CASCADE)",
    "CREATE TABLE scenario_steps (run_id TEXT NOT NULL REFERENCES runs ON DELETE CASCADE, step_id INTEGER NOT NULL, target TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES messages(message_id), assistant_id TEXT NOT NULL REFERENCES messages(message_id), revision INTEGER NOT NULL, PRIMARY KEY(run_id,step_id))",
    "CREATE TABLE fact_state (run_id TEXT PRIMARY KEY REFERENCES runs ON DELETE CASCADE, data TEXT NOT NULL, revision INTEGER NOT NULL)",
    "CREATE TABLE checkpoints (run_id TEXT PRIMARY KEY REFERENCES runs ON DELETE CASCADE, boundary INTEGER NOT NULL)",
    "CREATE TABLE evaluation_outputs (run_id TEXT NOT NULL REFERENCES runs ON DELETE CASCADE, snapshot_id TEXT NOT NULL, variant TEXT NOT NULL CHECK(variant IN ('A','B')), data TEXT NOT NULL, PRIMARY KEY(run_id,snapshot_id,variant))",
)


class Day10Store:
    def __init__(self, path: Path):
        self.connection = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(path, isolation_level=None, timeout=1)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute("PRAGMA synchronous=FULL")
            tables = dict(self.connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
            if not tables:
                with self.transaction() as db:
                    for statement in DDL: db.execute(statement)
            else:
                expected = {statement.split()[2]: statement for statement in DDL}
                if tables != expected: raise LabError("storage_schema_invalid", 500)
        except (OSError, sqlite3.Error):
            self.close()
            raise LabError("storage_error", 500) from None
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    @contextmanager
    def transaction(self):
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
                self.connection.execute("COMMIT")
            except BaseException:
                if self.connection.in_transaction: self.connection.execute("ROLLBACK")
                raise
        except sqlite3.Error:
            raise LabError("storage_error", 500) from None

    def create(self, strategy):
        if strategy not in ("window", "facts", "branches"): raise LabError("invalid_strategy", 422)
        run_id = str(uuid4())
        with self.transaction() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,0)", (run_id, strategy, VERSION, SCENARIO))
            db.execute("INSERT INTO streams VALUES (?, 'root')", (run_id,))
            if strategy == "facts": db.execute("INSERT INTO fact_state VALUES (?, '[]', 0)", (run_id,))
        return self.load(run_id, strategy)

    def load(self, run_id, strategy):
        try:
            row = self.connection.execute("SELECT * FROM runs WHERE run_id=? AND strategy=?", (run_id,strategy)).fetchone()
            if row is None: raise LabError("run_not_found", 404)
            run = dict(row)
            if run["config_version"] != VERSION or run["scenario_version"] != SCENARIO:
                raise LabError("configuration_mismatch")
            streams = [r[0] for r in self.connection.execute("SELECT label FROM streams WHERE run_id=? ORDER BY label", (run_id,))]
            checkpoint = self.connection.execute("SELECT boundary FROM checkpoints WHERE run_id=?", (run_id,)).fetchone()
            run["checkpoint"] = checkpoint[0] if checkpoint else None
            messages = [dict(r) for r in self.connection.execute("SELECT * FROM messages WHERE run_id=? ORDER BY stream,position", (run_id,))]
            steps = [dict(r) for r in self.connection.execute("SELECT * FROM scenario_steps WHERE run_id=? ORDER BY step_id", (run_id,))]
            fact_row = self.connection.execute("SELECT data,revision FROM fact_state WHERE run_id=?", (run_id,)).fetchone()
            run["facts"] = strict_json(fact_row[0]) if fact_row else []
            run["messages"], run["steps"] = messages, steps
            valid_streams = ["A", "B", "root"] if checkpoint else ["root"]
            if streams != valid_streams or (checkpoint and strategy != "branches"):
                raise ValueError()
            for stream in streams:
                history = [m for m in messages if m["stream"] == stream]
                if len(history) % 2: raise ValueError()
                for index, message in enumerate(history):
                    if message["position"] != index or message["role"] != ("user" if index % 2 == 0 else "assistant"):
                        raise ValueError()
            root_size = sum(m["stream"] == "root" for m in messages)
            if checkpoint and (run["checkpoint"] != 12 or root_size != 12): raise ValueError()
            if len(messages) != len(steps)*2 or len(steps)>8: raise ValueError()
            by_id = {m["message_id"]: m for m in messages}
            for i, step in enumerate(steps, 1):
                user, assistant = by_id[step["user_id"]], by_id[step["assistant_id"]]
                if (step["step_id"] != i or step["target"] != target_for(strategy,i) or
                    user["role"] != "user" or assistant["role"] != "assistant" or
                    user["stream"] != step["target"] or assistant["stream"] != step["target"] or
                    assistant["position"] != user["position"]+1 or user["content"] != FIXTURES[i-1]): raise ValueError()
            if run["revision"] != len(steps) + bool(checkpoint): raise ValueError()
            if bool(fact_row) != (strategy == "facts"): raise ValueError()
            if fact_row and fact_row[1] != run["revision"]: raise ValueError()
            identities = set()
            for raw in run["facts"]:
                f = Fact.model_validate(raw)
                key = (f.scope, f.key)
                if key in identities or (f.state == "cleared") != (f.value is None): raise ValueError()
                identities.add(key)
                user = by_id[f.user_id]
                source = user_assertions(user["content"]).get(key)
                if user["role"] != "user" or source is None or source[1] != f.evidence or type(source[0]) is not type(f.value) or source[0] != f.value: raise ValueError()
            return run
        except sqlite3.Error:
            raise LabError("storage_error", 500) from None
        except (ValueError, TypeError, KeyError):
            raise LabError("run_state_invalid", 500) from None

    def check_revision(self, run_id, strategy, revision):
        run = self.load(run_id, strategy)
        if run["revision"] != revision: raise LabError("revision_conflict")
        return run

    def commit_turn(self, run, target, step, user_id, message, reply, facts):
        with self.transaction() as db:
            current = self.check_revision(run["run_id"],run["strategy"],run["revision"])
            self.validate_send(current,target,step,message)
            pos = sum(m["stream"] == target for m in current["messages"])
            assistant_id = str(uuid4())
            db.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?)", [
                (user_id,run["run_id"],target,pos,"user",message),
                (assistant_id,run["run_id"],target,pos+1,"assistant",reply)])
            revision = run["revision"]+1
            db.execute("INSERT INTO scenario_steps VALUES (?,?,?,?,?,?)", (run["run_id"],step,target,user_id,assistant_id,revision))
            if run["strategy"] == "facts":
                db.execute("UPDATE fact_state SET data=?,revision=? WHERE run_id=?", (json.dumps(facts,ensure_ascii=False),revision,run["run_id"]))
            db.execute("UPDATE runs SET revision=? WHERE run_id=?", (revision,run["run_id"]))

    @staticmethod
    def validate_send(run, target, step, message):
        if step != len(run["steps"])+1 or not 1<=step<=8: raise LabError("scenario_step_conflict")
        if message != FIXTURES[step-1]: raise LabError("scenario_not_applicable",422)
        if target != target_for(run["strategy"],step): raise LabError("invalid_target",422)
        if run["strategy"] == "branches" and step>6 and run["checkpoint"] is None:
            raise LabError("checkpoint_required")
        if run["checkpoint"] and target == "root": raise LabError("root_frozen")

    def checkpoint(self, run_id, strategy, revision):
        with self.transaction() as db:
            run = self.load(run_id,strategy)
            if strategy != "branches": raise LabError("invalid_strategy",422)
            if run["checkpoint"] is not None: return
            if run["revision"] != revision: raise LabError("revision_conflict")
            if len(run["steps"]) != 6: raise LabError("checkpoint_not_ready")
            db.execute("INSERT INTO checkpoints VALUES (?,12)",(run_id,))
            db.executemany("INSERT INTO streams VALUES (?,?)",[(run_id,"A"),(run_id,"B")])
            db.execute("UPDATE runs SET revision=revision+1 WHERE run_id=?",(run_id,))

    def delete(self, run_id, strategy):
        with self.transaction() as db:
            # Foreign namespace deletion cannot target a different strategy.
            db.execute("DELETE FROM runs WHERE run_id=? AND strategy=?",(run_id,strategy))

    def outputs(self, run_id):
        try:
            return [strict_json(r[0]) for r in self.connection.execute("SELECT data FROM evaluation_outputs WHERE run_id=? ORDER BY variant",(run_id,))]
        except (sqlite3.Error,ValueError): raise LabError("output_storage_error",500) from None

    def save_output(self, run, output):
        with self.transaction() as db:
            self.check_revision(run["run_id"],run["strategy"],run["revision"])
            db.execute("INSERT INTO evaluation_outputs VALUES (?,?,?,?) ON CONFLICT(run_id,snapshot_id,variant) DO UPDATE SET data=excluded.data",
                (run["run_id"],output["snapshot_id"],output["variant"],json.dumps(output,ensure_ascii=False)))


def snapshot_id(run):
    return hashlib.sha256(json.dumps(run,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def sources(run, target):
    if run["strategy"] != "branches": return deepcopy(run["messages"][-6:])
    return deepcopy([m for m in run["messages"] if m["stream"] == "root"] +
                    [m for m in run["messages"] if target != "root" and m["stream"] == target])
