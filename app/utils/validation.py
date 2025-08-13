"""
Input validation utilities for the Australian Supermarket Sale Checker.

This module provides validation functions for user inputs including
queries, postcodes, and other parameters to ensure data integrity
and security.
"""

import re
import logging
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, validator
from ..models import CheckItemsRequest

logger = logging.getLogger(__name__)

# Australian postcode regex pattern (4 digits, 0800-9999)
POSTCODE_PATTERN = re.compile(r'^\d{4}$')

# Valid Australian postcode ranges
VALID_POSTCODE_RANGES = [
    (1000, 1999),  # NSW (including ACT 2600-2999)
    (2000, 2999),  # NSW 
    (3000, 3999),  # VIC
    (4000, 4999),  # QLD
    (5000, 5999),  # SA
    (6000, 6999),  # WA
    (7000, 7999),  # TAS
    (800, 999),    # NT
]

class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)

class ValidationResult(BaseModel):
    """Result of validation operation."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    sanitized_value: Optional[str] = None

def validate_postcode(postcode: str) -> ValidationResult:
    """
    Validate Australian postcode.
    
    Args:
        postcode: The postcode string to validate
        
    Returns:
        ValidationResult with validation status and sanitized postcode
    """
    if not postcode:
        return ValidationResult(
            is_valid=False,
            errors=["Postcode is required"]
        )
    
    # Remove whitespace and convert to string
    clean_postcode = str(postcode).strip()
    
    # Check basic format
    if not POSTCODE_PATTERN.match(clean_postcode):
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid postcode format. Must be 4 digits (1000-9999), got: {postcode}"]
        )
    
    # Convert to int for range checking
    try:
        postcode_int = int(clean_postcode)
    except ValueError:
        return ValidationResult(
            is_valid=False,
            errors=[f"Postcode must be numeric, got: {postcode}"]
        )
    
    # Check if postcode is in valid Australian ranges
    is_valid_range = any(
        start <= postcode_int <= end 
        for start, end in VALID_POSTCODE_RANGES
    )
    
    if not is_valid_range:
        return ValidationResult(
            is_valid=False,
            errors=[f"Postcode {postcode} is not in a valid Australian range"]
        )
    
    return ValidationResult(
        is_valid=True,
        sanitized_value=clean_postcode
    )

def validate_query(query: str) -> ValidationResult:
    """
    Validate search query string.
    
    Args:
        query: The search query to validate
        
    Returns:
        ValidationResult with validation status and sanitized query
    """
    if not query:
        return ValidationResult(
            is_valid=False,
            errors=["Search query is required"]
        )
    
    # Convert to string and strip whitespace
    clean_query = str(query).strip()
    
    # Check minimum length
    if len(clean_query) < 2:
        return ValidationResult(
            is_valid=False,
            errors=["Search query must be at least 2 characters long"]
        )
    
    # Check maximum length
    if len(clean_query) > 200:
        return ValidationResult(
            is_valid=False,
            errors=["Search query must be less than 200 characters"]
        )
    
    # Check for potentially malicious patterns
    suspicious_patterns = [
        r'<script[^>]*>',  # Script tags
        r'javascript:',    # JavaScript URLs
        r'on\w+\s*=',     # Event handlers
        r'<%.*?%>',       # Server-side includes
        r'\$\{.*?\}',     # Template expressions
    ]
    
    warnings = []
    for pattern in suspicious_patterns:
        if re.search(pattern, clean_query, re.IGNORECASE):
            warnings.append(f"Query contains potentially suspicious content: {pattern}")
    
    # Basic sanitization - remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', clean_query)
    
    # Check for SQL injection patterns (basic)
    sql_patterns = [
        r'\b(union|select|insert|update|delete|drop|alter)\b',
        r'[\'";]',  # Quote characters
        r'--',      # SQL comments
        r'/\*.*?\*/',  # Block comments
    ]
    
    for pattern in sql_patterns:
        if re.search(pattern, clean_query, re.IGNORECASE):
            warnings.append("Query contains characters that might be used in SQL injection")
            break
    
    return ValidationResult(
        is_valid=True,
        warnings=warnings,
        sanitized_value=sanitized
    )

def validate_items_string(items: str) -> ValidationResult:
    """
    Validate comma-separated items string.
    
    Args:
        items: Comma-separated string of items to validate
        
    Returns:
        ValidationResult with validation status and sanitized items
    """
    if not items:
        return ValidationResult(
            is_valid=False,
            errors=["Items string is required"]
        )
    
    clean_items = str(items).strip()
    
    # Split and validate each item
    item_list = [item.strip() for item in clean_items.split(',')]
    item_list = [item for item in item_list if item]  # Remove empty items
    
    if not item_list:
        return ValidationResult(
            is_valid=False,
            errors=["At least one item is required"]
        )
    
    if len(item_list) > 20:
        return ValidationResult(
            is_valid=False,
            errors=["Too many items. Maximum 20 items allowed per request"]
        )
    
    # Validate each individual item
    errors = []
    warnings = []
    sanitized_items = []
    
    for i, item in enumerate(item_list):
        item_result = validate_query(item)
        
        if not item_result.is_valid:
            errors.extend([f"Item {i+1}: {error}" for error in item_result.errors])
        else:
            sanitized_items.append(item_result.sanitized_value)
            if item_result.warnings:
                warnings.extend([f"Item {i+1}: {warning}" for warning in item_result.warnings])
    
    if errors:
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings
        )
    
    return ValidationResult(
        is_valid=True,
        warnings=warnings,
        sanitized_value=', '.join(sanitized_items)
    )

def validate_check_request(request: CheckItemsRequest) -> ValidationResult:
    """
    Validate a complete check request.
    
    Args:
        request: The CheckRequest to validate
        
    Returns:
        ValidationResult with overall validation status
    """
    errors = []
    warnings = []
    
    # Validate items
    items_result = validate_items_string(request.items)
    if not items_result.is_valid:
        errors.extend(items_result.errors)
    else:
        warnings.extend(items_result.warnings)
    
    # Validate postcode
    postcode_result = validate_postcode(request.postcode)
    if not postcode_result.is_valid:
        errors.extend(postcode_result.errors)
    else:
        warnings.extend(postcode_result.warnings)
    
    # Log validation results
    if errors:
        logger.warning(
            "Request validation failed",
            extra={
                "items": request.items,
                "postcode": request.postcode,
                "errors": errors,
                "warnings": warnings
            }
        )
    elif warnings:
        logger.info(
            "Request validation passed with warnings",
            extra={
                "items": request.items,
                "postcode": request.postcode,
                "warnings": warnings
            }
        )
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input by removing/escaping dangerous characters.
    
    Args:
        text: Raw user input
        
    Returns:
        Sanitized text safe for processing
    """
    if not text:
        return ""
    
    # Convert to string and strip
    clean_text = str(text).strip()
    
    # Remove null bytes and control characters except newlines/tabs
    # Replace control chars with space to avoid word concatenation
    clean_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', ' ', clean_text)
    
    # Normalize whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    return clean_text.strip()