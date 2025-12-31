#!/usr/bin/env python3
"""
Quick Start Script for Task Queue System
Demonstrates basic usage with environment configuration.
"""

import os
import time
from core import TaskQueueSystem, TaskPriority

# Set environment variables (normally done via .env or export)
os.environ.setdefault('QUEUE_NUM_WORKERS', '3')
os.environ.setdefault('QUEUE_LOG_LEVEL', 'INFO')
os.environ.setdefault('QUEUE_DEFAULT_MAX_RETRIES', '2')


def main():
    print("\n" + "="*60)
    print("Task Queue System - Quick Start")
    print("="*60)
    
    # Create system (automatically loads from environment)
    print("\n1. Creating task queue system...")
    system = TaskQueueSystem()
    print(f"   ✓ System created with {system.num_workers} workers")
    
    # Register some example tasks
    print("\n2. Registering tasks...")
    
    @system.registry.register("greet")
    def greet(name: str, greeting: str = "Hello"):
        """Simple greeting task."""
        time.sleep(0.5)
        message = f"{greeting}, {name}!"
        print(f"   📝 {message}")
        return message
    
    @system.registry.register("calculate")
    def calculate(operation: str, a: int, b: int):
        """Math operation task."""
        time.sleep(0.3)
        if operation == "add":
            result = a + b
        elif operation == "multiply":
            result = a * b
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        print(f"   🔢 {a} {operation} {b} = {result}")
        return result
    
    @system.registry.register("sometimes_fails")
    def sometimes_fails(should_fail: bool = False):
        """Task that demonstrates retry logic."""
        if should_fail:
            raise RuntimeError("Task failed as requested")
        return "Success!"
    
    print("   ✓ Registered 3 tasks")
    
    # Start the system
    print("\n3. Starting workers...")
    system.start()
    print("   ✓ Workers started")
    
    # Submit tasks with different priorities
    print("\n4. Submitting tasks...")
    
    task_ids = []
    
    # High priority task
    tid = system.submit_task(
        "greet",
        args=("Alice",),
        kwargs={"greeting": "Hi"},
        priority=TaskPriority.HIGH
    )
    task_ids.append(("greet:Alice", tid))
    print(f"   → Submitted HIGH priority task: greet:Alice")
    
    # Medium priority calculation
    tid = system.submit_task(
        "calculate",
        args=("add", 10, 20),
        priority=TaskPriority.MEDIUM
    )
    task_ids.append(("calculate:add", tid))
    print(f"   → Submitted MEDIUM priority task: calculate:add")
    
    # Low priority task
    tid = system.submit_task(
        "greet",
        args=("Bob",),
        priority=TaskPriority.LOW
    )
    task_ids.append(("greet:Bob", tid))
    print(f"   → Submitted LOW priority task: greet:Bob")
    
    # Task that will fail and retry
    tid = system.submit_task(
        "sometimes_fails",
        kwargs={"should_fail": True},
        priority=TaskPriority.MEDIUM,
        max_retries=2
    )
    task_ids.append(("sometimes_fails", tid))
    print(f"   → Submitted task that will fail: sometimes_fails")
    
    # Wait for processing
    print("\n5. Processing tasks...")
    time.sleep(4)
    
    # Check results
    print("\n6. Task Results:")
    for name, task_id in task_ids:
        status = system.get_task_status(task_id)
        if status:
            print(f"\n   Task: {name}")
            print(f"   Status: {status['status']}")
            print(f"   Retries: {status['retry_count']}/{status['max_retries']}")
            if status['status'] == 'COMPLETED':
                print(f"   Result: {status['result']}")
            elif status['error']:
                print(f"   Error: {status['error']}")
    
    # Show metrics
    print("\n7. System Metrics:")
    stats = system.metrics.get_stats()
    print(f"   Total tasks: {stats['total_tasks']}")
    print(f"   Completed: {stats['completed_tasks']}")
    print(f"   Failed: {stats['failed_tasks']}")
    print(f"   Success rate: {stats['success_rate']}%")
    print(f"   Avg duration: {stats['avg_duration']}s")
    
    if stats['errors_by_type']:
        print(f"   Errors by type: {dict(stats['errors_by_type'])}")
    
    # Clean up
    print("\n8. Shutting down...")
    system.stop()
    print("   ✓ System stopped")
    
    print("\n" + "="*60)
    print("Quick Start Complete!")
    print("\nNext steps:")
    print("  • Run tests: python task_queue_tests.py")
    print("  • Start web dashboard: python task_queue_web.py")
    print("  • See examples: python examples.py")
    print("  • Read README.md for full documentation")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()