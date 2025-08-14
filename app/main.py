from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import asyncio
import time
from typing import Optional
from pydantic import BaseModel
from .models import CheckItemsRequest, CheckItemsResponse, ItemCheckResult, AdminLoginRequest, AdminLoginResponse
from .services.sale_checker import SaleChecker
from .utils.validation import validate_check_request, ValidationError
from .utils.rate_limiting import get_rate_limiter, cleanup_task
from .utils.error_handling import get_error_handler, handle_validation_error, handle_internal_error
from .utils.health_checks import get_system_health, initialize_health_checks
from .utils.metrics import get_metrics_collector, get_metrics_middleware, metrics_calculation_task
from .utils.graceful_degradation import get_degradation_status
from .utils.db_config import get_alternative_products, get_database_stats, clear_all_price_history
from .utils.auth import authenticate_admin, is_admin_authenticated, logout_admin, cleanup_expired_sessions

def extract_session_token(request: Request) -> Optional[str]:
    """Extract session token from Authorization header."""
    session_token = request.headers.get("Authorization")
    if session_token and session_token.startswith("Bearer "):
        return session_token[7:]  # Remove "Bearer " prefix
    return None

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Australian Supermarket Sale Checker",
    version="0.1.0",
    description="Check if grocery items are on sale at Australian supermarkets (Woolworths + Coles)"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize sale checker service
sale_checker = SaleChecker()

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Custom rate limiting middleware."""
    
    async def dispatch(self, request: Request, call_next):
        # Apply different rate limits based on endpoint
        path = request.url.path
        
        if path == "/check":
            limit_type = "check"
        elif path.startswith("/health"):
            limit_type = "global"  # More lenient for health checks
        elif path.startswith("/admin"):
            limit_type = "admin"  # Special rate limit for admin endpoints
        elif path.startswith("/static") or path == "/":
            limit_type = "global"  # Use global limit for static content
        else:
            limit_type = "global"
        
        rate_limiter = get_rate_limiter()
        is_allowed, headers = rate_limiter.check_rate_limit(request, limit_type)
        
        if not is_allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "type": "rate_limit_exceeded"
                },
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
        
        return response

# Add rate limiting middleware (disabled for testing)
# app.add_middleware(RateLimitMiddleware)

# Add metrics middleware  
metrics_middleware = get_metrics_middleware()
app.middleware("http")(metrics_middleware)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    return await handle_internal_error(request, exc, "global_handler")

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation exceptions."""
    return await handle_validation_error(request, [str(exc)], getattr(exc, 'field', None))

# Start cleanup task on startup
@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    initialize_health_checks()
    asyncio.create_task(cleanup_task())
    asyncio.create_task(metrics_calculation_task())
    
    # Cleanup expired admin sessions periodically
    async def admin_session_cleanup():
        while True:
            cleanup_expired_sessions()
            await asyncio.sleep(300)  # Cleanup every 5 minutes
    
    asyncio.create_task(admin_session_cleanup())


@app.get("/")
async def serve_frontend():
    """Serve the main web interface."""
    return FileResponse("static/modern.html")

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "timestamp": time.time()}

@app.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with external dependencies."""
    health_summary = await get_system_health()
    
    return {
        "status": health_summary.status.value,
        "timestamp": health_summary.timestamp,
        "response_time_ms": health_summary.response_time_ms,
        "summary": {
            "total_checks": len(health_summary.checks),
            "healthy": health_summary.healthy_count,
            "degraded": health_summary.degraded_count,
            "unhealthy": health_summary.unhealthy_count
        },
        "checks": [
            {
                "name": check.name,
                "status": check.status.value,
                "response_time_ms": check.response_time_ms,
                "details": check.details,
                "error": check.error,
                "timestamp": check.timestamp
            }
            for check in health_summary.checks
        ]
    }

@app.get("/metrics")
async def get_metrics(time_window: Optional[int] = None):
    """Get system metrics and performance statistics."""
    metrics_collector = get_metrics_collector()
    
    time_window_seconds = time_window * 60 if time_window else None  # Convert minutes to seconds
    metrics_data = metrics_collector.get_all_metrics(time_window_seconds)
    
    return {
        "metrics": metrics_data,
        "time_window_minutes": time_window,
        "collection_info": {
            "max_history": metrics_collector.max_history,
            "uptime_seconds": metrics_data["uptime_seconds"]
        }
    }

@app.get("/status/degradation")
async def get_degradation_status_endpoint():
    """Get current service degradation status."""
    return {
        "degradation_status": get_degradation_status(),
        "timestamp": time.time()
    }

@app.get("/database/stats")
async def get_database_stats_endpoint():
    """Get database statistics including price history and alternatives."""
    return {
        "stats": get_database_stats(),
        "timestamp": time.time()
    }


@app.get("/alternatives/{search_query}")
async def get_alternatives_endpoint(
    search_query: str,
    retailer: Optional[str] = None,
    days_back: Optional[int] = 30
):
    """Get stored alternative products for a search query."""
    try:
        alternatives = get_alternative_products(
            search_query=search_query,
            retailer=retailer,
            days_back=days_back or 30
        )
        
        return {
            "search_query": search_query,
            "retailer": retailer,
            "days_back": days_back or 30,
            "alternatives": alternatives,
            "total_results": len(alternatives),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Failed to get alternatives: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alternatives from database"
        )

@app.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(request_body: AdminLoginRequest):
    """Admin login endpoint."""
    try:
        session_token = authenticate_admin(request_body.username, request_body.password)
        
        if session_token:
            return AdminLoginResponse(
                success=True,
                message="Login successful",
                session_token=session_token
            )
        else:
            return AdminLoginResponse(
                success=False,
                message="Invalid credentials"
            )
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        return AdminLoginResponse(
            success=False,
            message="Login failed due to server error"
        )

@app.post("/admin/logout")
async def admin_logout(request: Request):
    """Admin logout endpoint."""
    try:
        # Get session token from header
        session_token = request.headers.get("Authorization")
        if session_token and session_token.startswith("Bearer "):
            session_token = session_token[7:]  # Remove "Bearer " prefix
        
        if session_token:
            logout_admin(session_token)
            return {"success": True, "message": "Logged out successfully"}
        else:
            return {"success": False, "message": "No active session found"}
    except Exception as e:
        logger.error(f"Admin logout error: {e}")
        return {"success": False, "message": "Logout failed"}

@app.get("/admin/status")
async def admin_status(request: Request):
    """Check admin authentication status."""
    try:
        # Get session token from header
        session_token = request.headers.get("Authorization")
        if session_token and session_token.startswith("Bearer "):
            session_token = session_token[7:]  # Remove "Bearer " prefix
        
        is_authenticated = is_admin_authenticated(session_token)
        
        return {
            "authenticated": is_authenticated,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Admin status check error: {e}")
        return {
            "authenticated": False,
            "timestamp": time.time()
        }

# Helper function to check admin authentication
def require_admin_auth(request: Request) -> bool:
    """Check if request has valid admin authentication."""
    session_token = request.headers.get("Authorization")
    if session_token and session_token.startswith("Bearer "):
        session_token = session_token[7:]  # Remove "Bearer " prefix
    
    return is_admin_authenticated(session_token)

@app.post("/admin/clear-database")
async def admin_clear_database(request: Request):
    """Clear all database data (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        success = clear_all_price_history()
        if success:
            logger.warning("Admin cleared entire database")
            return {"success": True, "message": "Database cleared successfully"}
        else:
            return {"success": False, "message": "Failed to clear database"}
    except Exception as e:
        logger.error(f"Admin database clear error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear database"
        )

@app.post("/admin/generate-dummy-data")
async def admin_generate_dummy_data(request: Request):
    """Generate dummy data for testing (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        # Import dummy data generation here to avoid circular imports
        from .utils.dummy_data import generate_dummy_price_history
        
        records_added = generate_dummy_price_history()
        result = {
            'success': True,
            'products_added': records_added,
            'message': f'Generated {records_added} dummy price records'
        }
        if result['success']:
            logger.info(f"Admin generated {result['products_added']} dummy products")
            return {
                "success": True, 
                "message": f"Generated {result['products_added']} dummy products",
                "details": result
            }
        else:
            return {"success": False, "message": result.get('error', 'Failed to generate dummy data')}
    except Exception as e:
        logger.error(f"Admin dummy data generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate dummy data"
        )

@app.get("/admin/tracked-products")
async def admin_get_tracked_products(request: Request):
    """Get all tracked products (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        from .utils.db_config import get_all_tracked_products
        products = get_all_tracked_products()
        
        return {
            "success": True,
            "products": products,
            "total_products": len(products),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Admin get tracked products error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracked products"
        )

@app.delete("/admin/product/{product_name}/{retailer}")
async def admin_delete_product(request: Request, product_name: str, retailer: str):
    """Delete a specific product's history (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        from .utils.db_config import delete_product_history
        result = delete_product_history(product_name, retailer)
        
        if result['success']:
            logger.info(f"Admin deleted product history: {product_name} at {retailer}")
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result['message']
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete product error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete product"
        )


@app.get("/price-history/{product_name}")
async def get_price_history_endpoint(
    product_name: str,
    retailer: Optional[str] = "woolworths",
    days_back: Optional[int] = 30
):
    """Get price history for a specific product."""
    try:
        from .utils.db_config import get_price_history
        
        history = get_price_history(product_name, retailer, days_back)
        
        return {
            "product_name": product_name,
            "retailer": retailer,
            "days_back": days_back,
            "history": history,
            "total_records": len(history),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Failed to get price history for {product_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve price history"
        )

@app.get("/sale-prediction/{product_name}")
async def get_sale_prediction_endpoint(
    product_name: str,
    retailer: Optional[str] = "woolworths"
):
    """Get sale prediction for a specific product."""
    try:
        from .utils.predictions import get_sale_prediction
        
        prediction = get_sale_prediction(product_name, retailer)
        
        return {
            **prediction,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Failed to get sale prediction for {product_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sale prediction"
        )

# Admin Price History Endpoint  
@app.get("/admin/price-history/{product_name}/{retailer}")
async def admin_get_price_history(product_name: str, retailer: str, request: Request):
    """Admin endpoint to get price history for a specific product."""
    session_token = extract_session_token(request)
    if not is_admin_authenticated(session_token):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    
    try:
        from .utils.db_config import get_price_history
        
        history = get_price_history(product_name, retailer, days_back=365)  # Get full year
        
        if not history:
            return {"success": False, "message": "No price history found"}
            
        return {
            "success": True,
            "history": history,
            "product_name": product_name,
            "retailer": retailer
        }
    except Exception as e:
        logger.error(f"Failed to get admin price history for {product_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve price history")

# Admin Favorites System
@app.post("/admin/favorites")
async def add_favorite(request: Request):
    """Add product to admin favorites."""
    session_token = extract_session_token(request)
    if not is_admin_authenticated(session_token):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    
    try:
        body = await request.json()
        product_name = body.get('product_name')
        retailer = body.get('retailer', 'woolworths')
        
        from .utils.db_config import add_to_favorites
        success = add_to_favorites(product_name, retailer)
        
        if success:
            return {"success": True, "message": "Added to favorites"}
        else:
            return {"success": False, "message": "Product already in favorites or failed to add"}
            
    except Exception as e:
        logger.error(f"Failed to add favorite: {e}")
        return {"success": False, "message": "Failed to add to favorites"}

@app.get("/admin/favorites")
async def get_favorites(request: Request):
    """Get admin favorites list."""
    session_token = extract_session_token(request)
    if not is_admin_authenticated(session_token):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    
    try:
        from .utils.db_config import get_favorites
        favorites = get_favorites()
        
        return {
            "success": True,
            "favorites": favorites
        }
    except Exception as e:
        logger.error(f"Failed to get favorites: {e}")
        return {"success": False, "message": "Failed to load favorites"}

@app.delete("/admin/favorites/{favorite_id}")
async def remove_favorite(favorite_id: int, request: Request):
    """Remove product from admin favorites."""
    session_token = extract_session_token(request)
    if not is_admin_authenticated(session_token):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    
    try:
        from .utils.db_config import remove_from_favorites
        success = remove_from_favorites(favorite_id)
        
        if success:
            return {"success": True, "message": "Removed from favorites"}
        else:
            return {"success": False, "message": "Failed to remove from favorites"}
            
    except Exception as e:
        logger.error(f"Failed to remove favorite: {e}")
        return {"success": False, "message": "Failed to remove from favorites"}

@app.post("/admin/batch-price-update")
async def admin_batch_price_update(
    request: Request,
    batch_size: Optional[int] = 50,
    max_batches: Optional[int] = None
):
    """Run comprehensive batch price update for all products (admin only, for CLI/background use)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        from .utils.daily_updates import get_daily_updater
        
        updater = get_daily_updater()
        result = await updater.update_all_products(
            batch_size=batch_size or 50,
            max_batches=max_batches
        )
        
        if result['success']:
            logger.info(f"Admin initiated comprehensive batch update: {result['stats']}")
            return result
        else:
            return result
            
    except Exception as e:
        logger.error(f"Admin batch price update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run batch price update"
        )

class DailyUpdateRequest(BaseModel):
    batch_size: Optional[int] = 20
    max_batches: Optional[int] = None
    quick_mode: Optional[bool] = False

@app.post("/daily-price-update")
async def daily_price_update(
    request: Request,
    update_params: DailyUpdateRequest = DailyUpdateRequest()
):
    """Run daily price update for tracked products with batching (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    # Extract parameters
    batch_size = update_params.batch_size
    max_batches = update_params.max_batches  
    quick_mode = update_params.quick_mode
    
    # Validate parameters
    if batch_size and (batch_size < 1 or batch_size > 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="batch_size must be between 1 and 100"
        )
    
    # Apply quick mode limitations
    if quick_mode:
        max_batches = min(max_batches or 5, 5)  # Limit to 5 batches in quick mode
        logger.info(f"Quick mode enabled: limiting to {max_batches} batches of {batch_size} products")
    
    if max_batches and (max_batches < 1 or max_batches > 200):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_batches must be between 1 and 200"
        )
    
    try:
        from .utils.daily_updates import get_daily_updater
        
        updater = get_daily_updater()
        result = await updater.update_all_products(
            batch_size=batch_size or 10,
            max_batches=max_batches
        )
        
        if result['success']:
            logger.info(f"Admin initiated batched daily price update: {result['stats']}")
            return result
        else:
            return result
            
    except Exception as e:
        logger.error(f"Admin daily price update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run daily price update"
        )

@app.post("/admin/init-database")
async def admin_init_database(request: Request):
    """Initialize the database with required tables (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        # Import the initialization function
        from .utils.db_config import init_database
        
        init_database()
        
        logger.info("Admin initialized database tables")
        return {
            "success": True, 
            "message": "Database tables initialized successfully"
        }
    except Exception as e:
        logger.error(f"Admin database initialization error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize database: {str(e)}"
        )

@app.get("/admin/debug-db")
async def debug_database(request: Request):
    """Debug database contents (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        from .utils.db_config import get_db_connection
        import psycopg2.extras
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get raw price history count
            cursor.execute("SELECT COUNT(*) as count FROM price_history")
            price_count = cursor.fetchone()['count']
            
            # Get sample price history records
            cursor.execute("SELECT * FROM price_history LIMIT 5")
            sample_price_records = [dict(row) for row in cursor.fetchall()]
            
            # Get distinct products
            cursor.execute("""
                SELECT DISTINCT product_name, retailer 
                FROM price_history 
                LIMIT 10
            """)
            distinct_products = [dict(row) for row in cursor.fetchall()]
            
            # Test the GROUP BY query that get_all_tracked_products uses
            try:
                cursor.execute("""
                    SELECT DISTINCT product_name, retailer, 
                           COUNT(*) as record_count,
                           MIN(date_recorded) as first_seen,
                           MAX(date_recorded) as last_seen
                    FROM price_history 
                    GROUP BY product_name, retailer
                    ORDER BY last_seen DESC
                """)
                grouped_products = [dict(row) for row in cursor.fetchall()]
            except Exception as e:
                grouped_products = {"error": str(e)}
            
            return {
                "success": True,
                "price_history_count": price_count,
                "sample_records": sample_price_records,
                "distinct_products": distinct_products,
                "grouped_products": grouped_products
            }
        
    except Exception as e:
        logger.error(f"Database debug error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug failed: {str(e)}"
        )

@app.post("/admin/bulk-import-data")
async def admin_bulk_import_data(request: Request, data: dict):
    """Bulk import historical data preserving original dates (admin only)."""
    if not require_admin_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    try:
        from .utils.db_config import log_price_data, log_alternative_products
        from datetime import datetime, date
        
        price_records = data.get('price_history', [])
        alt_records = data.get('alternatives', [])
        
        successful_price = 0
        failed_price = 0
        successful_alt = 0
        failed_alt = 0
        
        # Import price history records with original dates
        for record in price_records:
            try:
                # Parse date
                date_recorded = None
                if record.get('date_recorded'):
                    if isinstance(record['date_recorded'], str):
                        date_recorded = datetime.strptime(record['date_recorded'], '%Y-%m-%d').date()
                    else:
                        date_recorded = record['date_recorded']
                
                success = log_price_data(
                    product_name=record['product_name'],
                    retailer=record['retailer'],
                    price=record.get('price'),
                    was_price=record.get('was_price'),
                    on_sale=record.get('on_sale', False),
                    url=record.get('url'),
                    date_recorded=date_recorded
                )
                
                if success:
                    successful_price += 1
                else:
                    failed_price += 1
                    
            except Exception as e:
                logger.error(f"Failed to import price record: {e}")
                failed_price += 1
        
        # Import alternative records (smaller batch)
        current_batch = []
        batch_size = 50
        
        for record in alt_records:
            current_batch.append(record)
            
            if len(current_batch) >= batch_size:
                try:
                    success = log_alternative_products(
                        search_query=record.get('search_query', ''),
                        retailer=record.get('retailer', 'woolworths'),
                        alternatives=current_batch
                    )
                    if success:
                        successful_alt += len(current_batch)
                    else:
                        failed_alt += len(current_batch)
                except Exception as e:
                    logger.error(f"Failed to import alternative batch: {e}")
                    failed_alt += len(current_batch)
                
                current_batch = []
        
        # Process remaining alternatives
        if current_batch:
            try:
                success = log_alternative_products(
                    search_query='bulk_import',
                    retailer='woolworths', 
                    alternatives=current_batch
                )
                if success:
                    successful_alt += len(current_batch)
                else:
                    failed_alt += len(current_batch)
            except Exception as e:
                logger.error(f"Failed to import final alternative batch: {e}")
                failed_alt += len(current_batch)
        
        result = {
            "success": True,
            "message": f"Bulk import completed: {successful_price} price records, {successful_alt} alternatives imported",
            "stats": {
                "price_records": {
                    "successful": successful_price,
                    "failed": failed_price,
                    "total": len(price_records)
                },
                "alternatives": {
                    "successful": successful_alt,
                    "failed": failed_alt,
                    "total": len(alt_records)
                }
            }
        }
        
        logger.info(f"Admin bulk import completed: {result['message']}")
        return result
        
    except Exception as e:
        logger.error(f"Admin bulk import error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk import failed: {str(e)}"
        )

@app.post("/check", response_model=CheckItemsResponse)
async def check_items(request_body: CheckItemsRequest, request: Request):
    """
    Check if items are on sale at Australian supermarkets.
    
    Returns results for both Woolworths and Coles, showing the best match
    for each item at each retailer along with sale information.
    """
    # Validate input
    validation_result = validate_check_request(request_body)
    
    if not validation_result.is_valid:
        return await handle_validation_error(
            request=request,
            validation_errors=validation_result.errors
        )
    
    # Log warnings if any
    if validation_result.warnings:
        logger.info(
            "Request validation passed with warnings",
            extra={
                "items": request_body.items,
                "postcode": request_body.postcode,
                "warnings": validation_result.warnings
            }
        )
    
    # Parse comma-separated items
    items = [item.strip() for item in request_body.items.split(",") if item.strip()]
    
    try:
        # Use the sale checker service
        results = await sale_checker.check_items(items, request_body.postcode)
        
        # Convert to response model format
        response_results = []
        for result in results["results"]:
            response_results.append(ItemCheckResult(**result))
        
        logger.info(
            "Successfully processed request",
            extra={
                "items_count": len(items),
                "postcode": request_body.postcode,
                "results_count": len(response_results)
            }
        )
        
        return CheckItemsResponse(
            results=response_results,
            postcode=results["postcode"],
            itemsChecked=results["itemsChecked"]
        )
        
    except ValidationError as e:
        return await handle_validation_error(request, [str(e)])
    except Exception as e:
        return await handle_internal_error(request, e, "check_items")