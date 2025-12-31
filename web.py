from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import os
import time
import logging
from typing import Optional

from core import TaskQueueSystem, TaskPriority

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

cors_origins = os.getenv('WEB_CORS_ORIGINS', '*')
if cors_origins != '*':
    CORS(app, origins=cors_origins.split(','))
else:
    CORS(app)

task_system: Optional[TaskQueueSystem] = None

def create_app(system: TaskQueueSystem) -> Flask:
    """
    Create and configure Flask application.
    """
    global task_system
    task_system = system
    
    refresh_interval = int(os.getenv('WEB_REFRESH_INTERVAL', '2000'))
    max_recent_tasks = int(os.getenv('WEB_MAX_RECENT_TASKS', '20'))
    
    # Dashboard
    @app.route('/')
    def index():
        """Serve the main dashboard page."""
        return render_template('dashboard.html', refresh_interval=refresh_interval)
    
    @app.route('/health')
    def health():
        """Health check endpoint for monitoring."""
        return jsonify({
            'status': 'healthy',
            'workers': len(task_system.workers),
            'queue_size': task_system.queue.size()
        })
    
    # API
    @app.route('/api/dashboard')
    def get_dashboard():
        """
        Get dashboard data.
        """
        try:
            data = task_system.get_dashboard_data()
            # Limit recent tasks based on configuration
            data['recent_tasks'] = data['recent_tasks'][:max_recent_tasks]
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/tasks', methods=['POST'])
    def submit_task():
        """
        Submit a new task to the queue.
        """
        try:
            data = request.json
            
            if not data or 'func_name' not in data:
                return jsonify({'error': 'func_name is required'}), 400
            
            # Validate and convert priority
            priority_str = data.get('priority', 'MEDIUM').upper()
            try:
                priority = TaskPriority[priority_str]
            except KeyError:
                return jsonify({
                    'error': f'Invalid priority: {priority_str}',
                    'valid_priorities': [p.name for p in TaskPriority]
                }), 400
            
            # Submit task
            task_id = task_system.submit_task(
                func_name=data['func_name'],
                args=tuple(data.get('args', [])),
                kwargs=data.get('kwargs', {}),
                priority=priority,
                max_retries=data.get('max_retries'),
                retry_delay=data.get('retry_delay'),
                task_name=data.get('task_name')
            )
            
            return jsonify({
                'task_id': task_id,
                'status': 'submitted',
                'message': f'Task {task_id[:8]}... submitted successfully'
            }), 201
            
        except Exception as e:
            logger.error(f"Error submitting task: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/tasks/<task_id>', methods=['GET'])
    def get_task(task_id: str):
        """
        Get status of a specific task.
        """
        try:
            task_data = task_system.get_task_status(task_id)
            
            if task_data is None:
                return jsonify({
                    'error': 'Task not found',
                    'task_id': task_id
                }), 404
            
            return jsonify(task_data)
            
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/metrics', methods=['GET'])
    def get_metrics():
        """
        Get system metrics.
        """
        try:
            return jsonify(task_system.metrics.get_stats())
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/registered-tasks', methods=['GET'])
    def list_registered_tasks():
        """
        List all registered task functions.
        """
        try:
            return jsonify({
                'tasks': task_system.registry.list_tasks(),
                'count': len(task_system.registry.list_tasks())
            })
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/workers', methods=['GET'])
    def get_workers():
        """
        Get worker status information.
        """
        try:
            workers_data = []
            for worker in task_system.workers:
                workers_data.append({
                    'id': worker.worker_id,
                    'status': 'busy' if worker.current_task else 'idle',
                    'current_task': worker.current_task.to_dict() if worker.current_task else None
                })
            return jsonify({
                'workers': workers_data,
                'total': len(workers_data)
            })
        except Exception as e:
            logger.error(f"Error getting workers: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Error Handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    return app


def register_example_tasks(system: TaskQueueSystem) -> None:
    """
    Register example tasks for demonstration.
    """
    @system.registry.register("example_task")
    def example_task(duration: float = 1.0) -> str:
        """Example task that sleeps for specified duration."""
        time.sleep(duration)
        return f"Task completed after {duration}s"
    
    @system.registry.register("send_email")
    def send_email(to: str, subject: str, body: str = "") -> str:
        """Simulate sending an email."""
        time.sleep(0.5)
        logger.info(f"Email sent to {to}: {subject}")
        return f"Email sent to {to}"
    
    @system.registry.register("process_data")
    def process_data(items: int) -> str:
        """Simulate data processing."""
        time.sleep(items * 0.1)
        return f"Processed {items} items"
    
    @system.registry.register("flaky_task")
    def flaky_task(fail_rate: float = 0.5) -> str:
        """Task that randomly fails for testing retry logic."""
        import random
        if random.random() < fail_rate:
            raise RuntimeError("Random failure")
        return "Success"
    
    logger.info("Example tasks registered")


def main():
    # Load configuration from environment
    host = os.getenv('WEB_HOST', '0.0.0.0')
    port = int(os.getenv('WEB_PORT', '8000'))
    debug = os.getenv('WEB_DEBUG', 'false').lower() == 'true'
    
    system = TaskQueueSystem()
    register_example_tasks(system)
    system.start()
    
    # Create Flask app
    app = create_app(system)
    
    try:
        print("\n" + "="*60)
        print("Task Queue System started")
        print("="*60)
        print(f"Dashboard: http://{host}:{port}")
        print(f"API Docs: http://{host}:{port}/api/dashboard")
        print(f"Health: http://{host}:{port}/health")
        print(f"Workers: {system.num_workers}")
        print(f"Debug Mode: {debug}")
        print("="*60)
        print("\nPress Ctrl+C to stop")
        print()
        
        app.run(debug=debug, host=host, port=port, threaded=True)
        
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        system.stop()
        print("Task queue system stopped")


if __name__ == "__main__":
    main()