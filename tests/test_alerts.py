import unittest
from datetime import datetime, timezone

from dashboard import alerts

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc).timestamp()


def feat(event="Tornado Warning", id="urn:1", ends="2026-10-08T14:00:00-05:00", **extra):
    props = {
        "id": id, "event": event, "status": "Actual", "messageType": "Alert",
        "ends": ends, "expires": ends, "headline": event + " issued", "areaDesc": "Madison, AL",
    }
    props.update(extra)
    return {"properties": props}


def payload(*features):
    return {"features": list(features)}


class ParseTests(unittest.TestCase):
    def parse(self, *features):
        return alerts.parse(payload(*features), NOW)

    def test_tornado_warning_kept(self):
        out = self.parse(feat())
        self.assertEqual(out, [{
            "id": "urn:1", "event": "Tornado Warning", "level": "warning",
            "ends": "2026-10-08T14:00:00-05:00", "headline": "Tornado Warning issued",
            "area": "Madison, AL",
        }])

    def test_watch_level(self):
        out = self.parse(feat("Severe Thunderstorm Watch"))
        self.assertEqual(out[0]["level"], "watch")

    def test_filters(self):
        self.assertEqual(self.parse(feat("Wind Advisory")), [])
        self.assertEqual(self.parse(feat(messageType="Cancel")), [])
        self.assertEqual(self.parse(feat(status="Test")), [])
        self.assertEqual(self.parse(feat(ends="2026-10-08T06:00:00-05:00")), [])
        self.assertEqual(self.parse(feat("Flood Watch")), [])
        self.assertEqual(len(self.parse(feat("Flood Warning"))), 1)
        self.assertEqual(self.parse(feat("Ice Storm Watch")), [])

    def test_missing_id_skipped(self):
        f = feat()
        del f["properties"]["id"]
        self.assertEqual(self.parse(f), [])
        self.assertEqual(self.parse(feat(id="")), [])
        self.assertEqual(self.parse(feat(id=5)), [])

    def test_expires_only(self):
        out = self.parse(feat(ends=None, expires="2026-10-08T15:00:00-05:00"))
        self.assertEqual(out[0]["ends"], "2026-10-08T15:00:00-05:00")

    def test_expired_expires_only_and_neither(self):
        self.assertEqual(self.parse(feat(ends=None, expires="2026-10-08T06:00:00-05:00")), [])
        self.assertEqual(self.parse(feat(ends=None, expires=None)), [])

    def test_ordering(self):
        out = self.parse(
            feat("Severe Thunderstorm Watch", id="a", ends="2026-10-08T13:00:00-05:00"),
            feat("Flash Flood Warning", id="b"),
            feat("Tornado Warning", id="c", ends="2026-10-08T15:00:00-05:00"),
            feat("Flood Warning", id="d", ends="2026-10-08T13:00:00-05:00"),
            feat("Tornado Warning", id="e", ends="2026-10-08T13:30:00-05:00"),
        )
        self.assertEqual([a["id"] for a in out], ["e", "c", "b", "d", "a"])

    def test_trim_and_cut(self):
        out = self.parse(feat(headline="  " + "x" * 400 + "  ", areaDesc="  Here  "))
        self.assertEqual(out[0]["headline"], "x" * 300)
        self.assertEqual(out[0]["area"], "Here")

    def test_headline_falls_back_to_event(self):
        out = self.parse(feat(headline=None))
        self.assertEqual(out[0]["headline"], "Tornado Warning")

    def test_junk(self):
        for junk in (None, [], {}, {"features": "x"}, {"features": [{}]},
                     {"features": [{"properties": None}]}, {"features": [None, "x"]}):
            self.assertEqual(alerts.parse(junk, NOW), [])

    def test_no_private_keys(self):
        self.assertNotIn("_end", self.parse(feat())[0])

    def test_timestamp_forms(self):
        for end in ("2026-10-08T20:00:00Z", "2026-10-08T20:00:00z", " 2026-10-08T20:00:00Z ",
                    "2026-10-08T20:00:00"):
            out = self.parse(feat(ends=end))
            self.assertEqual(len(out), 1, end)
            self.assertEqual(out[0]["ends"], end.strip())

    def test_ends_unparseable_falls_back_to_expires(self):
        out = self.parse(feat(ends="soon", expires="2026-10-08T15:00:00-05:00"))
        self.assertEqual(out[0]["ends"], "2026-10-08T15:00:00-05:00")

    def test_ends_differs_from_expires(self):
        out = self.parse(feat(ends="2026-10-08T16:00:00-05:00", expires="2026-10-08T14:00:00-05:00"))
        self.assertEqual(out[0]["ends"], "2026-10-08T16:00:00-05:00")

    def test_event_allow_list_extras(self):
        self.assertEqual(self.parse(feat("Special Weather Statement")), [])
        self.assertEqual(len(self.parse(feat("Tornado Watch"))), 1)


class ServiceTests(unittest.TestCase):
    def make(self, fetch):
        self.clock = [NOW]
        return alerts.AlertService(fetch=fetch, now=lambda: self.clock[0], ttl=300)

    def test_cache_within_ttl(self):
        calls = []
        svc = self.make(lambda: calls.append(1) or payload(feat()))
        self.assertEqual(len(svc.get()), 1)
        self.clock[0] += 299
        svc.get()
        self.assertEqual(len(calls), 1)
        self.assertTrue(svc.fresh)

    def test_refetch_after_ttl(self):
        calls = []
        svc = self.make(lambda: calls.append(1) or payload(feat()))
        svc.get()
        self.clock[0] += 300
        svc.get()
        self.assertEqual(len(calls), 2)

    def test_cached_alert_expires(self):
        svc = self.make(lambda: payload(feat(ends="2026-10-08T07:02:00-05:00")))
        self.assertEqual(len(svc.get()), 1)
        self.clock[0] += 120
        self.assertEqual(svc.get(), [])

    def test_failure_keeps_last_good_then_drops_when_expired(self):
        state = {"ok": True}

        def fetch():
            if state["ok"]:
                return payload(feat(ends="2026-10-08T07:10:00-05:00"))
            raise OSError("offline")

        svc = self.make(fetch)
        svc.get()
        state["ok"] = False
        self.clock[0] += 301
        self.assertEqual(len(svc.get()), 1)
        self.assertFalse(svc.fresh)
        self.clock[0] += 400
        self.assertEqual(svc.get(), [])

    def test_no_data_failure(self):
        def fetch():
            raise OSError("offline")

        svc = self.make(fetch)
        self.assertEqual(svc.get(), [])
        self.assertFalse(svc.fresh)

    def test_backoff(self):
        calls = []

        def fetch():
            calls.append(1)
            raise OSError("offline")

        svc = self.make(fetch)
        svc.get()
        self.clock[0] += 30
        svc.get()
        self.assertEqual(len(calls), 1)
        self.clock[0] += 31
        svc.get()
        self.assertEqual(len(calls), 2)

    def test_recovery_after_failure(self):
        state = {"ok": False}

        def fetch():
            if state["ok"]:
                return payload(feat())
            raise OSError("offline")

        svc = self.make(fetch)
        svc.get()
        state["ok"] = True
        self.clock[0] += 61
        self.assertEqual(len(svc.get()), 1)
        self.assertTrue(svc.fresh)

    def test_junk_payload_is_failure_keeps_last_good(self):
        state = {"data": payload(feat())}
        calls = []

        def fetch():
            calls.append(1)
            return state["data"]

        svc = self.make(fetch)
        self.assertEqual(len(svc.get()), 1)
        for junk in ("garbage", None, [], {"features": "x"}, {}):
            state["data"] = junk
            self.clock[0] += 301
            before = len(calls)
            self.assertEqual(len(svc.get()), 1)
            self.assertFalse(svc.fresh)
            self.assertEqual(len(calls), before + 1)
            self.clock[0] += 10
            svc.get()
            self.assertEqual(len(calls), before + 1)  # back-off
            self.clock[0] += 51

    def test_empty_success_clears_cache(self):
        state = {"data": payload(feat())}
        svc = self.make(lambda: state["data"])
        self.assertEqual(len(svc.get()), 1)
        state["data"] = {"features": []}
        self.clock[0] += 301
        self.assertEqual(svc.get(), [])
        self.assertTrue(svc.fresh)

    def test_fresh_flag(self):
        state = {"ok": True}

        def fetch():
            if state["ok"]:
                return payload(feat())
            raise OSError("x")

        svc = self.make(fetch)
        svc.get()
        self.assertTrue(svc.fresh)
        state["ok"] = False
        self.clock[0] += 301
        svc.get()
        self.assertFalse(svc.fresh)
        self.clock[0] += 10
        svc.get()
        self.assertFalse(svc.fresh)

    def test_never_raises_on_junk(self):
        svc = self.make(lambda: "garbage")
        self.assertEqual(svc.get(), [])


if __name__ == "__main__":
    unittest.main()
