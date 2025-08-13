"""
Database utilities for price history tracking.
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)

# Database file path - use absolute path to ensure it's found
DB_PATH = "/Users/nickmirsepassi/nick-claude/test02/price_history.db"


@contextmanager
def get_db_connection():
    """Get database connection with proper error handling."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Initialize the database with required tables."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create price_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                retailer TEXT NOT NULL,
                price REAL,
                was_price REAL,
                on_sale BOOLEAN DEFAULT FALSE,
                date_recorded DATE NOT NULL,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_name, retailer, date_recorded)
            )
        """)
        
        # Create alternative_products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alternative_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_query TEXT NOT NULL,
                retailer TEXT NOT NULL,
                product_name TEXT NOT NULL,
                price REAL,
                was_price REAL,
                on_sale BOOLEAN DEFAULT FALSE,
                promo_text TEXT,
                url TEXT,
                match_score REAL,
                rank_position INTEGER,
                date_recorded DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create favorites table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                retailer TEXT NOT NULL DEFAULT 'woolworths',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_name, retailer)
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_retailer_date 
            ON price_history(product_name, retailer, date_recorded)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alternatives_query_retailer_date 
            ON alternative_products(search_query, retailer, date_recorded)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alternatives_product_name 
            ON alternative_products(product_name)
        """)
        
        conn.commit()
        logger.info("Database initialized successfully")


def normalize_product_name(product_name: str) -> str:
    """Normalize product name for consistent storage."""
    if not product_name:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    normalized = " ".join(product_name.lower().split())
    
    # Remove common variations that don't affect the core product
    # Example: "Woolworths" brand prefix, size variations etc.
    # This can be expanded based on patterns we see
    
    return normalized


def log_alternative_products(
    search_query: str,
    retailer: str,
    alternatives: List[Dict[str, Any]],
    date_recorded: Optional[date] = None
) -> bool:
    """
    Log alternative product results to the database.
    
    Args:
        search_query: Original search query
        retailer: Retailer name (woolworths/coles)
        alternatives: List of alternative product dictionaries
        date_recorded: Date to record (defaults to today)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not search_query or not retailer or not alternatives:
        logger.warning("Missing required fields for alternatives logging")
        return False
    
    try:
        normalized_query = normalize_product_name(search_query)
        record_date = date_recorded or date.today()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First, delete any existing alternatives for this query/retailer/date
            cursor.execute("""
                DELETE FROM alternative_products 
                WHERE search_query = ? AND retailer = ? AND date_recorded = ?
            """, (normalized_query, retailer, record_date))
            
            # Insert new alternatives
            for rank_position, alt in enumerate(alternatives, 1):
                cursor.execute("""
                    INSERT INTO alternative_products 
                    (search_query, retailer, product_name, price, was_price, on_sale, 
                     promo_text, url, match_score, rank_position, date_recorded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    normalized_query,
                    retailer,
                    normalize_product_name(alt.get('name', '')),
                    alt.get('price'),
                    alt.get('was'),
                    alt.get('onSale', False),
                    alt.get('promoText'),
                    alt.get('url'),
                    alt.get('matchScore'),
                    rank_position,
                    record_date
                ))
            
            conn.commit()
            logger.debug(f"Logged {len(alternatives)} alternatives for '{search_query}' at {retailer}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to log alternative products: {e}")
        return False


def log_price_data(
    product_name: str,
    retailer: str,
    price: Optional[float],
    was_price: Optional[float] = None,
    on_sale: bool = False,
    url: Optional[str] = None,
    date_recorded: Optional[date] = None
) -> bool:
    """
    Log price data to the database.
    
    Args:
        product_name: Name of the product
        retailer: Retailer name (woolworths/coles)
        price: Current price
        was_price: Previous price if on sale
        on_sale: Whether product is on sale
        url: Product URL
        date_recorded: Date to record (defaults to today)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not product_name or not retailer:
        logger.warning("Missing required fields for price logging")
        return False
    
    try:
        normalized_name = normalize_product_name(product_name)
        record_date = date_recorded or date.today()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Use INSERT OR REPLACE to handle duplicates (one entry per day)
            cursor.execute("""
                INSERT OR REPLACE INTO price_history 
                (product_name, retailer, price, was_price, on_sale, date_recorded, url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                normalized_name,
                retailer,
                price,
                was_price,
                on_sale,
                record_date,
                url
            ))
            
            conn.commit()
            logger.debug(f"Logged price data for {normalized_name} at {retailer}: ${price}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to log price data: {e}")
        return False


def get_alternative_products(
    search_query: str,
    retailer: Optional[str] = None,
    days_back: int = 30
) -> List[Dict[str, Any]]:
    """
    Get alternative products for a search query.
    
    Args:
        search_query: Original search query to look up
        retailer: Specific retailer or None for all
        days_back: Number of days of history to retrieve
    
    Returns:
        List of alternative product records
    """
    try:
        normalized_query = normalize_product_name(search_query)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT search_query, retailer, product_name, price, was_price, on_sale, 
                       promo_text, url, match_score, rank_position, date_recorded, created_at
                FROM alternative_products 
                WHERE search_query = ?
                AND date_recorded >= date('now', '-{} days')
            """.format(days_back)
            
            params = [normalized_query]
            
            if retailer:
                query += " AND retailer = ?"
                params.append(retailer)
            
            query += " ORDER BY date_recorded DESC, rank_position ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            alternatives = []
            for row in rows:
                alternatives.append({
                    'search_query': row['search_query'],
                    'retailer': row['retailer'],
                    'product_name': row['product_name'],
                    'price': row['price'],
                    'was_price': row['was_price'],
                    'on_sale': bool(row['on_sale']),
                    'promo_text': row['promo_text'],
                    'url': row['url'],
                    'match_score': row['match_score'],
                    'rank_position': row['rank_position'],
                    'date_recorded': row['date_recorded'],
                    'created_at': row['created_at']
                })
            
            return alternatives
            
    except Exception as e:
        logger.error(f"Failed to get alternative products: {e}")
        return []


def get_price_history(
    product_name: str,
    retailer: Optional[str] = None,
    days_back: int = 30
) -> List[Dict[str, Any]]:
    """
    Get price history for a product.
    
    Args:
        product_name: Product name to look up
        retailer: Specific retailer or None for all
        days_back: Number of days of history to retrieve
    
    Returns:
        List of price history records
    """
    try:
        normalized_name = normalize_product_name(product_name)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT product_name, retailer, price, was_price, on_sale, 
                       date_recorded, url, created_at
                FROM price_history 
                WHERE product_name = ?
                AND date_recorded >= date('now', '-{} days')
            """.format(days_back)
            
            params = [normalized_name]
            
            if retailer:
                query += " AND retailer = ?"
                params.append(retailer)
            
            query += " ORDER BY date_recorded ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            history = []
            for row in rows:
                history.append({
                    'product_name': row['product_name'],
                    'retailer': row['retailer'],
                    'price': row['price'],
                    'was_price': row['was_price'],
                    'on_sale': bool(row['on_sale']),
                    'date_recorded': row['date_recorded'],
                    'url': row['url'],
                    'created_at': row['created_at']
                })
            
            return history
            
    except Exception as e:
        logger.error(f"Failed to get price history: {e}")
        return []


def get_all_tracked_products() -> List[Dict[str, Any]]:
    """Get list of all products we're tracking."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT product_name, retailer, 
                       COUNT(*) as record_count,
                       MIN(date_recorded) as first_seen,
                       MAX(date_recorded) as last_seen
                FROM price_history 
                GROUP BY product_name, retailer
                ORDER BY last_seen DESC
            """)
            
            rows = cursor.fetchall()
            
            products = []
            for row in rows:
                products.append({
                    'product_name': row['product_name'],
                    'retailer': row['retailer'],
                    'record_count': row['record_count'],
                    'first_seen': row['first_seen'],
                    'last_seen': row['last_seen']
                })
            
            return products
            
    except Exception as e:
        logger.error(f"Failed to get tracked products: {e}")
        return []


def clear_all_price_history() -> bool:
    """
    Clear all price history and alternative products data from the database.
    
    WARNING: This will permanently delete all tracked price data!
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get count before deletion for logging
            cursor.execute("SELECT COUNT(*) as total FROM price_history")
            price_records = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM alternative_products")
            alt_records = cursor.fetchone()['total']
            
            # Delete all records
            cursor.execute("DELETE FROM price_history")
            cursor.execute("DELETE FROM alternative_products")
            
            # Reset the auto-increment counters
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='price_history'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='alternative_products'")
            
            conn.commit()
            
            logger.warning(f"Cleared {price_records} price history and {alt_records} alternative product records from database")
            return True
            
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        return False


def delete_product_history(product_name: str, retailer: str) -> Dict[str, Any]:
    """
    Delete all price history for a specific product at a specific retailer.
    
    Args:
        product_name: Product name to delete
        retailer: Retailer to delete from
    
    Returns:
        Dict with success status and number of records deleted
    """
    try:
        normalized_name = normalize_product_name(product_name)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First, count how many records will be deleted
            cursor.execute(
                "SELECT COUNT(*) FROM price_history WHERE product_name = ? AND retailer = ?",
                (normalized_name, retailer)
            )
            records_to_delete = cursor.fetchone()[0]
            
            if records_to_delete == 0:
                return {
                    "success": False,
                    "message": "No records found for this product and retailer",
                    "records_deleted": 0
                }
            
            # Delete the records
            cursor.execute(
                "DELETE FROM price_history WHERE product_name = ? AND retailer = ?",
                (normalized_name, retailer)
            )
            
            conn.commit()
            
            logger.info(f"Deleted {records_to_delete} records for {normalized_name} at {retailer}")
            return {
                "success": True,
                "message": f"Successfully deleted {records_to_delete} records",
                "records_deleted": records_to_delete
            }
            
    except Exception as e:
        logger.error(f"Failed to delete product history: {e}")
        return {
            "success": False,
            "message": f"Error deleting product: {str(e)}",
            "records_deleted": 0
        }


def get_database_stats() -> Dict[str, Any]:
    """Get basic statistics about the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Price history stats
            cursor.execute("SELECT COUNT(*) FROM price_history")
            total_records = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT product_name) FROM price_history")
            unique_products = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT retailer) FROM price_history")
            unique_retailers = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(date_recorded), MAX(date_recorded) FROM price_history")
            date_range = cursor.fetchone()
            
            # Alternative products stats
            cursor.execute("SELECT COUNT(*) FROM alternative_products")
            total_alternatives = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT search_query) FROM alternative_products")
            unique_queries = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT product_name) FROM alternative_products")
            unique_alt_products = cursor.fetchone()[0]
            
            return {
                'price_history': {
                    'total_records': total_records,
                    'unique_products': unique_products,
                    'unique_retailers': unique_retailers,
                    'oldest_record': date_range[0] if date_range and date_range[0] else None,
                    'newest_record': date_range[1] if date_range and date_range[1] else None
                },
                'alternatives': {
                    'total_records': total_alternatives,
                    'unique_queries': unique_queries,
                    'unique_products': unique_alt_products
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {
            'price_history': {
                'total_records': 0,
                'unique_products': 0,
                'unique_retailers': 0,
                'oldest_record': None,
                'newest_record': None
            },
            'alternatives': {
                'total_records': 0,
                'unique_queries': 0,
                'unique_products': 0
            }
        }


# Favorites System Functions (SQLite version)
def add_to_favorites(product_name: str, retailer: str) -> bool:
    """Add product to admin favorites."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute(
                "SELECT id FROM favorites WHERE product_name = ? AND retailer = ?",
                (product_name, retailer)
            )
            
            if cursor.fetchone():
                return False  # Already exists
                
            # Add to favorites
            cursor.execute(
                "INSERT INTO favorites (product_name, retailer) VALUES (?, ?)",
                (product_name, retailer)
            )
            
            conn.commit()
            logger.info(f"Added {product_name} ({retailer}) to favorites")
            return True
            
    except Exception as e:
        logger.error(f"Failed to add favorite: {e}")
        return False

def get_favorites() -> list:
    """Get all admin favorites."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, product_name, retailer, created_at
                FROM favorites
                ORDER BY created_at DESC
            """)
            
            favorites = []
            for row in cursor.fetchall():
                favorites.append({
                    'id': row['id'],
                    'product_name': row['product_name'],
                    'retailer': row['retailer'],
                    'created_at': row['created_at']
                })
            
            return favorites
            
    except Exception as e:
        logger.error(f"Failed to get favorites: {e}")
        return []

def remove_from_favorites(favorite_id: int) -> bool:
    """Remove product from admin favorites."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Removed favorite ID {favorite_id}")
                return True
            else:
                return False
                
    except Exception as e:
        logger.error(f"Failed to remove favorite: {e}")
        return False


# Initialize database on import
try:
    init_database()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")