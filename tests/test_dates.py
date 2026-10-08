import unittest
from datetime import date

from dashboard import dates

TODAY = date(2026, 10, 8)


def add(data, label="Mom's birthday", month=10, day=14, year=None):
    return dates.add(data, {"label": label, "month": month, "day": day, "year": year})


class AddTests(unittest.TestCase):
    def test_add_stores_and_trims(self):
        data = {}
        item = add(data, "  Mom's   birthday ")
        self.assertEqual(data["dates"], [item])
        self.assertEqual((item["label"], item["month"], item["day"], item["year"]), ("Mom's birthday", 10, 14, None))

    def test_bad_input_rejected(self):
        for body in [{"label": "", "month": 1, "day": 1}, {"label": "x", "month": 13, "day": 1}, {"label": "x", "month": 2, "day": 30},
                     {"label": "x", "month": 2, "day": 29, "year": 2027}, {"label": "x", "month": "1", "day": 1},
                     {"label": "x", "month": True, "day": 1}, {"label": "x" * 101, "month": 1, "day": 1}]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                dates.add({}, body)

    def test_yearly_feb_29_is_allowed(self):
        add({}, "Leap", 2, 29)

    def test_full(self):
        data = {}
        for i in range(dates.MAX_ITEMS):
            add(data, f"d{i}")
        with self.assertRaises(ValueError):
            add(data, "one more")

    def test_remove(self):
        data = {}
        item = add(data)
        dates.remove(data, item["id"])
        self.assertEqual(data["dates"], [])
        with self.assertRaises(KeyError):
            dates.remove(data, item["id"])


class ViewTests(unittest.TestCase):
    def test_yearly_counts_down_and_rolls_to_next_year(self):
        data = {}
        add(data, "Soon", 10, 14)
        add(data, "Today", 10, 8)
        add(data, "Passed", 10, 7)
        out = {i["label"]: i for i in dates.view(data, TODAY)["items"]}
        self.assertEqual((out["Today"]["days"], out["Today"]["when"]), (0, "Today"))
        self.assertEqual((out["Soon"]["days"], out["Soon"]["when"]), (6, "in 6 days"))
        self.assertEqual(out["Passed"]["days"], 364)

    def test_tomorrow_and_feb_29_in_a_common_year(self):
        data = {}
        add(data, "Tmrw", 10, 9)
        add(data, "Leap", 2, 29)
        out = {i["label"]: i for i in dates.view(data, date(2027, 2, 27))["items"]}
        self.assertEqual(out["Leap"]["days"], 1)  # Feb 28, 2027
        self.assertEqual(dates.view(data, TODAY)["items"][0]["when"], "Tomorrow")

    def test_one_time_past_is_hidden_from_soon_and_pruned(self):
        data = {}
        add(data, "Trip", 10, 20, 2026)
        add(data, "Old", 9, 1, 2026)
        add(data, "Yesterday", 10, 7, 2026)
        view = dates.view(data, TODAY)
        self.assertEqual([i["label"] for i in view["soon"]], ["Trip"])
        self.assertEqual({i["label"]: i["when"] for i in view["items"]}["Old"], "Past")
        dates.prune(data, TODAY)
        self.assertEqual(sorted(i["label"] for i in data["dates"]), ["Trip", "Yesterday"])

    def test_soon_is_limited_in_window_and_counts_the_rest(self):
        data = {}
        for n in range(5):
            add(data, f"d{n}", 10, 9 + n)
        add(data, "Far", 12, 25)
        view = dates.view(data, TODAY)
        self.assertEqual(len(view["soon"]), 3)
        self.assertEqual(view["moreSoon"], 2)

    def test_junk_in_the_file_is_skipped(self):
        data = {"dates": [None, {"id": "x"}, {"id": "y", "label": "L", "month": 2, "day": 31, "year": None}]}
        add(data, "Good")
        self.assertEqual([i["label"] for i in dates.view(data, TODAY)["items"]], ["Good"])
        dates.prune(data, TODAY)


if __name__ == "__main__":
    unittest.main()
