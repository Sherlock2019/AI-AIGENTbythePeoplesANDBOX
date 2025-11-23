# Visitor Tracking System

A comprehensive visitor tracking system that captures IP addresses and country origins for all visitors to your API.

## Features

- **Automatic IP Tracking**: Captures IP addresses from all API requests
- **Geolocation**: Determines country, region, city, and organization for each IP
- **Visit Analytics**: Tracks visit counts, first seen, last seen timestamps
- **Path Tracking**: Records which API endpoints each visitor accessed
- **User Agent Tracking**: Captures browser/client information
- **Persistent Storage**: Data is saved to JSON file for persistence
- **API Endpoints**: RESTful API to query visitor data
- **CLI Script**: Command-line tool to view visitors

## How It Works

The visitor tracking system uses middleware that intercepts all incoming requests to your FastAPI application. For each request:

1. Extracts the client IP address (handles proxies via X-Forwarded-For, X-Real-IP headers)
2. Looks up geolocation information (country, city, organization) using free geolocation APIs
3. Stores visitor data in a JSON file at `/root/WIP/data/visitors/visitors.json`
4. Updates visit counts and timestamps

## Usage

### View All Visitors (CLI)

```bash
# Show all visitors in table format
python view_visitors.py

# Show statistics
python view_visitors.py --stats

# Output as JSON
python view_visitors.py --json

# Show details for a specific IP
python view_visitors.py --ip 1.2.3.4
```

### API Endpoints

#### Get All Visitors
```bash
curl http://localhost:8090/v1/monitoring/visitors
```

#### Get Visitor Statistics
```bash
curl http://localhost:8090/v1/monitoring/visitors/stats
```

#### Get Specific Visitor Details
```bash
curl http://localhost:8090/v1/monitoring/visitors/1.2.3.4
```

### Example API Response

```json
{
  "visitors": [
    {
      "ip": "203.0.113.42",
      "country": "United States",
      "country_code": "US",
      "region": "California",
      "city": "San Francisco",
      "org": "Example ISP",
      "isp": "Example ISP",
      "first_seen": "2025-01-15T10:30:00+00:00",
      "last_seen": "2025-01-15T14:22:00+00:00",
      "visit_count": 15,
      "paths_visited": [
        "GET /v1/health",
        "POST /v1/chat",
        "GET /docs"
      ],
      "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      ]
    }
  ],
  "count": 1
}
```

## Data Storage

Visitor data is stored in:
```
/root/WIP/data/visitors/visitors.json
```

The file format is JSON with IP addresses as keys:
```json
{
  "203.0.113.42": {
    "ip": "203.0.113.42",
    "country": "United States",
    "country_code": "US",
    "region": "California",
    "city": "San Francisco",
    "org": "Example ISP",
    "isp": "Example ISP",
    "first_seen": "2025-01-15T10:30:00+00:00",
    "last_seen": "2025-01-15T14:22:00+00:00",
    "visit_count": 15,
    "paths_visited": ["GET /v1/health", "POST /v1/chat"],
    "user_agents": ["Mozilla/5.0..."]
  }
}
```

## Geolocation Services

The system uses free geolocation APIs (no API key required):

1. **ip-api.com** (primary) - Free tier: 45 requests/minute
2. **ipapi.co** (fallback) - Free tier available

For local/private IPs (127.0.0.1, 192.168.x.x, 10.x.x.x), the system marks them as "Local Network" without making API calls.

## Configuration

You can customize the data directory by setting an environment variable:

```bash
export VISITOR_DATA_DIR="/path/to/visitor/data"
```

Default location: `/root/WIP/data/visitors`

## Privacy & Security

- **IP Addresses**: Only IP addresses are stored (no personal information)
- **No Cookies**: Tracking is based solely on IP addresses
- **Local Storage**: Data is stored locally on your server
- **No External Tracking**: No data is sent to third-party analytics services

## Integration

The visitor tracking middleware is automatically enabled when you start your FastAPI application. It's integrated into `services/api/main.py`:

```python
from services.api.middleware.visitor_tracker import VisitorTrackingMiddleware

app.add_middleware(VisitorTrackingMiddleware)
```

## Troubleshooting

### No visitors appearing
- Ensure the API server is running and receiving requests
- Check that the data directory exists and is writable: `/root/WIP/data/visitors`
- Verify middleware is added in `main.py`

### Geolocation not working
- Check internet connectivity (geolocation APIs require internet access)
- Verify firewall allows outbound HTTP requests
- Check API rate limits (ip-api.com: 45 requests/minute)

### Script not working
- Ensure Python path includes project root
- Check that `requests` library is installed: `pip install requests`
- Verify visitor data file exists: `/root/WIP/data/visitors/visitors.json`

## Dependencies

- `requests` - For geolocation API calls
- `fastapi` - Already part of your application
- `starlette` - Already part of your application

Install if needed:
```bash
pip install requests
```

## Example Output

### CLI Table Format
```
IP Address         Country              City                  Organization                    Visits  First Seen            Last Seen
------------------------------------------------------------------------------------------------------------------------------------------------
203.0.113.42       United States        San Francisco         Example ISP                     15      2025-01-15T10:30:00   2025-01-15T14:22:00
198.51.100.10      Canada               Toronto               Another ISP                     8       2025-01-15T11:00:00   2025-01-15T13:45:00
```

### Statistics Output
```
================================================================================
VISITOR STATISTICS
================================================================================
Total Unique Visitors: 42
Total Visits: 156

Visitors by Country:
  United States: 25
  Canada: 8
  United Kingdom: 5
  Germany: 4

Top 10 IPs by Visit Count:
  1. 203.0.113.42      United States        (15 visits)
  2. 198.51.100.10     Canada               (8 visits)
  ...
================================================================================
```

## Notes

- IP addresses are cached to avoid repeated geolocation API calls
- Local/private IPs are automatically detected and marked as "Local Network"
- The system handles proxy headers (X-Forwarded-For, X-Real-IP) for accurate IP detection
- Visit counts increment on each request
- Paths and user agents are tracked per visitor
