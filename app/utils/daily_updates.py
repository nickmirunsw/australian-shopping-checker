"""
Daily price update functionality for building historical data.
"""

import asyncio
import logging
from datetime import date
from typing import List, Dict, Any, Tuple
from ..adapters.woolworths import WoolworthsAdapter
from .db_config import get_all_tracked_products, get_products_missing_todays_price, log_price_data
from .matching import get_product_matcher

logger = logging.getLogger(__name__)


class DailyPriceUpdater:
    """Handles daily price updates for all tracked products."""
    
    def __init__(self):
        self.woolworths = WoolworthsAdapter()
        self.retailers = {
            "woolworths": self.woolworths
        }
        self.consecutive_failures = 0
        self.circuit_breaker_threshold = 10  # Stop after 10 consecutive failures
    
    async def update_all_products(self, batch_size: int = 20, max_batches: int = None, 
                                progress_callback=None) -> Dict[str, Any]:
        """
        Update prices for all products currently in the database using batching.
        
        Args:
            batch_size: Number of products to update in each batch (default: 50)
            max_batches: Maximum number of batches to process (None for unlimited)
            progress_callback: Optional callback function to report progress
            
        Returns:
            Dict with update results and statistics
        """
        try:
            # Get all tracked products
            tracked_products = get_all_tracked_products()
            
            if not tracked_products:
                return {
                    "success": True,
                    "message": "No products to update",
                    "stats": {
                        "total_products": 0,
                        "successful_updates": 0,
                        "failed_updates": 0,
                        "new_records": 0
                    }
                }
            
            total_products = len(tracked_products)
            total_batches = (total_products + batch_size - 1) // batch_size  # Ceiling division
            
            # Limit batches if max_batches is specified
            if max_batches:
                total_batches = min(total_batches, max_batches)
                products_to_process = tracked_products[:max_batches * batch_size]
            else:
                products_to_process = tracked_products
            
            successful_updates = 0
            failed_updates = 0
            new_records = 0
            processed_products = 0
            
            logger.info(f"Starting batched daily price update: {len(products_to_process)} products in {total_batches} batches of {batch_size}")
            
            # Process products in batches
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(products_to_process))
                batch_products = products_to_process[start_idx:end_idx]
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_products)} products)")
                
                batch_successful = 0
                batch_failed = 0
                
                for i, product in enumerate(batch_products):
                    product_name = product['product_name']
                    retailer = product['retailer']
                    global_index = start_idx + i + 1
                    updated_data = None
                    
                    try:
                        if progress_callback:
                            progress_callback(global_index, len(products_to_process), product_name, batch_num + 1, total_batches)
                        
                        # Search for current price data with timeout
                        logger.info(f"Updating product {global_index}/{len(products_to_process)}: {product_name}")
                        
                        # Use asyncio.wait_for to add timeout protection
                        try:
                            updated_data = await asyncio.wait_for(
                                self._get_current_price_data(product_name, retailer),
                                timeout=30.0  # 30 second timeout per product
                            )
                        except asyncio.TimeoutError:
                            logger.warning(f"Timeout while updating {product_name} - skipping")
                            failed_updates += 1
                            batch_failed += 1
                            continue
                        
                        if updated_data:
                            logger.info(f"Found price data for {product_name}: ${updated_data['price']}")
                            
                            # Reset consecutive failures on successful API call
                            self.consecutive_failures = 0
                            
                            # Database operation with retry logic
                            max_db_retries = 3
                            db_success = False
                            
                            for retry in range(max_db_retries):
                                try:
                                    success = log_price_data(
                                        product_name=updated_data['product_name'],
                                        retailer=updated_data['retailer'],
                                        price=updated_data['price'],
                                        was_price=updated_data.get('was_price'),
                                        on_sale=updated_data.get('on_sale', False),
                                        url=updated_data.get('url')
                                    )
                                    
                                    if success:
                                        successful_updates += 1
                                        batch_successful += 1
                                        new_records += 1
                                        db_success = True
                                        logger.debug(f"Updated price for {product_name}: ${updated_data['price']}")
                                        break
                                    else:
                                        logger.warning(f"Database insert failed for {product_name} (attempt {retry + 1})")
                                        if retry < max_db_retries - 1:
                                            await asyncio.sleep(1.0)  # Wait before retry
                                        
                                except Exception as db_error:
                                    logger.error(f"Database error for {product_name} (attempt {retry + 1}): {db_error}")
                                    if retry < max_db_retries - 1:
                                        await asyncio.sleep(1.0)  # Wait before retry
                            
                            if not db_success:
                                failed_updates += 1
                                batch_failed += 1
                                logger.error(f"Failed to log price data for {product_name} after {max_db_retries} attempts")
                        else:
                            failed_updates += 1
                            batch_failed += 1
                            self.consecutive_failures += 1
                            logger.warning(f"Could not find current price data for {product_name} (search term extraction or API search failed)")
                            
                            # Circuit breaker: if too many consecutive failures, abort
                            if self.consecutive_failures >= self.circuit_breaker_threshold:
                                logger.error(f"Circuit breaker triggered: {self.consecutive_failures} consecutive failures. Stopping update process.")
                                result = {
                                    "success": False,
                                    "message": f"Update aborted due to circuit breaker: {self.consecutive_failures} consecutive API failures. This may indicate API rate limiting or service issues.",
                                    "stats": {
                                        "total_products_in_db": total_products,
                                        "products_processed": processed_products + i + 1,  # Include current item
                                        "successful_updates": successful_updates,
                                        "failed_updates": failed_updates,
                                        "new_records": new_records,
                                        "success_rate": round((successful_updates / (processed_products + i + 1)) * 100, 1) if (processed_products + i + 1) > 0 else 0,
                                        "batches_processed": batch_num + 1,
                                        "batch_size": batch_size,
                                        "circuit_breaker_triggered": True
                                    }
                                }
                                return result
                    
                    except Exception as e:
                        failed_updates += 1
                        batch_failed += 1
                        logger.error(f"Unexpected error updating {product_name}: {e}")
                    
                    # Dynamic delay to be respectful to the API and avoid rate limits
                    if updated_data:
                        delay = 0.5  # Longer delay for successful requests
                    else:
                        delay = 0.2  # Shorter delay for failed requests
                    
                    await asyncio.sleep(delay)
                
                # Log batch completion
                batch_success_rate = (batch_successful / len(batch_products)) * 100 if batch_products else 0
                logger.info(f"Batch {batch_num + 1} completed: {batch_successful}/{len(batch_products)} successful ({batch_success_rate:.1f}%)")
                
                processed_products += len(batch_products)
                
                # Dynamic delay between batches based on success rate
                if batch_num < total_batches - 1:  # Don't sleep after last batch
                    # Longer delay if batch had many failures (API might be stressed)
                    if batch_success_rate < 50:
                        delay_time = 5.0
                        logger.info(f"Low success rate ({batch_success_rate:.1f}%) - waiting {delay_time} seconds before next batch...")
                    elif batch_success_rate < 80:
                        delay_time = 3.0
                        logger.info(f"Moderate success rate ({batch_success_rate:.1f}%) - waiting {delay_time} seconds before next batch...")
                    else:
                        delay_time = 1.5
                        logger.info(f"Good success rate ({batch_success_rate:.1f}%) - waiting {delay_time} seconds before next batch...")
                    
                    await asyncio.sleep(delay_time)
            
            success_rate = (successful_updates / processed_products) * 100 if processed_products > 0 else 0
            
            result = {
                "success": True,
                "message": f"Batched daily update completed: {successful_updates}/{processed_products} products updated ({success_rate:.1f}% success rate) in {total_batches} batches",
                "stats": {
                    "total_products_in_db": total_products,
                    "products_processed": processed_products,
                    "successful_updates": successful_updates,
                    "failed_updates": failed_updates,
                    "new_records": new_records,
                    "success_rate": round(success_rate, 1),
                    "batches_processed": total_batches,
                    "batch_size": batch_size
                }
            }
            
            logger.info(f"Daily update completed: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"Daily update failed: {e}")
            return {
                "success": False,
                "message": f"Daily update failed: {str(e)}",
                "stats": {
                    "total_products_in_db": 0,
                    "products_processed": 0,
                    "successful_updates": 0,
                    "failed_updates": 0,
                    "new_records": 0,
                    "batches_processed": 0,
                    "batch_size": batch_size
                }
            }
    
    async def smart_daily_update(self, progress_callback=None) -> Dict[str, Any]:
        """
        Smart daily update: randomly select 100 products missing today's price data.
        
        This is a gentler approach that distributes updates throughout the day,
        avoiding API rate limits and allowing admin to do frequent small updates.
        
        Args:
            progress_callback: Optional callback function to report progress
            
        Returns:
            Dict with update results and statistics
        """
        try:
            # Reset consecutive failures counter for new update session
            self.consecutive_failures = 0
            
            # Get products missing today's price data
            products_to_update = get_products_missing_todays_price(limit=100)
            
            if not products_to_update:
                return {
                    "success": True,
                    "message": "All products have today's price data! 🎉",
                    "stats": {
                        "total_products_missing": 0,
                        "products_processed": 0,
                        "successful_updates": 0,
                        "failed_updates": 0,
                        "new_records": 0,
                        "success_rate": 100.0,
                        "update_type": "smart"
                    }
                }
            
            total_products = len(products_to_update)
            successful_updates = 0
            failed_updates = 0
            new_records = 0
            
            logger.info(f"Starting smart daily update: {total_products} products missing today's price data")
            
            # Process products one by one (no batching needed for 100 items)
            for i, product in enumerate(products_to_update):
                product_name = product['product_name']
                retailer = product['retailer']
                current_index = i + 1
                updated_data = None
                
                try:
                    if progress_callback:
                        progress_callback(current_index, total_products, product_name, 1, 1)
                    
                    # Search for current price data with timeout
                    logger.info(f"Smart update {current_index}/{total_products}: {product_name}")
                    
                    try:
                        updated_data = await asyncio.wait_for(
                            self._get_current_price_data(product_name, retailer),
                            timeout=30.0  # 30 second timeout per product
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout while updating {product_name} - skipping")
                        failed_updates += 1
                        continue
                    
                    if updated_data:
                        logger.info(f"Found price data for {product_name}: ${updated_data['price']}")
                        
                        # Reset consecutive failures on successful API call
                        self.consecutive_failures = 0
                        
                        # Database operation with retry logic
                        max_db_retries = 3
                        db_success = False
                        
                        for retry in range(max_db_retries):
                            try:
                                success = log_price_data(
                                    product_name=updated_data['product_name'],
                                    retailer=updated_data['retailer'],
                                    price=updated_data['price'],
                                    was_price=updated_data.get('was_price'),
                                    on_sale=updated_data.get('on_sale', False),
                                    url=updated_data.get('url')
                                )
                                
                                if success:
                                    successful_updates += 1
                                    new_records += 1
                                    db_success = True
                                    logger.debug(f"Updated price for {product_name}: ${updated_data['price']}")
                                    break
                                else:
                                    logger.warning(f"Database insert failed for {product_name} (attempt {retry + 1})")
                                    if retry < max_db_retries - 1:
                                        await asyncio.sleep(1.0)  # Wait before retry
                                    
                            except Exception as db_error:
                                logger.error(f"Database error for {product_name} (attempt {retry + 1}): {db_error}")
                                if retry < max_db_retries - 1:
                                    await asyncio.sleep(1.0)  # Wait before retry
                        
                        if not db_success:
                            failed_updates += 1
                            logger.error(f"Failed to log price data for {product_name} after {max_db_retries} attempts")
                    else:
                        failed_updates += 1
                        self.consecutive_failures += 1
                        logger.warning(f"Could not find current price data for {product_name}")
                        
                        # Circuit breaker for smart updates (stricter threshold)
                        if self.consecutive_failures >= 5:  # Lower threshold for smart updates
                            logger.warning(f"Smart update circuit breaker triggered: {self.consecutive_failures} consecutive failures. Stopping early.")
                            break
                
                except Exception as e:
                    failed_updates += 1
                    self.consecutive_failures += 1
                    logger.error(f"Unexpected error updating {product_name}: {e}")
                    
                    # Circuit breaker
                    if self.consecutive_failures >= 5:
                        logger.warning(f"Smart update circuit breaker triggered: {self.consecutive_failures} consecutive failures. Stopping early.")
                        break
                
                # Respectful delay between requests
                if updated_data:
                    delay = 1.0  # 1 second delay for successful requests
                else:
                    delay = 0.5  # Shorter delay for failed requests
                
                await asyncio.sleep(delay)
            
            processed_products = successful_updates + failed_updates
            success_rate = (successful_updates / processed_products) * 100 if processed_products > 0 else 0
            
            result = {
                "success": True,
                "message": f"Smart update completed: {successful_updates}/{processed_products} products updated ({success_rate:.1f}% success rate)",
                "stats": {
                    "total_products_missing": total_products,
                    "products_processed": processed_products,
                    "successful_updates": successful_updates,
                    "failed_updates": failed_updates,
                    "new_records": new_records,
                    "success_rate": round(success_rate, 1),
                    "update_type": "smart",
                    "circuit_breaker_triggered": self.consecutive_failures >= 5
                }
            }
            
            logger.info(f"Smart daily update completed: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"Smart daily update failed: {e}")
            return {
                "success": False,
                "message": f"Smart daily update failed: {str(e)}",
                "stats": {
                    "total_products_missing": 0,
                    "products_processed": 0,
                    "successful_updates": 0,
                    "failed_updates": 0,
                    "new_records": 0,
                    "success_rate": 0,
                    "update_type": "smart"
                }
            }
    
    async def _get_current_price_data(self, product_name: str, retailer: str) -> Dict[str, Any]:
        """
        Get current price data for a specific product.
        
        This function tries to search for the product by name and find the best match.
        """
        try:
            if retailer not in self.retailers:
                logger.warning(f"Unsupported retailer: {retailer}")
                return None
            
            adapter = self.retailers[retailer]
            
            # Extract search terms from product name
            search_term = self._extract_search_term(product_name)
            
            # Search for the product
            products = await adapter.search(search_term, "2000")  # Use default postcode
            
            if not products:
                logger.debug(f"No products found for search term: {search_term}")
                return None
            
            # Find the best match using our matching algorithm
            matcher = get_product_matcher()
            best_match, score = matcher.find_best_match(product_name, products)
            
            if not best_match or not score or score.total_score < 0.2:  # Reduced threshold from 0.3 to 0.2
                logger.warning(f"No good match found for {product_name} (best score: {score.total_score if score else 0}, search term: '{search_term}')")
                return None
            
            # Return the updated price data
            return {
                "product_name": product_name,  # Keep the original normalized name
                "retailer": retailer,
                "price": best_match.price,
                "was_price": best_match.was,
                "on_sale": best_match.promoFlag or False,
                "url": best_match.url
            }
            
        except Exception as e:
            logger.error(f"Error getting price data for {product_name}: {e}")
            return None
    
    def _extract_search_term(self, product_name: str) -> str:
        """
        Extract a good search term from the stored product name.
        
        For example:
        "woolworths full cream milk 3l dummy" -> "milk"
        "cc's corn chips taco 175g" -> "corn chips"
        """
        name = product_name.lower()
        
        # Remove "dummy" suffix if present
        if "dummy" in name:
            name = name.replace("dummy", "").strip()
        
        # Remove common brand prefixes
        brands_to_remove = [
            "woolworths ", "coles ", "cc's ", "wonder white ",
            "kettle ", "thins ", "kitkat ", "coca cola ", "pepsi "
        ]
        
        for brand in brands_to_remove:
            if name.startswith(brand):
                name = name[len(brand):].strip()
                break
        
        # Remove size information and focus on the main product
        # This is a simple approach - could be more sophisticated
        words = name.split()
        
        # Remove size-like words (numbers + units)
        filtered_words = []
        for word in words:
            # Skip words that look like sizes (e.g., "3l", "175g", "700g")
            if any(char.isdigit() for char in word) and any(char.isalpha() for char in word):
                continue
            # Skip standalone numbers
            if word.isdigit():
                continue
            filtered_words.append(word)
        
        # Take the first few meaningful words (increased from 2 to 3)
        search_term = " ".join(filtered_words[:3]) if filtered_words else name
        
        # Fallback to first few words if nothing meaningful found
        if not search_term.strip():
            search_term = " ".join(words[:2]) if len(words) >= 2 else (words[0] if words else product_name)
        
        logger.info(f"Extracted search term '{search_term}' from '{product_name}'")
        return search_term.strip()


# Global instance
_daily_updater = None

def get_daily_updater():
    """Get the global daily updater instance."""
    global _daily_updater
    if _daily_updater is None:
        _daily_updater = DailyPriceUpdater()
    return _daily_updater