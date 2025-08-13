"""
Comprehensive error handling utilities with structured error responses.

This module provides standardized error handling, logging, and response formatting
to ensure consistent error reporting across the application.
"""

import logging
import traceback
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import time

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ErrorCategory(str, Enum):
    """Categories of errors for better classification."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication" 
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    NETWORK = "network"
    BUSINESS_LOGIC = "business_logic"
    INTERNAL = "internal"
    NOT_FOUND = "not_found"

class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ErrorDetails:
    """Detailed error information for logging and debugging."""
    code: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str
    http_status: int
    retryable: bool = False
    retry_after: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    """Structured error response model."""
    error: str = Field(..., description="Error type/code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="ISO timestamp when error occurred")
    request_id: Optional[str] = Field(None, description="Request identifier for tracking")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retrying")

class ErrorHandler:
    """
    Centralized error handler with structured logging and responses.
    """
    
    def __init__(self):
        # Predefined error configurations
        self.error_configs = {
            "VALIDATION_FAILED": ErrorDetails(
                code="VALIDATION_FAILED",
                message="Input validation failed",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.LOW,
                user_message="Please check your input and try again",
                http_status=status.HTTP_400_BAD_REQUEST,
                retryable=False
            ),
            "RATE_LIMIT_EXCEEDED": ErrorDetails(
                code="RATE_LIMIT_EXCEEDED",
                message="Rate limit exceeded",
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.MEDIUM,
                user_message="Too many requests. Please try again later",
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
                retryable=True,
                retry_after=60
            ),
            "EXTERNAL_SERVICE_UNAVAILABLE": ErrorDetails(
                code="EXTERNAL_SERVICE_UNAVAILABLE",
                message="External service is currently unavailable",
                category=ErrorCategory.EXTERNAL_SERVICE,
                severity=ErrorSeverity.HIGH,
                user_message="Service temporarily unavailable. Please try again later",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
                retry_after=300
            ),
            "NETWORK_TIMEOUT": ErrorDetails(
                code="NETWORK_TIMEOUT",
                message="Network request timed out",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.MEDIUM,
                user_message="Request timed out. Please try again",
                http_status=status.HTTP_504_GATEWAY_TIMEOUT,
                retryable=True,
                retry_after=30
            ),
            "PRODUCT_NOT_FOUND": ErrorDetails(
                code="PRODUCT_NOT_FOUND",
                message="No matching products found",
                category=ErrorCategory.NOT_FOUND,
                severity=ErrorSeverity.LOW,
                user_message="No products found matching your search",
                http_status=status.HTTP_404_NOT_FOUND,
                retryable=False
            ),
            "INTERNAL_ERROR": ErrorDetails(
                code="INTERNAL_ERROR",
                message="An internal error occurred",
                category=ErrorCategory.INTERNAL,
                severity=ErrorSeverity.CRITICAL,
                user_message="An unexpected error occurred. Please try again later",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                retryable=True,
                retry_after=60
            ),
            "DATABASE_CONNECTION": ErrorDetails(
                code="DATABASE_CONNECTION",
                message="Database connection failed",
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.HIGH,
                user_message="Service temporarily unavailable. Please try again later",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
                retry_after=120
            )
        }
    
    def log_error(self, 
                  error_code: str, 
                  exception: Optional[Exception] = None,
                  request: Optional[Request] = None,
                  context: Optional[Dict[str, Any]] = None,
                  user_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Log error with structured information.
        
        Args:
            error_code: Predefined error code
            exception: Original exception if any
            request: FastAPI request object
            context: Additional context information
            user_data: User-related data (will be sanitized)
            
        Returns:
            Unique request ID for tracking
        """
        request_id = f"{int(time.time() * 1000)}-{id(request) if request else 0}"
        
        error_config = self.error_configs.get(error_code, self.error_configs["INTERNAL_ERROR"])
        
        # Build log context
        log_context = {
            "request_id": request_id,
            "error_code": error_code,
            "error_category": error_config.category.value,
            "error_severity": error_config.severity.value,
            "retryable": error_config.retryable,
            "timestamp": time.time()
        }
        
        # Add request information
        if request:
            log_context.update({
                "method": request.method,
                "path": str(request.url.path),
                "query_params": dict(request.query_params),
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent")
            })
        
        # Add context information
        if context:
            # Sanitize context to remove sensitive data
            sanitized_context = self._sanitize_context(context)
            log_context["context"] = sanitized_context
        
        # Add user data (sanitized)
        if user_data:
            sanitized_user_data = self._sanitize_user_data(user_data)
            log_context["user_data"] = sanitized_user_data
        
        # Log based on severity
        if error_config.severity == ErrorSeverity.CRITICAL:
            logger.critical(error_config.message, extra=log_context, exc_info=exception)
        elif error_config.severity == ErrorSeverity.HIGH:
            logger.error(error_config.message, extra=log_context, exc_info=exception)
        elif error_config.severity == ErrorSeverity.MEDIUM:
            logger.warning(error_config.message, extra=log_context, exc_info=exception)
        else:
            logger.info(error_config.message, extra=log_context, exc_info=exception)
        
        return request_id
    
    def create_error_response(self, 
                             error_code: str,
                             request_id: str,
                             details: Optional[Dict[str, Any]] = None) -> ErrorResponse:
        """
        Create structured error response.
        
        Args:
            error_code: Predefined error code
            request_id: Request identifier
            details: Additional error details for user
            
        Returns:
            Structured error response
        """
        error_config = self.error_configs.get(error_code, self.error_configs["INTERNAL_ERROR"])
        
        response = ErrorResponse(
            error=error_code,
            message=error_config.user_message,
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            request_id=request_id
        )
        
        if error_config.retry_after:
            response.retry_after = error_config.retry_after
        
        if details:
            response.details = details
        
        return response
    
    def handle_exception(self, 
                        error_code: str,
                        exception: Optional[Exception] = None,
                        request: Optional[Request] = None,
                        context: Optional[Dict[str, Any]] = None,
                        details: Optional[Dict[str, Any]] = None) -> JSONResponse:
        """
        Handle exception with logging and structured response.
        
        Args:
            error_code: Predefined error code
            exception: Original exception
            request: FastAPI request object
            context: Additional context for logging
            details: Additional details for user response
            
        Returns:
            JSON error response
        """
        # Log the error
        request_id = self.log_error(
            error_code=error_code,
            exception=exception,
            request=request,
            context=context
        )
        
        # Create structured response
        error_response = self.create_error_response(
            error_code=error_code,
            request_id=request_id,
            details=details
        )
        
        # Get HTTP status code
        error_config = self.error_configs.get(error_code, self.error_configs["INTERNAL_ERROR"])
        
        # Create JSON response
        response = JSONResponse(
            status_code=error_config.http_status,
            content=error_response.dict()
        )
        
        # Add retry headers if applicable
        if error_config.retry_after:
            response.headers["Retry-After"] = str(error_config.retry_after)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check various headers for real IP (proxy setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize context data to remove sensitive information."""
        sensitive_keys = {
            'password', 'token', 'secret', 'key', 'auth', 'credential',
            'api_key', 'access_token', 'refresh_token', 'session_id'
        }
        
        sanitized = {}
        for key, value in context.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, dict)):
                # Truncate large objects
                str_value = str(value)
                if len(str_value) > 500:
                    sanitized[key] = f"{str_value[:500]}... [TRUNCATED]"
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = str(type(value))
        
        return sanitized
    
    def _sanitize_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize user data for logging."""
        # Only include safe fields
        safe_fields = {
            'user_id', 'username', 'email_hash', 'role', 'session_duration',
            'last_login', 'preferences', 'settings', 'location', 'timezone'
        }
        
        sanitized = {}
        for key, value in user_data.items():
            if key in safe_fields:
                sanitized[key] = value
            elif 'email' in key.lower() and isinstance(value, str):
                # Hash email for privacy
                import hashlib
                sanitized[f"{key}_hash"] = hashlib.md5(value.encode()).hexdigest()[:8]
        
        return sanitized
    
    def add_error_config(self, error_code: str, error_details: ErrorDetails) -> None:
        """Add custom error configuration."""
        self.error_configs[error_code] = error_details
    
    def get_error_info(self, error_code: str) -> Optional[ErrorDetails]:
        """Get error configuration by code."""
        return self.error_configs.get(error_code)


# Global error handler instance
_error_handler = ErrorHandler()

def get_error_handler() -> ErrorHandler:
    """Get global error handler instance."""
    return _error_handler

# Convenience functions for common error scenarios

async def handle_validation_error(request: Request, 
                                  validation_errors: List[str],
                                  field_name: Optional[str] = None) -> JSONResponse:
    """Handle validation errors with structured response."""
    error_handler = get_error_handler()
    
    details = {
        "validation_errors": validation_errors
    }
    if field_name:
        details["field"] = field_name
    
    return error_handler.handle_exception(
        error_code="VALIDATION_FAILED",
        request=request,
        details=details
    )

async def handle_external_service_error(request: Request,
                                       service_name: str,
                                       original_error: Exception) -> JSONResponse:
    """Handle external service errors."""
    error_handler = get_error_handler()
    
    context = {
        "service_name": service_name,
        "error_type": type(original_error).__name__
    }
    
    details = {
        "service": service_name,
        "error_type": "service_unavailable"
    }
    
    return error_handler.handle_exception(
        error_code="EXTERNAL_SERVICE_UNAVAILABLE",
        exception=original_error,
        request=request,
        context=context,
        details=details
    )

async def handle_network_timeout(request: Request,
                                operation: str,
                                timeout_seconds: float) -> JSONResponse:
    """Handle network timeout errors."""
    error_handler = get_error_handler()
    
    context = {
        "operation": operation,
        "timeout_seconds": timeout_seconds
    }
    
    details = {
        "operation": operation,
        "timeout": f"{timeout_seconds}s"
    }
    
    return error_handler.handle_exception(
        error_code="NETWORK_TIMEOUT",
        request=request,
        context=context,
        details=details
    )

async def handle_internal_error(request: Request,
                               exception: Exception,
                               operation: Optional[str] = None) -> JSONResponse:
    """Handle internal/unexpected errors."""
    error_handler = get_error_handler()
    
    context = {
        "exception_type": type(exception).__name__,
        "traceback": traceback.format_exc()
    }
    if operation:
        context["operation"] = operation
    
    return error_handler.handle_exception(
        error_code="INTERNAL_ERROR",
        exception=exception,
        request=request,
        context=context
    )