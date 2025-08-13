import re
import asyncio
import logging
from typing import List, Dict, Any, Union, Optional, Tuple
from difflib import SequenceMatcher

from ..models import ProductResult
from ..adapters.woolworths import WoolworthsAdapter
from ..utils.matching import get_product_matcher, MatchScore
from ..utils.graceful_degradation import execute_multi_retailer_search_with_degradation
from ..utils.db_config import log_price_data, log_alternative_products, get_all_tracked_products

logger = logging.getLogger(__name__)


class SaleChecker:
    """Service for checking items across multiple retailers."""
    
    def __init__(self):
        self.woolworths = WoolworthsAdapter()
        self.retailers = {
            "woolworths": self.woolworths
        }
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching by lowercasing and removing extra whitespace."""
        return re.sub(r'\s+', ' ', text.lower().strip())
    
    def _extract_size_info(self, text: str) -> Tuple[str, str]:
        """Extract size/quantity information from product text."""
        # Common size patterns: 2L, 250ml, 1kg, 500g, 12 pack, etc.
        size_patterns = [
            r'(\d+(?:\.\d+)?)\s*([lL]|[mM][lL]|[gG]|[kK][gG])',  # 2L, 250ml, 1kg, 500g
            r'(\d+)\s*([pP]ack|[pP]k)',  # 12 pack, 6pk
            r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*([lL]|[mM][lL]|[gG]|[kK][gG])',  # 6x250ml
            r'(\d+(?:\.\d+)?)\s*([oO]z)',  # 16oz
        ]
        
        normalized = self._normalize_text(text)
        size_info = ""
        
        for pattern in size_patterns:
            matches = re.findall(pattern, normalized)
            if matches:
                size_info = " ".join(["".join(match) for match in matches])
                break
        
        # Remove size info from text for cleaner matching
        text_without_size = normalized
        for pattern in size_patterns:
            text_without_size = re.sub(pattern, '', text_without_size)
        
        text_without_size = re.sub(r'\s+', ' ', text_without_size).strip()
        
        return text_without_size, size_info
    
    def _calculate_match_score(self, query: str, product: ProductResult) -> float:
        """Calculate a match score between query and product (0-1, higher is better)."""
        query_normalized = self._normalize_text(query)
        product_name_normalized = self._normalize_text(product.name)
        
        # Extract size information
        query_text, query_size = self._extract_size_info(query_normalized)
        product_text, product_size = self._extract_size_info(product_name_normalized)
        
        # Base text similarity using SequenceMatcher
        text_similarity = SequenceMatcher(None, query_text, product_text).ratio()
        
        # Bonus for size match
        size_bonus = 0.0
        if query_size and product_size:
            size_similarity = SequenceMatcher(None, query_size, product_size).ratio()
            if size_similarity > 0.8:  # Close size match
                size_bonus = 0.2
            elif size_similarity > 0.5:  # Partial size match
                size_bonus = 0.1
        
        # Bonus for exact word matches
        query_words = set(query_text.split())
        product_words = set(product_text.split())
        
        if query_words and product_words:
            word_overlap = len(query_words.intersection(product_words)) / len(query_words)
            word_bonus = word_overlap * 0.1
        else:
            word_bonus = 0.0
        
        total_score = min(1.0, text_similarity + size_bonus + word_bonus)
        
        logger.debug(f"Match score for '{query}' vs '{product.name}': {total_score:.3f} "
                    f"(text: {text_similarity:.3f}, size: {size_bonus:.3f}, words: {word_bonus:.3f})")
        
        return total_score
    
    def _select_best_match(self, query: str, products: List[ProductResult]) -> Optional[ProductResult]:
        """Select the best matching product for a query using advanced matching."""
        if not products:
            return None
        
        matcher = get_product_matcher()
        best_product, best_score = matcher.find_best_match(query, products)
        
        if best_product and best_score:
            logger.info(
                f"Best match for '{query}': {best_product.name}",
                extra={
                    "query": query,
                    "product_name": best_product.name,
                    "retailer": best_product.retailer,
                    "score": best_score.total_score,
                    "confidence": best_score.confidence,
                    "name_similarity": best_score.name_similarity,
                    "bonuses": {
                        "exact_match": best_score.exact_match_bonus,
                        "brand_match": best_score.brand_match_bonus,
                        "size_match": best_score.size_match_bonus,
                        "keyword_match": best_score.keyword_match_bonus
                    }
                }
            )
            return best_product
        else:
            logger.info(
                f"No suitable match found for '{query}'",
                extra={
                    "query": query,
                    "candidates_count": len(products)
                }
            )
            return None
    
    async def check_items(self, items: List[str], postcode: str) -> Dict[str, Any]:
        """
        Check items across all retailers and return the best matches.
        
        Args:
            items: List of item queries (e.g., ["milk 2L", "weet-bix"])
            postcode: Australian postcode for location-based search
            
        Returns:
            Dict with results for each retailer and item
        """
        results = []
        
        for item in items:
            logger.info(f"Checking item: '{item}' at postcode '{postcode}'")
            
            # Check if this is a search for dummy data
            if "dummy" in item.lower():
                # Get dummy products from database and create mock results
                tracked_products = get_all_tracked_products()
                dummy_products = [p for p in tracked_products if "dummy" in p['product_name'].lower() and item.lower().replace("dummy", "").strip() in p['product_name'].lower()]
                
                for dummy_product in dummy_products:
                    # Create a mock result for the dummy product
                    result = {
                        "input": item,
                        "retailer": dummy_product['retailer'],
                        "bestMatch": dummy_product['product_name'],
                        "alternatives": [],
                        "onSale": True,  # Show as on sale for demo
                        "price": 3.50,   # Mock current price
                        "was": 4.65,     # Mock was price
                        "promoText": "Historical Sale Pattern Available",
                        "url": "https://example.com/dummy",
                        "inStock": True,
                        "potentialSavings": []
                    }
                    results.append(result)
                continue  # Skip real search for dummy items
            
            # Create search functions for graceful degradation
            search_functions = {}
            for retailer_name, adapter in self.retailers.items():
                # Create lambda with proper closure
                search_functions[retailer_name] = (lambda a, i, p: lambda: a.search(i, p))(adapter, item, postcode)
            
            # Execute searches with graceful degradation
            retailer_products = await execute_multi_retailer_search_with_degradation(
                search_functions=search_functions
            )
            
            # Find best match AND alternatives for each retailer
            for retailer_name, products in retailer_products.items():
                if not products:
                    result = {
                        "input": item,
                        "retailer": retailer_name,
                        "bestMatch": None,
                        "alternatives": [],
                        "onSale": False,
                        "price": None,
                        "was": None,
                        "promoText": None,
                        "url": None,
                        "inStock": None,
                        "potentialSavings": []
                    }
                    results.append(result)
                    continue
                
                # Get multiple matches using the matcher
                matcher = get_product_matcher()
                all_matches = matcher.find_multiple_matches(item, products, max_results=8)
                
                if all_matches:
                    best_match = all_matches[0]
                    alternatives = []
                    potential_savings = []
                    
                    # Process alternative matches
                    for match in all_matches[1:]:
                        alt_data = {
                            "name": match.product.name,
                            "price": match.product.price,
                            "was": match.product.was,
                            "onSale": match.product.promoFlag or False,
                            "promoText": match.product.promoText,
                            "url": match.product.url,
                            "matchScore": round(match.score.total_score, 2) if hasattr(match, 'score') else 0.8
                        }
                        alternatives.append(alt_data)
                        
                        # Calculate potential savings compared to best match
                        if best_match.product.price and match.product.price:
                            saving = best_match.product.price - match.product.price
                            if saving > 0:
                                potential_savings.append({
                                    "alternative": match.product.name,
                                    "currentPrice": round(best_match.product.price, 2),
                                    "alternativePrice": round(match.product.price, 2),
                                    "savings": round(saving, 2),
                                    "percentage": round((saving / best_match.product.price) * 100, 1)
                                })
                    
                    result = {
                        "input": item,
                        "retailer": retailer_name,
                        "bestMatch": best_match.product.name,
                        "alternatives": alternatives,
                        "onSale": best_match.product.promoFlag or False,
                        "price": best_match.product.price,
                        "was": best_match.product.was,
                        "promoText": best_match.product.promoText,
                        "url": best_match.product.url,
                        "inStock": best_match.product.inStock,
                        "potentialSavings": potential_savings
                    }
                else:
                    # No good match found
                    result = {
                        "input": item,
                        "retailer": retailer_name,
                        "bestMatch": None,
                        "alternatives": [],
                        "onSale": False,
                        "price": None,
                        "was": None,
                        "promoText": None,
                        "url": None,
                        "inStock": None,
                        "potentialSavings": []
                    }
                
                results.append(result)
                
                # Log price data and alternatives for tracking (non-blocking)
                try:
                    # Log the best match to price_history
                    if result.get('bestMatch') and result.get('price') is not None:
                        log_price_data(
                            product_name=result['bestMatch'],
                            retailer=result['retailer'],
                            price=result['price'],
                            was_price=result.get('was'),
                            on_sale=result.get('onSale', False),
                            url=result.get('url')
                        )
                    
                    # Log each alternative as individual price records
                    if result.get('alternatives'):
                        # Store alternatives in dedicated alternatives table
                        log_alternative_products(
                            search_query=item,
                            retailer=result['retailer'],
                            alternatives=result['alternatives']
                        )
                        
                        # ALSO log each alternative as individual price history records
                        for alternative in result['alternatives']:
                            if alternative.get('name') and alternative.get('price') is not None:
                                log_price_data(
                                    product_name=alternative['name'],
                                    retailer=result['retailer'],
                                    price=alternative['price'],
                                    was_price=alternative.get('was'),
                                    on_sale=alternative.get('onSale', False),
                                    url=alternative.get('url')
                                )
                                logger.debug(f"Logged alternative '{alternative['name']}' to price_history")
                except Exception as e:
                    # Don't let database errors break the main functionality
                    logger.warning(f"Failed to log data to database: {e}")
        
        return {
            "results": results,
            "postcode": postcode,
            "itemsChecked": len(items)
        }