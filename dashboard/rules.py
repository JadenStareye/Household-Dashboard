import calendar
import copy
import uuid
from datetime import date, timedelta

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
REPEATS = ["daily", "weekdays", "weekly", "biweekly", "monthly"]


def _monday(d):
    return d - timedelta(days=d.weekday())


def matches(rule, d):
    repeat = rule["repeat"]
    if repeat == "daily":
        return True
    if repeat == "weekdays":
        return d.weekday() < 5
    if repeat == "weekly":
        return DAYS[d.weekday()] in rule.get("days", [])
    if repeat == "biweekly":
        if DAYS[d.weekday()] not in rule.get("days", []):
            return False
        anchor = date.fromisoformat(rule["anchor"])
        return ((_monday(d) - _monday(anchor)).days // 7) % 2 == 0
    if repeat == "monthly":
        last = calendar.monthrange(d.year, d.month)[1]
        return d.day == min(rule["dayOfMonth"], last)
    raise ValueError(f"unknown repeat: {repeat}")


def _days(raw):
    days = raw.get("days")
    if not isinstance(days, list):
        raise ValueError("Pick at least one day")
    chosen = [day for day in DAYS if day in days]
    if not chosen:
        raise ValueError("Pick at least one day")
    return chosen


def validate(raw, today, existing_id=None):
    if not isinstance(raw, dict):
        raise ValueError("Rule must be an object")
    title = raw.get("title")
    title = title.strip() if isinstance(title, str) else ""
    if not title:
        raise ValueError("Enter a rule name")
    if len(title) > 200:
        raise ValueError("Rule name is too long (200 characters max)")
    repeat = raw.get("repeat")
    if repeat not in REPEATS:
        raise ValueError("Choose how often it repeats")
    rule = {"title": title, "repeat": repeat, "paused": bool(raw.get("paused", False))}
    if repeat in ("weekly", "biweekly"):
        rule["days"] = _days(raw)
    if repeat == "biweekly":
        anchor = raw.get("anchor")
        if anchor is None:
            anchor = today.isoformat()
        try:
            rule["anchor"] = date.fromisoformat(anchor).isoformat()
        except (TypeError, ValueError):
            raise ValueError("Start date must be a valid date") from None
    if repeat == "monthly":
        dom = raw.get("dayOfMonth")
        if isinstance(dom, bool) or not isinstance(dom, int) or not 1 <= dom <= 31:
            raise ValueError("Day of month must be 1 to 31")
        rule["dayOfMonth"] = dom
    return rule


def seed(data, seed_rules):
    if data.get("rulesSeeded") is True:
        return
    data["rules"] = [dict(copy.deepcopy(r), paused=False) for r in seed_rules]
    data["rulesSeeded"] = True


def _rules(data):
    return data.setdefault("rules", [])


def create(data, raw, today):
    rule = validate(raw, today)
    rule["id"] = uuid.uuid4().hex[:8]
    _rules(data).append(rule)
    return rule


def update(data, rule_id, raw, today):
    rs = _rules(data)
    for i, existing in enumerate(rs):
        if existing["id"] == rule_id:
            rule = validate(raw, today, existing_id=rule_id)
            rule["id"] = rule_id
            rs[i] = rule
            return rule
    raise KeyError(rule_id)


def delete(data, rule_id):
    rs = _rules(data)
    for existing in rs:
        if existing["id"] == rule_id:
            rs.remove(existing)
            return
    raise KeyError(rule_id)
