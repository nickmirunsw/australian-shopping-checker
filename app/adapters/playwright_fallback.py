"""
Playwright-based web scraping fallback adapter for Woolworths only.
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Union
from urllib.parse import quote_plus

from .base import BaseAdapter
from ..models import ProductResult
from ..settings import settings
from ..utils.data_validation import validate_scraped_products

logger = logging.getLogger(__name__)

# Try to import playwright, make it optional
try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    Page = None
    Playwright = None
    logger.warning("Playwright not installed. Web scraping fallback unavailable.")


class PlaywrightFallbackAdapter(BaseAdapter):
    """
    Playwright-based web scraping adapter for product search fallback.
    """
    
    def __init__(self, retailer_name: str, base_url: str):
        self.retailer_name = retailer_name
        self.base_url = base_url
        self.playwright: Optional[Union[Playwright, Any]] = None
        self.browser: Optional[Union[Browser, Any]] = None
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.error(f"Playwright not available for {retailer_name} fallback adapter")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed")
        
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth settings to avoid detection
        self.browser = await self.playwright.chromium.launch(
            headless=settings.PLAYWRIGHT_HEADLESS,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security', 
                '--disable-features=VizDisplayCompositor',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--no-first-run',
                '--disable-default-apps'
            ]
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def search(self, query: str, postcode: str) -> List[ProductResult]:
        """
        Search for products using browser automation.
        
        This method is implemented by specific retailer adapters.
        """
        raise NotImplementedError("Subclasses must implement search method")
    
    async def _create_page(self):
        """Create a new browser page with common settings."""
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use async context manager.")
        
        page = await self.browser.new_page()
        
        # Set realistic headers to appear more like a real browser
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        # Set viewport for consistent rendering
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Set timeout
        page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)
        
        return page
    
    async def _wait_for_results(self, page, selector: str, timeout: int = 10000):
        """Wait for search results to appear."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            logger.warning(f"Timeout waiting for results selector '{selector}': {e}")
    
    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price from text string."""
        if not text:
            return None
        
        # Remove common currency symbols and whitespace
        clean_text = re.sub(r'[^\d.,]', '', text)
        
        # Handle different price formats
        price_match = re.search(r'(\d+(?:\.\d{2})?)', clean_text)
        if price_match:
            try:
                return float(price_match.group(1))
            except ValueError:
                pass
        
        return None
    
    def _is_on_sale_from_elements(self, product_element) -> bool:
        """Check if product appears to be on sale based on DOM elements."""
        # This would check for sale indicators in the HTML
        # Implementation depends on specific retailer's markup
        return False


class WoolworthsPlaywrightAdapter(PlaywrightFallbackAdapter):
    """Playwright adapter specifically for Woolworths."""
    
    def __init__(self):
        super().__init__("woolworths", "https://www.woolworths.com.au")
    
    async def search(self, query: str, postcode: str) -> List[ProductResult]:
        """Search Woolworths using browser automation."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return []
        
        logger.info(f"Using Playwright fallback for Woolworths search: '{query}' at {postcode}")
        
        try:
            page = await self._create_page()
            
            # Navigate to Woolworths search page
            search_url = f"{self.base_url}/shop/search/products?searchTerm={quote_plus(query)}"
            logger.debug(f"Navigating to: {search_url}")
            
            await page.goto(search_url)
            
            # Handle location popup if it appears
            try:
                location_popup = page.locator('[data-testid="postcode-popup"], .location-popup')
                if await location_popup.is_visible(timeout=3000):
                    logger.debug("Handling location popup")
                    postcode_input = page.locator('input[placeholder*="postcode"], input[data-testid*="postcode"]')
                    if await postcode_input.is_visible():
                        await postcode_input.fill(postcode)
                        await page.keyboard.press('Enter')
                        await page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug(f"No location popup or error handling it: {e}")
            
            # Wait for search results
            await self._wait_for_results(page, '.product-list, [data-testid="product"], .search-results')
            
            # Extract products
            products = []
            product_selectors = [
                '[data-testid="product-tile"]',
                '.product-tile',
                '.product-item',
                '.search-result-item'
            ]
            
            for selector in product_selectors:
                product_elements = await page.query_selector_all(selector)
                if product_elements:
                    logger.debug(f"Found {len(product_elements)} products with selector: {selector}")
                    for element in product_elements[:24]:  # Limit to first 24 results
                        product = await self._extract_woolworths_product(element, query)
                        if product:
                            products.append(product)
                    break
            
            await page.close()
            
            logger.info(f"Woolworths Playwright adapter found {len(products)} raw products")
            
            # Validate scraped products
            validated_products = validate_scraped_products(products, min_quality_score=0.6)
            
            logger.info(f"Woolworths Playwright adapter returning {len(validated_products)} validated products")
            return validated_products
            
        except Exception as e:
            logger.error(f"Error in Woolworths Playwright search: {e}")
            return []
    
    async def _extract_woolworths_product(self, product_element: Any, query: str) -> Optional[ProductResult]:
        """Extract product information from Woolworths product element."""
        try:
            # Woolworths-specific selectors
            name_selectors = [
                '[data-testid="product-title"]',
                '.product-title',
                'h3',
                '.title',
                '[data-testid="product-name"]'
            ]
            
            price_selectors = [
                '[data-testid="price-dollars"]',
                '.price-dollars',
                '.current-price',
                '.price'
            ]
            
            was_selectors = [
                '[data-testid="was-price"]',
                '.was-price',
                '.strikethrough-price'
            ]
            
            # Extract name
            name = None
            for selector in name_selectors:
                element = product_element.query_selector(selector)
                if element:
                    name = await element.inner_text()
                    break
            
            if not name:
                return None
            
            # Extract current price
            price = None
            for selector in price_selectors:
                element = product_element.query_selector(selector)
                if element:
                    price_text = await element.inner_text()
                    price = self._extract_price(price_text)
                    break
            
            # Extract was price
            was = None
            for selector in was_selectors:
                element = product_element.query_selector(selector)
                if element:
                    was_text = await element.inner_text()
                    was = self._extract_price(was_text)
                    break
            
            # Extract promo text
            promo_selectors = [
                '[data-testid="product-badge"]',
                '.product-badge',
                '.promotion-text',
                '.special-offer'
            ]
            
            promo_text = None
            for selector in promo_selectors:
                element = product_element.query_selector(selector)
                if element:
                    promo_text = await element.inner_text()
                    break
            
            # Extract URL
            url = None
            link_element = product_element.query_selector('a[href]')
            if link_element:
                relative_url = await link_element.get_attribute('href')
                if relative_url:
                    url = f"{self.base_url}{relative_url}" if relative_url.startswith('/') else relative_url
            
            is_on_sale = self._is_on_sale_from_elements(product_element) or (was is not None and price is not None and was > price)
            
            return ProductResult(
                name=name.strip(),
                price=price,
                was=was,
                promoText=promo_text.strip() if promo_text else None,
                promoFlag=is_on_sale,
                url=url,
                inStock=None,  # Hard to determine from search results
                retailer="woolworths"
            )
            
        except Exception as e:
            logger.error(f"Error extracting Woolworths product: {e}")
            return None