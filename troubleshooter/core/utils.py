import re
from typing import List


def bulletize(items: List[str]) -> List[str]:
    return [f"• {txt}" for txt in items if txt.strip()]


def split_lines(text: str) -> List[str]:
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]
