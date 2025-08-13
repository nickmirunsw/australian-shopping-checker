import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import httpx

from ..models import ProductResult

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """Base class for retailer adapters."""
    
    @abstractmethod
    async def search(self, query: str, postcode: str) -> List[ProductResult]:
        """
        Search for products at this retailer.
        
        Args:
            query: Search term (e.g., "milk 2L", "weet-bix")
            postcode: Australian postcode for location-based search
            
        Returns:
            List of ProductResult objects matching the search
        """
        pass
    
    async def _retry_request_with_backoff(
        self, 
        client: httpx.AsyncClient, 
        url: str, 
        params: Dict[str, Any], 
        query: str, 
        postcode: str, 
        max_retries: int = 3,
        timeout: float = 30.0,
        backoff_factor: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request with exponential backoff retry and comprehensive logging.
        
        This method implements a robust retry strategy with:
        - Exponential backoff (1s, 2s, 4s with configurable factor)
        - Specific retry logic for transient errors (429, 5xx)
        - Comprehensive structured logging
        - Proper timeout handling
        - Exception handling for network issues
        
        Args:
            client: HTTPX async client instance
            url: Request URL
            params: Query parameters
            query: Search query (for logging)
            postcode: Postcode (for logging)
            max_retries: Maximum number of retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 30.0)
            backoff_factor: Multiplier for backoff delay (default: 1.0)
            
        Returns:
            JSON response dict if successful, None if all retries failed
        """
        retailer_name = getattr(self, 'retailer_name', 'unknown')
        last_status_code = None
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                request_start = time.time()
                
                # Make the HTTP request
                response = await client.get(
                    url, 
                    params=params, 
                    headers=getattr(self, 'headers', {}), 
                    timeout=timeout
                )
                
                latency = time.time() - request_start
                last_status_code = response.status_code
                
                # Log structured request information
                log_extra = {
                    "query": query,
                    "postcode": postcode,
                    "retailer": retailer_name,
                    "status_code": response.status_code,
                    "latency": round(latency, 3),
                    "attempt": attempt + 1,
                    "url": url
                }
                
                if response.status_code == 200:
                    logger.info("HTTP request successful", extra=log_extra)
                    try:
                        return response.json()
                    except Exception as json_error:
                        logger.error(
                            f"Failed to parse JSON response: {json_error}",
                            extra={**log_extra, "parse_error": str(json_error)}
                        )
                        return None
                
                # Handle retryable status codes
                elif response.status_code in [429, 500, 502, 503, 504]:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * backoff_factor
                        logger.warning(
                            f"Request failed with retryable status {response.status_code}, retrying in {wait_time}s",
                            extra={
                                **log_extra,
                                "retry_delay": wait_time,
                                "retryable": True
                            }
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            f"Max retries reached for status {response.status_code}",
                            extra={**log_extra, "max_retries_reached": True}
                        )
                        return None
                
                # Handle non-retryable status codes
                else:
                    logger.error(
                        f"Request failed with non-retryable status {response.status_code}",
                        extra={
                            **log_extra, 
                            "response_text": response.text[:200],  # First 200 chars for debugging
                            "retryable": False
                        }
                    )
                    return None
                    
            except httpx.TimeoutException as e:
                latency = time.time() - request_start if 'request_start' in locals() else None
                last_exception = e
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * backoff_factor
                    logger.warning(
                        f"Request timed out after {timeout}s, retrying in {wait_time}s",
                        extra={
                            "query": query,
                            "postcode": postcode,
                            "retailer": retailer_name,
                            "latency": latency,
                            "attempt": attempt + 1,
                            "retry_delay": wait_time,
                            "timeout": timeout,
                            "error_type": "timeout"
                        }
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Request timed out after max retries ({max_retries} attempts)",
                        extra={
                            "query": query,
                            "postcode": postcode,
                            "retailer": retailer_name,
                            "latency": latency,
                            "max_retries": max_retries,
                            "timeout": timeout,
                            "error_type": "timeout"
                        }
                    )
                    return None
            
            except (httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * backoff_factor
                    logger.warning(
                        f"Network error occurred, retrying in {wait_time}s: {e}",
                        extra={
                            "query": query,
                            "postcode": postcode,
                            "retailer": retailer_name,
                            "attempt": attempt + 1,
                            "retry_delay": wait_time,
                            "error_type": "network",
                            "error_details": str(e)
                        }
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Network error after max retries: {e}",
                        extra={
                            "query": query,
                            "postcode": postcode,
                            "retailer": retailer_name,
                            "max_retries": max_retries,
                            "error_type": "network",
                            "error_details": str(e)
                        }
                    )
                    return None
            
            except Exception as e:
                last_exception = e
                logger.error(
                    f"Unexpected error during HTTP request: {e}",
                    extra={
                        "query": query,
                        "postcode": postcode,
                        "retailer": retailer_name,
                        "attempt": attempt + 1,
                        "error_type": "unexpected",
                        "error_details": str(e)
                    }
                )
                return None
        
        # If we get here, all retries failed
        logger.error(
            "All retry attempts failed",
            extra={
                "query": query,
                "postcode": postcode,
                "retailer": retailer_name,
                "max_retries": max_retries,
                "last_status_code": last_status_code,
                "last_exception": str(last_exception) if last_exception else None
            }
        )
        return None