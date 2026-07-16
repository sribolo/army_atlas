"""Short relative-time labels ("2d", "5h", "just now") for feed-style UI."""

from datetime import datetime, timezone


def time_ago(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    if seconds < 2592000:
        return f"{int(seconds // 86400)}d"
    if seconds < 31536000:
        return f"{int(seconds // 2592000)}mo"
    return f"{int(seconds // 31536000)}y"


def day_label(dt: datetime) -> str:
    """Date-separator label for grouping a list of timestamps by calendar
    day — "Today", "Yesterday", a weekday name within the last week, or a
    full date further back. No per-user timezone is stored anywhere in
    this app, so this compares UTC calendar dates like every other
    timestamp here (see time_ago above).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta_days = (datetime.now(timezone.utc).date() - dt.date()).days
    if delta_days == 0:
        return "Today"
    if delta_days == 1:
        return "Yesterday"
    if delta_days < 7:
        return dt.strftime("%A")
    return dt.strftime("%b %-d, %Y")
