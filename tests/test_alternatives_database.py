"""
Tests for alternative products database functionality.
"""
import pytest
import tempfile
import os
from datetime import date, timedelta
from unittest.mock import patch

# Import database functions
import sys
sys.path.append('.')
from app.utils.database import (
    log_alternative_products, 
    get_alternative_products, 
    get_database_stats,
    init_database,
    get_db_connection,
    clear_all_price_history
)


class TestAlternativesDatabase:
    """Test alternative products database functionality."""
    
    def setup_method(self):
        """Setup test database."""
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        
        # Patch the DB_PATH to use our temporary database
        self.original_db_path = None
        import app.utils.database as db_module
        self.original_db_path = db_module.DB_PATH
        db_module.DB_PATH = self.temp_db.name
        
        # Initialize the test database
        init_database()
    
    def teardown_method(self):
        """Cleanup test database."""
        # Restore original DB path
        if self.original_db_path:
            import app.utils.database as db_module
            db_module.DB_PATH = self.original_db_path
        
        # Remove temporary database file
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_log_alternative_products_success(self):
        """Test successful logging of alternative products."""
        alternatives = [
            {
                'name': 'Woolworths Full Cream Milk 2L',
                'price': 4.50,
                'was': 5.00,
                'onSale': True,
                'promoText': 'Save 50c',
                'url': 'https://woolworths.com.au/product/123',
                'matchScore': 0.95
            },
            {
                'name': 'Woolworths Skim Milk 2L',
                'price': 4.20,
                'was': None,
                'onSale': False,
                'promoText': None,
                'url': 'https://woolworths.com.au/product/456',
                'matchScore': 0.75
            }
        ]
        
        result = log_alternative_products('milk 2L', 'woolworths', alternatives)
        assert result is True
    
    def test_log_alternative_products_missing_params(self):
        """Test logging with missing parameters."""
        result = log_alternative_products('', 'woolworths', [])
        assert result is False
        
        result = log_alternative_products('milk', '', [])
        assert result is False
        
        result = log_alternative_products('milk', 'woolworths', [])
        assert result is False
    
    def test_get_alternative_products(self):
        """Test retrieving alternative products."""
        # First, log some alternatives
        alternatives = [
            {
                'name': 'Product A',
                'price': 10.00,
                'was': 12.00,
                'onSale': True,
                'promoText': 'On Sale',
                'url': 'https://example.com/a',
                'matchScore': 0.9
            },
            {
                'name': 'Product B',
                'price': 8.50,
                'was': None,
                'onSale': False,
                'promoText': None,
                'url': 'https://example.com/b',
                'matchScore': 0.7
            }
        ]
        
        log_alternative_products('test product', 'woolworths', alternatives)
        
        # Retrieve the alternatives
        retrieved = get_alternative_products('test product', 'woolworths')
        
        assert len(retrieved) == 2
        assert retrieved[0]['product_name'] == 'product a'  # normalized
        assert retrieved[0]['price'] == 10.00
        assert retrieved[0]['on_sale'] is True
        assert retrieved[0]['match_score'] == 0.9
        assert retrieved[0]['rank_position'] == 1
        
        assert retrieved[1]['product_name'] == 'product b'  # normalized
        assert retrieved[1]['price'] == 8.50
        assert retrieved[1]['on_sale'] is False
        assert retrieved[1]['match_score'] == 0.7
        assert retrieved[1]['rank_position'] == 2
    
    def test_get_alternative_products_with_retailer_filter(self):
        """Test retrieving alternatives with retailer filter."""
        alternatives = [
            {'name': 'Product X', 'price': 5.00, 'onSale': False, 'matchScore': 0.8}
        ]
        
        # Log for different retailers
        log_alternative_products('bread', 'woolworths', alternatives)
        log_alternative_products('bread', 'coles', alternatives)
        
        # Retrieve for specific retailer
        woolworths_results = get_alternative_products('bread', 'woolworths')
        coles_results = get_alternative_products('bread', 'coles')
        all_results = get_alternative_products('bread')
        
        assert len(woolworths_results) == 1
        assert len(coles_results) == 1
        assert len(all_results) == 2
        
        assert woolworths_results[0]['retailer'] == 'woolworths'
        assert coles_results[0]['retailer'] == 'coles'
    
    def test_get_alternative_products_with_date_filter(self):
        """Test retrieving alternatives with date filter."""
        alternatives = [
            {'name': 'Old Product', 'price': 10.00, 'onSale': False, 'matchScore': 0.8}
        ]
        
        # Log alternatives with old date
        old_date = date.today() - timedelta(days=40)
        log_alternative_products('old search', 'woolworths', alternatives, old_date)
        
        # Log alternatives with recent date
        log_alternative_products('recent search', 'woolworths', alternatives)
        
        # Test different date ranges
        results_30_days = get_alternative_products('old search', 'woolworths', 30)
        results_45_days = get_alternative_products('old search', 'woolworths', 45)
        
        assert len(results_30_days) == 0  # Old data filtered out
        assert len(results_45_days) == 1  # Old data included
        
        results_recent = get_alternative_products('recent search', 'woolworths', 30)
        assert len(results_recent) == 1  # Recent data included
    
    def test_get_database_stats_with_alternatives(self):
        """Test database stats include alternatives data."""
        # Initially empty
        stats = get_database_stats()
        assert stats['alternatives']['total_records'] == 0
        assert stats['alternatives']['unique_queries'] == 0
        assert stats['alternatives']['unique_products'] == 0
        
        # Add some alternatives
        alternatives = [
            {'name': 'Product A', 'price': 5.00, 'onSale': False, 'matchScore': 0.9},
            {'name': 'Product B', 'price': 6.00, 'onSale': True, 'matchScore': 0.8}
        ]
        
        log_alternative_products('query1', 'woolworths', alternatives)
        log_alternative_products('query2', 'coles', alternatives[:1])
        
        # Check updated stats
        stats = get_database_stats()
        assert stats['alternatives']['total_records'] == 3
        assert stats['alternatives']['unique_queries'] == 2
        assert stats['alternatives']['unique_products'] == 2  # Product A and B (normalized)
    
    def test_replace_existing_alternatives(self):
        """Test that logging alternatives replaces existing ones for same query/retailer/date."""
        # Log initial alternatives
        initial_alternatives = [
            {'name': 'Initial Product', 'price': 10.00, 'onSale': False, 'matchScore': 0.8}
        ]
        log_alternative_products('test query', 'woolworths', initial_alternatives)
        
        # Verify initial state
        results = get_alternative_products('test query', 'woolworths')
        assert len(results) == 1
        assert results[0]['product_name'] == 'initial product'
        
        # Log new alternatives (should replace the old ones)
        new_alternatives = [
            {'name': 'New Product A', 'price': 8.00, 'onSale': True, 'matchScore': 0.9},
            {'name': 'New Product B', 'price': 9.00, 'onSale': False, 'matchScore': 0.7}
        ]
        log_alternative_products('test query', 'woolworths', new_alternatives)
        
        # Verify replacement
        results = get_alternative_products('test query', 'woolworths')
        assert len(results) == 2
        assert results[0]['product_name'] == 'new product a'
        assert results[1]['product_name'] == 'new product b'
        
        # Verify rank positions are correct
        assert results[0]['rank_position'] == 1
        assert results[1]['rank_position'] == 2
    
    def test_clear_all_data_includes_alternatives(self):
        """Test that clearing all data removes alternatives too."""
        # Add some alternatives
        alternatives = [
            {'name': 'Test Product', 'price': 5.00, 'onSale': False, 'matchScore': 0.8}
        ]
        log_alternative_products('test', 'woolworths', alternatives)
        
        # Verify data exists
        results = get_alternative_products('test', 'woolworths')
        assert len(results) == 1
        
        stats = get_database_stats()
        assert stats['alternatives']['total_records'] == 1
        
        # Clear all data
        success = clear_all_price_history()
        assert success is True
        
        # Verify data is cleared
        results = get_alternative_products('test', 'woolworths')
        assert len(results) == 0
        
        stats = get_database_stats()
        assert stats['alternatives']['total_records'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])