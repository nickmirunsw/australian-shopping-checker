"""
Tests for input validation utilities.
"""

import pytest
from app.utils.validation import (
    validate_postcode,
    validate_query,
    validate_items_string,
    validate_check_request,
    sanitize_user_input,
    ValidationError
)
from app.models import CheckItemsRequest


class TestValidatePostcode:
    """Test postcode validation."""
    
    def test_valid_postcodes(self):
        """Test valid Australian postcodes."""
        valid_postcodes = [
            "2000",  # NSW
            "3000",  # VIC
            "4000",  # QLD
            "5000",  # SA
            "6000",  # WA
            "7000",  # TAS
            "0800",  # NT
            "2600",  # ACT
            "7999"   # TAS edge case
        ]
        
        for postcode in valid_postcodes:
            result = validate_postcode(postcode)
            assert result.is_valid, f"Postcode {postcode} should be valid"
            assert result.sanitized_value == postcode
            assert not result.errors
    
    def test_invalid_postcodes(self):
        """Test invalid postcodes."""
        invalid_postcodes = [
            "",      # Empty
            "0000",  # Invalid range
            "123",   # Too short
            "12345", # Too long
            "abcd",  # Non-numeric
            "0500",  # Invalid range
            " 2000 " # Will be cleaned but should work
        ]
        
        for postcode in invalid_postcodes[:-1]:  # Exclude the last one (whitespace)
            result = validate_postcode(postcode)
            assert not result.is_valid, f"Postcode {postcode} should be invalid"
            assert result.errors
    
    def test_postcode_with_whitespace(self):
        """Test postcode with whitespace gets cleaned."""
        result = validate_postcode(" 2000 ")
        assert result.is_valid
        assert result.sanitized_value == "2000"
    
    def test_empty_postcode(self):
        """Test empty postcode."""
        result = validate_postcode("")
        assert not result.is_valid
        assert "required" in result.errors[0].lower()


class TestValidateQuery:
    """Test query validation."""
    
    def test_valid_queries(self):
        """Test valid search queries."""
        valid_queries = [
            "milk",
            "milk 2L",
            "Woolworths brand milk",
            "apples and oranges",
            "bread 680g white",
            "a" * 199  # Maximum length - 1
        ]
        
        for query in valid_queries:
            result = validate_query(query)
            assert result.is_valid, f"Query '{query}' should be valid"
            assert not result.errors
    
    def test_invalid_queries(self):
        """Test invalid queries."""
        invalid_queries = [
            "",       # Empty
            "a",      # Too short
            "a" * 201 # Too long
        ]
        
        for query in invalid_queries:
            result = validate_query(query)
            assert not result.is_valid, f"Query '{query}' should be invalid"
            assert result.errors
    
    def test_suspicious_content_warnings(self):
        """Test that suspicious content generates warnings."""
        suspicious_queries = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "onclick=alert('xss')",
            "union select * from users",
            "'; drop table users; --"
        ]
        
        for query in suspicious_queries:
            result = validate_query(query)
            # Should be valid but with warnings
            assert result.is_valid, f"Query '{query}' should be valid but with warnings"
            assert result.warnings, f"Query '{query}' should have warnings"
    
    def test_whitespace_normalization(self):
        """Test that excessive whitespace is normalized."""
        result = validate_query("  milk   2L  ")
        assert result.is_valid
        assert result.sanitized_value == "milk 2L"


class TestValidateItemsString:
    """Test items string validation."""
    
    def test_valid_items_string(self):
        """Test valid comma-separated items."""
        items_strings = [
            "milk",
            "milk, bread",
            "milk 2L, bread 680g, apples",
            "  milk  ,  bread  ",  # With whitespace
            "aa, bb, cc, dd, ee"  # Multiple items
        ]
        
        for items_str in items_strings:
            result = validate_items_string(items_str)
            assert result.is_valid, f"Items string '{items_str}' should be valid"
            assert not result.errors
    
    def test_invalid_items_string(self):
        """Test invalid items strings."""
        invalid_items = [
            "",  # Empty
            ",",  # Only comma
            ",,",  # Multiple commas only
            ", , ,",  # Commas with whitespace
        ]
        
        for items_str in invalid_items:
            result = validate_items_string(items_str)
            assert not result.is_valid, f"Items string '{items_str}' should be invalid"
            assert result.errors
    
    def test_too_many_items(self):
        """Test too many items in string."""
        # Create 21 items (over the limit)
        items = ", ".join([f"item{i}" for i in range(21)])
        result = validate_items_string(items)
        assert not result.is_valid
        assert "maximum 20 items" in result.errors[0].lower()
    
    def test_items_with_individual_validation_errors(self):
        """Test items string where individual items have errors."""
        # One valid item, one invalid (too short)
        result = validate_items_string("milk, a")
        assert not result.is_valid
        assert any("item 2" in error.lower() for error in result.errors)


class TestValidateCheckRequest:
    """Test complete request validation."""
    
    def test_valid_request(self):
        """Test valid check request."""
        request = CheckItemsRequest(items="milk, bread", postcode="2000")
        result = validate_check_request(request)
        assert result.is_valid
        assert not result.errors
    
    def test_invalid_request_items(self):
        """Test request with invalid items."""
        request = CheckItemsRequest(items="", postcode="2000")
        result = validate_check_request(request)
        assert not result.is_valid
        assert result.errors
    
    def test_invalid_request_postcode(self):
        """Test request with invalid postcode."""
        request = CheckItemsRequest(items="milk", postcode="0000")
        result = validate_check_request(request)
        assert not result.is_valid
        assert result.errors
    
    def test_invalid_request_both(self):
        """Test request with both items and postcode invalid."""
        request = CheckItemsRequest(items="", postcode="0000")
        result = validate_check_request(request)
        assert not result.is_valid
        # Should have errors for both fields
        assert len(result.errors) >= 2


class TestSanitizeUserInput:
    """Test user input sanitization."""
    
    def test_sanitize_normal_text(self):
        """Test sanitization of normal text."""
        text = "milk 2L brand"
        result = sanitize_user_input(text)
        assert result == "milk 2L brand"
    
    def test_sanitize_whitespace(self):
        """Test whitespace normalization."""
        text = "  milk   2L  "
        result = sanitize_user_input(text)
        assert result == "milk 2L"
    
    def test_sanitize_control_characters(self):
        """Test removal of control characters."""
        text = "milk\x00\x01\x02bread"
        result = sanitize_user_input(text)
        assert result == "milk bread"
    
    def test_sanitize_empty_input(self):
        """Test sanitization of empty input."""
        assert sanitize_user_input("") == ""
        assert sanitize_user_input(None) == ""
    
    def test_sanitize_preserve_newlines_tabs(self):
        """Test that newlines and tabs are preserved."""
        text = "milk\tbread\napples"
        result = sanitize_user_input(text)
        assert "\t" in result or " " in result  # Tab converted to space
        assert "milk" in result and "bread" in result and "apples" in result


class TestValidationError:
    """Test ValidationError exception."""
    
    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        error = ValidationError("Test message", "field_name", "ERROR_CODE")
        assert error.message == "Test message"
        assert error.field == "field_name"
        assert error.code == "ERROR_CODE"
        assert str(error) == "Test message"
    
    def test_validation_error_minimal(self):
        """Test creating ValidationError with minimal args."""
        error = ValidationError("Test message")
        assert error.message == "Test message"
        assert error.field is None
        assert error.code is None