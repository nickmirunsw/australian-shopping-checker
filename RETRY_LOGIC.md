# Retry Logic Documentation

## Overview

The Australian Supermarket Sale Checker implements a robust HTTP retry mechanism to handle transient network failures and API unavailability. This document describes the retry strategy, configuration options, and best practices implemented in the system.

## Retry Strategy

### Exponential Backoff

The system uses exponential backoff with the following pattern:
- **Attempt 1**: Immediate request
- **Attempt 2**: Wait 1 second, then retry
- **Attempt 3**: Wait 2 seconds, then retry
- **Attempt 4**: Wait 4 seconds, then retry

Formula: `wait_time = (2 ** attempt) * backoff_factor`

### Retryable Conditions

The system will retry requests under the following conditions:

#### HTTP Status Codes (Retryable)
- `429` - Too Many Requests (rate limiting)
- `500` - Internal Server Error
- `502` - Bad Gateway 
- `503` - Service Unavailable
- `504` - Gateway Timeout

#### HTTP Status Codes (Non-Retryable)
- `200` - Success (no retry needed)
- `400` - Bad Request (client error, won't change on retry)
- `401` - Unauthorized (authentication issue)
- `403` - Forbidden (permission issue) 
- `404` - Not Found (resource doesn't exist)
- All other 4xx codes (client errors)

#### Network Exceptions (Retryable)
- `httpx.TimeoutException` - Request timeout
- `httpx.ConnectError` - Connection failed
- `httpx.NetworkError` - General network issues

#### Network Exceptions (Non-Retryable)
- `httpx.HTTPError` - General HTTP errors (logged but not retried)
- Generic `Exception` - Unexpected errors (logged but not retried)

## Configuration

### Default Settings

```python
max_retries = 3              # Maximum number of attempts (including initial)
timeout = 30.0               # Request timeout in seconds
backoff_factor = 1.0         # Multiplier for exponential backoff
```

### Customization

The retry behavior can be customized per request:

```python
# Custom retry configuration
data = await adapter._retry_request_with_backoff(
    client=client,
    url=url,
    params=params,
    query=query,
    postcode=postcode,
    max_retries=5,           # More retries for critical requests
    timeout=45.0,            # Longer timeout
    backoff_factor=1.5       # More aggressive backoff
)
```

## Implementation Details

### Base Class Method

All retry logic is implemented in `BaseAdapter._retry_request_with_backoff()`:

```python
async def _retry_request_with_backoff(
    self, 
    client: httpx.AsyncClient, 
    url: str, 
    params: Dict[str, Any], 
    query: str, 
    postcode: str, 
    max_retries: int = 3,
    timeout: float = 30.0,
    backoff_factor: float = 1.0
) -> Optional[Dict[str, Any]]:
```

### Adapter Integration

Each retailer adapter (Woolworths, Coles) wraps this method:

```python
async def _retry_request(self, client, url, params, query, postcode, max_retries=3):
    return await self._retry_request_with_backoff(
        client=client,
        url=url, 
        params=params,
        query=query,
        postcode=postcode,
        max_retries=max_retries,
        timeout=30.0,
        backoff_factor=1.0
    )
```

## Logging

### Structured Logging Fields

All retry attempts include structured logging with these fields:

```json
{
    "query": "milk 2L",
    "postcode": "2000", 
    "retailer": "woolworths",
    "status_code": 500,
    "latency": 1.234,
    "attempt": 2,
    "url": "https://api.example.com/search",
    "retry_delay": 2.0,
    "error_type": "server_error",
    "retryable": true
}
```

### Log Levels

- **INFO**: Successful requests (200 responses)
- **WARNING**: Retryable failures (will retry)  
- **ERROR**: Non-retryable failures or max retries reached

### Example Log Messages

```
INFO: HTTP request successful
WARNING: Request failed with retryable status 503, retrying in 2.0s
WARNING: Request timed out after 30.0s, retrying in 1.0s  
ERROR: Max retries reached for status 500
ERROR: Request failed with non-retryable status 404
```

## Error Handling

### JSON Parsing

Even successful HTTP requests (200) can fail during JSON parsing:

```python
try:
    return response.json()
except Exception as json_error:
    logger.error(
        f"Failed to parse JSON response: {json_error}",
        extra={**log_extra, "parse_error": str(json_error)}
    )
    return None
```

### Network Isolation

Different network error types are handled with specific logging:

- **Timeout**: Includes timeout duration and latency
- **Connection**: Includes connection details
- **Network**: General network error information

## Performance Considerations

### Total Request Time

With default settings, the maximum time for a failed request:
- Attempt 1: 30s timeout + 1s wait = 31s
- Attempt 2: 30s timeout + 2s wait = 32s  
- Attempt 3: 30s timeout = 30s
- **Total: ~93 seconds maximum**

### Backoff Benefits

Exponential backoff helps:
- Reduce server load during outages
- Improve success rate for transient issues
- Spread retry attempts over time
- Comply with rate limiting policies

## Testing

### Unit Tests

The retry logic includes comprehensive tests for:
- Successful requests (no retries)
- Retryable errors with eventual success
- Non-retryable errors (immediate failure)
- Timeout handling
- Network error handling
- Max retries behavior
- Logging verification

### Test Examples

```python
# Test retry on 503 with eventual success
respx.get(url).mock(side_effect=[
    httpx.Response(503),    # First attempt fails
    httpx.Response(503),    # Second attempt fails  
    httpx.Response(200, json={"data": "success"})  # Third succeeds
])

# Test non-retryable 404
respx.get(url).mock(return_value=httpx.Response(404))

# Test timeout with retries
def timeout_then_success(request):
    if not hasattr(timeout_then_success, 'calls'):
        timeout_then_success.calls = 0
    timeout_then_success.calls += 1
    
    if timeout_then_success.calls <= 2:
        raise httpx.TimeoutException("Timeout")
    return httpx.Response(200, json={"data": "success"})
```

## Monitoring

### Metrics to Track

For production monitoring, track these metrics:
- Retry attempt distribution (1st, 2nd, 3rd attempt success rates)
- Request latency by attempt number
- Error type frequency (timeout, 5xx, network)
- Retry success rate by retailer
- Total request duration including retries

### Alerts

Consider alerts for:
- High retry rate (>50% of requests requiring retries)
- Frequent max retries reached
- Unusual error patterns
- Retailer-specific issues

## Best Practices

### When to Adjust Settings

**Increase max_retries:**
- Critical business operations
- Known intermittent issues
- High-latency networks

**Increase timeout:**  
- Large response payloads
- Slow retailer APIs
- High-latency networks

**Adjust backoff_factor:**
- Rate limiting issues (increase to 1.5-2.0)
- Fast recovery expected (decrease to 0.5)

### Circuit Breaker Pattern

Consider implementing circuit breaker pattern for:
- Extended outages (>5 minutes)
- Systematic failures (>90% error rate)
- Cascade failure prevention

### Cache Integration

The retry logic works seamlessly with caching:
- Cache misses trigger retries as needed
- Failed requests still cache empty results
- Cached responses bypass retry logic entirely

## Troubleshooting

### Common Issues

**High retry rates:**
- Check retailer API status
- Review rate limiting policies  
- Verify network connectivity
- Check timeout settings

**Timeout issues:**
- Monitor response times
- Check network latency
- Consider increasing timeout
- Verify server capacity

**Parsing errors:**
- Check API response format changes
- Verify content-type headers
- Review API documentation
- Test with API directly

### Debug Logging

Enable debug logging to see detailed retry behavior:

```python
import logging
logging.getLogger('app.adapters').setLevel(logging.DEBUG)
```

This will show all retry attempts, delays, and decision points in the retry process.