"""Thread-safe, durable heartbeat state for the Green Check scraper."""

import socket
import threading
import time
import uuid
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class HealthReporter:
    def __init__(self, client, queue, configured_group_count, interval_seconds=60):
        self.client = client
        self.queue = queue
        self.interval_seconds = interval_seconds
        self.started = time.monotonic()
        self.host_identifier = socket.gethostname()
        self.configured_group_count = configured_group_count
        self.completed_group_count = 0
        self.posts_discovered = 0
        self.comments_discovered = 0
        self.current_group_id = None
        self.last_error_summary = None
        self.last_completed_scrape = None
        self.browser_session_status = "unknown"
        self.last_sent = 0
        self.cycle_id = str(uuid.uuid4())
        self._outcomes = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

    def payload(self):
        with self._lock:
            outcomes = self.queue.source_outcomes(self.cycle_id)
            if not outcomes:
                outcomes = self.queue.latest_source_outcomes()
            return {
                "client_id": self.client.client_id,
                "scraper_version": "0.2.0",
                "host_identifier": self.host_identifier,
                "current_time": utc_now(),
                "last_completed_scrape": self.last_completed_scrape,
                "current_group_id": self.current_group_id,
                "configured_group_count": self.configured_group_count,
                "completed_group_count": self.completed_group_count,
                "posts_discovered": self.posts_discovered,
                "comments_discovered": self.comments_discovered,
                "pending_queue_count": self.queue.pending_count(),
                "last_error_summary": self.last_error_summary,
                "browser_session_status": self.browser_session_status,
                "process_uptime_seconds": int(time.monotonic() - self.started),
                "source_outcomes": outcomes,
            }

    def send_if_due(self, force=False):
        with self._lock:
            if not force and time.monotonic() - self.last_sent < self.interval_seconds:
                return False
        try:
            self.client.heartbeat(self.payload())
        except Exception as error:
            print(f"Green Check heartbeat failed: {str(error)[:300]}")
            return False
        with self._lock:
            self.last_sent = time.monotonic()
        return True

    def start(self):
        self.send_if_due(force=True)
        self._thread = threading.Thread(
            target=self._run, name="greencheck-heartbeat", daemon=True
        )
        self._thread.start()

    def _run(self):
        while not self._stop.wait(self.interval_seconds):
            self.send_if_due(force=True)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=min(5, self.interval_seconds + 1))
        self.send_if_due(force=True)

    def set_browser_status(self, status):
        with self._lock:
            self.browser_session_status = status
        self.send_if_due(force=True)

    def begin_source(self, source):
        outcome = {
            "group_id": source["group_id"],
            "group_name": source["group_name"],
            "status": "started",
            "started_at": utc_now(),
            "completed_at": None,
            "posts_discovered": 0,
            "comments_discovered": 0,
            "error_summary": None,
        }
        with self._lock:
            self.current_group_id = source["group_id"]
            self._outcomes[source["group_id"]] = outcome
            self.queue.record_source_outcome(self.cycle_id, outcome)
        self.send_if_due(force=True)

    def complete_source(self, source, posts_discovered):
        with self._lock:
            outcome = self._outcomes[source["group_id"]]
            outcome.update(
                status="succeeded",
                completed_at=utc_now(),
                posts_discovered=posts_discovered,
                error_summary=None,
            )
            self.completed_group_count += 1
            self.posts_discovered += posts_discovered
            self.queue.record_source_outcome(self.cycle_id, outcome)
        self.send_if_due(force=True)

    def fail_source(self, source, error):
        message = str(error)[:2000]
        with self._lock:
            outcome = self._outcomes[source["group_id"]]
            outcome.update(status="failed", completed_at=utc_now(), error_summary=message)
            self.completed_group_count += 1
            self.last_error_summary = message
            self.queue.record_source_outcome(self.cycle_id, outcome)
        self.send_if_due(force=True)

    def skip_source(self, source, reason):
        message = str(reason)[:2000]
        with self._lock:
            outcome = self._outcomes[source["group_id"]]
            outcome.update(status="skipped", completed_at=utc_now(), error_summary=message)
            self.completed_group_count += 1
            self.last_error_summary = message
            self.queue.record_source_outcome(self.cycle_id, outcome)
        self.send_if_due(force=True)

    def add_comments(self, group_id, count):
        if not count:
            return
        with self._lock:
            outcome = self._outcomes.get(group_id)
            if outcome is None:
                return
            outcome["comments_discovered"] += count
            self.comments_discovered += count
            self.queue.record_source_outcome(self.cycle_id, outcome)

    def source_error(self, group_id, error):
        message = str(error)[:2000]
        with self._lock:
            outcome = self._outcomes.get(group_id)
            if outcome is None:
                return
            outcome.update(status="failed", error_summary=message)
            self.last_error_summary = message
            self.queue.record_source_outcome(self.cycle_id, outcome)
        self.send_if_due(force=True)

    def finish_cycle(self):
        with self._lock:
            self.current_group_id = None
            self.last_completed_scrape = utc_now()
        self.send_if_due(force=True)
