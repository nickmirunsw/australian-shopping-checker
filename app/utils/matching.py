"""
Advanced product matching utilities with configurable similarity thresholds.

This module provides sophisticated product matching algorithms to improve
the accuracy of finding relevant products from retailer search results.
"""

import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..models import ProductResult
from ..settings import settings

logger = logging.getLogger(__name__)

@dataclass
class MatchScore:
    """Represents a match score with breakdown."""
    total_score: float
    name_similarity: float
    exact_match_bonus: float
    brand_match_bonus: float
    size_match_bonus: float
    keyword_match_bonus: float
    confidence: str  # "high", "medium", "low"

class ProductMatcher:
    """
    Advanced product matcher with configurable thresholds and scoring.
    """
    
    def __init__(self, 
                 min_similarity: float = 0.3,
                 high_confidence_threshold: float = 0.8,
                 medium_confidence_threshold: float = 0.6,
                 exact_match_bonus: float = 0.2,
                 brand_match_bonus: float = 0.15,
                 size_match_bonus: float = 0.1,
                 keyword_match_bonus: float = 0.05):
        """
        Initialize product matcher with configurable parameters.
        
        Args:
            min_similarity: Minimum similarity score to consider a match
            high_confidence_threshold: Threshold for high confidence matches
            medium_confidence_threshold: Threshold for medium confidence matches
            exact_match_bonus: Bonus for exact word matches
            brand_match_bonus: Bonus for brand name matches
            size_match_bonus: Bonus for size/quantity matches
            keyword_match_bonus: Bonus per matching keyword
        """
        self.min_similarity = min_similarity
        self.high_confidence_threshold = high_confidence_threshold
        self.medium_confidence_threshold = medium_confidence_threshold
        self.exact_match_bonus = exact_match_bonus
        self.brand_match_bonus = brand_match_bonus
        self.size_match_bonus = size_match_bonus
        self.keyword_match_bonus = keyword_match_bonus
        
        # Common Australian grocery brands for bonus scoring
        self.common_brands = {
            'woolworths', 'coles', 'iga', 'aldi', 'macro', 'homebrand',
            'cadbury', 'nestle', 'kellogg', 'uncle tobys', 'sanitarium',
            'bega', 'devondale', 'paul\'s', 'dairy farmers', 'norco',
            'steggles', 'lilydale', 'ingham\'s', 'tegel', 'primo',
            'masterfoods', 'maggi', 'continental', 'praise', 'fountain'
        }
        
        # Size/quantity keywords for bonus scoring
        self.size_keywords = {
            'ml', 'l', 'litre', 'liter', 'g', 'kg', 'gram', 'kilogram',
            'pack', 'each', 'dozen', 'bunch', 'bag', 'box', 'bottle',
            'can', 'jar', 'tube', 'punnet', 'tray', 'roll', 'sheet'
        }
    
    def normalize_product_name(self, name: str) -> str:
        """Normalize product name for better matching."""
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove common retailer prefixes
        prefixes_to_remove = [
            'woolworths ', 'coles ', 'iga ', 'aldi ', 'macro ', 'homebrand ',
            'select ', 'brand ', 'organic ', 'free range ', 'natural '
        ]
        
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        # Normalize size units
        size_normalizations = {
            r'\b(\d+)\s*litre?s?\b': r'\1L',
            r'\b(\d+)\s*ml\b': r'\1ml',
            r'\b(\d+)\s*grams?\b': r'\1g',
            r'\b(\d+)\s*kgs?\b': r'\1kg',
            r'\b(\d+)\s*kilograms?\b': r'\1kg',
        }
        
        for pattern, replacement in size_normalizations.items():
            normalized = re.sub(pattern, replacement, normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        if not text:
            return []
        
        # Normalize text
        normalized = self.normalize_product_name(text)
        
        # Split into words and filter
        words = re.findall(r'\b\w+\b', normalized)
        
        # Filter out common stop words but keep important descriptors
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'a', 'an'
        }
        
        # Keep words that are likely product descriptors
        keywords = []
        for word in words:
            if len(word) >= 2 and word not in stop_words:
                keywords.append(word)
        
        return keywords
    
    def calculate_basic_similarity(self, query: str, product_name: str) -> float:
        """Calculate basic string similarity using SequenceMatcher."""
        if not query or not product_name:
            return 0.0
        
        # Normalize both strings
        norm_query = self.normalize_product_name(query)
        norm_product = self.normalize_product_name(product_name)
        
        if not norm_query or not norm_product:
            return 0.0
        
        # Calculate similarity
        similarity = SequenceMatcher(None, norm_query, norm_product).ratio()
        
        return similarity
    
    def calculate_keyword_similarity(self, query: str, product_name: str) -> float:
        """Calculate similarity based on keyword matching."""
        query_keywords = set(self.extract_keywords(query))
        product_keywords = set(self.extract_keywords(product_name))
        
        if not query_keywords or not product_keywords:
            return 0.0
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = len(query_keywords.intersection(product_keywords))
        union = len(query_keywords.union(product_keywords))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def calculate_exact_match_bonus(self, query: str, product_name: str) -> float:
        """Calculate bonus for exact word matches."""
        query_words = set(self.extract_keywords(query))
        product_words = set(self.extract_keywords(product_name))
        
        if not query_words:
            return 0.0
        
        exact_matches = query_words.intersection(product_words)
        match_ratio = len(exact_matches) / len(query_words)
        
        return match_ratio * self.exact_match_bonus
    
    def calculate_brand_match_bonus(self, query: str, product_name: str) -> float:
        """Calculate bonus for brand name matches."""
        query_lower = query.lower()
        product_lower = product_name.lower()
        
        for brand in self.common_brands:
            if brand in query_lower and brand in product_lower:
                return self.brand_match_bonus
        
        return 0.0
    
    def calculate_size_match_bonus(self, query: str, product_name: str) -> float:
        """Calculate bonus for size/quantity matches."""
        query_lower = query.lower()
        product_lower = product_name.lower()
        
        bonus = 0.0
        for size_keyword in self.size_keywords:
            if size_keyword in query_lower and size_keyword in product_lower:
                bonus += self.size_match_bonus * 0.5  # Partial bonus per match
        
        # Extract specific size numbers (e.g., "2L", "500ml")
        query_sizes = re.findall(r'\d+(?:\.\d+)?(?:ml|l|g|kg)', query_lower)
        product_sizes = re.findall(r'\d+(?:\.\d+)?(?:ml|l|g|kg)', product_lower)
        
        for q_size in query_sizes:
            if q_size in product_sizes:
                bonus += self.size_match_bonus
        
        return min(bonus, self.size_match_bonus)  # Cap the bonus
    
    def calculate_keyword_count_bonus(self, query: str, product_name: str) -> float:
        """Calculate bonus based on number of matching keywords."""
        query_keywords = set(self.extract_keywords(query))
        product_keywords = set(self.extract_keywords(product_name))
        
        matching_keywords = query_keywords.intersection(product_keywords)
        bonus = len(matching_keywords) * self.keyword_match_bonus
        
        return min(bonus, self.keyword_match_bonus * 3)  # Cap bonus at 3 keywords
    
    def calculate_match_score(self, query: str, product_name: str) -> MatchScore:
        """
        Calculate comprehensive match score with breakdown.
        
        Args:
            query: User search query
            product_name: Product name from retailer
            
        Returns:
            MatchScore object with detailed scoring breakdown
        """
        if not query or not product_name:
            return MatchScore(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "low")
        
        # Calculate base similarity (weighted at 60%)
        basic_similarity = self.calculate_basic_similarity(query, product_name)
        keyword_similarity = self.calculate_keyword_similarity(query, product_name)
        base_score = (basic_similarity * 0.6) + (keyword_similarity * 0.4)
        
        # Calculate bonuses
        exact_match_bonus = self.calculate_exact_match_bonus(query, product_name)
        brand_match_bonus = self.calculate_brand_match_bonus(query, product_name)
        size_match_bonus = self.calculate_size_match_bonus(query, product_name)
        keyword_match_bonus = self.calculate_keyword_count_bonus(query, product_name)
        
        # Total score
        total_score = base_score + exact_match_bonus + brand_match_bonus + size_match_bonus + keyword_match_bonus
        total_score = min(total_score, 1.0)  # Cap at 1.0
        
        # Determine confidence level
        if total_score >= self.high_confidence_threshold:
            confidence = "high"
        elif total_score >= self.medium_confidence_threshold:
            confidence = "medium"
        else:
            confidence = "low"
        
        return MatchScore(
            total_score=total_score,
            name_similarity=base_score,
            exact_match_bonus=exact_match_bonus,
            brand_match_bonus=brand_match_bonus,
            size_match_bonus=size_match_bonus,
            keyword_match_bonus=keyword_match_bonus,
            confidence=confidence
        )
    
    def find_best_match(self, query: str, products: List[ProductResult]) -> Tuple[Optional[ProductResult], Optional[MatchScore]]:
        """
        Find the best matching product from a list of candidates.
        
        Args:
            query: User search query
            products: List of product results to match against
            
        Returns:
            Tuple of (best_product, match_score) or (None, None) if no good match
        """
        if not products:
            return None, None
        
        best_product = None
        best_score = None
        best_score_value = 0.0
        
        for product in products:
            if not product.name:
                continue
            
            match_score = self.calculate_match_score(query, product.name)
            
            if match_score.total_score > best_score_value and match_score.total_score >= self.min_similarity:
                best_product = product
                best_score = match_score
                best_score_value = match_score.total_score
        
        # Log the matching result
        if best_product and best_score:
            logger.debug(
                "Best product match found",
                extra={
                    "query": query,
                    "product_name": best_product.name,
                    "score": best_score.total_score,
                    "confidence": best_score.confidence,
                    "retailer": best_product.retailer
                }
            )
        else:
            logger.debug(
                "No suitable product match found",
                extra={
                    "query": query,
                    "candidates_count": len(products),
                    "min_similarity": self.min_similarity
                }
            )
        
        return best_product, best_score
    
    def rank_products(self, query: str, products: List[ProductResult]) -> List[Tuple[ProductResult, MatchScore]]:
        """
        Rank all products by match score.
        
        Args:
            query: User search query
            products: List of product results to rank
            
        Returns:
            List of (product, match_score) tuples sorted by score descending
        """
        if not products:
            return []
        
        scored_products = []
        
        for product in products:
            if not product.name:
                continue
            
            match_score = self.calculate_match_score(query, product.name)
            
            if match_score.total_score >= self.min_similarity:
                scored_products.append((product, match_score))
        
        # Sort by score descending
        scored_products.sort(key=lambda x: x[1].total_score, reverse=True)
        
        return scored_products
    
    def find_multiple_matches(self, query: str, products: List[ProductResult], max_results: int = 8) -> List[Any]:
        """
        Find multiple matching products, returning the best matches with scores.
        
        Args:
            query: User search query
            products: List of product results to match against
            max_results: Maximum number of results to return
            
        Returns:
            List of match objects with product and score attributes
        """
        if not products:
            return []
        
        # Get ranked products
        ranked = self.rank_products(query, products)
        
        # Convert to match objects and limit results
        matches = []
        for product, score in ranked[:max_results]:
            # Create a simple match object
            match_obj = type('Match', (), {
                'product': product,
                'score': score
            })()
            matches.append(match_obj)
        
        logger.debug(
            f"Found {len(matches)} matches for query '{query}' (max_results={max_results})",
            extra={
                "query": query,
                "matches_count": len(matches),
                "products_count": len(products)
            }
        )
        
        return matches


# Global matcher instance with settings-based configuration
_product_matcher = None

def get_product_matcher() -> ProductMatcher:
    """Get configured product matcher instance."""
    global _product_matcher
    if _product_matcher is None:
        _product_matcher = ProductMatcher(
            min_similarity=getattr(settings, 'MIN_PRODUCT_SIMILARITY', 0.3),
            high_confidence_threshold=getattr(settings, 'HIGH_CONFIDENCE_THRESHOLD', 0.8),
            medium_confidence_threshold=getattr(settings, 'MEDIUM_CONFIDENCE_THRESHOLD', 0.6),
            exact_match_bonus=getattr(settings, 'EXACT_MATCH_BONUS', 0.2),
            brand_match_bonus=getattr(settings, 'BRAND_MATCH_BONUS', 0.15),
            size_match_bonus=getattr(settings, 'SIZE_MATCH_BONUS', 0.1),
            keyword_match_bonus=getattr(settings, 'KEYWORD_MATCH_BONUS', 0.05)
        )
    return _product_matcher