# Quick Start: Visitor Tracking

## What Was Added

1. **Visitor Tracking Middleware** (`services/api/middleware/visitor_tracker.py`)
   - Automatically tracks all visitor IPs and country origins
   - Integrated into FastAPI app

2. **CLI Script** (`view_visitors.py`)
   - Command-line tool to view all visitors

3. **API Endpoints** (added to `/v1/monitoring/visitors`)
   - GET `/v1/monitoring/visitors` - List all visitors
   - GET `/v1/monitoring/visitors/stats` - Get statistics
   - GET `/v1/monitoring/visitors/{ip}` - Get specific visitor details

## Quick Usage

### View Visitors via CLI
```bash
# Show all visitors
python view_visitors.py

# Show statistics
python view_visitors.py --stats

# Show specific IP
python view_visitors.py --ip 1.2.3.4
```

### View Visitors via API
```bash
# All visitors
curl http://localhost:8090/v1/monitoring/visitors

# Statistics
curl http://localhost:8090/v1/monitoring/visitors/stats

# Specific IP
curl http://localhost:8090/v1/monitoring/visitors/1.2.3.4
```

## Data Location

Visitor data is stored at:
```
/root/WIP/data/visitors/visitors.json
```

## How It Works

- Every API request automatically tracks the visitor's IP
- Geolocation is looked up (country, city, organization)
- Data is saved to JSON file
- No configuration needed - it's already integrated!

## Next Steps

1. Restart your API server to enable tracking
2. Make some requests to your API
3. Run `python view_visitors.py` to see visitors

That's it! 🎉
