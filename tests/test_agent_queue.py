"""
Unit Test Suite for Asynchronous Investigation Event Queue & Distributed Task Dispatcher (tests/test_agent_queue.py)
Tests priority heap ordering, FIFO tie-breaking, idempotency deduplication,
exponential backoff retries, DLQ management, worker thread execution,
snapshot persistence, and FastAPI REST endpoints.
"""

import time
import unittest
from fastapi.testclient import TestClient

from src.agent.queue import (
    InvestigationTaskQueue,
    InvestigationTask,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from src.api.main import app, task_queue


class TestInvestigationTaskQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Asynchronous Investigation Event Queue Test Suite ===")

    def setUp(self):
        self.queue = InvestigationTaskQueue(max_workers=2)

    def tearDown(self):
        self.queue.stop_workers(timeout=1.0)

    def test_priority_ordering_and_fifo_tiebreak(self):
        """Verify higher priority tasks (CRITICAL, HIGH) preempt lower priority tasks (NORMAL, LOW)."""
        # Register a mock handler to record execution sequence
        exec_sequence = []
        def handler(task: InvestigationTask):
            exec_sequence.append(task.payload["name"])
            return {"name": task.payload["name"]}

        self.queue.register_handler(TaskType.CUSTOM.value, handler)

        # Submit in reverse order
        t_low, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"name": "low_1"}, priority=TaskPriority.LOW)
        t_norm1, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"name": "norm_1"}, priority=TaskPriority.NORMAL)
        t_norm2, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"name": "norm_2"}, priority=TaskPriority.NORMAL)
        t_high, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"name": "high_1"}, priority=TaskPriority.HIGH)
        t_crit, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"name": "crit_1"}, priority=TaskPriority.CRITICAL)

        # Process all tasks synchronously
        count = self.queue.process_all_sync()
        self.assertEqual(count, 5)

        # Order must be: crit_1, high_1, norm_1, norm_2 (FIFO tie-break), low_1
        expected = ["crit_1", "high_1", "norm_1", "norm_2", "low_1"]
        self.assertEqual(exec_sequence, expected)
        print("PASS: Priority heap ordering and FIFO tie-breaking verified.")

    def test_idempotency_deduplication(self):
        """Verify identical idempotency keys deduplicate submissions without duplicate execution."""
        task1, is_dedup1 = self.queue.submit_task(
            TaskType.STREAMING_TRANSACTION.value,
            {"transaction": {"TransactionID": "tx_999", "TransactionAmt": 120.0}},
            idempotency_key="idemp_key_tx_999",
        )
        self.assertFalse(is_dedup1)

        task2, is_dedup2 = self.queue.submit_task(
            TaskType.STREAMING_TRANSACTION.value,
            {"transaction": {"TransactionID": "tx_999", "TransactionAmt": 120.0}},
            idempotency_key="idemp_key_tx_999",
        )
        self.assertTrue(is_dedup2)
        self.assertEqual(task1.task_id, task2.task_id)

        # Verify auto-hash idempotency when key is omitted
        t3, is_dedup3 = self.queue.submit_task(
            TaskType.STREAMING_TRANSACTION.value,
            {"transaction": {"TransactionID": "tx_888", "TransactionAmt": 50.0}},
        )
        t4, is_dedup4 = self.queue.submit_task(
            TaskType.STREAMING_TRANSACTION.value,
            {"transaction": {"TransactionID": "tx_888", "TransactionAmt": 50.0}},
        )
        self.assertFalse(is_dedup3)
        self.assertTrue(is_dedup4)
        self.assertEqual(t3.task_id, t4.task_id)
        print("PASS: Idempotency deduplication (explicit and hashed) verified.")

    def test_exponential_backoff_retry_and_dlq(self):
        """Verify failing tasks retry with backoff and move to DLQ when max retries exceeded."""
        attempts = []
        def failing_handler(task: InvestigationTask):
            attempts.append(time.time())
            raise RuntimeError(f"Simulated fault attempt #{len(attempts)}")

        self.queue.register_handler("FAILING_TASK", failing_handler)

        task, _ = self.queue.submit_task(
            "FAILING_TASK",
            {"dummy": True},
            max_retries=2,
            backoff_factor=0.01,
        )

        # Process first attempt (fails -> retries queued)
        t_run1 = self.queue.process_next_sync()
        self.assertEqual(t_run1.retry_count, 1)
        self.assertEqual(t_run1.status, TaskStatus.PENDING)

        # Process second attempt (fails -> retries queued)
        t_run2 = self.queue.process_next_sync()
        self.assertEqual(t_run2.retry_count, 2)
        self.assertEqual(t_run2.status, TaskStatus.PENDING)

        # Process third attempt (max_retries reached -> FAILED -> DLQ)
        t_run3 = self.queue.process_next_sync()
        self.assertEqual(t_run3.status, TaskStatus.FAILED)
        self.assertIn("Simulated fault", t_run3.error)

        # Check DLQ
        dlq_tasks = self.queue.get_dead_letter_tasks()
        self.assertEqual(len(dlq_tasks), 1)
        self.assertEqual(dlq_tasks[0].task_id, task.task_id)

        # Retry from DLQ
        requeued = self.queue.retry_dlq_task(task.task_id)
        self.assertIsNotNone(requeued)
        self.assertEqual(requeued.status, TaskStatus.PENDING)
        self.assertEqual(requeued.retry_count, 0)
        self.assertEqual(len(self.queue.get_dead_letter_tasks()), 0)
        print("PASS: Exponential backoff retries, DLQ routing, and DLQ replay verified.")

    def test_task_cancellation(self):
        """Verify pending tasks can be cancelled and are skipped during execution."""
        t1, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"val": 1})
        t2, _ = self.queue.submit_task(TaskType.CUSTOM.value, {"val": 2})

        # Cancel t1
        cancelled = self.queue.cancel_task(t1.task_id)
        self.assertTrue(cancelled)
        self.assertEqual(t1.status, TaskStatus.CANCELLED)

        # Cannot cancel non-existent task
        self.assertFalse(self.queue.cancel_task("non_existent_id"))

        # Handlers
        executed = []
        self.queue.register_handler(TaskType.CUSTOM.value, lambda t: executed.append(t.payload["val"]))
        self.queue.process_all_sync()

        # Only t2 should execute
        self.assertEqual(executed, [2])
        print("PASS: Task cancellation and skipping verified.")

    def test_background_worker_concurrency_and_stats(self):
        """Verify multi-threaded worker pool executes tasks asynchronously and updates stats."""
        self.queue.start_workers(count=2)

        # Enqueue 4 streaming transaction tasks
        for i in range(4):
            self.queue.submit_task(
                TaskType.STREAMING_TRANSACTION.value,
                {"transaction": {"TransactionID": f"TX_{i}", "TransactionAmt": 100.0 * (i + 1)}},
            )

        # Wait for workers to process tasks
        for _ in range(50):
            stats = self.queue.get_stats()
            if stats["completed_tasks"] == 4:
                break
            time.sleep(0.05)

        self.queue.stop_workers(timeout=1.0)
        stats = self.queue.get_stats()

        self.assertEqual(stats["completed_tasks"], 4)
        self.assertEqual(stats["queue_depth"], 0)
        self.assertGreaterEqual(stats["avg_duration_ms"], 0.0)
        self.assertEqual(stats["status_breakdown"][TaskStatus.COMPLETED.value], 4)
        print("PASS: Background worker pool concurrency and metrics calculation verified.")

    def test_snapshot_export_and_restore(self):
        """Verify serialization and deserialization of queue state across restarts."""
        t1, _ = self.queue.submit_task(
            TaskType.STREAMING_TRANSACTION.value,
            {"transaction": {"TransactionID": "tx_snap_1", "TransactionAmt": 450.0}},
            idempotency_key="snap_key_1",
        )
        self.queue.process_next_sync()

        t2, _ = self.queue.submit_task(
            TaskType.STREAMING_TRANSACTION.value,
            {"transaction": {"TransactionID": "tx_snap_2", "TransactionAmt": 750.0}},
            idempotency_key="snap_key_2",
        )

        snapshot = self.queue.export_snapshot()
        self.assertEqual(len(snapshot["tasks"]), 2)
        self.assertIn("snap_key_1", snapshot["idempotency_map"])

        # Create new queue and restore
        new_queue = InvestigationTaskQueue()
        new_queue.load_snapshot(snapshot)

        restored_stats = new_queue.get_stats()
        self.assertEqual(restored_stats["total_tasks"], 2)
        self.assertEqual(restored_stats["completed_tasks"], 1)
        self.assertEqual(restored_stats["queue_depth"], 1)

        # Process the remaining pending task in the restored queue
        processed = new_queue.process_next_sync()
        self.assertIsNotNone(processed)
        self.assertEqual(processed.task_id, t2.task_id)
        self.assertEqual(processed.status, TaskStatus.COMPLETED)
        print("PASS: Queue snapshot export and restore verified.")

    def test_fastapi_queue_endpoints(self):
        """Verify REST API queue endpoints for submission, polling, stats, and DLQ."""
        client = TestClient(app)

        # 1. Enqueue Task
        resp = client.post(
            "/api/queue/tasks",
            json={
                "task_type": "STREAMING_TRANSACTION",
                "payload": {"transaction": {"TransactionID": "tx_api_001", "TransactionAmt": 125.0}},
                "priority": "HIGH",
                "idempotency_key": "api_idemp_001",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("task", data)
        self.assertFalse(data["is_deduplicated"])
        task_id = data["task"]["task_id"]

        # 2. Duplicate submission test
        resp_dup = client.post(
            "/api/queue/tasks",
            json={
                "task_type": "STREAMING_TRANSACTION",
                "payload": {"transaction": {"TransactionID": "tx_api_001", "TransactionAmt": 125.0}},
                "priority": "HIGH",
                "idempotency_key": "api_idemp_001",
            },
        )
        self.assertEqual(resp_dup.status_code, 200)
        self.assertTrue(resp_dup.json()["is_deduplicated"])

        # 3. Get Task Status
        resp_get = client.get(f"/api/queue/tasks/{task_id}")
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.json()["task_id"], task_id)

        # 4. Get Queue Stats
        resp_stats = client.get("/api/queue/stats")
        self.assertEqual(resp_stats.status_code, 200)
        stats = resp_stats.json()
        self.assertIn("queue_depth", stats)
        self.assertIn("completed_tasks", stats)

        # 5. Get DLQ
        resp_dlq = client.get("/api/queue/dlq")
        self.assertEqual(resp_dlq.status_code, 200)
        self.assertIn("dead_letter_tasks", resp_dlq.json())

        # 6. Cancel Task
        resp_cancel = client.post(f"/api/queue/tasks/{task_id}/cancel")
        self.assertEqual(resp_cancel.status_code, 200)
        self.assertEqual(resp_cancel.json()["status"], "cancelled")
        print("PASS: FastAPI queue endpoints verified.")


if __name__ == "__main__":
    unittest.main()
