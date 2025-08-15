import httpx
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from .base import BaseAdapter
from ..models import ProductResult
from ..settings import settings
from ..utils.cache import get_cache

logger = logging.getLogger(__name__)

# Import Playwright fallback if available
try:
    from .playwright_fallback import WoolworthsPlaywrightAdapter
    PLAYWRIGHT_FALLBACK_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_FALLBACK_AVAILABLE = False
    logger.debug("Playwright fallback not available for Woolworths")


class WoolworthsAdapter(BaseAdapter):
    """Adapter for Woolworths product search."""
    
    def __init__(self):
        self.base_url = "https://www.woolworths.com.au"
        self.api_base = "https://www.woolworths.com.au/apis/ui"
        self.retailer_name = "woolworths"
        self.cache = get_cache()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-AU,en;q=0.9",
            "Referer": "https://www.woolworths.com.au/shop/search/products",
            "Origin": "https://www.woolworths.com.au"
        }
    
    async def _retry_request(self, client: httpx.AsyncClient, url: str, params: Dict[str, Any], query: str, postcode: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Make HTTP request with exponential backoff retry and structured logging."""
        return await self._retry_request_with_backoff(
            client=client,
            url=url,
            params=params,
            query=query,
            postcode=postcode,
            max_retries=max_retries,
            timeout=30.0,
            backoff_factor=1.0
        )
    
    def is_on_sale(self, product_data: Dict[str, Any]) -> bool:
        """
        Check if a product is on sale based on the rule:
        promoFlag is true OR (was and price and price < was) OR promoText exists.
        """
        # Check promo flag
        if product_data.get("isOnSpecial") or product_data.get("isPromotional"):
            return True
            
        # Check price comparison
        pricing = product_data.get("pricing", {})
        current_price = pricing.get("now") or pricing.get("comparable")
        was_price = pricing.get("was")
        
        if current_price and was_price and current_price < was_price:
            return True
            
        # Check promo text
        promo_callout = product_data.get("promoCallout") or product_data.get("promotionCallout")
        badges = product_data.get("badges", [])
        
        if promo_callout or (badges and len(badges) > 0):
            return True
            
        return False
    
    def _parse_product(self, product_data: Dict[str, Any]) -> ProductResult:
        """Parse Woolworths product data into ProductResult."""
        # Extract name using actual API field names
        raw_name = product_data.get("DisplayName") or product_data.get("Name", "Unknown Product")
        
        # Extract size information for better product differentiation
        size_info = product_data.get("PackageSize") or product_data.get("Size") or ""
        
        # Combine name with size if size is available and not already in name
        name = raw_name
        if size_info and size_info.lower() not in raw_name.lower():
            name = f"{raw_name} {size_info}".strip()
        
        # Add stockcode for absolute uniqueness (critical for preventing mixing)
        stockcode = product_data.get("Stockcode")
        if stockcode:
            # Include stockcode in internal name for absolute differentiation
            # This ensures 60g and 140g versions are treated as completely different products
            name = f"{name} [WOW:{stockcode}]"
        
        # Extract pricing using actual API field names
        price = product_data.get("Price")
        was = product_data.get("WasPrice") if product_data.get("WasPrice", 0) != product_data.get("Price", 0) else None
        
        # Extract promo information
        promo_flag = product_data.get("IsOnSpecial", False) or product_data.get("IsHalfPrice", False)
        promo_text = None
        
        # Look for savings amount
        savings = product_data.get("SavingsAmount", 0) or 0
        if savings > 0:
            promo_text = f"Save ${savings:.2f}"
        
        # Extract URL
        url_friendly = product_data.get("UrlFriendlyName")
        url = None
        if stockcode:
            url = f"https://www.woolworths.com.au/shop/productdetails/{stockcode}/{url_friendly}"
        
        # Extract stock info
        in_stock = product_data.get("IsAvailable") or product_data.get("IsInStock")
        
        # Create display name (without stockcode) for user-facing results
        display_name = raw_name
        if size_info and size_info.lower() not in raw_name.lower():
            display_name = f"{raw_name} {size_info}".strip()
        
        return ProductResult(
            name=name,  # Internal name with stockcode for uniqueness
            display_name=display_name,  # Clean name for display
            price=price,
            was=was,
            promoText=promo_text,
            promoFlag=promo_flag,
            url=url,
            inStock=in_stock,
            retailer="woolworths",
            stockcode=stockcode  # Store for reference
        )
    
    async def search(self, query: str, postcode: str) -> List[ProductResult]:
        """
        Search for products on Woolworths using their public API with caching.
        """
        start_time = time.time()
        
        # Check cache first
        cached_result = self.cache.get(self.retailer_name, query, postcode)
        if cached_result is not None:
            total_time = time.time() - start_time
            logger.info(
                "Cache hit for search",
                extra={
                    "query": query,
                    "postcode": postcode,
                    "retailer": self.retailer_name,
                    "cache_hit": True,
                    "latency": round(total_time, 3),
                    "results_count": len(cached_result)
                }
            )
            return cached_result
        
        # Cache miss - perform actual search
        logger.info(
            "Cache miss, performing API search",
            extra={
                "query": query,
                "postcode": postcode,
                "retailer": self.retailer_name,
                "cache_hit": False
            }
        )
        
        # Use the confirmed working endpoint only
        endpoints_to_try = [
            f"{self.api_base}/Search/products"  # This one works!
        ]
        
        params = {
            "searchTerm": query,
            "postcode": postcode,
            "pageNumber": 1,
            "pageSize": 36,  # Maximum allowed by Woolworths API
            "sortType": "Relevance"
        }
        
        results = []
        api_succeeded = False
        
        async with httpx.AsyncClient() as client:
            for endpoint in endpoints_to_try:
                logger.debug(f"Trying endpoint: {endpoint}")
                data = await self._retry_request(client, endpoint, params, query, postcode)
                
                if data:
                    try:
                        # Handle the actual Woolworths API response structure
                        products_list = data.get("Products", [])
                        
                        if products_list:
                            for product_group in products_list:
                                # Each item in Products array has a nested Products array
                                nested_products = product_group.get("Products", [])
                                for product_data in nested_products:
                                    try:
                                        result = self._parse_product(product_data)
                                        results.append(result)
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to parse product: {e}",
                                            extra={
                                                "query": query,
                                                "postcode": postcode,
                                                "retailer": self.retailer_name,
                                                "parse_error": str(e)
                                            }
                                        )
                                        continue
                            
                            api_succeeded = True
                            break  # Found results, stop trying other endpoints
                            
                    except Exception as e:
                        logger.error(
                            f"Failed to parse response from {endpoint}: {e}",
                            extra={
                                "query": query,
                                "postcode": postcode,
                                "retailer": self.retailer_name,
                                "endpoint": endpoint,
                                "parse_error": str(e)
                            }
                        )
                        continue
        
        # If API failed and Playwright fallback is enabled, try web scraping
        if not api_succeeded and not results and settings.ENABLE_PLAYWRIGHT_FALLBACK and PLAYWRIGHT_FALLBACK_AVAILABLE:
            logger.info(
                f"API search failed for {query}, attempting Playwright fallback",
                extra={
                    "query": query,
                    "postcode": postcode,
                    "retailer": self.retailer_name,
                    "fallback": "playwright"
                }
            )
            
            try:
                async with WoolworthsPlaywrightAdapter() as playwright_adapter:
                    playwright_results = await playwright_adapter.search(query, postcode)
                    results.extend(playwright_results)
                    
                    logger.info(
                        f"Playwright fallback found {len(playwright_results)} products",
                        extra={
                            "query": query,
                            "postcode": postcode,
                            "retailer": self.retailer_name,
                            "fallback_results": len(playwright_results)
                        }
                    )
            except Exception as e:
                logger.error(
                    f"Playwright fallback failed: {e}",
                    extra={
                        "query": query,
                        "postcode": postcode,
                        "retailer": self.retailer_name,
                        "fallback_error": str(e)
                    }
                )
        
        # Cache the results (even if empty)
        self.cache.put(self.retailer_name, query, postcode, results)
        
        total_time = time.time() - start_time
        logger.info(
            f"Search completed",
            extra={
                "query": query,
                "postcode": postcode,
                "retailer": self.retailer_name,
                "cache_hit": False,
                "latency": round(total_time, 3),
                "results_count": len(results)
            }
        )
        
        return results
    
    async def find_closest_store(self, postcode: str) -> Optional[Dict[str, Any]]:
        """
        Find the closest Woolworths store to a given postcode.
        
        Returns store information including name, address, and distance.
        """
        try:
            # Try different Woolworths store locator API endpoints
            endpoints_to_try = [
                f"{self.base_url}/api/v1/stores/search",
                f"{self.api_base}/stores/search", 
                f"{self.api_base}/store/locator",
                f"{self.base_url}/apis/ui/stores/search"
            ]
            
            # Try different parameter variations
            param_variations = [
                {"postcode": postcode, "limit": 1, "orderBy": "distance"},
                {"postCode": postcode, "maxResults": 1, "sortBy": "distance"},
                {"searchTerm": postcode, "limit": 1},
                {"query": postcode, "maxItems": 1}
            ]
            
            async with httpx.AsyncClient() as client:
                for store_url in endpoints_to_try:
                    for params in param_variations:
                        try:
                            logger.debug(f"Trying store endpoint: {store_url} with params: {params}")
                            response = await client.get(
                                store_url,
                                params=params,
                                headers=self.headers,
                                timeout=10.0
                            )
                            
                            logger.debug(f"Store API response: {response.status_code}")
                            
                            if response.status_code == 200:
                                data = response.json()
                                logger.debug(f"Store API data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                                
                                # Check if we have stores in various possible response formats
                                stores = (data.get('stores', []) or 
                                         data.get('Stores', []) or
                                         data.get('results', []) or
                                         data.get('data', []) or
                                         (data.get('Store', {}).get('stores', []) if data.get('Store') else []))
                                
                                if stores:
                                    # Get the first (closest) store
                                    store = stores[0]
                                    
                                    # Extract store information
                                    store_info = {
                                        "name": store.get('name', store.get('Name', store.get('storeName', 'Unknown Store'))),
                                        "address": self._format_store_address(store),
                                        "suburb": store.get('suburb', store.get('Suburb', '')),
                                        "state": store.get('state', store.get('State', '')),
                                        "postcode": store.get('postcode', store.get('Postcode', '')),
                                        "distance": store.get('distance', store.get('Distance', 0)),
                                        "phone": store.get('phone', store.get('PhoneNumber', '')),
                                        "trading_hours": store.get('tradingHours', store.get('TradingHours', {}))
                                    }
                                    
                                    logger.info(f"Found closest store for postcode {postcode}: {store_info['name']}")
                                    return store_info
                                    
                        except Exception as e:
                            logger.debug(f"Failed to get stores from {store_url}: {e}")
                            continue
                
                # If we get here, none of the endpoints worked - use fallback
                logger.warning(f"All store locator endpoints failed for postcode {postcode}, using fallback")
                return self._get_fallback_store_info(postcode)
                    
        except Exception as e:
            logger.error(f"Error finding closest store for postcode {postcode}: {e}")
            return None
    
    def _format_store_address(self, store: Dict[str, Any]) -> str:
        """Format store address from API response."""
        # Try different address field variations
        address_parts = []
        
        # Street address
        street = store.get('address', store.get('Address', ''))
        if street:
            address_parts.append(street)
        
        # Suburb
        suburb = store.get('suburb', store.get('Suburb', ''))
        if suburb:
            address_parts.append(suburb)
        
        # State and postcode
        state = store.get('state', store.get('State', ''))
        postcode = store.get('postcode', store.get('Postcode', ''))
        if state and postcode:
            address_parts.append(f"{state} {postcode}")
        elif state:
            address_parts.append(state)
        elif postcode:
            address_parts.append(str(postcode))
        
        return ', '.join(address_parts) if address_parts else 'Address not available'
    
    def _get_fallback_store_info(self, postcode: str) -> Dict[str, Any]:
        """Fallback store information based on major Australian postcodes."""
        # Map postcodes to major city areas with representative store info
        postcode_to_area = {
            # NSW - Sydney
            "2000": {"area": "Sydney CBD", "state": "NSW", "store": "Woolworths Town Hall"},
            "2001": {"area": "Sydney CBD", "state": "NSW", "store": "Woolworths Town Hall"}, 
            "2010": {"area": "Surry Hills", "state": "NSW", "store": "Woolworths Surry Hills"},
            "2050": {"area": "Camperdown", "state": "NSW", "store": "Woolworths Camperdown"},
            "2060": {"area": "North Sydney", "state": "NSW", "store": "Woolworths North Sydney"},
            "2100": {"area": "Northern Beaches", "state": "NSW", "store": "Woolworths Brookvale"},
            "2150": {"area": "Parramatta", "state": "NSW", "store": "Woolworths Parramatta"},
            "2200": {"area": "Bankstown", "state": "NSW", "store": "Woolworths Bankstown"},
            
            # VIC - Melbourne  
            "3000": {"area": "Melbourne CBD", "state": "VIC", "store": "Woolworths Metro Melbourne Central"},
            "3001": {"area": "Melbourne CBD", "state": "VIC", "store": "Woolworths Metro Melbourne Central"},
            "3050": {"area": "Carlton", "state": "VIC", "store": "Woolworths Carlton"},
            "3121": {"area": "Richmond", "state": "VIC", "store": "Woolworths Richmond"},
            "3141": {"area": "South Yarra", "state": "VIC", "store": "Woolworths South Yarra"},
            "3181": {"area": "Prahran", "state": "VIC", "store": "Woolworths Prahran"},
            
            # QLD - Brisbane
            "4000": {"area": "Brisbane CBD", "state": "QLD", "store": "Woolworths Brisbane City"},
            "4001": {"area": "Brisbane CBD", "state": "QLD", "store": "Woolworths Brisbane City"},
            "4006": {"area": "Fortitude Valley", "state": "QLD", "store": "Woolworths Fortitude Valley"},
            "4101": {"area": "South Brisbane", "state": "QLD", "store": "Woolworths South Brisbane"},
            
            # WA - Perth
            "6000": {"area": "Perth CBD", "state": "WA", "store": "Woolworths Perth City"},
            "6001": {"area": "Perth CBD", "state": "WA", "store": "Woolworths Perth City"},
            "6050": {"area": "Mount Lawley", "state": "WA", "store": "Woolworths Mount Lawley"},
            
            # SA - Adelaide
            "5000": {"area": "Adelaide CBD", "state": "SA", "store": "Woolworths Adelaide City"},
            "5001": {"area": "Adelaide CBD", "state": "SA", "store": "Woolworths Adelaide City"},
            
            # TAS - Hobart
            "7000": {"area": "Hobart CBD", "state": "TAS", "store": "Woolworths Hobart City"},
            "7001": {"area": "Hobart CBD", "state": "TAS", "store": "Woolworths Hobart City"},
            
            # NT - Darwin
            "0800": {"area": "Darwin CBD", "state": "NT", "store": "Woolworths Darwin City"},
            "0801": {"area": "Darwin CBD", "state": "NT", "store": "Woolworths Darwin City"},
            
            # ACT - Canberra  
            "2600": {"area": "Canberra City", "state": "ACT", "store": "Woolworths Canberra City"},
            "2601": {"area": "Canberra City", "state": "ACT", "store": "Woolworths Canberra City"},
        }
        
        # Try exact postcode match first
        if postcode in postcode_to_area:
            area_info = postcode_to_area[postcode]
        else:
            # Try to match by postcode prefix (state-based fallback)
            prefix = postcode[:1]
            state_defaults = {
                "2": {"area": "Sydney Metro", "state": "NSW", "store": "Woolworths Sydney Metro Store"},
                "3": {"area": "Melbourne Metro", "state": "VIC", "store": "Woolworths Melbourne Metro Store"}, 
                "4": {"area": "Brisbane Metro", "state": "QLD", "store": "Woolworths Brisbane Metro Store"},
                "5": {"area": "Adelaide Metro", "state": "SA", "store": "Woolworths Adelaide Metro Store"},
                "6": {"area": "Perth Metro", "state": "WA", "store": "Woolworths Perth Metro Store"},
                "7": {"area": "Tasmania", "state": "TAS", "store": "Woolworths Tasmania Store"},
                "0": {"area": "Darwin Area", "state": "NT", "store": "Woolworths Darwin Area Store"},
            }
            area_info = state_defaults.get(prefix, {
                "area": "Regional Australia", 
                "state": "Unknown", 
                "store": "Woolworths Regional Store"
            })
        
        return {
            "name": area_info["store"],
            "address": f"{area_info['area']}, {area_info['state']} {postcode}",
            "suburb": area_info["area"],
            "state": area_info["state"],
            "postcode": postcode,
            "distance": 0,  # Unknown distance
            "phone": "1800 000 610",  # Woolworths customer service
            "trading_hours": {},
            "note": "Store information is estimated based on postcode area"
        }