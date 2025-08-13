"""
Rate limiting utilities to prevent API abuse.

This module provides rate limiting functionality using sliding window
and token bucket algorithms to control request frequency.
"""

import time
import logging
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from threading import Lock
from dataclasses import dataclass, field
import asyncio

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests: int  # Number of requests allowed
    window: int    # Time window in seconds
    burst: int = None  # Optional burst allowance

@dataclass
class ClientInfo:
    """Information about a client's request history."""
    requests: deque = field(default_factory=deque)  # Timestamps of requests
    tokens: float = 0.0  # Available tokens for token bucket
    last_refill: float = field(default_factory=time.time)  # Last token refill time
    blocked_until: float = 0.0  # When client is blocked until

class RateLimiter:
    """
    Rate limiter using sliding window and token bucket algorithms.
    """
    
    def __init__(self):
        self.clients: Dict[str, ClientInfo] = defaultdict(ClientInfo)
        self.lock = Lock()
        
        # Default rate limits (can be overridden per endpoint)
        self.default_limits = {
            'global': RateLimit(requests=100, window=60, burst=10),  # 100 req/min with 10 burst
            'check': RateLimit(requests=20, window=60, burst=5),     # 20 req/min with 5 burst
            'heavy': RateLimit(requests=5, window=60, burst=2),      # 5 req/min with 2 burst
            'admin': RateLimit(requests=200, window=60, burst=20),   # 200 req/min for admin endpoints (more lenient)
        }
    
    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Try to get real IP from headers (for proxy setups)
        real_ip = request.headers.get('X-Real-IP')
        forwarded_for = request.headers.get('X-Forwarded-For')
        
        if real_ip:
            client_ip = real_ip
        elif forwarded_for:
            # Take the first IP from X-Forwarded-For
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else 'unknown'
        
        # Include user agent for more granular identification
        user_agent = request.headers.get('User-Agent', 'unknown')
        
        # Create a client ID (you might want to hash this for privacy)
        client_id = f"{client_ip}:{hash(user_agent) % 10000}"
        
        return client_id
    
    def _cleanup_old_requests(self, client_info: ClientInfo, window: int) -> None:
        """Remove requests older than the window."""
        current_time = time.time()
        cutoff_time = current_time - window
        
        while client_info.requests and client_info.requests[0] <= cutoff_time:
            client_info.requests.popleft()
    
    def _refill_tokens(self, client_info: ClientInfo, rate_limit: RateLimit) -> None:
        """Refill tokens using token bucket algorithm."""
        current_time = time.time()
        time_passed = current_time - client_info.last_refill
        
        if time_passed <= 0:
            return
        
        # Calculate tokens to add (rate per second)
        tokens_per_second = rate_limit.requests / rate_limit.window
        tokens_to_add = time_passed * tokens_per_second
        
        # Add tokens but don't exceed bucket capacity
        max_tokens = rate_limit.burst or rate_limit.requests
        client_info.tokens = min(max_tokens, client_info.tokens + tokens_to_add)
        client_info.last_refill = current_time
    
    def _is_rate_limited(self, client_info: ClientInfo, rate_limit: RateLimit) -> Tuple[bool, Optional[float]]:
        """
        Check if client is rate limited.
        
        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        current_time = time.time()
        
        # Check if client is currently blocked
        if client_info.blocked_until > current_time:
            retry_after = client_info.blocked_until - current_time
            return True, retry_after
        
        # Clean up old requests for sliding window
        self._cleanup_old_requests(client_info, rate_limit.window)
        
        # Refill tokens for token bucket
        self._refill_tokens(client_info, rate_limit)
        
        # Check sliding window limit
        if len(client_info.requests) >= rate_limit.requests:
            # Calculate when the oldest request will expire
            oldest_request = client_info.requests[0]
            retry_after = rate_limit.window - (current_time - oldest_request)
            return True, max(0, retry_after)
        
        # Check token bucket (for burst protection)
        if client_info.tokens < 1.0:
            # Calculate when next token will be available
            tokens_per_second = rate_limit.requests / rate_limit.window
            retry_after = (1.0 - client_info.tokens) / tokens_per_second
            return True, retry_after
        
        return False, None
    
    def check_rate_limit(self, request: Request, limit_type: str = 'global') -> Tuple[bool, Dict[str, str]]:
        """
        Check if request should be rate limited.
        
        Args:
            request: FastAPI request object
            limit_type: Type of rate limit to apply
            
        Returns:
            Tuple of (is_allowed, headers)
        """
        client_id = self._get_client_id(request)
        rate_limit = self.default_limits.get(limit_type, self.default_limits['global'])
        
        with self.lock:
            client_info = self.clients[client_id]
            
            is_limited, retry_after = self._is_rate_limited(client_info, rate_limit)
            
            headers = {
                'X-RateLimit-Limit': str(rate_limit.requests),
                'X-RateLimit-Window': str(rate_limit.window),
                'X-RateLimit-Remaining': str(max(0, rate_limit.requests - len(client_info.requests))),
            }
            
            if is_limited:
                if retry_after:
                    headers['Retry-After'] = str(int(retry_after) + 1)
                
                # Log rate limit violation
                logger.warning(
                    f"Rate limit exceeded for client {client_id}",
                    extra={
                        'client_id': client_id,
                        'limit_type': limit_type,
                        'requests_in_window': len(client_info.requests),
                        'limit': rate_limit.requests,
                        'window': rate_limit.window,
                        'retry_after': retry_after,
                        'path': request.url.path,
                        'method': request.method
                    }
                )
                
                return False, headers
            
            # Allow request - record it and consume token
            current_time = time.time()
            client_info.requests.append(current_time)
            client_info.tokens = max(0, client_info.tokens - 1.0)
            
            # Log successful request
            logger.debug(
                f"Rate limit check passed for client {client_id}",
                extra={
                    'client_id': client_id,
                    'limit_type': limit_type,
                    'requests_in_window': len(client_info.requests),
                    'tokens_remaining': client_info.tokens,
                    'path': request.url.path,
                    'method': request.method
                }
            )
            
            return True, headers
    
    def block_client(self, client_id: str, duration: int = 300) -> None:
        """
        Block a client for a specified duration.
        
        Args:
            client_id: Client identifier to block
            duration: Block duration in seconds (default 5 minutes)
        """
        with self.lock:
            client_info = self.clients[client_id]
            client_info.blocked_until = time.time() + duration
            
            logger.warning(
                f"Client {client_id} blocked for {duration} seconds",
                extra={
                    'client_id': client_id,
                    'block_duration': duration,
                    'blocked_until': client_info.blocked_until
                }
            )
    
    def unblock_client(self, client_id: str) -> None:
        """Unblock a client."""
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id].blocked_until = 0.0
                logger.info(f"Client {client_id} unblocked")
    
    def get_client_stats(self, client_id: str) -> Dict[str, any]:
        """Get statistics for a specific client."""
        with self.lock:
            if client_id not in self.clients:
                return {'exists': False}
            
            client_info = self.clients[client_id]
            current_time = time.time()
            
            return {
                'exists': True,
                'requests_in_window': len(client_info.requests),
                'tokens': client_info.tokens,
                'blocked_until': client_info.blocked_until,
                'is_blocked': client_info.blocked_until > current_time,
                'last_request': client_info.requests[-1] if client_info.requests else None
            }
    
    def cleanup_expired_clients(self, max_age: int = 3600) -> int:
        """
        Clean up clients that haven't made requests recently.
        
        Args:
            max_age: Maximum age in seconds to keep client data
            
        Returns:
            Number of clients cleaned up
        """
        current_time = time.time()
        cutoff_time = current_time - max_age
        
        with self.lock:
            clients_to_remove = []
            
            for client_id, client_info in self.clients.items():
                # Remove if no recent requests and not blocked
                if (not client_info.requests or 
                    client_info.requests[-1] < cutoff_time) and \
                   client_info.blocked_until <= current_time:
                    clients_to_remove.append(client_id)
            
            for client_id in clients_to_remove:
                del self.clients[client_id]
            
            logger.info(f"Cleaned up {len(clients_to_remove)} expired clients")
            return len(clients_to_remove)


# Global rate limiter instance
_rate_limiter = RateLimiter()

def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return _rate_limiter

async def rate_limit_middleware(request: Request, call_next, limit_type: str = 'global'):
    """
    Rate limiting middleware for FastAPI.
    
    Args:
        request: FastAPI request
        call_next: Next middleware/endpoint
        limit_type: Type of rate limit to apply
        
    Returns:
        Response or rate limit error
    """
    rate_limiter = get_rate_limiter()
    
    is_allowed, headers = rate_limiter.check_rate_limit(request, limit_type)
    
    if not is_allowed:
        # Return rate limit exceeded response
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "type": "rate_limit_exceeded"
            },
            headers=headers
        )
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers to response
    for header_name, header_value in headers.items():
        response.headers[header_name] = header_value
    
    return response

# Background task to clean up expired clients
async def cleanup_task():
    """Background task to periodically clean up expired client data."""
    rate_limiter = get_rate_limiter()
    
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            rate_limiter.cleanup_expired_clients()
        except Exception as e:
            logger.error(f"Error in rate limiter cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying