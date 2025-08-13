"""
Tests for cache integration in retailer adapters.
"""
import time
import pytest
import httpx
import respx
from unittest.mock import patch, MagicMock

from app.adapters.woolworths import WoolworthsAdapter
from app.adapters.coles import ColesAdapter
from app.models import ProductResult
from app.utils.cache import clear_cache

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear cache before each test."""
    clear_cache()
    yield
    clear_cache()


class TestWoolworthsCaching:
    """Test caching functionality in WoolworthsAdapter."""
    
    @respx.mock
    async def test_cache_miss_and_hit(self):
        """Test cache miss on first request, hit on second."""
        adapter = WoolworthsAdapter()
        
        # Mock successful API response
        mock_response = {
            "products": [
                {
                    "displayName": "Woolworths Full Cream Milk 2L",
                    "pricing": {"now": 4.50, "was": 5.00},
                    "isOnSpecial": True,
                    "promoCallout": "Save 50c",
                    "stockcode": "123456",
                    "isAvailable": True
                }
            ]
        }
        
        # Mock the API endpoint
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        # First request - should be cache miss
        with patch('app.adapters.woolworths.logger') as mock_logger:
            results1 = await adapter.search("milk 2L", "2000")
            
            # Check that cache miss was logged
            mock_logger.info.assert_any_call(
                "Cache miss, performing API search",
                extra={
                    "query": "milk 2L",
                    "postcode": "2000", 
                    "retailer": "woolworths",
                    "cache_hit": False
                }
            )
        
        # Verify results
        assert len(results1) == 1
        assert results1[0].name == "Woolworths Full Cream Milk 2L"
        assert results1[0].price == 4.50
        assert results1[0].promoFlag is True
        
        # Second request - should be cache hit (no HTTP call)
        with patch('app.adapters.woolworths.logger') as mock_logger:
            results2 = await adapter.search("milk 2L", "2000")
            
            # Check that cache hit was logged
            mock_logger.info.assert_any_call(
                "Cache hit for search",
                extra={
                    "query": "milk 2L",
                    "postcode": "2000",
                    "retailer": "woolworths", 
                    "cache_hit": True,
                    "latency": pytest.approx(0.0, abs=0.1),
                    "results_count": 1
                }
            )
        
        # Results should be identical
        assert results2 == results1
        
        # Verify only one HTTP request was made (first request only)
        assert len(respx.calls) == 1
    
    @respx.mock
    async def test_cache_with_different_keys(self):
        """Test that different query/postcode combinations create separate cache entries."""
        adapter = WoolworthsAdapter()
        
        # Mock different responses for different queries
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json={"products": [
                {"displayName": "Test Product", "pricing": {"now": 1.0}}
            ]})
        )
        
        # Different combinations should create separate cache entries
        await adapter.search("milk", "2000")
        await adapter.search("milk", "2001")  # Different postcode
        await adapter.search("bread", "2000")  # Different query
        
        # Should have made 3 separate HTTP requests
        assert len(respx.calls) == 3
        
        # Now repeat the same requests - should hit cache
        await adapter.search("milk", "2000")  # Cache hit
        await adapter.search("milk", "2001")  # Cache hit 
        await adapter.search("bread", "2000")  # Cache hit
        
        # Still should be only 3 HTTP requests (no additional calls)
        assert len(respx.calls) == 3
    
    @respx.mock
    async def test_cache_key_normalization(self):
        """Test that queries are normalized for consistent caching."""
        adapter = WoolworthsAdapter()
        
        mock_response = {"products": [{"displayName": "Milk", "pricing": {"now": 4.0}}]}
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        # First request with specific formatting
        await adapter.search("  MILK 2L  ", "2000")
        
        # Second request with different formatting but same meaning
        await adapter.search("milk 2l", "2000")
        
        # Should only make one HTTP request due to key normalization
        assert len(respx.calls) == 1
    
    async def test_cache_ttl_expiration(self):
        """Test that cached entries expire after TTL."""
        # Create adapter with a very short cache TTL
        from app.utils.cache import TTLCache
        adapter = WoolworthsAdapter()
        
        # Replace the cache with one that has a very short TTL
        short_ttl_cache = TTLCache(max_size=1000, default_ttl_seconds=1)  # 1 second TTL
        adapter.cache = short_ttl_cache
            
        with respx.mock:
            # Mock only the first endpoint to succeed
            respx.get(url__startswith="https://www.woolworths.com.au/apis/ui/Search/products").mock(
                return_value=httpx.Response(200, json={"products": []})
            )
            
            # First request - cache miss
            await adapter.search("milk", "2000")
            initial_call_count = len(respx.calls)
            assert initial_call_count == 1
            
            # Immediate second request - cache hit
            await adapter.search("milk", "2000") 
            assert len(respx.calls) == initial_call_count
            
            # Wait for cache to expire
            time.sleep(1.5)
            
            # Third request after expiration - cache miss
            await adapter.search("milk", "2000")
            assert len(respx.calls) > initial_call_count
    
    @respx.mock
    async def test_empty_results_cached(self):
        """Test that empty results are also cached."""
        adapter = WoolworthsAdapter()
        
        # Mock empty response
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json={"products": []})
        )
        
        # First request - empty results
        results1 = await adapter.search("nonexistent_product", "2000")
        assert results1 == []
        assert len(respx.calls) == 1
        
        # Second request - should hit cache even for empty results  
        results2 = await adapter.search("nonexistent_product", "2000")
        assert results2 == []
        assert len(respx.calls) == 1  # No additional HTTP call
    
    @respx.mock  
    async def test_cache_on_api_failure(self):
        """Test cache behavior when API calls fail."""
        adapter = WoolworthsAdapter()
        
        # Mock all endpoints to return 500 error
        respx.get(url__startswith="https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )
        respx.get(url__startswith="https://www.woolworths.com.au/api/ui/Search/products").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )
        respx.get(url__startswith="https://www.woolworths.com.au/apis/search/products").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )
        
        # First request - API failure with retries, should return empty and cache empty result
        results1 = await adapter.search("milk", "2000")
        assert results1 == []
        initial_call_count = len(respx.calls)
        
        # Second request - should hit cache (no additional HTTP calls)
        results2 = await adapter.search("milk", "2000")
        assert results2 == []
        assert len(respx.calls) == initial_call_count  # No additional calls


class TestColesCaching:
    """Test caching functionality in ColesAdapter."""
    
    @respx.mock
    async def test_cache_integration_consistency(self):
        """Test that Coles adapter caching works consistently with Woolworths."""
        adapter = ColesAdapter()
        
        mock_response = {
            "results": [
                {
                    "name": "Coles Full Cream Milk 2L",
                    "pricing": {"currentPrice": 4.80},
                    "id": "789012",
                    "inStock": True
                }
            ]
        }
        
        respx.get("https://www.coles.com.au/api/products/search").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        # First request - cache miss
        with patch('app.adapters.coles.logger') as mock_logger:
            results1 = await adapter.search("milk 2L", "2000")
            
            mock_logger.info.assert_any_call(
                "Cache miss, performing API search",
                extra={
                    "query": "milk 2L",
                    "postcode": "2000",
                    "retailer": "coles", 
                    "cache_hit": False
                }
            )
        
        # Second request - cache hit
        with patch('app.adapters.coles.logger') as mock_logger:
            results2 = await adapter.search("milk 2L", "2000")
            
            mock_logger.info.assert_any_call(
                "Cache hit for search",
                extra={
                    "query": "milk 2L",
                    "postcode": "2000",
                    "retailer": "coles",
                    "cache_hit": True, 
                    "latency": pytest.approx(0.0, abs=0.1),
                    "results_count": 1
                }
            )
        
        assert results1 == results2
        assert len(respx.calls) == 1
    
    @respx.mock
    async def test_retailer_specific_caching(self):
        """Test that Woolworths and Coles cache entries are separate."""
        woolworths_adapter = WoolworthsAdapter()
        coles_adapter = ColesAdapter()
        
        # Mock different responses for each retailer
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json={
                "products": [{"displayName": "Woolworths Milk", "pricing": {"now": 4.50}}]
            })
        )
        
        respx.get("https://www.coles.com.au/api/products/search").mock(
            return_value=httpx.Response(200, json={
                "results": [{"name": "Coles Milk", "pricing": {"currentPrice": 4.80}}]
            })
        )
        
        # Search same query on both retailers
        woolworths_results = await woolworths_adapter.search("milk", "2000")
        coles_results = await coles_adapter.search("milk", "2000")
        
        # Both should make HTTP requests (separate cache entries)
        assert len(respx.calls) == 2
        
        # Results should be different
        assert woolworths_results[0].name == "Woolworths Milk"
        assert coles_results[0].name == "Coles Milk"
        
        # Repeat searches should hit cache
        await woolworths_adapter.search("milk", "2000")  # Cache hit
        await coles_adapter.search("milk", "2000")  # Cache hit
        
        # Should still be only 2 HTTP requests
        assert len(respx.calls) == 2


class TestCacheLogging:
    """Test cache-related logging functionality."""
    
    @respx.mock
    async def test_cache_logging_details(self):
        """Test that cache operations are logged with proper details."""
        adapter = WoolworthsAdapter()
        
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json={"products": []})
        )
        
        with patch('app.adapters.woolworths.logger') as mock_logger:
            # First request - cache miss  
            await adapter.search("test_query", "2001")
            
            # Verify cache miss logging
            mock_logger.info.assert_any_call(
                "Cache miss, performing API search",
                extra={
                    "query": "test_query",
                    "postcode": "2001",
                    "retailer": "woolworths",
                    "cache_hit": False
                }
            )
            
            # Verify search completion logging
            mock_logger.info.assert_any_call(
                "Search completed",
                extra={
                    "query": "test_query",
                    "postcode": "2001", 
                    "retailer": "woolworths",
                    "cache_hit": False,
                    "latency": pytest.approx(0.0, abs=1.0),
                    "results_count": 0
                }
            )
        
        with patch('app.adapters.woolworths.logger') as mock_logger:
            # Second request - cache hit
            await adapter.search("test_query", "2001")
            
            # Verify cache hit logging
            mock_logger.info.assert_any_call(
                "Cache hit for search", 
                extra={
                    "query": "test_query",
                    "postcode": "2001",
                    "retailer": "woolworths",
                    "cache_hit": True,
                    "latency": pytest.approx(0.0, abs=0.1),
                    "results_count": 0
                }
            )


class TestCachePerformance:
    """Test cache performance characteristics."""
    
    @respx.mock
    async def test_cache_performance_improvement(self):
        """Test that cache significantly improves response times."""
        adapter = WoolworthsAdapter()
        
        # Mock slow API response
        def slow_response(request):
            time.sleep(0.1)  # Simulate network delay
            return httpx.Response(200, json={"products": []})
        
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            side_effect=slow_response
        )
        
        # First request - should be slow (includes network delay)
        start_time = time.time()
        await adapter.search("milk", "2000")
        first_request_time = time.time() - start_time
        
        # Second request - should be fast (cache hit)
        start_time = time.time()  
        await adapter.search("milk", "2000")
        second_request_time = time.time() - start_time
        
        # Cache hit should be significantly faster
        assert second_request_time < first_request_time / 10  # At least 10x faster
        assert second_request_time < 0.01  # Less than 10ms
    
    async def test_concurrent_cache_access(self):
        """Test cache behavior under concurrent access."""
        import asyncio
        
        adapter = WoolworthsAdapter()
        
        with respx.mock:
            respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
                return_value=httpx.Response(200, json={"products": []})
            )
            
            # Run multiple concurrent requests for same query
            tasks = []
            for _ in range(10):
                task = asyncio.create_task(adapter.search("concurrent_test", "2000"))
                tasks.append(task)
            
            # Wait for all requests to complete
            results = await asyncio.gather(*tasks)
            
            # All results should be identical
            first_result = results[0]
            for result in results[1:]:
                assert result == first_result
            
            # Only one HTTP request should have been made
            # (first request populates cache, others hit cache)
            assert len(respx.calls) <= 2  # Allow for some race condition tolerance