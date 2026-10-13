"""Fetch upcoming class sessions for one CorePower studio.

Talks directly to the public (unauthenticated) Elasticsearch-backed endpoint
that CorePower's own website uses to render its schedule pages:

    POST https://api2.corepoweryoga.com/elastic

No API key or login is required -- this is the same request the public
corepoweryoga.com schedule page makes from the browser.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import requests

ELASTIC_URL = "https://api2.corepoweryoga.com/elastic"
REQUEST_TIMEOUT = 30


def _iso_utc(moment: dt.datetime) -> str:
    """Format a datetime as the millisecond-precision UTC string the API expects."""
    moment = moment.astimezone(dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def fetch_sessions(
    center_id: str,
    *,
    days_ahead: int = 14,
    now: dt.datetime | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Return the raw class-session dicts for one studio over the next `days_ahead` days.

    Each dict is exactly what CorePower's API returns per class: fields of interest
    include session_id, name, start_time_utc, end_time_utc, instructors, class,
    center, capacity, available_slots, can_book_status, recurrence_id.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    window_end = now + dt.timedelta(days=days_ahead)

    query = {
        "size": 1000,
        "query": {
            "bool": {
                "filter": [
                    {"terms": {"center.id": [center_id]}},
                    {
                        "range": {
                            "start_time_utc": {
                                "gte": _iso_utc(now),
                                "lte": _iso_utc(window_end),
                            }
                        }
                    },
                ]
            }
        },
    }

    http = session or requests.Session()
    resp = http.post(ELASTIC_URL, json=query, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise ValueError(f"Unexpected response shape from {ELASTIC_URL}: {type(data)}")

    # Sort by start time so downstream consumers (and the generated .ics) read chronologically.
    data.sort(key=lambda session: session.get("start_time_utc", ""))
    return data


if __name__ == "__main__":
    import json
    import sys

    center = sys.argv[1] if len(sys.argv) > 1 else "22991841-d47c-4101-b8ff-423905dcf181"
    sessions = fetch_sessions(center)
    print(f"Fetched {len(sessions)} sessions for center {center}")
    if sessions:
        print(json.dumps(sessions[0], indent=2)[:1500])
