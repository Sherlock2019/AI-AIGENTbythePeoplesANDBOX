# agents/real_estate_evaluator/runner.py
"""
Real Estate Evaluator runner
Contract: run(df: pd.DataFrame, form_fields: Dict[str, Any]) -> pd.DataFrame

Outputs:
- market_price: float (per sqm from local sources)
- customer_price: float (from input)
- price_delta: float (percentage difference)
- price_range_category: str (color zone category)
- property_type: str
- evaluation_status: "above_market" | "at_market" | "below_market"
- confidence: float (0-100)
"""

from typing import Dict, Any
import math
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Import scraper
try:
    from .scraper import scrape_market_price, batch_scrape_market_prices
    SCRAPER_AVAILABLE = True
except ImportError:
    logger.warning("Web scraper not available, using static data only")
    SCRAPER_AVAILABLE = False
    scrape_market_price = None
    batch_scrape_market_prices = None


# Vietnam neighborhood market price database (simulated local source)
NEIGHBORHOOD_MARKET_PRICES = {
    # HCMC Districts
    ("HCMC", "District 1"): 5200,
    ("HCMC", "District 2"): 3800,
    ("HCMC", "District 3"): 3200,
    ("HCMC", "District 7"): 2900,
    ("HCMC", "Binh Thanh"): 2650,
    ("HCMC", "Phu Nhuan"): 2800,
    ("HCMC", "Tan Binh"): 2400,
    ("HCMC", "District 10"): 2200,
    
    # Hanoi Districts
    ("Hanoi", "Hoan Kiem"): 5800,
    ("Hanoi", "Tay Ho"): 4200,
    ("Hanoi", "Cau Giay"): 3100,
    ("Hanoi", "Ba Dinh"): 3500,
    ("Hanoi", "Ha Dong"): 2200,
    ("Hanoi", "Dong Da"): 2800,
    ("Hanoi", "Hai Ba Trung"): 2600,
    
    # Da Nang Districts
    ("Da Nang", "Hai Chau"): 2350,
    ("Da Nang", "Son Tra"): 1950,
    ("Da Nang", "Ngu Hanh Son"): 1750,
    ("Da Nang", "Lien Chieu"): 1500,
    ("Da Nang", "Thanh Khe"): 1600,
    
    # Hue Districts
    ("Hue", "Phu Nhuan"): 1250,
    ("Hue", "Phu Hoi"): 1150,
    ("Hue", "Truong An"): 1100,
    ("Hue", "Phuoc Vinh"): 1050,
}

# Property type multipliers
PROPERTY_TYPE_MULTIPLIERS = {
    "Apartment": 1.0,
    "Condo": 1.05,
    "House": 1.15,
    "Villa": 1.25,
    "Shop": 1.20,
    "Office": 1.10,
    "Land Plot": 0.85,
    "Factory": 0.70,
    "Warehouse": 0.65,
}


def _fnum(v, default=None):
    """Robust float caster"""
    if v is None:
        return default
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("", "nan", "none", "null"):
            return default
        try:
            return float(s)
        except Exception:
            return default
    try:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
        return float(v)
    except Exception:
        return default


def _get_market_price(row: pd.Series, use_scraper: bool = True) -> float:
    """
    Lookup market price from local source or web scraping based on city/district.
    Falls back to geolocation-based estimation if exact match not found.
    
    Args:
        row: Property data row
        use_scraper: Whether to attempt web scraping first
    """
    city = str(row.get("city", "")).strip()
    district = str(row.get("district", "")).strip()
    neighborhood = str(row.get("neighborhood", "")).strip()
    lat = _fnum(row.get("lat"))
    lon = _fnum(row.get("lon"))
    prop_type = str(row.get("property_type", "Apartment")).strip()
    
    base_price = None
    
    # Try web scraping first if available
    if use_scraper and SCRAPER_AVAILABLE and city and district:
        try:
            scraped_price = scrape_market_price(city, district, prop_type.lower())
            if scraped_price:
                base_price = scraped_price
                logger.info(f"Scraped price for {city}/{district}: ${base_price:.0f}/sqm")
        except Exception as e:
            logger.warning(f"Scraping failed for {city}/{district}: {e}")
    
    # Try exact match from static database
    if base_price is None and city and district:
        key = (city, district)
        if key in NEIGHBORHOOD_MARKET_PRICES:
            base_price = NEIGHBORHOOD_MARKET_PRICES[key]
        elif neighborhood:
            # Try with neighborhood name
            for (c, d), price in NEIGHBORHOOD_MARKET_PRICES.items():
                if c == city and (d.lower() in neighborhood.lower() or neighborhood.lower() in d.lower()):
                    base_price = price
                    break
    
    # Geolocation-based fallback
    if base_price is None and lat is not None and lon is not None:
        # Estimate based on Vietnam regions
        if 10.0 <= lat <= 11.0 and 106.0 <= lon <= 107.0:  # HCMC area
            base_price = 3000
        elif 20.5 <= lat <= 21.5 and 105.0 <= lon <= 106.0:  # Hanoi area
            base_price = 3500
        elif 15.5 <= lat <= 16.5 and 107.5 <= lon <= 108.5:  # Da Nang area
            base_price = 2000
        elif 16.0 <= lat <= 16.8 and 107.0 <= lon <= 108.0:  # Hue area
            base_price = 1200
        else:
            base_price = 2000  # Default
    elif base_price is None:
        base_price = 2500  # Fallback default
    
    # Apply property type multiplier
    multiplier = PROPERTY_TYPE_MULTIPLIERS.get(prop_type, 1.0)
    
    return float(base_price * multiplier)


def _get_price_range_category(price_per_sqm: float) -> str:
    """Categorize price into color zones"""
    if price_per_sqm < 2000:
        return "very_low"  # Green
    elif price_per_sqm < 3000:
        return "low"  # Light green
    elif price_per_sqm < 4000:
        return "medium"  # Yellow
    elif price_per_sqm < 5000:
        return "high"  # Orange
    else:
        return "very_high"  # Red


def _get_color_for_range(category: str) -> str:
    """Get hex color for price range category"""
    colors = {
        "very_low": "#2d5016",
        "low": "#73b504",
        "medium": "#ffcc00",
        "high": "#ff6600",
        "very_high": "#ff0000"
    }
    return colors.get(category, "#808080")


def run(df: pd.DataFrame, form_fields: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Main runner function for real estate evaluation.
    
    Expected input columns:
    - address (optional)
    - city (required for accurate pricing)
    - district (optional but recommended)
    - neighborhood (optional)
    - property_type (default: "Apartment")
    - customer_price (required - total price customer wants)
    - area_sqm (required - property area in square meters)
    - lat (optional but recommended)
    - lon (optional but recommended)
    
    Parameters:
    - use_scraper: bool (default: True) - Whether to use web scraping
    """
    form_fields = form_fields or {}
    df = df.copy()
    
    # Check if scraping is enabled
    use_scraper = form_fields.get("use_scraper", True)
    if isinstance(use_scraper, str):
        use_scraper = use_scraper.lower() in ("true", "1", "yes", "on")
    
    # Ensure required columns exist
    if "area_sqm" not in df.columns:
        df["area_sqm"] = 80.0  # Default 80 sqm
    if "property_type" not in df.columns:
        df["property_type"] = "Apartment"
    if "customer_price" not in df.columns:
        df["customer_price"] = np.nan
    
    # Batch scrape if enabled and available
    if use_scraper and SCRAPER_AVAILABLE and batch_scrape_market_prices:
        try:
            scraped_prices = batch_scrape_market_prices(df.to_dict(orient="records"))
            logger.info(f"Scraped prices for {len(scraped_prices)} locations")
        except Exception as e:
            logger.warning(f"Batch scraping failed: {e}")
            scraped_prices = {}
    else:
        scraped_prices = {}
    
    # Calculate market price per sqm
    # Use scraped prices if available, otherwise fall back to static lookup
    def _get_price_with_scraped(row):
        city = str(row.get("city", "")).strip()
        district = str(row.get("district", "")).strip()
        
        # Check if we have scraped price for this location
        if (city, district) in scraped_prices:
            base_price = scraped_prices[(city, district)]
            prop_type = str(row.get("property_type", "Apartment")).strip()
            multiplier = PROPERTY_TYPE_MULTIPLIERS.get(prop_type, 1.0)
            return float(base_price * multiplier)
        else:
            return _get_market_price(row, use_scraper=use_scraper)
    
    df["market_price_per_sqm"] = df.apply(_get_price_with_scraped, axis=1)
    
    # Calculate customer price per sqm
    area = df["area_sqm"].fillna(80.0).astype(float)
    customer_price = df["customer_price"].fillna(0.0).astype(float)
    df["customer_price_per_sqm"] = np.where(area > 0, customer_price / area, 0.0)
    
    # Calculate price delta (percentage)
    with np.errstate(divide="ignore", invalid="ignore"):
        df["price_delta"] = ((df["customer_price_per_sqm"] - df["market_price_per_sqm"]) / df["market_price_per_sqm"]) * 100.0
    df["price_delta"] = df["price_delta"].replace([np.inf, -np.inf], np.nan).fillna(0.0).round(2)
    
    # Categorize price ranges
    df["price_range_category"] = df["market_price_per_sqm"].apply(_get_price_range_category)
    df["color"] = df["price_range_category"].apply(_get_color_for_range)
    
    # Evaluation status
    def _get_status(row):
        delta = row.get("price_delta", 0.0)
        if delta > 10:
            return "above_market"
        elif delta < -10:
            return "below_market"
        else:
            return "at_market"
    
    df["evaluation_status"] = df.apply(_get_status, axis=1)
    
    # Confidence score (based on data completeness)
    def _calculate_confidence(row):
        score = 50.0  # Base score
        if pd.notna(row.get("city")) and str(row.get("city")).strip():
            score += 20.0
        if pd.notna(row.get("district")) and str(row.get("district")).strip():
            score += 15.0
        if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
            score += 15.0
        return min(score, 100.0)
    
    df["confidence"] = df.apply(_calculate_confidence, axis=1).round(1)
    
    # Ensure lat/lon for mapping
    if "lat" not in df.columns:
        df["lat"] = np.nan
    if "lon" not in df.columns:
        df["lon"] = np.nan
    
    return df


def _generate_zone_polygon(center_lat: float, center_lon: float, radius_km: float = 5.0, num_points: int = 32) -> list:
    """
    Generate a circular polygon around a center point.
    Returns a list of [lon, lat] coordinates forming a closed polygon.
    """
    import math
    
    # Approximate km per degree at Vietnam latitude (~16°N)
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(center_lat))
    
    radius_lat = radius_km / km_per_deg_lat
    radius_lon = radius_km / km_per_deg_lon
    
    polygon = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        lat = center_lat + radius_lat * math.sin(angle)
        lon = center_lon + radius_lon * math.cos(angle)
        polygon.append([lon, lat])
    
    # Close the polygon
    polygon.append(polygon[0])
    return polygon


def generate_zone_data(df: pd.DataFrame) -> list:
    """
    Generate zone data (polygons) for each unique city/district combination
    with market price information for colored zones.
    
    Returns list of zone dictionaries with polygon coordinates and price info.
    """
    zones = []
    
    # District center coordinates (approximate)
    DISTRICT_CENTERS = {
        # HCMC Districts
        ("HCMC", "District 1"): (10.7769, 106.7009),
        ("HCMC", "District 2"): (10.7856, 106.7534),
        ("HCMC", "District 3"): (10.7833, 106.6944),
        ("HCMC", "District 7"): (10.7242, 106.7278),
        ("HCMC", "Binh Thanh"): (10.8040, 106.6950),
        ("HCMC", "Phu Nhuan"): (10.7992, 106.6650),
        ("HCMC", "Tan Binh"): (10.8019, 106.6444),
        ("HCMC", "District 10"): (10.7679, 106.6669),
        
        # Hanoi Districts
        ("Hanoi", "Hoan Kiem"): (21.0285, 105.8542),
        ("Hanoi", "Tay Ho"): (21.0716, 105.8344),
        ("Hanoi", "Cau Giay"): (21.0367, 105.8157),
        ("Hanoi", "Ba Dinh"): (21.0353, 105.8333),
        ("Hanoi", "Ha Dong"): (21.9714, 105.7787),
        ("Hanoi", "Dong Da"): (21.0104, 105.8281),
        ("Hanoi", "Hai Ba Trung"): (21.0104, 105.8542),
        
        # Da Nang Districts
        ("Da Nang", "Hai Chau"): (16.0472, 108.2097),
        ("Da Nang", "Son Tra"): (16.0902, 108.2412),
        ("Da Nang", "Ngu Hanh Son"): (16.0099, 108.2427),
        ("Da Nang", "Lien Chieu"): (16.0377, 108.1546),
        ("Da Nang", "Thanh Khe"): (16.0667, 108.2000),
        
        # Hue Districts
        ("Hue", "Phu Nhuan"): (16.4498, 107.5623),
        ("Hue", "Phu Hoi"): (16.4667, 107.5850),
        ("Hue", "Truong An"): (16.4534, 107.5865),
        ("Hue", "Phuoc Vinh"): (16.4321, 107.5423),
    }
    
    # Get unique city/district combinations from evaluated data
    unique_zones = df.groupby(['city', 'district']).agg({
        'market_price_per_sqm': 'mean',
        'lat': 'mean',
        'lon': 'mean'
    }).reset_index()
    
    for _, row in unique_zones.iterrows():
        city = str(row['city']).strip()
        district = str(row['district']).strip()
        market_price = float(row['market_price_per_sqm'])
        lat = float(row['lat'])
        lon = float(row['lon'])
        
        # Get center from database or use average coordinates
        center_key = (city, district)
        if center_key in DISTRICT_CENTERS:
            center_lat, center_lon = DISTRICT_CENTERS[center_key]
        else:
            center_lat, center_lon = lat, lon
        
        # Determine zone radius based on city (larger cities = larger districts)
        if city in ["HCMC", "Hanoi"]:
            radius_km = 8.0
        elif city in ["Da Nang"]:
            radius_km = 6.0
        else:
            radius_km = 5.0
        
        # Generate polygon
        polygon_coords = _generate_zone_polygon(center_lat, center_lon, radius_km)
        
        # Determine color based on price range
        if market_price < 2000:
            color = "#2d5016"  # Very Low - Dark Green
            price_range = "very_low"
        elif market_price < 3000:
            color = "#73b504"  # Low - Light Green
            price_range = "low"
        elif market_price < 4000:
            color = "#ffcc00"  # Medium - Yellow
            price_range = "medium"
        elif market_price < 5000:
            color = "#ff6600"  # High - Orange
            price_range = "high"
        else:
            color = "#ff0000"  # Very High - Red
            price_range = "very_high"
        
        zones.append({
            "city": city,
            "district": district,
            "market_price": market_price,
            "polygon": polygon_coords,
            "color": color,
            "price_range": price_range,
            "center_lat": center_lat,
            "center_lon": center_lon,
        })
    
    return zones
