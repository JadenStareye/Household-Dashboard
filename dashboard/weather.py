import json
import time
import urllib.request
from datetime import datetime

URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=34.73&longitude=-86.59"
    "&current=temperature_2m,weather_code&hourly=precipitation_probability"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,sunrise,sunset"
    "&temperature_unit=fahrenheit&timezone=America%2FChicago&forecast_days=4"
)
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=34.73&longitude=-86.59&current=us_aqi"
RAIN_HOURS = 3


def kind_for(code):
    if code == 0:
        return "Clear", "clear"
    if code in (1, 2):
        return "Partly cloudy", "partly"
    if code == 3:
        return "Cloudy", "cloudy"
    if code in (45, 48):
        return "Fog", "fog"
    if 51 <= code <= 57:
        return "Drizzle", "rain"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "Rain", "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "Snow", "snow"
    if code >= 95:
        return "Thunderstorms", "storm"
    return "Cloudy", "cloudy"


def rain_soon(payload):
    # Highest rain chance over the next few hours; None if the hourly data is missing or doesn't line up.
    try:
        hourly = payload["hourly"]
        start = hourly["time"].index(payload["current"]["time"][:13] + ":00")
        window = [p for p in hourly["precipitation_probability"][start:start + RAIN_HOURS] if p is not None]
        return max(window) if window else None
    except (KeyError, ValueError, TypeError):
        return None


def aqi_of(payload):
    try:
        return round(payload["air"]["current"]["us_aqi"])
    except (KeyError, TypeError):
        return None


def parse(payload):
    current, daily = payload["current"], payload["daily"]
    label, kind = kind_for(current["weather_code"])
    outlook = []
    for i in (1, 2, 3):
        day = datetime.fromisoformat(daily["time"][i])
        outlook.append(
            {
                "day": day.strftime("%a"),
                "high": round(daily["temperature_2m_max"][i]),
                "kind": kind_for(daily["weather_code"][i])[1],
            }
        )
    return {
        "available": True,
        "temp": round(current["temperature_2m"]),
        "label": label,
        "kind": kind,
        "high": round(daily["temperature_2m_max"][0]),
        "low": round(daily["temperature_2m_min"][0]),
        "rain": daily["precipitation_probability_max"][0] or 0,
        "sunrise": daily["sunrise"][0],
        "sunset": daily["sunset"][0],
        "outlook": outlook,
        "rainSoon": rain_soon(payload),
        "aqi": aqi_of(payload),
    }


def _get_json(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_fetch():
    payload = _get_json(URL)
    try:
        payload["air"] = _get_json(AIR_URL)
    except Exception:
        pass  # air quality is optional; never lose the weather over it
    return payload


class WeatherService:
    def __init__(self, fetch=None, now=time.time, ttl=1800):
        self._fetch = fetch or _http_fetch
        self._now = now
        self._ttl = ttl
        self._cache = None
        self._fetched_at = 0.0

    def get(self):
        current = self._now()
        if self._cache and current - self._fetched_at < self._ttl:
            return self._out(False)
        try:
            self._cache = parse(self._fetch())
            self._fetched_at = current
            return self._out(False)
        except Exception:
            if self._cache:
                return self._out(True)
            return {"available": False}

    def _out(self, stale):
        updated = datetime.fromtimestamp(self._fetched_at).isoformat(timespec="minutes")
        return {**self._cache, "stale": stale, "updatedAt": updated}
