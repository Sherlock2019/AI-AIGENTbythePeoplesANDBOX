#!/usr/bin/env python3
"""🔧 Sandbox Manager - Admin interface for managing landing page agents"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ.setdefault("STREAMLIT_TELEMETRY_DISABLED", "true")
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

if __name__ == "__main__":
    # Path to the admin page
    admin_page = project_root / "services" / "ui" / "pages" / "admin_agents.py"
    
    if not admin_page.exists():
        print(f"❌ Error: Admin page not found at {admin_page}")
        sys.exit(1)
    
    print("🔧 Starting Sandbox Manager Admin Interface...")
    print(f"📄 Admin page: {admin_page}")
    print("🌐 Opening browser at http://localhost:8502")
    print("Press Ctrl+C to stop the server")
    print("-" * 60)
    
    # Run Streamlit with the admin page
    try:
        subprocess.run([
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(admin_page),
            "--server.port=8502",
            "--server.headless=false",
            "--browser.gatherUsageStats=false",
        ])
    except KeyboardInterrupt:
        print("\n👋 Sandbox Manager stopped.")
        sys.exit(0)
