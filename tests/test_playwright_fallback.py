"""
Tests for Playwright fallback functionality.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import List

from app.adapters.playwright_fallback import (
    PlaywrightFallbackAdapter, 
    WoolworthsPlaywrightAdapter,
    ColesPlaywrightAdapter,
    PLAYWRIGHT_AVAILABLE
)
from app.models import ProductResult

pytestmark = pytest.mark.asyncio


class TestPlaywrightAvailability:
    """Test Playwright availability detection."""
    
    def test_playwright_import_detection(self):
        """Test that Playwright import is detected correctly."""
        # This test will pass or fail based on whether Playwright is actually installed
        # In a real environment, this helps verify the fallback detection works
        assert isinstance(PLAYWRIGHT_AVAILABLE, bool)
    
    def test_adapter_creation_without_playwright(self):
        """Test adapter creation when Playwright is not available."""
        with patch('app.adapters.playwright_fallback.PLAYWRIGHT_AVAILABLE', False):
            adapter = WoolworthsPlaywrightAdapter()
            assert adapter.retailer_name == "woolworths"
            assert adapter.base_url == "https://www.woolworths.com.au"


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestPlaywrightFallbackAdapter:
    """Test the base Playwright fallback adapter."""
    
    async def test_context_manager_protocol(self):
        """Test async context manager protocol."""
        adapter = WoolworthsPlaywrightAdapter()
        
        # Mock playwright to avoid actual browser launch
        with patch('app.adapters.playwright_fallback.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright.return_value.start.return_value = mock_pw_instance
            mock_pw_instance.chromium.launch.return_value = mock_browser
            
            async with adapter as ctx:
                assert ctx is adapter
                assert adapter.playwright is mock_pw_instance
                assert adapter.browser is mock_browser
    
    async def test_context_manager_cleanup(self):
        """Test proper cleanup in async context manager."""
        adapter = WoolworthsPlaywrightAdapter()
        
        with patch('app.adapters.playwright_fallback.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright.return_value.start.return_value = mock_pw_instance
            mock_pw_instance.chromium.launch.return_value = mock_browser
            
            async with adapter:
                pass
            
            # Verify cleanup was called
            mock_browser.close.assert_called_once()
            mock_pw_instance.stop.assert_called_once()
    
    def test_extract_price_valid_formats(self):
        """Test price extraction from various text formats."""
        adapter = WoolworthsPlaywrightAdapter()
        
        test_cases = [
            ("$4.50", 4.50),
            ("4.50", 4.50),
            ("$4", 4.00),
            ("4", 4.00),
            ("$1,234.56", 1234.56),
            ("Price: $3.99", 3.99),
            ("", None),
            ("No price", None),
            ("Free", None)
        ]
        
        for price_text, expected in test_cases:
            result = adapter._extract_price(price_text)
            assert result == expected, f"Failed for '{price_text}': expected {expected}, got {result}"
    
    async def test_create_page_settings(self):
        """Test that page creation applies correct settings."""
        adapter = WoolworthsPlaywrightAdapter()
        
        with patch('app.adapters.playwright_fallback.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            
            mock_playwright.return_value.start.return_value = mock_pw_instance
            mock_pw_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            async with adapter:
                page = await adapter._create_page()
                
                # Verify page settings were applied
                mock_page.set_user_agent.assert_called_once()
                mock_page.set_viewport_size.assert_called_once_with({"width": 1920, "height": 1080})
                mock_page.set_default_timeout.assert_called_once()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestWoolworthsPlaywrightAdapter:
    """Test Woolworths-specific Playwright adapter."""
    
    async def test_search_with_mocked_browser(self):
        """Test search method with mocked browser interaction."""
        adapter = WoolworthsPlaywrightAdapter()
        
        # Mock the entire browser interaction
        with patch.object(adapter, '_create_page') as mock_create_page, \
             patch.object(adapter, '_wait_for_results') as mock_wait_results, \
             patch.object(adapter, '_extract_woolworths_product') as mock_extract:
            
            # Mock page and elements
            mock_page = AsyncMock()
            mock_create_page.return_value = mock_page
            
            # Mock product elements
            mock_elements = [AsyncMock(), AsyncMock()]
            mock_page.query_selector_all.return_value = mock_elements
            
            # Mock product extraction
            mock_products = [
                ProductResult(
                    name="Test Milk 2L",
                    price=4.50,
                    was=5.00,
                    promoText="Save 50c",
                    promoFlag=True,
                    url="https://woolworths.com.au/product/123",
                    inStock=None,
                    retailer="woolworths"
                )
            ]
            mock_extract.side_effect = mock_products
            
            # Mock browser context
            adapter.browser = AsyncMock()
            
            results = await adapter.search("milk 2L", "2000")
            
            # Verify navigation and extraction
            mock_page.goto.assert_called_once()
            mock_wait_results.assert_called_once()
            mock_page.query_selector_all.assert_called()
            mock_extract.assert_called()
            mock_page.close.assert_called_once()
            
            assert len(results) == 1
            assert results[0].name == "Test Milk 2L"
            assert results[0].retailer == "woolworths"
    
    async def test_extract_woolworths_product_complete(self):
        """Test product extraction with complete product data."""
        adapter = WoolworthsPlaywrightAdapter()
        
        # Mock product element with all data
        mock_element = AsyncMock()
        mock_name_element = AsyncMock()
        mock_price_element = AsyncMock()
        mock_was_element = AsyncMock()
        mock_promo_element = AsyncMock()
        mock_link_element = AsyncMock()
        
        # Configure mock returns
        mock_element.query_selector.side_effect = lambda selector: {
            '[data-testid="product-title"]': mock_name_element,
            '[data-testid="price-current"]': mock_price_element,
            '[data-testid="price-was"]': mock_was_element,
            '[data-testid="product-badge"]': mock_promo_element,
            'a[href]': mock_link_element
        }.get(selector)
        
        mock_name_element.inner_text.return_value = "Woolworths Full Cream Milk 2L"
        mock_price_element.inner_text.return_value = "$4.50"
        mock_was_element.inner_text.return_value = "$5.00"
        mock_promo_element.inner_text.return_value = "Save 50c"
        mock_link_element.get_attribute.return_value = "/product/123456"
        
        # Mock sale detection
        with patch.object(adapter, '_is_on_sale_from_elements', return_value=True):
            product = await adapter._extract_woolworths_product(mock_element, "milk 2L")
        
        assert product is not None
        assert product.name == "Woolworths Full Cream Milk 2L"
        assert product.price == 4.50
        assert product.was == 5.00
        assert product.promoText == "Save 50c"
        assert product.promoFlag is True
        assert product.url == "https://www.woolworths.com.au/product/123456"
        assert product.retailer == "woolworths"
    
    async def test_extract_woolworths_product_minimal(self):
        """Test product extraction with minimal product data."""
        adapter = WoolworthsPlaywrightAdapter()
        
        # Mock product element with minimal data
        mock_element = AsyncMock()
        mock_name_element = AsyncMock()
        
        mock_element.query_selector.side_effect = lambda selector: {
            '[data-testid="product-title"]': mock_name_element if 'title' in selector else None,
        }.get(selector, None)
        
        mock_name_element.inner_text.return_value = "Basic Product"
        
        with patch.object(adapter, '_is_on_sale_from_elements', return_value=False):
            product = await adapter._extract_woolworths_product(mock_element, "product")
        
        assert product is not None
        assert product.name == "Basic Product"
        assert product.price is None
        assert product.was is None
        assert product.promoText is None
        assert product.promoFlag is False
        assert product.url is None
        assert product.retailer == "woolworths"
    
    async def test_extract_woolworths_product_no_name(self):
        """Test product extraction when no name is found."""
        adapter = WoolworthsPlaywrightAdapter()
        
        # Mock element with no name
        mock_element = AsyncMock()
        mock_element.query_selector.return_value = None
        
        product = await adapter._extract_woolworths_product(mock_element, "query")
        
        assert product is None


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestColesPlaywrightAdapter:
    """Test Coles-specific Playwright adapter."""
    
    async def test_search_url_generation(self):
        """Test that Coles search URL is generated correctly."""
        adapter = ColesPlaywrightAdapter()
        
        with patch.object(adapter, '_create_page') as mock_create_page, \
             patch.object(adapter, '_wait_for_results'), \
             patch.object(adapter, '_extract_coles_product', return_value=None):
            
            mock_page = AsyncMock()
            mock_create_page.return_value = mock_page
            mock_page.query_selector_all.return_value = []
            
            # Mock browser context
            adapter.browser = AsyncMock()
            
            await adapter.search("test query", "2000")
            
            # Verify URL format
            expected_url_part = "https://www.coles.com.au/search?q=test+query"
            actual_call = mock_page.goto.call_args[0][0]
            assert actual_call.startswith(expected_url_part)
    
    async def test_extract_coles_product_with_sale(self):
        """Test Coles product extraction with sale information."""
        adapter = ColesPlaywrightAdapter()
        
        # Mock product element
        mock_element = AsyncMock()
        mock_name_element = AsyncMock()
        mock_price_element = AsyncMock()
        mock_was_element = AsyncMock()
        
        mock_element.query_selector.side_effect = lambda selector: {
            '[data-testid="product-name"]': mock_name_element,
            '[data-testid="price"]': mock_price_element,
            '[data-testid="was-price"]': mock_was_element,
        }.get(selector)
        
        mock_name_element.inner_text.return_value = "Coles Brand Milk 2L"
        mock_price_element.inner_text.return_value = "$4.20"
        mock_was_element.inner_text.return_value = "$4.80"
        
        with patch.object(adapter, '_is_on_sale_from_elements', return_value=False):
            product = await adapter._extract_coles_product(mock_element, "milk")
        
        assert product is not None
        assert product.name == "Coles Brand Milk 2L"
        assert product.price == 4.20
        assert product.was == 4.80
        assert product.promoFlag is True  # Should be True because was > price
        assert product.retailer == "coles"


class TestPlaywrightIntegration:
    """Test integration of Playwright fallback with main adapters."""
    
    @patch('app.adapters.woolworths.PLAYWRIGHT_FALLBACK_AVAILABLE', True)
    @patch('app.adapters.woolworths.settings.ENABLE_PLAYWRIGHT_FALLBACK', True)
    async def test_woolworths_fallback_on_api_failure(self):
        """Test that Woolworths adapter uses Playwright fallback when API fails."""
        from app.adapters.woolworths import WoolworthsAdapter
        
        adapter = WoolworthsAdapter()
        
        # Mock API failure
        with patch.object(adapter, '_retry_request', return_value=None), \
             patch('app.adapters.woolworths.WoolworthsPlaywrightAdapter') as mock_playwright_adapter:
            
            # Mock Playwright adapter
            mock_instance = AsyncMock()
            mock_playwright_adapter.return_value.__aenter__.return_value = mock_instance
            mock_instance.search.return_value = [
                ProductResult(
                    name="Playwright Result",
                    price=4.50,
                    retailer="woolworths"
                )
            ]
            
            results = await adapter.search("milk", "2000")
            
            # Verify Playwright was called as fallback
            mock_playwright_adapter.assert_called_once()
            mock_instance.search.assert_called_once_with("milk", "2000")
            
            assert len(results) == 1
            assert results[0].name == "Playwright Result"
    
    @patch('app.adapters.coles.PLAYWRIGHT_FALLBACK_AVAILABLE', True)
    @patch('app.adapters.coles.settings.ENABLE_PLAYWRIGHT_FALLBACK', True)
    async def test_coles_fallback_on_api_failure(self):
        """Test that Coles adapter uses Playwright fallback when API fails."""
        from app.adapters.coles import ColesAdapter
        
        adapter = ColesAdapter()
        
        # Mock API failure
        with patch.object(adapter, '_retry_request', return_value=None), \
             patch('app.adapters.coles.ColesPlaywrightAdapter') as mock_playwright_adapter:
            
            # Mock Playwright adapter
            mock_instance = AsyncMock()
            mock_playwright_adapter.return_value.__aenter__.return_value = mock_instance
            mock_instance.search.return_value = [
                ProductResult(
                    name="Coles Playwright Result",
                    price=3.80,
                    retailer="coles"
                )
            ]
            
            results = await adapter.search("bread", "2001")
            
            # Verify Playwright was called as fallback
            mock_playwright_adapter.assert_called_once()
            mock_instance.search.assert_called_once_with("bread", "2001")
            
            assert len(results) == 1
            assert results[0].name == "Coles Playwright Result"
    
    @patch('app.adapters.woolworths.settings.ENABLE_PLAYWRIGHT_FALLBACK', False)
    async def test_no_fallback_when_disabled(self):
        """Test that Playwright fallback is not used when disabled."""
        # Import after patching settings
        from app.adapters.woolworths import WoolworthsAdapter
        
        adapter = WoolworthsAdapter()
        # Clear cache to ensure fresh API call
        adapter.cache.clear()
        
        with patch.object(adapter, '_retry_request', return_value=None), \
             patch('app.adapters.woolworths.WoolworthsPlaywrightAdapter') as mock_playwright_adapter:
            
            results = await adapter.search("milk_no_cache", "2000")
            
            # Verify Playwright was NOT called
            mock_playwright_adapter.assert_not_called()
            
            assert len(results) == 0  # Empty results when API fails and fallback disabled
    
    async def test_fallback_logs_appropriately(self):
        """Test that appropriate logs are generated during fallback."""
        with patch('app.adapters.woolworths.PLAYWRIGHT_FALLBACK_AVAILABLE', True), \
             patch('app.adapters.woolworths.settings.ENABLE_PLAYWRIGHT_FALLBACK', True):
            
            # Import after patching to ensure settings are applied
            from app.adapters.woolworths import WoolworthsAdapter
            
            adapter = WoolworthsAdapter()
            # Clear cache to ensure fresh API call
            adapter.cache.clear()
            
            with patch.object(adapter, '_retry_request', return_value=None), \
                 patch('app.adapters.woolworths.WoolworthsPlaywrightAdapter') as mock_playwright_adapter, \
                 patch('app.adapters.woolworths.logger') as mock_logger:
                
                # Mock successful Playwright fallback
                mock_instance = AsyncMock()
                mock_playwright_adapter.return_value.__aenter__.return_value = mock_instance
                mock_instance.search.return_value = [ProductResult(name="Test", retailer="woolworths")]
                
                await adapter.search("milk_unique_query", "2000")
                
                # Verify appropriate log messages - check if any call matches
                info_calls = [call for call in mock_logger.info.call_args_list]
                fallback_logged = any(
                    "API search failed" in str(call) and "attempting Playwright fallback" in str(call)
                    for call in info_calls
                )
                results_logged = any(
                    "Playwright fallback found" in str(call) and "products" in str(call)
                    for call in info_calls
                )
                
                assert fallback_logged, f"Expected fallback log not found in: {info_calls}"
                assert results_logged, f"Expected results log not found in: {info_calls}"


class TestPlaywrightErrorHandling:
    """Test error handling in Playwright fallback."""
    
    @patch('app.adapters.playwright_fallback.PLAYWRIGHT_AVAILABLE', False)
    async def test_search_when_playwright_unavailable(self):
        """Test search behavior when Playwright is not available."""
        adapter = WoolworthsPlaywrightAdapter()
        
        results = await adapter.search("milk", "2000")
        
        assert results == []
    
    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
    async def test_context_manager_without_playwright(self):
        """Test context manager when Playwright is not available."""
        adapter = WoolworthsPlaywrightAdapter()
        
        with patch('app.adapters.playwright_fallback.PLAYWRIGHT_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="Playwright not installed"):
                async with adapter:
                    pass
    
    async def test_fallback_error_logging(self):
        """Test that Playwright fallback errors are properly logged."""
        with patch('app.adapters.woolworths.PLAYWRIGHT_FALLBACK_AVAILABLE', True), \
             patch('app.adapters.woolworths.settings.ENABLE_PLAYWRIGHT_FALLBACK', True):
            
            # Import after patching to ensure settings are applied
            from app.adapters.woolworths import WoolworthsAdapter
            
            adapter = WoolworthsAdapter()
            # Clear cache to ensure fresh API call
            adapter.cache.clear()
            
            with patch.object(adapter, '_retry_request', return_value=None), \
                 patch('app.adapters.woolworths.WoolworthsPlaywrightAdapter') as mock_playwright_adapter, \
                 patch('app.adapters.woolworths.logger') as mock_logger:
                
                # Mock Playwright failure
                mock_playwright_adapter.return_value.__aenter__.side_effect = Exception("Browser launch failed")
                
                results = await adapter.search("milk_error_test", "2000")
                
                # Check if error was logged - look for any error call containing our message
                error_calls = [call for call in mock_logger.error.call_args_list]
                error_logged = any(
                    "Playwright fallback failed" in str(call) and "Browser launch failed" in str(call)
                    for call in error_calls
                )
                
                assert error_logged, f"Expected error log not found in: {error_calls}"
                assert results == []  # Should return empty results on fallback failure