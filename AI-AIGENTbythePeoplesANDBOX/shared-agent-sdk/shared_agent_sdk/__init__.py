"""Shared SDK for all AI agents: utilities, data loaders, and helpers."""
import os, json, pandas as pd

def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_json(path):
    with open(path) as f:
        return json.load(f)
