import json
import random
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dashboard.api import App
from dashboard.store import Store

RULES = [
    {"id": "vit", "title": "Take vitamins", "repeat": "daily"},
    {"id": "kit", "title": "Clean kitchen", "repeat": "weekly", "days": ["mon"]},
]


def recipes(prefix, n):
    return [{"id": f"{prefix}{i}", "name": f"{prefix} {i}", "description": "d", "url": "https://example.com", "minutes": 20} for i in range(n)]


RECIPES = {"chris": recipes("c", 9), "v": recipes("v", 9)}


class FakeWeather:
    def get(self):
        return {"available": False}


class FakeAlerts:
    def __init__(self, alerts=(), fresh=True):
        self.alerts = list(alerts)
        self.fresh = fresh

    def get(self):
        return list(self.alerts)


def alert(alert_id, event="Tornado Warning"):
    return {"id": alert_id, "event": event, "level": "warning", "ends": None, "headline": event, "area": "Test County"}


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.clock = [date(2026, 10, 5)]  # Monday
        self.mono = [1000.0]
        self.opened = []
        self.open_result = True
        self.app = self.build()

    def fake_open(self, url):
        self.opened.append(url)
        return self.open_result

    def build(self, rules=None, alerts=None):
        store = Store(self.dir / "data.json", self.dir / "backups")
        return App(store, RULES if rules is None else rules, RECIPES, FakeWeather(),
                   clock=lambda: self.clock[0], rng=random.Random(3), now=lambda: self.mono[0],
                   opener=self.fake_open, alerts=alerts)

    def call(self, method, path, body=None):
        return self.app.handle(method, path, body)

    def test_open_recipe_link_in_default_browser(self):
        status, body = self.call("POST", "/api/open", {"url": "https://example.com"})
        self.assertEqual((status, body), (200, {"ok": True}))
        self.assertEqual(self.opened, ["https://example.com"])

    def test_open_refuses_urls_that_are_not_recipes(self):
        for url in ("https://evil.example.org/x", "file:///C:/Windows/notepad.exe", "", None, 5, ["https://example.com"]):
            status, _ = self.call("POST", "/api/open", {"url": url})
            self.assertEqual(status, 400, url)
        self.assertEqual(self.call("POST", "/api/open", {})[0], 400)
        self.assertEqual(self.opened, [])

    def test_open_reports_failure_when_no_browser_opens(self):
        self.open_result = False
        status, body = self.call("POST", "/api/open", {"url": "https://example.com"})
        self.assertEqual(status, 500)
        self.assertIn("error", body)

    def test_open_only_allows_post(self):
        self.assertEqual(self.call("GET", "/api/open")[0], 404)

    def test_state_shape(self):
        status, state = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["date"], "2026-10-05")
        self.assertEqual(state["dateLabel"], "Monday, October 5")
        self.assertEqual([t["title"] for t in state["tasks"]["today"]], ["Take vitamins", "Clean kitchen"])
        self.assertEqual(len(state["dinners"]["chris"]["picks"]), 3)
        self.assertEqual(len(state["dinners"]["v"]["picks"]), 3)

    def test_add_toggle_move_dismiss_delete(self):
        _, state = self.call("POST", "/api/tasks", {"title": "Call dentist"})
        task = next(t for t in state["tasks"]["today"] if t["title"] == "Call dentist")
        _, state = self.call("POST", f"/api/tasks/{task['id']}/done")
        self.assertTrue(next(t for t in state["tasks"]["today"] if t["id"] == task["id"])["done"])
        _, state = self.call("POST", f"/api/tasks/{task['id']}/move")
        self.assertNotIn(task["id"], [t["id"] for t in state["tasks"]["today"]])
        status, _ = self.call("DELETE", f"/api/tasks/{task['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(self.call("DELETE", f"/api/tasks/{task['id']}")[0], 404)

    def test_bad_input_and_unknown_routes(self):
        self.assertEqual(self.call("POST", "/api/tasks", {"title": "  "})[0], 400)
        self.assertEqual(self.call("POST", "/api/tasks/zzzz/done")[0], 404)
        self.assertEqual(self.call("GET", "/api/nope")[0], 404)

    def test_non_object_body_is_400(self):
        for bad in ([1], "x", 5, []):
            self.assertEqual(self.call("POST", "/api/tasks", bad)[0], 400)

    def test_dinner_actions(self):
        _, state = self.call("GET", "/api/state")
        first = state["dinners"]["chris"]["picks"][0]["id"]
        _, state = self.call("POST", "/api/dinners/chris/swap", {"recipeId": first})
        self.assertNotIn(first, [r["id"] for r in state["dinners"]["chris"]["picks"]])
        pick = state["dinners"]["chris"]["picks"][0]["id"]
        _, state = self.call("POST", "/api/dinners/chris/favorite", {"recipeId": pick})
        self.assertEqual([r["id"] for r in state["dinners"]["chris"]["favorites"]], [pick])
        vpick = state["dinners"]["v"]["picks"][0]["id"]
        _, state = self.call("POST", "/api/dinners/v/hide", {"recipeId": vpick})
        self.assertEqual([r["id"] for r in state["dinners"]["v"]["hidden"]], [vpick])
        _, state = self.call("POST", "/api/dinners/v/restore", {"recipeId": vpick})
        self.assertEqual(state["dinners"]["v"]["hidden"], [])
        self.assertEqual(self.call("POST", "/api/dinners/chris/hide", {"recipeId": pick})[0], 404)
        self.assertEqual(self.call("POST", "/api/dinners/chris/swap", {"recipeId": "nope"})[0], 404)

    def test_rollover_next_day(self):
        _, day1 = self.call("GET", "/api/state")
        open_ids = [t["id"] for t in day1["tasks"]["today"]]
        picks1 = [r["id"] for r in day1["dinners"]["chris"]["picks"]]
        self.clock[0] = date(2026, 10, 6)
        _, day2 = self.call("GET", "/api/state")
        self.assertEqual(sorted(t["id"] for t in day2["tasks"]["carryover"]), sorted(open_ids))
        self.assertEqual([t["title"] for t in day2["tasks"]["today"]], ["Take vitamins"])
        self.assertTrue(set(picks1).isdisjoint(r["id"] for r in day2["dinners"]["chris"]["picks"]))

    def test_restart_keeps_state(self):
        _, before = self.call("GET", "/api/state")
        self.app = self.build()
        _, after = self.call("GET", "/api/state")
        self.assertEqual(before["tasks"], after["tasks"])
        self.assertEqual(before["dinners"]["chris"]["picks"], after["dinners"]["chris"]["picks"])

    # ---- settings

    def test_settings_defaults_and_update(self):
        _, state = self.call("GET", "/api/state")
        self.assertEqual(state["settings"], {"theme": "auto", "accent": "blue", "textSize": "normal"})
        status, state = self.call("PUT", "/api/settings", {"theme": "dark", "accent": "rose"})
        self.assertEqual(status, 200)
        self.assertEqual(state["settings"], {"theme": "dark", "accent": "rose", "textSize": "normal"})
        self.app = self.build()
        _, state = self.call("GET", "/api/state")
        self.assertEqual(state["settings"]["theme"], "dark")

    def test_settings_validation(self):
        for body in ({"theme": "neon"}, {"accent": "teal"}, {"textSize": "huge"}, {"theme": ["dark"]}):
            status, payload = self.call("PUT", "/api/settings", body)
            self.assertEqual((status, payload["error"]), (400, "Pick one of the choices offered"))
        status, _ = self.call("PUT", "/api/settings", {"theme": "light", "accent": "teal"})
        self.assertEqual(status, 400)
        _, state = self.call("GET", "/api/state")
        self.assertEqual(state["settings"]["theme"], "auto")
        self.assertEqual(self.call("PUT", "/api/settings", [1])[0], 400)

    # ---- rules

    def test_rules_seeded_once(self):
        _, state = self.call("GET", "/api/state")
        self.assertEqual([r["id"] for r in state["rules"]], ["vit", "kit"])
        self.assertFalse(state["rules"][0]["paused"])
        self.assertEqual(self.call("DELETE", "/api/rules/kit")[0], 200)
        self.app = self.build()
        _, state = self.call("GET", "/api/state")
        self.assertEqual([r["id"] for r in state["rules"]], ["vit"])

    def test_new_rule_task_appears_in_same_response(self):
        _, state = self.call("POST", "/api/rules", {"title": "Stretch", "repeat": "daily"})
        self.assertIn("Stretch", [t["title"] for t in state["tasks"]["today"]])

    def test_rule_create_update_delete(self):
        status, state = self.call("POST", "/api/rules", {"title": "Water plants", "repeat": "weekly", "days": ["tue"]})
        self.assertEqual(status, 200)
        rule = state["rules"][-1]
        self.assertEqual(rule["title"], "Water plants")
        status, state = self.call("PUT", f"/api/rules/{rule['id']}", {"title": "Water ferns", "repeat": "daily"})
        self.assertEqual(status, 200)
        self.assertEqual(next(r for r in state["rules"] if r["id"] == rule["id"])["title"], "Water ferns")
        status, state = self.call("DELETE", f"/api/rules/{rule['id']}")
        self.assertEqual(status, 200)
        self.assertNotIn(rule["id"], [r["id"] for r in state["rules"]])

    def test_rule_errors(self):
        self.assertEqual(self.call("POST", "/api/rules", {"title": "", "repeat": "daily"})[0], 400)
        self.assertEqual(self.call("POST", "/api/rules", {"title": "x", "repeat": "weekly"})[0], 400)
        self.assertEqual(self.call("PUT", "/api/rules/nope", {"title": "x", "repeat": "daily"})[0], 404)
        self.assertEqual(self.call("DELETE", "/api/rules/nope")[0], 404)
        self.assertEqual(self.call("POST", "/api/rules", [1])[0], 400)

    def test_rule_hyphenated_ids_route(self):
        self.app = self.build([{"id": "clean-mon-1", "title": "Clean", "repeat": "daily"}])
        self.assertEqual(self.call("DELETE", "/api/rules/clean-mon-1")[0], 200)

    def test_editing_rule_does_not_duplicate_todays_task(self):
        self.call("GET", "/api/state")
        _, state = self.call("PUT", "/api/rules/vit", {"title": "Take vitamins now", "repeat": "daily"})
        titles = [t["title"] for t in state["tasks"]["today"]]
        self.assertEqual(titles, ["Take vitamins", "Clean kitchen"])

    def test_malformed_rule_is_skipped(self):
        bad = [
            {"id": "m", "title": "Monthly", "repeat": "monthly"},
            {"id": "b", "title": "Biweekly", "repeat": "biweekly", "days": ["mon"]},
            {"id": "x", "title": "Weird", "repeat": "yearly"},
            {"id": "n", "title": "Num", "repeat": "monthly", "dayOfMonth": "five"},
            {"title": "No id", "repeat": "daily"},
            {"id": "t", "repeat": "daily"},
            "garbage",
            {"id": "ok", "title": "Fine", "repeat": "daily"},
        ]
        (self.dir / "data.json").write_text(
            json.dumps({"tasks": [], "generated": [], "rulesSeeded": True, "rules": bad}), encoding="utf-8"
        )
        self.app = self.build()
        status, state = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual([t["title"] for t in state["tasks"]["today"]], ["Fine"])

    def test_old_data_file_loads(self):
        (self.dir / "data.json").write_text(
            '{"tasks": [{"id": "aaaa1111", "title": "Old", "date": "2026-10-05", "done": false,'
            ' "dismissed": false, "source": "manual", "ruleId": null}], "generated": []}',
            encoding="utf-8",
        )
        self.app = self.build()
        status, state = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertIn("Old", [t["title"] for t in state["tasks"]["today"]])
        self.assertEqual(state["settings"]["accent"], "blue")
        self.assertEqual(len(state["rules"]), 2)

    # ---- tasks

    def test_add_for_date_and_upcoming(self):
        status, state = self.call("POST", "/api/tasks", {"title": "Dentist", "date": "2026-10-09"})
        self.assertEqual(status, 200)
        self.assertNotIn("Dentist", [t["title"] for t in state["tasks"]["today"]])
        self.assertEqual([(u["title"], u["date"]) for u in state["tasks"]["upcoming"]], [("Dentist", "2026-10-09")])
        self.assertEqual(self.call("POST", "/api/tasks", {"title": "Past", "date": "2026-10-01"})[0], 400)
        self.assertEqual(self.call("POST", "/api/tasks", {"title": "Bad", "date": "nope"})[0], 400)
        uid = state["tasks"]["upcoming"][0]["id"]
        self.assertEqual(self.call("DELETE", f"/api/tasks/{uid}")[0], 200)

    def test_moved_recurring_task_in_upcoming_is_dismissed_not_deleted(self):
        _, state = self.call("GET", "/api/state")
        vit = next(t for t in state["tasks"]["today"] if t["title"] == "Take vitamins")
        _, state = self.call("POST", f"/api/tasks/{vit['id']}/move")
        moved = [u for u in state["tasks"]["upcoming"] if u["title"] == "Take vitamins"]
        self.assertEqual([u["source"] for u in moved], ["recurring"])
        self.assertEqual(self.call("DELETE", f"/api/tasks/{moved[0]['id']}")[0], 400)
        status, state = self.call("POST", f"/api/tasks/{moved[0]['id']}/dismiss")
        self.assertEqual(status, 200)
        self.assertNotIn("Take vitamins", [u["title"] for u in state["tasks"]["upcoming"]])
        self.assertIsNotNone(state["undo"])
        _, state = self.call("POST", "/api/tasks", {"title": "Dentist", "date": "2026-10-09"})
        self.assertEqual([u["source"] for u in state["tasks"]["upcoming"] if u["title"] == "Dentist"], ["manual"])

    def test_undo_with_stale_id_is_refused(self):
        _, state = self.call("GET", "/api/state")
        task = state["tasks"]["today"][0]
        _, state = self.call("POST", f"/api/tasks/{task['id']}/dismiss")
        undo_id = state["undo"]["id"]
        self.assertEqual(self.call("POST", "/api/undo", {"id": undo_id + 5}), (400, {"error": "Nothing to undo"}))
        self.assertEqual(self.call("POST", "/api/undo", {"id": undo_id})[0], 200)
        _, state = self.call("POST", f"/api/tasks/{task['id']}/dismiss")
        self.assertEqual(self.call("POST", "/api/undo")[0], 200)

    def test_edit_title(self):
        _, state = self.call("POST", "/api/tasks", {"title": "Old name"})
        task = next(t for t in state["tasks"]["today"] if t["title"] == "Old name")
        status, state = self.call("PATCH", f"/api/tasks/{task['id']}", {"title": "  New name "})
        self.assertEqual(status, 200)
        self.assertIn("New name", [t["title"] for t in state["tasks"]["today"]])
        self.assertEqual(self.call("PATCH", f"/api/tasks/{task['id']}", {"title": " "})[0], 400)
        self.assertEqual(self.call("PATCH", f"/api/tasks/{task['id']}", {"title": 5})[0], 400)
        self.assertEqual(self.call("PATCH", "/api/tasks/zzzz", {"title": "x"})[0], 404)

    def test_reorder(self):
        _, state = self.call("POST", "/api/tasks", {"title": "Third"})
        ids = [t["id"] for t in state["tasks"]["today"]]
        status, state = self.call("POST", "/api/tasks/reorder", {"ids": list(reversed(ids))})
        self.assertEqual(status, 200)
        self.assertEqual([t["id"] for t in state["tasks"]["today"]], list(reversed(ids)))
        self.assertEqual(self.call("POST", "/api/tasks/reorder", {"ids": "x"})[0], 400)
        self.assertEqual(self.call("POST", "/api/tasks/reorder", {})[0], 400)

    def three_day_carryover(self):
        self.app = self.build([{"id": "r", "title": "Daily chore", "repeat": "daily"}])
        for day in (5, 6, 7):
            self.clock[0] = date(2026, 10, day)
            self.call("GET", "/api/state")
        self.clock[0] = date(2026, 10, 8)
        _, state = self.call("GET", "/api/state")
        self.assertEqual(len(state["tasks"]["carryover"]), 1)
        self.assertEqual(state["tasks"]["carryover"][0]["count"], 3)
        return state["tasks"]["carryover"][0]

    def test_group_done_dismiss_move_affect_all_members(self):
        for action in ("done", "dismiss", "move"):
            with self.subTest(action=action):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                self.dir = Path(tmp.name)
                self.clock[0] = date(2026, 10, 5)
                entry = self.three_day_carryover()
                status, state = self.call("POST", f"/api/tasks/{entry['id']}/{action}")
                self.assertEqual(status, 200)
                self.assertEqual(state["tasks"]["carryover"], [])
                if action == "move":
                    self.assertEqual([t["id"] for t in state["tasks"]["today"]].count(entry["id"]), 0)

    def test_dismiss_carryover_and_undo(self):
        entry = self.three_day_carryover()
        status, state = self.call("POST", "/api/tasks/dismiss-carryover")
        self.assertEqual(status, 200)
        self.assertEqual(state["tasks"]["carryover"], [])
        self.assertEqual(state["undo"]["label"], "Cleared 1 task")
        status, state = self.call("POST", "/api/undo")
        self.assertEqual(status, 200)
        self.assertEqual(state["tasks"]["carryover"][0]["count"], 3)
        self.assertEqual(sorted(state["tasks"]["carryover"][0]["ids"]), sorted(entry["ids"]))
        self.assertIsNone(state["undo"])

    def test_dismiss_carryover_label_counts_groups_but_undo_restores_all(self):
        self.app = self.build([{"id": "r", "title": "Daily chore", "repeat": "daily"}])
        for day in (5, 6, 7):
            self.clock[0] = date(2026, 10, day)
            self.call("GET", "/api/state")
        self.call("POST", "/api/tasks", {"title": "Manual one"})
        self.clock[0] = date(2026, 10, 8)
        _, state = self.call("GET", "/api/state")
        self.assertEqual(len(state["tasks"]["carryover"]), 2)
        _, state = self.call("POST", "/api/tasks/dismiss-carryover")
        self.assertEqual(state["undo"]["label"], "Cleared 2 tasks")
        _, state = self.call("POST", "/api/undo")
        self.assertEqual(sum(e["count"] for e in state["tasks"]["carryover"]), 4)

    def test_undo_group_dismiss_restores_all_members(self):
        entry = self.three_day_carryover()
        _, state = self.call("POST", f"/api/tasks/{entry['id']}/dismiss")
        self.assertEqual(state["undo"]["label"], "Task dismissed")
        _, state = self.call("POST", "/api/undo")
        self.assertEqual(state["tasks"]["carryover"][0]["count"], 3)

    def test_undo_each_action(self):
        _, state = self.call("POST", "/api/tasks", {"title": "Thing"})
        tid = next(t["id"] for t in state["tasks"]["today"] if t["title"] == "Thing")
        cases = (
            ("POST", f"/api/tasks/{tid}/dismiss", "Task dismissed"),
            ("POST", f"/api/tasks/{tid}/move", "Task moved to tomorrow"),
            ("DELETE", f"/api/tasks/{tid}", "Task removed"),
        )
        for method, path, label in cases:
            _, state = self.call(method, path)
            self.assertEqual(state["undo"]["label"], label)
            _, state = self.call("POST", "/api/undo")
            self.assertIn(tid, [t["id"] for t in state["tasks"]["today"]])

    def test_undo_id_increments_and_replaces(self):
        _, state = self.call("POST", "/api/tasks", {"title": "A"})
        a = next(t["id"] for t in state["tasks"]["today"] if t["title"] == "A")
        _, state = self.call("POST", "/api/tasks", {"title": "B"})
        b = next(t["id"] for t in state["tasks"]["today"] if t["title"] == "B")
        self.assertIsNone(state["undo"])
        _, s1 = self.call("POST", f"/api/tasks/{a}/dismiss")
        _, s2 = self.call("POST", f"/api/tasks/{b}/dismiss")
        self.assertGreater(s2["undo"]["id"], s1["undo"]["id"])
        _, state = self.call("POST", "/api/undo")
        ids = [t["id"] for t in state["tasks"]["today"]]
        self.assertIn(b, ids)
        self.assertNotIn(a, ids)

    def test_failed_action_does_not_record_undo(self):
        self.assertEqual(self.call("DELETE", "/api/tasks/nope")[0], 404)
        self.assertEqual(self.call("POST", "/api/undo")[0], 400)
        _, state = self.call("GET", "/api/state")
        recurring = state["tasks"]["today"][0]["id"]
        self.assertEqual(self.call("DELETE", f"/api/tasks/{recurring}")[0], 400)
        self.assertIsNone(self.call("GET", "/api/state")[1]["undo"])

    def test_undo_expires(self):
        _, state = self.call("POST", "/api/tasks", {"title": "A"})
        tid = next(t["id"] for t in state["tasks"]["today"] if t["title"] == "A")
        self.call("POST", f"/api/tasks/{tid}/dismiss")
        self.mono[0] += 30
        self.assertIsNotNone(self.call("GET", "/api/state")[1]["undo"])
        self.mono[0] += 0.5
        self.assertIsNone(self.call("GET", "/api/state")[1]["undo"])
        status, payload = self.call("POST", "/api/undo")
        self.assertEqual((status, payload["error"]), (400, "Nothing to undo"))

    def test_undo_with_nothing_is_400(self):
        status, payload = self.call("POST", "/api/undo")
        self.assertEqual((status, payload["error"]), (400, "Nothing to undo"))

    # ---- Dinner plans ----
    def new_plan(self, **fields):
        status, state = self.call("POST", "/api/plans", {"title": "Spicy chicken", **fields})
        self.assertEqual(status, 200, state)
        return state

    def test_state_has_plans_and_old_data_is_empty(self):
        _, state = self.call("GET", "/api/state")
        self.assertEqual(state["plans"], {"items": [], "nudge": None})

    def test_create_plan_returns_plan_id_and_shows_in_state(self):
        state = self.new_plan(prepMinutes=40, startTime="17:15", ingredients=["salt"], steps=["Heat pan", "Cook"])
        plan = state["plans"]["items"][0]
        self.assertEqual(state["planId"], plan["id"])
        self.assertEqual((plan["title"], plan["date"], plan["prepMinutes"], plan["startTime"]),
                         ("Spicy chicken", "2026-10-05", 40, "17:15"))
        self.assertEqual([s["text"] for s in plan["steps"]], ["Heat pan", "Cook"])
        self.assertEqual(state["plans"]["nudge"], {"id": plan["id"], "title": "Spicy chicken", "startTime": "17:15"})
        self.assertNotIn("planId", self.call("GET", "/api/state")[1])

    def test_plans_survive_a_restart(self):
        self.new_plan(steps=["Cook"])
        self.app = self.build()
        self.assertEqual(self.call("GET", "/api/state")[1]["plans"]["items"][0]["title"], "Spicy chicken")

    def test_plan_validation_errors_are_plain_400s(self):
        for body, message in (
            ({"title": ""}, "Enter a name for the dinner"),
            ({"title": "A", "prepMinutes": 0}, "Prep time must be a whole number of minutes from 1 to 600"),
            ({"title": "A", "startTime": "7:30"}, "Start time must look like 17:30"),
            ({"title": "A", "date": "nope"}, "Pick a date within the last two months or the next year"),
            ({"title": "A", "url": "https://evil.example.org"}, "That recipe link can't be used"),
        ):
            status, payload = self.call("POST", "/api/plans", body)
            self.assertEqual((status, payload), (400, {"error": message}))
        self.assertEqual(self.call("GET", "/api/state")[1]["plans"]["items"], [])

    def test_plan_endpoints_refuse_non_dict_bodies_and_unknown_ids(self):
        self.assertEqual(self.call("POST", "/api/plans", [1])[0], 400)
        self.assertEqual(self.call("PUT", "/api/plans/nope", {"title": "x"})[0], 404)
        self.assertEqual(self.call("DELETE", "/api/plans/nope")[0], 404)
        self.assertEqual(self.call("POST", "/api/plans/nope/copy")[0], 404)
        plan_id = self.new_plan(steps=["Cook"])["planId"]
        self.assertEqual(self.call("POST", f"/api/plans/{plan_id}/check", {"kind": "steps", "itemId": "nope"})[0], 404)
        self.assertEqual(self.call("POST", f"/api/plans/{plan_id}/check", {"kind": "pans", "itemId": "x"})[0], 400)

    def test_edit_plan_keeps_checks_for_unchanged_lines(self):
        state = self.new_plan(steps=["Heat pan", "Cook"])
        plan = state["plans"]["items"][0]
        _, state = self.call("POST", f"/api/plans/{plan['id']}/check", {"kind": "steps", "itemId": plan["steps"][0]["id"]})
        self.assertTrue(state["plans"]["items"][0]["steps"][0]["done"])
        status, state = self.call("PUT", f"/api/plans/{plan['id']}", {"steps": ["Heat pan", "Cook well"], "startTime": "17:00"})
        steps = state["plans"]["items"][0]["steps"]
        self.assertEqual(status, 200)
        self.assertEqual([(s["text"], s["done"]) for s in steps], [("Heat pan", True), ("Cook well", False)])
        self.assertEqual(state["plans"]["items"][0]["startTime"], "17:00")

    def test_nudge_goes_away_when_every_step_is_checked(self):
        plan = self.new_plan(startTime="17:00", steps=["Cook"])["plans"]["items"][0]
        _, state = self.call("POST", f"/api/plans/{plan['id']}/check", {"kind": "steps", "itemId": plan["steps"][0]["id"]})
        self.assertIsNone(state["plans"]["nudge"])

    def test_copy_plan_makes_a_fresh_one_for_today(self):
        plan = self.new_plan(date="2026-10-07", steps=["Cook"])["plans"]["items"][0]
        self.clock[0] = date(2026, 10, 8)
        status, state = self.call("POST", f"/api/plans/{plan['id']}/copy")
        self.assertEqual(status, 200)
        copy = next(p for p in state["plans"]["items"] if p["id"] == state["planId"])
        self.assertEqual((copy["date"], [s["done"] for s in copy["steps"]]), ("2026-10-08", [False]))
        self.assertEqual(len(state["plans"]["items"]), 2)

    def test_plan_from_a_dinner_card_prefills_and_reuses(self):
        status, state = self.call("POST", "/api/dinners/chris/plan", {"recipeId": "c0"})
        self.assertEqual(status, 200)
        plan = state["plans"]["items"][0]
        self.assertEqual((plan["title"], plan["url"], plan["prepMinutes"]), ("c 0", "https://example.com", 20))
        _, again = self.call("POST", "/api/dinners/v/plan", {"recipeId": "v0"})
        self.assertEqual(len(again["plans"]["items"]), 1)  # same url today: reused, not duplicated
        self.assertEqual(again["planId"], plan["id"])
        self.assertEqual(self.call("POST", "/api/dinners/chris/plan", {"recipeId": "nope"})[0], 404)
        self.assertEqual(self.call("POST", "/api/dinners/chris/plan", {})[0], 404)

    def test_delete_plan_is_undoable(self):
        plan = self.new_plan(steps=["Cook"])["plans"]["items"][0]
        status, state = self.call("DELETE", f"/api/plans/{plan['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(state["plans"]["items"], [])
        self.assertEqual(state["undo"]["label"], "Plan deleted")
        status, state = self.call("POST", "/api/undo", {"id": state["undo"]["id"]})
        self.assertEqual(status, 200)
        self.assertEqual([p["id"] for p in state["plans"]["items"]], [plan["id"]])
        self.assertIsNone(state["undo"])
        self.assertEqual(self.call("POST", "/api/undo")[0], 400)

    def test_task_undo_still_works_beside_plans(self):
        self.new_plan()
        _, state = self.call("POST", "/api/tasks", {"title": "A"})
        task_id = next(t["id"] for t in state["tasks"]["today"] if t["title"] == "A")
        _, state = self.call("POST", f"/api/tasks/{task_id}/dismiss")
        self.assertEqual(state["undo"]["label"], "Task dismissed")
        _, state = self.call("POST", "/api/undo")
        self.assertIn("A", [t["title"] for t in state["tasks"]["today"]])
        self.assertEqual(len(state["plans"]["items"]), 1)

    def test_old_plans_are_pruned(self):
        self.new_plan(date="2026-08-10")  # 56 days before the Monday clock: kept
        self.clock[0] = date(2026, 10, 10)  # now 61 days later: pruned
        self.assertEqual(self.call("GET", "/api/state")[1]["plans"]["items"], [])

    # ---- Shopping list ----
    def shop_add(self, text):
        status, state = self.call("POST", "/api/shopping", {"text": text})
        self.assertEqual(status, 200, state)
        return state

    def test_dates_add_list_remove_and_validation(self):
        status, state = self.call("POST", "/api/dates", {"label": "Mom's birthday", "month": 10, "day": 14})
        self.assertEqual(status, 200)
        self.assertEqual([i["label"] for i in state["dates"]["items"]], ["Mom's birthday"])
        self.assertEqual(self.call("POST", "/api/dates", {"label": "x", "month": 2, "day": 30})[0], 400)
        self.assertEqual(self.call("DELETE", "/api/dates/nope")[0], 404)
        status, state = self.call("DELETE", "/api/dates/" + state["dates"]["items"][0]["id"])
        self.assertEqual((status, state["dates"]["items"]), (200, []))

    def test_state_has_empty_shopping_list(self):
        self.assertEqual(self.call("GET", "/api/state")[1]["shopping"], [])

    def test_shopping_add_validation_and_retick(self):
        state = self.shop_add("Milk")
        self.assertEqual([(i["text"], i["done"]) for i in state["shopping"]], [("Milk", False)])
        self.assertEqual(self.call("POST", "/api/shopping", {"text": "  "}), (400, {"error": "Enter an item"}))
        self.assertEqual(self.call("POST", "/api/shopping", {})[1], {"error": "Enter an item"})
        self.assertEqual(self.call("POST", "/api/shopping", [1])[0], 400)
        item_id = state["shopping"][0]["id"]
        self.call("POST", f"/api/shopping/{item_id}/check")
        _, state = self.call("POST", "/api/shopping", {"text": "milk"})
        self.assertEqual([(i["text"], i["done"]) for i in state["shopping"]], [("Milk", False)])

    def test_shopping_list_full_message(self):
        for n in range(200):
            self.app.data.setdefault("shoppingList", []).append({"id": f"i{n}", "text": f"Item {n}", "done": False})
        status, payload = self.call("POST", "/api/shopping", {"text": "One more"})
        self.assertEqual((status, payload), (400, {"error": "The list is full. Clear some items first."}))

    def test_shopping_check_and_remove(self):
        item_id = self.shop_add("Milk")["shopping"][0]["id"]
        _, state = self.call("POST", f"/api/shopping/{item_id}/check")
        self.assertTrue(state["shopping"][0]["done"])
        _, state = self.call("POST", f"/api/shopping/{item_id}/check")
        self.assertFalse(state["shopping"][0]["done"])
        self.assertEqual(self.call("POST", "/api/shopping/nope/check")[0], 404)
        self.assertEqual(self.call("DELETE", "/api/shopping/nope")[0], 404)
        status, state = self.call("DELETE", f"/api/shopping/{item_id}")
        self.assertEqual((status, state["shopping"], state["undo"]), (200, [], None))

    def test_shopping_clear_is_undoable(self):
        self.shop_add("Milk")
        self.shop_add("Eggs")
        self.shop_add("Bread")
        ids = {i["text"]: i["id"] for i in self.call("GET", "/api/state")[1]["shopping"]}
        self.call("POST", f"/api/shopping/{ids['Milk']}/check")
        status, state = self.call("POST", "/api/shopping/clear")
        self.assertEqual(status, 200)
        self.assertEqual(sorted(i["text"] for i in state["shopping"]), ["Bread", "Eggs"])
        self.assertEqual(state["undo"]["label"], "Cleared 1 item")
        _, state = self.call("POST", "/api/undo", {"id": state["undo"]["id"]})
        self.assertEqual([(i["text"], i["done"]) for i in state["shopping"]],
                         [("Eggs", False), ("Bread", False), ("Milk", True)])
        self.assertIsNone(state["undo"])

    def test_shopping_clear_label_plural_and_noop(self):
        _, state = self.call("POST", "/api/shopping/clear")
        self.assertIsNone(state["undo"])
        for text in ("Milk", "Eggs"):
            item_id = next(i["id"] for i in self.shop_add(text)["shopping"] if i["text"] == text)
            self.call("POST", f"/api/shopping/{item_id}/check")
        _, state = self.call("POST", "/api/shopping/clear")
        self.assertEqual(state["undo"]["label"], "Cleared 2 items")
        self.mono[0] += 1
        _, state = self.call("POST", "/api/shopping/clear")  # nothing ticked: keeps the earlier undo
        self.assertEqual(state["undo"]["label"], "Cleared 2 items")

    def test_task_and_plan_undo_still_work_with_shopping(self):
        self.shop_add("Milk")
        plan = self.new_plan(steps=["Cook"])["plans"]["items"][0]
        _, state = self.call("DELETE", f"/api/plans/{plan['id']}")
        _, state = self.call("POST", "/api/undo")
        self.assertEqual(len(state["plans"]["items"]), 1)
        self.assertEqual([i["text"] for i in state["shopping"]], ["Milk"])

    def test_plan_ingredients_import(self):
        plan = self.new_plan(ingredients=["Salt", "Rice", "Onion"])["plans"]["items"][0]
        self.call("POST", f"/api/plans/{plan['id']}/check", {"kind": "ingredients", "itemId": plan["ingredients"][0]["id"]})
        self.shop_add("rice")
        status, state = self.call("POST", f"/api/plans/{plan['id']}/shopping")
        self.assertEqual(status, 200)
        self.assertEqual(state["added"], 1)
        self.assertEqual(sorted(i["text"] for i in state["shopping"]), ["Onion", "rice"])
        self.assertEqual(self.call("POST", f"/api/plans/{plan['id']}/shopping")[1]["added"], 0)

    def test_plan_import_with_no_ingredients_and_unknown_plan(self):
        plan = self.new_plan(steps=["Cook"])["plans"]["items"][0]
        status, state = self.call("POST", f"/api/plans/{plan['id']}/shopping")
        self.assertEqual((status, state["added"], state["shopping"]), (200, 0, []))
        self.assertEqual(self.call("POST", "/api/plans/nope/shopping")[0], 404)

    def test_plan_import_into_a_full_list_adds_nothing(self):
        plan = self.new_plan(ingredients=["Salt", "Pepper"])["plans"]["items"][0]
        for n in range(199):
            self.app.data.setdefault("shoppingList", []).append({"id": f"i{n}", "text": f"Item {n}", "done": False})
        status, payload = self.call("POST", f"/api/plans/{plan['id']}/shopping")
        self.assertEqual((status, payload), (400, {"error": "The list is full. Clear some items first."}))
        self.assertEqual(len(self.app.data["shoppingList"]), 199)  # atomic: neither new ingredient was added

    def test_plan_import_unticks_and_counts_a_ticked_match(self):
        plan = self.new_plan(ingredients=["Rice"])["plans"]["items"][0]
        item_id = self.shop_add("rice")["shopping"][0]["id"]
        self.call("POST", f"/api/shopping/{item_id}/check")
        status, state = self.call("POST", f"/api/plans/{plan['id']}/shopping")
        self.assertEqual((status, state["added"]), (200, 1))
        self.assertEqual([(i["text"], i["done"]) for i in state["shopping"]], [("rice", False)])

    def test_shopping_survives_a_restart(self):
        self.shop_add("Milk")
        self.app = self.build()
        self.assertEqual([i["text"] for i in self.call("GET", "/api/state")[1]["shopping"]], ["Milk"])

    def with_alerts(self, *ids, fresh=True):
        self.alerts = FakeAlerts([alert(i) for i in ids], fresh)
        self.app = self.build(alerts=self.alerts)

    def test_alerts_default_to_none(self):
        self.assertEqual(self.call("GET", "/api/alerts"), (200, {"alerts": []}))

    def test_alerts_listed(self):
        self.with_alerts("a1", "a2")
        status, body = self.call("GET", "/api/alerts")
        self.assertEqual(status, 200)
        self.assertEqual([a["id"] for a in body["alerts"]], ["a1", "a2"])

    def test_alert_dismiss_hides_it(self):
        self.with_alerts("a1", "a2")
        status, body = self.call("POST", "/api/alerts/dismiss", {"id": "a1"})
        self.assertEqual(status, 200)
        self.assertEqual([a["id"] for a in body["alerts"]], ["a2"])
        self.assertEqual([a["id"] for a in self.call("GET", "/api/alerts")[1]["alerts"]], ["a2"])

    def test_alert_dismiss_unknown_id_is_404(self):
        self.with_alerts("a1")
        self.assertEqual(self.call("POST", "/api/alerts/dismiss", {"id": "nope"})[0], 404)

    def test_alert_dismiss_rejects_bad_input(self):
        self.with_alerts("a1")
        for body in ({}, {"id": ""}, {"id": 5}, {"id": None}, {"id": ["a1"]}):
            self.assertEqual(self.call("POST", "/api/alerts/dismiss", body)[0], 400, body)
        self.assertEqual(self.call("POST", "/api/alerts/dismiss", ["a1"])[0], 400)

    def test_alert_dismissal_survives_restart_and_new_id_shows(self):
        self.with_alerts("a1")
        self.call("POST", "/api/alerts/dismiss", {"id": "a1"})
        self.app = self.build(alerts=self.alerts)
        self.assertEqual(self.call("GET", "/api/alerts")[1]["alerts"], [])
        self.alerts.alerts = [alert("a1-v2")]
        self.assertEqual([a["id"] for a in self.call("GET", "/api/alerts")[1]["alerts"]], ["a1-v2"])

    def test_alert_dismissals_pruned_only_when_fresh(self):
        self.with_alerts("a1", "a2")
        self.call("POST", "/api/alerts/dismiss", {"id": "a1"})
        self.call("POST", "/api/alerts/dismiss", {"id": "a2"})
        self.alerts.alerts = [alert("a2")]
        self.alerts.fresh = False
        self.call("GET", "/api/alerts")
        self.assertEqual(self.app.data["alertsDismissed"], ["a1", "a2"])
        self.alerts.fresh = True
        self.call("GET", "/api/alerts")
        self.assertEqual(self.app.data["alertsDismissed"], ["a2"])
        self.assertEqual(self.build(alerts=self.alerts).data["alertsDismissed"], ["a2"])

    def test_alert_dismissals_keep_newest_fifty(self):
        ids = [f"id{i}" for i in range(55)]
        self.with_alerts(*ids)
        for i in ids:
            self.call("POST", "/api/alerts/dismiss", {"id": i})
        self.assertEqual(self.app.data["alertsDismissed"], ids[-50:])

    def test_alerts_fetched_outside_the_lock(self):
        app = self.app
        seen = []

        class Probe(FakeAlerts):
            def get(probe):
                seen.append(app.lock.locked())
                return []

        app.alerts = Probe()
        self.call("GET", "/api/alerts")
        self.assertEqual(seen, [False])

    def count_saves(self):
        saves = []
        real = self.app.store.save
        self.app.store.save = lambda data: (saves.append(1), real(data))[1]
        return saves

    def test_alert_get_saves_only_when_pruning(self):
        self.with_alerts("a1", "a2")
        self.call("POST", "/api/alerts/dismiss", {"id": "a1"})
        saves = self.count_saves()
        self.call("GET", "/api/alerts")
        self.assertEqual(saves, [])
        self.alerts.alerts = [alert("a2")]
        self.call("GET", "/api/alerts")
        self.assertEqual(len(saves), 1)
        self.assertEqual(self.app.data["alertsDismissed"], [])

    def test_alerts_source_that_raises_gives_empty_list(self):
        class Boom(FakeAlerts):
            def get(self):
                raise RuntimeError("boom")

        self.app.alerts = Boom()
        self.assertEqual(self.call("GET", "/api/alerts"), (200, {"alerts": []}))

if __name__ == "__main__":
    unittest.main()
