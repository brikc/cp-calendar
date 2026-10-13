"""Regenerate every tracked studio's .ics file (and the docs/index.html landing page).

Run from the repo root:  python scripts/generate_all.py
This is what the scheduled GitHub Action calls.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ics import build_calendar  # noqa: E402
from fetch_schedule import fetch_sessions  # noqa: E402

STUDIOS_CONFIG = REPO_ROOT / "studios.json"
DOCS_DIR = REPO_ROOT / "docs"
DAYS_AHEAD = 14


def load_studios() -> list[dict[str, str]]:
    return json.loads(STUDIOS_CONFIG.read_text())


def generate_studio_feed(studio: dict[str, str], *, generated_at: dt.datetime) -> int:
    sessions = fetch_sessions(studio["zenotiCenterId"], days_ahead=DAYS_AHEAD, now=generated_at)
    calendar = build_calendar(sessions, studio_name=studio["name"], generated_at=generated_at)

    DOCS_DIR.mkdir(exist_ok=True)
    out_path = DOCS_DIR / f"{studio['slug']}.ics"
    out_path.write_bytes(calendar.to_ical())
    return len(sessions)


def write_index(studios: list[dict[str, str]], counts: dict[str, int], *, generated_at: dt.datetime) -> None:
    rows = "\n".join(
        f"      <tr><td>{s['name']}</td>"
        f"<td><a href=\"{s['slug']}.ics\">{s['slug']}.ics</a></td>"
        f"<td>{counts.get(s['slug'], 0)}</td></tr>"
        for s in studios
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CorePower Calendar Feeds</title>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd; }}
    code {{ background: #f2f2f2; padding: 0.1rem 0.3rem; border-radius: 3px; }}
    .meta {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>CorePower Yoga — Calendar Feeds</h1>
  <p class="meta">Last generated: {generated_at.strftime('%b %-d, %Y %-I:%M %p UTC')}</p>
  <p>Add any feed below to Google Calendar via
    <strong>Settings → Add calendar → From URL</strong>, using its full URL
    (right-click the link to copy it).</p>
  <table>
    <tr><th>Studio</th><th>Feed</th><th>Classes (next {DAYS_AHEAD} days)</th></tr>
{rows}
  </table>
  <p class="meta">
    Not an official CorePower Yoga product. Generated from CorePower's public
    schedule data on a schedule; Google Calendar may take several hours to
    reflect updates after a feed changes.
  </p>
</body>
</html>
"""
    (DOCS_DIR / "index.html").write_text(html)


def main() -> None:
    generated_at = dt.datetime.now(dt.timezone.utc)
    studios = load_studios()

    counts: dict[str, int] = {}
    for studio in studios:
        n = generate_studio_feed(studio, generated_at=generated_at)
        counts[studio["slug"]] = n
        print(f"  {studio['name']:<24} {n:>4} classes -> docs/{studio['slug']}.ics")

    write_index(studios, counts, generated_at=generated_at)
    print(f"Wrote docs/index.html and {len(studios)} feed(s) at {generated_at.isoformat()}")


if __name__ == "__main__":
    main()
