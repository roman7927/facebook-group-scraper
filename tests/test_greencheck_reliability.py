import tempfile
import time
import unittest
from pathlib import Path

from greencheck_health import HealthReporter
from greencheck_queue import OutboundQueue


class FakeClient:
    client_id = "test-scraper"

    def __init__(self):
        self.heartbeats = []

    def heartbeat(self, payload):
        self.heartbeats.append(payload)
        return {"accepted": True}


class GreenCheckReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.temporary.name) / "queue.sqlite3"

    def tearDown(self):
        self.temporary.cleanup()

    def test_heartbeat_runs_during_long_work(self):
        client = FakeClient()
        queue = OutboundQueue(self.queue_path)
        health = HealthReporter(client, queue, 1, interval_seconds=0.05)

        health.start()
        time.sleep(0.13)
        health.stop()

        self.assertGreaterEqual(len(client.heartbeats), 3)
        self.assertTrue(all(item["host_identifier"] for item in client.heartbeats))

    def test_pending_depth_includes_batches_waiting_for_backoff(self):
        queue = OutboundQueue(self.queue_path)
        queue.enqueue("batch-one", {"batch_id": "batch-one"})
        queue.failure("batch-one", 0, "temporary", permanent=False)

        self.assertEqual(queue.pending(), [])
        self.assertEqual(queue.pending_count(), 1)

    def test_source_outcome_survives_fresh_reporter(self):
        source = {
            "group_id": "nocateehomes",
            "group_name": "Nocatee",
            "facebook_source_type": "group",
        }
        queue = OutboundQueue(self.queue_path)
        health = HealthReporter(FakeClient(), queue, 1)
        health.begin_source(source)
        health.fail_source(source, RuntimeError("Facebook feed unavailable"))

        reopened = OutboundQueue(self.queue_path)
        fresh = HealthReporter(FakeClient(), reopened, 1)
        outcomes = fresh.payload()["source_outcomes"]

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["group_id"], "nocateehomes")
        self.assertEqual(outcomes[0]["status"], "failed")
        self.assertEqual(outcomes[0]["error_summary"], "Facebook feed unavailable")
        self.assertEqual(health.completed_group_count, 1)

    def test_success_outcome_tracks_posts_and_comments(self):
        source = {
            "group_id": "1831119503607023",
            "group_name": "Palm Coast",
            "facebook_source_type": "group",
        }
        health = HealthReporter(FakeClient(), OutboundQueue(self.queue_path), 1)
        health.begin_source(source)
        health.complete_source(source, 4)
        health.add_comments(source["group_id"], 7)

        outcome = health.payload()["source_outcomes"][0]
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(outcome["posts_discovered"], 4)
        self.assertEqual(outcome["comments_discovered"], 7)


if __name__ == "__main__":
    unittest.main()
