"""
Monitoring metrics utilities for tracking system performance and usage.

This module provides comprehensive metrics collection including response times,
cache hit rates, error rates, and other key performance indicators.
"""

import time
import logging
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from threading import Lock
import statistics

logger = logging.getLogger(__name__)

@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass 
class MetricSummary:
    """Summary statistics for a metric."""
    count: int
    min_value: float
    max_value: float
    avg_value: float
    median_value: float
    p95_value: float
    p99_value: float
    recent_values: List[float]

class MetricsCollector:
    """
    Thread-safe metrics collector for tracking system performance.
    """
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.lock = Lock()
        
        # Store metrics as time series data
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Counters for simple increment metrics
        self.counters: Dict[str, int] = defaultdict(int)
        
        # Gauges for current value metrics
        self.gauges: Dict[str, float] = {}
        
        # Start time for uptime calculation
        self.start_time = time.time()
    
    def record_value(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a metric value with optional tags."""
        with self.lock:
            metric_value = MetricValue(value=value, tags=tags or {})
            self.metrics[metric_name].append(metric_value)
        
        logger.debug(f"Recorded metric {metric_name}: {value}")
    
    def increment_counter(self, counter_name: str, increment: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        with self.lock:
            self.counters[counter_name] += increment
        
        # Also record as a time series for trend analysis
        self.record_value(f"{counter_name}_rate", increment, tags)
    
    def set_gauge(self, gauge_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric to a specific value."""
        with self.lock:
            self.gauges[gauge_name] = value
        
        # Also record as time series
        self.record_value(gauge_name, value, tags)
    
    def get_metric_summary(self, metric_name: str, time_window_seconds: Optional[float] = None) -> Optional[MetricSummary]:
        """Get summary statistics for a metric."""
        with self.lock:
            if metric_name not in self.metrics:
                return None
            
            metric_data = list(self.metrics[metric_name])
        
        if not metric_data:
            return None
        
        # Filter by time window if specified
        if time_window_seconds:
            cutoff_time = time.time() - time_window_seconds
            metric_data = [m for m in metric_data if m.timestamp >= cutoff_time]
        
        if not metric_data:
            return None
        
        values = [m.value for m in metric_data]
        values.sort()
        
        return MetricSummary(
            count=len(values),
            min_value=min(values),
            max_value=max(values),
            avg_value=statistics.mean(values),
            median_value=statistics.median(values),
            p95_value=values[int(len(values) * 0.95)] if len(values) > 1 else values[0],
            p99_value=values[int(len(values) * 0.99)] if len(values) > 1 else values[0],
            recent_values=values[-10:]  # Last 10 values
        )
    
    def get_counter_value(self, counter_name: str) -> int:
        """Get current counter value."""
        with self.lock:
            return self.counters.get(counter_name, 0)
    
    def get_gauge_value(self, gauge_name: str) -> Optional[float]:
        """Get current gauge value."""
        with self.lock:
            return self.gauges.get(gauge_name)
    
    def get_all_metrics(self, time_window_seconds: Optional[float] = None) -> Dict[str, Any]:
        """Get all current metrics and summaries."""
        with self.lock:
            metric_names = list(self.metrics.keys())
            counter_names = list(self.counters.keys())
            gauge_names = list(self.gauges.keys())
        
        result = {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.start_time,
            "counters": {name: self.get_counter_value(name) for name in counter_names},
            "gauges": {name: self.get_gauge_value(name) for name in gauge_names},
            "summaries": {}
        }
        
        # Generate summaries for all metrics
        for metric_name in metric_names:
            summary = self.get_metric_summary(metric_name, time_window_seconds)
            if summary:
                result["summaries"][metric_name] = {
                    "count": summary.count,
                    "min": summary.min_value,
                    "max": summary.max_value,
                    "avg": round(summary.avg_value, 3),
                    "median": round(summary.median_value, 3),
                    "p95": round(summary.p95_value, 3),
                    "p99": round(summary.p99_value, 3)
                }
        
        return result
    
    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self.lock:
            self.metrics.clear()
            self.counters.clear()
            self.gauges.clear()
        
        logger.info("All metrics reset")

# Application-specific metrics functions

class APIMetrics:
    """Specific metrics for the API endpoints."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_request(self, endpoint: str, method: str, status_code: int, response_time_ms: float) -> None:
        """Record API request metrics."""
        tags = {
            "endpoint": endpoint,
            "method": method,
            "status_code": str(status_code)
        }
        
        # Response time
        self.collector.record_value("api_response_time_ms", response_time_ms, tags)
        
        # Request count
        self.collector.increment_counter("api_requests_total", tags=tags)
        
        # Error count
        if status_code >= 400:
            self.collector.increment_counter("api_errors_total", tags=tags)
    
    def record_cache_operation(self, operation: str, hit: bool, response_time_ms: float = 0) -> None:
        """Record cache operation metrics."""
        tags = {"operation": operation}
        
        # Cache hit/miss
        if hit:
            self.collector.increment_counter("cache_hits_total", tags=tags)
        else:
            self.collector.increment_counter("cache_misses_total", tags=tags)
        
        # Cache operation time
        if response_time_ms > 0:
            self.collector.record_value("cache_operation_time_ms", response_time_ms, tags)
    
    def record_external_service_call(self, service: str, success: bool, response_time_ms: float) -> None:
        """Record external service call metrics."""
        tags = {"service": service, "success": str(success)}
        
        # Service call count
        self.collector.increment_counter("external_service_calls_total", tags=tags)
        
        # Service response time
        self.collector.record_value("external_service_response_time_ms", response_time_ms, tags)
        
        # Service errors
        if not success:
            self.collector.increment_counter("external_service_errors_total", tags=tags)
    
    def record_product_matching(self, retailer: str, query: str, matches_found: int, best_score: float) -> None:
        """Record product matching metrics."""
        tags = {"retailer": retailer}
        
        # Matches found
        self.collector.record_value("product_matches_found", matches_found, tags)
        
        # Best match score
        self.collector.record_value("product_match_score", best_score, tags)
        
        # Query processing
        self.collector.increment_counter("product_queries_total", tags=tags)
    
    def update_cache_hit_rate(self) -> None:
        """Calculate and update cache hit rate gauge."""
        hits = self.collector.get_counter_value("cache_hits_total")
        misses = self.collector.get_counter_value("cache_misses_total")
        total = hits + misses
        
        if total > 0:
            hit_rate = (hits / total) * 100
            self.collector.set_gauge("cache_hit_rate_percent", hit_rate)
    
    def update_error_rate(self, time_window_seconds: float = 300) -> None:
        """Calculate and update error rate gauge."""
        requests_summary = self.collector.get_metric_summary("api_requests_total", time_window_seconds)
        errors_summary = self.collector.get_metric_summary("api_errors_total", time_window_seconds)
        
        if requests_summary and requests_summary.count > 0:
            error_count = errors_summary.count if errors_summary else 0
            error_rate = (error_count / requests_summary.count) * 100
            self.collector.set_gauge("error_rate_percent", error_rate)

# Global metrics collector
_metrics_collector = MetricsCollector()
_api_metrics = APIMetrics(_metrics_collector)

def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics_collector

def get_api_metrics() -> APIMetrics:
    """Get API metrics helper."""
    return _api_metrics

# Middleware and decorator functions for automatic metrics collection

class MetricsMiddleware:
    """Middleware to automatically collect API metrics."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.api_metrics = APIMetrics(collector)
    
    async def __call__(self, request, call_next):
        """Process request and collect metrics."""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            response_time_ms = (time.time() - start_time) * 1000
            
            # Record request metrics
            self.api_metrics.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=response_time_ms
            )
            
            return response
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            # Record error metrics
            self.api_metrics.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                response_time_ms=response_time_ms
            )
            
            raise
        
        finally:
            # Update calculated metrics
            self.api_metrics.update_cache_hit_rate()
            self.api_metrics.update_error_rate()

def get_metrics_middleware() -> MetricsMiddleware:
    """Get metrics middleware instance."""
    return MetricsMiddleware(_metrics_collector)

# Utility functions for common metric operations

def time_function(func_name: str):
    """Decorator to time function execution."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time_ms = (time.time() - start_time) * 1000
                _metrics_collector.record_value(f"function_time_ms_{func_name}", execution_time_ms)
                return result
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                _metrics_collector.record_value(f"function_time_ms_{func_name}", execution_time_ms, 
                                              {"error": True})
                _metrics_collector.increment_counter(f"function_errors_{func_name}")
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time_ms = (time.time() - start_time) * 1000
                _metrics_collector.record_value(f"function_time_ms_{func_name}", execution_time_ms)
                return result
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                _metrics_collector.record_value(f"function_time_ms_{func_name}", execution_time_ms, 
                                              {"error": True})
                _metrics_collector.increment_counter(f"function_errors_{func_name}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# Background task for periodic metrics calculation
async def metrics_calculation_task():
    """Background task to periodically calculate derived metrics."""
    api_metrics = get_api_metrics()
    
    while True:
        try:
            # Update calculated metrics every 30 seconds
            await asyncio.sleep(30)
            
            api_metrics.update_cache_hit_rate()
            api_metrics.update_error_rate()
            
        except Exception as e:
            logger.error(f"Error in metrics calculation task: {e}")
            await asyncio.sleep(60)  # Wait longer on error