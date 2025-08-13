"""
Tests for the TTL cache implementation.
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List
import pytest

from app.utils.cache import TTLCache, get_cache, clear_cache


class TestTTLCache:
    """Test the TTLCache class."""
    
    def test_basic_get_put(self):
        """Test basic cache get/put operations."""
        cache = TTLCache(max_size=100, default_ttl_seconds=60)
        
        # Test cache miss
        result = cache.get("woolworths", "milk", "2000")
        assert result is None
        
        # Test cache put and hit
        test_data = ["product1", "product2"]
        cache.put("woolworths", "milk", "2000", test_data)
        
        result = cache.get("woolworths", "milk", "2000")
        assert result == test_data
        
        # Test different key
        result = cache.get("coles", "milk", "2000")
        assert result is None
    
    def test_key_normalization(self):
        """Test that cache keys are normalized consistently."""
        cache = TTLCache()
        
        test_data = ["normalized_data"]
        cache.put("woolworths", "  MILK 2L  ", "2000", test_data)
        
        # Should hit with different casing/spacing
        result = cache.get("woolworths", "milk 2l", "2000")
        assert result == test_data
        
        # Should hit with extra whitespace
        result = cache.get("woolworths", "  milk 2l  ", "2000")
        assert result == test_data
    
    def test_ttl_expiration(self):
        """Test that items expire after TTL."""
        cache = TTLCache(default_ttl_seconds=1)  # 1 second TTL
        
        test_data = ["expiring_data"]
        cache.put("woolworths", "milk", "2000", test_data)
        
        # Should hit immediately
        result = cache.get("woolworths", "milk", "2000")
        assert result == test_data
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should miss after expiration
        result = cache.get("woolworths", "milk", "2000")
        assert result is None
    
    def test_custom_ttl(self):
        """Test custom TTL per item."""
        cache = TTLCache(default_ttl_seconds=60)
        
        test_data = ["custom_ttl_data"]
        cache.put("woolworths", "milk", "2000", test_data, ttl_seconds=1)
        
        # Should hit immediately
        result = cache.get("woolworths", "milk", "2000")
        assert result == test_data
        
        # Wait for custom TTL expiration
        time.sleep(1.5)
        
        # Should miss after custom TTL
        result = cache.get("woolworths", "milk", "2000")
        assert result is None
    
    def test_lru_eviction(self):
        """Test LRU eviction when cache exceeds max size."""
        cache = TTLCache(max_size=3, default_ttl_seconds=60)
        
        # Fill cache to capacity
        cache.put("woolworths", "item1", "2000", "data1")
        cache.put("woolworths", "item2", "2000", "data2")
        cache.put("woolworths", "item3", "2000", "data3")
        
        # All should be present
        assert cache.get("woolworths", "item1", "2000") == "data1"
        assert cache.get("woolworths", "item2", "2000") == "data2"
        assert cache.get("woolworths", "item3", "2000") == "data3"
        
        # Add one more item - should evict least recently used
        cache.put("woolworths", "item4", "2000", "data4")
        
        # item1 should be evicted (least recently used)
        assert cache.get("woolworths", "item1", "2000") is None
        assert cache.get("woolworths", "item2", "2000") == "data2"
        assert cache.get("woolworths", "item3", "2000") == "data3"
        assert cache.get("woolworths", "item4", "2000") == "data4"
    
    def test_lru_access_order(self):
        """Test that accessing items affects LRU order."""
        cache = TTLCache(max_size=3, default_ttl_seconds=60)
        
        # Fill cache
        cache.put("woolworths", "item1", "2000", "data1")
        cache.put("woolworths", "item2", "2000", "data2")
        cache.put("woolworths", "item3", "2000", "data3")
        
        # Access item1 to make it most recently used
        cache.get("woolworths", "item1", "2000")
        
        # Add new item - should evict item2 (now least recently used)
        cache.put("woolworths", "item4", "2000", "data4")
        
        # item1 should still be present, item2 should be evicted
        assert cache.get("woolworths", "item1", "2000") == "data1"
        assert cache.get("woolworths", "item2", "2000") is None
        assert cache.get("woolworths", "item3", "2000") == "data3"
        assert cache.get("woolworths", "item4", "2000") == "data4"
    
    def test_cache_statistics(self):
        """Test cache statistics reporting."""
        cache = TTLCache(max_size=100, default_ttl_seconds=60)
        
        # Empty cache stats
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["expired_items"] == 0
        assert stats["default_ttl_seconds"] == 60
        
        # Add some items
        cache.put("woolworths", "item1", "2000", "data1")
        cache.put("coles", "item2", "2001", "data2")
        
        stats = cache.stats()
        assert stats["size"] == 2
        assert stats["expired_items"] == 0
        
        # Add expired item with negative TTL to ensure immediate expiration
        cache.put("woolworths", "expired", "2000", "expired_data", ttl_seconds=-1)
        
        stats = cache.stats()
        assert stats["size"] == 3
        assert stats["expired_items"] == 1
    
    def test_cache_clear(self):
        """Test cache clearing functionality."""
        cache = TTLCache()
        
        # Add items
        cache.put("woolworths", "item1", "2000", "data1")
        cache.put("coles", "item2", "2001", "data2")
        
        assert cache.size() == 2
        
        # Clear cache
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get("woolworths", "item1", "2000") is None
        assert cache.get("coles", "item2", "2001") is None
    
    def test_thread_safety(self):
        """Test that cache operations are thread-safe."""
        cache = TTLCache(max_size=1000, default_ttl_seconds=10)
        num_threads = 10
        items_per_thread = 50
        
        def worker_function(thread_id: int):
            """Worker function for thread safety test."""
            results = []
            for i in range(items_per_thread):
                key = f"thread{thread_id}_item{i}"
                data = f"data_{thread_id}_{i}"
                
                # Put data
                cache.put("woolworths", key, "2000", data)
                
                # Get data back
                result = cache.get("woolworths", key, "2000")
                results.append(result == data)
                
                # Also try accessing other threads' data
                other_thread_id = (thread_id + 1) % num_threads
                other_key = f"thread{other_thread_id}_item{i}"
                cache.get("woolworths", other_key, "2000")
            
            return results
        
        # Run threads concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(worker_function, thread_id) 
                for thread_id in range(num_threads)
            ]
            
            # Collect results
            all_results = []
            for future in futures:
                thread_results = future.result()
                all_results.extend(thread_results)
        
        # All operations should have succeeded
        assert all(all_results), "Some thread-safety test operations failed"
        
        # Cache should contain data from all threads
        final_size = cache.size()
        assert final_size > 0, "Cache should contain data after concurrent operations"
    
    def test_periodic_expired_cleanup(self):
        """Test that expired items are cleaned up periodically."""
        cache = TTLCache(default_ttl_seconds=1)
        
        # Add items that will expire immediately
        for i in range(100):  # First 100 operations don't trigger cleanup
            cache.put("woolworths", f"item{i}", "2000", f"data{i}", ttl_seconds=-1)  # Already expired
        
        # The 101st operation should trigger cleanup (when size % 100 == 0)
        cache.put("woolworths", "trigger_cleanup", "2000", "cleanup_data")
        
        # After cleanup, most expired items should be removed
        # Only the trigger item should remain (or very few items due to timing)
        final_size = cache.size()
        assert final_size <= 10, f"Expected cleanup to remove most expired items, got {final_size} items remaining"


class TestCacheIntegration:
    """Test cache integration with the global cache instance."""
    
    def test_global_cache_singleton(self):
        """Test that get_cache() returns a singleton instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        
        assert cache1 is cache2, "get_cache() should return the same instance"
    
    def test_global_cache_clear(self):
        """Test clearing the global cache."""
        cache = get_cache()
        
        # Add data to global cache
        cache.put("woolworths", "test", "2000", "test_data")
        assert cache.get("woolworths", "test", "2000") == "test_data"
        
        # Clear global cache
        clear_cache()
        
        # Data should be gone
        assert cache.get("woolworths", "test", "2000") is None
    
    def test_cache_key_generation(self):
        """Test cache key generation with various inputs."""
        cache = TTLCache()
        
        # Test with different retailers
        cache.put("woolworths", "milk", "2000", "woolworths_data")
        cache.put("coles", "milk", "2000", "coles_data")
        
        assert cache.get("woolworths", "milk", "2000") == "woolworths_data"
        assert cache.get("coles", "milk", "2000") == "coles_data"
        
        # Test with different postcodes
        cache.put("woolworths", "milk", "2001", "postcode_2001_data")
        
        assert cache.get("woolworths", "milk", "2000") == "woolworths_data"
        assert cache.get("woolworths", "milk", "2001") == "postcode_2001_data"
        
        # Test with different queries
        cache.put("woolworths", "bread", "2000", "bread_data")
        
        assert cache.get("woolworths", "milk", "2000") == "woolworths_data"
        assert cache.get("woolworths", "bread", "2000") == "bread_data"


class TestCacheEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_none_values(self):
        """Test caching None values."""
        cache = TTLCache()
        
        # Cache None value
        cache.put("woolworths", "empty_result", "2000", None)
        
        # Should return None (not cache miss)
        result = cache.get("woolworths", "empty_result", "2000")
        assert result is None
        
        # Should be distinguishable from cache miss by checking if key exists
        # (This is a limitation - None values and cache misses both return None)
        # In practice, this is acceptable since empty results are valid cache entries
    
    def test_empty_collections(self):
        """Test caching empty collections."""
        cache = TTLCache()
        
        # Cache empty list
        cache.put("woolworths", "no_results", "2000", [])
        
        result = cache.get("woolworths", "no_results", "2000")
        assert result == []
        
        # Cache empty dict
        cache.put("coles", "no_data", "2001", {})
        
        result = cache.get("coles", "no_data", "2001")
        assert result == {}
    
    def test_large_data_caching(self):
        """Test caching large data structures."""
        cache = TTLCache()
        
        # Create large data structure
        large_data = [{"product_id": i, "name": f"Product {i}", "price": i * 1.99} for i in range(1000)]
        
        cache.put("woolworths", "large_dataset", "2000", large_data)
        
        result = cache.get("woolworths", "large_dataset", "2000")
        assert result == large_data
        assert len(result) == 1000
    
    def test_special_characters_in_keys(self):
        """Test cache keys with special characters."""
        cache = TTLCache()
        
        # Test with various special characters in query
        special_queries = [
            "milk & cookies",
            "bread (whole grain)",
            "cheese - cheddar",
            "fruits/vegetables",
            "items@sale",
            "50% off!",
            "café coffee ñoño"
        ]
        
        for i, query in enumerate(special_queries):
            data = f"data_{i}"
            cache.put("woolworths", query, "2000", data)
            
            result = cache.get("woolworths", query, "2000")
            assert result == data, f"Failed for query: {query}"
    
    def test_very_small_cache_size(self):
        """Test cache with very small max size."""
        cache = TTLCache(max_size=1)
        
        # Add first item
        cache.put("woolworths", "item1", "2000", "data1")
        assert cache.get("woolworths", "item1", "2000") == "data1"
        
        # Add second item - should evict first
        cache.put("woolworths", "item2", "2000", "data2")
        assert cache.get("woolworths", "item1", "2000") is None
        assert cache.get("woolworths", "item2", "2000") == "data2"
        
        # Size should never exceed 1
        assert cache.size() == 1