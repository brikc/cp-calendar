"""Turn CorePower class-session JSON into a Google-Calendar-subscribable .ics file."""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from icalendar import Calendar, Event

# Map CorePower's class category names to the slugs used in their own
# site navigation / class-detail URLs, e.g.:
#   https://www.corepoweryoga.com/yoga-fitness-classes/yoga-sculpt/studio
# Used to build a direct, human-clickable link to the live class page.
CATEGORY_SLUGS = {
    "CorePower Yoga 1": "corepower-1",
    "CorePower Yoga 2": "corepower-2",
    "CorePower Yoga 3": "corepower-1",  # no distinct nav page observed; falls back below anyway
    "Yoga Sculpt": "yoga-sculpt",
    "CorePower Yoga Strength X": "corepower-strength-x",
    "Hot Power Fusion": "hot-power-fusion",
    "CoreRestore": "corerestore",
}

STUDIO_SCHEDULE_URL = "https://www.corepoweryoga.com/yoga-schedules/studio"
UID_NAMESPACE = NAMESPACE_URL  # stable namespace for deriving deterministic UIDs


def _parse_api_utc(value: str) -> dt.datetime:
    """Parse the API's millisecond-precision 'Z' timestamps into aware UTC datetimes."""
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def _class_detail_url(session: dict[str, Any]) -> str:
    """Link to this class type's page for this specific studio.

    CorePower's actual Next.js route is /yoga-fitness-classes/[classtype]/[id]
    (confirmed against the live site); there is no real per-session page --
    an earlier version of this guessed a 4-segment /session/.../sessionId
    path from minified JS that turned out to be client-side-only modal state
    and 404s on direct navigation. This route is real and always resolves;
    its [id] segment is read client-side to filter that class type down to
    one studio, so the link lands you on the right studio's listing for that
    class type, sorted chronologically, where you can confirm the exact class.
    """
    category = (session.get("class") or {}).get("category") or {}
    category_name = category.get("name")
    center_id = (session.get("center") or {}).get("id")

    slug = CATEGORY_SLUGS.get(category_name)
    if slug and center_id:
        return f"https://www.corepoweryoga.com/yoga-fitness-classes/{slug}/{center_id}"
    return STUDIO_SCHEDULE_URL


def _session_uid(session: dict[str, Any]) -> str:
    """Deterministic UID from session_id, so re-running updates events in place
    instead of creating duplicates on every sync."""
    session_id = session.get("session_id") or session.get("session_guid") or session.get("id")
    return str(uuid5(UID_NAMESPACE, f"corepoweryoga.com/session/{session_id}")) + "@cp-calendar"


def _build_session_event(session: dict[str, Any], *, studio_name: str, generated_at: dt.datetime) -> Event:
    event = Event()

    category_name = ((session.get("class") or {}).get("category") or {}).get("name", "Class")
    instructors = ", ".join(i.get("name", "") for i in session.get("instructors", []) if i.get("name")) or "TBD"
    capacity = session.get("capacity")
    available = session.get("available_slots")

    start = _parse_api_utc(session["start_time_utc"])
    end = _parse_api_utc(session["end_time_utc"])

    description_lines = [
        f"Instructor: {instructors}",
        f"Studio: {studio_name}",
    ]
    if capacity is not None and available is not None:
        description_lines.append(f"Spots: {available} available of {capacity}")
    description_lines.append("")
    description_lines.append(
        f"Synced: {generated_at.strftime('%b %-d, %-I:%M %p %Z')} "
        f"({generated_at.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} UTC)"
    )
    description_lines.append("Tap the event link to check this studio's live schedule on corepoweryoga.com.")

    event.add("uid", _session_uid(session))
    event.add("summary", f"{category_name} — {studio_name}")
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("dtstamp", generated_at)
    event.add("location", studio_name)
    event.add("description", "\n".join(description_lines))
    event.add("url", _class_detail_url(session))
    return event


def _build_sync_banner_event(*, studio_name: str, generated_at: dt.datetime) -> Event:
    """An all-day event on 'today' so staleness is visible without opening any class event."""
    event = Event()
    today = generated_at.date()
    event.add("uid", f"sync-banner-{studio_name.lower().replace(' ', '-')}-{today.isoformat()}@cp-calendar")
    event.add(
        "summary",
        f"📅 {studio_name} feed last generated {generated_at.strftime('%b %-d, %-I:%M %p %Z')}",
    )
    event.add("dtstart", today)
    event.add("dtend", today + dt.timedelta(days=1))
    event.add("dtstamp", generated_at)
    event.add(
        "description",
        "This feed is regenerated on a schedule and Google Calendar may take hours to "
        "re-fetch it. Open a class's link to confirm it against the live CorePower site.",
    )
    event.add("transp", "TRANSPARENT")
    return event


def build_calendar(
    sessions: Iterable[dict[str, Any]],
    *,
    studio_name: str,
    generated_at: dt.datetime | None = None,
) -> Calendar:
    generated_at = generated_at or dt.datetime.now(dt.timezone.utc)

    cal = Calendar()
    cal.add("prodid", "-//cp-calendar//corepower-sync//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", f"CorePower Yoga — {studio_name}")
    cal.add(
        "x-wr-caldesc",
        f"Auto-synced class schedule for CorePower Yoga {studio_name}. "
        "Not official; generated from CorePower's public schedule data.",
    )
    # Hint to subscribers how often it's worth re-checking (advisory only -- Google
    # does not reliably honor this, hence the banner + per-event timestamps too).
    cal.add("x-published-ttl", "PT4H")

    cal.add_component(_build_sync_banner_event(studio_name=studio_name, generated_at=generated_at))
    for session in sessions:
        cal.add_component(_build_session_event(session, studio_name=studio_name, generated_at=generated_at))

    return cal


if __name__ == "__main__":
    import sys

    from fetch_schedule import fetch_sessions

    center = sys.argv[1] if len(sys.argv) > 1 else "22991841-d47c-4101-b8ff-423905dcf181"
    name = sys.argv[2] if len(sys.argv) > 2 else "North Boulder"
    sessions = fetch_sessions(center)
    cal = build_calendar(sessions, studio_name=name)
    sys.stdout.buffer.write(cal.to_ical())
