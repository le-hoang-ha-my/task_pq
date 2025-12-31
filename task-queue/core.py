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
