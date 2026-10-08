import copy
import re
import uuid
from datetime import date, timedelta

KEEP_DAYS = 60
MAX_ITEMS = 60
MAX_TEXT = 200
TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
KINDS = ("ingredients", "steps")


def _plans(data):
    return data.setdefault("plans", [])


def _new_id():
    return uuid.uuid4().hex[:8]


def _usable(plan):
    """A plan the screen can show; hand-edited junk in data.json is skipped, never fatal."""
    try:
        date.fromisoformat(plan["date"])
        return (
            isinstance(plan["id"], str)
            and isinstance(plan["title"], str)
            and isinstance(plan.get("startTime", ""), str)
            and (plan.get("startTime", "") == "" or bool(TIME.fullmatch(plan["startTime"])))
            and (plan.get("prepMinutes") is None or (isinstance(plan["prepMinutes"], int) and not isinstance(plan["prepMinutes"], bool)))
            and all(isinstance(i["text"], str) and isinstance(i["id"], str) for kind in KINDS for i in plan[kind])
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _find(data, plan_id):
    for plan in _plans(data):
        if _usable(plan) and plan["id"] == plan_id:
            return plan
    raise KeyError(plan_id)


def find(data, plan_id):
    return _find(data, plan_id)


def _title(raw):
    title = raw.strip() if isinstance(raw, str) else ""
    if not title:
        raise ValueError("Enter a name for the dinner")
    if len(title) > MAX_TEXT:
        raise ValueError(f"Keep the name to {MAX_TEXT} letters or fewer")
    return title


def _date(raw, today):
    try:
        d = raw if isinstance(raw, date) else date.fromisoformat(raw)
    except (TypeError, ValueError):
        d = None
    if d is None or d < today - timedelta(days=KEEP_DAYS) or d > today + timedelta(days=365):
        raise ValueError("Pick a date within the last two months or the next year")
    return d.isoformat()


def _prep(raw):
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= 600:
        raise ValueError("Prep time must be a whole number of minutes from 1 to 600")
    return raw


def _start(raw):
    if raw is None or raw == "":
        return ""
    if not isinstance(raw, str) or not TIME.fullmatch(raw):
        raise ValueError("Start time must look like 17:30")
    return raw


def _lines(raw, label):
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"{label} must be a list of lines")
    lines = [x.strip() for x in raw if x.strip()]
    if len(lines) > MAX_ITEMS:
        raise ValueError(f"Keep {label.lower()} to {MAX_ITEMS} lines or fewer")
    if any(len(x) > MAX_TEXT for x in lines):
        raise ValueError(f"Each line in {label.lower()} must be {MAX_TEXT} letters or fewer")
    return lines


def _items(lines, old):
    """Keep the id and checked state of a line that is unchanged at the same position."""
    items = []
    for i, text in enumerate(lines):
        if i < len(old) and old[i]["text"] == text:
            items.append(old[i])
        else:
            items.append({"id": _new_id(), "text": text, "done": False})
    return items


def _url(raw, known, current):
    if raw is None or raw == "":
        return ""
    if raw == current:
        return raw
    if not isinstance(raw, str) or raw not in known:
        raise ValueError("That recipe link can't be used")
    return raw


def _build(body, base, today, known):
    """A complete, validated plan. Nothing is stored until every field passes."""
    def pick(key, default):
        return body[key] if key in body else base.get(key, default)

    plan = {
        "id": base.get("id") or _new_id(),
        "title": _title(pick("title", None)),
        "url": _url(pick("url", ""), known, base.get("url", "")),
        "date": _date(pick("date", today), today),
        "prepMinutes": _prep(pick("prepMinutes", None)),
        "startTime": _start(pick("startTime", "")),
    }
    for kind, label in (("ingredients", "Ingredients"), ("steps", "Steps")):
        old = base.get(kind, [])
        lines = _lines(body[kind], label) if kind in body else [i["text"] for i in old]
        plan[kind] = _items(lines, old)
    return plan


def create(data, body, today, known):
    plan = _build(body, {}, today, known)
    _plans(data).append(plan)
    return plan


def update(data, plan_id, body, today, known):
    old = _find(data, plan_id)
    new = _build(body, old, today, known)
    plans = _plans(data)
    plans[plans.index(old)] = new
    return new


def delete(data, plan_id):
    plan = _find(data, plan_id)
    _plans(data).remove(plan)
    return copy.deepcopy(plan)


def restore(data, record):
    plans = _plans(data)
    for saved in record.get("plans", []):
        if not any(p.get("id") == saved["id"] for p in plans if isinstance(p, dict)):
            plans.append(copy.deepcopy(saved))


def check(data, plan_id, kind, item_id):
    if kind not in KINDS:
        raise ValueError("Pick ingredients or steps")
    for item in _find(data, plan_id)[kind]:
        if item["id"] == item_id:
            item["done"] = not item.get("done")
            return item
    raise KeyError(item_id)


def _fresh(items):
    return [{"id": _new_id(), "text": i["text"], "done": False} for i in items]


def copy_plan(data, plan_id, today):
    old = _find(data, plan_id)
    plan = {
        "id": _new_id(),
        "title": old["title"],
        "url": old.get("url") or "",
        "date": today.isoformat(),
        "prepMinutes": old.get("prepMinutes"),
        "startTime": old.get("startTime") or "",
        "ingredients": _fresh(old["ingredients"]),
        "steps": _fresh(old["steps"]),
    }
    _plans(data).append(plan)
    return plan


def from_recipe(data, recipe, today):
    iso = today.isoformat()
    for plan in _plans(data):
        if _usable(plan) and plan["date"] == iso and plan.get("url") == recipe["url"]:
            return plan
    try:
        minutes = _prep(recipe.get("minutes"))
    except ValueError:
        minutes = None
    plan = {
        "id": _new_id(),
        "title": recipe["name"].strip()[:MAX_TEXT],
        "url": recipe["url"],
        "date": iso,
        "prepMinutes": minutes,
        "startTime": "",
        "ingredients": [],
        "steps": [],
    }
    _plans(data).append(plan)
    return plan


def prune(data, today):
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    data["plans"] = [p for p in _plans(data) if not _usable(p) or p["date"] >= cutoff]


def _shown(plan):
    return {
        "id": plan["id"],
        "title": plan["title"],
        "url": plan.get("url") or "",
        "date": plan["date"],
        "prepMinutes": plan.get("prepMinutes"),
        "startTime": plan.get("startTime") or "",
        "ingredients": [{"id": i["id"], "text": i["text"], "done": bool(i.get("done"))} for i in plan["ingredients"]],
        "steps": [{"id": i["id"], "text": i["text"], "done": bool(i.get("done"))} for i in plan["steps"]],
    }


def _nudge(todays):
    due = [p for p in todays if p["startTime"] and (not p["steps"] or any(not s["done"] for s in p["steps"]))]
    if not due:
        return None
    first = min(due, key=lambda p: p["startTime"])
    return {"id": first["id"], "title": first["title"], "startTime": first["startTime"]}


def view(data, today):
    iso = today.isoformat()
    shown = [_shown(p) for p in _plans(data) if _usable(p)]
    todays = sorted((p for p in shown if p["date"] == iso), key=lambda p: p["startTime"] or "99:99")
    future = sorted((p for p in shown if p["date"] > iso), key=lambda p: (p["date"], p["startTime"] or "99:99"))
    past = sorted((p for p in shown if p["date"] < iso), key=lambda p: p["date"], reverse=True)
    return {"items": todays + future + past, "nudge": _nudge(todays)}
