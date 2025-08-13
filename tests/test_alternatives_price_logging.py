"""
Test that alternatives are properly logged to price_history table.
"""
import pytest
import tempfile
import os
from datetime import date
from unittest.mock import patch, MagicMock

# Import required modules
import sys
sys.path.append('.')
from app.utils.database import (
    log_price_data, 
    log_alternative_products,
    get_database_stats,
    init_database,
    get_db_connection
)


class TestAlternativesPriceLogging:
    """Test that alternatives are logged as individual price records."""
    
    def setup_method(self):
        """Setup test database."""
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        
        # Patch the DB_PATH to use our temporary database
        import app.utils.database as db_module
        self.original_db_path = db_module.DB_PATH
        db_module.DB_PATH = self.temp_db.name
        
        # Initialize the test database
        init_database()
    
    def teardown_method(self):
        """Cleanup test database."""
        # Restore original DB path
        if hasattr(self, 'original_db_path'):
            import app.utils.database as db_module
            db_module.DB_PATH = self.original_db_path
        
        # Remove temporary database file
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_simulate_full_service_logging(self):
        """Test simulating what the SaleChecker service should do."""
        # Simulate a search result with best match + alternatives
        best_match = {
            'name': 'Woolworths Full Cream Milk 2L',
            'price': 4.50,
            'was': 5.00,
            'onSale': True,
            'url': 'https://woolworths.com/123'
        }
        
        alternatives = [
            {'name': 'Woolworths Skim Milk 2L', 'price': 4.20, 'was': None, 'onSale': False, 'url': 'https://woolworths.com/456', 'matchScore': 0.8},
            {'name': 'Woolworths Light Milk 2L', 'price': 4.30, 'was': 4.50, 'onSale': True, 'url': 'https://woolworths.com/789', 'matchScore': 0.7},
            {'name': 'Woolworths Organic Milk 2L', 'price': 6.50, 'was': None, 'onSale': False, 'url': 'https://woolworths.com/abc', 'matchScore': 0.6}
        ]
        
        # Log best match to price_history
        result = log_price_data(
            product_name=best_match['name'],
            retailer='woolworths',
            price=best_match['price'],
            was_price=best_match.get('was'),
            on_sale=best_match.get('onSale', False),
            url=best_match.get('url')
        )
        assert result is True
        
        # Log alternatives to alternatives table
        result = log_alternative_products('milk 2L', 'woolworths', alternatives)
        assert result is True
        
        # Log each alternative as individual price record (this is the key fix)
        for alternative in alternatives:
            if alternative.get('name') and alternative.get('price') is not None:
                result = log_price_data(
                    product_name=alternative['name'],
                    retailer='woolworths',
                    price=alternative['price'],
                    was_price=alternative.get('was'),
                    on_sale=alternative.get('onSale', False),
                    url=alternative.get('url')
                )
                assert result is True
        
        # Verify all products are in price_history
        stats = get_database_stats()
        assert stats['price_history']['total_records'] == 4  # 1 best match + 3 alternatives
        assert stats['price_history']['unique_products'] == 4  # All products are unique
        assert stats['alternatives']['total_records'] == 3  # 3 alternatives in alternatives table
        
        # Verify actual data in price_history table
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT product_name, price, on_sale 
                FROM price_history 
                ORDER BY product_name
            """)
            rows = cursor.fetchall()
            
            # Convert to list for easier testing
            products = [(row['product_name'], row['price'], bool(row['on_sale'])) for row in rows]
            
            expected_products = [
                ('woolworths full cream milk 2l', 4.50, True),    # best match
                ('woolworths light milk 2l', 4.30, True),        # alternative 1
                ('woolworths organic milk 2l', 6.50, False),     # alternative 2
                ('woolworths skim milk 2l', 4.20, False)         # alternative 3
            ]
            
            assert products == expected_products
    
    def test_alternatives_without_prices_not_logged(self):
        """Test that alternatives without prices are not logged to price_history."""
        alternatives = [
            {'name': 'Product With Price', 'price': 5.00, 'onSale': False, 'matchScore': 0.8},
            {'name': 'Product Without Price', 'price': None, 'onSale': False, 'matchScore': 0.7},
            {'name': 'Product With Zero Price', 'price': 0.00, 'onSale': False, 'matchScore': 0.6}
        ]
        
        # Log alternatives
        log_alternative_products('test query', 'woolworths', alternatives)
        
        # Log each alternative that has a valid price
        for alternative in alternatives:
            if alternative.get('name') and alternative.get('price') is not None:
                log_price_data(
                    product_name=alternative['name'],
                    retailer='woolworths',
                    price=alternative['price'],
                    was_price=alternative.get('was'),
                    on_sale=alternative.get('onSale', False),
                    url=alternative.get('url')
                )
        
        # Verify only products with valid prices are in price_history
        stats = get_database_stats()
        assert stats['price_history']['total_records'] == 2  # Product with price + product with zero price
        assert stats['alternatives']['total_records'] == 3   # All 3 alternatives in alternatives table
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT product_name FROM price_history ORDER BY product_name")
            rows = cursor.fetchall()
            
            product_names = [row['product_name'] for row in rows]
            expected_names = ['product with price', 'product with zero price']  # normalized names
            
            assert product_names == expected_names
    
    def test_duplicate_alternatives_handling(self):
        """Test that duplicate alternatives are handled correctly."""
        alternatives = [
            {'name': 'Duplicate Product', 'price': 5.00, 'onSale': False, 'matchScore': 0.9},
            {'name': 'Duplicate Product', 'price': 5.50, 'onSale': True, 'matchScore': 0.8},  # Same product, different price
            {'name': 'Unique Product', 'price': 6.00, 'onSale': False, 'matchScore': 0.7}
        ]
        
        # Log alternatives
        log_alternative_products('test query', 'woolworths', alternatives)
        
        # Log each alternative
        for alternative in alternatives:
            if alternative.get('name') and alternative.get('price') is not None:
                log_price_data(
                    product_name=alternative['name'],
                    retailer='woolworths',
                    price=alternative['price'],
                    was_price=alternative.get('was'),
                    on_sale=alternative.get('onSale', False),
                    url=alternative.get('url')
                )
        
        # The price_history table has UNIQUE constraint on (product_name, retailer, date_recorded)
        # So the second "Duplicate Product" should replace the first one
        stats = get_database_stats()
        assert stats['price_history']['total_records'] == 2  # Only 2 unique products per day
        assert stats['price_history']['unique_products'] == 2
        assert stats['alternatives']['total_records'] == 3   # All alternatives stored in alternatives table
        
        # Verify the latest price is kept for duplicate product
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT product_name, price, on_sale 
                FROM price_history 
                WHERE product_name = 'duplicate product'
            """)
            row = cursor.fetchone()
            
            # Should have the latest values (INSERT OR REPLACE behavior)
            assert row['price'] == 5.50
            assert bool(row['on_sale']) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])