# Task Queue System

A Python task queue with priority scheduling, automatic retries, and real-time monitoring dashboard.

## Quick Start

### 1. Installation
```bash
# Clone repository
git clone <your-repo-url>
cd task_pq

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install flask flask-cors

# Configure environment
cp .env.example .env
```

### 2. Run the System
```bash
python web.py
```

Visit **http://localhost:8000** in your browser.

**Note for Mac users:** Port 5000 conflicts with macOS AirPlay. Here, I set the port to 8000 by default.

## Usage

### Option 1: Web dashboard

1. Start the server:
```bash
   python web.py
```

2. Open browser: http://localhost:8000

3. Submit tasks (sample tasks included as quick actions on the website)

4. Monitor: Watch the dashboard auto-refresh showing:
   - Total/completed/failed task counts
   - Success rate and average duration
   - Worker status (busy/idle)
   - Recent tasks with status

### Option 2: REST API

- Submit a Task:
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "func_name": "example_task",
    "args": [2.0],
    "priority": "HIGH",
    "max_retries": 3
  }'
```

Response:
```json
{
  "task_id": "abc-123-xyz",
  "status": "submitted",
  "message": "Task abc-123... submitted successfully"
}
```

- Check task status:
```bash
curl http://localhost:8000/api/tasks/abc-123-xyz
```

- Get system metrics:
```bash
curl http://localhost:8000/api/metrics
```

- List available tasks:
```bash
curl http://localhost:8000/api/registered-tasks
```

### Option 3: Python
```python
from core import TaskQueueSystem, TaskPriority

# Create and start system
system = TaskQueueSystem(num_workers=4)

# Register your custom task
@system.registry.register("my_task")
def my_task(name: str, count: int):
    print(f"Processing {count} items for {name}")
    return f"Completed {count} items"

# Start workers
system.start()

# Submit task
task_id = system.submit_task(
    func_name="my_task",
    args=("Alice", 100),
    priority=TaskPriority.HIGH,
    max_retries=3
)

# Check status
import time
time.sleep(2)
status = system.get_task_status(task_id)
print(f"Status: {status['status']}")
print(f"Result: {status['result']}")

# Stop system
system.stop()
```

## Adding your own tasks

Edit `web.py` and add functions to the `register_example_tasks()` function:
```python
def register_example_tasks(system: TaskQueueSystem) -> None:
    # ...existing tasks...
    
    # Add your custom task
    @system.registry.register("fetch_user_data")
    def fetch_user_data(user_id: int):
        """Fetch data for a user from API."""
        import requests
        response = requests.get(f'https://api.example.com/users/{user_id}')
        return response.json()
    
    @system.registry.register("send_sms")
    def send_sms(phone: str, message: str):
        """Send SMS notification."""
        print(f"SMS to {phone}: {message}")
        return True
```

Restart the server and submit via API:
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "func_name": "fetch_user_data",
    "args": [123],
    "priority": "HIGH"
  }'
```

## Notes

- Set `WEB_DEBUG=false` in production
- Consider adding API authentication for production use