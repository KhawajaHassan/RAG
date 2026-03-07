from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from fastapi import Header


def require_openai_key(x_openai_key: Optional[str] = Header(default=None)) -> str:
    """
    Kept for backward-compatibility with the frontend but no longer enforced.
    For the Ollama-based backend we do not require any API key.
    """
    return x_openai_key or ""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {}

