"""
Asynchronous Investigation Event Queue & Distributed Task Dispatcher (src/agent/queue.py)
Provides persistent in-memory FIFO/priority task queue with idempotency keys,
backoff retries, worker concurrency controls, and dead letter queue (DLQ) for
high-throughput enterprise ingestion and streaming fraud investigations.
"""

import time
import uuid
import heapq
import hashlib
import json
import logging
import threading
from enum import Enum, IntEnum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable, Tuple

logger = logging.getLogger("tigergraph.agent.queue")


class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

    @classmethod
    def from_str(cls, val: Any) -> "TaskPriority":
        if isinstance(val, int):
            return cls(val) if val in cls._value2member_map_ else cls.NORMAL
        val_upper = str(val).upper().strip()
        if val_upper in cls.__members__:
            return cls[val_upper]
        return cls.NORMAL


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskType(str, Enum):
    CASE_INVESTIGATION = "CASE_INVESTIGATION"
    AML_SCREENING = "AML_SCREENING"
    CYBER_FORENSICS = "CYBER_FORENSICS"
    STREAMING_TRANSACTION = "STREAMING_TRANSACTION"
    BATCH_BENCHMARK = "BATCH_BENCHMARK"
    CUSTOM = "CUSTOM"


@dataclass
class InvestigationTask:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = TaskPriority.NORMAL
    idempotency_key: Optional[str] = None
    status: str = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_ms: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    backoff_factor: float = 0.05
    sequence_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["priority_name"] = TaskPriority(self.priority).name if self.priority in TaskPriority._value2member_map_ else str(self.priority)
        return d


class InvestigationTaskQueue:
    """
    Enterprise-grade asynchronous task queue and dispatcher for agent investigations.
    Supports priority heap ordering, FIFO sequence tie-breaking, idempotency deduplication,
    exponential backoff retries, dead-letter queuing, and configurable worker concurrency.
    """

    def __init__(self, max_workers: int = 2, agent: Optional[Any] = None):
        self.max_workers = max_workers
        self.agent = agent
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        
        # Core storage
        self._tasks: Dict[str, InvestigationTask] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> task_id
        self._heap: List[Tuple[int, int, str]] = []  # (priority, sequence_id, task_id)
        self._dead_letter_queue: List[str] = []     # list of failed task_ids
        self._sequence_counter: int = 0

        # Handlers
        self._handlers: Dict[str, Callable[[InvestigationTask], Dict[str, Any]]] = {}
        self._register_default_handlers()

        # Worker management
        self._workers: List[threading.Thread] = []
        self._running = False

    def _register_default_handlers(self):
        self._handlers[TaskType.CASE_INVESTIGATION.value] = self._handle_case_investigation
        self._handlers[TaskType.AML_SCREENING.value] = self._handle_aml_screening
        self._handlers[TaskType.CYBER_FORENSICS.value] = self._handle_cyber_forensics
        self._handlers[TaskType.STREAMING_TRANSACTION.value] = self._handle_streaming_transaction

    def register_handler(self, task_type: str, handler: Callable[[InvestigationTask], Dict[str, Any]]):
        """Registers a custom execution handler for a specific task type."""
        with self._lock:
            self._handlers[task_type] = handler

    # -------------------------------------------------------------------------
    # Default Handlers
    # -------------------------------------------------------------------------

    def _handle_case_investigation(self, task: InvestigationTask) -> Dict[str, Any]:
        case_id = task.payload.get("case_id")
        if not case_id:
            raise ValueError("Payload missing required parameter 'case_id'")
        if self.agent:
            return self.agent.investigate_case(case_id)
        return {"case_id": case_id, "verdict": "mock_verdict", "status": "simulated"}

    def _handle_aml_screening(self, task: InvestigationTask) -> Dict[str, Any]:
        from src.agent.aml_agent import AMLSpecialistAgent
        client = getattr(self.agent, "client", None) if self.agent else None
        agent = AMLSpecialistAgent(client=client)
        assessment = agent.assess(
            customer_id=task.payload.get("customer_id"),
            card_ids=task.payload.get("card_ids"),
            transactions=task.payload.get("transactions"),
            as_of=task.payload.get("as_of"),
        )
        return assessment.to_dict()

    def _handle_cyber_forensics(self, task: InvestigationTask) -> Dict[str, Any]:
        from src.agent.cyber_agent import CyberForensicsAgent
        client = getattr(self.agent, "client", None) if self.agent else None
        agent = CyberForensicsAgent(client=client)
        assessment = agent.assess(
            device_id=task.payload.get("device_id"),
            card_id=task.payload.get("card_id"),
            ip_address=task.payload.get("ip_address"),
            as_of=task.payload.get("as_of"),
        )
        return assessment.to_dict()

    def _handle_streaming_transaction(self, task: InvestigationTask) -> Dict[str, Any]:
        tx = task.payload.get("transaction", {})
        tx_id = str(tx.get("TransactionID", "UNKNOWN"))
        amt = float(tx.get("TransactionAmt", 0.0))
        risk_score = 0.10 if amt < 250.0 else (0.85 if amt > 5000.0 else 0.35)
        decision = "ALLOW" if risk_score < 0.50 else "REVIEW"
        return {
            "transaction_id": tx_id,
            "amount": amt,
            "risk_score": risk_score,
            "decision": decision,
        }

    # -------------------------------------------------------------------------
    # Task Submission & Lifecycle
    # -------------------------------------------------------------------------

    def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: Union[TaskPriority, int, str] = TaskPriority.NORMAL,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.05,
    ) -> Tuple[InvestigationTask, bool]:
        """
        Submits a task to the queue with idempotency deduplication.
        Returns (task, is_deduplicated).
        """
        prio = TaskPriority.from_str(priority)

        # Generate idempotency key if not provided
        if not idempotency_key:
            canonical_payload = json.dumps(payload, sort_keys=True)
            idempotency_key = hashlib.sha256(f"{task_type}:{canonical_payload}".encode("utf-8")).hexdigest()[:16]

        with self._lock:
            # Check idempotency
            if idempotency_key in self._idempotency_map:
                existing_id = self._idempotency_map[idempotency_key]
                existing_task = self._tasks.get(existing_id)
                if existing_task and existing_task.status in [
                    TaskStatus.PENDING,
                    TaskStatus.RUNNING,
                    TaskStatus.COMPLETED,
                ]:
                    return existing_task, True

            self._sequence_counter += 1
            task_id = f"task_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            task = InvestigationTask(
                task_id=task_id,
                task_type=task_type,
                payload=payload,
                priority=prio.value,
                idempotency_key=idempotency_key,
                status=TaskStatus.PENDING,
                created_at=time.time(),
                max_retries=max_retries,
                backoff_factor=backoff_factor,
                sequence_id=self._sequence_counter,
            )

            self._tasks[task_id] = task
            self._idempotency_map[idempotency_key] = task_id
            heapq.heappush(self._heap, (task.priority, task.sequence_id, task_id))
            self._cv.notify()
            return task, False

    def get_task(self, task_id: str) -> Optional[InvestigationTask]:
        """Retrieves a task by task_id."""
        with self._lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancels a pending or running task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            if task.started_at:
                task.duration_ms = round((task.completed_at - task.started_at) * 1000, 2)
            return True

    # -------------------------------------------------------------------------
    # Execution & Processing
    # -------------------------------------------------------------------------

    def _execute_task(self, task: InvestigationTask):
        """Executes a single task with error handling, retries, and DLQ."""
        handler = self._handlers.get(task.task_type)
        if not handler:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = f"No handler registered for task type '{task.task_type}'"
                task.completed_at = time.time()
                self._dead_letter_queue.append(task.task_id)
            return

        with self._lock:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()

        start_t = time.time()
        try:
            res = handler(task)
            duration = round((time.time() - start_t) * 1000, 2)
            with self._lock:
                task.status = TaskStatus.COMPLETED
                task.result = res
                task.completed_at = time.time()
                task.duration_ms = duration
                task.error = None
        except Exception as exc:
            duration = round((time.time() - start_t) * 1000, 2)
            with self._lock:
                task.error = str(exc)
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING
                    # Exponential backoff delay
                    backoff_delay = task.backoff_factor * (2 ** (task.retry_count - 1))
                    time.sleep(backoff_delay)
                    self._sequence_counter += 1
                    task.sequence_id = self._sequence_counter
                    heapq.heappush(self._heap, (task.priority, task.sequence_id, task.task_id))
                    self._cv.notify()
                else:
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
                    task.duration_ms = duration
                    self._dead_letter_queue.append(task.task_id)

    def process_next_sync(self) -> Optional[InvestigationTask]:
        """
        Synchronously processes the next highest-priority task from the queue.
        Helpful for deterministic tests and single-threaded execution.
        """
        task = None
        with self._lock:
            while self._heap:
                prio, seq, tid = heapq.heappop(self._heap)
                cand = self._tasks.get(tid)
                if cand and cand.status == TaskStatus.PENDING:
                    task = cand
                    break

        if task:
            self._execute_task(task)
            return task
        return None

    def process_all_sync(self) -> int:
        """Processes all pending tasks synchronously until the queue is empty."""
        processed = 0
        while True:
            t = self.process_next_sync()
            if not t:
                break
            processed += 1
        return processed

    # -------------------------------------------------------------------------
    # Worker Pool Management
    # -------------------------------------------------------------------------

    def _worker_loop(self):
        while self._running:
            task = None
            with self._cv:
                while self._running and not self._has_pending_task():
                    self._cv.wait(timeout=0.2)

                if not self._running:
                    break

                while self._heap:
                    prio, seq, tid = heapq.heappop(self._heap)
                    cand = self._tasks.get(tid)
                    if cand and cand.status == TaskStatus.PENDING:
                        task = cand
                        break

            if task:
                self._execute_task(task)

    def _has_pending_task(self) -> bool:
        return any(
            t_id in self._tasks and self._tasks[t_id].status == TaskStatus.PENDING
            for _, _, t_id in self._heap
        )

    def start_workers(self, count: Optional[int] = None):
        """Starts background worker threads."""
        with self._lock:
            if self._running:
                return
            self._running = True
            num_workers = count or self.max_workers
            self._workers = []
            for i in range(num_workers):
                t = threading.Thread(target=self._worker_loop, name=f"InvestigationWorker-{i+1}", daemon=True)
                t.start()
                self._workers.append(t)

    def stop_workers(self, timeout: float = 2.0):
        """Stops all worker threads gracefully."""
        with self._lock:
            self._running = False
            self._cv.notify_all()

        for t in self._workers:
            t.join(timeout=timeout)
        self._workers.clear()

    # -------------------------------------------------------------------------
    # Dead Letter Queue & Inspection
    # -------------------------------------------------------------------------

    def get_dead_letter_tasks(self) -> List[InvestigationTask]:
        """Returns all failed tasks in the dead-letter queue."""
        with self._lock:
            return [self._tasks[tid] for tid in self._dead_letter_queue if tid in self._tasks]

    def retry_dlq_task(self, task_id: str) -> Optional[InvestigationTask]:
        """Re-enqueues a failed task from the DLQ, resetting its retries."""
        with self._lock:
            if task_id not in self._dead_letter_queue:
                return None
            self._dead_letter_queue.remove(task_id)
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.status = TaskStatus.PENDING
            task.retry_count = 0
            task.error = None
            self._sequence_counter += 1
            task.sequence_id = self._sequence_counter
            heapq.heappush(self._heap, (task.priority, task.sequence_id, task.task_id))
            self._cv.notify()
            return task

    # -------------------------------------------------------------------------
    # Metrics & Observability
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Returns comprehensive queue throughput and latency statistics."""
        with self._lock:
            counts = {
                TaskStatus.PENDING.value: 0,
                TaskStatus.RUNNING.value: 0,
                TaskStatus.COMPLETED.value: 0,
                TaskStatus.FAILED.value: 0,
                TaskStatus.CANCELLED.value: 0,
            }
            type_counts: Dict[str, int] = {}
            priority_counts: Dict[str, int] = {}
            durations: List[float] = []

            for task in self._tasks.values():
                counts[task.status] = counts.get(task.status, 0) + 1
                type_counts[task.task_type] = type_counts.get(task.task_type, 0) + 1
                p_name = TaskPriority(task.priority).name if task.priority in TaskPriority._value2member_map_ else str(task.priority)
                priority_counts[p_name] = priority_counts.get(p_name, 0) + 1
                if task.duration_ms is not None:
                    durations.append(task.duration_ms)

            durations.sort()
            avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
            p95_duration = round(durations[int(len(durations) * 0.95)], 2) if durations else 0.0

            return {
                "total_tasks": len(self._tasks),
                "queue_depth": counts[TaskStatus.PENDING.value],
                "active_tasks": counts[TaskStatus.RUNNING.value],
                "completed_tasks": counts[TaskStatus.COMPLETED.value],
                "failed_tasks": counts[TaskStatus.FAILED.value],
                "cancelled_tasks": counts[TaskStatus.CANCELLED.value],
                "dlq_size": len(self._dead_letter_queue),
                "active_workers": sum(1 for t in self._workers if t.is_alive()),
                "max_workers": self.max_workers,
                "avg_duration_ms": avg_duration,
                "p95_duration_ms": p95_duration,
                "status_breakdown": counts,
                "type_breakdown": type_counts,
                "priority_breakdown": priority_counts,
            }

    # -------------------------------------------------------------------------
    # Snapshot Persistence
    # -------------------------------------------------------------------------

    def export_snapshot(self) -> Dict[str, Any]:
        """Exports queue state to a serializable dictionary."""
        with self._lock:
            return {
                "tasks": [t.to_dict() for t in self._tasks.values()],
                "dead_letter_queue": list(self._dead_letter_queue),
                "idempotency_map": dict(self._idempotency_map),
                "sequence_counter": self._sequence_counter,
            }

    def load_snapshot(self, snapshot: Dict[str, Any]):
        """Loads queue state from an exported snapshot."""
        with self._lock:
            self._tasks.clear()
            self._heap.clear()
            self._idempotency_map = dict(snapshot.get("idempotency_map", {}))
            self._dead_letter_queue = list(snapshot.get("dead_letter_queue", []))
            self._sequence_counter = int(snapshot.get("sequence_counter", 0))

            for td in snapshot.get("tasks", []):
                t = InvestigationTask(
                    task_id=td["task_id"],
                    task_type=td["task_type"],
                    payload=td["payload"],
                    priority=td.get("priority", TaskPriority.NORMAL),
                    idempotency_key=td.get("idempotency_key"),
                    status=td.get("status", TaskStatus.PENDING),
                    created_at=td.get("created_at", time.time()),
                    started_at=td.get("started_at"),
                    completed_at=td.get("completed_at"),
                    duration_ms=td.get("duration_ms"),
                    result=td.get("result"),
                    error=td.get("error"),
                    retry_count=td.get("retry_count", 0),
                    max_retries=td.get("max_retries", 3),
                    backoff_factor=td.get("backoff_factor", 0.05),
                    sequence_id=td.get("sequence_id", 0),
                )
                self._tasks[t.task_id] = t
                if t.status == TaskStatus.PENDING:
                    heapq.heappush(self._heap, (t.priority, t.sequence_id, t.task_id))
