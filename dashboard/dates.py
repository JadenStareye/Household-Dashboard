import calendar
import uuid
from datetime import date, timedelta

MAX_ITEMS = 100
MAX_TEXT = 100
WINDOW = 30  # days ahead that show on the Today screen
SHOW = 3
PAST_KEEP = 7  # a finished one-time countdown is removed this many days later


def _valid(month, day, year):
    if isinstance(month, bool) or isinstance(day, bool) or not isinstance(month, int) or not isinstance(day, int):
        return False
    if not 1 <= month <= 12 or year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2200):
        return False
    return 1 <= day <= calendar.monthrange(year or 2000, month)[1]  # 2000 is a leap year: yearly Feb 29 is allowed


def _usable(item):
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str) and item["id"]
        and isinstance(item.get("label"), str) and item["label"].strip()
        and _valid(item.get("month"), item.get("day"), item.get("year"))
    )


def _stored(data):
    items = data.setdefault("dates", [])
    if not isinstance(items, list):
        items = data["dates"] = []
    return items


def add(data, body):
    label = " ".join(body["label"].split()) if isinstance(body.get("label"), str) else ""
    if not label:
        raise ValueError("Enter a name")
    if len(label) > MAX_TEXT:
        raise ValueError("Keep the name to 100 letters or fewer")
    month, day, year = body.get("month"), body.get("day"), body.get("year")
    if not _valid(month, day, year):
        raise ValueError("That date doesn't exist")
    items = _stored(data)
    if sum(1 for i in items if _usable(i)) >= MAX_ITEMS:
        raise ValueError("The list is full. Remove some dates first.")
    item = {"id": uuid.uuid4().hex[:8], "label": label, "month": month, "day": day, "year": year}
    items.append(item)
    return item


def remove(data, item_id):
    items = _stored(data)
    found = next((i for i in items if _usable(i) and i["id"] == item_id), None)
    if found is None:
        raise KeyError(item_id)
    items.remove(found)


def _next(item, today):
    """The next date this falls on (today counts), or None for a one-time date already past."""
    month, day, year = item["month"], item["day"], item.get("year")
    if year is not None:
        found = date(year, month, day)
        return found if found >= today else None
    for y in (today.year, today.year + 1):
        # Feb 29 falls on Feb 28 in a common year.
        found = date(y, month, min(day, calendar.monthrange(y, month)[1]))
        if found >= today:
            return found


def _when(days):
    return "Today" if days == 0 else "Tomorrow" if days == 1 else f"in {days} days"


def prune(data, today):
    cutoff = today - timedelta(days=PAST_KEEP)
    data["dates"] = [
        i for i in _stored(data)
        if not _usable(i) or i.get("year") is None or date(i["year"], i["month"], i["day"]) >= cutoff
    ]


def view(data, today):
    shown = []
    for item in _stored(data):
        if not _usable(item):
            continue
        upcoming = _next(item, today)
        days = (upcoming - today).days if upcoming else None
        shown.append({
            "id": item["id"], "label": item["label"].strip(), "month": item["month"], "day": item["day"],
            "year": item.get("year"), "days": days, "when": _when(days) if days is not None else "Past",
        })
    shown.sort(key=lambda i: (i["days"] is None, i["days"] if i["days"] is not None else 0, i["label"].casefold()))
    soon = [i for i in shown if i["days"] is not None and i["days"] <= WINDOW]
    return {"items": shown, "soon": soon[:SHOW], "moreSoon": max(0, len(soon) - SHOW)}
