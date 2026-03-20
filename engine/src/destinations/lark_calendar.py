"""
Lark Calendar integration.
Create/update events on the user's or bot's calendar.
"""
from typing import Optional, Dict, Any, List

from .lark import _api_call


def get_primary_calendar_id() -> Optional[str]:
    """
    Get the primary calendar ID for the bot/tenant.
    Returns the calendar_id or None.
    """
    try:
        data = _api_call("GET", "/open-apis/calendar/v4/calendars", params={"page_size": 50})
        calendars = data.get("data", {}).get("calendar_list", [])
        for cal in calendars:
            if cal.get("role") == "owner" or cal.get("type") == "primary":
                return cal.get("calendar_id")
        # Fallback: return first calendar
        if calendars:
            return calendars[0].get("calendar_id")
        return None
    except Exception as e:
        print(f"[Lark Calendar] Error getting calendars: {e}")
        return None


def create_calendar_event(
    calendar_id: str,
    summary: str,
    description: str = "",
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    attendee_emails: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a calendar event.

    Args:
        calendar_id: The calendar to add the event to
        summary: Event title
        description: Event description
        start_timestamp: Unix timestamp (seconds) for start time
        end_timestamp: Unix timestamp (seconds) for end time
        attendee_emails: List of attendee email addresses

    Returns:
        Event data dict or None on failure
    """
    import time as time_mod

    if not start_timestamp:
        # Default: 1 hour from now
        start_timestamp = int(time_mod.time()) + 3600
    if not end_timestamp:
        end_timestamp = start_timestamp + 3600  # 1 hour duration

    event_body: Dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start_time": {
            "timestamp": str(start_timestamp),
        },
        "end_time": {
            "timestamp": str(end_timestamp),
        },
    }

    # Add attendees if provided
    if attendee_emails:
        event_body["attendees"] = [
            {"type": "user", "is_optional": False, "user_id": email}
            for email in attendee_emails
        ]

    try:
        data = _api_call(
            "POST",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/events",
            json_data=event_body,
        )
        event = data.get("data", {}).get("event", {})
        print(f"[Lark Calendar] Event created: {summary} -> {event.get('event_id')}")
        return event
    except Exception as e:
        print(f"[Lark Calendar] Error creating event: {e}")
        return None


def create_followup_event(
    calendar_id: str,
    client_name: str,
    subject: str,
    notes: str = "",
    followup_timestamp: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Convenience: create a follow-up calendar event for a client thread.
    """
    summary = f"Follow up: {client_name} - {subject[:40]}"
    description = f"Follow-up for email thread:\n{subject}\n\nNotes:\n{notes}"

    return create_calendar_event(
        calendar_id=calendar_id,
        summary=summary,
        description=description,
        start_timestamp=followup_timestamp,
    )
