import unittest
from datetime import date, timedelta

from dashboard import plans

MON = date(2026, 10, 5)
TUE = date(2026, 10, 6)
KNOWN = {"https://example.com/r"}


def make(data=None, **fields):
    data = {} if data is None else data
    body = {"title": "Spicy chicken"}
    body.update(fields)
    return data, plans.create(data, body, MON, KNOWN)


def texts(items):
    return [i["text"] for i in items]


class CreateTests(unittest.TestCase):
    def test_defaults(self):
        data, plan = make()
        self.assertEqual(data["plans"], [plan])
        self.assertRegex(plan["id"], r"^[0-9a-f]{8}$")
        self.assertEqual(plan["title"], "Spicy chicken")
        self.assertEqual(plan["date"], "2026-10-05")
        self.assertIsNone(plan["prepMinutes"])
        self.assertEqual((plan["startTime"], plan["url"]), ("", ""))
        self.assertEqual((plan["ingredients"], plan["steps"]), ([], []))

    def test_full_plan_trims_and_drops_blank_lines(self):
        _, plan = make(
            title="  Spicy chicken  ", date="2026-10-07", prepMinutes=40, startTime="17:15",
            url="https://example.com/r", ingredients=["  salt ", "", "pepper", "   "], steps=["Heat pan", "Cook"],
        )
        self.assertEqual(plan["title"], "Spicy chicken")
        self.assertEqual((plan["date"], plan["prepMinutes"], plan["startTime"]), ("2026-10-07", 40, "17:15"))
        self.assertEqual(texts(plan["ingredients"]), ["salt", "pepper"])
        self.assertEqual(texts(plan["steps"]), ["Heat pan", "Cook"])
        self.assertTrue(all(i["done"] is False and len(i["id"]) == 8 for i in plan["ingredients"] + plan["steps"]))

    def test_bad_values_are_refused_and_change_nothing(self):
        far = (MON + timedelta(days=366)).isoformat()
        old = (MON - timedelta(days=61)).isoformat()
        bad = [
            {"title": ""}, {"title": "   "}, {"title": 5}, {"title": "x" * 201},
            {"date": "nope"}, {"date": far}, {"date": old}, {"date": 5},
            {"prepMinutes": 0}, {"prepMinutes": 601}, {"prepMinutes": "5"}, {"prepMinutes": True}, {"prepMinutes": 1.5},
            {"startTime": "7:30"}, {"startTime": "24:00"}, {"startTime": "17:60"}, {"startTime": 5},
            {"ingredients": "salt"}, {"ingredients": [1]}, {"ingredients": ["x"] * 61}, {"ingredients": ["x" * 201]},
            {"steps": "Heat pan"}, {"steps": ["x"] * 61},
            {"url": "https://evil.example.org/x"}, {"url": 5},
        ]
        data = {}
        for fields in bad:
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError) as caught:
                    plans.create(data, {"title": "Dinner", **fields}, MON, KNOWN)
                self.assertTrue(str(caught.exception))
        self.assertEqual(data.get("plans", []), [])

    def test_sixty_items_and_edge_dates_are_fine(self):
        _, plan = make(ingredients=["x"] * 60, date=(MON - timedelta(days=60)).isoformat())
        self.assertEqual(len(plan["ingredients"]), 60)
        make(date=(MON + timedelta(days=365)).isoformat())


class UpdateTests(unittest.TestCase):
    def test_unchanged_lines_keep_ids_and_checks(self):
        data, plan = make(steps=["a", "b", "c"])
        before = {s["text"]: dict(s) for s in plan["steps"]}
        plans.check(data, plan["id"], "steps", plan["steps"][0]["id"])
        plans.check(data, plan["id"], "steps", plan["steps"][2]["id"])
        new = plans.update(data, plan["id"], {"steps": ["a", "B", "c"]}, MON, KNOWN)
        a, b, c = new["steps"]
        self.assertEqual((a["id"], a["done"]), (before["a"]["id"], True))
        self.assertNotEqual(b["id"], before["b"]["id"])
        self.assertEqual((b["text"], b["done"]), ("B", False))
        self.assertEqual((c["id"], c["done"]), (before["c"]["id"], True))
        self.assertEqual(data["plans"], [new])

    def test_absent_keys_are_unchanged(self):
        data, plan = make(prepMinutes=30, ingredients=["salt"], steps=["Cook"])
        new = plans.update(data, plan["id"], {"startTime": "17:15"}, MON, KNOWN)
        self.assertEqual((new["title"], new["prepMinutes"], new["startTime"]), ("Spicy chicken", 30, "17:15"))
        self.assertEqual(new["ingredients"], plan["ingredients"])

    def test_failed_update_changes_nothing(self):
        data, plan = make(steps=["Cook"])
        snapshot = [dict(p) for p in data["plans"]]
        with self.assertRaises(ValueError):
            plans.update(data, plan["id"], {"title": "New name", "prepMinutes": 0}, MON, KNOWN)
        self.assertEqual(data["plans"], snapshot)
        self.assertEqual(data["plans"][0]["title"], "Spicy chicken")

    def test_unchanged_retired_url_is_accepted_but_a_new_unknown_one_is_not(self):
        data, plan = make(url="https://example.com/r")
        plans.update(data, plan["id"], {"title": "Renamed", "url": "https://example.com/r"}, MON, set())
        plans.update(data, plan["id"], {"title": "Renamed again"}, MON, set())
        with self.assertRaises(ValueError):
            plans.update(data, plan["id"], {"url": "https://other.example.com"}, MON, set())

    def test_unknown_plan_raises_keyerror(self):
        with self.assertRaises(KeyError):
            plans.update({}, "nope", {"title": "x"}, MON, KNOWN)


class ActionTests(unittest.TestCase):
    def test_check_toggles_each_kind(self):
        data, plan = make(ingredients=["salt"], steps=["Cook"])
        plans.check(data, plan["id"], "ingredients", plan["ingredients"][0]["id"])
        self.assertTrue(data["plans"][0]["ingredients"][0]["done"])
        self.assertFalse(data["plans"][0]["steps"][0]["done"])
        plans.check(data, plan["id"], "ingredients", plan["ingredients"][0]["id"])
        self.assertFalse(data["plans"][0]["ingredients"][0]["done"])

    def test_check_errors(self):
        data, plan = make(steps=["Cook"])
        with self.assertRaises(ValueError):
            plans.check(data, plan["id"], "pans", "x")
        with self.assertRaises(KeyError):
            plans.check(data, plan["id"], "steps", "nope")
        with self.assertRaises(KeyError):
            plans.check(data, "nope", "steps", "x")

    def test_find_returns_the_usable_plan_or_raises(self):
        data, plan = make(steps=["Cook"])
        self.assertEqual(plans.find(data, plan["id"])["title"], "Spicy chicken")
        with self.assertRaises(KeyError):
            plans.find(data, "nope")

    def test_delete_returns_a_copy_and_restore_puts_it_back_once(self):
        data, plan = make(steps=["Cook"])
        saved = plans.delete(data, plan["id"])
        self.assertEqual(data["plans"], [])
        saved["title"] = "changed after delete"
        plans.restore(data, {"plans": [plan]})
        plans.restore(data, {"plans": [plan]})
        self.assertEqual([p["title"] for p in data["plans"]], ["Spicy chicken"])
        with self.assertRaises(KeyError):
            plans.delete(data, "nope")

    def test_copy_plan_is_for_today_with_checks_cleared(self):
        data, plan = make(date="2026-10-01", prepMinutes=30, startTime="17:00", url="https://example.com/r",
                          ingredients=["salt"], steps=["Cook"])
        plans.check(data, plan["id"], "steps", plan["steps"][0]["id"])
        copy = plans.copy_plan(data, plan["id"], TUE)
        self.assertEqual((copy["title"], copy["date"], copy["prepMinutes"], copy["startTime"], copy["url"]),
                         ("Spicy chicken", "2026-10-06", 30, "17:00", "https://example.com/r"))
        self.assertEqual(texts(copy["steps"]), ["Cook"])
        self.assertFalse(copy["steps"][0]["done"])
        self.assertNotEqual(copy["id"], plan["id"])
        self.assertNotEqual(copy["steps"][0]["id"], plan["steps"][0]["id"])
        self.assertTrue(data["plans"][0]["steps"][0]["done"])
        self.assertEqual(len(data["plans"]), 2)


class HandEditedTests(unittest.TestCase):
    def test_bad_start_time_types_are_skipped_not_fatal(self):
        for bad in (5, ["a"], "25:99", "5pm"):
            data, _ = make(title="Good", startTime="17:00")
            make(data, title="Bad")
            data["plans"][1]["startTime"] = bad
            titles = [p["title"] for p in plans.view(data, MON)["items"]]
            self.assertEqual(titles, ["Good"], bad)

    def test_bad_prep_minutes_plan_is_skipped(self):
        for bad in ("30", True, 1.5):
            data, _ = make(title="Good")
            make(data, title="Bad")
            data["plans"][1]["prepMinutes"] = bad
            titles = [p["title"] for p in plans.view(data, MON)["items"]]
            self.assertEqual(titles, ["Good"], bad)

    def test_check_toggles_an_item_with_no_done_key(self):
        data, plan = make(steps=["Cook"])
        del data["plans"][0]["steps"][0]["done"]
        plans.check(data, plan["id"], "steps", plan["steps"][0]["id"])
        self.assertTrue(data["plans"][0]["steps"][0]["done"])


class FromRecipeTests(unittest.TestCase):
    RECIPE = {"id": "r1", "name": "Keto Lamb Chops", "url": "https://example.com/r", "minutes": 15}

    def test_prefills_from_the_recipe(self):
        data = {}
        plan = plans.from_recipe(data, self.RECIPE, MON)
        self.assertEqual((plan["title"], plan["url"], plan["prepMinutes"], plan["date"], plan["startTime"]),
                         ("Keto Lamb Chops", "https://example.com/r", 15, "2026-10-05", ""))
        self.assertEqual((plan["ingredients"], plan["steps"]), ([], []))
        self.assertEqual(data["plans"], [plan])

    def test_same_recipe_same_day_reuses_the_plan(self):
        data = {}
        first = plans.from_recipe(data, self.RECIPE, MON)
        again = plans.from_recipe(data, self.RECIPE, MON)
        self.assertIs(first, again)
        self.assertEqual(len(data["plans"]), 1)
        plans.from_recipe(data, self.RECIPE, TUE)
        self.assertEqual(len(data["plans"]), 2)

    def test_bad_minutes_become_unset(self):
        for minutes in (0, 9999, "x", None):
            plan = plans.from_recipe({}, dict(self.RECIPE, minutes=minutes), MON)
            self.assertIsNone(plan["prepMinutes"], minutes)


class PruneAndViewTests(unittest.TestCase):
    def test_prune_keeps_sixty_days_and_malformed_plans(self):
        data, _ = make(date=(MON - timedelta(days=60)).isoformat())
        make(data, title="Too old", date=(MON - timedelta(days=60)).isoformat())
        data["plans"][1]["date"] = (MON - timedelta(days=61)).isoformat()
        data["plans"].append({"id": "bad"})
        plans.prune(data, MON)
        self.assertEqual([p.get("title") for p in data["plans"]], ["Spicy chicken", None])

    def test_view_orders_today_then_future_then_past(self):
        data = {}
        for title, day, start in (
            ("Older", "2026-09-20", ""), ("Yesterday", "2026-10-04", ""), ("Later", "2026-10-08", ""),
            ("Tomorrow", "2026-10-06", ""), ("Tonight late", "2026-10-05", "18:00"),
            ("Tonight no time", "2026-10-05", ""), ("Tonight early", "2026-10-05", "17:00"),
        ):
            make(data, title=title, date=day, startTime=start)
        titles = [p["title"] for p in plans.view(data, MON)["items"]]
        self.assertEqual(titles, ["Tonight early", "Tonight late", "Tonight no time", "Tomorrow", "Later", "Yesterday", "Older"])

    def test_nudge_is_earliest_unfinished_plan_with_a_start_time(self):
        data = {}
        _, early = make(data, title="Early", startTime="17:00", steps=["Cook"])
        make(data, title="Late", startTime="18:00", steps=["Cook"])
        make(data, title="No time", steps=["Cook"])
        make(data, title="Tomorrow", date="2026-10-06", startTime="09:00", steps=["Cook"])
        self.assertEqual(plans.view(data, MON)["nudge"], {"id": early["id"], "title": "Early", "startTime": "17:00"})
        plans.check(data, early["id"], "steps", early["steps"][0]["id"])
        self.assertEqual(plans.view(data, MON)["nudge"]["title"], "Late")

    def test_nudge_with_no_steps_and_with_nothing(self):
        data = {}
        self.assertIsNone(plans.view(data, MON)["nudge"])
        make(data, title="No steps", startTime="17:00")
        self.assertEqual(plans.view(data, MON)["nudge"]["title"], "No steps")
        data["plans"][0]["startTime"] = ""
        self.assertIsNone(plans.view(data, MON)["nudge"])

    def test_view_skips_malformed_plans_and_old_data_is_empty(self):
        data = {"plans": [{"id": "x"}, {"id": "y", "title": "T", "date": "nope"}, "junk"]}
        self.assertEqual(plans.view(data, MON), {"items": [], "nudge": None})
        self.assertEqual(plans.view({}, MON), {"items": [], "nudge": None})


if __name__ == "__main__":
    unittest.main()
