"""
Generate dummy historical data for testing price tracking and predictions.
"""

import logging
from datetime import date, timedelta
import random
from .db_config import log_price_data

logger = logging.getLogger(__name__)


def generate_dummy_price_history():
    """Generate dummy historical price data for testing."""
    
    # Dummy product with clear "DUMMY" suffix
    product_name = "Woolworths Full Cream Milk 3L DUMMY"
    retailer = "woolworths"
    
    # Base price and sale parameters
    base_price = 4.65
    sale_price = 3.50
    sale_frequency = 14  # Sale every ~2 weeks
    sale_duration = 3    # Sales last ~3 days
    
    # Generate 60 days of historical data
    start_date = date.today() - timedelta(days=60)
    current_date = start_date
    
    records_added = 0
    
    while current_date <= date.today():
        # Determine if this should be a sale day
        days_since_start = (current_date - start_date).days
        
        # Create sale cycles - sale every ~2 weeks for ~3 days
        cycle_day = days_since_start % sale_frequency
        is_sale_period = cycle_day < sale_duration
        
        # Add some randomness to make it more realistic
        if is_sale_period:
            # 80% chance of being on sale during sale period
            on_sale = random.random() < 0.8
        else:
            # 5% chance of random sale outside normal cycle
            on_sale = random.random() < 0.05
        
        if on_sale:
            price = sale_price
            was_price = base_price
        else:
            # Add slight price variation for realism
            price = base_price + random.uniform(-0.10, 0.10)
            was_price = None
        
        # Round to 2 decimal places
        price = round(price, 2)
        
        try:
            success = log_price_data(
                product_name=product_name,
                retailer=retailer,
                price=price,
                was_price=was_price,
                on_sale=on_sale,
                url="https://www.woolworths.com.au/shop/productdetails/888140/woolworths-full-cream-milk-dummy",
                date_recorded=current_date
            )
            
            if success:
                records_added += 1
                
        except Exception as e:
            logger.error(f"Failed to add dummy data for {current_date}: {e}")
        
        current_date += timedelta(days=1)
    
    # Add another dummy product for variety
    product_name_2 = "Wonder White Bread 700g DUMMY"
    base_price_2 = 3.20
    sale_price_2 = 2.50
    
    current_date = start_date
    while current_date <= date.today():
        days_since_start = (current_date - start_date).days
        
        # Different sale cycle - every 21 days for 4 days
        cycle_day = days_since_start % 21
        is_sale_period = cycle_day < 4
        
        if is_sale_period and random.random() < 0.7:
            price = sale_price_2
            was_price = base_price_2
            on_sale = True
        else:
            price = base_price_2 + random.uniform(-0.15, 0.15)
            was_price = None
            on_sale = False
        
        price = round(price, 2)
        
        try:
            success = log_price_data(
                product_name=product_name_2,
                retailer=retailer,
                price=price,
                was_price=was_price,
                on_sale=on_sale,
                url="https://www.woolworths.com.au/shop/productdetails/123456/wonder-white-bread-dummy",
                date_recorded=current_date
            )
            
            if success:
                records_added += 1
                
        except Exception as e:
            logger.error(f"Failed to add dummy data for {current_date}: {e}")
        
        current_date += timedelta(days=1)
    
    logger.info(f"Added {records_added} dummy price history records")
    return records_added


if __name__ == "__main__":
    # Can be run standalone to generate dummy data
    generate_dummy_price_history()