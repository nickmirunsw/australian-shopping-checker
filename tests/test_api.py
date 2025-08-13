import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.adapters.base import BaseAdapter
from app.adapters.woolworths import WoolworthsAdapter
from app.adapters.coles import ColesAdapter
from app.models import ProductResult
from app.services.sale_checker import SaleChecker

client = TestClient(app)


class TestImports:
    """Test that all modules can be imported without network calls."""
    
    def test_base_adapter_import(self):
        """Test base adapter can be imported."""
        assert BaseAdapter is not None
    
    def test_woolworths_adapter_import(self):
        """Test Woolworths adapter can be imported and instantiated."""
        adapter = WoolworthsAdapter()
        assert isinstance(adapter, BaseAdapter)
    
    def test_coles_adapter_import(self):
        """Test Coles adapter can be imported and instantiated."""
        adapter = ColesAdapter()
        assert isinstance(adapter, BaseAdapter)
    
    def test_product_result_model(self):
        """Test ProductResult model can be created."""
        product = ProductResult(
            name="Test Product",
            price=4.50,
            was=5.00,
            promoText="Save $0.50",
            promoFlag=True,
            url="https://example.com/product",
            inStock=True,
            retailer="woolworths"
        )
        assert product.name == "Test Product"
        assert product.price == 4.50
        assert product.retailer == "woolworths"


class TestSaleChecker:
    """Test sale checker service functionality."""
    
    def test_sale_checker_creation(self):
        """Test sale checker can be instantiated."""
        checker = SaleChecker()
        assert checker is not None
        assert "woolworths" in checker.retailers
        assert "coles" in checker.retailers
    
    def test_normalize_text(self):
        """Test text normalization."""
        checker = SaleChecker()
        assert checker._normalize_text("  MILK   2L  ") == "milk 2l"
        assert checker._normalize_text("Weet-Bix Original") == "weet-bix original"
    
    def test_extract_size_info(self):
        """Test size information extraction."""
        checker = SaleChecker()
        
        # Test basic sizes
        text, size = checker._extract_size_info("milk 2L")
        assert "milk" in text
        assert "2l" in size
        
        text, size = checker._extract_size_info("weet-bix 500g")
        assert "weet-bix" in text
        assert "500g" in size
        
        # Test pack sizes
        text, size = checker._extract_size_info("coca cola 12 pack")
        assert "coca cola" in text
        assert "12pack" in size
    
    def test_calculate_match_score(self):
        """Test match score calculation."""
        checker = SaleChecker()
        
        product = ProductResult(
            name="Woolworths Full Cream Milk 2L",
            price=4.50,
            retailer="woolworths"
        )
        
        # Exact match should score high
        score = checker._calculate_match_score("milk 2L", product)
        assert score > 0.5
        
        # Unrelated product should score low
        unrelated_product = ProductResult(
            name="Chocolate Biscuits 300g",
            price=3.00,
            retailer="woolworths"
        )
        score = checker._calculate_match_score("milk 2L", unrelated_product)
        assert score < 0.3
    
    def test_select_best_match(self):
        """Test best match selection."""
        checker = SaleChecker()
        
        products = [
            ProductResult(name="Chocolate Milk 1L", price=3.50, retailer="woolworths"),
            ProductResult(name="Full Cream Milk 2L", price=4.50, retailer="woolworths"),
            ProductResult(name="Skim Milk 2L", price=4.20, retailer="woolworths"),
        ]
        
        best_match = checker._select_best_match("milk 2L", products)
        assert best_match is not None
        assert "2L" in best_match.name
    
    def test_select_best_match_empty_list(self):
        """Test best match selection with empty product list."""
        checker = SaleChecker()
        best_match = checker._select_best_match("milk", [])
        assert best_match is None


class TestAPIEndpoints:
    """Test FastAPI endpoints."""
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_check_endpoint_validation_empty_items(self):
        """Test validation for empty items."""
        response = client.post("/check", json={
            "items": "",
            "postcode": "2000"
        })
        assert response.status_code == 400
        assert "No items provided" in response.json()["detail"]
    
    def test_check_endpoint_validation_too_many_items(self):
        """Test validation for too many items."""
        items = ", ".join([f"item{i}" for i in range(15)])  # 15 items > 10 limit
        response = client.post("/check", json={
            "items": items,
            "postcode": "2000"
        })
        assert response.status_code == 400
        assert "Maximum 10 items" in response.json()["detail"]
    
    @patch('app.services.sale_checker.SaleChecker.check_items')
    def test_check_endpoint_success(self, mock_check_items):
        """Test successful check endpoint."""
        # Mock the sale checker response
        mock_check_items.return_value = {
            "results": [
                {
                    "input": "milk 2L",
                    "retailer": "woolworths",
                    "bestMatch": "Woolworths Full Cream Milk 2L",
                    "onSale": True,
                    "price": 4.50,
                    "was": 5.00,
                    "promoText": "Save 50c",
                    "url": "https://woolworths.com.au/product/123",
                    "inStock": True
                },
                {
                    "input": "milk 2L",
                    "retailer": "coles",
                    "bestMatch": "Coles Full Cream Milk 2L",
                    "onSale": False,
                    "price": 4.80,
                    "was": None,
                    "promoText": None,
                    "url": "https://coles.com.au/product/456",
                    "inStock": True
                }
            ],
            "postcode": "2000",
            "itemsChecked": 1
        }
        
        response = client.post("/check", json={
            "items": "milk 2L",
            "postcode": "2000"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["postcode"] == "2000"
        assert data["itemsChecked"] == 1
        assert len(data["results"]) == 2
        
        # Check Woolworths result
        woolworths_result = next(r for r in data["results"] if r["retailer"] == "woolworths")
        assert woolworths_result["bestMatch"] == "Woolworths Full Cream Milk 2L"
        assert woolworths_result["onSale"] is True
        assert woolworths_result["price"] == 4.50
        assert woolworths_result["was"] == 5.00
        
        # Check Coles result
        coles_result = next(r for r in data["results"] if r["retailer"] == "coles")
        assert coles_result["bestMatch"] == "Coles Full Cream Milk 2L"
        assert coles_result["onSale"] is False
        assert coles_result["price"] == 4.80
    
    def test_check_endpoint_multiple_items(self):
        """Test check endpoint with multiple items."""
        with patch('app.services.sale_checker.SaleChecker.check_items') as mock_check_items:
            mock_check_items.return_value = {
                "results": [
                    {
                        "input": "milk 2L",
                        "retailer": "woolworths",
                        "bestMatch": "Woolworths Milk 2L",
                        "onSale": True,
                        "price": 4.50,
                        "was": 5.00,
                        "promoText": "Special",
                        "url": None,
                        "inStock": True
                    },
                    {
                        "input": "bread",
                        "retailer": "woolworths", 
                        "bestMatch": "Woolworths White Bread",
                        "onSale": False,
                        "price": 2.50,
                        "was": None,
                        "promoText": None,
                        "url": None,
                        "inStock": True
                    }
                ],
                "postcode": "2101",
                "itemsChecked": 2
            }
            
            response = client.post("/check", json={
                "items": "milk 2L, bread",
                "postcode": "2101"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["itemsChecked"] == 2
            
            # Verify the mock was called with parsed items
            mock_check_items.assert_called_once_with(["milk 2L", "bread"], "2101")


class TestAPIIntegration:
    """Integration tests with real adapters (mocked network calls)."""
    
    @respx.mock
    def test_check_endpoint_integration(self):
        """Test check endpoint with mocked adapter responses."""
        # Mock Woolworths response
        woolworths_response = {
            "products": [{
                "displayName": "Woolworths Full Cream Milk 2L",
                "stockcode": 123456,
                "pricing": {"now": 4.50, "was": 5.00},
                "promoCallout": "Save 50c",
                "isOnSpecial": True,
                "isAvailable": True
            }]
        }
        
        # Mock Coles response (empty)
        coles_response = {"results": []}
        
        respx.get("https://www.woolworths.com.au/apis/ui/Search/products").mock(
            return_value=httpx.Response(200, json=woolworths_response)
        )
        respx.get("https://www.coles.com.au/api/products/search").mock(
            return_value=httpx.Response(200, json=coles_response)
        )
        respx.get("https://www.coles.com.au/api/search/products").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://www.coles.com.au/api/v1/products/search").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://www.coles.com.au/search/api/products").mock(
            return_value=httpx.Response(500)
        )
        
        response = client.post("/check", json={
            "items": "milk 2L",
            "postcode": "2000"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have results from both retailers
        assert len(data["results"]) == 2
        
        # Find Woolworths result
        woolworths_result = next(
            (r for r in data["results"] if r["retailer"] == "woolworths"), 
            None
        )
        assert woolworths_result is not None
        assert woolworths_result["bestMatch"] == "Woolworths Full Cream Milk 2L"
        assert woolworths_result["onSale"] is True
        
        # Find Coles result (should be empty)
        coles_result = next(
            (r for r in data["results"] if r["retailer"] == "coles"), 
            None
        )
        assert coles_result is not None
        assert coles_result["bestMatch"] is None
        assert coles_result["onSale"] is False