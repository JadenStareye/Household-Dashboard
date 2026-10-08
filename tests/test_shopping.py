import unittest

from dashboard import shopping

FULL = "The list is full. Clear some items first."


def fill(data, n):
    for i in range(n):
        shopping.add(data, f"item {i}")


class AddTests(unittest.TestCase):
    def test_add_trims_and_stores(self):
        data = {}
        item = shopping.add(data, "  Milk  ")
        self.assertEqual(data["shoppingList"], [item])
        self.assertEqual(item["text"], "Milk")
        self.assertIs(item["done"], False)
        self.assertRegex(item["id"], r"^[0-9a-f]{8}$")

    def test_empty_and_non_string_rejected(self):
        data = {}
        for bad in ["", "   ", None, 5, ["milk"]]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as caught:
                    shopping.add(data, bad)
                self.assertEqual(str(caught.exception), "Enter an item")
        self.assertEqual(data.get("shoppingList", []), [])

    def test_length_limit(self):
        data = {}
        self.assertEqual(len(shopping.add(data, "x" * 200)["text"]), 200)
        with self.assertRaises(ValueError) as caught:
            shopping.add(data, "x" * 201)
        self.assertEqual(str(caught.exception), "Keep it under 200 characters")
        self.assertEqual(len(data["shoppingList"]), 1)

    def test_dedupe_case_and_whitespace_returns_existing(self):
        data = {}
        first = shopping.add(data, "Milk")
        again = shopping.add(data, " milk ")
        self.assertIs(again, first)
        self.assertEqual(len(data["shoppingList"]), 1)
        self.assertIs(shopping.add(data, "MILK")["done"], False)
        self.assertIs(shopping.add(data, "a  b"), shopping.add(data, "A B"))

    def test_readd_unticks(self):
        data = {}
        item = shopping.add(data, "Milk")
        shopping.check(data, item["id"])
        self.assertIs(item["done"], True)
        shopping.add(data, "milk")
        self.assertIs(item["done"], False)
        self.assertEqual(len(data["shoppingList"]), 1)

    def test_limit_of_200_items(self):
        data = {}
        fill(data, 200)
        self.assertEqual(len(data["shoppingList"]), 200)
        with self.assertRaises(ValueError) as caught:
            shopping.add(data, "one too many")
        self.assertEqual(str(caught.exception), FULL)
        self.assertEqual(len(data["shoppingList"]), 200)

    def test_full_list_still_dedupes(self):
        data = {}
        fill(data, 200)
        self.assertEqual(shopping.add(data, "ITEM 3")["text"], "item 3")

    def test_junk_entries_do_not_raise(self):
        data = {"shoppingList": [None, 5, {"id": 1}, {"id": "a", "text": "  "}]}
        item = shopping.add(data, "Milk")
        self.assertEqual(item["text"], "Milk")
        self.assertEqual(len(data["shoppingList"]), 5)

    def test_non_list_storage_is_replaced(self):
        data = {"shoppingList": "junk"}
        shopping.add(data, "Milk")
        self.assertEqual(len(data["shoppingList"]), 1)


class JunkLimitTests(unittest.TestCase):
    def test_junk_does_not_count_toward_limit(self):
        data = {"shoppingList": [None] * 200}
        self.assertEqual(shopping.add(data, "Milk")["text"], "Milk")
        data = {"shoppingList": [{"id": 1}] * 200}
        self.assertEqual(shopping.add_many(data, ["Milk", "Eggs"]), 2)

    def test_usable_items_still_limited_alongside_junk(self):
        data = {"shoppingList": [None] * 5}
        fill(data, 200)
        with self.assertRaises(ValueError):
            shopping.add(data, "extra")
        with self.assertRaises(ValueError):
            shopping.add_many(data, ["extra"])


class AddManyTests(unittest.TestCase):
    def test_text_length_boundary(self):
        data = {}
        self.assertEqual(shopping.add_many(data, ["x" * 200, "y" * 201]), 1)
        self.assertEqual(len(data["shoppingList"]), 1)
        self.assertEqual(len(data["shoppingList"][0]["text"]), 200)

    def test_counts_new_items(self):
        data = {}
        self.assertEqual(shopping.add_many(data, ["Milk", "Eggs"]), 2)
        self.assertEqual([i["text"] for i in data["shoppingList"]], ["Milk", "Eggs"])

    def test_skips_blank_nonstring_overlong_and_present(self):
        data = {}
        shopping.add(data, "Milk")
        added = shopping.add_many(data, ["", "  ", None, 5, "x" * 201, " milk ", "Eggs", "eggs"])
        self.assertEqual(added, 1)
        self.assertEqual([i["text"] for i in data["shoppingList"]], ["Milk", "Eggs"])

    def test_counts_unticked_match(self):
        data = {}
        item = shopping.add(data, "Milk")
        shopping.check(data, item["id"])
        self.assertEqual(shopping.add_many(data, ["milk", "Eggs"]), 2)
        self.assertIs(item["done"], False)
        self.assertEqual(len(data["shoppingList"]), 2)

    def test_empty_input(self):
        data = {}
        self.assertEqual(shopping.add_many(data, []), 0)

    def test_atomic_when_too_many(self):
        data = {}
        fill(data, 199)
        ticked = data["shoppingList"][0]
        ticked["done"] = True
        before = [dict(i) for i in data["shoppingList"]]
        with self.assertRaises(ValueError) as caught:
            shopping.add_many(data, ["item 0", "new a", "new b"])
        self.assertEqual(str(caught.exception), FULL)
        self.assertEqual(data["shoppingList"], before)

    def test_exactly_filling_is_allowed(self):
        data = {}
        fill(data, 198)
        self.assertEqual(shopping.add_many(data, ["new a", "new b"]), 2)
        self.assertEqual(len(data["shoppingList"]), 200)

    def test_junk_entries_do_not_raise(self):
        data = {"shoppingList": [None, {"id": "a"}, 3]}
        self.assertEqual(shopping.add_many(data, ["Milk"]), 1)


class CheckRemoveTests(unittest.TestCase):
    def test_check_toggles(self):
        data = {}
        item = shopping.add(data, "Milk")
        self.assertIs(shopping.check(data, item["id"])["done"], True)
        self.assertIs(shopping.check(data, item["id"])["done"], False)

    def test_check_item_missing_done(self):
        data = {"shoppingList": [{"id": "a1", "text": "Milk"}]}
        self.assertIs(shopping.check(data, "a1")["done"], True)

    def test_check_unknown_id(self):
        with self.assertRaises(KeyError):
            shopping.check({}, "nope")

    def test_check_skips_junk(self):
        data = {"shoppingList": [None, 5, {"id": "a", "text": " "}, {"id": "b", "text": "Milk"}]}
        self.assertIs(shopping.check(data, "b")["done"], True)
        with self.assertRaises(KeyError):
            shopping.check(data, "a")

    def test_remove(self):
        data = {}
        keep = shopping.add(data, "Eggs")
        gone = shopping.add(data, "Milk")
        shopping.remove(data, gone["id"])
        self.assertEqual(data["shoppingList"], [keep])

    def test_remove_unknown_id(self):
        data = {}
        shopping.add(data, "Milk")
        with self.assertRaises(KeyError):
            shopping.remove(data, "nope")
        self.assertEqual(len(data["shoppingList"]), 1)


class ClearRestoreTests(unittest.TestCase):
    def test_clear_removes_ticked_and_returns_copies(self):
        data = {}
        a = shopping.add(data, "Milk")
        b = shopping.add(data, "Eggs")
        c = shopping.add(data, "Tea")
        shopping.check(data, a["id"])
        shopping.check(data, c["id"])
        gone = shopping.clear(data)
        self.assertEqual([i["text"] for i in gone], ["Milk", "Tea"])
        self.assertEqual(data["shoppingList"], [b])
        gone[0]["text"] = "changed"
        self.assertEqual(a["text"], "Milk")

    def test_clear_with_none_ticked(self):
        data = {}
        shopping.add(data, "Milk")
        self.assertEqual(shopping.clear(data), [])
        self.assertEqual(len(data["shoppingList"]), 1)

    def test_clear_on_empty_and_junk(self):
        self.assertEqual(shopping.clear({}), [])
        data = {"shoppingList": [None, 5, {"id": 1, "done": True}]}
        self.assertEqual(shopping.clear(data), [])
        self.assertEqual(len(data["shoppingList"]), 3)

    def test_restore_appends_missing_ids(self):
        data = {}
        a = shopping.add(data, "Milk")
        shopping.check(data, a["id"])
        gone = shopping.clear(data)
        shopping.add(data, "Eggs")
        shopping.restore(data, {"shopping": gone})
        self.assertEqual([i["text"] for i in data["shoppingList"]], ["Eggs", "Milk"])
        self.assertIsNot(data["shoppingList"][1], gone[0])

    def test_restore_skips_existing_id(self):
        data = {"shoppingList": [{"id": "a1", "text": "Milk", "done": False}]}
        shopping.restore(data, {"shopping": [{"id": "a1", "text": "Other", "done": True}]})
        self.assertEqual(data["shoppingList"], [{"id": "a1", "text": "Milk", "done": False}])

    def test_restore_skips_item_already_re_added_by_text(self):
        data = {}
        shopping.check(data, shopping.add(data, "Milk")["id"])
        gone = shopping.clear(data)
        shopping.add(data, "milk")
        shopping.restore(data, {"shopping": gone})
        self.assertEqual([i["text"] for i in data["shoppingList"]], ["milk"])

    def test_restore_respects_the_item_cap(self):
        data = {"shoppingList": [{"id": f"i{n}", "text": f"Item {n}", "done": False} for n in range(199)]}
        saved = [{"id": "s1", "text": "Saved 1", "done": True}, {"id": "s2", "text": "Saved 2", "done": True}]
        shopping.restore(data, {"shopping": saved})
        self.assertEqual(len(data["shoppingList"]), shopping.MAX_ITEMS)
        self.assertEqual(data["shoppingList"][-1]["id"], "s1")

    def test_restore_record_without_key(self):
        data = {}
        shopping.restore(data, {"plans": []})
        self.assertEqual(data.get("shoppingList", []), [])

    def test_restore_ignores_unusable(self):
        data = {}
        shopping.restore(data, {"shopping": [None, 5, {"id": 1}, {"id": "a", "text": " "},
                                             {"id": "g", "text": "Good", "done": True}]})
        self.assertEqual(data["shoppingList"], [{"id": "g", "text": "Good", "done": True}])


class RestoreRobustTests(unittest.TestCase):
    def test_bad_shopping_value_or_record(self):
        for record in [{"shopping": None}, {"shopping": "x"}, {"shopping": 5}, {"shopping": {"id": "a"}}, None, [], "x", 5]:
            with self.subTest(record=record):
                data = {}
                shopping.restore(data, record)
                self.assertEqual(data.get("shoppingList", []), [])

    def test_duplicate_ids_in_one_record(self):
        data = {}
        shopping.restore(data, {"shopping": [{"id": "a", "text": "One"}, {"id": "a", "text": "Two"}]})
        self.assertEqual([i["text"] for i in data["shoppingList"]], ["One"])


class BoolishDoneTests(unittest.TestCase):
    def test_view_treats_done_as_bool(self):
        data = {"shoppingList": [{"id": str(n), "text": f"t{n}", "done": d} for n, d in enumerate(["false", 1, None, 0])]}
        self.assertEqual([(i["id"], i["done"]) for i in shopping.view(data)],
                         [("2", False), ("3", False), ("0", True), ("1", True)])

    def test_check_toggles_truthiness(self):
        data = {"shoppingList": [{"id": "a", "text": "A", "done": "false"}, {"id": "b", "text": "B", "done": None}]}
        self.assertIs(shopping.check(data, "a")["done"], False)
        self.assertIs(shopping.check(data, "b")["done"], True)

    def test_clear_uses_truthiness(self):
        data = {"shoppingList": [{"id": "a", "text": "A", "done": 1}, {"id": "b", "text": "B", "done": None},
                                 {"id": "c", "text": "C", "done": "false"}]}
        self.assertEqual([i["id"] for i in shopping.clear(data)], ["a", "c"])
        self.assertEqual([i["id"] for i in data["shoppingList"]], ["b"])


class ViewTests(unittest.TestCase):
    def test_missing_key_or_bad_type(self):
        self.assertEqual(shopping.view({}), [])
        self.assertEqual(shopping.view({"shoppingList": "junk"}), [])

    def test_unticked_first_then_ticked_stable(self):
        data = {"shoppingList": [
            {"id": "a", "text": "A", "done": True},
            {"id": "b", "text": "B", "done": False},
            {"id": "c", "text": "C", "done": True},
            {"id": "d", "text": "D"},
        ]}
        self.assertEqual(shopping.view(data), [
            {"id": "b", "text": "B", "done": False},
            {"id": "d", "text": "D", "done": False},
            {"id": "a", "text": "A", "done": True},
            {"id": "c", "text": "C", "done": True},
        ])

    def test_junk_skipped(self):
        data = {"shoppingList": [None, 5, {"id": 1}, {"id": "a", "text": "  "},
                                 {"id": "", "text": "x"}, {"id": "g", "text": "Good", "extra": 1}]}
        self.assertEqual(shopping.view(data), [{"id": "g", "text": "Good", "done": False}])


if __name__ == "__main__":
    unittest.main()
