"""
Sale prediction algorithm based on historical price data.
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from statistics import mean, median
import re
from .db_config import get_price_history

logger = logging.getLogger(__name__)


class SalePredictor:
    """Predicts future sale dates based on historical patterns."""
    
    def __init__(self):
        self.min_history_days = 14  # Need at least 2 weeks of data
        self.min_sales_count = 2    # Need at least 2 sales to detect pattern
    
    def analyze_sale_patterns(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze historical data to identify sale patterns.
        
        Returns:
            Dict with sale pattern analysis including frequency, duration, etc.
        """
        if len(history) < self.min_history_days:
            return {
                "has_pattern": False,
                "reason": "Insufficient data",
                "confidence": 0.0
            }
        
        # Extract sale periods
        sale_periods = self._extract_sale_periods(history)
        
        if len(sale_periods) < self.min_sales_count:
            return {
                "has_pattern": False,
                "reason": "Not enough sales detected",
                "confidence": 0.0,
                "sale_count": len(sale_periods)
            }
        
        # Calculate sale frequency (days between sales)
        sale_intervals = []
        for i in range(1, len(sale_periods)):
            prev_end = sale_periods[i-1]['end_date']
            current_start = sale_periods[i]['start_date']
            interval = (current_start - prev_end).days
            sale_intervals.append(interval)
        
        if not sale_intervals:
            return {
                "has_pattern": False,
                "reason": "Cannot calculate intervals",
                "confidence": 0.0
            }
        
        # Calculate pattern statistics
        avg_interval = mean(sale_intervals)
        median_interval = median(sale_intervals)
        
        # Calculate sale durations
        sale_durations = [
            (period['end_date'] - period['start_date']).days + 1
            for period in sale_periods
        ]
        avg_duration = mean(sale_durations)
        
        # Calculate confidence based on consistency
        interval_variance = sum((x - avg_interval) ** 2 for x in sale_intervals) / len(sale_intervals)
        interval_std = interval_variance ** 0.5
        
        # Lower variance = higher confidence
        confidence = max(0.0, min(1.0, 1.0 - (interval_std / avg_interval)))
        
        return {
            "has_pattern": True,
            "sale_count": len(sale_periods),
            "avg_interval_days": round(avg_interval, 1),
            "median_interval_days": round(median_interval, 1),
            "avg_duration_days": round(avg_duration, 1),
            "confidence": round(confidence, 2),
            "sale_periods": sale_periods,
            "last_sale": sale_periods[-1] if sale_periods else None
        }
    
    def _extract_sale_periods(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract continuous sale periods from price history."""
        sale_periods = []
        current_period = None
        
        for record in sorted(history, key=lambda x: x['date_recorded']):
            record_date = self._parse_date(record['date_recorded'])
            
            if record['on_sale']:
                if current_period is None:
                    # Start new sale period
                    current_period = {
                        'start_date': record_date,
                        'end_date': record_date,
                        'sale_price': record['price'],
                        'regular_price': record.get('was_price')
                    }
                else:
                    # Extend current sale period
                    current_period['end_date'] = record_date
                    # Update to lowest sale price in period
                    if record['price'] and (current_period['sale_price'] is None or 
                                          record['price'] < current_period['sale_price']):
                        current_period['sale_price'] = record['price']
            else:
                if current_period is not None:
                    # End current sale period
                    sale_periods.append(current_period)
                    current_period = None
        
        # Don't forget the last period if it's still ongoing
        if current_period is not None:
            sale_periods.append(current_period)
        
        return sale_periods
    
    def _parse_date(self, date_str: str) -> date:
        """Parse date string into date object."""
        if isinstance(date_str, date):
            return date_str
        
        # Handle common date formats
        if isinstance(date_str, str):
            # Try ISO format first
            try:
                return date.fromisoformat(date_str)
            except ValueError:
                pass
        
        # Default to today if parsing fails
        return date.today()
    
    def predict_next_sale(self, product_name: str, retailer: str = "woolworths", 
                         days_back: int = 60) -> Dict[str, Any]:
        """
        Predict the next sale for a product based on historical patterns.
        
        Args:
            product_name: Product to analyze
            retailer: Retailer to analyze
            days_back: Days of history to analyze
            
        Returns:
            Dict with prediction details
        """
        try:
            # Get historical data
            history = get_price_history(product_name, retailer, days_back)
            
            if not history:
                return {
                    "has_prediction": False,
                    "reason": "No historical data found",
                    "product_name": product_name,
                    "retailer": retailer
                }
            
            # Analyze patterns
            pattern_analysis = self.analyze_sale_patterns(history)
            
            if not pattern_analysis["has_pattern"]:
                return {
                    "has_prediction": False,
                    "reason": pattern_analysis.get("reason", "No pattern detected"),
                    "product_name": product_name,
                    "retailer": retailer,
                    "analysis": pattern_analysis
                }
            
            # Make prediction based on pattern
            last_sale = pattern_analysis["last_sale"]
            avg_interval = pattern_analysis["avg_interval_days"]
            confidence = pattern_analysis["confidence"]
            
            if not last_sale:
                return {
                    "has_prediction": False,
                    "reason": "No previous sales found",
                    "analysis": pattern_analysis
                }
            
            # Calculate predicted next sale date
            last_sale_end = last_sale["end_date"]
            predicted_date = last_sale_end + timedelta(days=int(avg_interval))
            
            # Calculate days until predicted sale
            days_until = (predicted_date - date.today()).days
            
            # Estimate sale price based on historical sales
            historical_sales = [p for p in pattern_analysis["sale_periods"] if p.get("sale_price")]
            predicted_sale_price = None
            predicted_regular_price = None
            
            if historical_sales:
                sale_prices = [p["sale_price"] for p in historical_sales if p["sale_price"]]
                regular_prices = [p["regular_price"] for p in historical_sales if p.get("regular_price")]
                
                if sale_prices:
                    predicted_sale_price = round(mean(sale_prices), 2)
                if regular_prices:
                    predicted_regular_price = round(mean(regular_prices), 2)
            
            return {
                "has_prediction": True,
                "predicted_sale_date": predicted_date.isoformat(),
                "days_until_sale": days_until,
                "confidence": confidence,
                "predicted_sale_price": predicted_sale_price,
                "predicted_regular_price": predicted_regular_price,
                "estimated_savings": round(predicted_regular_price - predicted_sale_price, 2) if predicted_regular_price and predicted_sale_price else None,
                "analysis": pattern_analysis,
                "product_name": product_name,
                "retailer": retailer
            }
            
        except Exception as e:
            logger.error(f"Error predicting sale for {product_name}: {e}")
            return {
                "has_prediction": False,
                "reason": f"Prediction error: {str(e)}",
                "product_name": product_name,
                "retailer": retailer
            }


def get_sale_prediction(product_name: str, retailer: str = "woolworths") -> Dict[str, Any]:
    """Get sale prediction for a product (convenience function)."""
    predictor = SalePredictor()
    return predictor.predict_next_sale(product_name, retailer)