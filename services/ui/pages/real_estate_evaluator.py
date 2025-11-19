#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏠 Real Estate Evaluator Agent — Interactive Map with Market Price Comparison
Author: AI Assistant
Version: 2025-11-10

Features:
- CSV upload with asset list (address, type, customer price, coordinates)
- Interactive MapLibre map with colored zones per price range
- Market price lookup from local sources
- Comparison between customer wanted price vs market price
- Support for different real estate types
- Two map versions: Standard and Ultra 3D
"""

import os
import io
import json
import math
from datetime import datetime
from typing import Any, Dict, List
import requests
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go

from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    get_palette,
    get_theme,
    render_theme_toggle,
)

# Page config
st.set_page_config(page_title="Real Estate Evaluator", layout="wide")
ss = st.session_state

API_URL = os.getenv("API_URL", "http://localhost:8090")

# Apply theme
apply_global_theme()

# Session defaults
def _init_defaults():
    ss.setdefault("re_evaluated_df", None)
    ss.setdefault("re_map_data", None)
    ss.setdefault("re_zone_data", None)
    ss.setdefault("re_summary", None)
    ss.setdefault("re_uploaded_file", None)
    ss.setdefault("re_auto_loaded", False)
    ss.setdefault("re_auto_evaluated", False)

_init_defaults()

# ============================================================================
# MAP GENERATION FUNCTIONS (defined early to avoid NameError)
# ============================================================================

def _generate_standard_map(map_data, zone_data, assets_geojson, zones_geojson, theme="dark"):
    """Generate standard map HTML with theme support"""
    palette = get_palette(theme)
    is_dark = theme == "dark"
    bg_color = palette['bg'] if is_dark else "#ffffff"
    text_color = palette['text'] if is_dark else "#000000"
    legend_bg = palette['card'] if is_dark else "rgba(255, 255, 255, 0.95)"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Real Estate Map - Market Price Zones</title>
        <script src='https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js'></script>
        <link href='https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css' rel='stylesheet' />
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: {bg_color};
                color: {text_color};
            }}
            #map {{
                width: 100%;
                height: 600px;
                border-radius: 10px;
            }}
            .legend {{
                position: absolute;
                bottom: 20px;
                left: 20px;
                z-index: 1000;
                padding: 15px;
                border-radius: 10px;
                background: {legend_bg};
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                min-width: 220px;
                color: {text_color};
            }}
            .legend h4 {{
                margin-bottom: 10px;
                font-size: 14px;
                font-weight: bold;
                color: {text_color};
            }}
            .legend-item {{
                display: flex;
                align-items: center;
                margin-bottom: 5px;
                font-size: 12px;
            }}
            .color-box {{
                width: 20px;
                height: 15px;
                margin-right: 8px;
                border-radius: 3px;
                border: 1px solid rgba(0,0,0,0.2);
            }}
            .popup-content {{
                font-family: inherit;
                min-width: 250px;
                color: {text_color};
            }}
            .popup-content h4 {{
                margin-bottom: 8px;
                color: #f5576c;
                font-size: 16px;
            }}
            .popup-content p {{
                margin: 4px 0;
                font-size: 13px;
                color: {text_color};
            }}
            .popup-content .price {{
                font-size: 18px;
                font-weight: bold;
                color: #f5576c;
            }}
            .popup-content .market-price {{
                font-size: 16px;
                font-weight: bold;
                color: #22c55e;
            }}
            .popup-content .delta {{
                font-size: 14px;
                font-weight: bold;
            }}
            .popup-content .delta.positive {{
                color: #ef4444;
            }}
            .popup-content .delta.negative {{
                color: #22c55e;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="legend">
            <h4>💰 Market Price per sqm</h4>
            <div class="legend-item"><div class="color-box" style="background: #2d5016;"></div>$1,000 - $2,000</div>
            <div class="legend-item"><div class="color-box" style="background: #73b504;"></div>$2,000 - $3,000</div>
            <div class="legend-item"><div class="color-box" style="background: #ffcc00;"></div>$3,000 - $4,000</div>
            <div class="legend-item"><div class="color-box" style="background: #ff6600;"></div>$4,000 - $5,000</div>
            <div class="legend-item"><div class="color-box" style="background: #ff0000;"></div>$5,000+</div>
        </div>
        
        <script>
            const assetsData = {json.dumps(assets_geojson)};
            const zonesData = {json.dumps(zones_geojson)};
            
            const mapStyle = {json.dumps('https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json' if is_dark else 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json')};
            
            // Calculate bounding box from assets
            const calculateBounds = (features) => {{
                if (!features || features.length === 0) return null;
                let minLon = Infinity, maxLon = -Infinity;
                let minLat = Infinity, maxLat = -Infinity;
                features.forEach(f => {{
                    const [lon, lat] = f.geometry.coordinates;
                    minLon = Math.min(minLon, lon);
                    maxLon = Math.max(maxLon, lon);
                    minLat = Math.min(minLat, lat);
                    maxLat = Math.max(maxLat, lat);
                }});
                return [[minLon, minLat], [maxLon, maxLat]];
            }};
            
            const map = new maplibregl.Map({{
                container: 'map',
                style: mapStyle,
                center: [107.5, 16.0],
                zoom: 5.5,
                pitch: 60,
                bearing: -20
            }});
            
            map.addControl(new maplibregl.NavigationControl(), 'top-left');
            
            map.on('load', () => {{
                // Add price zone polygons source
                map.addSource('price-zones', {{
                    type: 'geojson',
                    data: zonesData
                }});
                
                // Add zone fill layer (colored polygons)
                map.addLayer({{
                    id: 'zones-fill',
                    type: 'fill',
                    source: 'price-zones',
                    paint: {{
                        'fill-color': ['get', 'color'],
                        'fill-opacity': 0.3
                    }}
                }});
                
                // Add zone outline
                map.addLayer({{
                    id: 'zones-outline',
                    type: 'line',
                    source: 'price-zones',
                    paint: {{
                        'line-color': ['get', 'color'],
                        'line-width': 2,
                        'line-opacity': 0.6
                    }}
                }});
                
                // Add customer assets source (red pins)
                map.addSource('customer-assets', {{
                    type: 'geojson',
                    data: assetsData
                }});
                
                // Load pin icon
                map.loadImage('https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png', (error, image) => {{
                    if (error) {{
                        // Fallback to circle if icon fails to load
                        map.addLayer({{
                            id: 'customer-pins',
                            type: 'circle',
                            source: 'customer-assets',
                            paint: {{
                                'circle-radius': 10,
                                'circle-color': '#ff0000',
                                'circle-stroke-width': 3,
                                'circle-stroke-color': '#ffffff',
                                'circle-opacity': 0.9
                            }}
                        }});
                    }} else {{
                        map.addImage('red-pin', image);
                        map.addLayer({{
                            id: 'customer-pins',
                            type: 'symbol',
                            source: 'customer-assets',
                            layout: {{
                                'icon-image': 'red-pin',
                                'icon-size': 0.5,
                                'icon-anchor': 'bottom'
                            }}
                        }});
                    }}
                    
                    // Add price labels below pins
                    map.addLayer({{
                        id: 'customer-price-labels',
                        type: 'symbol',
                        source: 'customer-assets',
                        layout: {{
                            'text-field': ['concat', '$', ['to-string', ['round', ['get', 'customer_price']]], '/sqm'],
                            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                            'text-size': 11,
                            'text-offset': [0, 2.5],
                            'text-anchor': 'top'
                        }},
                        paint: {{
                            'text-color': '#ff0000',
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 2
                        }}
                    }});
                    
                    // Add delta labels
                    map.addLayer({{
                        id: 'customer-delta-labels',
                        type: 'symbol',
                        source: 'customer-assets',
                        layout: {{
                            'text-field': ['concat', ['get', 'price_delta'], '%'],
                            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                            'text-size': 10,
                            'text-offset': [0, 4.5],
                            'text-anchor': 'top'
                        }},
                        paint: {{
                            'text-color': ['case',
                                ['>', ['get', 'price_delta'], 0], '#ef4444',
                                '#22c55e'
                            ],
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 2
                        }}
                    }});
                    
                    // Auto-fit bounds to show all customer properties
                    const bounds = calculateBounds(assetsData.features);
                    if (bounds) {{
                        map.fitBounds(bounds, {{
                            padding: {{top: 50, bottom: 50, left: 50, right: 50}},
                            maxZoom: 12,
                            duration: 1500
                        }});
                    }}
                }});
                
                // Popup on click for customer assets
                map.on('click', 'customer-pins', (e) => {{
                    const props = e.features[0].properties;
                    const delta = parseFloat(props.price_delta).toFixed(1);
                    const status = props.status.replace('_', ' ');
                    const deltaClass = delta > 0 ? 'positive' : 'negative';
                    const deltaSign = delta > 0 ? '+' : '';
                    
                    new maplibregl.Popup()
                        .setLngLat([props.lon, props.lat])
                        .setHTML(`
                            <div class="popup-content">
                                <h4>${{props.name}}</h4>
                                <p class="market-price">💰 Market: ${{props.market_price.toLocaleString()}}/sqm</p>
                                <p class="price">💵 Customer: ${{props.customer_price.toLocaleString()}}/sqm</p>
                                <p class="delta ${{deltaClass}}">📊 Price Delta: ${{deltaSign}}${{delta}}%</p>
                                <p>📍 ${{props.city}} • ${{props.district || 'N/A'}}</p>
                                <p>🏘️ ${{props.property_type}}</p>
                                <p>📈 Status: ${{status}}</p>
                                <p>🏠 Area: ${{props.area_sqm}} sqm</p>
                                <p>✅ Confidence: ${{props.confidence}}%</p>
                            </div>
                        `)
                        .addTo(map);
                    
                    map.flyTo({{
                        center: [props.lon, props.lat],
                        zoom: 12,
                        pitch: 70,
                        essential: true
                    }});
                }});
                
                // Popup on click for zones
                map.on('click', 'zones-fill', (e) => {{
                    const props = e.features[0].properties;
                    new maplibregl.Popup()
                        .setLngLat(e.lngLat)
                        .setHTML(`
                            <div class="popup-content">
                                <h4>${{props.district}}</h4>
                                <p class="market-price">💰 Market Price: ${{props.market_price.toLocaleString()}}/sqm</p>
                                <p>📍 ${{props.city}}</p>
                                <p>📊 Price Range: ${{props.price_range.replace('_', ' ').toUpperCase()}}</p>
                            </div>
                        `)
                        .addTo(map);
                }});
                
                map.on('mouseenter', ['customer-pins', 'customer-price-labels', 'customer-delta-labels'], () => {{
                    map.getCanvas().style.cursor = 'pointer';
                }});
                
                map.on('mouseleave', ['customer-pins', 'customer-price-labels', 'customer-delta-labels'], () => {{
                    map.getCanvas().style.cursor = '';
                }});
                
                // Make labels clickable too
                map.on('click', ['customer-price-labels', 'customer-delta-labels'], (e) => {{
                    const props = e.features[0].properties;
                    const delta = parseFloat(props.price_delta).toFixed(1);
                    const status = props.status.replace('_', ' ');
                    const deltaClass = delta > 0 ? 'positive' : 'negative';
                    const deltaSign = delta > 0 ? '+' : '';
                    
                    new maplibregl.Popup()
                        .setLngLat([props.lon, props.lat])
                        .setHTML(`
                            <div class="popup-content">
                                <h4>${{props.name}}</h4>
                                <p class="market-price">💰 Market: ${{props.market_price.toLocaleString()}}/sqm</p>
                                <p class="price">💵 Customer: ${{props.customer_price.toLocaleString()}}/sqm</p>
                                <p class="delta ${{deltaClass}}">📊 Price Delta: ${{deltaSign}}${{delta}}%</p>
                                <p>📍 ${{props.city}} • ${{props.district || 'N/A'}}</p>
                                <p>🏘️ ${{props.property_type}}</p>
                                <p>📈 Status: ${{status}}</p>
                                <p>🏠 Area: ${{props.area_sqm}} sqm</p>
                                <p>✅ Confidence: ${{props.confidence}}%</p>
                            </div>
                        `)
                        .addTo(map);
                }});
                
                map.on('mouseenter', 'zones-fill', () => {{
                    map.getCanvas().style.cursor = 'pointer';
                }});
                
                map.on('mouseleave', 'zones-fill', () => {{
                    map.getCanvas().style.cursor = '';
                }});
            }});
        </script>
    </body>
    </html>
    """


def _generate_ultra_3d_map(map_data, zone_data, assets_geojson, zones_geojson, theme="dark"):
    """Generate Ultra 3D map HTML with advanced features and theme support"""
    # Calculate center from data
    if map_data:
        avg_lat = sum(item["lat"] for item in map_data) / len(map_data)
        avg_lon = sum(item["lon"] for item in map_data) / len(map_data)
    else:
        avg_lat, avg_lon = 16.0, 107.5
    
    # Calculate stats
    total_properties = len(map_data)
    avg_market_price = sum(item.get("market_price", 0) for item in map_data) / total_properties if total_properties > 0 else 0
    zones_count = len(zone_data)
    
    # Theme colors - normalize theme to ensure it's "dark" or "light"
    theme_normalized = str(theme).lower() if theme else "dark"
    is_dark = theme_normalized == "dark"
    palette = get_palette(theme_normalized)
    
    # Theme-specific styling
    bg_gradient = "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)" if is_dark else "linear-gradient(135deg, #f5f7fa 0%, #e2e8f0 50%, #cbd5e1 100%)"
    panel_bg = "rgba(0,0,0,0.9)" if is_dark else "rgba(255,255,255,0.95)"
    text_color = "#ffffff" if is_dark else "#000000"
    map_style_url = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" if is_dark else "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏗️ Vietnam Real Estate Ultra 3D Map</title>
        <script src='https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js'></script>
        <link href='https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css' rel='stylesheet' />
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {bg_gradient};
                min-height: 100vh;
                margin: 0;
                color: {text_color};
                overflow: hidden;
            }}
            #map-container {{
                position: relative;
                width: 100%;
                height: 800px;
                overflow: hidden;
            }}
            #map {{ width: 100%; height: 100%; }}
            #control-panel {{
                position: absolute;
                top: 20px;
                left: 20px;
                width: 280px;
                background: {panel_bg};
                backdrop-filter: blur(20px);
                border-radius: 20px;
                padding: 20px;
                z-index: 1000;
                box-shadow: 0 20px 50px rgba(0,0,0,0.6);
                max-height: calc(100% - 40px);
                overflow-y: auto;
                color: {text_color};
            }}
            #control-panel h1 {{
                font-size: 20px;
                margin-bottom: 10px;
                color: #00ff88;
                background: linear-gradient(90deg, #00ff88, #00d4ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .layer-controls {{
                background: {"rgba(255,255,255,0.05)" if is_dark else "rgba(0,0,0,0.05)"};
                border-radius: 15px;
                padding: 15px;
                margin: 15px 0;
            }}
            .layer-toggle {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid {"rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.1)"};
            }}
            .layer-toggle:last-child {{ border-bottom: none; }}
            .layer-toggle span {{
                color: {text_color};
            }}
            .toggle-switch {{
                width: 50px;
                height: 26px;
                background: {"#444" if is_dark else "#ccc"};
                border-radius: 13px;
                position: relative;
                cursor: pointer;
                transition: background 0.3s;
            }}
            .toggle-switch.active {{
                background: #00ff88;
            }}
            .toggle-switch::after {{
                content: '';
                position: absolute;
                top: 2px;
                left: 2px;
                width: 22px;
                height: 22px;
                background: white;
                border-radius: 50%;
                transition: transform 0.3s;
            }}
            .toggle-switch.active::after {{
                transform: translateX(24px);
            }}
            #stats-dashboard {{
                position: absolute;
                top: 20px;
                right: 20px;
                width: 280px;
                background: {panel_bg};
                border-radius: 20px;
                padding: 20px;
                backdrop-filter: blur(20px);
                z-index: 1000;
                color: {text_color};
            }}
            .stat-card {{
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #00ff88;
            }}
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #00ff88;
            }}
            .stat-label {{
                font-size: 12px;
                opacity: 0.7;
                margin-top: 5px;
            }}
            #legend {{
                position: absolute;
                bottom: 20px;
                right: 20px;
                background: {panel_bg};
                border-radius: 20px;
                padding: 20px;
                backdrop-filter: blur(20px);
                z-index: 1000;
                color: {text_color};
            }}
            .legend-item {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 6px;
                font-size: 12px;
            }}
            .legend-color {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
            }}
            .popup-content {{
                font-family: inherit;
                min-width: 250px;
                color: #000;
            }}
            .popup-content h4 {{
                margin-bottom: 8px;
                color: #f5576c;
                font-size: 16px;
            }}
            .popup-content p {{
                margin: 4px 0;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div id="map-container">
            <div id="map"></div>
            
            <!-- Control Panel -->
            <div id="control-panel">
                <h1>🏗️ Vietnam Real Estate Ultra 3D</h1>
                <p style="font-size: 12px; opacity: 0.7;">Interactive map with 3D districts & price zones</p>
                
                <div class="layer-controls">
                    <h3 style="color: #00ff88; margin-bottom: 15px; font-size: 14px;">🎨 3D Layers</h3>
                    <div class="layer-toggle">
                        <span style="font-size: 12px;">3D District Zones</span>
                        <div class="toggle-switch active" id="toggle-zones"></div>
                    </div>
                    <div class="layer-toggle">
                        <span style="font-size: 12px;">Customer Assets</span>
                        <div class="toggle-switch active" id="toggle-assets"></div>
                    </div>
                    <div class="layer-toggle">
                        <span style="font-size: 12px;">Zone Labels</span>
                        <div class="toggle-switch active" id="toggle-labels"></div>
                    </div>
                </div>
            </div>
            
            <!-- Stats Dashboard -->
            <div id="stats-dashboard">
                <h3 style="color: #00ff88; margin-bottom: 15px; font-size: 16px;">📈 Market Analytics</h3>
                <div class="stat-card">
                    <div class="stat-value" id="stat-total">{total_properties}</div>
                    <div class="stat-label">Total Properties</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-avg">${avg_market_price:,.0f}/sqm</div>
                    <div class="stat-label">Avg Market Price</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-zones">{zones_count}</div>
                    <div class="stat-label">Price Zones</div>
                </div>
            </div>
            
            <!-- Price Legend -->
            <div id="legend">
                <h3 style="color: #00ff88; margin-bottom: 15px; font-size: 16px;">💰 Price Zones ($/SQM)</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: #2d5016;"></div>
                    <span>$1,000 - $2,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #73b504;"></div>
                    <span>$2,000 - $3,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ffcc00;"></div>
                    <span>$3,000 - $4,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff6600;"></div>
                    <span>$4,000 - $5,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff0000;"></div>
                    <span>$5,000+</span>
                </div>
            </div>
        </div>
        
        <script>
            const assetsData = {json.dumps(assets_geojson)};
            const zonesData = {json.dumps(zones_geojson)};
            
            // Calculate bounding box from assets
            const calculateBounds = (features) => {{
                if (!features || features.length === 0) return null;
                let minLon = Infinity, maxLon = -Infinity;
                let minLat = Infinity, maxLat = -Infinity;
                features.forEach(f => {{
                    const [lon, lat] = f.geometry.coordinates;
                    minLon = Math.min(minLon, lon);
                    maxLon = Math.max(maxLon, lon);
                    minLat = Math.min(minLat, lat);
                    maxLat = Math.max(maxLat, lat);
                }});
                return [[minLon, minLat], [maxLon, maxLat]];
            }};
            
            // Map style based on theme
            const mapStyleUrl = {json.dumps(map_style_url)};
            const map = new maplibregl.Map({{
                container: 'map',
                style: mapStyleUrl,
                center: [{avg_lon}, {avg_lat}],
                zoom: 10,
                pitch: 60,
                bearing: -20,
                antialias: true
            }});
            
            map.addControl(new maplibregl.NavigationControl({{
                visualizePitch: true,
                showZoom: true,
                showCompass: true
            }}));
            
            map.on('load', () => {{
                // Add terrain
                map.addSource('terrain', {{
                    type: 'raster-dem',
                    url: 'https://demotiles.maplibre.org/terrain-tiles/tiles.json',
                    tileSize: 256
                }});
                
                map.addLayer({{
                    id: 'terrain-layer',
                    source: 'terrain',
                    type: 'hillshade',
                    paint: {{
                        'hillshade-shadow-color': '#000',
                        'hillshade-highlight-color': '#fff',
                        'hillshade-illumination-anchor': 'viewport'
                    }}
                }});
                
                // Add price zone polygons
                map.addSource('price-zones', {{
                    type: 'geojson',
                    data: zonesData
                }});
                
                // 3D extruded zones
                map.addLayer({{
                    id: 'district-zones',
                    source: 'price-zones',
                    type: 'fill-extrusion',
                    paint: {{
                        'fill-extrusion-color': ['get', 'color'],
                        'fill-extrusion-height': [
                            'interpolate',
                            ['linear'],
                            ['get', 'market_price'],
                            1000, 50,
                            2000, 100,
                            3000, 150,
                            4000, 200,
                            5000, 250
                        ],
                        'fill-extrusion-base': 0,
                        'fill-extrusion-opacity': 0.75,
                        'fill-extrusion-vertical-gradient': true
                    }}
                }});
                
                map.addLayer({{
                    id: 'district-zone-outline',
                    source: 'price-zones',
                    type: 'line',
                    paint: {{
                        'line-color': '#ffffff',
                        'line-width': 1.5,
                        'line-opacity': 0.6
                    }}
                }});
                
                // Add customer assets
                map.addSource('customer-assets', {{
                    type: 'geojson',
                    data: assetsData
                }});
                
                // Load pin icon
                map.loadImage('https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png', (error, image) => {{
                    if (error) {{
                        // Fallback to circle if icon fails to load
                        map.addLayer({{
                            id: 'customer-pins',
                            type: 'circle',
                            source: 'customer-assets',
                            paint: {{
                                'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 8, 15, 15],
                                'circle-color': '#ff0000',
                                'circle-stroke-width': 3,
                                'circle-stroke-color': '#ffffff',
                                'circle-opacity': 0.9
                            }}
                        }});
                    }} else {{
                        map.addImage('red-pin', image);
                        map.addLayer({{
                            id: 'customer-pins',
                            type: 'symbol',
                            source: 'customer-assets',
                            layout: {{
                                'icon-image': 'red-pin',
                                'icon-size': 0.5,
                                'icon-anchor': 'bottom'
                            }}
                        }});
                    }}
                    
                    // Add price labels below pins
                    map.addLayer({{
                        id: 'customer-price-labels',
                        type: 'symbol',
                        source: 'customer-assets',
                        layout: {{
                            'text-field': ['concat', '$', ['to-string', ['round', ['get', 'customer_price']]], '/sqm'],
                            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                            'text-size': 11,
                            'text-offset': [0, 2.5],
                            'text-anchor': 'top'
                        }},
                        paint: {{
                            'text-color': '#ff0000',
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 2
                        }}
                    }});
                    
                    // Add delta labels
                    map.addLayer({{
                        id: 'customer-delta-labels',
                        type: 'symbol',
                        source: 'customer-assets',
                        layout: {{
                            'text-field': ['concat', ['get', 'price_delta'], '%'],
                            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                            'text-size': 10,
                            'text-offset': [0, 4.5],
                            'text-anchor': 'top'
                        }},
                        paint: {{
                            'text-color': ['case',
                                ['>', ['get', 'price_delta'], 0], '#ef4444',
                                '#22c55e'
                            ],
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 2
                        }}
                    }});
                    
                    // Auto-fit bounds to show all customer properties
                    const bounds = calculateBounds(assetsData.features);
                    if (bounds) {{
                        map.fitBounds(bounds, {{
                            padding: {{top: 50, bottom: 50, left: 50, right: 50}},
                            maxZoom: 12,
                            duration: 1500
                        }});
                    }}
                }});
                
                // Zone labels
                map.addLayer({{
                    id: 'zone-labels',
                    source: 'price-zones',
                    type: 'symbol',
                    layout: {{
                        'text-field': ['get', 'district'],
                        'text-font': ['Open Sans Bold'],
                        'text-size': 14,
                        'text-transform': 'uppercase',
                        'text-anchor': 'center',
                        'text-pitch-alignment': 'viewport'
                    }},
                    paint: {{
                        'text-color': '#ffffff',
                        'text-halo-color': '#00ff88',
                        'text-halo-width': 3,
                        'text-opacity': 0.9
                    }}
                }});
                
                // Popups
                map.on('click', ['customer-pins', 'customer-price-labels', 'customer-delta-labels'], (e) => {{
                    const props = e.features[0].properties;
                    const delta = parseFloat(props.price_delta).toFixed(1);
                    const deltaSign = delta > 0 ? '+' : '';
                    
                    new maplibregl.Popup()
                        .setLngLat([props.lon, props.lat])
                        .setHTML(`
                            <div class="popup-content">
                                <h4>${{props.name}}</h4>
                                <p style="color: #22c55e; font-weight: bold;">💰 Market: ${{props.market_price.toLocaleString()}}/sqm</p>
                                <p style="color: #f5576c; font-weight: bold;">💵 Customer: ${{props.customer_price.toLocaleString()}}/sqm</p>
                                <p style="color: ${{delta > 0 ? '#ef4444' : '#22c55e'}}; font-weight: bold;">📊 Delta: ${{deltaSign}}${{delta}}%</p>
                                <p>📍 ${{props.city}} • ${{props.district || 'N/A'}}</p>
                                <p>🏘️ ${{props.property_type}}</p>
                                <p>🏠 Area: ${{props.area_sqm}} sqm</p>
                            </div>
                        `)
                        .addTo(map);
                }});
                
                map.on('mouseenter', ['customer-pins', 'customer-price-labels', 'customer-delta-labels'], () => {{
                    map.getCanvas().style.cursor = 'pointer';
                }});
                
                map.on('mouseleave', ['customer-pins', 'customer-price-labels', 'customer-delta-labels'], () => {{
                    map.getCanvas().style.cursor = '';
                }});
                
                map.on('click', 'district-zones', (e) => {{
                    const props = e.features[0].properties;
                    new maplibregl.Popup()
                        .setLngLat(e.lngLat)
                        .setHTML(`
                            <div class="popup-content">
                                <h4>${{props.district}}</h4>
                                <p style="color: #22c55e; font-weight: bold;">💰 Market: ${{props.market_price.toLocaleString()}}/sqm</p>
                                <p>📍 ${{props.city}}</p>
                                <p>📊 Range: ${{props.price_range.replace('_', ' ').toUpperCase()}}</p>
                            </div>
                        `)
                        .addTo(map);
                }});
                
                // Toggle controls
                document.getElementById('toggle-zones').onclick = function() {{
                    const visibility = map.getLayoutProperty('district-zones', 'visibility');
                    map.setLayoutProperty('district-zones', 'visibility', visibility === 'none' ? 'visible' : 'none');
                    map.setLayoutProperty('district-zone-outline', 'visibility', visibility === 'none' ? 'visible' : 'none');
                    this.classList.toggle('active');
                }};
                
                document.getElementById('toggle-assets').onclick = function() {{
                    const visibility = map.getLayoutProperty('customer-pins', 'visibility');
                    map.setLayoutProperty('customer-pins', 'visibility', visibility === 'none' ? 'visible' : 'none');
                    map.setLayoutProperty('customer-price-labels', 'visibility', visibility === 'none' ? 'visible' : 'none');
                    map.setLayoutProperty('customer-delta-labels', 'visibility', visibility === 'none' ? 'visible' : 'none');
                    this.classList.toggle('active');
                }};
                
                document.getElementById('toggle-labels').onclick = function() {{
                    const visibility = map.getLayoutProperty('zone-labels', 'visibility');
                    map.setLayoutProperty('zone-labels', 'visibility', visibility === 'none' ? 'visible' : 'none');
                    this.classList.toggle('active');
                }};
            }});
        </script>
    </body>
    </html>
    """

# Navigation
def render_nav_bar():
    # Get current theme for styling
    current_theme = get_theme()
    palette = get_palette(current_theme)
    
    # Style navigation buttons
    st.markdown(f"""
    <style>
    .nav-button-container {{
        display: flex;
        gap: 10px;
        margin-bottom: 20px;
        padding: 10px;
        background: {palette['card']};
        border-radius: 12px;
        border: 1px solid {palette['border']};
    }}
    .stButton > button {{
        background: {palette['accent']} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }}
    .stButton > button:hover {{
        background: {palette['accent_alt']} !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    </style>
    """, unsafe_allow_html=True)
    
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 1, 2])
    with nav_col1:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state["stage"] = "landing"
            st.rerun()
    with nav_col2:
        if st.button("🤖 Agents", use_container_width=True):
            st.session_state["stage"] = "agents"
            st.rerun()
    with nav_col3:
        if st.button("📊 Dashboard", use_container_width=True):
            st.switch_page("app.py")
    with nav_col4:
        render_theme_toggle(label="🌗 Theme", key="re_theme_toggle")

# Header
st.title("🏠 Real Estate Evaluator Agent")
st.caption("Interactive Map • Market Price Comparison • CSV Upload Support")
render_nav_bar()
st.markdown("---")

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📤 Upload Assets")
    
    # CSV Upload
    uploaded_file = st.file_uploader(
        "Upload CSV file with assets",
        type=["csv"],
        help="CSV should contain: address, city, district, property_type, customer_price, area_sqm, lat, lon"
    )
    
    # Load sample data by default
    st.subheader("📋 Sample Properties (10)")
    
    # Load sample CSV
    sample_csv_path = os.path.join(os.path.dirname(__file__), "../../../agents/real_estate_evaluator/sample_data.csv")
    if os.path.exists(sample_csv_path):
        if st.button("📥 Load 10 Sample Properties", type="primary"):
            try:
                sample_df = pd.read_csv(sample_csv_path)
                ss["re_uploaded_file"] = sample_df
                st.success(f"✅ Loaded {len(sample_df)} sample properties!")
                st.dataframe(sample_df)
            except Exception as e:
                st.error(f"Error loading sample: {e}")
    else:
        # Fallback: generate sample data
        if st.button("📥 Generate 10 Sample Properties", type="primary"):
            sample_data = {
                "address": [
                    "123 Le Loi Street",
                    "456 Nguyen Hue Boulevard",
                    "789 Tran Hung Dao",
                    "321 Hoang Dieu",
                    "654 Bach Dang",
                    "789 Le Duan",
                    "456 Hoang Hoa Tham",
                    "123 Cau Giay",
                    "789 Son Tra",
                    "321 Phu Nhuan"
                ],
                "city": ["HCMC", "HCMC", "Hanoi", "Hanoi", "Da Nang", "HCMC", "HCMC", "Hanoi", "Da Nang", "Hue"],
                "district": ["District 1", "District 1", "Hoan Kiem", "Tay Ho", "Hai Chau", "District 2", "Phu Nhuan", "Cau Giay", "Son Tra", "Phu Nhuan"],
                "property_type": ["Apartment", "Condo", "House", "Villa", "Apartment", "Apartment", "House", "Condo", "Villa", "Apartment"],
                "customer_price": [520000, 380000, 870000, 1260000, 220000, 320000, 450000, 310000, 390000, 120000],
                "area_sqm": [100, 85, 150, 200, 95, 90, 120, 75, 180, 96],
                "lat": [10.7769, 10.7750, 21.0285, 21.0716, 16.0472, 10.7856, 10.7992, 21.0367, 16.0902, 16.4498],
                "lon": [106.7009, 106.7020, 105.8542, 105.8344, 108.2097, 106.7534, 106.6650, 105.8157, 108.2412, 107.5623]
            }
            ss["re_uploaded_file"] = pd.DataFrame(sample_data)
            st.success("✅ Generated 10 sample properties!")
            st.dataframe(ss["re_uploaded_file"])
    
    # Auto-load sample on first visit and auto-evaluate
    if ss.get("re_uploaded_file") is None and not ss.get("re_auto_loaded", False):
        try:
            sample_csv_path = os.path.join(os.path.dirname(__file__), "../../../agents/real_estate_evaluator/sample_data.csv")
            if os.path.exists(sample_csv_path):
                ss["re_uploaded_file"] = pd.read_csv(sample_csv_path)
                ss["re_auto_loaded"] = True
            else:
                # Generate sample data if CSV doesn't exist
                sample_data = {
                    "address": [
                        "123 Le Loi Street",
                        "456 Nguyen Hue Boulevard",
                        "789 Tran Hung Dao",
                        "321 Hoang Dieu",
                        "654 Bach Dang",
                        "789 Le Duan",
                        "456 Hoang Hoa Tham",
                        "123 Cau Giay",
                        "789 Son Tra",
                        "321 Phu Nhuan"
                    ],
                    "city": ["HCMC", "HCMC", "Hanoi", "Hanoi", "Da Nang", "HCMC", "HCMC", "Hanoi", "Da Nang", "Hue"],
                    "district": ["District 1", "District 1", "Hoan Kiem", "Tay Ho", "Hai Chau", "District 2", "Phu Nhuan", "Cau Giay", "Son Tra", "Phu Nhuan"],
                    "property_type": ["Apartment", "Condo", "House", "Villa", "Apartment", "Apartment", "House", "Condo", "Villa", "Apartment"],
                    "customer_price": [520000, 380000, 870000, 1260000, 220000, 320000, 450000, 310000, 390000, 120000],
                    "area_sqm": [100, 85, 150, 200, 95, 90, 120, 75, 180, 96],
                    "lat": [10.7769, 10.7750, 21.0285, 21.0716, 16.0472, 10.7856, 10.7992, 21.0367, 16.0902, 16.4498],
                    "lon": [106.7009, 106.7020, 105.8542, 105.8344, 108.2097, 106.7534, 106.6650, 105.8157, 108.2412, 107.5623]
                }
                ss["re_uploaded_file"] = pd.DataFrame(sample_data)
                ss["re_auto_loaded"] = True
            
            # Auto-evaluate on load if not already evaluated
            if ss.get("re_evaluated_df") is None and not ss.get("re_auto_evaluated", False):
                ss["re_auto_evaluated"] = True
                with st.spinner("🔄 Auto-evaluating sample properties and loading map..."):
                    try:
                        url = f"{API_URL}/v1/agents/real_estate_evaluator/run/json"
                        payload = {
                            "df": ss["re_uploaded_file"].to_dict(orient="records"),
                            "params": {"use_scraper": True}
                        }
                        resp = requests.post(url, json=payload, timeout=60)
                        if resp.status_code == 200:
                            result = resp.json()
                            evaluated_df_data = result.get("evaluated_df", [])
                            if isinstance(evaluated_df_data, list):
                                ss["re_evaluated_df"] = pd.DataFrame(evaluated_df_data)
                            else:
                                ss["re_evaluated_df"] = pd.DataFrame([evaluated_df_data])
                            ss["re_map_data"] = result.get("map_data", [])
                            ss["re_zone_data"] = result.get("zone_data", [])
                            ss["re_summary"] = result.get("summary", {})
                            st.success("✅ Sample properties loaded and evaluated! Map is ready.")
                            st.rerun()  # Refresh to show the map
                    except Exception as e:
                        # Fallback to local evaluation
                        try:
                            from agents.real_estate_evaluator.agent import run as agent_run
                            result = agent_run(ss["re_uploaded_file"], {"use_scraper": True})
                            evaluated_df_data = result.get("evaluated_df", [])
                            if isinstance(evaluated_df_data, pd.DataFrame):
                                ss["re_evaluated_df"] = evaluated_df_data
                            else:
                                ss["re_evaluated_df"] = pd.DataFrame(evaluated_df_data)
                            ss["re_map_data"] = result.get("map_data", [])
                            ss["re_zone_data"] = result.get("zone_data", [])
                            ss["re_summary"] = result.get("summary", {})
                            st.success("✅ Sample properties loaded and evaluated! Map is ready.")
                            st.rerun()  # Refresh to show the map
                        except Exception as ex:
                            st.warning(f"⚠️ Auto-evaluation failed: {ex}. Please click 'Evaluate Assets' manually.")
        except Exception as e:
            st.warning(f"⚠️ Auto-loading sample data failed: {e}")
    
    # Process button
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            ss["re_uploaded_file"] = df
            st.success(f"✅ Loaded {len(df)} assets")
            st.dataframe(df.head())
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
    
    if ss.get("re_uploaded_file") is not None:
        st.subheader("⚙️ Evaluation Options")
        use_scraper = st.checkbox(
            "🌐 Enable Web Scraping (scrape from Vietnamese real estate websites)",
            value=True,
            help="Scrape live market prices from vietnam-real.estate, batdongsan.com.vn, muaban.net, alonhadat.com.vn"
        )
        
        if st.button("🔍 Evaluate Assets", type="primary"):
            with st.spinner("Evaluating assets and fetching market prices..."):
                try:
                    # Call the agent API
                    url = f"{API_URL}/v1/agents/real_estate_evaluator/run/json"
                    payload = {
                        "df": ss["re_uploaded_file"].to_dict(orient="records"),
                        "params": {
                            "use_scraper": use_scraper
                        }
                    }
                    
                    resp = requests.post(url, json=payload, timeout=60)
                    if resp.status_code == 200:
                        result = resp.json()
                        # Handle DataFrame conversion
                        evaluated_df_data = result.get("evaluated_df", [])
                        if isinstance(evaluated_df_data, list):
                            ss["re_evaluated_df"] = pd.DataFrame(evaluated_df_data)
                        else:
                            ss["re_evaluated_df"] = pd.DataFrame([evaluated_df_data])
                        ss["re_map_data"] = result.get("map_data", [])
                        ss["re_zone_data"] = result.get("zone_data", [])
                        ss["re_summary"] = result.get("summary", {})
                        st.success("✅ Evaluation complete!")
                    else:
                        st.error(f"API Error: {resp.status_code} - {resp.text}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    # Fallback: use local runner
                    try:
                        from agents.real_estate_evaluator.runner import run as runner_run
                        evaluated_df = runner_run(ss["re_uploaded_file"], {"use_scraper": use_scraper})
                        ss["re_evaluated_df"] = evaluated_df
                        
                        # Prepare map data
                        map_data = []
                        for _, row in evaluated_df.iterrows():
                            if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
                                map_data.append({
                                    "lat": float(row["lat"]),
                                    "lon": float(row["lon"]),
                                    "name": str(row.get("address", row.get("district", "Unknown"))),
                                    "city": str(row.get("city", "Unknown")),
                                    "district": str(row.get("district", "")),
                                    "property_type": str(row.get("property_type", "Apartment")),
                                    "market_price": float(row.get("market_price_per_sqm", 0)),
                                    "customer_price": float(row.get("customer_price_per_sqm", 0)),
                                    "price_delta": float(row.get("price_delta", 0)),
                                    "color": str(row.get("color", "#808080")),
                                    "price_range": str(row.get("price_range_category", "medium")),
                                    "status": str(row.get("evaluation_status", "at_market")),
                                    "area_sqm": float(row.get("area_sqm", 0)),
                                    "confidence": float(row.get("confidence", 0)),
                                })
                        ss["re_map_data"] = map_data
                        # Generate zone data
                        from agents.real_estate_evaluator.runner import generate_zone_data
                        ss["re_zone_data"] = generate_zone_data(evaluated_df)
                        st.success("✅ Evaluation complete (local mode)!")
                    except Exception as e2:
                        st.error(f"Local evaluation error: {e2}")

with col2:
    st.header("📊 Summary")
    
    if ss.get("re_summary"):
        summary = ss["re_summary"]
        st.metric("Total Assets", summary.get("total_assets", 0))
        st.metric("Assets on Map", summary.get("assets_on_map", 0))
        st.metric("Avg Market Price", f"${summary.get('avg_market_price', 0):,.0f}/sqm")
        st.metric("Avg Customer Price", f"${summary.get('avg_customer_price', 0):,.0f}/sqm")
        st.metric("Avg Price Delta", f"{summary.get('avg_price_delta', 0):.1f}%")
        
        # Status breakdown
        st.subheader("Evaluation Status")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Above Market", summary.get("above_market_count", 0))
        with col_b:
            st.metric("At Market", summary.get("at_market_count", 0))
        with col_c:
            st.metric("Below Market", summary.get("below_market_count", 0))

# Map visualization
if ss.get("re_map_data") and len(ss["re_map_data"]) > 0:
    st.header("🗺️ Interactive Map - Price Zones & Customer Assets")
    
    map_data = ss["re_map_data"]
    zone_data = ss.get("re_zone_data", [])
    
    # Prepare GeoJSON for customer assets (red pins)
    asset_features = []
    for item in map_data:
        asset_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [item["lon"], item["lat"]]
            },
            "properties": item
        })
    
    assets_geojson = {
        "type": "FeatureCollection",
        "features": asset_features
    }
    
    # Prepare GeoJSON for price zones (polygons)
    zone_features = []
    for zone in zone_data:
        zone_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [zone["polygon"]]
            },
            "properties": {
                "city": zone["city"],
                "district": zone["district"],
                "market_price": zone["market_price"],
                "color": zone["color"],
                "price_range": zone["price_range"]
            }
        })
    
    zones_geojson = {
        "type": "FeatureCollection",
        "features": zone_features
    }
    
    # Get current theme for map styling
    current_theme = get_theme()
    
    # Always use Ultra 3D Map
    map_html = _generate_ultra_3d_map(map_data, zone_data, assets_geojson, zones_geojson, current_theme)
    map_height = 800
    
    # Render map (will auto-update when theme changes via st.rerun())
    components.html(map_html, height=map_height)
    
    # Comparison table below map
    if ss.get("re_evaluated_df") is not None:
        st.header("📊 Asset Comparison Table")
        df = ss["re_evaluated_df"]
        
        # Create comparison table with key information
        comparison_data = []
        for _, row in df.iterrows():
            comparison_data.append({
                "Property Type": str(row.get("property_type", "N/A")),
                "Location": f"{row.get('city', 'N/A')}, {row.get('district', 'N/A')}",
                "Address": str(row.get("address", "N/A")),
                "Market Price/sqm": f"${row.get('market_price_per_sqm', 0):,.0f}",
                "Customer Price/sqm": f"${row.get('customer_price_per_sqm', 0):,.0f}",
                "Price Difference": f"{row.get('price_delta', 0):.1f}%",
                "Status": str(row.get("evaluation_status", "N/A")).replace("_", " ").title(),
                "Area (sqm)": f"{row.get('area_sqm', 0):.0f}",
                "Confidence": f"{row.get('confidence', 0):.0f}%"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Full Results CSV",
            data=csv,
            file_name=f"real_estate_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Charts
    st.subheader("📈 Price Analysis")
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        if len(df) > 0:
            fig = px.bar(
                df,
                x="address",
                y=["market_price_per_sqm", "customer_price_per_sqm"],
                title="Market vs Customer Price",
                labels={"value": "Price per sqm ($)", "address": "Property"},
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with chart_col2:
        if len(df) > 0:
            status_counts = df["evaluation_status"].value_counts()
            fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Evaluation Status Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
