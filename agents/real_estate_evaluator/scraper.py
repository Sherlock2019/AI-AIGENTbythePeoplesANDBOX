# agents/real_estate_evaluator/scraper.py
"""
Web scraper for Vietnamese real estate websites
Scrapes market prices from major Vietnamese real estate portals
"""

import requests
from typing import Dict, List, Optional, Tuple
import logging
import time
import re
from urllib.parse import quote
import json

logger = logging.getLogger(__name__)

# User agent to avoid blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
}


def scrape_batdongsan(city: str, district: str, property_type: str = "apartment") -> Optional[float]:
    """
    Scrape from batdongsan.com.vn
    Returns average price per sqm in USD
    """
    try:
        # Map property types to batdongsan.com.vn URL format
        type_map = {
            "apartment": "can-ho-chung-cu",
            "house": "nha-rieng",
            "villa": "biet-thu",
            "condo": "can-ho-chung-cu",
            "shop": "nha-mat-tien",
            "office": "van-phong",
            "land": "dat",
            "commercial": "nha-mat-tien"
        }
        
        # Map city names
        city_map = {
            "HCMC": "ho-chi-minh",
            "Ho Chi Minh City": "ho-chi-minh",
            "Hanoi": "ha-noi",
            "Ha Noi": "ha-noi",
            "Da Nang": "da-nang",
            "Hue": "hue",
            "Can Tho": "can-tho"
        }
        
        prop_type_url = type_map.get(property_type.lower(), "can-ho-chung-cu")
        city_clean = city_map.get(city, city.lower().replace(" ", "-"))
        
        # Clean district name for URL
        district_clean = district.lower().replace(" ", "-").replace("district", "quan")
        
        # Try multiple URL patterns for batdongsan.com.vn
        url_patterns = [
            f"https://batdongsan.com.vn/{prop_type_url}/ban/{city_clean}/{district_clean}",
            f"https://batdongsan.com.vn/{prop_type_url}/ban-{city_clean}-{district_clean}",
            f"https://batdongsan.com.vn/nha-dat-ban/{city_clean}/{district_clean}",
            f"https://batdongsan.com.vn/{prop_type_url}?city={city_clean}&district={district_clean}",
            f"https://batdongsan.com.vn/tim-kiem?keyword={city_clean}+{district_clean}+{prop_type_url}",
        ]
        
        prices = []
        
        for url in url_patterns:
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                if response.status_code != 200:
                    continue
                
                content = response.text
                
                # Look for price patterns (in VND, convert to USD)
                # Pattern: "X tỷ Y triệu" or "X.Y tỷ" or "X triệu/m²"
                price_patterns = [
                    r'(\d+\.?\d*)\s*tỷ\s*(\d+)?\s*triệu',
                    r'(\d+\.?\d*)\s*tỷ',
                    r'(\d+)\s*triệu/m²',
                    r'(\d+)\s*triệu/m2',
                    r'(\d+)\s*triệu\s*/m²',
                    r'(\d+)\s*triệu\s*/m2',
                    r'Giá[:\s]*(\d+\.?\d*)\s*(tỷ|triệu)',
                    r'price[:\s]*(\d+\.?\d*)\s*(tỷ|triệu)',
                    r'(\d+\.?\d*)\s*billion',
                    r'(\d+)\s*million/m²',
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            if len(match) >= 2:
                                value = float(match[0])
                                unit = match[1].lower() if isinstance(match[1], str) else ""
                                
                                if 'tỷ' in unit or 'billion' in unit:
                                    total_vnd = value * 1_000_000_000
                                else:
                                    total_vnd = value * 1_000_000
                            else:
                                billions = float(match[0])
                                millions = float(match[1]) if len(match) > 1 and match[1] and str(match[1]).isdigit() else 0
                                total_vnd = (billions * 1000 + millions) * 1_000_000
                        else:
                            # Single value - check context
                            value = float(match)
                            # Check surrounding context for unit
                            match_pos = content.lower().find(str(match))
                            context = content[max(0, match_pos-20):match_pos+50].lower()
                            if 'tỷ' in context or 'billion' in context:
                                total_vnd = value * 1_000_000_000
                            else:
                                total_vnd = value * 1_000_000
                        
                        # Convert VND to USD (approximate: 1 USD = 24,000 VND)
                        price_usd = total_vnd / 24_000
                        
                        # Validate price range (per sqm should be reasonable)
                        if 500 < price_usd < 10_000:
                            prices.append(price_usd)
                
                # Also look for JSON-LD structured data
                json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
                json_ld_matches = re.findall(json_ld_pattern, content, re.DOTALL | re.IGNORECASE)
                for json_ld in json_ld_matches:
                    try:
                        data = json.loads(json_ld)
                        if isinstance(data, dict):
                            # Look for price in various formats
                            price_value = None
                            if 'offers' in data:
                                offers = data['offers']
                                if isinstance(offers, dict):
                                    price_value = offers.get('price') or offers.get('priceCurrency')
                                elif isinstance(offers, list) and offers:
                                    price_value = offers[0].get('price') if isinstance(offers[0], dict) else None
                            
                            if not price_value:
                                price_value = data.get('price') or data.get('pricePerSqm') or data.get('price_per_sqm')
                            
                            if price_value:
                                if isinstance(price_value, (int, float)):
                                    # Assume VND if > 1000, USD if < 1000
                                    if price_value > 1000:
                                        price_usd = float(price_value) / 24_000
                                    else:
                                        price_usd = float(price_value)
                                    
                                    if 500 < price_usd < 10_000:
                                        prices.append(price_usd)
                    except json.JSONDecodeError:
                        pass
                
                # Look for data attributes with prices
                data_price_pattern = r'data-price=["\'](\d+\.?\d*)["\']|data-price-per-sqm=["\'](\d+\.?\d*)["\']'
                data_matches = re.findall(data_price_pattern, content, re.IGNORECASE)
                for match in data_matches:
                    price_value = float(match[0] if match[0] else match[1])
                    price_usd = price_value / 24_000 if price_value > 1000 else price_value
                    if 500 < price_usd < 10_000:
                        prices.append(price_usd)
                
                # Look for class-based price elements (common in batdongsan.com.vn)
                class_price_pattern = r'<[^>]*class=["\'][^"]*price[^"]*["\'][^>]*>.*?(\d+\.?\d*)\s*(tỷ|triệu)'
                class_matches = re.findall(class_price_pattern, content, re.DOTALL | re.IGNORECASE)
                for match in class_matches:
                    value = float(match[0])
                    unit = match[1].lower()
                    if 'tỷ' in unit:
                        total_vnd = value * 1_000_000_000
                    else:
                        total_vnd = value * 1_000_000
                    price_usd = total_vnd / 24_000
                    if 500 < price_usd < 10_000:
                        prices.append(price_usd)
                
                # If we found prices, break and use them
                if prices:
                    break
                    
            except Exception as e:
                logger.debug(f"Error trying batdongsan.com.vn URL pattern {url}: {e}")
                continue
        
        if prices:
            # Filter outliers and return average
            filtered_prices = [p for p in prices if 500 < p < 10_000]
            if filtered_prices:
                avg_price = sum(filtered_prices) / len(filtered_prices)
                logger.info(f"Scraped batdongsan.com.vn: {avg_price:.0f} USD/sqm for {city}/{district}")
                return avg_price
        
    except Exception as e:
        logger.warning(f"Error scraping batdongsan.com.vn for {city}/{district}: {e}")
    
    return None


def scrape_muaban(city: str, district: str, property_type: str = "apartment") -> Optional[float]:
    """
    Scrape from muaban.net
    Returns average price per sqm in USD
    """
    try:
        city_clean = city.lower().replace(" ", "-")
        district_clean = district.lower().replace(" ", "-")
        
        # muaban.net structure
        url = f"https://muaban.net/bat-dong-san/{city_clean}/{district_clean}"
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None
        
        content = response.text
        
        # Extract prices (similar pattern)
        price_patterns = [
            r'(\d+\.?\d*)\s*tỷ',
            r'(\d+)\s*triệu/m²',
        ]
        
        prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if 'tỷ' in pattern:
                    total_vnd = float(match) * 1_000_000_000
                else:
                    total_vnd = float(match) * 1_000_000
                
                price_usd = total_vnd / 24_000
                if 500 < price_usd < 10_000:
                    prices.append(price_usd)
        
        if prices:
            return sum(prices) / len(prices)
            
    except Exception as e:
        logger.warning(f"Error scraping muaban for {city}/{district}: {e}")
    
    return None


def scrape_alonhadat(city: str, district: str, property_type: str = "apartment") -> Optional[float]:
    """
    Scrape from alonhadat.com.vn
    Returns average price per sqm in USD
    """
    try:
        city_map = {
            "HCMC": "ho-chi-minh",
            "Hanoi": "ha-noi",
            "Da Nang": "da-nang",
            "Hue": "thua-thien-hue"
        }
        
        city_clean = city_map.get(city, city.lower().replace(" ", "-"))
        district_clean = district.lower().replace(" ", "-").replace("district", "quan")
        
        url = f"https://alonhadat.com.vn/nha-dat/{city_clean}/{district_clean}.html"
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None
        
        content = response.text
        
        # Extract price data
        prices = []
        price_matches = re.findall(r'(\d+\.?\d*)\s*(tỷ|triệu)', content, re.IGNORECASE)
        
        for match in price_matches:
            value = float(match[0])
            unit = match[1].lower()
            
            if 'tỷ' in unit:
                total_vnd = value * 1_000_000_000
            else:
                total_vnd = value * 1_000_000
            
            price_usd = total_vnd / 24_000
            if 500 < price_usd < 10_000:
                prices.append(price_usd)
        
        if prices:
            return sum(prices) / len(prices)
            
    except Exception as e:
        logger.warning(f"Error scraping alonhadat for {city}/{district}: {e}")
    
    return None


def scrape_vietnam_real_estate(city: str, district: str, property_type: str = "apartment") -> Optional[float]:
    """
    Scrape from vietnam-real.estate
    Returns average price per sqm in USD
    """
    try:
        # Map city names to URL format
        city_map = {
            "HCMC": "ho-chi-minh",
            "Ho Chi Minh City": "ho-chi-minh",
            "Hanoi": "ha-noi",
            "Ha Noi": "ha-noi",
            "Da Nang": "da-nang",
            "Hue": "hue",
            "Can Tho": "can-tho"
        }
        
        # Map property types
        type_map = {
            "apartment": "apartments",
            "condo": "apartments",
            "house": "houses",
            "villa": "villas",
            "shop": "commercial",
            "office": "commercial",
            "land": "land"
        }
        
        city_clean = city_map.get(city, city.lower().replace(" ", "-"))
        district_clean = district.lower().replace(" ", "-").replace("district", "quan")
        prop_type_url = type_map.get(property_type.lower(), "apartments")
        
        # Construct search URL - vietnam-real.estate structure
        # Try different URL patterns
        url_patterns = [
            f"https://vietnam-real.estate/{prop_type_url}/{city_clean}/{district_clean}",
            f"https://vietnam-real.estate/{prop_type_url}?city={city_clean}&district={district_clean}",
            f"https://vietnam-real.estate/search?q={city_clean}+{district_clean}+{prop_type_url}",
        ]
        
        prices = []
        
        for url in url_patterns:
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                if response.status_code != 200:
                    continue
                
                content = response.text
                
                # Look for price patterns in various formats
                # Pattern 1: "X tỷ Y triệu" or "X.Y tỷ"
                price_patterns = [
                    r'(\d+\.?\d*)\s*tỷ\s*(\d+)?\s*triệu',
                    r'(\d+\.?\d*)\s*tỷ',
                    r'(\d+)\s*triệu/m²',
                    r'(\d+)\s*triệu/m2',
                    r'(\d+)\s*triệu\s*/m²',
                    r'price[:\s]*(\d+\.?\d*)\s*(tỷ|triệu)',
                    r'(\d+\.?\d*)\s*billion',
                    r'(\d+)\s*million/m²',
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            if len(match) >= 2:
                                billions = float(match[0])
                                millions = float(match[1]) if match[1] and match[1].isdigit() else 0
                                total_vnd = (billions * 1000 + millions) * 1_000_000
                            else:
                                # Check context for unit
                                if 'tỷ' in pattern or 'billion' in pattern.lower():
                                    total_vnd = float(match[0]) * 1_000_000_000
                                else:
                                    total_vnd = float(match[0]) * 1_000_000
                        else:
                            # Single value
                            if 'tỷ' in pattern or 'billion' in pattern.lower():
                                total_vnd = float(match) * 1_000_000_000
                            else:
                                total_vnd = float(match) * 1_000_000
                        
                        # Convert VND to USD (approximate: 1 USD = 24,000 VND)
                        price_usd = total_vnd / 24_000
                        
                        # Also check for direct USD prices
                        usd_pattern = r'\$(\d+\.?\d*)\s*/\s*m²|\$(\d+\.?\d*)\s*per\s*sqm'
                        usd_matches = re.findall(usd_pattern, content, re.IGNORECASE)
                        for usd_match in usd_matches:
                            usd_price = float(usd_match[0] if usd_match[0] else usd_match[1])
                            if 500 < usd_price < 10_000:
                                prices.append(usd_price)
                        
                        # Validate price range (per sqm should be reasonable)
                        if 500 < price_usd < 10_000:
                            prices.append(price_usd)
                
                # Also try to find JSON data in script tags
                script_pattern = r'<script[^>]*>.*?(\{{.*?"price".*?\}}).*?</script>'
                script_matches = re.findall(script_pattern, content, re.DOTALL | re.IGNORECASE)
                for script_match in script_matches:
                    try:
                        data = json.loads(script_match)
                        if isinstance(data, dict):
                            price_value = data.get('price') or data.get('pricePerSqm') or data.get('price_per_sqm')
                            if price_value:
                                if isinstance(price_value, (int, float)):
                                    price_usd = float(price_value) / 24_000 if price_value > 1000 else float(price_value)
                                    if 500 < price_usd < 10_000:
                                        prices.append(price_usd)
                    except json.JSONDecodeError:
                        pass
                
                # If we found prices, break and use them
                if prices:
                    break
                    
            except Exception as e:
                logger.debug(f"Error trying URL pattern {url}: {e}")
                continue
        
        if prices:
            # Return average, filtering outliers
            filtered_prices = [p for p in prices if 500 < p < 10_000]
            if filtered_prices:
                avg_price = sum(filtered_prices) / len(filtered_prices)
                logger.info(f"Scraped vietnam-real.estate: {avg_price:.0f} USD/sqm for {city}/{district}")
                return avg_price
            
    except Exception as e:
        logger.warning(f"Error scraping vietnam-real.estate for {city}/{district}: {e}")
    
    return None


def scrape_market_price(city: str, district: str, property_type: str = "apartment", use_cache: bool = True) -> Optional[float]:
    """
    Scrape market price from multiple Vietnamese real estate websites.
    Returns average price per sqm in USD.
    
    Args:
        city: City name (e.g., "HCMC", "Hanoi")
        district: District name (e.g., "District 1", "Hoan Kiem")
        property_type: Type of property (apartment, house, villa, etc.)
        use_cache: Whether to use cached results
    
    Returns:
        Average price per sqm in USD, or None if scraping fails
    """
    # Cache key
    cache_key = f"{city}_{district}_{property_type}".lower()
    
    # Simple in-memory cache (in production, use Redis or similar)
    if not hasattr(scrape_market_price, '_cache'):
        scrape_market_price._cache = {}
    
    if use_cache and cache_key in scrape_market_price._cache:
        return scrape_market_price._cache[cache_key]
    
    prices = []
    
    # Try multiple sources
    scrapers = [
        ("vietnam-real.estate", scrape_vietnam_real_estate),
        ("batdongsan", scrape_batdongsan),
        ("muaban", scrape_muaban),
        ("alonhadat", scrape_alonhadat),
    ]
    
    for name, scraper_func in scrapers:
        try:
            price = scraper_func(city, district, property_type)
            if price:
                prices.append(price)
                logger.info(f"Scraped {name}: {price:.0f} USD/sqm for {city}/{district}")
        except Exception as e:
            logger.warning(f"Scraper {name} failed: {e}")
        
        # Rate limiting
        time.sleep(0.5)
    
    if prices:
        avg_price = sum(prices) / len(prices)
        scrape_market_price._cache[cache_key] = avg_price
        return avg_price
    
    return None


def batch_scrape_market_prices(properties: List[Dict]) -> Dict[Tuple[str, str], float]:
    """
    Batch scrape market prices for multiple properties.
    
    Args:
        properties: List of property dicts with 'city', 'district', 'property_type'
    
    Returns:
        Dict mapping (city, district) -> average price per sqm
    """
    results = {}
    
    # Group by city/district to avoid duplicate scraping
    locations = {}
    for prop in properties:
        city = str(prop.get("city", "")).strip()
        district = str(prop.get("district", "")).strip()
        prop_type = str(prop.get("property_type", "apartment")).strip()
        
        if city and district:
            key = (city, district, prop_type)
            if key not in locations:
                locations[key] = []
            locations[key].append(prop)
    
    # Scrape each unique location
    for (city, district, prop_type), props in locations.items():
        price = scrape_market_price(city, district, prop_type)
        if price:
            results[(city, district)] = price
    
    return results
