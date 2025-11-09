from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
FIXTURES = DATA_DIR / "fixtures" / "sample_cases.json"
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDINGS_MODEL = "all-MiniLM-L6-v2"
