# Woolworths Price Checker

A FastAPI service that checks grocery item prices and sales at Woolworths Australia.

## Installation (macOS)

### Using uv (recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <repo-url>
cd australian-supermarket-checker

# Install dependencies
uv sync

# Copy environment file
cp .env.example .env

# Optional: Install Playwright for web scraping fallback
uv run playwright install chromium
```

### Using pip + venv

```bash
# Clone and setup
git clone <repo-url>
cd australian-supermarket-checker

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Optional: Install Playwright for web scraping fallback
pip install playwright
playwright install chromium
```

## Running the Service

### FastAPI Web Server

Using uv:
```bash
uv run uvicorn app.main:app --reload
```

Using pip:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

The service will be available at http://127.0.0.1:8000

### Command Line Interface

The CLI provides both interactive and batch modes for checking grocery sales.

Using uv:
```bash
uv run python cli.py --help
```

Using pip:
```bash
source venv/bin/activate
python cli.py --help
```

Or if installed as a package:
```bash
sale-checker --help
```

## Testing

### Health Check
```bash
curl http://127.0.0.1:8000/health
```

Expected response:
```json
{"status": "ok"}
```

### Running Tests
```bash
# Using uv
uv run pytest

# Using pip
pytest
```

## API Endpoints

### Health Check
- `GET /health` - Health check endpoint
- `GET /health/detailed` - Detailed health check with external dependencies

### Check Items for Sales
- `POST /check` - Check items for prices and sales at Woolworths

### Database and Analytics
- `GET /database/stats` - Get database statistics including price history and alternatives
- `GET /alternatives/{search_query}` - Get stored alternative products for a search query
  - Query parameters:
    - `retailer` (optional): Filter by specific retailer
    - `days_back` (optional): Number of days of history to retrieve (default: 30)

### Metrics and Monitoring
- `GET /metrics` - Get system metrics and performance statistics
- `GET /status/degradation` - Get current service degradation status

### Admin Authentication (Protected Endpoints)
- `POST /admin/login` - Admin login (username: `admin`, password: `password`)
- `POST /admin/logout` - Admin logout
- `GET /admin/status` - Check admin authentication status
- `POST /admin/clear-database` - Clear all database data (⚠️ Admin only)
- `POST /admin/generate-dummy-data` - Generate test data (Admin only)
- `GET /admin/tracked-products` - Get all tracked products (Admin only)
- `DELETE /admin/product/{product_name}/{retailer}` - Delete specific product history (Admin only)

#### Request Format
```json
{
    "items": "milk 2L, weet-bix, granny smith",
    "postcode": "2101"
}
```

#### Response Format
```json
{
    "results": [
        {
            "input": "milk 2L",
            "retailer": "woolworths",
            "bestMatch": "Woolworths Full Cream Milk 2L",
            "onSale": true,
            "price": 4.50,
            "was": 5.00,
            "promoText": "Save 50c",
            "url": "https://woolworths.com.au/product/123",
            "inStock": true
        }
    ],
    "postcode": "2101",
    "itemsChecked": 1
}
```

#### Example Usage

**Single Item:**
```bash
curl -X POST http://127.0.0.1:8000/check \
  -H 'Content-Type: application/json' \
  -d '{"items":"milk 2L","postcode":"2000"}'
```

**Multiple Items:**
```bash
curl -X POST http://127.0.0.1:8000/check \
  -H 'Content-Type: application/json' \
  -d '{"items":"milk 2L, weet-bix, granny smith","postcode":"2101"}'
```

**Health Check:**
```bash
curl http://127.0.0.1:8000/health
```

## CLI Usage Examples

### Interactive Mode

Start interactive mode to check items continuously:
```bash
python cli.py --interactive
```

Example session:
```
🛒 Australian Supermarket Sale Checker - Interactive Mode
============================================================
Enter grocery items to check for sales (or 'quit' to exit)
Examples: 'milk 2L', 'weet-bix', 'apples'
Using postcode: 2000

Enter items to check: milk 2L, bread
========================================================================================================================
ITEM                 RETAILER     PRODUCT                             PRICE        WAS          ON SALE  STOCK   
========================================================================================================================
milk 2L              Woolworths   Woolworths Full Cream Milk 2L       $4.50        $5.00        🔥 YES   ✓ Yes   
💰 Save $0.50
bread                Woolworths   Woolworths White Bread 680g         $2.80                     No       ✓ Yes   

========================================================================================================================
📊 SUMMARY: Found 2 results, 1 items on sale
🏪 Postcode: 2000
🔍 Items checked: 2
🔥 Items on sale: 1
💰 Potential savings: $0.50

Enter items to check: quit
👋 Goodbye!
```

### Batch Mode

Check specific items with command line arguments:
```bash
# Single item
python cli.py "milk 2L"

# Multiple items
python cli.py "milk 2L" "bread" "apples"

# Custom postcode
python cli.py "milk 2L" --postcode 2001

# JSON output format
python cli.py "milk 2L" --format json

# Verbose logging
python cli.py "milk 2L" --verbose
```

### CLI Options

- `-p, --postcode`: Australian postcode (default: 2000)
- `-f, --format`: Output format - `table` or `json` (default: table)
- `-i, --interactive`: Run in interactive mode
- `-v, --verbose`: Enable verbose logging
- `--version`: Show version information
- `-h, --help`: Show help message

#### Response Fields

- `input`: Original search term
- `retailer`: "woolworths" 
- `bestMatch`: Name of best matching product (null if no good match)
- `onSale`: Boolean indicating if product is on sale
- `price`: Current price (null if not available)
- `was`: Previous/regular price (null if not on sale or not available)
- `promoText`: Promotional text like "Save $0.50" (null if none)
- `url`: Direct link to product page (null if not available)
- `inStock`: Stock availability (null if unknown)

## Playwright Web Scraping Fallback

When API endpoints are unavailable or fail, the service can automatically fallback to web scraping using Playwright browser automation. This provides additional resilience for retrieving product information.

### Setup Playwright Fallback

1. **Install Playwright** (if not already installed):
   ```bash
   # Using uv
   uv add playwright
   uv run playwright install chromium
   
   # Using pip
   pip install playwright
   playwright install chromium
   ```

2. **Enable Playwright Fallback** in your `.env` file:
   ```bash
   # Enable Playwright fallback when APIs fail
   ENABLE_PLAYWRIGHT_FALLBACK=true
   
   # Run browser in headless mode (recommended for production)
   PLAYWRIGHT_HEADLESS=true
   
   # Browser timeout in milliseconds
   PLAYWRIGHT_TIMEOUT=30000
   ```

### How Playwright Fallback Works

1. **Primary Method**: The service first attempts to use retailer APIs for product searches
2. **Automatic Fallback**: If APIs fail or return errors, Playwright automatically launches a browser
3. **Web Scraping**: The browser navigates to retailer websites and extracts product information
4. **Data Extraction**: Product details are parsed from the webpage DOM using robust selectors
5. **Return Results**: Extracted data is returned in the same format as API results

### Benefits

- **Resilience**: Service continues working even when APIs are down
- **Coverage**: Access to product data that may not be available via APIs
- **Consistency**: Same response format whether using APIs or web scraping

### Performance Considerations

- **Slower**: Web scraping is inherently slower than API calls
- **Resource Usage**: Requires more CPU and memory for browser automation
- **Caching**: Results are cached to minimize repeated browser operations

### Configuration Options

All Playwright settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_PLAYWRIGHT_FALLBACK` | `false` | Enable/disable Playwright fallback |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser in headless mode |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Browser timeout in milliseconds |

## Project Structure

```
app/
├── main.py              # FastAPI app
├── settings.py          # Settings loader
├── models.py           # Pydantic models
├── adapters/           # Retailer adapters
│   ├── base.py         # Base adapter interface
│   ├── woolworths.py   # Woolworths adapter
│   ├── coles.py        # Coles adapter
│   └── playwright_fallback.py # Web scraping fallback adapters
├── services/           # Business logic
│   └── sale_checker.py # Sale checking service
└── utils/              # Utilities
    └── cache.py        # Caching utilities
tests/                  # Test files
pyproject.toml          # Project dependencies
.env.example           # Environment variables template
```