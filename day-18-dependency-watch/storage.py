"""Short SQLite transactions; no transaction spans an await or a network call."""
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import sqlite3
from uuid import uuid4

from lookup import source_url
from watch_models import Aggregate, CreateInput, Execution, Receipt, Summary, WatchError, timestamp, utc_ms

logger = logging.getLogger("day18.storage")
SCHEMA = """
CREATE TABLE watches (
 watch_id TEXT PRIMARY KEY, group_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
 interval_seconds INTEGER NOT NULL CHECK(interval_seconds BETWEEN 30 AND 86400),
 max_runs INTEGER NOT NULL CHECK(max_runs BETWEEN 1 AND 100), created_at INTEGER NOT NULL,
 next_run_at INTEGER, status TEXT NOT NULL CHECK(status IN ('active','completed')),
 runs_total INTEGER NOT NULL DEFAULT 0, skipped_slots INTEGER NOT NULL DEFAULT 0,
 aggregate_json TEXT NOT NULL
);
CREATE TABLE executions (
 run_id TEXT PRIMARY KEY, watch_id TEXT NOT NULL REFERENCES watches(watch_id),
 scheduled_at INTEGER NOT NULL, started_at INTEGER NOT NULL, completed_at INTEGER,
 checked_at INTEGER, state TEXT NOT NULL CHECK(state IN ('running','succeeded','failed')),
 lookup_outcome TEXT, lookup_id TEXT, source_url TEXT NOT NULL,
 versions_json TEXT, error_category TEXT, aggregate_json TEXT,
 UNIQUE(watch_id, scheduled_at)
);
CREATE UNIQUE INDEX one_running ON executions(watch_id) WHERE state='running';
PRAGMA user_version=1;
"""


def execution(row):
    return Execution(run_id=row["run_id"], watch_id=row["watch_id"],
        **{k: timestamp(row[k]) for k in ("scheduled_at", "started_at", "completed_at", "checked_at")},
        **{k: row[k] for k in ("state", "lookup_outcome", "lookup_id", "source_url", "error_category")},
        version_count=None if row["versions_json"] is None else len(json.loads(row["versions_json"])))


def aggregate(rows, now):
    """Pure fold over terminal executions in scheduled order; gaps are not empty snapshots."""
    result = Aggregate(generated_at=timestamp(now))
    previous, seen = None, set()
    for row in rows:
        item = execution(row)
        result.executions.append(item)
        result.runs_total += 1
        result.successful += row["state"] == "succeeded"
        result.failed += row["state"] == "failed"
        result.interrupted += row["error_category"] == "interrupted"
        if item.checked_at is not None:
            result.first_checked_at = result.first_checked_at or item.checked_at
            result.last_checked_at = item.checked_at
        if row["state"] == "succeeded" and row["lookup_outcome"] in ("found", "no_versions"):
            versions = json.loads(row["versions_json"])
            current = set(versions)
            result.comparable_snapshots += 1
            if previous is None:
                result.first_version_count = len(versions)
            else:
                result.changes_detected += previous != current
                for version in versions:
                    if version not in seen:
                        result.newly_seen_versions.append(version)
                        seen.add(version)
            seen.update(current)
            previous = current
            result.last_version_count = len(versions)
        result.latest_execution = item
        result.through_execution_id = item.run_id
    return result


class Store:
    def __init__(self, path, *, clock=utc_ms, allow_short=False, failpoint=None):
        self.path, self.clock, self.allow_short = Path(path), clock, allow_short
        self.failpoint, self.healthy = failpoint, True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.path) as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if version == 0 and not tables:
                    db.executescript("BEGIN IMMEDIATE;" + SCHEMA + "COMMIT;")
                elif version != 1:
                    raise WatchError("unsupported_schema")
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise WatchError("storage_unavailable")
                db.execute("SELECT aggregate_json FROM watches LIMIT 0")
                db.execute("SELECT aggregate_json FROM executions LIMIT 0")
        except sqlite3.Error as exc:
            self.healthy = False
            raise WatchError("storage_unavailable") from exc

    @contextmanager
    def transaction(self, *, write=False):
        if not self.healthy:
            raise WatchError("storage_unavailable")
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=5)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except sqlite3.Error as exc:
            self.healthy = False
            raise WatchError("storage_unavailable") from exc
        finally:
            if db is not None:
                db.close()  # rolls back any uncommitted transition, including failpoints

    @staticmethod
    def receipt(row):
        return Receipt(**{k: row[k] for k in ("watch_id", "group_id", "artifact_id", "interval_seconds",
            "max_runs", "status", "runs_total", "skipped_slots")},
            created_at=timestamp(row["created_at"]), next_run_at=timestamp(row["next_run_at"]))

    def create(self, request: CreateInput):
        short = request.interval_seconds < 3600
        if short and (not self.allow_short or request.max_runs > 3):
            raise WatchError("short_interval_disabled_or_unbounded")
        now, watch_id = self.clock(), str(uuid4())
        with self.transaction(write=True) as db:
            active = db.execute("SELECT interval_seconds FROM watches WHERE status='active'").fetchall()
            if len(active) >= 5 or (short and any(r[0] < 3600 for r in active)):
                raise WatchError("active_watch_limit")
            db.execute("INSERT INTO watches VALUES (?,?,?,?,?,?,?,'active',0,0,?)",
                (watch_id, request.group_id, request.artifact_id, request.interval_seconds,
                 request.max_runs, now, now + request.interval_seconds * 1000,
                 Aggregate(generated_at=timestamp(now)).model_dump_json()))
            receipt = self.receipt(db.execute("SELECT * FROM watches WHERE watch_id=?", (watch_id,)).fetchone())
        logger.info(json.dumps({"event": "watch_created", **receipt.model_dump(mode="json")}))
        return receipt

    def summary(self, watch_id):
        with self.transaction() as db:
            watch = db.execute("SELECT * FROM watches WHERE watch_id=?", (str(watch_id),)).fetchone()
            if watch is None:
                raise WatchError("watch_not_found")
            running = db.execute("SELECT * FROM executions WHERE watch_id=? AND state='running'",
                                 (str(watch_id),)).fetchone()
            facts = json.loads(watch["aggregate_json"])
            return Summary(**{**self.receipt(watch).model_dump(), **facts},
                           running_execution=execution(running) if running else None)

    def due(self, now):
        with self.transaction() as db:
            return [r[0] for r in db.execute("SELECT watch_id FROM watches WHERE status='active' AND next_run_at<=? ORDER BY next_run_at,watch_id", (now,))]

    def claim(self, watch_id, now):
        with self.transaction(write=True) as db:
            watch = db.execute("SELECT * FROM watches WHERE watch_id=?", (watch_id,)).fetchone()
            if (watch is None or watch["status"] != "active" or watch["next_run_at"] > now
                    or db.execute("SELECT 1 FROM executions WHERE watch_id=? AND state='running'", (watch_id,)).fetchone()):
                return None
            interval = watch["interval_seconds"] * 1000
            skipped = (now - watch["next_run_at"]) // interval
            scheduled = watch["next_run_at"] + skipped * interval
            run_id = str(uuid4())
            db.execute("INSERT INTO executions (run_id,watch_id,scheduled_at,started_at,state,source_url) VALUES (?,?,?,?,'running',?)",
                       (run_id, watch_id, scheduled, now, source_url(watch["group_id"])))
            db.execute("UPDATE watches SET skipped_slots=skipped_slots+? WHERE watch_id=?", (skipped, watch_id))
            return dict(watch) | {"run_id": run_id, "scheduled_at": scheduled, "started_at": now}

    def _terminalize(self, db, run, now, result=None, failure=None, recovery=False):
        if run["state"] != "running":
            return None
        db.execute("UPDATE executions SET state=?,completed_at=?,checked_at=?,lookup_outcome=?,lookup_id=?,versions_json=?,error_category=? WHERE run_id=?",
            ("succeeded" if result else "failed", now,
             result.checked_at if result else getattr(failure, "checked_at", None),
             result.status if result else None,
             result.lookup_id if result else getattr(failure, "lookup_id", None),
             json.dumps(result.versions) if result else None,
             "interrupted" if recovery else getattr(failure, "category", None), run["run_id"]))
        rows = db.execute("SELECT * FROM executions WHERE watch_id=? AND state!='running' ORDER BY scheduled_at,run_id", (run["watch_id"],)).fetchall()
        facts = aggregate(rows, now)
        watch = db.execute("SELECT * FROM watches WHERE watch_id=?", (run["watch_id"],)).fetchone()
        interval = watch["interval_seconds"] * 1000
        next_run = run["scheduled_at"] + interval
        if not recovery:
            next_run = max(next_run, watch["created_at"] + ((now - watch["created_at"]) // interval + 1) * interval)
        completed = facts.runs_total >= watch["max_runs"]
        encoded = facts.model_dump_json()
        db.execute("UPDATE executions SET aggregate_json=? WHERE run_id=?", (encoded, run["run_id"]))
        if self.failpoint:
            self.failpoint("before_watch_update")
        db.execute("UPDATE watches SET runs_total=?,status=?,next_run_at=?,aggregate_json=?,skipped_slots=skipped_slots+? WHERE watch_id=?",
            (facts.runs_total, "completed" if completed else "active", None if completed else next_run, encoded, (next_run - run["scheduled_at"]) // interval - 1, run["watch_id"]))
        return facts.latest_execution

    def finish(self, run_id, *, result=None, failure=None, now=None):
        with self.transaction(write=True) as db:
            run = db.execute("SELECT * FROM executions WHERE run_id=?", (run_id,)).fetchone()
            item = self._terminalize(db, run, self.clock() if now is None else now, result, failure)
        if item:
            logger.info(json.dumps({"event": "execution_terminal", **item.model_dump(mode="json")}))

    def recover(self):
        # All stale running executions and their summaries become visible together.
        with self.transaction(write=True) as db:
            rows = db.execute("SELECT * FROM executions WHERE state='running' ORDER BY scheduled_at,run_id").fetchall()
            items = [self._terminalize(db, row, self.clock(), recovery=True) for row in rows]
        for item in items:
            logger.info(json.dumps({"event": "execution_recovered", **item.model_dump(mode="json")}))
