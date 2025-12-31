import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class QueueConfig:
    """
    Configuration for the task queue system.
    All values can be overridden via environment variables with the QUEUE_ prefix.
    """
    
    # Worker config
    num_workers: int
    worker_timeout: float
    
    # Retry config
    default_max_retries: int
    default_retry_delay: float
    max_retry_delay: float
    
    # Queue config
    queue_timeout: float
    max_queue_size: Optional[int]
    
    # Metrics config
    metrics_retention_size: int
    
    # Logging config
    log_level: str
    
    @classmethod
    def from_env(cls) -> 'QueueConfig':
        """
        Load config from environment variables.
        """
        return cls(
            # Worker settings
            num_workers=int(os.getenv('QUEUE_NUM_WORKERS', '4')),
            worker_timeout=float(os.getenv('QUEUE_WORKER_TIMEOUT', '1.0')),
            
            # Retry settings
            default_max_retries=int(os.getenv('QUEUE_DEFAULT_MAX_RETRIES', '3')),
            default_retry_delay=float(os.getenv('QUEUE_DEFAULT_RETRY_DELAY', '1.0')),
            max_retry_delay=float(os.getenv('QUEUE_MAX_RETRY_DELAY', '60.0')),
            
            # Queue settings
            queue_timeout=float(os.getenv('QUEUE_TIMEOUT', '1.0')),
            max_queue_size=int(os.getenv('QUEUE_MAX_SIZE', '0')) or None,
            
            # Metrics settings
            metrics_retention_size=int(os.getenv('QUEUE_METRICS_RETENTION', '1000')),
            
            # Logging
            log_level=os.getenv('QUEUE_LOG_LEVEL', 'INFO'),
        )


@dataclass
class WebConfig:
    """
    Configuration for the web dashboard and API.
    All values can be overridden via environment variables with the WEB_ prefix.
    """
    
    # Server Configuration
    host: str
    port: int
    debug: bool
    
    # Dashboard Configuration
    refresh_interval: int  # milliseconds
    max_recent_tasks: int
    
    # CORS Configuration
    cors_origins: str
    
    # API Keys
    api_key: Optional[str]
    
    @classmethod
    def from_env(cls) -> 'WebConfig':
        """
        Load web configuration from environment variables.
        
        Returns:
            WebConfig instance with values from environment or defaults
        """
        return cls(
            # Server settings
            host=os.getenv('WEB_HOST', '0.0.0.0'),
            port=int(os.getenv('WEB_PORT', '5000')),
            debug=os.getenv('WEB_DEBUG', 'false').lower() == 'true',
            
            # Dashboard settings
            refresh_interval=int(os.getenv('WEB_REFRESH_INTERVAL', '2000')),
            max_recent_tasks=int(os.getenv('WEB_MAX_RECENT_TASKS', '20')),
            
            # CORS
            cors_origins=os.getenv('WEB_CORS_ORIGINS', '*'),
            
            # API Key (optional, for future use)
            api_key=os.getenv('WEB_API_KEY'),
        )


def print_config(queue_config: QueueConfig, web_config: Optional[WebConfig] = None) -> None:
    print("\n" + "="*60)
    print("Queue config")
    print("="*60)
    
    print("\nQueue config")
    print(f"Workers: {queue_config.num_workers}")
    print(f"Worker timeout: {queue_config.worker_timeout}s")
    print(f"Queue timeout: {queue_config.queue_timeout}s")
    print(f"Max queue size: {queue_config.max_queue_size or 'Unlimited'}")
    
    print("\nRetry config")
    print(f"Default max retries: {queue_config.default_max_retries}")
    print(f"Default retry delay: {queue_config.default_retry_delay}s")
    print(f"Max retry delay: {queue_config.max_retry_delay}s")
    
    print("\nMetrics config")
    print(f"Retention size: {queue_config.metrics_retention_size}")
    
    print("\nLogging config")
    print(f"Log level: {queue_config.log_level}")
    
    if web_config:
        print("\nWeb config")
        print(f"Host: {web_config.host}")
        print(f"Port: {web_config.port}")
        print(f"Debug: {web_config.debug}")
        print(f"Refresh interval: {web_config.refresh_interval}ms")
        print(f"Max recent tasks: {web_config.max_recent_tasks}")
        print(f"CORS origins: {web_config.cors_origins}")
        print(f"API Key configured: {'Yes' if web_config.api_key else 'No'}")
    
    print("="*60 + "\n")


def validate_config(config: QueueConfig) -> list:
    """
    Validate configuration values and return list of warnings.
    """
    warnings = []
    
    if config.num_workers < 1:
        warnings.append("num_workers must be at least 1")
    elif config.num_workers > 100:
        warnings.append("num_workers > 100 may cause resource issues")
    
    if config.default_max_retries < 0:
        warnings.append("default_max_retries cannot be negative")
    elif config.default_max_retries > 10:
        warnings.append("default_max_retries > 10 may cause long delays")
    
    if config.default_retry_delay < 0:
        warnings.append("default_retry_delay cannot be negative")
    
    if config.max_retry_delay < config.default_retry_delay:
        warnings.append("max_retry_delay should be >= default_retry_delay")
    
    if config.metrics_retention_size < 1:
        warnings.append("metrics_retention_size must be at least 1")
    
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config.log_level not in valid_log_levels:
        warnings.append(f"log_level must be one of: {', '.join(valid_log_levels)}")
    
    return warnings

if __name__ == "__main__":
    queue_config = QueueConfig.from_env()
    web_config = WebConfig.from_env()
    
    print_config(queue_config, web_config)
    
    warnings = validate_config(queue_config)
    if warnings:
        print("Configuration Warnings:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print()