import copy
import uuid
from datetime import date, timedelta

from dashboard.rules import DAYS, matches  # noqa: F401

KEEP_DAYS = 30
rule_matches = matches


def _tasks(data):
    return data.setdefault("tasks", [])


def _new(title, d, source, rule_id=None):
    return {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "date": d.isoformat(),
        "done": False,
        "dismissed": False,
        "source": source,
        "ruleId": rule_id,
    }


def _find(data, task_id):
    for task in _tasks(data):
        if task["id"] == task_id:
            return task
    raise KeyError(task_id)


def generate_recurring(data, rules, today):
    tasks = _tasks(data)
    generated = data.setdefault("generated", [])
    iso = today.isoformat()
    for rule in rules:
        if rule.get("paused") or not matches(rule, today):
            continue
        key = f"{rule['id']}|{iso}"
        if key in generated:
            continue
        generated.append(key)
        already_here = any(
            t["ruleId"] == rule["id"] and t["date"] == iso and not t["done"] and not t["dismissed"]
            for t in tasks
        )
        if not already_here:
            task = _new(rule["title"], today, "recurring", rule["id"])
            task["order"] = _next_order(data)
            tasks.append(task)


def _order(task):
    return task.get("order", 0)


def _next_order(data):
    return max((_order(t) for t in _tasks(data)), default=0) + 1


def _clean_title(title):
    title = (title or "").strip()
    if not title:
        raise ValueError("Enter a task name")
    return title[:200]


def _parse_date(value, today):
    try:
        d = value if isinstance(value, date) else date.fromisoformat(value)
    except (TypeError, ValueError):
        d = None
    if d is None or d < today or d > today + timedelta(days=365):
        raise ValueError("Pick a date within the next year")
    return d


def add_task(data, title, today, date=None):
    title = _clean_title(title)
    d = today if date is None else _parse_date(date, today)
    task = _new(title, d, "manual")
    task["order"] = _next_order(data)
    _tasks(data).append(task)
    return task


def edit_title(data, task_id, title):
    task = _find(data, task_id)
    task["title"] = _clean_title(title)
    return task


def _group(data, task, today):
    """Tasks an action on `task` applies to: its carryover rule group, or just itself."""
    if today is None or task["source"] != "recurring" or not task.get("ruleId"):
        return [task]
    iso = today.isoformat()
    if task["dismissed"] or task["done"] or task["date"] >= iso:
        return [task]
    return [
        t for t in _tasks(data)
        if t["ruleId"] == task["ruleId"] and not t["dismissed"] and not t["done"] and t["date"] < iso
    ]


def toggle_done(data, task_id, today=None):
    task = _find(data, task_id)
    members = _group(data, task, today)
    if len(members) > 1:
        for t in members:
            t["done"] = True
        return task
    task["done"] = not task["done"]
    return task


def move_to_tomorrow(data, task_id, today):
    task = _find(data, task_id)
    lowest = min((_order(t) for t in _tasks(data)), default=1)
    for t in _group(data, task, today):
        if t is not task:
            t["dismissed"] = True
    task["date"] = (today + timedelta(days=1)).isoformat()
    task["done"] = False
    task["order"] = lowest - 1
    return task


def dismiss(data, task_id, today=None):
    task = _find(data, task_id)
    for t in _group(data, task, today):
        t["dismissed"] = True
    return task


def dismiss_carryover(data, today):
    iso = today.isoformat()
    for t in _tasks(data):
        if not t["dismissed"] and not t["done"] and t["date"] < iso:
            t["dismissed"] = True


def remove(data, task_id):
    task = _find(data, task_id)
    if task["source"] != "manual":
        raise ValueError("Only tasks you added can be removed")
    _tasks(data).remove(task)


def reorder(data, ids, today):
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("ids must be a list of task ids")
    iso = today.isoformat()
    by_id = {
        t["id"]: t for t in _tasks(data)
        if not t["dismissed"] and not t["done"] and t["date"] == iso
    }
    n = 0
    for task_id in ids:
        task = by_id.pop(task_id, None)
        if task is not None:
            n += 1
            task["order"] = n


def _carryover(data, iso):
    groups = {}
    for t in _tasks(data):
        if t["dismissed"] or t["done"] or t["date"] >= iso:
            continue
        key = t["ruleId"] if t["source"] == "recurring" and t.get("ruleId") else t["id"]
        groups.setdefault(key, []).append(t)
    entries = []
    for members in groups.values():
        rep = max(members, key=lambda t: t["date"])
        entries.append(dict(rep, ids=[t["id"] for t in members], count=len(members)))
    entries.sort(key=lambda e: e["date"])
    return entries


def view(data, today):
    iso = today.isoformat()
    live = [t for t in _tasks(data) if not t["dismissed"]]
    todays = sorted((t for t in live if t["date"] == iso), key=lambda t: (t["done"], _order(t)))
    future = sorted(
        (t for t in live if t["date"] > iso and not t["done"]),
        key=lambda t: (t["date"], _order(t)),
    )
    upcoming = [{"id": t["id"], "title": t["title"], "date": t["date"], "source": t.get("source", "manual")} for t in future]
    return {"carryover": _carryover(data, iso), "today": todays, "upcoming": upcoming}


def snapshot_for_undo(data, label, task_ids):
    wanted = set(task_ids)
    return {"label": label, "tasks": [copy.deepcopy(t) for t in _tasks(data) if t["id"] in wanted]}


def restore(data, record):
    tasks = _tasks(data)
    for saved in record["tasks"]:
        for i, t in enumerate(tasks):
            if t["id"] == saved["id"]:
                tasks[i] = copy.deepcopy(saved)
                break
        else:
            tasks.append(copy.deepcopy(saved))


def prune(data, today):
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    data["tasks"] = [
        t for t in _tasks(data) if not ((t["done"] or t["dismissed"]) and t["date"] < cutoff)
    ]
    data["generated"] = [k for k in data.setdefault("generated", []) if k.split("|")[1] >= cutoff]
