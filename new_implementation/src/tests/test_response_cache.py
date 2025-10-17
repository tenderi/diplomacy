"""
Comprehensive unit tests for Response Cache module.

Tests cover ResponseCache class including TTL expiration, LRU eviction,
thread safety, cache statistics, and error handling.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from typing import Dict, Any, List
import json

from server.response_cache import ResponseCache, cached_response, invalidate_cache, get_cache_stats, clear_response_cache


class TestResponseCache:
    """Test ResponseCache class."""
    
    @pytest.fixture
    def cache(self):
        """Create ResponseCache instance for testing."""
        return ResponseCache(default_ttl=60, max_size=10)
    
    @pytest.fixture
    def cache_short_ttl(self):
        """Create ResponseCache with short TTL for testing expiration."""
        return ResponseCache(default_ttl=1, max_size=5)
    
    def test_cache_initialization(self, cache):
        """Test cache initialization."""
        assert cache.default_ttl == 60
        assert cache.max_size == 10
        assert cache.hit_count == 0
        assert cache.miss_count == 0
        assert len(cache.cache) == 0
        assert len(cache.access_times) == 0
    
    def test_set_and_get_basic(self, cache):
        """Test basic set and get operations."""
        endpoint = "test_endpoint"
        params = {"param1": "value1"}
        data = {"result": "test_data"}
        
        # Set data
        cache.set(endpoint, params, data)
        
        # Get data
        result = cache.get(endpoint, params)
        
        assert result == data
        assert cache.hit_count == 1
        assert cache.miss_count == 0
    
    def test_get_nonexistent_key(self, cache):
        """Test getting non-existent key."""
        result = cache.get("nonexistent", {"param": "value"})
        
        assert result is None
        assert cache.hit_count == 0
        assert cache.miss_count == 1
    
    def test_get_expired_entry(self, cache_short_ttl):
        """Test getting expired entry."""
        endpoint = "test_endpoint"
        params = {"param": "value"}
        data = {"result": "test_data"}
        
        # Set data
        cache_short_ttl.set(endpoint, params, data)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Try to get expired data
        result = cache_short_ttl.get(endpoint, params)
        
        assert result is None
        assert cache_short_ttl.miss_count == 1
    
    def test_set_with_custom_ttl(self, cache):
        """Test setting data with custom TTL."""
        endpoint = "test_endpoint"
        params = {"param": "value"}
        data = {"result": "test_data"}
        custom_ttl = 30
        
        cache.set(endpoint, params, data, ttl=custom_ttl)
        
        # Verify data is accessible
        result = cache.get(endpoint, params)
        assert result == data
    
    def test_key_generation_consistency(self, cache):
        """Test that key generation is consistent."""
        endpoint = "test_endpoint"
        params = {"param1": "value1", "param2": "value2"}
        
        key1 = cache._generate_key(endpoint, params)
        key2 = cache._generate_key(endpoint, params)
        
        assert key1 == key2
        
        # Test with different parameter order (should be same)
        params_reordered = {"param2": "value2", "param1": "value1"}
        key3 = cache._generate_key(endpoint, params_reordered)
        
        assert key1 == key3
    
    def test_key_generation_different_params(self, cache):
        """Test that different parameters generate different keys."""
        endpoint = "test_endpoint"
        params1 = {"param1": "value1"}
        params2 = {"param1": "value2"}
        
        key1 = cache._generate_key(endpoint, params1)
        key2 = cache._generate_key(endpoint, params2)
        
        assert key1 != key2
    
    def test_invalidate_by_pattern(self, cache):
        """Test cache invalidation by pattern."""
        # Set multiple entries
        cache.set("endpoint1", {"param": "value1"}, {"data": "1"})
        cache.set("endpoint1", {"param": "value2"}, {"data": "2"})
        cache.set("endpoint2", {"param": "value1"}, {"data": "3"})
        
        # Invalidate all endpoint1 entries
        cache.invalidate_pattern("endpoint1")
        
        # Verify endpoint1 entries are gone
        assert cache.get("endpoint1", {"param": "value1"}) is None
        assert cache.get("endpoint1", {"param": "value2"}) is None
        
        # Verify endpoint2 entry still exists
        assert cache.get("endpoint2", {"param": "value1"}) == {"data": "3"}
    
    def test_invalidate_by_pattern_with_params(self, cache):
        """Test cache invalidation by pattern with specific parameters."""
        # Set multiple entries
        cache.set("endpoint1", {"param1": "value1", "param2": "value2"}, {"data": "1"})
        cache.set("endpoint1", {"param1": "value1", "param2": "value3"}, {"data": "2"})
        cache.set("endpoint1", {"param1": "value2", "param2": "value2"}, {"data": "3"})
        
        # Invalidate entries with param1=value1
        cache.invalidate("endpoint1", {"param1": "value1"})
        
        # Verify specific entries are gone
        assert cache.get("endpoint1", {"param1": "value1", "param2": "value2"}) is None
        assert cache.get("endpoint1", {"param1": "value1", "param2": "value3"}) is None
        
        # Verify other entry still exists
        assert cache.get("endpoint1", {"param1": "value2", "param2": "value2"}) == {"data": "3"}
    
    def test_clear_all(self, cache):
        """Test clearing all cache entries."""
        # Set multiple entries
        cache.set("endpoint1", {"param": "value1"}, {"data": "1"})
        cache.set("endpoint2", {"param": "value2"}, {"data": "2"})
        
        # Clear all
        cache.clear()
        
        # Verify all entries are gone
        assert cache.get("endpoint1", {"param": "value1"}) is None
        assert cache.get("endpoint2", {"param": "value2"}) is None
        assert len(cache.cache) == 0
        assert len(cache.access_times) == 0
    
    def test_lru_eviction(self, cache):
        """Test LRU eviction when max_size is reached."""
        # Set entries up to max_size
        for i in range(10):  # max_size is 10
            cache.set(f"endpoint{i}", {"param": f"value{i}"}, {"data": f"data{i}"})
        
        # Verify all entries are present
        for i in range(10):
            result = cache.get(f"endpoint{i}", {"param": f"value{i}"})
            assert result == {"data": f"data{i}"}
        
        # Add one more entry (should trigger LRU eviction)
        cache.set("endpoint10", {"param": "value10"}, {"data": "data10"})
        
        # Verify cache size is still max_size
        assert len(cache.cache) == 10
        
        # Verify oldest entry was evicted (endpoint0)
        assert cache.get("endpoint0", {"param": "value0"}) is None
        
        # Verify newest entry is present
        assert cache.get("endpoint10", {"param": "value10"}) == {"data": "data10"}
    
    def test_access_time_update(self, cache):
        """Test that access times are updated on get operations."""
        endpoint = "test_endpoint"
        params = {"param": "value"}
        data = {"result": "test_data"}
        
        # Set data
        cache.set(endpoint, params, data)
        
        # Get initial access time
        key = cache._generate_key(endpoint, params)
        initial_time = cache.access_times[key]
        
        # Wait a bit
        time.sleep(0.1)
        
        # Get data again
        cache.get(endpoint, params)
        
        # Verify access time was updated
        updated_time = cache.access_times[key]
        assert updated_time > initial_time
    
    def test_cache_statistics(self, cache):
        """Test cache statistics tracking."""
        # Initial stats
        assert cache.hit_count == 0
        assert cache.miss_count == 0
        
        # Set and get data (hit)
        cache.set("endpoint", {"param": "value"}, {"data": "test"})
        cache.get("endpoint", {"param": "value"})
        
        assert cache.hit_count == 1
        assert cache.miss_count == 0
        
        # Get non-existent data (miss)
        cache.get("nonexistent", {"param": "value"})
        
        assert cache.hit_count == 1
        assert cache.miss_count == 1
        
        # Get same data again (hit)
        cache.get("endpoint", {"param": "value"})
        
        assert cache.hit_count == 2
        assert cache.miss_count == 1
    
    def test_get_cache_stats(self, cache):
        """Test get_cache_stats function."""
        # Set some data
        cache.set("endpoint1", {"param": "value1"}, {"data": "1"})
        cache.set("endpoint2", {"param": "value2"}, {"data": "2"})
        
        # Generate some hits and misses
        cache.get("endpoint1", {"param": "value1"})  # hit
        cache.get("nonexistent", {"param": "value"})  # miss
        
        # Get stats
        stats = cache.get_stats()
        
        assert "hit_count" in stats
        assert "miss_count" in stats
        assert "total_requests" in stats
        assert "hit_rate" in stats
        assert "cache_size" in stats
        assert "max_size" in stats
        
        assert stats["hit_count"] == 1
        assert stats["miss_count"] == 1
        assert stats["total_requests"] == 2
        assert stats["hit_rate"] == 0.5
        assert stats["cache_size"] == 2
        assert stats["max_size"] == 10


class TestResponseCacheThreadSafety:
    """Test thread safety of ResponseCache."""
    
    @pytest.fixture
    def cache(self):
        """Create ResponseCache instance."""
        return ResponseCache(default_ttl=60, max_size=100)
    
    def test_concurrent_set_operations(self, cache):
        """Test concurrent set operations."""
        def set_data(thread_id: int):
            for i in range(10):
                cache.set(f"endpoint_{thread_id}", {"param": f"value_{i}"}, {"data": f"data_{thread_id}_{i}"})
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=set_data, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all data was set correctly
        for thread_id in range(5):
            for i in range(10):
                result = cache.get(f"endpoint_{thread_id}", {"param": f"value_{i}"})
                assert result == {"data": f"data_{thread_id}_{i}"}
    
    def test_concurrent_get_operations(self, cache):
        """Test concurrent get operations."""
        # Set up test data
        for i in range(10):
            cache.set("endpoint", {"param": f"value_{i}"}, {"data": f"data_{i}"})
        
        results = []
        
        def get_data():
            for i in range(10):
                result = cache.get("endpoint", {"param": f"value_{i}"})
                results.append(result)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=get_data)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all results are correct
        assert len(results) == 50  # 5 threads * 10 gets each
        for result in results:
            assert result is not None
            assert "data" in result
    
    def test_concurrent_set_and_get(self, cache):
        """Test concurrent set and get operations."""
        def set_data():
            for i in range(20):
                cache.set("endpoint", {"param": f"value_{i}"}, {"data": f"data_{i}"})
        
        def get_data():
            for i in range(20):
                cache.get("endpoint", {"param": f"value_{i}"})
        
        # Create threads
        set_thread = threading.Thread(target=set_data)
        get_thread = threading.Thread(target=get_data)
        
        # Start threads
        set_thread.start()
        get_thread.start()
        
        # Wait for completion
        set_thread.join()
        get_thread.join()
        
        # Verify cache is in consistent state
        assert len(cache.cache) <= cache.max_size
        assert len(cache.access_times) <= cache.max_size


class TestCachedResponseDecorator:
    """Test cached_response decorator."""
    
    @pytest.fixture
    def cache(self):
        """Create ResponseCache instance."""
        return ResponseCache(default_ttl=60, max_size=10)
    
    def test_cached_response_basic(self, cache):
        """Test basic cached_response functionality."""
        call_count = 0
        
        @cached_response(ttl=60)
        def test_function(param1: str, param2: int) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"result": f"{param1}_{param2}", "call_count": call_count}
        
        # First call
        result1 = test_function("test", 123)
        assert result1["result"] == "test_123"
        assert result1["call_count"] == 1
        assert call_count == 1
        
        # Second call (should be cached)
        result2 = test_function("test", 123)
        assert result2["result"] == "test_123"
        assert result2["call_count"] == 1  # Should be cached value
        assert call_count == 1  # Function should not be called again
        
        # Different parameters (should not be cached)
        result3 = test_function("test", 456)
        assert result3["result"] == "test_456"
        assert result3["call_count"] == 2
        assert call_count == 2
    
    def test_cached_response_with_custom_ttl(self, cache):
        """Test cached_response with custom TTL."""
        call_count = 0
        
        @cached_response(ttl=1)  # 1 second TTL
        def test_function(param: str) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"result": param, "call_count": call_count}
        
        # First call
        result1 = test_function("test")
        assert call_count == 1
        
        # Immediate second call (should be cached)
        result2 = test_function("test")
        assert call_count == 1
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Third call (should call function again)
        result3 = test_function("test")
        assert call_count == 2
    
    def test_cached_response_with_exception(self, cache):
        """Test cached_response with exceptions."""
        call_count = 0
        
        @cached_response(ttl=60)
        def test_function(param: str) -> str:
            nonlocal call_count
            call_count += 1
            if param == "error":
                raise ValueError("Test error")
            return f"result_{param}"
        
        # Call with error
        with pytest.raises(ValueError):
            test_function("error")
        
        assert call_count == 1
        
        # Call again with error (should not be cached)
        with pytest.raises(ValueError):
            test_function("error")
        
        assert call_count == 2
        
        # Call with success
        result = test_function("success")
        assert result == "result_success"
        assert call_count == 3
        
        # Call again with success (should be cached)
        result = test_function("success")
        assert result == "result_success"
        assert call_count == 3


class TestCacheUtilityFunctions:
    """Test cache utility functions."""
    
    @pytest.fixture
    def cache(self):
        """Create ResponseCache instance."""
        return ResponseCache(default_ttl=60, max_size=10)
    
    def test_invalidate_cache_function(self):
        """Test invalidate_cache function."""
        from server.response_cache import _response_cache
        
        # Clear the global cache first
        _response_cache.clear()
        
        # Set some data
        _response_cache.set("endpoint1", {"param": "value1"}, {"data": "1"})
        _response_cache.set("endpoint2", {"param": "value2"}, {"data": "2"})
        
        # Invalidate using function
        invalidate_cache("endpoint1")
        
        # Verify endpoint1 is invalidated
        assert _response_cache.get("endpoint1", {"param": "value1"}) is None
        
        # Verify endpoint2 still exists
        assert _response_cache.get("endpoint2", {"param": "value2"}) == {"data": "2"}
    
    def test_clear_response_cache_function(self):
        """Test clear_response_cache function."""
        from server.response_cache import _response_cache
        
        # Clear the global cache first
        _response_cache.clear()
        
        # Set some data
        _response_cache.set("endpoint1", {"param": "value1"}, {"data": "1"})
        _response_cache.set("endpoint2", {"param": "value2"}, {"data": "2"})
        
        # Clear using function
        clear_response_cache()
        
        # Verify all data is cleared
        assert _response_cache.get("endpoint1", {"param": "value1"}) is None
        assert _response_cache.get("endpoint2", {"param": "value2"}) is None
        assert len(_response_cache.cache) == 0


class TestResponseCacheEdgeCases:
    """Test edge cases and error handling in ResponseCache."""
    
    @pytest.fixture
    def cache(self):
        """Create ResponseCache instance."""
        return ResponseCache(default_ttl=60, max_size=10)
    
    def test_set_with_none_data(self, cache):
        """Test setting None data."""
        cache.set("endpoint", {"param": "value"}, None)
        
        result = cache.get("endpoint", {"param": "value"})
        assert result is None
    
    def test_set_with_empty_data(self, cache):
        """Test setting empty data."""
        cache.set("endpoint", {"param": "value"}, {})
        
        result = cache.get("endpoint", {"param": "value"})
        assert result == {}
    
    def test_set_with_large_data(self, cache):
        """Test setting large data."""
        large_data = {"data": "x" * 10000}  # 10KB string
        
        cache.set("endpoint", {"param": "value"}, large_data)
        
        result = cache.get("endpoint", {"param": "value"})
        assert result == large_data
    
    def test_set_with_complex_data(self, cache):
        """Test setting complex nested data."""
        complex_data = {
            "level1": {
                "level2": {
                    "level3": [1, 2, 3, {"nested": "value"}]
                }
            },
            "list": [1, 2, 3],
            "tuple": (1, 2, 3)
        }
        
        cache.set("endpoint", {"param": "value"}, complex_data)
        
        result = cache.get("endpoint", {"param": "value"})
        assert result == complex_data
    
    def test_invalidate_nonexistent_pattern(self, cache):
        """Test invalidating non-existent pattern."""
        # Should not raise error
        cache.invalidate("nonexistent_endpoint")
        
        # Verify cache is still functional
        cache.set("endpoint", {"param": "value"}, {"data": "test"})
        result = cache.get("endpoint", {"param": "value"})
        assert result == {"data": "test"}
    
    def test_get_with_none_params(self, cache):
        """Test getting with None parameters."""
        cache.set("endpoint", None, {"data": "test"})
        
        result = cache.get("endpoint", None)
        assert result == {"data": "test"}
    
    def test_set_with_zero_ttl(self, cache):
        """Test setting with zero TTL."""
        cache.set("endpoint", {"param": "value"}, {"data": "test"}, ttl=0)
        
        # Should be immediately expired
        result = cache.get("endpoint", {"param": "value"})
        assert result is None
    
    def test_set_with_negative_ttl(self, cache):
        """Test setting with negative TTL."""
        cache.set("endpoint", {"param": "value"}, {"data": "test"}, ttl=-1)
        
        # Should be immediately expired
        result = cache.get("endpoint", {"param": "value"})
        assert result is None
