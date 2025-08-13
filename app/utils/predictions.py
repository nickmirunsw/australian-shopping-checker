"""
Sale prediction analysis for tracked products.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from .db_config import get_price_history
import statistics

logger = logging.getLogger(__name__)

def get_sale_prediction(product_name: str, retailer: str = "woolworths") -> Dict[str, Any]:
    """
    Generate sale prediction for a product based on historical data.
    
    Returns:
        Dict with prediction data including confidence, next sale date, etc.
    """
    try:
        # Get extended price history (1 year)
        history = get_price_history(product_name, retailer, days_back=365)
        
        logger.info(f"Prediction for {product_name}: Found {len(history) if history else 0} historical records")
        
        if not history or len(history) < 3:  # Reduced minimum from 7 to 3 for testing
            return {
                "has_prediction": False,
                "reason": f"Not enough historical data to predict sales (found {len(history) if history else 0} records, need at least 3).",
                "product_name": product_name,
                "retailer": retailer
            }
        
        # Analyze sale patterns
        analysis = analyze_sale_patterns(history)
        
        logger.info(f"Sale analysis for {product_name}: {analysis['sale_count']} sales detected")
        
        if not analysis["has_sales"]:
            return {
                "has_prediction": False,
                "reason": f"No sales detected in historical data. Analyzed {len(history)} records.",
                "product_name": product_name,
                "retailer": retailer,
                "analysis": analysis
            }
        
        # Generate prediction
        prediction = generate_prediction(history, analysis)
        
        return {
            "has_prediction": True,
            "product_name": product_name,
            "retailer": retailer,
            "prediction": prediction,
            "analysis": analysis,
            **prediction  # Flatten prediction into main object for compatibility
        }
        
    except Exception as e:
        logger.error(f"Error generating sale prediction for {product_name}: {e}")
        return {
            "has_prediction": False,
            "reason": f"Error analyzing data: {str(e)}",
            "product_name": product_name,
            "retailer": retailer
        }

def analyze_sale_patterns(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze historical data to find sale patterns."""
    try:
        # Sort history by date
        sorted_history = sorted(history, key=lambda x: x['date_recorded'])
        
        # Find sales (items with was_price or on_sale flag)
        sales = []
        regular_prices = []
        
        for record in sorted_history:
            # Handle different date formats from database
            date_str = record['date_recorded']
            try:
                if isinstance(date_str, str):
                    # Handle ISO format with Z or timezone
                    if 'T' in date_str:
                        date_recorded = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        # Handle simple date format YYYY-MM-DD
                        date_recorded = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    # Handle date objects directly
                    date_recorded = datetime.combine(date_str, datetime.min.time())
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date '{date_str}': {e}")
                continue
                
            price = float(record['price'])
            was_price = float(record['was_price']) if record.get('was_price') else None
            on_sale = bool(record.get('on_sale', False))
            
            if on_sale or was_price:
                sales.append({
                    'date': date_recorded,
                    'price': price,
                    'was_price': was_price,
                    'savings': (was_price - price) if was_price else 0
                })
            else:
                regular_prices.append(price)
        
        if not sales:
            return {
                "has_sales": False,
                "sale_count": 0,
                "avg_interval_days": 0,
                "avg_sale_price": 0,
                "avg_regular_price": statistics.mean(regular_prices) if regular_prices else 0
            }
        
        # Calculate intervals between sales
        intervals = []
        if len(sales) > 1:
            for i in range(1, len(sales)):
                interval = (sales[i]['date'] - sales[i-1]['date']).days
                if interval > 0:  # Avoid same-day duplicates
                    intervals.append(interval)
        
        avg_interval = statistics.mean(intervals) if intervals else 30
        avg_sale_price = statistics.mean([s['price'] for s in sales])
        avg_regular_price = statistics.mean(regular_prices) if regular_prices else avg_sale_price * 1.2
        avg_savings = statistics.mean([s['savings'] for s in sales if s['savings'] > 0])
        
        return {
            "has_sales": True,
            "sale_count": len(sales),
            "avg_interval_days": round(avg_interval, 1),
            "avg_sale_price": round(avg_sale_price, 2),
            "avg_regular_price": round(avg_regular_price, 2),
            "avg_savings": round(avg_savings, 2) if avg_savings else 0,
            "last_sale_date": sales[-1]['date'].isoformat() if sales else None,
            "intervals": intervals
        }
        
    except Exception as e:
        logger.error(f"Error analyzing sale patterns: {e}")
        return {
            "has_sales": False,
            "sale_count": 0,
            "avg_interval_days": 0,
            "avg_sale_price": 0,
            "avg_regular_price": 0
        }

def generate_prediction(history: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate sale prediction based on analysis."""
    try:
        if not analysis["has_sales"]:
            return {
                "confidence": 0.0,
                "estimated_next_sale": "No prediction available",
                "reasoning": "No sales detected in historical data"
            }
        
        # Get last sale date
        last_sale_str = analysis.get("last_sale_date")
        if not last_sale_str:
            return {
                "confidence": 0.1,
                "estimated_next_sale": "Unable to determine",
                "reasoning": "Could not determine last sale date"
            }
        
        # Parse last sale date consistently  
        try:
            if 'T' in last_sale_str:
                last_sale_date = datetime.fromisoformat(last_sale_str.replace('Z', '+00:00'))
            else:
                last_sale_date = datetime.strptime(last_sale_str, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.error(f"Could not parse last sale date '{last_sale_str}': {e}")
            return {
                "confidence": 0.0,
                "estimated_next_sale": "Error parsing date",
                "reasoning": f"Date parsing error: {e}"
            }
        avg_interval = analysis["avg_interval_days"]
        
        # Predict next sale date
        predicted_date = last_sale_date + timedelta(days=avg_interval)
        days_until_sale = (predicted_date - datetime.now()).days
        
        # Calculate confidence based on data consistency
        intervals = analysis.get("intervals", [])
        if len(intervals) < 2:
            confidence = 0.3
            reasoning = f"Limited data: only {analysis['sale_count']} sales detected"
        else:
            # Higher confidence if intervals are consistent
            std_dev = statistics.stdev(intervals) if len(intervals) > 1 else avg_interval
            consistency = 1 - min(std_dev / avg_interval, 1) if avg_interval > 0 else 0
            confidence = min(0.9, 0.4 + (consistency * 0.5))
            reasoning = f"Based on {analysis['sale_count']} sales with average {avg_interval:.1f} day intervals"
        
        # Format prediction
        if days_until_sale < 0:
            estimated_next_sale = "Overdue (predicted sale has passed)"
        elif days_until_sale == 0:
            estimated_next_sale = "Today (predicted)"
        elif days_until_sale == 1:
            estimated_next_sale = "Tomorrow (predicted)"
        elif days_until_sale <= 7:
            estimated_next_sale = f"In {days_until_sale} days ({predicted_date.strftime('%b %d')})"
        else:
            estimated_next_sale = f"In {days_until_sale} days ({predicted_date.strftime('%b %d, %Y')})"
        
        return {
            "confidence": round(confidence, 2),
            "estimated_next_sale": estimated_next_sale,
            "predicted_sale_date": predicted_date.isoformat(),
            "days_until_sale": days_until_sale,
            "predicted_sale_price": analysis["avg_sale_price"],
            "estimated_savings": analysis.get("avg_savings", 0),
            "average_sale_cycle": analysis["avg_interval_days"],
            "reasoning": reasoning
        }
        
    except Exception as e:
        logger.error(f"Error generating prediction: {e}")
        return {
            "confidence": 0.0,
            "estimated_next_sale": "Error generating prediction",
            "reasoning": f"Prediction error: {str(e)}"
        }