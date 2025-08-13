"""
Health check utilities for monitoring external dependencies and system status.

This module provides comprehensive health checking for external services,
databases, network connectivity, and internal system components.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import httpx
from contextlib import asynccontextmanager

from ..settings import settings

logger = logging.getLogger(__name__)

class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    name: str
    status: HealthStatus
    response_time_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class SystemHealthSummary:
    """Overall system health summary."""
    status: HealthStatus
    checks: List[HealthCheckResult]
    response_time_ms: float
    timestamp: float = field(default_factory=time.time)
    
    @property
    def healthy_count(self) -> int:
        """Number of healthy checks."""
        return len([c for c in self.checks if c.status == HealthStatus.HEALTHY])
    
    @property
    def degraded_count(self) -> int:
        """Number of degraded checks."""
        return len([c for c in self.checks if c.status == HealthStatus.DEGRADED])
    
    @property
    def unhealthy_count(self) -> int:
        """Number of unhealthy checks."""
        return len([c for c in self.checks if c.status == HealthStatus.UNHEALTHY])

class HealthChecker:
    """
    Comprehensive health checker for external dependencies and system components.
    """
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.timeout = 10.0  # Default timeout in seconds
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function."""
        self.checks[name] = check_func
        logger.debug(f"Registered health check: {name}")
    
    async def run_check(self, name: str, check_func: Callable) -> HealthCheckResult:
        """Run a single health check with timeout and error handling."""
        start_time = time.time()
        
        try:
            # Run check with timeout
            result = await asyncio.wait_for(check_func(), timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheckResult):
                result.response_time_ms = response_time
                return result
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                return HealthCheckResult(
                    name=name,
                    status=status,
                    response_time_ms=response_time
                )
            else:
                # Assume healthy if check returns truthy value
                return HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    details={"result": str(result)}
                )
        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=f"Health check timed out after {self.timeout}s"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e),
                details={"exception_type": type(e).__name__}
            )
    
    async def check_all(self) -> SystemHealthSummary:
        """Run all registered health checks."""
        start_time = time.time()
        results = []
        
        if not self.checks:
            logger.warning("No health checks registered")
            return SystemHealthSummary(
                status=HealthStatus.UNKNOWN,
                checks=[],
                response_time_ms=0
            )
        
        # Run all checks concurrently
        check_tasks = [
            self.run_check(name, check_func)
            for name, check_func in self.checks.items()
        ]
        
        results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # Handle any exceptions from gather
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_name = list(self.checks.keys())[i]
                final_results.append(HealthCheckResult(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=0,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        # Determine overall status
        overall_status = self._determine_overall_status(final_results)
        
        total_response_time = (time.time() - start_time) * 1000
        
        summary = SystemHealthSummary(
            status=overall_status,
            checks=final_results,
            response_time_ms=total_response_time
        )
        
        # Log summary
        logger.info(
            f"Health check completed: {overall_status.value}",
            extra={
                "overall_status": overall_status.value,
                "healthy_count": summary.healthy_count,
                "degraded_count": summary.degraded_count,
                "unhealthy_count": summary.unhealthy_count,
                "total_checks": len(final_results),
                "response_time_ms": total_response_time
            }
        )
        
        return summary
    
    def _determine_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Determine overall system health status based on individual checks."""
        if not results:
            return HealthStatus.UNKNOWN
        
        unhealthy_count = len([r for r in results if r.status == HealthStatus.UNHEALTHY])
        degraded_count = len([r for r in results if r.status == HealthStatus.DEGRADED])
        
        # If more than 50% are unhealthy, system is unhealthy
        if unhealthy_count > len(results) * 0.5:
            return HealthStatus.UNHEALTHY
        
        # If any are unhealthy or degraded, system is degraded
        if unhealthy_count > 0 or degraded_count > 0:
            return HealthStatus.DEGRADED
        
        # All checks are healthy
        return HealthStatus.HEALTHY

# Specific health check implementations

async def check_woolworths_api() -> HealthCheckResult:
    """Check Woolworths API health."""
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try a simple search query
            response = await client.get(
                "https://www.woolworths.com.au/apis/ui/Search/products",
                params={"searchTerm": "milk", "pageSize": 1},
                headers={"User-Agent": settings.USER_AGENT}
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                products_found = len(data.get("products", []))
                
                return HealthCheckResult(
                    name="woolworths_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    details={
                        "status_code": response.status_code,
                        "products_found": products_found,
                        "endpoint": "search"
                    }
                )
            else:
                return HealthCheckResult(
                    name="woolworths_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    details={"status_code": response.status_code},
                    error=f"API returned status {response.status_code}"
                )
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name="woolworths_api",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"exception_type": type(e).__name__}
        )

async def check_coles_api() -> HealthCheckResult:
    """Check Coles API health."""
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try a simple search query
            response = await client.get(
                "https://www.coles.com.au/api/products/search",
                params={"q": "milk", "pageSize": 1},
                headers={"User-Agent": settings.USER_AGENT}
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                products_found = len(data.get("results", []))
                
                return HealthCheckResult(
                    name="coles_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    details={
                        "status_code": response.status_code,
                        "products_found": products_found,
                        "endpoint": "search"
                    }
                )
            else:
                return HealthCheckResult(
                    name="coles_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    details={"status_code": response.status_code},
                    error=f"API returned status {response.status_code}"
                )
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name="coles_api",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"exception_type": type(e).__name__}
        )

async def check_cache_system() -> HealthCheckResult:
    """Check cache system health."""
    start_time = time.time()
    
    try:
        from ..utils.cache import get_cache
        cache = get_cache()
        
        # Test cache operations
        test_key = "health_check_test"
        test_value = [{"test": "data", "timestamp": time.time()}]
        
        # Test put and get operations
        cache.put("test_retailer", test_key, "test_postcode", test_value)
        retrieved = cache.get("test_retailer", test_key, "test_postcode")
        
        response_time = (time.time() - start_time) * 1000
        
        if retrieved == test_value:
            # Get cache statistics
            stats = cache.get_stats()
            
            return HealthCheckResult(
                name="cache_system",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                details={
                    "cache_size": stats.get("size", 0),
                    "hit_rate": stats.get("hit_rate", 0),
                    "operations": "put_get_successful"
                }
            )
        else:
            return HealthCheckResult(
                name="cache_system",
                status=HealthStatus.DEGRADED,
                response_time_ms=response_time,
                error="Cache put/get operation failed",
                details={"expected": test_value, "retrieved": retrieved}
            )
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name="cache_system",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"exception_type": type(e).__name__}
        )

async def check_internet_connectivity() -> HealthCheckResult:
    """Check basic internet connectivity."""
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to reach a reliable external service
            response = await client.get("https://httpbin.org/status/200")
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return HealthCheckResult(
                    name="internet_connectivity",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    details={"endpoint": "httpbin.org"}
                )
            else:
                return HealthCheckResult(
                    name="internet_connectivity",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    details={"status_code": response.status_code}
                )
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name="internet_connectivity",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"exception_type": type(e).__name__}
        )

async def check_playwright_availability() -> HealthCheckResult:
    """Check if Playwright is available and functional."""
    start_time = time.time()
    
    try:
        if not settings.ENABLE_PLAYWRIGHT_FALLBACK:
            return HealthCheckResult(
                name="playwright_availability",
                status=HealthStatus.HEALTHY,
                response_time_ms=0,
                details={"status": "disabled", "reason": "not_enabled_in_settings"}
            )
        
        # Try to import Playwright
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="playwright_availability",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error="Playwright not installed",
                details={"import_error": "playwright module not found"}
            )
        
        # Try to create a playwright instance (don't launch browser for health check)
        playwright_instance = async_playwright()
        await playwright_instance.start()
        browser_types = ["chromium", "firefox", "webkit"]
        available_browsers = []
        
        for browser_type in browser_types:
            try:
                browser_launcher = getattr(playwright_instance, browser_type)
                if browser_launcher:
                    available_browsers.append(browser_type)
            except Exception:
                pass
        
        await playwright_instance.stop()
        
        response_time = (time.time() - start_time) * 1000
        
        if available_browsers:
            return HealthCheckResult(
                name="playwright_availability",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                details={
                    "available_browsers": available_browsers,
                    "primary_browser": "chromium" if "chromium" in available_browsers else available_browsers[0]
                }
            )
        else:
            return HealthCheckResult(
                name="playwright_availability",
                status=HealthStatus.DEGRADED,
                response_time_ms=response_time,
                error="No browsers available",
                details={"available_browsers": available_browsers}
            )
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return HealthCheckResult(
            name="playwright_availability",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"exception_type": type(e).__name__}
        )

# Global health checker instance
_health_checker = HealthChecker()

def get_health_checker() -> HealthChecker:
    """Get global health checker instance."""
    return _health_checker

def initialize_health_checks() -> None:
    """Initialize all health checks."""
    health_checker = get_health_checker()
    
    # Register all health checks
    health_checker.register_check("woolworths_api", check_woolworths_api)
    health_checker.register_check("coles_api", check_coles_api)
    health_checker.register_check("cache_system", check_cache_system)
    health_checker.register_check("internet_connectivity", check_internet_connectivity)
    health_checker.register_check("playwright_availability", check_playwright_availability)
    
    logger.info("Health checks initialized")

async def get_system_health() -> SystemHealthSummary:
    """Get complete system health status."""
    health_checker = get_health_checker()
    return await health_checker.check_all()