-- SQL script to import CSV data into PostgreSQL
-- Run this in your Railway PostgreSQL console

-- Import price_history data
-- First, you'll need to upload price_history_export.csv to your PostgreSQL instance
-- Then run:
-- \copy price_history(id,product_name,retailer,price,was_price,on_sale,date_recorded,url,created_at) FROM 'price_history_export.csv' WITH CSV HEADER;

-- Import alternative_products data  
-- Upload alternative_products_export.csv to your PostgreSQL instance
-- Then run:
-- \copy alternative_products(id,search_query,retailer,product_name,price,was_price,on_sale,promo_text,url,match_score,rank_position,date_recorded,created_at) FROM 'alternative_products_export.csv' WITH CSV HEADER;

-- Reset sequences to avoid ID conflicts
SELECT setval('price_history_id_seq', (SELECT MAX(id) FROM price_history));
SELECT setval('alternative_products_id_seq', (SELECT MAX(id) FROM alternative_products));
