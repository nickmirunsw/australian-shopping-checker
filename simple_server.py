#!/usr/bin/env python3
"""
Simple FastAPI server for the Australian Supermarket Sale Checker
"""

import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import time

# Import the real sale checker
from app.services.sale_checker import SaleChecker
from app.models import CheckItemsRequest, CheckItemsResponse, ItemCheckResult
from app.utils.database import get_price_history, get_all_tracked_products, clear_all_price_history, get_database_stats, delete_product_history
from app.utils.dummy_data import generate_dummy_price_history
from app.utils.predictions import get_sale_prediction
from app.utils.daily_updates import get_daily_updater

# Create app
app = FastAPI(title="Australian Supermarket Sale Checker")

# Initialize sale checker service
sale_checker = SaleChecker()

# Mount static files if they exist
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass  # Static files not available

@app.get("/")
async def serve_frontend():
    """Serve the main web interface."""
    try:
        return FileResponse("static/modern.html")
    except Exception:
        return {"message": "Australian Supermarket Sale Checker API", "status": "running"}

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "timestamp": time.time()}

@app.post("/check-items", response_model=CheckItemsResponse)
async def check_items(request_body: CheckItemsRequest):
    """
    Check if items are on sale at Australian supermarkets.
    """
    # Parse comma-separated items
    items = [item.strip() for item in request_body.items.split(",") if item.strip()]
    
    try:
        # Use the real sale checker service
        results = await sale_checker.check_items(items, request_body.postcode)
        
        # Convert to response model format
        response_results = []
        for result in results["results"]:
            response_results.append(ItemCheckResult(**result))
        
        return CheckItemsResponse(
            results=response_results,
            postcode=results["postcode"],
            itemsChecked=results["itemsChecked"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking items: {str(e)}")


@app.get("/price-history/{product_name}")
async def get_product_price_history(product_name: str, retailer: Optional[str] = None, days_back: int = 30):
    """Get price history for a specific product."""
    try:
        history = get_price_history(product_name, retailer, days_back)
        return {
            "product_name": product_name,
            "retailer": retailer,
            "days_back": days_back,
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting price history: {str(e)}")


@app.get("/tracked-products")
async def get_tracked_products():
    """Get list of all products being tracked."""
    try:
        products = get_all_tracked_products()
        return {
            "products": products,
            "count": len(products)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting tracked products: {str(e)}")


@app.get("/sale-prediction/{product_name}")
async def get_product_sale_prediction(product_name: str, retailer: str = "woolworths"):
    """Get sale prediction for a specific product."""
    try:
        prediction = get_sale_prediction(product_name, retailer)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sale prediction: {str(e)}")


@app.get("/database-stats")
async def get_database_statistics():
    """Get database statistics."""
    try:
        stats = get_database_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting database stats: {str(e)}")


@app.get("/admin/database-stats")  
async def get_admin_database_statistics():
    """Get database statistics (admin endpoint - always fresh data)."""
    try:
        stats = get_database_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting admin database stats: {str(e)}")


@app.delete("/clear-database")
async def clear_database():
    """Clear all price history data from the database. WARNING: This is permanent!"""
    try:
        success = clear_all_price_history()
        if success:
            return {
                "message": "Database cleared successfully",
                "success": True
            }
        else:
            return {
                "message": "Failed to clear database",
                "success": False
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing database: {str(e)}")


@app.post("/smart-daily-update")
async def run_smart_daily_update():
    """
    Smart daily update: Update 100 random products missing today's price data.
    
    This endpoint provides a gentler alternative to full daily updates.
    It randomly selects 100 products that don't have price data for today,
    allowing for distributed updates throughout the day without overwhelming the API.
    """
    try:
        updater = get_daily_updater()
        result = await updater.smart_daily_update()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running smart daily update: {str(e)}")


@app.post("/quick-update")
async def run_quick_update():
    """
    Quick update: Update 10 random products missing today's price data.
    
    This is a smaller, faster alternative for quick price checks.
    """
    try:
        updater = get_daily_updater()
        result = await updater.quick_update()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running quick update: {str(e)}")


@app.post("/daily-update-25")
async def run_daily_update_25():
    """
    Daily update: Update 25 random products missing today's price data.
    
    Perfect for spreading updates throughout the day to gradually build database.
    """
    try:
        updater = get_daily_updater()
        result = await updater.daily_update_25()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running daily update: {str(e)}")


@app.post("/daily-price-update")
async def run_daily_price_update():
    """Update prices for all products currently tracked in the database."""
    try:
        updater = get_daily_updater()
        result = await updater.update_all_products()
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running daily price update: {str(e)}")


@app.post("/generate-dummy-data")
async def generate_dummy_data():
    """Generate dummy historical data for testing (DUMMY products only)."""
    try:
        records_added = generate_dummy_price_history()
        return {
            "message": "Dummy data generated successfully",
            "records_added": records_added
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating dummy data: {str(e)}")


@app.delete("/delete-product/{product_name}")
async def delete_product(product_name: str, retailer: str):
    """Delete all price history for a specific product at a specific retailer."""
    try:
        result = delete_product_history(product_name, retailer)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("Starting simple server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)