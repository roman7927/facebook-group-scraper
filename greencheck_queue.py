"""Durable local state for Green Check batches and per-source outcomes."""

import json
import random
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OutboundQueue:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        with self.lock:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS batches ("
                "batch_id TEXT PRIMARY KEY, payload BLOB NOT NULL, created_at TEXT NOT NULL, "
                "attempt_count INTEGER NOT NULL DEFAULT 0, last_attempt_at TEXT, "
                "next_retry_at TEXT, last_error TEXT, delivery_status TEXT NOT NULL)"
            )
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS source_outcomes ("
                "cycle_id TEXT NOT NULL, group_id TEXT NOT NULL, payload TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, PRIMARY KEY(cycle_id, group_id))"
            )
            self.db.commit()

    def enqueue(self, batch_id, payload):
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        with self.lock:
            self.db.execute(
                "INSERT OR IGNORE INTO batches"
                "(batch_id,payload,created_at,next_retry_at,delivery_status) VALUES(?,?,?,?,?)",
                (batch_id, raw, now(), now(), "pending"),
            )
            self.db.commit()

    def pending(self):
        with self.lock:
            return self.db.execute(
                "SELECT batch_id,payload,attempt_count FROM batches "
                "WHERE delivery_status='pending' AND next_retry_at<=? ORDER BY created_at",
                (now(),),
            ).fetchall()

    def pending_count(self):
        with self.lock:
            row = self.db.execute(
                "SELECT count(*) FROM batches WHERE delivery_status='pending'"
            ).fetchone()
            return int(row[0])

    def delivered(self, batch_id):
        with self.lock:
            self.db.execute(
                "UPDATE batches SET delivery_status='delivered',last_error=NULL "
                "WHERE batch_id=?",
                (batch_id,),
            )
            self.db.commit()

    def failure(self, batch_id, attempts, message, permanent):
        with self.lock:
            if permanent:
                self.db.execute(
                    "UPDATE batches SET delivery_status='quarantined',last_error=? "
                    "WHERE batch_id=?",
                    (message, batch_id),
                )
            else:
                delay = min(3600, 2 ** min(attempts, 10)) + random.uniform(0, 1)
                retry = (
                    datetime.now(timezone.utc) + timedelta(seconds=delay)
                ).isoformat().replace("+00:00", "Z")
                self.db.execute(
                    "UPDATE batches SET attempt_count=?,last_attempt_at=?,next_retry_at=?,"
                    "last_error=? WHERE batch_id=?",
                    (attempts + 1, now(), retry, message, batch_id),
                )
            self.db.commit()

    def record_source_outcome(self, cycle_id, outcome):
        payload = json.dumps(outcome, separators=(",", ":"), ensure_ascii=False)
        with self.lock:
            self.db.execute(
                "INSERT INTO source_outcomes(cycle_id,group_id,payload,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(cycle_id,group_id) DO UPDATE SET "
                "payload=excluded.payload,updated_at=excluded.updated_at",
                (cycle_id, outcome["group_id"], payload, now()),
            )
            self.db.commit()

    def source_outcomes(self, cycle_id):
        with self.lock:
            rows = self.db.execute(
                "SELECT payload FROM source_outcomes WHERE cycle_id=? ORDER BY updated_at,group_id",
                (cycle_id,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def latest_source_outcomes(self):
        with self.lock:
            row = self.db.execute(
                "SELECT cycle_id FROM source_outcomes ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return self.source_outcomes(row[0]) if row else []
