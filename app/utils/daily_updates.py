"""
Daily price update functionality for building historical data.
"""

import asyncio
import logging
from datetime import date
from typing import List, Dict, Any, Tuple
from ..adapters.woolworths import WoolworthsAdapter
from .db_config import get_all_tracked_products, log_price_data
from .matching import get_product_matcher

logger = logging.getLogger(__name__)


class DailyPriceUpdater:
    """Handles daily price updates for all tracked products."""
    
    def __init__(self):
        self.woolworths = WoolworthsAdapter()
        self.retailers = {
            "woolworths": self.woolworths
        }
    
    async def update_all_products(self, batch_size: int = 50, max_batches: int = None, 
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
                    
                    try:
                        if progress_callback:
                            progress_callback(global_index, len(products_to_process), product_name, batch_num + 1, total_batches)
                        
                        # Search for current price data
                        updated_data = await self._get_current_price_data(product_name, retailer)
                        
                        if updated_data:
                            # Log the new price data
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
                                logger.debug(f"Updated price for {product_name}: ${updated_data['price']}")
                            else:
                                failed_updates += 1
                                batch_failed += 1
                                logger.warning(f"Failed to log price data for {product_name}")
                        else:
                            failed_updates += 1
                            batch_failed += 1
                            logger.warning(f"Could not find current price data for {product_name}")
                    
                    except Exception as e:
                        failed_updates += 1
                        batch_failed += 1
                        logger.error(f"Error updating {product_name}: {e}")
                    
                    # Dynamic delay to be respectful to the API
                    # Shorter delay for successful requests, longer for failures
                    delay = 0.2 if updated_data else 0.5
                    await asyncio.sleep(delay)
                
                # Log batch completion
                batch_success_rate = (batch_successful / len(batch_products)) * 100 if batch_products else 0
                logger.info(f"Batch {batch_num + 1} completed: {batch_successful}/{len(batch_products)} successful ({batch_success_rate:.1f}%)")
                
                processed_products += len(batch_products)
                
                # Longer delay between batches to avoid overwhelming APIs
                if batch_num < total_batches - 1:  # Don't sleep after last batch
                    logger.info(f"Waiting 2 seconds before next batch...")
                    await asyncio.sleep(2.0)
            
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
            
            if not best_match or not score or score.total_score < 0.3:
                logger.debug(f"No good match found for {product_name} (best score: {score.total_score if score else 0})")
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
        
        # Take the first few meaningful words
        search_term = " ".join(filtered_words[:2]) if filtered_words else name
        
        # Fallback to first word if nothing meaningful found
        if not search_term.strip():
            search_term = words[0] if words else product_name
        
        logger.debug(f"Extracted search term '{search_term}' from '{product_name}'")
        return search_term.strip()


# Global instance
_daily_updater = None

def get_daily_updater():
    """Get the global daily updater instance."""
    global _daily_updater
    if _daily_updater is None:
        _daily_updater = DailyPriceUpdater()
    return _daily_updater