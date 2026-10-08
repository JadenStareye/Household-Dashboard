import unittest
from datetime import date

from dashboard import rules, todo

TODAY = date(2026, 10, 6)


class MatchesTest(unittest.TestCase):
    def test_daily_and_weekdays(self):
        self.assertTrue(rules.matches({"repeat": "daily"}, date(2026, 10, 10)))
        self.assertTrue(rules.matches({"repeat": "weekdays"}, date(2026, 10, 9)))
        self.assertFalse(rules.matches({"repeat": "weekdays"}, date(2026, 10, 10)))

    def test_weekly(self):
        rule = {"repeat": "weekly", "days": ["mon", "fri"]}
        self.assertTrue(rules.matches(rule, date(2026, 10, 5)))
        self.assertFalse(rules.matches(rule, date(2026, 10, 6)))

    def test_unknown_repeat(self):
        with self.assertRaises(ValueError):
            rules.matches({"repeat": "yearly"}, TODAY)

    def test_biweekly_monday_anchor(self):
        rule = {"repeat": "biweekly", "days": ["mon"], "anchor": "2026-10-05"}
        self.assertTrue(rules.matches(rule, date(2026, 10, 5)))
        self.assertFalse(rules.matches(rule, date(2026, 10, 12)))
        self.assertTrue(rules.matches(rule, date(2026, 10, 19)))

    def test_biweekly_anchor_midweek_uses_its_monday(self):
        rule = {"repeat": "biweekly", "days": ["mon", "sat"], "anchor": "2026-10-08"}
        self.assertTrue(rules.matches(rule, date(2026, 10, 5)))
        self.assertTrue(rules.matches(rule, date(2026, 10, 10)))
        self.assertFalse(rules.matches(rule, date(2026, 10, 12)))

    def test_biweekly_across_year_boundary(self):
        rule = {"repeat": "biweekly", "days": ["mon"], "anchor": "2026-12-28"}
        self.assertTrue(rules.matches(rule, date(2026, 12, 28)))
        self.assertFalse(rules.matches(rule, date(2027, 1, 4)))
        self.assertTrue(rules.matches(rule, date(2027, 1, 11)))

    def test_biweekly_anchor_week_before_year_boundary(self):
        rule = {"repeat": "biweekly", "days": ["mon"], "anchor": "2026-12-21"}
        self.assertFalse(rules.matches(rule, date(2026, 12, 28)))
        self.assertTrue(rules.matches(rule, date(2027, 1, 4)))

    def test_biweekly_before_anchor(self):
        rule = {"repeat": "biweekly", "days": ["mon"], "anchor": "2026-10-05"}
        self.assertFalse(rules.matches(rule, date(2026, 9, 28)))
        self.assertTrue(rules.matches(rule, date(2026, 9, 21)))

    def test_monthly(self):
        rule = {"repeat": "monthly", "dayOfMonth": 15}
        self.assertTrue(rules.matches(rule, date(2026, 10, 15)))
        self.assertFalse(rules.matches(rule, date(2026, 10, 16)))

    def test_monthly_31_clamps_to_last_day(self):
        rule = {"repeat": "monthly", "dayOfMonth": 31}
        self.assertTrue(rules.matches(rule, date(2026, 2, 28)))
        self.assertFalse(rules.matches(rule, date(2026, 2, 27)))
        self.assertTrue(rules.matches(rule, date(2026, 4, 30)))
        self.assertTrue(rules.matches(rule, date(2026, 10, 31)))

    def test_monthly_leap_february(self):
        self.assertTrue(rules.matches({"repeat": "monthly", "dayOfMonth": 31}, date(2028, 2, 29)))
        self.assertFalse(rules.matches({"repeat": "monthly", "dayOfMonth": 31}, date(2028, 2, 28)))
        self.assertFalse(rules.matches({"repeat": "monthly", "dayOfMonth": 29}, date(2026, 2, 27)))
        self.assertTrue(rules.matches({"repeat": "monthly", "dayOfMonth": 29}, date(2026, 2, 28)))


class ValidateTest(unittest.TestCase):
    def test_daily_drops_irrelevant_and_unknown(self):
        out = rules.validate(
            {"title": "  Vit  ", "repeat": "daily", "days": ["mon"], "dayOfMonth": 3, "x": 1, "paused": 1},
            TODAY,
        )
        self.assertEqual(out, {"title": "Vit", "repeat": "daily", "paused": True})

    def test_paused_defaults_false(self):
        out = rules.validate({"title": "a", "repeat": "weekdays"}, TODAY)
        self.assertIs(out["paused"], False)

    def test_weekly_days_deduped_and_ordered(self):
        out = rules.validate(
            {"title": "a", "repeat": "weekly", "days": ["fri", "mon", "fri", "bogus"]}, TODAY
        )
        self.assertEqual(out["days"], ["mon", "fri"])

    def test_weekly_needs_a_valid_day(self):
        for days in ([], ["bogus"], None, "mon"):
            with self.assertRaises(ValueError):
                rules.validate({"title": "a", "repeat": "weekly", "days": days}, TODAY)

    def test_biweekly_anchor_default_and_given(self):
        out = rules.validate({"title": "a", "repeat": "biweekly", "days": ["tue"]}, TODAY)
        self.assertEqual(out["anchor"], "2026-10-06")
        out = rules.validate(
            {"title": "a", "repeat": "biweekly", "days": ["tue"], "anchor": "2026-01-01"}, TODAY
        )
        self.assertEqual(out["anchor"], "2026-01-01")

    def test_biweekly_bad_anchor(self):
        for anchor in ("nope", "2026-13-01", 5):
            with self.assertRaises(ValueError):
                rules.validate(
                    {"title": "a", "repeat": "biweekly", "days": ["tue"], "anchor": anchor}, TODAY
                )

    def test_monthly(self):
        out = rules.validate(
            {"title": "a", "repeat": "monthly", "dayOfMonth": 31, "days": ["mon"]}, TODAY
        )
        self.assertEqual(out["dayOfMonth"], 31)
        self.assertNotIn("days", out)
        for bad in (0, 32, True, "5", 2.5, None):
            with self.assertRaises(ValueError):
                rules.validate({"title": "a", "repeat": "monthly", "dayOfMonth": bad}, TODAY)

    def test_title_and_repeat_errors(self):
        for raw in (
            {"title": "", "repeat": "daily"},
            {"title": "   ", "repeat": "daily"},
            {"title": "x" * 201, "repeat": "daily"},
            {"title": 5, "repeat": "daily"},
            {"repeat": "daily"},
            {"title": "a", "repeat": "yearly"},
            {"title": "a"},
        ):
            with self.assertRaises(ValueError):
                rules.validate(raw, TODAY)
        rules.validate({"title": "x" * 200, "repeat": "daily"}, TODAY)

    def test_non_dict(self):
        with self.assertRaises(ValueError):
            rules.validate([], TODAY)


class SeedTest(unittest.TestCase):
    SEED = [{"id": "a", "title": "A", "repeat": "daily"}]

    def test_seed_once(self):
        data = {}
        rules.seed(data, self.SEED)
        self.assertEqual(
            data["rules"], [{"id": "a", "title": "A", "repeat": "daily", "paused": False}]
        )
        self.assertIs(data["rulesSeeded"], True)
        self.assertNotIn("paused", self.SEED[0])
        data["rules"][0]["title"] = "changed"
        rules.seed(data, self.SEED)
        self.assertEqual(data["rules"][0]["title"], "changed")

    def test_deleted_stays_deleted(self):
        data = {}
        rules.seed(data, self.SEED)
        rules.delete(data, "a")
        rules.seed(data, self.SEED)
        self.assertEqual(data["rules"], [])


class CrudTest(unittest.TestCase):
    def test_create_update_delete(self):
        data = {"rules": []}
        rule = rules.create(data, {"title": "A", "repeat": "daily"}, TODAY)
        self.assertEqual(len(rule["id"]), 8)
        self.assertEqual(data["rules"], [rule])
        updated = rules.update(data, rule["id"], {"title": "B", "repeat": "weekdays"}, TODAY)
        self.assertEqual(updated["id"], rule["id"])
        self.assertEqual(data["rules"], [updated])
        self.assertEqual(updated["title"], "B")
        rules.delete(data, rule["id"])
        self.assertEqual(data["rules"], [])

    def test_create_without_rules_key(self):
        data = {}
        rules.create(data, {"title": "A", "repeat": "daily"}, TODAY)
        self.assertEqual(len(data["rules"]), 1)

    def test_missing(self):
        data = {"rules": []}
        with self.assertRaises(KeyError):
            rules.update(data, "zz", {"title": "A", "repeat": "daily"}, TODAY)
        with self.assertRaises(KeyError):
            rules.delete(data, "zz")

    def test_invalid_leaves_data_untouched(self):
        data = {"rules": []}
        with self.assertRaises(ValueError):
            rules.create(data, {"title": "", "repeat": "daily"}, TODAY)
        self.assertEqual(data["rules"], [])


class TodoIntegrationTest(unittest.TestCase):
    def test_paused_rules_skipped_and_missing_paused_ok(self):
        data = {}
        rs = [
            {"id": "p", "title": "Paused", "repeat": "daily", "paused": True},
            {"id": "q", "title": "Live", "repeat": "daily"},
        ]
        todo.generate_recurring(data, rs, TODAY)
        self.assertEqual([t["ruleId"] for t in data["tasks"]], ["q"])


if __name__ == "__main__":
    unittest.main()
