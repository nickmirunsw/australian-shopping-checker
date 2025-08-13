"""
Tests for product matching utilities.
"""

import pytest
from app.utils.matching import ProductMatcher, MatchScore, get_product_matcher
from app.models import ProductResult


class TestProductMatcher:
    """Test ProductMatcher functionality."""
    
    def test_normalize_product_name(self):
        """Test product name normalization."""
        matcher = ProductMatcher()
        
        test_cases = [
            ("Woolworths Full Cream Milk 2L", "full cream milk 2l"),
            ("COLES Organic Free Range Eggs", "organic free range eggs"),
            ("  Extra   Spaces  ", "extra spaces"),
            ("2 Litre Milk", "2L milk"),
            ("500 grams pasta", "500g pasta"),
            ("1 kilogram flour", "1kg flour"),
        ]
        
        for input_name, expected in test_cases:
            result = matcher.normalize_product_name(input_name)
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_extract_keywords(self):
        """Test keyword extraction."""
        matcher = ProductMatcher()
        
        test_cases = [
            ("milk 2L full cream", ["milk", "2l", "full", "cream"]),
            ("bread white 680g", ["bread", "white", "680g"]),
            ("the quick brown fox", ["quick", "brown", "fox"]),  # Stop words removed
            ("apples and oranges", ["apples", "oranges"]),  # 'and' removed
        ]
        
        for input_text, expected in test_cases:
            result = matcher.extract_keywords(input_text)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_calculate_basic_similarity(self):
        """Test basic similarity calculation."""
        matcher = ProductMatcher()
        
        # Exact match
        similarity = matcher.calculate_basic_similarity("milk 2L", "milk 2L")
        assert similarity == 1.0
        
        # Partial match
        similarity = matcher.calculate_basic_similarity("milk", "milk 2L")
        assert similarity > 0.5
        
        # No match
        similarity = matcher.calculate_basic_similarity("milk", "bread")
        assert similarity < 0.5
        
        # Empty strings
        similarity = matcher.calculate_basic_similarity("", "milk")
        assert similarity == 0.0
    
    def test_calculate_keyword_similarity(self):
        """Test keyword-based similarity."""
        matcher = ProductMatcher()
        
        # Perfect keyword match
        similarity = matcher.calculate_keyword_similarity("milk cream", "cream milk")
        assert similarity == 1.0
        
        # Partial keyword match
        similarity = matcher.calculate_keyword_similarity("milk 2L", "milk full cream")
        assert 0.20 <= similarity <= 0.75  # 1 word matches out of different totals
        
        # No keyword match
        similarity = matcher.calculate_keyword_similarity("milk", "bread")
        assert similarity == 0.0
    
    def test_calculate_exact_match_bonus(self):
        """Test exact match bonus calculation."""
        matcher = ProductMatcher()
        
        # All words match exactly
        bonus = matcher.calculate_exact_match_bonus("milk cream", "cream milk full")
        assert bonus > 0.0
        
        # No exact matches
        bonus = matcher.calculate_exact_match_bonus("milk", "bread")
        assert bonus == 0.0
    
    def test_calculate_brand_match_bonus(self):
        """Test brand match bonus."""
        matcher = ProductMatcher()
        
        # Brand match
        bonus = matcher.calculate_brand_match_bonus("woolworths milk", "woolworths full cream milk")
        assert bonus == matcher.brand_match_bonus
        
        # No brand match
        bonus = matcher.calculate_brand_match_bonus("milk", "bread")
        assert bonus == 0.0
    
    def test_calculate_size_match_bonus(self):
        """Test size match bonus."""
        matcher = ProductMatcher()
        
        # Size unit match
        bonus = matcher.calculate_size_match_bonus("milk 2L", "full cream milk 2L")
        assert bonus > 0.0
        
        # No size match
        bonus = matcher.calculate_size_match_bonus("milk", "bread 680g")
        assert bonus == 0.0
    
    def test_calculate_match_score(self):
        """Test comprehensive match score calculation."""
        matcher = ProductMatcher()
        
        # Perfect match
        score = matcher.calculate_match_score("milk 2L", "milk 2L")
        assert score.total_score > 0.9
        assert score.confidence == "high"
        
        # Good match with brand
        score = matcher.calculate_match_score("woolworths milk", "woolworths full cream milk 2L")
        assert score.total_score > 0.6
        assert score.brand_match_bonus > 0.0
        
        # Poor match
        score = matcher.calculate_match_score("milk", "bread 680g")
        assert score.total_score < 0.3
        assert score.confidence == "low"
    
    def test_find_best_match(self):
        """Test finding best match from product list."""
        matcher = ProductMatcher()
        
        products = [
            ProductResult(name="White Bread 680g", retailer="woolworths"),
            ProductResult(name="Milk Full Cream 2L", retailer="woolworths"),
            ProductResult(name="Organic Milk 2L", retailer="coles"),
            ProductResult(name="Apples Granny Smith", retailer="coles"),
        ]
        
        # Should match milk products
        best_product, match_score = matcher.find_best_match("milk 2L", products)
        assert best_product is not None
        assert "milk" in best_product.name.lower()
        assert "2l" in best_product.name.lower()
        assert match_score.total_score > 0.5
        
        # Should match bread
        best_product, match_score = matcher.find_best_match("bread", products)
        assert best_product is not None
        assert "bread" in best_product.name.lower()
        
        # No good match
        best_product, match_score = matcher.find_best_match("pasta", products)
        # Depending on threshold, might be None or a poor match
        if best_product:
            assert match_score.total_score < 0.5
    
    def test_rank_products(self):
        """Test ranking products by match score."""
        matcher = ProductMatcher()
        
        products = [
            ProductResult(name="White Bread 680g", retailer="woolworths"),
            ProductResult(name="Milk Full Cream 2L", retailer="woolworths"),
            ProductResult(name="Milk 2L Light", retailer="coles"),
            ProductResult(name="Organic Milk 1L", retailer="coles"),
        ]
        
        ranked = matcher.rank_products("milk 2L", products)
        
        # Should return products in order of match quality
        assert len(ranked) >= 2  # At least milk products should match
        
        # First result should be best match
        best_product, best_score = ranked[0]
        assert "milk" in best_product.name.lower()
        
        # Scores should be in descending order
        for i in range(len(ranked) - 1):
            assert ranked[i][1].total_score >= ranked[i+1][1].total_score
    
    def test_matcher_with_no_products(self):
        """Test matcher behavior with empty product list."""
        matcher = ProductMatcher()
        
        best_product, match_score = matcher.find_best_match("milk", [])
        assert best_product is None
        assert match_score is None
        
        ranked = matcher.rank_products("milk", [])
        assert ranked == []
    
    def test_matcher_with_empty_names(self):
        """Test matcher behavior with products that have empty names."""
        matcher = ProductMatcher()
        
        products = [
            ProductResult(name="", retailer="woolworths"),
            ProductResult(name="Unknown Product", retailer="coles"),  # Can't use None
            ProductResult(name="Milk 2L", retailer="woolworths"),
        ]
        
        best_product, match_score = matcher.find_best_match("milk", products)
        assert best_product is not None
        assert best_product.name == "Milk 2L"
    
    def test_configurable_thresholds(self):
        """Test matcher with different threshold configurations."""
        # Strict matcher
        strict_matcher = ProductMatcher(
            min_similarity=0.8,
            high_confidence_threshold=0.9,
            medium_confidence_threshold=0.75
        )
        
        # Lenient matcher
        lenient_matcher = ProductMatcher(
            min_similarity=0.2,
            high_confidence_threshold=0.6,
            medium_confidence_threshold=0.4
        )
        
        products = [ProductResult(name="Milk Full Cream", retailer="woolworths")]
        
        # Strict matcher might reject marginal matches
        strict_result, strict_score = strict_matcher.find_best_match("milk", products)
        
        # Lenient matcher should accept more matches
        lenient_result, lenient_score = lenient_matcher.find_best_match("milk", products)
        
        # Both should find the match, but confidence levels might differ
        assert lenient_result is not None
        if strict_result:
            assert strict_score.total_score >= strict_matcher.min_similarity


class TestMatchScore:
    """Test MatchScore dataclass."""
    
    def test_match_score_creation(self):
        """Test creating MatchScore objects."""
        score = MatchScore(
            total_score=0.85,
            name_similarity=0.7,
            exact_match_bonus=0.1,
            brand_match_bonus=0.05,
            size_match_bonus=0.0,
            keyword_match_bonus=0.0,
            confidence="high"
        )
        
        assert score.total_score == 0.85
        assert score.confidence == "high"
        assert score.name_similarity == 0.7


class TestGlobalMatcher:
    """Test global matcher function."""
    
    def test_get_product_matcher(self):
        """Test getting global matcher instance."""
        matcher1 = get_product_matcher()
        matcher2 = get_product_matcher()
        
        # Should return same instance (singleton pattern)
        assert matcher1 is matcher2
        assert isinstance(matcher1, ProductMatcher)