# Real Estate Evaluator Agent

## Overview
The Real Estate Evaluator Agent provides interactive market price comparison for Vietnamese real estate properties. It features web scraping from major Vietnamese real estate websites and displays properties on an interactive map with colored price zones.

## Features

### 1. Market Price Lookup
- **Web Scraping**: Automatically scrapes live market prices from:
  - vietnam-real.estate
  - batdongsan.com.vn
  - muaban.net
  - alonhadat.com.vn
- **Static Database**: Fallback to curated neighborhood price database
- **Geolocation Fallback**: Estimates prices based on coordinates if district info is missing

### 2. Price Comparison
- Compares customer wanted price vs market price per sqm
- Calculates price delta percentage
- Evaluation status: "above_market", "at_market", "below_market"
- Confidence score based on data completeness

### 3. Colored Price Zones
Properties are displayed in colored zones based on market price per sqm:
- **Very Low** ($1,000-$2,000): Dark Green (#2d5016)
- **Low** ($2,000-$3,000): Light Green (#73b504)
- **Medium** ($3,000-$4,000): Yellow (#ffcc00)
- **High** ($4,000-$5,000): Orange (#ff6600)
- **Very High** ($5,000+): Red (#ff0000)

### 4. Interactive Map
- 3D extruded buildings showing price ranges
- Clickable markers with detailed popups
- Market price prominently displayed
- Comparison with customer price
- Price delta visualization

## Sample Data

The agent comes with 10 sample properties across Vietnam:
- HCMC: District 1, District 2, Phu Nhuan
- Hanoi: Hoan Kiem, Tay Ho, Cau Giay
- Da Nang: Hai Chau, Son Tra
- Hue: Phu Nhuan

## Usage

### CSV Format
Required columns:
- `address` (optional)
- `city` (required)
- `district` (recommended)
- `property_type` (default: "Apartment")
- `customer_price` (required - total price)
- `area_sqm` (required)
- `lat` (recommended)
- `lon` (recommended)

### Property Types Supported
- Apartment
- Condo
- House
- Villa
- Shop
- Office
- Land Plot
- Factory
- Warehouse

### Web Scraping
Enable/disable web scraping via checkbox in the UI. When enabled, the agent will:
1. Attempt to scrape live prices from Vietnamese real estate websites
2. Fall back to static database if scraping fails
3. Use geolocation estimation as final fallback

## API Endpoints

### POST `/v1/agents/real_estate_evaluator/run/json`
Accepts JSON payload with:
```json
{
  "df": [...],  // Array of property objects
  "params": {
    "use_scraper": true  // Enable web scraping
  }
}
```

Returns:
```json
{
  "run_id": "...",
  "summary": {...},
  "evaluated_df": [...],
  "map_data": [...]
}
```

## Files Structure

```
agents/real_estate_evaluator/
├── __init__.py          # Module exports
├── agent.py            # Main agent entry point
├── runner.py           # Evaluation logic
├── scraper.py          # Web scraping module
├── agent.yaml          # Agent configuration
├── sample_data.csv     # 10 sample properties
└── README.md           # This file
```

## Dependencies

- requests (for web scraping)
- pandas (data processing)
- numpy (calculations)

## Notes

- Web scraping may be rate-limited by websites
- Scraped prices are cached to avoid duplicate requests
- Market prices are converted from VND to USD (approximate rate: 24,000 VND = 1 USD)
- Property type multipliers adjust base prices (e.g., Villa +25%, Factory -30%)
