#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STARTUP = os.path.join(ROOT, "newstart.sh")

print("🚀 Executing launch script…")
try:
    subprocess.run(["bash", STARTUP], check=True)
    print("✅ Launch script completed.")
except subprocess.CalledProcessError as exc:
    print(f"⚠️ Launch script failed ({exc.returncode}) → aborting.")
    sys.exit(exc.returncode)

print("▶️ Starting Streamlit UI (services/ui/app.py)")
os.execvp("streamlit", ["streamlit", "run", "services/ui/app.py"])
