#!/usr/bin/env python3
"""
Proper migration that preserves historical dates by directly inserting SQLite data
into PostgreSQL via the admin API endpoint we'll create.
"""

import sqlite3
import requests
import json

def get_sqlite_data():
    """Get all historical data from SQLite preserving dates."""
    conn = sqlite3.connect('price_history.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all price history with original dates
    cursor.execute("""
        SELECT product_name, retailer, price, was_price, on_sale, date_recorded, url, created_at
        FROM price_history 
        ORDER BY date_recorded, created_at
    """)
    price_history = []
    for row in cursor.fetchall():
        price_history.append({
            'product_name': row['product_name'],
            'retailer': row['retailer'],
            'price': row['price'],
            'was_price': row['was_price'],
            'on_sale': bool(row['on_sale']),
            'date_recorded': row['date_recorded'],
            'url': row['url'],
            'created_at': row['created_at']
        })
    
    # Get alternatives
    cursor.execute("""
        SELECT search_query, retailer, product_name, price, was_price, on_sale, 
               promo_text, url, match_score, rank_position, date_recorded, created_at
        FROM alternative_products 
        ORDER BY date_recorded, created_at
    """)
    alternatives = []
    for row in cursor.fetchall():
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
    
    conn.close()
    return price_history, alternatives

def main():
    print("🔍 Analyzing SQLite data...")
    price_history, alternatives = get_sqlite_data()
    
    print(f"📊 SQLite Database Analysis:")
    print(f"   - {len(price_history)} price history records")
    print(f"   - {len(alternatives)} alternative records")
    
    # Analyze date ranges
    if price_history:
        dates = [r['date_recorded'] for r in price_history if r['date_recorded']]
        if dates:
            print(f"   - Date range: {min(dates)} to {max(dates)}")
    
    # Count products with multiple days
    from collections import defaultdict
    product_days = defaultdict(set)
    for record in price_history:
        key = (record['product_name'], record['retailer'])
        product_days[key].add(record['date_recorded'])
    
    multi_day_products = {k: len(v) for k, v in product_days.items() if len(v) > 1}
    print(f"   - {len(multi_day_products)} products have multiple days of data")
    
    if multi_day_products:
        print("   - Top multi-day products:")
        for (name, retailer), days in sorted(multi_day_products.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     • {name}: {days} days")
    
    # Ask for confirmation 
    print(f"\n❓ Do you want to proceed with proper historical migration?")
    print(f"   This will:")
    print(f"   1. Clear current production database")
    print(f"   2. Import all {len(price_history)} price records with original dates")
    print(f"   3. Import all {len(alternatives)} alternative records")
    print(f"   4. Preserve your multi-day tracking data")
    
    print("\nProceeding with migration...")
    
    # Login to admin
    print("\n🔐 Logging in to admin...")
    login_response = requests.post('https://web-production-877fd.up.railway.app/admin/login', 
        json={'username': 'admin', 'password': 'password'})
    
    if login_response.status_code != 200:
        print("❌ Admin login failed")
        return False
    
    token = login_response.json()['session_token']
    print("✅ Admin login successful")
    
    # Clear current database
    print("🗑️ Clearing production database...")
    clear_response = requests.post('https://web-production-877fd.up.railway.app/admin/clear-database',
        headers={'Authorization': f'Bearer {token}'})
    
    if clear_response.status_code == 200:
        print("✅ Production database cleared")
    else:
        print(f"⚠️ Clear failed: {clear_response.status_code}")
        return False
    
    # Bulk import data
    print(f"📥 Importing {len(price_history)} price records and {len(alternatives)} alternatives...")
    
    import_data = {
        'price_history': price_history,
        'alternatives': alternatives
    }
    
    import_response = requests.post('https://web-production-877fd.up.railway.app/admin/bulk-import-data',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json=import_data,
        timeout=120  # 2 minute timeout for bulk import
    )
    
    if import_response.status_code == 200:
        result = import_response.json()
        print("✅ Bulk import successful!")
        print(f"   - Price records: {result['stats']['price_records']['successful']}/{result['stats']['price_records']['total']}")
        print(f"   - Alternatives: {result['stats']['alternatives']['successful']}/{result['stats']['alternatives']['total']}")
    else:
        print(f"❌ Bulk import failed: {import_response.status_code}")
        try:
            print(f"   Error: {import_response.json()}")
        except:
            print(f"   Raw response: {import_response.text}")
        return False
    
    # Check final database stats
    print("\n📊 Checking final database stats...")
    stats_response = requests.get('https://web-production-877fd.up.railway.app/database/stats')
    if stats_response.status_code == 200:
        stats = stats_response.json()['stats']
        price_records = stats['price_history']['total_records']
        alt_records = stats['alternatives']['total_records']
        print(f"✅ Production database now contains:")
        print(f"   - {price_records} price history records")
        print(f"   - {alt_records} alternative product records")
        print(f"   - Date range: {stats['price_history']['oldest_record']} to {stats['price_history']['newest_record']}")
    
    return True

if __name__ == "__main__":
    main()