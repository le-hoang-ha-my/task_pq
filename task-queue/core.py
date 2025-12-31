import logging
import time
import uuid
import os
import heapq
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from collections import defaultdict

log_level = os.getenv('QUEUE_LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """
    Task priority levels: lower value = higher priority
    """
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Task:
    """
    Represents a unit of work in the queue.
    
    Attributes:
        id: Unique task identifier
        name: Human-readable task name
        func_name: Name of the registered function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        priority: Task priority level
        status: Current task status
        max_retries: Maximum number of retry attempts
        retry_count: Current retry attempt number
        retry_delay: Initial retry delay in seconds (uses exponential backoff)
        created_at: Timestamp when task was created
        started_at: Timestamp when task execution started
        completed_at: Timestamp when task completed or failed
        error: Error message if task failed
        result: Return value if task completed successfully
    """
    id: str
    name: str
    func_name: str
    args: tuple
    kwargs: dict
    priority: TaskPriority
    status: TaskStatus = TaskStatus.PENDING
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Any = None
    
    def __lt__(self, other: 'Task') -> bool:
        """
        Enable heap comparison based on priority, then creation time.
        Lower priority value = higher priority in queue.
        """
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at
    
    def to_dict(self) -> dict:
        """Serialize task to dictionary for API responses."""
        data = asdict(self)
        data['priority'] = self.priority.name
        data['status'] = self.status.name
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


class TaskRegistry:
    """
    Registry for task functions that can be executed by workers.
    """
    
    def __init__(self):
        self._functions: Dict[str, Callable] = {}
        self._lock = threading.Lock()
    
    def register(self, name: str) -> Callable:
        """
        Decorator to register a function as an executable task.
        """
        def decorator(func: Callable) -> Callable:
            with self._lock:
                if name in self._functions:
                    logger.warning(f"Task '{name}' already registered, overwriting")
                self._functions[name] = func
                logger.info(f"Registered task: {name}")
            return func
        return decorator
    
    def get(self, name: str) -> Optional[Callable]:
        """
        Retrieve a registered function by name.
        """
        with self._lock:
            return self._functions.get(name)
    
    def list_tasks(self) -> List[str]:
        """
        Get list of all registered task names.
        """
        with self._lock:
            return list(self._functions.keys())
    
    def unregister(self, name: str) -> bool:
        """
        Remove a task from the registry.
        """
        with self._lock:
            if name in self._functions:
                del self._functions[name]
                logger.info(f"Unregistered task: {name}")
                return True
            return False


class TaskQueue:
    """
    Thread-safe priority queue for tasks.
    """
    
    def __init__(self):
        self._heap: List[Task] = []
        self._lock = threading.Lock()
        self._task_map: Dict[str, Task] = {}
        self._condition = threading.Condition(self._lock)
    
    def enqueue(self, task: Task) -> None:
        """
        Add a task to the queue.
        """
        with self._lock:
            heapq.heappush(self._heap, task)
            self._task_map[task.id] = task
            self._condition.notify()
            logger.debug(f"Task {task.id} enqueued with priority {task.priority.name}")
    
    def dequeue(self, timeout: Optional[float] = None) -> Optional[Task]:
        """
        Remove and return the highest priority task.
        Blocks until a task is available or timeout expires.
        """
        with self._condition:
            while not self._heap:
                if not self._condition.wait(timeout=timeout):
                    return None
            
            task = heapq.heappop(self._heap)
            logger.debug(f"Task {task.id} dequeued")
            return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieve a task by ID without removing it.
        """
        with self._lock:
            return self._task_map.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """
        Get all tasks in the system (for monitoring).
        """
        with self._lock:
            return list(self._task_map.values())
    
    def size(self) -> int:
        """
        Get number of pending tasks in queue.
        """
        with self._lock:
            return len(self._heap)


class Worker:
    """
    Worker thread that processes tasks from the queue.
    """
    
    def __init__(
        self,
        worker_id: int,
        queue: TaskQueue,
        registry: TaskRegistry,
        metrics: 'Metrics'
    ):
        """
        Initialize worker.
        
        Args:
            worker_id: Unique worker identifier
            queue: Shared task queue
            registry: Task function registry
            metrics: Metrics tracker
        """
        self.worker_id = worker_id
        self.queue = queue
        self.registry = registry
        self.metrics = metrics
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.current_task: Optional[Task] = None
    
    def start(self) -> None:
        """Start the worker thread."""
        if self._running:
            logger.warning(f"Worker {self.worker_id} already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Worker {self.worker_id} started")
    
    def stop(self) -> None:
        """Stop the worker thread."""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"Worker {self.worker_id} stopped")
    
    def _run(self) -> None:
        """Main worker loop."""
        while self._running:
            task = self.queue.dequeue(timeout=1.0)
            if task is None:
                continue
            
            self.current_task = task
            self._process_task(task)
            self.current_task = None
    
    def _process_task(self, task: Task) -> None:
        """
        Execute a single task with retry logic.
        """
        func = self.registry.get(task.func_name)
        if func is None:
            task.status = TaskStatus.FAILED
            task.error = f"Function '{task.func_name}' not registered"
            task.completed_at = datetime.now()
            logger.error(f"Task {task.id}: {task.error}")
            self.metrics.record_failure(task)
            return
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        logger.info(
            f"Worker {self.worker_id} processing task {task.id} "
            f"({task.name}) [attempt {task.retry_count + 1}/{task.max_retries + 1}]"
        )
        
        try:
            start_time = time.time()
            result = func(*task.args, **task.kwargs)
            duration = time.time() - start_time
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            self.metrics.record_success(task, duration)
            logger.info(f"Task {task.id} completed in {duration:.2f}s")
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            task.error = error_msg
            logger.error(f"Task {task.id} failed: {error_msg}")
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                
                # Exponential backoff
                delay = task.retry_delay * (2 ** (task.retry_count - 1))
                max_delay = float(os.getenv('QUEUE_MAX_RETRY_DELAY', '60.0'))
                delay = min(delay, max_delay)
                
                logger.info(
                    f"Retrying task {task.id} in {delay:.1f}s "
                    f"(attempt {task.retry_count}/{task.max_retries})"
                )
                
                time.sleep(delay)
                task.status = TaskStatus.PENDING
                self.queue.enqueue(task)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                self.metrics.record_failure(task)
                logger.error(
                    f"Task {task.id} failed permanently after "
                    f"{task.retry_count} retries"
                )


class Metrics:
    """
    Thread-safe metrics collection for monitoring queue performance.
    
    Tracks counts, durations, error types, and provides aggregated statistics.
    """
    
    def __init__(self, retention_size: Optional[int] = None):
        """
        Initialize metrics tracker.
        
        Args:
            retention_size: Number of task durations to keep in memory
        """
        self._lock = threading.Lock()
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_duration = 0.0
        self.task_durations: List[float] = []
        self.errors_by_type: Dict[str, int] = defaultdict(int)
        self.tasks_by_priority: Dict[str, int] = defaultdict(int)
        self.retention_size = retention_size or int(
            os.getenv('QUEUE_METRICS_RETENTION', '1000')
        )
    
    def record_enqueue(self, task: Task) -> None:
        """Record a task being added to the queue."""
        with self._lock:
            self.total_tasks += 1
            self.tasks_by_priority[task.priority.name] += 1
    
    def record_success(self, task: Task, duration: float) -> None:
        """Record a successful task completion."""
        with self._lock:
            self.completed_tasks += 1
            self.total_duration += duration
            self.task_durations.append(duration)
            
            # Keep only recent durations for memory efficiency
            if len(self.task_durations) > self.retention_size:
                self.task_durations.pop(0)
    
    def record_failure(self, task: Task) -> None:
        """Record a task failure."""
        with self._lock:
            self.failed_tasks += 1
            if task.error:
                error_type = task.error.split(':')[0].strip()
                self.errors_by_type[error_type] += 1
    
    def get_stats(self) -> dict:
        """
        Get current statistics snapshot.
        
        Returns:
            Dictionary containing all metrics
        """
        with self._lock:
            avg_duration = (
                self.total_duration / self.completed_tasks
                if self.completed_tasks > 0
                else 0
            )
            success_rate = (
                (self.completed_tasks / self.total_tasks * 100)
                if self.total_tasks > 0
                else 0
            )
            
            return {
                'total_tasks': self.total_tasks,
                'completed_tasks': self.completed_tasks,
                'failed_tasks': self.failed_tasks,
                'pending_tasks': self.total_tasks - self.completed_tasks - self.failed_tasks,
                'success_rate': round(success_rate, 2),
                'avg_duration': round(avg_duration, 3),
                'errors_by_type': dict(self.errors_by_type),
                'tasks_by_priority': dict(self.tasks_by_priority)
            }
    
    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self.total_tasks = 0
            self.completed_tasks = 0
            self.failed_tasks = 0
            self.total_duration = 0.0
            self.task_durations.clear()
            self.errors_by_type.clear()
            self.tasks_by_priority.clear()
            logger.info("Metrics reset")

