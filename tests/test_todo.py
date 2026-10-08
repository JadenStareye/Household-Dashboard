import unittest
from datetime import date

from dashboard import todo

RULES = [
    {"id": "vit", "title": "Take vitamins", "repeat": "daily"},
    {"id": "kit", "title": "Clean kitchen", "repeat": "weekly", "days": ["mon"]},
    {"id": "wk", "title": "Weekday item", "repeat": "weekdays"},
]
MON, TUE, WED = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
SAT = date(2026, 10, 10)


def titles(tasks):
    return [t["title"] for t in tasks]


class RecurringTests(unittest.TestCase):
    def test_monday_generates_all_three(self):
        data = {}
        todo.generate_recurring(data, RULES, MON)
        self.assertEqual(titles(data["tasks"]), ["Take vitamins", "Clean kitchen", "Weekday item"])

    def test_saturday_only_daily(self):
        data = {}
        todo.generate_recurring(data, RULES, SAT)
        self.assertEqual(titles(data["tasks"]), ["Take vitamins"])

    def test_generate_twice_no_duplicates(self):
        data = {}
        todo.generate_recurring(data, RULES, MON)
        todo.generate_recurring(data, RULES, MON)
        self.assertEqual(len(data["tasks"]), 3)

    def test_unknown_repeat_raises(self):
        with self.assertRaises(ValueError):
            todo.generate_recurring({}, [{"id": "x", "title": "x", "repeat": "yearly"}], MON)

    def test_moved_recurring_not_regenerated_or_duplicated(self):
        data = {}
        todo.generate_recurring(data, RULES, MON)
        vit = next(t for t in data["tasks"] if t["ruleId"] == "vit")
        todo.move_to_tomorrow(data, vit["id"], MON)
        todo.generate_recurring(data, RULES, MON)
        self.assertEqual([t for t in data["tasks"] if t["ruleId"] == "vit"][0]["date"], TUE.isoformat())
        self.assertEqual(len([t for t in data["tasks"] if t["ruleId"] == "vit"]), 1)
        todo.generate_recurring(data, RULES, TUE)
        self.assertEqual(len([t for t in data["tasks"] if t["ruleId"] == "vit"]), 1)
        self.assertIn("Weekday item", titles(todo.view(data, TUE)["today"]))


class ActionTests(unittest.TestCase):
    def test_add_task_strips_and_rejects_empty(self):
        data = {}
        task = todo.add_task(data, "  Call dentist  ", MON)
        self.assertEqual(task["title"], "Call dentist")
        self.assertEqual(task["source"], "manual")
        with self.assertRaises(ValueError):
            todo.add_task(data, "   ", MON)

    def test_toggle_done(self):
        data = {}
        task = todo.add_task(data, "A", MON)
        todo.toggle_done(data, task["id"])
        self.assertTrue(data["tasks"][0]["done"])
        todo.toggle_done(data, task["id"])
        self.assertFalse(data["tasks"][0]["done"])

    def test_unknown_id_raises_keyerror(self):
        with self.assertRaises(KeyError):
            todo.toggle_done({}, "nope")

    def test_remove_manual_only(self):
        data = {}
        manual = todo.add_task(data, "A", MON)
        todo.generate_recurring(data, RULES, MON)
        recurring = next(t for t in data["tasks"] if t["source"] == "recurring")
        with self.assertRaises(ValueError):
            todo.remove(data, recurring["id"])
        todo.remove(data, manual["id"])
        self.assertNotIn(manual["id"], [t["id"] for t in data["tasks"]])


class ViewTests(unittest.TestCase):
    def test_unfinished_yesterday_is_carryover_not_moved(self):
        data = {}
        a = todo.add_task(data, "Open", MON)
        b = todo.add_task(data, "Finished", MON)
        c = todo.add_task(data, "Dismissed", MON)
        todo.toggle_done(data, b["id"])
        todo.dismiss(data, c["id"])
        view = todo.view(data, TUE)
        self.assertEqual(titles(view["carryover"]), ["Open"])
        self.assertEqual(view["today"], [])
        self.assertEqual(next(t for t in data["tasks"] if t["id"] == a["id"])["date"], MON.isoformat())

    def test_move_from_carryover_lands_tomorrow(self):
        data = {}
        a = todo.add_task(data, "Open", MON)
        todo.move_to_tomorrow(data, a["id"], TUE)
        upcoming = [{"id": a["id"], "title": "Open", "date": WED.isoformat(), "source": "manual"}]
        self.assertEqual(todo.view(data, TUE), {"carryover": [], "today": [], "upcoming": upcoming})
        self.assertEqual(titles(todo.view(data, WED)["today"]), ["Open"])

    def test_done_tasks_sort_to_bottom(self):
        data = {}
        a = todo.add_task(data, "A", MON)
        todo.add_task(data, "B", MON)
        todo.toggle_done(data, a["id"])
        self.assertEqual(titles(todo.view(data, MON)["today"]), ["B", "A"])

    def test_prune_drops_old_finished_tasks_and_keys(self):
        data = {}
        old = todo.add_task(data, "Old", date(2026, 8, 1))
        todo.toggle_done(data, old["id"])
        keep = todo.add_task(data, "Old but open", date(2026, 8, 1))
        data["generated"] = ["vit|2026-08-01", "vit|2026-10-05"]
        todo.prune(data, MON)
        self.assertEqual([t["id"] for t in data["tasks"]], [keep["id"]])
        self.assertEqual(data["generated"], ["vit|2026-10-05"])


def water(data, days):
    rules = [{"id": "wat", "title": "Water plants", "repeat": "daily"}]
    for d in days:
        todo.generate_recurring(data, rules, d)


D1, D2, D3 = date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)


class OrderTests(unittest.TestCase):
    def test_add_task_order_increments(self):
        data = {}
        a = todo.add_task(data, "A", MON)
        b = todo.add_task(data, "B", MON)
        self.assertEqual((a["order"], b["order"]), (1, 2))

    def test_missing_order_tolerated(self):
        data = {}
        a = todo.add_task(data, "A", MON)
        b = todo.add_task(data, "B", MON)
        del a["order"]
        del b["order"]
        self.assertEqual(titles(todo.view(data, MON)["today"]), ["A", "B"])
        c = todo.add_task(data, "C", MON)
        self.assertEqual(c["order"], 1)

    def test_move_to_tomorrow_goes_first(self):
        data = {}
        todo.add_task(data, "A", MON)
        b = todo.add_task(data, "B", MON)
        todo.move_to_tomorrow(data, b["id"], MON)
        self.assertEqual(b["order"], 0)
        todo.add_task(data, "C", TUE)
        self.assertEqual(titles(todo.view(data, TUE)["today"]), ["B", "C"])

    def test_reorder(self):
        data = {}
        a = todo.add_task(data, "A", MON)
        b = todo.add_task(data, "B", MON)
        c = todo.add_task(data, "C", MON)
        done = todo.add_task(data, "D", MON)
        todo.toggle_done(data, done["id"])
        future = todo.add_task(data, "F", MON, date=TUE)
        future_order = future["order"]
        todo.reorder(data, [c["id"], a["id"], done["id"], future["id"], "nope", b["id"]], MON)
        self.assertEqual(titles(todo.view(data, MON)["today"]), ["C", "A", "B", "D"])
        self.assertEqual([c["order"], a["order"], b["order"]], [1, 2, 3])
        self.assertEqual(future["order"], future_order)

    def test_reorder_validates(self):
        for bad in ("abc", [1], None, {"a": 1}):
            with self.assertRaises(ValueError):
                todo.reorder({}, bad, MON)


class DatedTests(unittest.TestCase):
    def test_future_hidden_then_shown(self):
        data = {}
        t = todo.add_task(data, "Later", MON, date=WED)
        view = todo.view(data, MON)
        self.assertEqual(view["today"], [])
        self.assertEqual(view["carryover"], [])
        self.assertEqual(view["upcoming"], [{"id": t["id"], "title": "Later", "date": WED.isoformat(), "source": "manual"}])
        self.assertEqual(titles(todo.view(data, WED)["today"]), ["Later"])
        self.assertEqual(todo.view(data, WED)["upcoming"], [])

    def test_iso_string_date_and_bounds(self):
        data = {}
        todo.add_task(data, "S", MON, date="2026-10-07")
        todo.add_task(data, "Today", MON, date=MON)
        todo.add_task(data, "Max", MON, date=date(2027, 10, 5))
        for bad in (date(2026, 10, 4), date(2027, 10, 6), "garbage", "2026-13-01"):
            with self.assertRaises(ValueError) as cm:
                todo.add_task(data, "X", MON, date=bad)
            self.assertEqual(str(cm.exception), "Pick a date within the next year")

    def test_upcoming_sorted_and_excludes_dismissed(self):
        data = {}
        todo.add_task(data, "B", MON, date=WED)
        todo.add_task(data, "A", MON, date=TUE)
        todo.add_task(data, "C", MON, date=WED)
        d = todo.add_task(data, "D", MON, date=WED)
        todo.dismiss(data, d["id"])
        self.assertEqual(titles(todo.view(data, MON)["upcoming"]), ["A", "B", "C"])

    def test_remove_future_manual(self):
        data = {}
        t = todo.add_task(data, "Later", MON, date=WED)
        todo.remove(data, t["id"])
        self.assertEqual(data["tasks"], [])


class CarryoverGroupTests(unittest.TestCase):
    def test_three_days_collapse(self):
        data = {}
        water(data, [D1, D2, D3])
        manual = todo.add_task(data, "Call", D2)
        carry = todo.view(data, TUE)["carryover"]
        self.assertEqual(titles(carry), ["Call", "Water plants"])
        w = carry[1]
        self.assertEqual(w["count"], 3)
        self.assertEqual(len(w["ids"]), 3)
        self.assertEqual(w["date"], D3.isoformat())
        self.assertEqual(w["id"], w["ids"][-1])
        self.assertEqual(carry[0]["ids"], [manual["id"]])
        self.assertEqual(carry[0]["count"], 1)

    def test_group_done(self):
        data = {}
        water(data, [D1, D2, D3])
        rep = todo.view(data, TUE)["carryover"][0]["id"]
        todo.toggle_done(data, rep, TUE)
        self.assertTrue(all(t["done"] for t in data["tasks"]))
        self.assertEqual(todo.view(data, TUE)["carryover"], [])

    def test_group_dismiss(self):
        data = {}
        water(data, [D1, D2, D3])
        todo.dismiss(data, data["tasks"][0]["id"], TUE)
        self.assertTrue(all(t["dismissed"] for t in data["tasks"]))

    def test_group_move_leaves_one_task_tomorrow(self):
        data = {}
        water(data, [D1, D2, D3])
        rep = todo.view(data, TUE)["carryover"][0]["id"]
        todo.move_to_tomorrow(data, rep, TUE)
        live = [t for t in data["tasks"] if not t["dismissed"]]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["id"], rep)
        self.assertEqual(live[0]["date"], WED.isoformat())
        self.assertEqual(todo.view(data, TUE)["carryover"], [])

    def test_without_today_acts_on_single_task(self):
        data = {}
        water(data, [D1, D2])
        todo.dismiss(data, data["tasks"][0]["id"])
        self.assertEqual([t["dismissed"] for t in data["tasks"]], [True, False])

    def test_non_carryover_unaffected(self):
        data = {}
        water(data, [D2, D3])
        todo.toggle_done(data, data["tasks"][1]["id"], D3)
        self.assertEqual([t["done"] for t in data["tasks"]], [False, True])

    def test_dismiss_carryover(self):
        data = {}
        water(data, [D1, D2, D3])
        todo.add_task(data, "Call", D2)
        today_task = todo.add_task(data, "Now", TUE)
        todo.dismiss_carryover(data, TUE)
        self.assertEqual(todo.view(data, TUE)["carryover"], [])
        self.assertFalse(today_task["dismissed"])


class EditTests(unittest.TestCase):
    def test_edit_title(self):
        data = {}
        t = todo.add_task(data, "A", MON)
        todo.edit_title(data, t["id"], "  New  ")
        self.assertEqual(t["title"], "New")
        todo.edit_title(data, t["id"], "x" * 300)
        self.assertEqual(len(t["title"]), 200)
        with self.assertRaises(ValueError):
            todo.edit_title(data, t["id"], "  ")
        with self.assertRaises(KeyError):
            todo.edit_title(data, "nope", "x")


class UndoTests(unittest.TestCase):
    def roundtrip(self, data, ids, action):
        import json
        before = json.loads(json.dumps(data["tasks"]))
        rec = todo.snapshot_for_undo(data, "label", ids)
        self.assertEqual(rec["label"], "label")
        json.dumps(rec)
        action()
        self.assertNotEqual(data["tasks"], before)
        todo.restore(data, rec)
        self.assertEqual(sorted(data["tasks"], key=lambda t: t["id"]), sorted(before, key=lambda t: t["id"]))

    def test_dismiss(self):
        data = {}
        t = todo.add_task(data, "A", MON)
        self.roundtrip(data, [t["id"]], lambda: todo.dismiss(data, t["id"]))

    def test_move_group(self):
        data = {}
        water(data, [D1, D2, D3])
        ids = [t["id"] for t in data["tasks"]]
        self.roundtrip(data, ids, lambda: todo.move_to_tomorrow(data, ids[-1], TUE))

    def test_remove(self):
        data = {}
        t = todo.add_task(data, "A", MON)
        self.roundtrip(data, [t["id"]], lambda: todo.remove(data, t["id"]))
        self.assertEqual(len(data["tasks"]), 1)

    def test_dismiss_carryover(self):
        data = {}
        water(data, [D1, D2, D3])
        todo.add_task(data, "Call", D2)
        ids = [t["id"] for t in data["tasks"]]
        self.roundtrip(data, ids, lambda: todo.dismiss_carryover(data, TUE))

    def test_unknown_ids_skipped(self):
        rec = todo.snapshot_for_undo({"tasks": []}, "x", ["nope"])
        self.assertEqual(rec["tasks"], [])


if __name__ == "__main__":
    unittest.main()
