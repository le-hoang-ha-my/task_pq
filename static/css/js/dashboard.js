
// API Functions

/**
 * Fetch dashboard data from API
 * @returns {Promise<Object>} Dashboard data
 */
async function fetchDashboard() {
    try {
        const response = await fetch('/api/dashboard');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Error fetching dashboard:', error);
        showError('Failed to fetch dashboard data. Retrying...');
    }
}

/**
 * Submit a new task via API
 * @param {string} funcName - Function name
 * @param {string} priority - Task priority
 * @param {number} maxRetries - Maximum retry attempts
 * @returns {Promise<Object>} Task submission result
 */
async function submitTask(funcName, priority, maxRetries) {
    const response = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            func_name: funcName,
            priority: priority,
            max_retries: parseInt(maxRetries)
        })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

// DOM Update Functions

/**
 * Update all dashboard elements with new data
 * @param {Object} data - Dashboard data from API
 */
function updateDashboard(data) {
    updateMetrics(data.metrics, data.queue_size);
    updateWorkers(data.workers);
    updateTasksTable(data.recent_tasks);
}

/**
 * Update metrics cards
 * @param {Object} metrics - Metrics data
 * @param {number} queueSize - Current queue size
 */
function updateMetrics(metrics, queueSize) {
    document.getElementById('total-tasks').textContent = metrics.total_tasks;
    document.getElementById('completed-tasks').textContent = metrics.completed_tasks;
    document.getElementById('failed-tasks').textContent = metrics.failed_tasks;
    document.getElementById('queue-size').textContent = queueSize;
    document.getElementById('avg-duration').textContent = metrics.avg_duration + 's';
    document.getElementById('success-rate').textContent = metrics.success_rate + '% success rate';
}

/**
 * Update workers status display
 * @param {Array} workers - Array of worker objects
 */
function updateWorkers(workers) {
    const container = document.getElementById('workers-container');
    
    container.innerHTML = workers.map(worker => {
        const isBusy = worker.current_task !== null;
        const taskInfo = isBusy 
            ? `<div style="color: #94a3b8; font-size: 0.875rem; margin-top: 8px;">
                Processing: ${escapeHtml(worker.current_task.name)}
               </div>`
            : '';
        
        return `
            <div class="worker-card">
                <div class="worker-header">
                    <span class="worker-id">Worker ${worker.id}</span>
                    <span class="status-badge ${isBusy ? 'status-busy' : 'status-idle'}">
                        ${isBusy ? 'Busy' : 'Idle'}
                    </span>
                </div>
                ${taskInfo}
            </div>
        `;
    }).join('');
}

/**
 * Update tasks table
 * @param {Array} tasks - Array of task objects
 */
function updateTasksTable(tasks) {
    const tbody = document.getElementById('tasks-tbody');
    
    if (tasks.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; color: #64748b; padding: 30px;">
                    No tasks yet. Submit a task to get started.
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = tasks.map(task => {
        const created = formatTimestamp(task.created_at);
        const duration = calculateDuration(task);
        
        return `
            <tr>
                <td class="task-id" title="${escapeHtml(task.id)}">${escapeHtml(task.id.substring(0, 8))}</td>
                <td>${escapeHtml(task.name)}</td>
                <td class="priority-${task.priority.toLowerCase()}">${task.priority}</td>
                <td>
                    <span class="task-status status-${task.status.toLowerCase()}">
                        ${task.status}
                    </span>
                </td>
                <td>${task.retry_count}/${task.max_retries}</td>
                <td>${created}</td>
                <td>${duration}</td>
            </tr>
        `;
    }).join('');
}

// Event Handlers

/**
 * Handle task form submission
 * @param {Event} event - Form submit event
 */
async function handleTaskSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const taskName = document.getElementById('task-name').value.trim();
    const priority = document.getElementById('task-priority').value;
    const maxRetries = document.getElementById('max-retries').value;
    
    // Disable form during submission
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = 'Submitting...';
    
    try {
        const result = await submitTask(taskName, priority, maxRetries);
        console.log('Task submitted:', result);
        
        // Clear form
        document.getElementById('task-name').value = '';
        
        // Show success feedback
        showSuccess('Task submitted successfully!');
        
        // Refresh dashboard immediately
        fetchDashboard();
    } catch (error) {
        console.error('Error submitting task:', error);
        showError('Failed to submit task. Please try again.');
    } finally {
        // Re-enable form
        submitButton.disabled = false;
        submitButton.textContent = originalText;
    }
}

// Utility Functions

/**
 * Format ISO timestamp to readable time
 * @param {string} isoString - ISO 8601 timestamp
 * @returns {string} Formatted time string
 */
function formatTimestamp(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString();
}

/**
 * Calculate task duration
 * @param {Object} task - Task object
 * @returns {string} Duration string
 */
function calculateDuration(task) {
    if (!task.completed_at || !task.started_at) {
        return '-';
    }
    
    const start = new Date(task.started_at);
    const end = new Date(task.completed_at);
    const durationSeconds = (end - start) / 1000;
    
    return durationSeconds.toFixed(2) + 's';
}

/**
 * Escape HTML to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Show success message
 * @param {string} message - Success message
 */
function showSuccess(message) {
    console.log('Success: ', message);
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    console.error('Error: ', message);
}

// Initialization

/**
 * Initialize dashboard when DOM is ready
 */
function initDashboard() {
    console.log('Initializing Task Queue Dashboard...');
    
    // Set up form handler
    const taskForm = document.getElementById('task-form');
    if (taskForm) {
        taskForm.addEventListener('submit', handleTaskSubmit);
    }
    
    // Initial data fetch
    fetchDashboard();
    
    // Set up auto-refresh
    setInterval(fetchDashboard, REFRESH_INTERVAL);
    
    console.log(`Dashboard initialized. Auto-refresh every ${REFRESH_INTERVAL}ms`);
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    // DOM already loaded
    initDashboard();
}