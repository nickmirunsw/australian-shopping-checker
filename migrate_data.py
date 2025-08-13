#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL.
Run this after deploying to Railway to transfer your existing data.
"""

import sqlite3
import psycopg2
import psycopg2.extras
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

def get_sqlite_data(db_path="price_history.db"):
    """Extract all data from SQLite database."""
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

def insert_postgresql_data(data, database_url):
    """Insert data into PostgreSQL database."""
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Insert price history data
        print(f"Migrating {len(data['price_history'])} price history records...")
        for i, record in enumerate(data['price_history'], 1):
            try:
                cursor.execute("""
                    INSERT INTO price_history 
                    (product_name, retailer, price, was_price, on_sale, date_recorded, url, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_name, retailer, date_recorded) DO NOTHING
                """, (
                    record['product_name'],
                    record['retailer'],
                    record['price'],
                    record['was_price'],
                    record['on_sale'],
                    record['date_recorded'],
                    record['url'],
                    record['created_at']
                ))
                
                if i % 10 == 0:
                    print(f"  Processed {i}/{len(data['price_history'])} price records...")
                    
            except Exception as e:
                print(f"  Error inserting price record {i}: {e}")
                continue
        
        # Insert alternative products data
        print(f"Migrating {len(data['alternatives'])} alternative product records...")
        for i, record in enumerate(data['alternatives'], 1):
            try:
                cursor.execute("""
                    INSERT INTO alternative_products 
                    (search_query, retailer, product_name, price, was_price, on_sale, 
                     promo_text, url, match_score, rank_position, date_recorded, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record['search_query'],
                    record['retailer'], 
                    record['product_name'],
                    record['price'],
                    record['was_price'],
                    record['on_sale'],
                    record['promo_text'],
                    record['url'],
                    record['match_score'],
                    record['rank_position'],
                    record['date_recorded'],
                    record['created_at']
                ))
                
                if i % 10 == 0:
                    print(f"  Processed {i}/{len(data['alternatives'])} alternative records...")
                    
            except Exception as e:
                print(f"  Error inserting alternative record {i}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print("✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        return False

def main():
    """Main migration function."""
    print("🚀 Starting SQLite to PostgreSQL migration...")
    
    # Check if SQLite database exists
    sqlite_path = "price_history.db"
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite database not found at {sqlite_path}")
        print("Make sure you're running this from the project root directory.")
        return 1
    
    # Get PostgreSQL URL from environment or user input
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found in environment.")
        database_url = input("Enter your Railway PostgreSQL URL: ").strip()
        if not database_url:
            print("❌ Database URL is required.")
            return 1
    
    # Extract SQLite data
    print("📤 Extracting data from SQLite...")
    data = get_sqlite_data(sqlite_path)
    if not data:
        return 1
    
    print(f"Found {len(data['price_history'])} price history records")
    print(f"Found {len(data['alternatives'])} alternative product records")
    
    if len(data['price_history']) == 0 and len(data['alternatives']) == 0:
        print("No data to migrate. Exiting.")
        return 0
    
    # Confirm migration
    confirm = input("Proceed with migration? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Migration cancelled.")
        return 0
    
    # Insert into PostgreSQL
    print("📥 Inserting data into PostgreSQL...")
    success = insert_postgresql_data(data, database_url)
    
    if success:
        print("\n🎉 Migration completed!")
        print("Your SQLite data has been successfully transferred to PostgreSQL.")
        print("You can now deploy your app and all your existing data will be available.")
        return 0
    else:
        print("\n❌ Migration failed.")
        return 1

if __name__ == "__main__":
    exit(main())