import random
import unittest
from datetime import date, timedelta

from dashboard import dinners

RECIPES = [{"id": f"r{i}", "name": f"Dish {i}", "url": "https://example.com", "minutes": 20} for i in range(1, 10)]
DAY1 = date(2026, 10, 6)


def fresh():
    return {}, random.Random(1)


class RotationTests(unittest.TestCase):
    def test_three_distinct_picks_stable_within_day(self):
        data, rng = fresh()
        state = dinners.ensure_today(data, "chris", RECIPES, DAY1, rng)
        picks = list(state["picks"])
        self.assertEqual(len(set(picks)), 3)
        again = dinners.ensure_today(data, "chris", RECIPES, DAY1, random.Random(99))
        self.assertEqual(again["picks"], picks)

    def test_retired_picks_are_replaced_the_same_day(self):
        data, rng = fresh()
        dinners.ensure_today(data, "chris", RECIPES, DAY1, rng)
        data["dinners"]["chris"]["picks"] = ["gone-1", "gone-2", "r1"]
        state = dinners.ensure_today(data, "chris", RECIPES, DAY1, rng)
        self.assertEqual(len(state["picks"]), 3)
        self.assertEqual(state["picks"][0], "r1")
        self.assertTrue(all(p in {r["id"] for r in RECIPES} for p in state["picks"]))

    def test_full_cycle_has_no_repeats(self):
        data, rng = fresh()
        seen = []
        for offset in range(3):
            day = DAY1 + timedelta(days=offset)
            seen += dinners.ensure_today(data, "chris", RECIPES, day, rng)["picks"]
        self.assertEqual(len(set(seen)), 9)

    def test_swap_replaces_with_unseen_and_persists(self):
        data, rng = fresh()
        picks = list(dinners.ensure_today(data, "chris", RECIPES, DAY1, rng)["picks"])
        state = dinners.swap(data, "chris", RECIPES, DAY1, picks[1], rng)
        self.assertEqual(state["picks"][0], picks[0])
        self.assertEqual(state["picks"][2], picks[2])
        self.assertNotIn(state["picks"][1], picks)
        self.assertEqual(dinners.ensure_today(data, "chris", RECIPES, DAY1, rng)["picks"], state["picks"])

    def test_swap_unknown_recipe_raises(self):
        data, rng = fresh()
        dinners.ensure_today(data, "chris", RECIPES, DAY1, rng)
        with self.assertRaises(KeyError):
            dinners.swap(data, "chris", RECIPES, DAY1, "nope", rng)


class FavoriteAndHideTests(unittest.TestCase):
    def test_favorites_appear_twice_in_fresh_queue(self):
        data, rng = fresh()
        dinners.toggle_favorite(data, "chris", "r4", RECIPES)
        state = data["dinners"]["chris"]
        dinners._refill(state, [r["id"] for r in RECIPES], rng)
        self.assertEqual(state["queue"].count("r4"), 2)
        self.assertEqual(len(state["queue"]), 10)

    def test_toggle_favorite_on_and_off(self):
        data = {}
        dinners.toggle_favorite(data, "v", "r2", RECIPES)
        self.assertEqual(data["dinners"]["v"]["favorites"], ["r2"])
        dinners.toggle_favorite(data, "v", "r2", RECIPES)
        self.assertEqual(data["dinners"]["v"]["favorites"], [])
        with self.assertRaises(KeyError):
            dinners.toggle_favorite(data, "v", "zzz", RECIPES)

    def test_hide_removes_from_picks_favorites_and_future(self):
        data, rng = fresh()
        picks = list(dinners.ensure_today(data, "v", RECIPES, DAY1, rng)["picks"])
        target = picks[0]
        dinners.toggle_favorite(data, "v", target, RECIPES)
        state = dinners.hide(data, "v", target, RECIPES, DAY1, rng)
        self.assertNotIn(target, state["picks"])
        self.assertEqual(len(state["picks"]), 3)
        self.assertNotIn(target, state["favorites"])
        for offset in range(1, 6):
            later = dinners.ensure_today(data, "v", RECIPES, DAY1 + timedelta(days=offset), rng)
            self.assertNotIn(target, later["picks"])

    def test_restore_unhides(self):
        data, rng = fresh()
        dinners.hide(data, "v", "r1", RECIPES, DAY1, rng)
        dinners.restore(data, "v", "r1")
        self.assertEqual(data["dinners"]["v"]["hidden"], [])

    def test_view_flags_favorites_and_lists_hidden(self):
        data, rng = fresh()
        picks = dinners.ensure_today(data, "v", RECIPES, DAY1, rng)["picks"]
        dinners.toggle_favorite(data, "v", picks[0], RECIPES)
        not_shown = next(r["id"] for r in RECIPES if r["id"] not in picks)
        dinners.hide(data, "v", not_shown, RECIPES, DAY1, rng)
        view = dinners.view(data, "v", RECIPES)
        self.assertTrue(view["picks"][0]["favorite"])
        self.assertFalse(view["picks"][1]["favorite"])
        self.assertEqual([r["id"] for r in view["favorites"]], [picks[0]])
        self.assertEqual([r["id"] for r in view["hidden"]], [not_shown])

    def test_small_list_does_not_loop_forever(self):
        data, rng = fresh()
        tiny = RECIPES[:2]
        state = dinners.ensure_today(data, "chris", tiny, DAY1, rng)
        self.assertEqual(len(state["picks"]), 2)


if __name__ == "__main__":
    unittest.main()
