#!/usr/bin/env python3
"""
Australian Supermarket Sale Checker - Command Line Interface

A CLI tool to check if grocery items are on sale at Australian supermarkets.
Supports both Woolworths and Coles with intelligent product matching and caching.
"""

import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from app.services.sale_checker import SaleChecker
from app.settings import settings
from app.utils.validation import validate_items_string, validate_postcode, ValidationError


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    if verbose:
        level = logging.DEBUG
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    else:
        level = logging.WARNING  # Only show warnings and errors by default
        format_str = "%(levelname)s: %(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def format_price(price: Optional[float]) -> str:
    """Format price for display."""
    if price is None:
        return "N/A"
    return f"${price:.2f}"


def format_savings(current: Optional[float], was: Optional[float]) -> str:
    """Format savings amount for display."""
    if current is None or was is None or was <= current:
        return ""
    savings = was - current
    return f"(Save ${savings:.2f})"


def print_table_header() -> None:
    """Print the table header for results."""
    print("\n" + "=" * 120)
    print(f"{'ITEM':<20} {'RETAILER':<12} {'PRODUCT':<35} {'PRICE':<12} {'WAS':<12} {'ON SALE':<8} {'STOCK':<8}")
    print("=" * 120)


def print_result_row(input_item: str, result: dict) -> None:
    """Print a single result row in table format with alternatives and savings."""
    retailer = result['retailer'].title()
    product = result['bestMatch'] or "No match found"
    price = format_price(result['price'])
    was_price = format_price(result['was']) if result.get('was') else ""
    on_sale = "🔥 YES" if result['onSale'] else "No"
    in_stock = "✓ Yes" if result.get('inStock') is True else ("✗ No" if result.get('inStock') is False else "?")
    
    # Truncate long product names
    if len(product) > 33:
        product = product[:30] + "..."
    
    print(f"{input_item:<20} {retailer:<12} {product:<35} {price:<12} {was_price:<12} {on_sale:<8} {in_stock:<8}")
    
    # Show promo text if available and on sale
    if result['onSale'] and result.get('promoText'):
        print(f"{'':<20} {'':<12} 💰 {result['promoText']}")
    
    # Show alternatives if available
    alternatives = result.get('alternatives', [])
    if alternatives:
        print(f"{'':<20} {'':<12} 📦 {len(alternatives)} alternatives available:")
        for i, alt in enumerate(alternatives[:3], 1):  # Show top 3 alternatives
            alt_name = alt.get('name', '')[:50]  # Truncate if too long
            alt_price = format_price(alt.get('price'))
            alt_sale = " 🔥" if alt.get('onSale') else ""
            print(f"{'':<20} {'':<12}    {i}. {alt_name} - {alt_price}{alt_sale}")
    
    # Show potential savings
    potential_savings = result.get('potentialSavings', [])
    if potential_savings:
        print(f"{'':<20} {'':<12} 💡 Potential savings:")
        for saving in potential_savings[:2]:  # Show top 2 savings
            saving_name = saving.get('alternative', '')[:40]  # Truncate if too long
            savings_amount = saving.get('savings', 0)
            percentage = saving.get('percentage', 0)
            print(f"{'':<20} {'':<12}    💰 {saving_name}: Save ${savings_amount:.2f} ({percentage:.1f}%)")
    
    # Add spacing between different input items
    if alternatives or potential_savings:
        print()


def print_json_output(results: dict) -> None:
    """Print results in JSON format."""
    import json
    print(json.dumps(results, indent=2, default=str))


def print_summary(results: dict) -> None:
    """Print a summary of the results."""
    total_results = len(results['results'])
    on_sale_count = sum(1 for r in results['results'] if r['onSale'])
    
    print("\n" + "=" * 120)
    print(f"📊 SUMMARY: Found {total_results} results, {on_sale_count} items on sale")
    print(f"🏪 Postcode: {results['postcode']}")
    print(f"🔍 Items checked: {results['itemsChecked']}")
    
    if on_sale_count > 0:
        print(f"🔥 Items on sale: {on_sale_count}")
        total_savings = 0
        for result in results['results']:
            if result['onSale'] and result.get('price') and result.get('was'):
                total_savings += result['was'] - result['price']
        
        if total_savings > 0:
            print(f"💰 Potential savings: ${total_savings:.2f}")


async def interactive_mode(postcode: str, output_format: str, verbose: bool) -> None:
    """Run interactive mode for continuous item checking."""
    setup_logging(verbose)
    checker = SaleChecker()
    
    # Validate postcode at startup
    postcode_result = validate_postcode(postcode)
    if not postcode_result.is_valid:
        print("❌ Invalid postcode provided:")
        for error in postcode_result.errors:
            print(f"   - {error}")
        print("Please provide a valid Australian postcode (1000-9999)")
        sys.exit(1)
    
    print("🛒 Australian Supermarket Sale Checker - Interactive Mode")
    print("=" * 60)
    print("Enter grocery items to check for sales (or 'quit' to exit)")
    print("Examples: 'milk 2L', 'weet-bix', 'apples'")
    print(f"Using postcode: {postcode}")
    print()
    
    while True:
        try:
            # Get user input
            items_input = input("Enter items to check: ").strip()
            
            if not items_input:
                continue
            
            if items_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            # Validate input
            validation_result = validate_items_string(items_input)
            
            if not validation_result.is_valid:
                print("❌ Input validation errors:")
                for error in validation_result.errors:
                    print(f"   - {error}")
                continue
            
            if validation_result.warnings:
                print("⚠️  Input validation warnings:")
                for warning in validation_result.warnings:
                    print(f"   - {warning}")
            
            # Parse comma-separated items like the API does
            items_list = [item.strip() for item in items_input.split(",") if item.strip()]
                
            # Check the items
            results = await checker.check_items(items_list, postcode)
            
            # Display results
            if output_format == 'json':
                print_json_output(results)
            else:
                print_table_header()
                
                # Group results by input item
                current_item = None
                for result in results['results']:
                    if result['input'] != current_item:
                        current_item = result['input']
                    print_result_row(current_item, result)
                
                print_summary(results)
            
            print()  # Empty line for readability
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            if verbose:
                import traceback
                traceback.print_exc()


async def batch_mode(items: List[str], postcode: str, output_format: str, verbose: bool) -> None:
    """Run batch mode for checking provided items."""
    setup_logging(verbose)
    checker = SaleChecker()
    
    # Validate postcode
    postcode_result = validate_postcode(postcode)
    if not postcode_result.is_valid:
        print("❌ Postcode validation errors:")
        for error in postcode_result.errors:
            print(f"   - {error}")
        sys.exit(1)
    
    # Validate each item
    for i, item in enumerate(items):
        item_result = validate_items_string(item)
        if not item_result.is_valid:
            print(f"❌ Item {i+1} validation errors:")
            for error in item_result.errors:
                print(f"   - {error}")
            sys.exit(1)
        
        if item_result.warnings:
            print(f"⚠️  Item {i+1} validation warnings:")
            for warning in item_result.warnings:
                print(f"   - {warning}")
    
    # Join items into a single string for display, but pass list to checker
    items_str = ", ".join(items)
    
    if verbose:
        print(f"🔍 Checking items: {items_str}")
        print(f"📍 Postcode: {postcode}")
        print()
    
    try:
        # Check the items - pass the list directly
        results = await checker.check_items(items, postcode)
        
        # Display results
        if output_format == 'json':
            print_json_output(results)
        else:
            print_table_header()
            
            # Group results by input item
            current_item = None
            for result in results['results']:
                if result['input'] != current_item:
                    current_item = result['input']
                print_result_row(current_item, result)
            
            print_summary(results)
    
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="sale-checker",
        description="Check if grocery items are on sale at Australian supermarkets",
        epilog="""
Examples:
  %(prog)s --interactive                    # Interactive mode
  %(prog)s milk 2L bread apples            # Check specific items
  %(prog)s "weet-bix" --postcode 2001      # Custom postcode
  %(prog)s milk --format json              # JSON output
  %(prog)s --help                          # Show this help
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Positional arguments for items
    parser.add_argument(
        "items",
        nargs="*",
        help="Grocery items to check (e.g., 'milk 2L', 'bread', 'apples')"
    )
    
    # Options
    parser.add_argument(
        "-p", "--postcode",
        default=settings.DEFAULT_POSTCODE,
        help=f"Australian postcode for location-based search (default: {settings.DEFAULT_POSTCODE})"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)"
    )
    
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Australian Supermarket Sale Checker v0.1.0"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate arguments
    if not args.interactive and not args.items:
        parser.error("Must provide items to check or use --interactive mode")
    
    if args.interactive and args.items:
        parser.error("Cannot use --interactive with item arguments")
    
    # Validate postcode (basic Australian postcode validation)
    if not (args.postcode.isdigit() and len(args.postcode) == 4 and args.postcode.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9'))):
        parser.error(f"Invalid Australian postcode: {args.postcode}")
    
    # Run the appropriate mode
    try:
        if args.interactive:
            asyncio.run(interactive_mode(args.postcode, args.format, args.verbose))
        else:
            asyncio.run(batch_mode(args.items, args.postcode, args.format, args.verbose))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()