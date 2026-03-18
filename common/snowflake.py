"""Snowflake ID client - fetch unique IDs from external service."""
import logging
import os
import random
import time

import requests

logger = logging.getLogger(__name__)

# URL from env, e.g. http://localhost:18041/api/snowflake/id?bid=1002
SNOWFLAKE_ID_URL = (os.environ.get("SNOWFLAKE_ID_URL") or "").strip()


def _fallback_id() -> int:
    """Fallback when snowflake service unavailable: timestamp * 10000 + random."""
    return int(time.time() * 10000) + random.randint(0, 9999)


def get_snowflake_id() -> int:
    """
    Fetch a snowflake ID from the configured URL.
    Falls back to timestamp-based ID if service unavailable.
    """
    url = SNOWFLAKE_ID_URL
    if not url:
        logger.warning("SNOWFLAKE_ID_URL not set, using fallback ID")
        return _fallback_id()

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        # Assume response is {"id": 123...} or direct number
        if isinstance(data, (int, float)):
            return int(data)
        if isinstance(data, dict) and "id" in data:
            return int(data["id"])
        # Try common keys
        for key in ("id", "data", "value"):
            if key in data:
                return int(data[key])
        logger.error("Snowflake API response format unexpected: %s", data)
        return _fallback_id()
    except Exception as e:
        logger.warning("Failed to fetch snowflake ID from %s: %s, using fallback", url, e)
        return _fallback_id()
