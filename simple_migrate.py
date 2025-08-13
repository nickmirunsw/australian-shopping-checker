#!/usr/bin/env python3
"""
Simple migration script that doesn't require psycopg2.
Uses HTTP requests to the deployed app to populate data.
"""

import sqlite3
import requests
import json
import time
import os

def get_unique_products_from_sqlite():
    """Get unique products from SQLite for migration."""
    conn = sqlite3.connect("price_history.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get unique product names that have actual price data
    cursor.execute("""
        SELECT DISTINCT product_name, retailer, price, was_price, on_sale, date_recorded
        FROM price_history 
        WHERE price IS NOT NULL 
        ORDER BY date_recorded DESC
        LIMIT 50
    """)
    
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return products

def populate_via_searches():
    """Populate the database by making search requests."""
    
    app_url = "https://web-production-877fd.up.railway.app"
    
    print("🔍 Getting unique products from your SQLite database...")
    products = get_unique_products_from_sqlite()
    print(f"Found {len(products)} unique products to migrate")
    
    if not products:
        print("No products found in SQLite database")
        return
    
    print("\n📥 Starting data population via search requests...")
    
    successful_searches = 0
    for i, product in enumerate(products, 1):
        try:
            # Extract search terms from product name
            product_name = product['product_name']
            
            # Clean up product name to make a good search term
            search_terms = product_name.replace('woolworths', '').replace('coles', '').strip()
            search_terms = ' '.join(search_terms.split()[:3])  # First 3 words
            
            if not search_terms:
                continue
                
            print(f"  [{i}/{len(products)}] Searching for: {search_terms}")
            
            # Make search request
            response = requests.post(f"{app_url}/check", 
                json={
                    "items": search_terms,
                    "postcode": "2000"
                }, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                results_count = len(result.get('results', []))
                print(f"    ✅ Found {results_count} products")
                successful_searches += 1
            else:
                print(f"    ⚠️  Search failed (status {response.status_code})")
            
            # Be respectful with API calls
            time.sleep(1)
            
        except Exception as e:
            print(f"    ❌ Error searching for {product_name}: {e}")
            continue
    
    print(f"\n✅ Completed {successful_searches}/{len(products)} successful searches")
    
    # Check final database stats
    try:
        stats_response = requests.get(f"{app_url}/database/stats")
        if stats_response.status_code == 200:
            stats = stats_response.json()['stats']
            price_records = stats['price_history']['total_records']
            alt_records = stats['alternatives']['total_records']
            print(f"\n📊 Your production database now has:")
            print(f"   - {price_records} price history records")
            print(f"   - {alt_records} alternative product records")
            print(f"   - Total: {price_records + alt_records} records")
        
            if price_records > 0:
                print("\n🎉 Migration successful! Your app now has current price data.")
                print("The system will continue to track prices going forward.")
            else:
                print("\n⚠️  No price records were created. The products might not have been found in current Woolworths catalog.")
        
    except Exception as e:
        print(f"Warning: Couldn't get final stats: {e}")

if __name__ == "__main__":
    print("🚀 Starting simple data migration...")
    populate_via_searches()
    print(f"\nYour app is live at: https://web-production-877fd.up.railway.app")