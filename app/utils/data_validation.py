"""
Data validation utilities for scraped content quality assurance.

This module provides validation functions to ensure scraped product data
meets quality standards and contains expected information.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..models import ProductResult

logger = logging.getLogger(__name__)

@dataclass
class ValidationIssue:
    """Represents a validation issue found in product data."""
    field: str
    issue_type: str
    message: str
    severity: str  # "error", "warning", "info"

@dataclass
class DataValidationResult:
    """Result of data validation with issues and metrics."""
    is_valid: bool
    issues: List[ValidationIssue]
    quality_score: float  # 0-1 where 1 is perfect
    validated_product: Optional[ProductResult] = None

class ProductDataValidator:
    """
    Validator for ensuring product data quality and consistency.
    """
    
    def __init__(self):
        # Common Australian grocery terms that should appear in product names
        self.grocery_keywords = {
            'milk', 'bread', 'butter', 'cheese', 'eggs', 'flour', 'sugar', 'rice', 
            'pasta', 'cereal', 'yogurt', 'cream', 'meat', 'chicken', 'beef', 'pork',
            'fish', 'salmon', 'tuna', 'apple', 'banana', 'orange', 'carrot', 'potato',
            'tomato', 'lettuce', 'spinach', 'broccoli', 'onion', 'garlic', 'oil',
            'sauce', 'soap', 'shampoo', 'tissue', 'paper', 'detergent', 'coffee',
            'tea', 'chocolate', 'biscuit', 'cookie', 'juice', 'water', 'beer', 'wine'
        }
        
        # Valid price range (in AUD)
        self.min_price = 0.01
        self.max_price = 999.99
        
        # Valid retailers
        self.valid_retailers = {'woolworths', 'coles'}
        
        # Suspicious patterns in product names
        self.suspicious_patterns = [
            r'<[^>]+>',  # HTML tags
            r'javascript:',  # JavaScript
            r'[^\w\s\-\.\(\)&\$\+\%\/\:\'\,]',  # Unusual characters
            r'\b(lorem|ipsum|placeholder|test|sample|example)\b',  # Placeholder text
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',  # URLs
        ]
    
    def validate_product_name(self, name: str) -> List[ValidationIssue]:
        """Validate product name for quality and consistency."""
        issues = []
        
        if not name or not name.strip():
            issues.append(ValidationIssue(
                field="name",
                issue_type="missing_value",
                message="Product name is missing or empty",
                severity="error"
            ))
            return issues
        
        name = name.strip()
        
        # Check minimum length
        if len(name) < 3:
            issues.append(ValidationIssue(
                field="name",
                issue_type="too_short",
                message=f"Product name too short: '{name}'",
                severity="warning"
            ))
        
        # Check maximum length
        if len(name) > 200:
            issues.append(ValidationIssue(
                field="name",
                issue_type="too_long",
                message=f"Product name too long ({len(name)} chars)",
                severity="warning"
            ))
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                issues.append(ValidationIssue(
                    field="name",
                    issue_type="suspicious_content",
                    message=f"Suspicious pattern found in name: {pattern}",
                    severity="error"
                ))
        
        # Check if name contains common grocery terms
        name_lower = name.lower()
        contains_grocery_term = any(term in name_lower for term in self.grocery_keywords)
        
        if not contains_grocery_term:
            issues.append(ValidationIssue(
                field="name",
                issue_type="unlikely_product",
                message="Product name doesn't contain common grocery terms",
                severity="warning"
            ))
        
        # Check for repeated text (common scraping error)
        words = name_lower.split()
        if len(words) > 2:
            word_counts = {}
            for word in words:
                if len(word) > 2:  # Only check meaningful words
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            repeated_words = [word for word, count in word_counts.items() if count > 2]
            if repeated_words:
                issues.append(ValidationIssue(
                    field="name",
                    issue_type="repeated_content",
                    message=f"Repeated words detected: {repeated_words}",
                    severity="warning"
                ))
        
        return issues
    
    def validate_price(self, price: Optional[float], was_price: Optional[float] = None) -> List[ValidationIssue]:
        """Validate price data for reasonableness and consistency."""
        issues = []
        
        if price is not None:
            # Check price range
            if price < self.min_price:
                issues.append(ValidationIssue(
                    field="price",
                    issue_type="unrealistic_value",
                    message=f"Price too low: ${price}",
                    severity="warning"
                ))
            
            if price > self.max_price:
                issues.append(ValidationIssue(
                    field="price",
                    issue_type="unrealistic_value",
                    message=f"Price too high: ${price}",
                    severity="warning"
                ))
            
            # Check for impossible precision (more than 2 decimal places)
            try:
                decimal_price = Decimal(str(price))
                if decimal_price.as_tuple().exponent < -2:
                    issues.append(ValidationIssue(
                        field="price",
                        issue_type="invalid_precision",
                        message=f"Price has too many decimal places: ${price}",
                        severity="warning"
                    ))
            except InvalidOperation:
                issues.append(ValidationIssue(
                    field="price",
                    issue_type="invalid_format",
                    message=f"Price format invalid: {price}",
                    severity="error"
                ))
        
        # Validate was_price if provided
        if was_price is not None:
            if was_price < self.min_price or was_price > self.max_price:
                issues.append(ValidationIssue(
                    field="was",
                    issue_type="unrealistic_value",
                    message=f"Was price out of range: ${was_price}",
                    severity="warning"
                ))
            
            # Check price consistency
            if price is not None and was_price <= price:
                issues.append(ValidationIssue(
                    field="was",
                    issue_type="inconsistent_pricing",
                    message=f"Was price (${was_price}) should be higher than current price (${price})",
                    severity="error"
                ))
        
        return issues
    
    def validate_url(self, url: Optional[str], retailer: str) -> List[ValidationIssue]:
        """Validate product URL for correctness and security."""
        issues = []
        
        if url is None:
            # Missing URL is not critical but reduces quality
            issues.append(ValidationIssue(
                field="url",
                issue_type="missing_value",
                message="Product URL is missing",
                severity="info"
            ))
            return issues
        
        # Check URL format
        if not re.match(r'https?://[^\s<>"{}|\\^`\[\]]+', url):
            issues.append(ValidationIssue(
                field="url",
                issue_type="invalid_format",
                message=f"Invalid URL format: {url}",
                severity="error"
            ))
            return issues
        
        # Check if URL matches expected retailer domain
        expected_domains = {
            'woolworths': 'woolworths.com.au',
            'coles': 'coles.com.au'
        }
        
        expected_domain = expected_domains.get(retailer.lower())
        if expected_domain and expected_domain not in url.lower():
            issues.append(ValidationIssue(
                field="url",
                issue_type="mismatched_retailer",
                message=f"URL domain doesn't match retailer {retailer}: {url}",
                severity="error"
            ))
        
        # Check URL length
        if len(url) > 500:
            issues.append(ValidationIssue(
                field="url",
                issue_type="too_long",
                message=f"URL too long ({len(url)} chars)",
                severity="warning"
            ))
        
        return issues
    
    def validate_retailer(self, retailer: Optional[str]) -> List[ValidationIssue]:
        """Validate retailer information."""
        issues = []
        
        if not retailer:
            issues.append(ValidationIssue(
                field="retailer",
                issue_type="missing_value",
                message="Retailer is missing",
                severity="error"
            ))
            return issues
        
        if retailer.lower() not in self.valid_retailers:
            issues.append(ValidationIssue(
                field="retailer",
                issue_type="invalid_value",
                message=f"Unknown retailer: {retailer}",
                severity="error"
            ))
        
        return issues
    
    def validate_promo_data(self, promo_text: Optional[str], promo_flag: Optional[bool], price: Optional[float], was_price: Optional[float]) -> List[ValidationIssue]:
        """Validate promotional data for consistency."""
        issues = []
        
        # If promo_flag is True, there should be supporting evidence
        if promo_flag is True:
            has_was_price = was_price is not None and price is not None and was_price > price
            has_promo_text = promo_text is not None and len(promo_text.strip()) > 0
            
            if not has_was_price and not has_promo_text:
                issues.append(ValidationIssue(
                    field="promoFlag",
                    issue_type="unsupported_claim",
                    message="Product marked as on sale but no supporting evidence (was price or promo text)",
                    severity="warning"
                ))
        
        # If there's a was price, promo_flag should probably be True
        if was_price is not None and price is not None and was_price > price:
            if promo_flag is not True:
                issues.append(ValidationIssue(
                    field="promoFlag",
                    issue_type="missing_flag",
                    message="Product has discount pricing but promo_flag is not True",
                    severity="warning"
                ))
        
        # Validate promo text content
        if promo_text:
            # Check for suspicious content
            if re.search(r'<[^>]+>', promo_text):
                issues.append(ValidationIssue(
                    field="promoText",
                    issue_type="contains_html",
                    message="Promo text contains HTML tags",
                    severity="warning"
                ))
            
            # Check length
            if len(promo_text.strip()) > 100:
                issues.append(ValidationIssue(
                    field="promoText",
                    issue_type="too_long",
                    message=f"Promo text too long ({len(promo_text)} chars)",
                    severity="info"
                ))
        
        return issues
    
    def validate_product(self, product: ProductResult) -> DataValidationResult:
        """
        Validate a complete product for data quality.
        
        Args:
            product: Product to validate
            
        Returns:
            Validation result with issues and quality score
        """
        all_issues = []
        
        # Validate each field
        all_issues.extend(self.validate_product_name(product.name or ""))
        all_issues.extend(self.validate_price(product.price, product.was))
        all_issues.extend(self.validate_url(product.url, product.retailer or ""))
        all_issues.extend(self.validate_retailer(product.retailer))
        all_issues.extend(self.validate_promo_data(
            product.promoText, 
            product.promoFlag, 
            product.price, 
            product.was
        ))
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(all_issues)
        
        # Determine if valid (no critical errors)
        critical_errors = [issue for issue in all_issues if issue.severity == "error"]
        is_valid = len(critical_errors) == 0
        
        # Create cleaned product if valid
        validated_product = None
        if is_valid:
            validated_product = self._clean_product_data(product)
        
        result = DataValidationResult(
            is_valid=is_valid,
            issues=all_issues,
            quality_score=quality_score,
            validated_product=validated_product
        )
        
        # Log validation result
        if critical_errors:
            logger.warning(
                f"Product validation failed: {product.name}",
                extra={
                    "retailer": product.retailer,
                    "errors": len(critical_errors),
                    "warnings": len([i for i in all_issues if i.severity == "warning"]),
                    "quality_score": quality_score
                }
            )
        elif all_issues:
            logger.debug(
                f"Product validation passed with issues: {product.name}",
                extra={
                    "retailer": product.retailer,
                    "warnings": len([i for i in all_issues if i.severity == "warning"]),
                    "quality_score": quality_score
                }
            )
        
        return result
    
    def _calculate_quality_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate a quality score from 0-1 based on validation issues."""
        if not issues:
            return 1.0
        
        # Weight different issue types
        weights = {
            "error": -0.3,
            "warning": -0.1,
            "info": -0.05
        }
        
        total_deduction = sum(weights.get(issue.severity, -0.1) for issue in issues)
        
        # Ensure score stays between 0 and 1
        quality_score = max(0.0, min(1.0, 1.0 + total_deduction))
        
        return quality_score
    
    def _clean_product_data(self, product: ProductResult) -> ProductResult:
        """Clean and normalize product data."""
        # Create a copy with cleaned data
        cleaned_data = {
            "name": (product.name or "").strip(),
            "price": product.price,
            "was": product.was,
            "promoText": (product.promoText or "").strip() if product.promoText else None,
            "promoFlag": product.promoFlag,
            "url": (product.url or "").strip() if product.url else None,
            "inStock": product.inStock,
            "retailer": (product.retailer or "").lower()
        }
        
        # Remove empty strings
        for key in ["promoText", "url"]:
            if cleaned_data[key] == "":
                cleaned_data[key] = None
        
        return ProductResult(**cleaned_data)

# Global validator instance
_product_validator = ProductDataValidator()

def get_product_validator() -> ProductDataValidator:
    """Get global product validator instance."""
    return _product_validator

def validate_scraped_products(products: List[ProductResult], 
                            min_quality_score: float = 0.7) -> List[ProductResult]:
    """
    Validate a list of scraped products and filter by quality.
    
    Args:
        products: List of products to validate
        min_quality_score: Minimum quality score to include
        
    Returns:
        List of validated and cleaned products
    """
    validator = get_product_validator()
    validated_products = []
    
    for product in products:
        validation_result = validator.validate_product(product)
        
        if validation_result.is_valid and validation_result.quality_score >= min_quality_score:
            validated_products.append(validation_result.validated_product)
        else:
            logger.debug(
                f"Product filtered due to low quality: {product.name}",
                extra={
                    "quality_score": validation_result.quality_score,
                    "min_required": min_quality_score,
                    "issues_count": len(validation_result.issues)
                }
            )
    
    logger.info(
        f"Product validation completed: {len(validated_products)}/{len(products)} products passed",
        extra={
            "total_products": len(products),
            "validated_products": len(validated_products),
            "filtered_products": len(products) - len(validated_products),
            "min_quality_score": min_quality_score
        }
    )
    
    return validated_products