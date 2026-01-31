"""
Priority Queue - Fast lane for high-stakes simulations

Features:
1. Priority-based task ordering
2. Fast lane for critical simulations (LAL @ CLE type games)
3. Background queue for low-priority tasks
4. Concurrency limits to prevent overload
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Optional, Dict, List, Awaitable
from enum import IntEnum
import logging
import uuid

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Priority levels (lower number = higher priority)."""
    CRITICAL = 0    # Health checks, must never fail
    HIGH = 1        # User-facing simulations, LAL @ CLE
    MEDIUM = 2      # Standard requests
    LOW = 3         # Background refreshes
    BACKGROUND = 4  # Can be delayed indefinitely


@dataclass(order=True)
class PriorityTask:
    """A task with priority ordering."""
    priority: Priority
    timestamp: datetime = field(compare=False)
    task_id: str = field(compare=False)
    func: Callable = field(compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    result: Optional[Any] = field(default=None, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    status: str = field(default="pending", compare=False)


class PriorityQueue:
    """
    CPU resource allocation by priority.
    
    High-stakes simulations (LAL @ CLE) get the fast lane.
    Background tasks (Hustle Stat refresh) get queued at lower priority.
    
    Concurrency Control:
    - Max concurrent HIGH priority: 4
    - Max concurrent MEDIUM priority: 8
    - Max concurrent LOW/BACKGROUND: 2
    """
    
    # Concurrency limits by priority
    CONCURRENCY_LIMITS = {
        Priority.CRITICAL: 10,   # Always allow critical
        Priority.HIGH: 4,
        Priority.MEDIUM: 8,
        Priority.LOW: 2,
        Priority.BACKGROUND: 2
    }
    
    def __init__(self):
        """Initialize the priority queue."""
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: Dict[str, PriorityTask] = {}
        self._completed: Dict[str, PriorityTask] = {}
        self._semaphores: Dict[Priority, asyncio.Semaphore] = {
            p: asyncio.Semaphore(limit) 
            for p, limit in self.CONCURRENCY_LIMITS.items()
        }
        self._processor_task: Optional[asyncio.Task] = None
        self._running_flag = False
        
        self._stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "by_priority": {p.name: 0 for p in Priority}
        }
        
        logger.info("[NEXUS] PriorityQueue initialized")
    
    async def start(self):
        """Start the background processor."""
        if not self._running_flag:
            self._running_flag = True
            self._processor_task = asyncio.create_task(self._process_queue())
            logger.info("[NEXUS] PriorityQueue processor started")
    
    async def stop(self):
        """Stop the background processor."""
        self._running_flag = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("[NEXUS] PriorityQueue processor stopped")
    
    async def submit(
        self,
        func: Callable[..., Awaitable[Any]],
        priority: Priority = Priority.MEDIUM,
        *args,
        **kwargs
    ) -> str:
        """
        Submit a task to the priority queue.
        
        Args:
            func: Async callable to execute
            priority: Task priority level
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = PriorityTask(
            priority=priority,
            timestamp=datetime.now(),
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs
        )
        
        await self._queue.put(task)
        self._stats["total_submitted"] += 1
        self._stats["by_priority"][priority.name] += 1
        
        logger.debug(f"[NEXUS] Task {task_id} submitted with priority {priority.name}")
        
        return task_id
    
    async def submit_and_wait(
        self,
        func: Callable[..., Awaitable[Any]],
        priority: Priority = Priority.MEDIUM,
        timeout: float = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Submit a task and wait for its result.
        
        Args:
            func: Async callable to execute
            priority: Task priority level
            timeout: Max seconds to wait for result
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Task result
            
        Raises:
            TimeoutError: If task doesn't complete in time
            Exception: If task fails
        """
        task_id = await self.submit(func, priority, *args, **kwargs)
        
        # Wait for completion
        start_time = datetime.now()
        while True:
            task = self._completed.get(task_id)
            if task:
                if task.error:
                    raise Exception(task.error)
                return task.result
            
            # Check timeout
            if timeout:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
            
            await asyncio.sleep(0.05)
    
    async def execute_immediate(
        self,
        func: Callable[..., Awaitable[Any]],
        priority: Priority = Priority.HIGH,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute immediately with priority-based concurrency control.
        
        For HIGH priority tasks that need fast-lane execution.
        Bypasses the queue but respects concurrency limits.
        """
        semaphore = self._semaphores.get(priority, self._semaphores[Priority.MEDIUM])
        
        async with semaphore:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
    
    async def _process_queue(self):
        """Background processor for queued tasks."""
        while self._running_flag:
            try:
                # Get next task (blocks if queue is empty)
                task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # Get semaphore for this priority
                semaphore = self._semaphores.get(
                    task.priority, 
                    self._semaphores[Priority.MEDIUM]
                )
                
                # Execute with concurrency limit
                asyncio.create_task(
                    self._execute_task(task, semaphore)
                )
                
            except asyncio.TimeoutError:
                # No tasks in queue, continue loop
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[NEXUS] Queue processor error: {e}")
    
    async def _execute_task(
        self, 
        task: PriorityTask, 
        semaphore: asyncio.Semaphore
    ):
        """Execute a single task with semaphore control."""
        async with semaphore:
            self._running[task.task_id] = task
            task.status = "running"
            
            try:
                if asyncio.iscoroutinefunction(task.func):
                    task.result = await task.func(*task.args, **task.kwargs)
                else:
                    task.result = task.func(*task.args, **task.kwargs)
                
                task.status = "completed"
                self._stats["total_completed"] += 1
                logger.debug(f"[NEXUS] Task {task.task_id} completed")
                
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                self._stats["total_failed"] += 1
                logger.warning(f"[NEXUS] Task {task.task_id} failed: {e}")
            finally:
                del self._running[task.task_id]
                self._completed[task.task_id] = task
                
                # Clean up old completed tasks (keep last 100)
                if len(self._completed) > 100:
                    oldest = sorted(
                        self._completed.values(), 
                        key=lambda t: t.timestamp
                    )[:50]
                    for t in oldest:
                        del self._completed[t.task_id]
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task by ID."""
        # Check running
        if task_id in self._running:
            task = self._running[task_id]
            return {
                "task_id": task_id,
                "status": task.status,
                "priority": task.priority.name,
                "submitted_at": task.timestamp.isoformat()
            }
        
        # Check completed
        if task_id in self._completed:
            task = self._completed[task_id]
            return {
                "task_id": task_id,
                "status": task.status,
                "priority": task.priority.name,
                "submitted_at": task.timestamp.isoformat(),
                "result_available": task.result is not None,
                "error": task.error
            }
        
        return None
    
    def get_queue_depth(self) -> Dict[str, int]:
        """Get current queue depth by priority."""
        return {
            "total_pending": self._queue.qsize(),
            "running": len(self._running),
            "completed": len(self._completed)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            **self._stats,
            "queue_depth": self.get_queue_depth(),
            "success_rate": (
                self._stats["total_completed"] / 
                max(self._stats["total_submitted"], 1) * 100
            )
        }
    
    def clear_completed(self):
        """Clear completed task history."""
        self._completed.clear()
