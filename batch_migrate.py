#!/usr/bin/env python3
"""
Batch migration - import historical data in smaller chunks.
"""

import sqlite3
import requests
import json
import time

def get_sqlite_data():
    """Get all historical data from SQLite."""
    conn = sqlite3.connect('price_history.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
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
    
    conn.close()
    return price_history

def main():
    print("🚀 Starting batch migration...")
    
    # Login to admin
    print("🔐 Logging in to admin...")
    login_response = requests.post('https://web-production-877fd.up.railway.app/admin/login', 
        json={'username': 'admin', 'password': 'password'})
    
    if login_response.status_code != 200:
        print("❌ Admin login failed")
        return False
    
    token = login_response.json()['session_token']
    print("✅ Admin login successful")
    
    # Get SQLite data
    price_history = get_sqlite_data()
    print(f"📊 Found {len(price_history)} price records to migrate")
    
    # Clear current database
    print("🗑️ Clearing production database...")
    clear_response = requests.post('https://web-production-877fd.up.railway.app/admin/clear-database',
        headers={'Authorization': f'Bearer {token}'})
    
    if clear_response.status_code == 200:
        print("✅ Production database cleared")
    else:
        print(f"❌ Clear failed: {clear_response.status_code}")
        return False
    
    # Import in batches of 50
    batch_size = 50
    successful_batches = 0
    failed_batches = 0
    total_imported = 0
    
    for i in range(0, len(price_history), batch_size):
        batch = price_history[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(price_history) + batch_size - 1) // batch_size
        
        print(f"📥 Importing batch {batch_num}/{total_batches} ({len(batch)} records)...")
        
        import_data = {
            'price_history': batch,
            'alternatives': []  # Skip alternatives for now to focus on price history
        }
        
        try:
            import_response = requests.post('https://web-production-877fd.up.railway.app/admin/bulk-import-data',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                json=import_data,
                timeout=60  # 1 minute timeout per batch
            )
            
            if import_response.status_code == 200:
                result = import_response.json()
                batch_success = result['stats']['price_records']['successful']
                total_imported += batch_success
                successful_batches += 1
                print(f"   ✅ Batch {batch_num}: {batch_success}/{len(batch)} records imported")
            else:
                print(f"   ❌ Batch {batch_num} failed: {import_response.status_code}")
                failed_batches += 1
            
            # Small delay between batches
            time.sleep(2)
            
        except Exception as e:
            print(f"   ❌ Batch {batch_num} error: {e}")
            failed_batches += 1
    
    # Check final stats
    print(f"\n📊 Migration Summary:")
    print(f"   - Successful batches: {successful_batches}/{successful_batches + failed_batches}")
    print(f"   - Total records imported: {total_imported}/{len(price_history)}")
    
    # Check database stats
    stats_response = requests.get('https://web-production-877fd.up.railway.app/database/stats')
    if stats_response.status_code == 200:
        stats = stats_response.json()['stats']
        print(f"\n✅ Production database now contains:")
        print(f"   - {stats['price_history']['total_records']} price records")
        print(f"   - Date range: {stats['price_history']['oldest_record']} to {stats['price_history']['newest_record']}")
        
        # Check for multi-day products
        if stats['price_history']['oldest_record'] != stats['price_history']['newest_record']:
            print(f"   - ✅ Multi-day data preserved!")

if __name__ == "__main__":
    main()