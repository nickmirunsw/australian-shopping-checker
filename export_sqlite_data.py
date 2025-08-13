#!/usr/bin/env python3
"""
Export SQLite data to CSV files for manual import to PostgreSQL.
"""

import sqlite3
import csv
import os
from datetime import datetime

def export_sqlite_to_csv(db_path="price_history.db"):
    """Export SQLite data to CSV files."""
    
    if not os.path.exists(db_path):
        print(f"❌ SQLite database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Export price_history table
        print("📤 Exporting price_history table...")
        cursor.execute("SELECT * FROM price_history ORDER BY created_at")
        price_rows = cursor.fetchall()
        
        with open('price_history_export.csv', 'w', newline='', encoding='utf-8') as csvfile:
            if price_rows:
                fieldnames = price_rows[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in price_rows:
                    writer.writerow(dict(row))
        
        print(f"   ✅ Exported {len(price_rows)} price history records to price_history_export.csv")
        
        # Export alternative_products table
        print("📤 Exporting alternative_products table...")
        cursor.execute("SELECT * FROM alternative_products ORDER BY created_at")
        alt_rows = cursor.fetchall()
        
        with open('alternative_products_export.csv', 'w', newline='', encoding='utf-8') as csvfile:
            if alt_rows:
                fieldnames = alt_rows[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in alt_rows:
                    writer.writerow(dict(row))
        
        print(f"   ✅ Exported {len(alt_rows)} alternative product records to alternative_products_export.csv")
        
        conn.close()
        
        # Create SQL import script
        print("📝 Creating SQL import script...")
        with open('import_data.sql', 'w') as sqlfile:
            sqlfile.write("""-- SQL script to import CSV data into PostgreSQL
-- Run this in your Railway PostgreSQL console

-- Import price_history data
-- First, you'll need to upload price_history_export.csv to your PostgreSQL instance
-- Then run:
-- \\copy price_history(id,product_name,retailer,price,was_price,on_sale,date_recorded,url,created_at) FROM 'price_history_export.csv' WITH CSV HEADER;

-- Import alternative_products data  
-- Upload alternative_products_export.csv to your PostgreSQL instance
-- Then run:
-- \\copy alternative_products(id,search_query,retailer,product_name,price,was_price,on_sale,promo_text,url,match_score,rank_position,date_recorded,created_at) FROM 'alternative_products_export.csv' WITH CSV HEADER;

-- Reset sequences to avoid ID conflicts
SELECT setval('price_history_id_seq', (SELECT MAX(id) FROM price_history));
SELECT setval('alternative_products_id_seq', (SELECT MAX(id) FROM alternative_products));
""")
        
        print("\n🎉 Export completed!")
        print("\nFiles created:")
        print("- price_history_export.csv")
        print("- alternative_products_export.csv") 
        print("- import_data.sql")
        
        print(f"\nTotal records: {len(price_rows)} price records + {len(alt_rows)} alternative records = {len(price_rows) + len(alt_rows)} total")
        
        return True
        
    except Exception as e:
        print(f"❌ Error exporting data: {e}")
        return False

if __name__ == "__main__":
    export_sqlite_to_csv()