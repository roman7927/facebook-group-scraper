"""Authoritative Green Check source discovery with an explicit stale cache."""
import json
from datetime import datetime, timezone
from pathlib import Path

from greencheck_client import GreenCheckError


def _validate(item):
    required = ("group_id", "group_name", "group_url", "facebook_source_type")
    if not all(isinstance(item.get(key), str) and item[key] for key in required):
        raise ValueError("Green Check config contains an invalid source")
    if item["facebook_source_type"] not in {"group", "page"}:
        raise ValueError("Green Check config has an unsupported Facebook source type")
    return {key: item[key] for key in required} | {"scrape_enabled": bool(item.get("scrape_enabled", False))}


def load_sources(client, cache_path):
    cache_path = Path(cache_path)
    try:
        payload = client.config()
        sources = [_validate(item) for item in payload.get("groups", []) if item.get("scrape_enabled", False)]
        cache_path.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "groups": sources}), encoding="utf-8")
        return sources, False
    except GreenCheckError as error:
        if not error.temporary or not cache_path.exists():
            raise
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return [_validate(item) for item in cached.get("groups", [])], True
