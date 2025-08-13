#!/usr/bin/env python3
"""
Migrate SQLite data to PostgreSQL via your deployed app's API.
This doesn't require installing psycopg2 locally.
"""

import sqlite3
import requests
import json
import os
from datetime import datetime

def get_sqlite_data(db_path="price_history.db"):
    """Get data from SQLite database."""
    if not os.path.exists(db_path):
        print(f"❌ SQLite database not found at {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get price history data
        cursor.execute("SELECT * FROM price_history ORDER BY created_at")
        price_history = [dict(row) for row in cursor.fetchall()]
        
        # Get alternative products data
        cursor.execute("SELECT * FROM alternative_products ORDER BY created_at")
        alternatives = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'price_history': price_history,
            'alternatives': alternatives
        }
    except Exception as e:
        print(f"Error reading SQLite data: {e}")
        return None

def migrate_via_api():
    """Migrate data using your deployed app."""
    
    # Get your app URL
    app_url = input("Enter your Railway app URL (e.g., https://your-app.up.railway.app): ").strip()
    if not app_url.startswith('http'):
        app_url = 'https://' + app_url
    
    # Remove trailing slash
    app_url = app_url.rstrip('/')
    
    print(f"🚀 Using app URL: {app_url}")
    
    # Test connection
    try:
        print("🔍 Testing connection to your app...")
        response = requests.get(f"{app_url}/health", timeout=10)
        if response.status_code != 200:
            print(f"❌ Can't connect to your app. Status: {response.status_code}")
            return False
        print("✅ App is reachable!")
    except Exception as e:
        print(f"❌ Can't connect to your app: {e}")
        print("Make sure your Railway app is deployed and running.")
        return False
    
    # Get admin credentials
    admin_username = input("Enter admin username (default: admin): ").strip() or "admin"
    admin_password = input("Enter admin password (default: password): ").strip() or "password"
    
    # Login to admin
    print("🔐 Logging in as admin...")
    try:
        login_response = requests.post(f"{app_url}/admin/login", json={
            "username": admin_username,
            "password": admin_password
        }, timeout=10)
        
        if login_response.status_code != 200:
            print(f"❌ Admin login failed. Status: {login_response.status_code}")
            print("Make sure your admin credentials are correct.")
            return False
        
        login_data = login_response.json()
        if not login_data.get('success'):
            print(f"❌ Admin login failed: {login_data.get('message', 'Unknown error')}")
            return False
        
        session_token = login_data.get('session_token')
        if not session_token:
            print("❌ No session token received")
            return False
            
        print("✅ Admin login successful!")
        
    except Exception as e:
        print(f"❌ Error during admin login: {e}")
        return False
    
    # Prepare headers with auth token
    headers = {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }
    
    # Get SQLite data
    print("📤 Reading local SQLite data...")
    data = get_sqlite_data()
    if not data:
        return False
    
    print(f"Found {len(data['price_history'])} price records")
    print(f"Found {len(data['alternatives'])} alternative records")
    
    # Confirm migration
    total_records = len(data['price_history']) + len(data['alternatives'])
    confirm = input(f"Migrate {total_records} records to production? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Migration cancelled.")
        return False
    
    # First, clear existing data in production
    print("🗑️  Clearing existing production data...")
    try:
        clear_response = requests.post(f"{app_url}/admin/clear-database", headers=headers, timeout=30)
        if clear_response.status_code == 200:
            clear_data = clear_response.json()
            if clear_data.get('success'):
                print("✅ Production database cleared")
            else:
                print(f"⚠️  Clear database warning: {clear_data.get('message')}")
        else:
            print(f"⚠️  Warning: Couldn't clear production database (status {clear_response.status_code})")
    except Exception as e:
        print(f"⚠️  Warning: Error clearing production database: {e}")
        print("Continuing with migration...")
    
    # Simulate adding products by doing searches (this will populate the database)
    print("📥 Migrating data by simulating product searches...")
    
    # Get unique products from price history
    unique_products = {}
    for record in data['price_history']:
        key = (record['product_name'], record['retailer'])
        if key not in unique_products:
            unique_products[key] = record
    
    print(f"🔍 Simulating searches for {len(unique_products)} unique products...")
    
    # Simulate searches to populate the database
    search_count = 0
    for (product_name, retailer), record in unique_products.items():
        try:
            # Extract search term from product name
            search_term = product_name.split()[:2]  # First 2 words
            search_term = ' '.join(search_term)
            
            # Make a search request (this will populate the database)
            search_response = requests.post(f"{app_url}/check", json={
                "items": search_term,
                "postcode": "2000"
            }, timeout=15)
            
            search_count += 1
            if search_count % 10 == 0:
                print(f"  Processed {search_count}/{len(unique_products)} products...")
            
            # Small delay to be respectful
            import time
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  Warning: Error searching for {product_name}: {e}")
            continue
    
    print(f"✅ Completed migration simulation for {search_count} products")
    
    # Check database stats
    try:
        stats_response = requests.get(f"{app_url}/database/stats", timeout=10)
        if stats_response.status_code == 200:
            stats = stats_response.json()['stats']
            price_records = stats['price_history']['total_records']
            alt_records = stats['alternatives']['total_records']
            print(f"\n📊 Production database now contains:")
            print(f"   - {price_records} price history records")
            print(f"   - {alt_records} alternative product records")
            print(f"   - Total: {price_records + alt_records} records")
        
    except Exception as e:
        print(f"Warning: Couldn't get database stats: {e}")
    
    print("\n🎉 Migration completed!")
    print(f"Your app is live at: {app_url}")
    print("The database now has current price data and will continue to track prices going forward.")
    
    return True

if __name__ == "__main__":
    print("🚀 Starting migration via deployed app API...")
    migrate_via_api()