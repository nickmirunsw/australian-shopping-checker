"""
Graceful degradation utilities for maintaining service availability during failures.

This module provides strategies for handling partial failures, fallback mechanisms,
and service resilience patterns to ensure the best possible user experience
even when some components are unavailable.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass
from enum import Enum

from ..models import ProductResult

logger = logging.getLogger(__name__)

class ServiceStatus(str, Enum):
    """Service availability status."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

@dataclass
class ServiceResult:
    """Result from a service call with degradation information."""
    success: bool
    data: Any
    error: Optional[str] = None
    response_time_ms: float = 0.0
    fallback_used: bool = False
    degradation_reason: Optional[str] = None

@dataclass
class DegradationConfig:
    """Configuration for degradation behavior."""
    enable_fallbacks: bool = True
    enable_partial_results: bool = True
    enable_cached_fallback: bool = True
    max_wait_time_seconds: float = 10.0
    min_success_threshold: float = 0.5  # Minimum success rate to continue
    circuit_breaker_threshold: int = 5  # Failed requests before circuit breaker opens
    circuit_breaker_timeout: int = 60   # Seconds to wait before trying again

class CircuitBreaker:
    """Circuit breaker pattern for external service calls."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit breaker state."""
        current_time = time.time()
        
        if self.state == "open":
            if current_time - self.last_failure_time > self.timeout:
                self.state = "half-open"
                return True
            return False
        
        return True
    
    def record_success(self):
        """Record successful request."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

class GracefulDegradationManager:
    """
    Manager for implementing graceful degradation strategies.
    """
    
    def __init__(self, config: Optional[DegradationConfig] = None):
        self.config = config or DegradationConfig()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.service_status: Dict[str, ServiceStatus] = {}
        self.last_successful_results: Dict[str, Any] = {}  # Cache for fallback
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                self.config.circuit_breaker_threshold,
                self.config.circuit_breaker_timeout
            )
        return self.circuit_breakers[service_name]
    
    async def execute_with_degradation(self, 
                                      service_name: str,
                                      primary_func: Callable,
                                      fallback_func: Optional[Callable] = None,
                                      cached_fallback: bool = True,
                                      timeout_seconds: Optional[float] = None) -> ServiceResult:
        """
        Execute a service call with graceful degradation.
        
        Args:
            service_name: Name of the service for tracking
            primary_func: Primary function to execute
            fallback_func: Optional fallback function
            cached_fallback: Whether to use cached results as fallback
            timeout_seconds: Timeout for the operation
            
        Returns:
            ServiceResult with success/failure information
        """
        start_time = time.time()
        timeout = timeout_seconds or self.config.max_wait_time_seconds
        
        # Check circuit breaker
        circuit_breaker = self.get_circuit_breaker(service_name)
        if not circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker open for {service_name}, skipping primary call")
            return await self._try_fallback(service_name, fallback_func, cached_fallback, start_time)
        
        # Try primary function
        try:
            logger.debug(f"Executing primary function for {service_name}")
            
            if asyncio.iscoroutinefunction(primary_func):
                result = await asyncio.wait_for(primary_func(), timeout=timeout)
            else:
                result = primary_func()
            
            response_time = (time.time() - start_time) * 1000
            
            # Record success
            circuit_breaker.record_success()
            self.service_status[service_name] = ServiceStatus.AVAILABLE
            
            # Cache successful result for future fallback
            if self.config.enable_cached_fallback:
                self.last_successful_results[service_name] = {
                    'result': result,
                    'timestamp': time.time()
                }
            
            logger.debug(f"Primary function succeeded for {service_name} in {response_time:.1f}ms")
            
            return ServiceResult(
                success=True,
                data=result,
                response_time_ms=response_time
            )
        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            circuit_breaker.record_failure()
            
            logger.warning(f"Primary function timed out for {service_name} after {timeout}s")
            
            return ServiceResult(
                success=False,
                data=None,
                error=f"Timeout after {timeout}s",
                response_time_ms=response_time
            )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            circuit_breaker.record_failure()
            
            logger.warning(f"Primary function failed for {service_name}: {str(e)}")
            
            # Try fallback
            if self.config.enable_fallbacks:
                return await self._try_fallback(service_name, fallback_func, cached_fallback, start_time, str(e))
            
            return ServiceResult(
                success=False,
                data=None,
                error=str(e),
                response_time_ms=response_time
            )
    
    async def _try_fallback(self, 
                           service_name: str, 
                           fallback_func: Optional[Callable],
                           cached_fallback: bool,
                           start_time: float,
                           original_error: Optional[str] = None) -> ServiceResult:
        """Try fallback mechanisms in order of preference."""
        
        # Try provided fallback function first
        if fallback_func and self.config.enable_fallbacks:
            try:
                logger.info(f"Trying fallback function for {service_name}")
                
                if asyncio.iscoroutinefunction(fallback_func):
                    result = await fallback_func()
                else:
                    result = fallback_func()
                
                response_time = (time.time() - start_time) * 1000
                self.service_status[service_name] = ServiceStatus.DEGRADED
                
                logger.info(f"Fallback function succeeded for {service_name}")
                
                return ServiceResult(
                    success=True,
                    data=result,
                    response_time_ms=response_time,
                    fallback_used=True,
                    degradation_reason=f"Primary failed: {original_error or 'unknown'}"
                )
            
            except Exception as e:
                logger.warning(f"Fallback function failed for {service_name}: {str(e)}")
        
        # Try cached fallback
        if cached_fallback and self.config.enable_cached_fallback:
            cached_result = self.last_successful_results.get(service_name)
            if cached_result:
                # Check if cache is not too old (1 hour max)
                cache_age = time.time() - cached_result['timestamp']
                if cache_age < 3600:  # 1 hour
                    response_time = (time.time() - start_time) * 1000
                    self.service_status[service_name] = ServiceStatus.DEGRADED
                    
                    logger.info(f"Using cached fallback for {service_name} (age: {cache_age:.0f}s)")
                    
                    return ServiceResult(
                        success=True,
                        data=cached_result['result'],
                        response_time_ms=response_time,
                        fallback_used=True,
                        degradation_reason=f"Using cached data from {cache_age:.0f}s ago"
                    )
        
        # All fallbacks failed
        response_time = (time.time() - start_time) * 1000
        self.service_status[service_name] = ServiceStatus.UNAVAILABLE
        
        return ServiceResult(
            success=False,
            data=None,
            error=original_error or "All fallback mechanisms failed",
            response_time_ms=response_time
        )
    
    async def execute_multiple_with_degradation(self,
                                               service_calls: Dict[str, Callable],
                                               fallback_calls: Optional[Dict[str, Callable]] = None,
                                               min_success_threshold: Optional[float] = None) -> Dict[str, ServiceResult]:
        """
        Execute multiple service calls with graceful degradation.
        
        Args:
            service_calls: Dict of service_name -> function
            fallback_calls: Dict of service_name -> fallback_function  
            min_success_threshold: Minimum success rate required
            
        Returns:
            Dict of service_name -> ServiceResult
        """
        threshold = min_success_threshold or self.config.min_success_threshold
        fallback_calls = fallback_calls or {}
        
        # Execute all service calls concurrently
        tasks = {}
        for service_name, func in service_calls.items():
            fallback_func = fallback_calls.get(service_name)
            task = self.execute_with_degradation(
                service_name, func, fallback_func, cached_fallback=True
            )
            tasks[service_name] = asyncio.create_task(task)
        
        # Wait for all tasks to complete
        results = {}
        for service_name, task in tasks.items():
            try:
                results[service_name] = await task
            except Exception as e:
                results[service_name] = ServiceResult(
                    success=False,
                    data=None,
                    error=str(e)
                )
        
        # Check success threshold
        successful_services = len([r for r in results.values() if r.success])
        success_rate = successful_services / len(results) if results else 0
        
        if success_rate < threshold:
            logger.warning(
                f"Service success rate ({success_rate:.2%}) below threshold ({threshold:.2%})",
                extra={
                    "successful_services": successful_services,
                    "total_services": len(results),
                    "success_rate": success_rate,
                    "threshold": threshold
                }
            )
        
        return results
    
    def get_service_status_summary(self) -> Dict[str, Any]:
        """Get summary of service statuses."""
        status_counts = {}
        for status in ServiceStatus:
            status_counts[status.value] = len([
                s for s in self.service_status.values() if s == status
            ])
        
        circuit_breaker_status = {}
        for service_name, cb in self.circuit_breakers.items():
            circuit_breaker_status[service_name] = {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "last_failure": cb.last_failure_time
            }
        
        return {
            "service_status_counts": status_counts,
            "individual_services": dict(self.service_status),
            "circuit_breakers": circuit_breaker_status,
            "cached_results_count": len(self.last_successful_results)
        }

# Global degradation manager
_degradation_manager = GracefulDegradationManager()

def get_degradation_manager() -> GracefulDegradationManager:
    """Get global degradation manager."""
    return _degradation_manager

# Utility functions for common degradation patterns

async def execute_retailer_search_with_degradation(retailer_name: str,
                                                  search_func: Callable,
                                                  fallback_func: Optional[Callable] = None) -> List[ProductResult]:
    """
    Execute retailer search with graceful degradation.
    
    Args:
        retailer_name: Name of the retailer
        search_func: Primary search function
        fallback_func: Optional fallback function
        
    Returns:
        List of products (may be empty if all methods fail)
    """
    manager = get_degradation_manager()
    
    result = await manager.execute_with_degradation(
        service_name=f"{retailer_name}_search",
        primary_func=search_func,
        fallback_func=fallback_func,
        cached_fallback=True,
        timeout_seconds=15.0
    )
    
    if result.success:
        products = result.data or []
        
        # Log degradation information
        if result.fallback_used:
            logger.info(
                f"Retailer search degraded for {retailer_name}",
                extra={
                    "retailer": retailer_name,
                    "products_found": len(products),
                    "degradation_reason": result.degradation_reason,
                    "fallback_used": True
                }
            )
        
        return products
    else:
        logger.error(
            f"Retailer search failed for {retailer_name}: {result.error}",
            extra={
                "retailer": retailer_name,
                "error": result.error,
                "response_time_ms": result.response_time_ms
            }
        )
        return []

async def execute_multi_retailer_search_with_degradation(search_functions: Dict[str, Callable],
                                                        fallback_functions: Optional[Dict[str, Callable]] = None) -> Dict[str, List[ProductResult]]:
    """
    Execute searches across multiple retailers with degradation.
    
    Args:
        search_functions: Dict of retailer_name -> search_function
        fallback_functions: Dict of retailer_name -> fallback_function
        
    Returns:
        Dict of retailer_name -> list of products
    """
    manager = get_degradation_manager()
    
    # Execute all searches
    service_results = await manager.execute_multiple_with_degradation(
        service_calls=search_functions,
        fallback_calls=fallback_functions,
        min_success_threshold=0.3  # At least 30% of retailers should succeed
    )
    
    # Convert results to product lists
    retailer_products = {}
    successful_retailers = []
    failed_retailers = []
    
    for retailer_name, result in service_results.items():
        if result.success:
            products = result.data or []
            # Ensure products is not a coroutine
            if hasattr(products, '__await__'):
                products = await products
            retailer_products[retailer_name] = products
            successful_retailers.append(retailer_name)
            
            if result.fallback_used:
                logger.info(f"Used fallback for {retailer_name}: {result.degradation_reason}")
        else:
            retailer_products[retailer_name] = []
            failed_retailers.append(retailer_name)
    
    # Log overall summary
    total_products = sum(len(products) for products in retailer_products.values())
    
    logger.info(
        "Multi-retailer search completed",
        extra={
            "successful_retailers": successful_retailers,
            "failed_retailers": failed_retailers,
            "total_products": total_products,
            "success_rate": len(successful_retailers) / len(search_functions) if search_functions else 0
        }
    )
    
    return retailer_products

def create_cached_fallback(cache_key: str, data: Any) -> None:
    """Create a cached fallback entry for future use."""
    manager = get_degradation_manager()
    manager.last_successful_results[cache_key] = {
        'result': data,
        'timestamp': time.time()
    }

def get_degradation_status() -> Dict[str, Any]:
    """Get current degradation status for monitoring."""
    manager = get_degradation_manager()
    return manager.get_service_status_summary()