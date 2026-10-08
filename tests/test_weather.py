import unittest

from dashboard import weather

SAMPLE = {
    "current": {"time": "2026-10-06T14:15", "temperature_2m": 78.4, "weather_code": 0},
    "hourly": {
        "time": [f"2026-10-06T{h:02d}:00" for h in range(24)],
        "precipitation_probability": [0] * 14 + [10, 55, 30, 90] + [0] * 6,
    },
    "air": {"current": {"us_aqi": 41.6}},
    "daily": {
        "time": ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"],
        "weather_code": [0, 2, 61, 95],
        "temperature_2m_max": [84.2, 82.1, 79.0, 74.4],
        "temperature_2m_min": [61.0, 60.0, 58.0, 55.0],
        "precipitation_probability_max": [5, 10, 60, 80],
        "sunrise": ["2026-10-06T06:58"] * 4,
        "sunset": ["2026-10-06T18:21"] * 4,
    },
}


class ParseTests(unittest.TestCase):
    def test_parse(self):
        out = weather.parse(SAMPLE)
        self.assertTrue(out["available"])
        self.assertEqual((out["temp"], out["label"], out["kind"]), (78, "Clear", "clear"))
        self.assertEqual((out["high"], out["low"], out["rain"]), (84, 61, 5))
        self.assertEqual(out["sunrise"], "2026-10-06T06:58")
        self.assertEqual(out["outlook"][0], {"day": "Wed", "high": 82, "kind": "partly"})
        self.assertEqual([o["kind"] for o in out["outlook"]], ["partly", "rain", "storm"])

    def test_rain_soon_is_max_of_next_three_hours_from_now(self):
        out = weather.parse(SAMPLE)
        self.assertEqual(out["rainSoon"], 55)  # hours 14-16; the 90 at 17:00 is outside the window
        self.assertEqual(out["aqi"], 42)

    def test_optional_data_missing_gives_none(self):
        bare = {k: v for k, v in SAMPLE.items() if k not in ("hourly", "air")}
        out = weather.parse(bare)
        self.assertIsNone(out["rainSoon"])
        self.assertIsNone(out["aqi"])

    def test_kind_for_codes(self):
        self.assertEqual(weather.kind_for(3)[1], "cloudy")
        self.assertEqual(weather.kind_for(45)[1], "fog")
        self.assertEqual(weather.kind_for(73)[1], "snow")
        self.assertEqual(weather.kind_for(81)[1], "rain")


class ServiceTests(unittest.TestCase):
    def make(self, fetch):
        self.clock = [1000.0]
        return weather.WeatherService(fetch=fetch, now=lambda: self.clock[0], ttl=1800)

    def test_cache_within_ttl(self):
        calls = []
        svc = self.make(lambda: calls.append(1) or SAMPLE)
        svc.get()
        self.clock[0] += 600
        out = svc.get()
        self.assertEqual(len(calls), 1)
        self.assertFalse(out["stale"])

    def test_refetch_after_ttl(self):
        calls = []
        svc = self.make(lambda: calls.append(1) or SAMPLE)
        svc.get()
        self.clock[0] += 1801
        svc.get()
        self.assertEqual(len(calls), 2)

    def test_failure_after_success_is_stale(self):
        state = {"ok": True}

        def fetch():
            if state["ok"]:
                return SAMPLE
            raise OSError("offline")

        svc = self.make(fetch)
        svc.get()
        state["ok"] = False
        self.clock[0] += 1801
        out = svc.get()
        self.assertTrue(out["available"])
        self.assertTrue(out["stale"])
        self.assertIn("updatedAt", out)

    def test_first_failure_is_unavailable(self):
        def fetch():
            raise OSError("offline")

        self.assertEqual(self.make(fetch).get(), {"available": False})


if __name__ == "__main__":
    unittest.main()
