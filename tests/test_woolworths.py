import pytest
import respx
import httpx
from app.adapters.woolworths import WoolworthsAdapter


class TestWoolworthsAdapter:
    """Test cases for Woolworths adapter."""
    
    def test_adapter_creation(self):
        """Test that adapter can be created."""
        adapter = WoolworthsAdapter()
        assert adapter is not None
        assert adapter.base_url == "https://www.woolworths.com.au"
        assert "User-Agent" in adapter.headers
    
    def test_headers_contain_required_fields(self):
        """Test that headers contain required fields for browser simulation."""
        adapter = WoolworthsAdapter()
        required_headers = ["User-Agent", "Accept", "Referer", "Origin"]
        for header in required_headers:
            assert header in adapter.headers
    
    def test_is_on_sale_with_promo_flag(self):
        """Test is_on_sale with promo flag set."""
        adapter = WoolworthsAdapter()
        product_data = {"isOnSpecial": True}
        assert adapter.is_on_sale(product_data) is True
    
    def test_is_on_sale_with_price_comparison(self):
        """Test is_on_sale with was price higher than current."""
        adapter = WoolworthsAdapter()
        product_data = {
            "pricing": {
                "now": 4.50,
                "was": 5.00
            }
        }
        assert adapter.is_on_sale(product_data) is True
    
    def test_is_on_sale_with_promo_text(self):
        """Test is_on_sale with promo text present."""
        adapter = WoolworthsAdapter()
        product_data = {"promoCallout": "Save $0.50"}
        assert adapter.is_on_sale(product_data) is True
    
    def test_is_on_sale_with_badges(self):
        """Test is_on_sale with promotional badges."""
        adapter = WoolworthsAdapter()
        product_data = {"badges": ["Special", "Limited Time"]}
        assert adapter.is_on_sale(product_data) is True
    
    def test_is_not_on_sale(self):
        """Test is_on_sale returns False when no promotional indicators."""
        adapter = WoolworthsAdapter()
        product_data = {
            "pricing": {
                "now": 5.00,
                "was": 4.50  # Price went up, not on sale
            }
        }
        assert adapter.is_on_sale(product_data) is False
    
    def test_parse_product_complete(self):
        """Test parsing a complete product with all fields."""
        adapter = WoolworthsAdapter()
        product_data = {
            "displayName": "Woolworths Full Cream Milk 2L",
            "stockcode": 123456,
            "pricing": {
                "now": 2.50,
                "was": 3.20
            },
            "promoCallout": "Save 70c",
            "isOnSpecial": True,
            "isAvailable": True,
            "urlFriendlyName": "woolworths-full-cream-milk-2l"
        }
        
        result = adapter._parse_product(product_data)
        
        assert result.name == "Woolworths Full Cream Milk 2L"
        assert result.price == 2.50
        assert result.was == 3.20
        assert result.promoText == "Save 70c"
        assert result.promoFlag is True
        assert result.url == "https://www.woolworths.com.au/shop/productdetails/123456"
        assert result.inStock is True
        assert result.retailer == "woolworths"
    
    def test_parse_product_minimal(self):
        """Test parsing a product with minimal fields."""
        adapter = WoolworthsAdapter()
        product_data = {
            "name": "Basic Product",
            "pricing": {"now": 1.99}
        }
        
        result = adapter._parse_product(product_data)
        
        assert result.name == "Basic Product"
        assert result.price == 1.99
        assert result.was is None
        assert result.promoText is None
        assert result.promoFlag is False
        assert result.url is None
        assert result.inStock is None
        assert result.retailer == "woolworths"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_successful_response(self):
        """Test successful search with mocked API response."""
        mock_response = {
            "products": [
                {
                    "displayName": "Pauls Full Cream Milk 2L",
                    "stockcode": 123456,
                    "pricing": {
                        "now": 4.50,
                        "was": 5.00
                    },
                    "promoCallout": "Save $0.50",
                    "isOnSpecial": True,
                    "isAvailable": True
                },
                {
                    "displayName": "Devondale Full Cream Milk 2L", 
                    "stockcode": 789012,
                    "pricing": {
                        "now": 4.20
                    },
                    "isAvailable": True
                }
            ]
        }
        
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        adapter = WoolworthsAdapter()
        results = await adapter.search("milk 2L", "2000")
        
        assert len(results) == 2
        
        # Check first product (on sale)
        assert results[0].name == "Pauls Full Cream Milk 2L"
        assert results[0].price == 4.50
        assert results[0].was == 5.00
        assert results[0].promoText == "Save $0.50"
        assert results[0].promoFlag is True
        
        # Check second product (not on sale)
        assert results[1].name == "Devondale Full Cream Milk 2L"
        assert results[1].price == 4.20
        assert results[1].promoFlag is False
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_no_results(self):
        """Test search with no results."""
        mock_response = {"products": []}
        
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        adapter = WoolworthsAdapter()
        results = await adapter.search("nonexistentproduct", "2000")
        
        assert results == []
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_api_error(self):
        """Test search with API error."""
        # Mock all endpoints to return 500
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://www.woolworths.com.au/api/ui/Search/products").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://www.woolworths.com.au/apis/search/products").mock(
            return_value=httpx.Response(500)
        )
        
        adapter = WoolworthsAdapter()
        results = await adapter.search("milk 2L", "2000")
        
        assert results == []