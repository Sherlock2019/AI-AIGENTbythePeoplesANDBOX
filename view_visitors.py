#!/usr/bin/env python3
"""
Script to view all visitor IPs and country origins.
Usage: python view_visitors.py [--stats] [--json] [--ip <ip_address>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.api.middleware.visitor_tracker import (
    get_all_visitors,
    get_visitor_stats,
    load_visitor_data,
)


def format_table(visitors: list[dict]) -> str:
    """Format visitors as a table."""
    if not visitors:
        return "No visitors tracked yet."
    
    # Sort by last_seen (most recent first)
    sorted_visitors = sorted(
        visitors,
        key=lambda v: v.get("last_seen", ""),
        reverse=True
    )
    
    # Table header
    header = (
        f"{'IP Address':<18} {'Country':<20} {'City':<20} "
        f"{'Organization':<30} {'Visits':<8} {'First Seen':<20} {'Last Seen':<20}"
    )
    separator = "-" * len(header)
    
    lines = [header, separator]
    
    # Table rows
    for visitor in sorted_visitors:
        ip = visitor.get("ip", "Unknown")
        country = visitor.get("country", "Unknown")
        city = visitor.get("city", "Unknown")
        org = visitor.get("org", "Unknown")[:28]  # Truncate long org names
        visits = visitor.get("visit_count", 0)
        first_seen = visitor.get("first_seen", "Unknown")[:19]  # Remove timezone
        last_seen = visitor.get("last_seen", "Unknown")[:19]
        
        line = (
            f"{ip:<18} {country:<20} {city:<20} "
            f"{org:<30} {visits:<8} {first_seen:<20} {last_seen:<20}"
        )
        lines.append(line)
    
    return "\n".join(lines)


def print_stats() -> None:
    """Print visitor statistics."""
    stats = get_visitor_stats()
    
    print("\n" + "=" * 80)
    print("VISITOR STATISTICS")
    print("=" * 80)
    print(f"Total Unique Visitors: {stats['total_visitors']}")
    print(f"Total Visits: {stats['total_visits']}")
    
    if stats['countries']:
        print("\nVisitors by Country:")
        sorted_countries = sorted(
            stats['countries'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        for country, count in sorted_countries:
            print(f"  {country}: {count}")
    
    if stats['top_ips']:
        print("\nTop 10 IPs by Visit Count:")
        for i, ip_info in enumerate(stats['top_ips'], 1):
            print(
                f"  {i}. {ip_info['ip']:<18} "
                f"{ip_info['country']:<20} ({ip_info['visit_count']} visits)"
            )
    
    print("=" * 80 + "\n")


def print_visitor_details(ip: str) -> None:
    """Print detailed information about a specific visitor."""
    visitors = load_visitor_data()
    
    if ip not in visitors:
        print(f"No data found for IP: {ip}")
        return
    
    visitor = visitors[ip]
    
    print("\n" + "=" * 80)
    print(f"VISITOR DETAILS: {ip}")
    print("=" * 80)
    print(f"IP Address:       {visitor.get('ip', 'Unknown')}")
    print(f"Country:           {visitor.get('country', 'Unknown')} ({visitor.get('country_code', 'XX')})")
    print(f"Region:            {visitor.get('region', 'Unknown')}")
    print(f"City:              {visitor.get('city', 'Unknown')}")
    print(f"Organization:      {visitor.get('org', 'Unknown')}")
    print(f"ISP:               {visitor.get('isp', 'Unknown')}")
    print(f"Visit Count:       {visitor.get('visit_count', 0)}")
    print(f"First Seen:        {visitor.get('first_seen', 'Unknown')}")
    print(f"Last Seen:         {visitor.get('last_seen', 'Unknown')}")
    
    paths = visitor.get("paths_visited", [])
    if paths:
        print(f"\nPaths Visited ({len(paths)}):")
        for path in paths:
            print(f"  - {path}")
    
    user_agents = visitor.get("user_agents", [])
    if user_agents:
        print(f"\nUser Agents ({len(user_agents)}):")
        for ua in user_agents:
            print(f"  - {ua}")
    
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="View visitor IPs and country origins",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_visitors.py              # Show all visitors in table format
  python view_visitors.py --stats      # Show statistics
  python view_visitors.py --json       # Output as JSON
  python view_visitors.py --ip 1.2.3.4 # Show details for specific IP
        """
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show visitor statistics"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--ip",
        type=str,
        help="Show detailed information for a specific IP address"
    )
    
    args = parser.parse_args()
    
    # Check if visitor data file exists
    visitor_data_file = Path(os.getenv("VISITOR_DATA_DIR", "/root/WIP/data/visitors")) / "visitors.json"
    if not visitor_data_file.exists():
        print("No visitor data found. Visitors will be tracked once the API receives requests.")
        print(f"Data will be stored at: {visitor_data_file}")
        return
    
    # Handle specific IP lookup
    if args.ip:
        print_visitor_details(args.ip)
        return
    
    # Get all visitors
    visitors = get_all_visitors()
    
    if args.stats:
        print_stats()
    elif args.json:
        print(json.dumps(visitors, indent=2, ensure_ascii=False))
    else:
        # Default: show table
        print("\n" + "=" * 80)
        print("ALL VISITORS")
        print("=" * 80)
        print(format_table(visitors))
        print("\nUse --stats for statistics or --ip <address> for details on a specific IP.")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
