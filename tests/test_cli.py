"""
Tests for CLI functionality.
"""
import pytest
import asyncio
import sys
from io import StringIO
from unittest.mock import patch, MagicMock, AsyncMock
from argparse import Namespace

import cli
from app.models import ProductResult


# Only async tests need the asyncio marker


class TestCLIFormatting:
    """Test CLI output formatting functions."""
    
    def test_format_price_with_value(self):
        """Test price formatting with valid value."""
        result = cli.format_price(4.50)
        assert result == "$4.50"
    
    def test_format_price_with_none(self):
        """Test price formatting with None."""
        result = cli.format_price(None)
        assert result == "N/A"
    
    def test_format_savings_with_valid_prices(self):
        """Test savings formatting with valid prices."""
        result = cli.format_savings(4.50, 5.00)
        assert result == "(Save $0.50)"
    
    def test_format_savings_with_no_savings(self):
        """Test savings formatting when no savings."""
        result = cli.format_savings(5.00, 4.50)  # Price increased
        assert result == ""
    
    def test_format_savings_with_none_values(self):
        """Test savings formatting with None values."""
        result = cli.format_savings(None, 5.00)
        assert result == ""
        
        result = cli.format_savings(4.50, None)
        assert result == ""


class TestCLIOutput:
    """Test CLI output functions."""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_table_header(self, mock_stdout):
        """Test table header printing."""
        cli.print_table_header()
        output = mock_stdout.getvalue()
        
        assert "ITEM" in output
        assert "RETAILER" in output
        assert "PRODUCT" in output
        assert "PRICE" in output
        assert "=" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_result_row_on_sale(self, mock_stdout):
        """Test printing result row for item on sale."""
        result = {
            'retailer': 'woolworths',
            'bestMatch': 'Pauls Full Cream Milk 2L',
            'price': 4.50,
            'was': 5.00,
            'onSale': True,
            'inStock': True,
            'promoText': 'Save $0.50'
        }
        
        cli.print_result_row('milk 2L', result)
        output = mock_stdout.getvalue()
        
        assert 'milk 2L' in output
        assert 'Woolworths' in output
        assert 'Pauls Full Cream Milk 2L' in output
        assert '$4.50' in output
        assert '$5.00' in output
        assert '🔥 YES' in output
        assert '✓ Yes' in output
        assert '💰 Save $0.50' in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_result_row_not_on_sale(self, mock_stdout):
        """Test printing result row for item not on sale."""
        result = {
            'retailer': 'coles',
            'bestMatch': 'Coles Milk 2L',
            'price': 4.80,
            'was': None,
            'onSale': False,
            'inStock': False,
            'promoText': None
        }
        
        cli.print_result_row('milk', result)
        output = mock_stdout.getvalue()
        
        assert 'milk' in output
        assert 'Coles' in output
        assert 'No' in output  # Not on sale
        assert '✗ No' in output  # Not in stock
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_json_output(self, mock_stdout):
        """Test JSON output printing."""
        results = {
            'results': [
                {
                    'input': 'milk',
                    'retailer': 'woolworths',
                    'bestMatch': 'Test Milk',
                    'onSale': True,
                    'price': 4.50
                }
            ],
            'postcode': '2000',
            'itemsChecked': 1
        }
        
        cli.print_json_output(results)
        output = mock_stdout.getvalue()
        
        # Should be valid JSON
        import json
        parsed = json.loads(output)
        assert parsed['postcode'] == '2000'
        assert len(parsed['results']) == 1
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_summary(self, mock_stdout):
        """Test summary printing."""
        results = {
            'results': [
                {'onSale': True, 'price': 4.50, 'was': 5.00},
                {'onSale': False, 'price': 3.00, 'was': None},
                {'onSale': True, 'price': 2.50, 'was': 3.00}
            ],
            'postcode': '2001',
            'itemsChecked': 2
        }
        
        cli.print_summary(results)
        output = mock_stdout.getvalue()
        
        assert '📊 SUMMARY' in output
        assert '3 results' in output
        assert '2 items on sale' in output
        assert '2001' in output
        assert '2' in output  # items checked
        assert '$1.00' in output  # total savings (0.50 + 0.50)


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""
    
    def test_basic_items_parsing(self):
        """Test parsing basic item arguments."""
        with patch('sys.argv', ['cli.py', 'milk', 'bread', 'apples']):
            with patch('cli.batch_mode') as mock_batch:  # Prevent actual execution
                cli.main()
                # Verify batch mode was called with correct arguments
                mock_batch.assert_called_once()
    
    def test_interactive_flag(self):
        """Test interactive mode flag."""
        with patch('sys.argv', ['cli.py', '--interactive']):
            with patch('cli.interactive_mode') as mock_interactive:
                cli.main()
                # Verify interactive mode was called
                mock_interactive.assert_called_once()
    
    def test_postcode_validation_valid(self):
        """Test valid postcode validation."""
        with patch('sys.argv', ['cli.py', 'milk', '--postcode', '2000']):
            with patch('cli.batch_mode') as mock_batch:
                cli.main()
                # Verify postcode was passed correctly
                mock_batch.assert_called_once()
    
    def test_postcode_validation_invalid(self):
        """Test invalid postcode validation."""
        with patch('sys.argv', ['cli.py', 'milk', '--postcode', '123']):  # Too short
            with patch('sys.stderr', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    cli.main()
                assert exc_info.value.code != 0  # Should exit with error
    
    def test_format_options(self):
        """Test output format options."""
        with patch('sys.argv', ['cli.py', 'milk', '--format', 'json']):
            with patch('cli.batch_mode') as mock_batch:
                cli.main()
                # Verify format option was passed correctly
                mock_batch.assert_called_once()
    
    def test_verbose_flag(self):
        """Test verbose flag."""
        with patch('sys.argv', ['cli.py', 'milk', '--verbose']):
            with patch('cli.batch_mode') as mock_batch:
                cli.main()
                # Verify verbose flag was passed correctly
                mock_batch.assert_called_once()
    
    def test_version_flag(self):
        """Test version flag."""
        with patch('sys.argv', ['cli.py', '--version']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    cli.main()
                assert 'v0.1.0' in mock_stdout.getvalue()
    
    def test_help_flag(self):
        """Test help flag."""
        with patch('sys.argv', ['cli.py', '--help']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    cli.main()
                output = mock_stdout.getvalue()
                assert 'usage:' in output.lower()
                assert 'examples:' in output.lower()


@pytest.mark.asyncio
class TestBatchMode:
    """Test CLI batch mode functionality."""
    
    @patch('cli.SaleChecker')
    async def test_batch_mode_success(self, mock_checker_class):
        """Test successful batch mode execution."""
        # Mock the sale checker
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.return_value = {
            'results': [
                {
                    'input': 'milk',
                    'retailer': 'woolworths',
                    'bestMatch': 'Test Milk',
                    'onSale': True,
                    'price': 4.50,
                    'was': 5.00,
                    'inStock': True
                }
            ],
            'postcode': '2000',
            'itemsChecked': 1
        }
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.batch_mode(['milk'], '2000', 'table', False)
        
        # Verify checker was called correctly
        mock_checker.check_items.assert_called_once_with(['milk'], '2000')
        
        # Verify output
        output = mock_stdout.getvalue()
        assert 'ITEM' in output  # Table header
        assert 'milk' in output
        assert 'Test Milk' in output
        assert '🔥 YES' in output  # On sale
    
    @patch('cli.SaleChecker')
    async def test_batch_mode_json_output(self, mock_checker_class):
        """Test batch mode with JSON output."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.return_value = {
            'results': [],
            'postcode': '2000',
            'itemsChecked': 0
        }
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.batch_mode(['milk'], '2000', 'json', False)
        
        output = mock_stdout.getvalue()
        # Should be valid JSON
        import json
        parsed = json.loads(output)
        assert parsed['postcode'] == '2000'
    
    @patch('cli.SaleChecker')
    async def test_batch_mode_error_handling(self, mock_checker_class):
        """Test batch mode error handling."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.side_effect = Exception("API Error")
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with pytest.raises(SystemExit) as exc_info:
                await cli.batch_mode(['milk'], '2000', 'table', False)
        
        # Should exit with error code
        assert exc_info.value.code == 1
        assert 'Error: API Error' in mock_stderr.getvalue()
    
    @patch('cli.SaleChecker')
    async def test_batch_mode_multiple_items(self, mock_checker_class):
        """Test batch mode with multiple items."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.return_value = {
            'results': [
                {'input': 'milk', 'retailer': 'woolworths', 'bestMatch': 'Milk', 'onSale': False, 'price': 4.50, 'was': None, 'promoText': None, 'url': None, 'inStock': None},
                {'input': 'milk', 'retailer': 'coles', 'bestMatch': 'Milk', 'onSale': True, 'price': 4.20, 'was': 4.80, 'promoText': 'Save 60c', 'url': None, 'inStock': True},
                {'input': 'bread', 'retailer': 'woolworths', 'bestMatch': 'Bread', 'onSale': False, 'price': 3.00, 'was': None, 'promoText': None, 'url': None, 'inStock': True},
                {'input': 'bread', 'retailer': 'coles', 'bestMatch': 'Bread', 'onSale': False, 'price': 3.20, 'was': None, 'promoText': None, 'url': None, 'inStock': True}
            ],
            'postcode': '2000',
            'itemsChecked': 2
        }
        
        with patch('sys.stdout', new_callable=StringIO):
            await cli.batch_mode(['milk', 'bread'], '2000', 'table', False)
        
        # Should pass items as list
        mock_checker.check_items.assert_called_once_with(['milk', 'bread'], '2000')


@pytest.mark.asyncio  
class TestInteractiveMode:
    """Test CLI interactive mode functionality."""
    
    @patch('cli.SaleChecker')
    @patch('builtins.input')
    async def test_interactive_mode_single_query(self, mock_input, mock_checker_class):
        """Test interactive mode with single query."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.return_value = {
            'results': [
                {
                    'input': 'milk',
                    'retailer': 'woolworths',
                    'bestMatch': 'Test Milk',
                    'onSale': True,
                    'price': 4.50,
                    'was': 5.00,
                    'promoText': 'Save 50c',
                    'url': None,
                    'inStock': True
                }
            ],
            'postcode': '2000',
            'itemsChecked': 1
        }
        
        # Mock user input: query milk, then quit
        mock_input.side_effect = ['milk', 'quit']
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.interactive_mode('2000', 'table', False)
        
        # Verify checker was called
        mock_checker.check_items.assert_called_once_with(['milk'], '2000')
        
        # Verify output contains interactive prompts
        output = mock_stdout.getvalue()
        assert 'Interactive Mode' in output
        assert 'Enter grocery items to check' in output
    
    @patch('cli.SaleChecker')
    @patch('builtins.input')
    async def test_interactive_mode_json_output(self, mock_input, mock_checker_class):
        """Test interactive mode with JSON output."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.return_value = {
            'results': [],
            'postcode': '2000',
            'itemsChecked': 0
        }
        
        mock_input.side_effect = ['milk', 'quit']
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.interactive_mode('2000', 'json', False)
        
        output = mock_stdout.getvalue()
        # Should contain JSON output
        assert '{' in output and '}' in output
    
    @patch('cli.SaleChecker')
    @patch('builtins.input')
    async def test_interactive_mode_empty_input(self, mock_input, mock_checker_class):
        """Test interactive mode handling empty input."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        
        # Mock user input: empty string, then quit
        mock_input.side_effect = ['', 'quit']
        
        with patch('sys.stdout', new_callable=StringIO):
            await cli.interactive_mode('2000', 'table', False)
        
        # Checker should not be called for empty input
        mock_checker.check_items.assert_not_called()
    
    @patch('cli.SaleChecker')
    @patch('builtins.input')
    async def test_interactive_mode_keyboard_interrupt(self, mock_input, mock_checker_class):
        """Test interactive mode handling keyboard interrupt."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        
        # Simulate Ctrl+C
        mock_input.side_effect = KeyboardInterrupt()
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.interactive_mode('2000', 'table', False)
        
        output = mock_stdout.getvalue()
        assert 'Goodbye' in output
    
    @patch('cli.SaleChecker')
    @patch('builtins.input')
    async def test_interactive_mode_error_handling(self, mock_input, mock_checker_class):
        """Test interactive mode error handling."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        mock_checker.check_items.side_effect = Exception("API Error")
        
        mock_input.side_effect = ['milk', 'quit']
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.interactive_mode('2000', 'table', False)
        
        output = mock_stdout.getvalue()
        assert '❌ Error: API Error' in output
    
    @patch('cli.SaleChecker')
    @patch('builtins.input')
    async def test_interactive_mode_quit_variations(self, mock_input, mock_checker_class):
        """Test interactive mode quit command variations."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        
        # Test different quit commands
        for quit_cmd in ['quit', 'exit', 'q', 'QUIT', 'Exit']:
            mock_input.side_effect = [quit_cmd]
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                await cli.interactive_mode('2000', 'table', False)
            
            output = mock_stdout.getvalue()
            assert 'Goodbye' in output


class TestCLISetup:
    """Test CLI setup functions."""
    
    @patch('logging.basicConfig')
    def test_setup_logging_verbose(self, mock_logging):
        """Test verbose logging setup."""
        cli.setup_logging(verbose=True)
        
        mock_logging.assert_called_once()
        call_kwargs = mock_logging.call_args[1]
        assert call_kwargs['level'] == cli.logging.DEBUG
        assert 'asctime' in call_kwargs['format']
    
    @patch('logging.basicConfig')
    def test_setup_logging_normal(self, mock_logging):
        """Test normal logging setup."""
        cli.setup_logging(verbose=False)
        
        mock_logging.assert_called_once()
        call_kwargs = mock_logging.call_args[1]
        assert call_kwargs['level'] == cli.logging.WARNING
        assert 'asctime' not in call_kwargs['format']


@pytest.mark.asyncio
class TestCLIIntegration:
    """Test CLI integration with the service layer."""
    
    @patch('cli.SaleChecker')
    async def test_cli_service_integration(self, mock_checker_class):
        """Test CLI properly integrates with SaleChecker service."""
        mock_checker = AsyncMock()
        mock_checker_class.return_value = mock_checker
        
        # Mock realistic service response
        mock_checker.check_items.return_value = {
            'results': [
                {
                    'input': 'milk 2L',
                    'retailer': 'woolworths',
                    'bestMatch': 'Woolworths Full Cream Milk 2L',
                    'onSale': True,
                    'price': 4.50,
                    'was': 5.00,
                    'promoText': 'Save $0.50',
                    'url': 'https://woolworths.com.au/product/123',
                    'inStock': True
                },
                {
                    'input': 'milk 2L',
                    'retailer': 'coles',
                    'bestMatch': 'Coles Full Cream Milk 2L',
                    'onSale': False,
                    'price': 4.80,
                    'was': None,
                    'promoText': None,
                    'url': 'https://coles.com.au/product/456',
                    'inStock': True
                }
            ],
            'postcode': '2000',
            'itemsChecked': 1
        }
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await cli.batch_mode(['milk 2L'], '2000', 'table', False)
        
        # Verify service was called correctly
        mock_checker.check_items.assert_called_once_with(['milk 2L'], '2000')
        
        # Verify output formatting
        output = mock_stdout.getvalue()
        assert 'Woolworths' in output
        assert 'Coles' in output
        assert '🔥 YES' in output  # Woolworths on sale
        assert 'No' in output  # Coles not on sale (but stock status shows as Yes)
        assert '$4.50' in output  # Woolworths price
        assert '$4.80' in output  # Coles price
        assert 'Save $0.50' in output  # Promo text