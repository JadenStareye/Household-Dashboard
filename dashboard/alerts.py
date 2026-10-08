import json
import threading
import time
import urllib.request
from datetime import datetime

URL = "https://api.weather.gov/alerts/active?point=34.73,-86.59"
HEADERS = {"User-Agent": "HomeDashboard (local household dashboard)", "Accept": "application/geo+json"}
WATCH_AND_WARNING = ("Tornado", "Severe Thunderstorm", "Flash Flood", "Winter Storm", "Extreme Heat",
                     "Excessive Heat", "Extreme Cold", "Tropical Storm", "Hurricane")
WARNING_ONLY = ("Flood", "Ice Storm", "Blizzard")
ALLOWED = {f"{n} {k}" for n in WATCH_AND_WARNING for k in ("Warning", "Watch")} | {f"{n} Warning" for n in WARNING_ONLY}
PRIORITY = {"Tornado": 0, "Severe Thunderstorm": 1, "Flash Flood": 2}
MAX_TEXT = 300
RETRY_SECONDS = 60


def _text(value):
    return value.strip()[:MAX_TEXT] if isinstance(value, str) else ""


def _when(value):
    # Timestamps without an offset are treated as server-local time.
    try:
        return datetime.fromisoformat(value.strip().upper().replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None


def _rank(item):
    name = item["event"].rsplit(" ", 1)[0]
    return (0 if item["level"] == "warning" else 1, PRIORITY.get(name, 3), item["_end"])


def _end_of(props):
    # Prefer `ends`; fall back to `expires` (also if `ends` is missing or unparseable).
    for key in ("ends", "expires"):
        text = props.get(key)
        when = _when(text)
        if when is not None:
            return text, when.timestamp()
    return None, None


def _parse_ranked(payload, now_ts):
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        return []
    found = []
    for feature in features:
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            continue
        event = _text(props.get("event"))
        alert_id = props.get("id")
        if (props.get("status") != "Actual" or props.get("messageType") == "Cancel"
                or event not in ALLOWED or not isinstance(alert_id, str) or not alert_id):
            continue
        end_text, end = _end_of(props)
        if end is None or end <= now_ts:
            continue
        found.append({
            "id": alert_id, "event": event,
            "level": "warning" if event.endswith("Warning") else "watch",
            "ends": end_text.strip(), "headline": _text(props.get("headline")) or event,
            "area": _text(props.get("areaDesc")), "_end": end,
        })
    found.sort(key=_rank)
    return found


def _public(item):
    return {k: v for k, v in item.items() if k != "_end"}


def parse(payload, now_ts):
    return [_public(a) for a in _parse_ranked(payload, now_ts)]


def _http_fetch():
    request = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class AlertService:
    def __init__(self, fetch=None, now=time.time, ttl=300):
        self._fetch = fetch or _http_fetch
        self._now = now
        self._ttl = ttl
        self._cache = []
        self._fetched_at = None
        self._retry_at = 0.0
        self._lock = threading.Lock()
        self.fresh = False  # True when the last get() used data fetched within ttl

    def get(self):
        with self._lock:
            return self._get()

    def _get(self):
        current = self._now()
        due = self._fetched_at is None or current - self._fetched_at >= self._ttl
        if due and current >= self._retry_at:
            try:
                payload = self._fetch()
                if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
                    raise ValueError("not an alerts feature collection")
                self._cache = _parse_ranked(payload, current)
                self._fetched_at = current
            except Exception:
                self._retry_at = current + RETRY_SECONDS
        self.fresh = self._fetched_at is not None and current - self._fetched_at < self._ttl
        return [_public(a) for a in self._cache if a["_end"] > current]
