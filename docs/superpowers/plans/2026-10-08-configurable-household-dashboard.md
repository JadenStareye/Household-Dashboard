# Configurable Household Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-household home dashboard into a Windows app that other households can install and configure themselves, through a first-run wizard and in-app Settings.

**Architecture:** Start from a data-free copy of the existing stdlib-only Python server and vanilla web UI. One validated `household.json` (in `%APPDATA%\HomeDashboard`) replaces everything that was hardcoded: location, units, modules, rooms (which generate a weekday cleaning rotation as ordinary repeating rules) and any number of meal slots fed by read-only starter packs. The browser gains a setup wizard, three Settings tabs and a scale-to-fit layout; PyInstaller and Inno Setup package it.

**Tech Stack:** Python 3.11+ standard library (runtime), vanilla JS and CSS, `unittest`, PyInstaller, Inno Setup 6, Open-Meteo (weather, place search), US National Weather Service (alerts).

**Spec:** `docs/superpowers/specs/2026-10-08-configurable-household-dashboard-design.md`

## Global Constraints

- **Runtime is standard library only.** PyInstaller and Inno Setup are build-time tools, installed in a throwaway virtualenv (`.venv-build`), never into the global Python.
- **Repo:** `C:\Users\shado\Claude\Household-Dashboard`, remote `https://github.com/JadenStareye/Household-Dashboard.git`, branch `main`. The plan and spec are already committed there.
- **The source app `C:\Users\shado\Claude\home-dashboard` is a live household's install.** Read it only to copy files in Task 0 (and to build an exclusion list in Task 6). Never edit it. Never stop the process listening on port 8765; dev servers started in this plan fall back to 8766 or higher, so always use the port the server prints.
- **None of the original household's data may appear in the new repo**: no names, town, coordinates, recipes or chores. Example and fixture content uses "Sample Household", Portland, `example.com`.
- **A household's own files live in `%APPDATA%\HomeDashboard`** (override with `HOME_DASHBOARD_DATA`). The install folder is never written to. The server binds `127.0.0.1` only. Every file write is atomic.
- **UI rules:** keep the existing labels and visual language; every touch target at least 52px; no `innerHTML`, `insertAdjacent` or `outerHTML`; server validation messages are plain language and reach the user through the `detail` field of failed requests.
- **Line endings:** the copied web files use CRLF. Edit them only with the supplied Python patch scripts (they read and write in text mode and assert every replacement matches exactly once). Save each script as `_patch_<name>.py` at the repo root, run it with `python`, then delete it before committing.
- **Commands:** run from the repo root. Bash steps use Git Bash; PowerShell steps are marked. Test command: `python -m unittest discover -s tests -t .`
- **Browser checks** (Tasks 7 to 10) need a browser. If the executing agent has none, finish the automated steps, mark the browser steps as pending for the user, and say so in the report.

**User decisions (already made):**
- "Download and run locally": a Windows installer with Python bundled, for friends and family; no hosting, accounts, payments or licensing.
- The person setting up is a non-technical household member, so a first-run wizard plus a gear-icon settings screen; no JSON editing.
- Configurable: location and units, chores, dinner meal slots, and which modules are shown.
- Chores: a rooms wizard that generates a weekday rotation.
- Meals: flexible meal slots; recipes come from curated starter packs (new lists) with name, link, time and tags only, plus the household's own recipes.
- Layout: responsive to any screen size; modules toggle on or off.
- "Skip over V's recipes as that is only for our household" and "Skip over Vs settings for all data, use placeholders as examples": nothing from the original household ships; placeholders demonstrate each configurable part.
- Updates are manual: send a new installer; household data survives reinstall.
- Approach: refactor the existing app (option 1), not a rewrite.

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `dashboard/chores_gen.py` | Rooms in, Monday to Friday cleaning rotation out | 1 |
| `dashboard/paths.py` | Where bundled files and household data live | 2 |
| `dashboard/store.py` | Existing store; atomic write becomes a shared helper | 2 |
| `dashboard/packs.py` | Starter pack and recipe validation, recipe pool per meal | 2 |
| `dashboard/household.py` | `household.json` validation, saving, backups, recovery | 2 |
| `examples/household.example.json` | Placeholder household that demonstrates every field | 2 |
| `dashboard/geocode.py` | Place search for the wizard | 3 |
| `dashboard/weather.py`, `dashboard/alerts.py` | Take place and unit from the household | 3 |
| `dashboard/api.py` | Household routes, generic meal slots | 4 |
| `server.py` | Data folder wiring, port fallback | 5 |
| `packs/*.json`, `scripts/check_links.py` | Four starter packs and the link checker | 6 |
| `web/household.js` | Dashboard meal sections, module switches, scaling, and (Task 8) the editors and Settings tabs | 7, 8 |
| `web/wizard.js` | First-run and re-run setup wizard | 9 |
| `web/index.html`, `web/app.js`, `web/app.css`, `web/plans.js` | Small edits through patch scripts | 7, 8, 9 |
| `launcher.py` | What the installed app runs | 11 |
| `packaging/*` | PyInstaller spec, Inno Setup script, build and smoke-test scripts | 12 |
| `README.md`, `PRODUCT.md`, `docs/INSTALL.md` | Documentation | 13 |

Task order: 0, then 1 to 3 (independent), 4, 5, 6, then the browser work 7 to 10 in order, then 11, 12, 13. Tasks 0 to 5, 7 to 9 and 11 were replayed in this order against a fresh copy of the source app and the whole test suite passed after each, and a PyInstaller build of the same code started, served its page and asked for first-run setup. The code in this plan comes from those verified files.

---


### Task 0: Start the repo from a data-free copy

**Goal:** The new repo holds a working copy of the single-household app with every household-specific content file left behind, and its tests pass.

**Files:**
- Create: `server.py`, `dashboard/`, `web/`, `scripts/`, `tests/`, `.gitignore` (copied)
- Do not copy: `content/`, `data/`, `docs/`, `start.bat`, `install_startup.ps1`, `README.md`, `PRODUCT.md`, `.git`, `tests/test_content_chores.py`, `tests/test_content_recipes.py`

**Acceptance Criteria:**
- [ ] No `content/` or `data/` folder exists in the new repo
- [ ] The two content tests are gone and the remaining suite passes
- [ ] `origin/main` contains the initial commit

**Verify:** `python -m unittest discover -s tests -t .` -> `Ran 316 tests ... OK (skipped=2)`

**Steps:**

- [ ] **Step 1: Confirm where you are**

```bash
cd /c/Users/shado/Claude/Household-Dashboard
git remote -v
git status --short
```

Expected: `origin` is `https://github.com/JadenStareye/Household-Dashboard.git`, and only `docs/` is untracked or committed (the plan and spec).

- [ ] **Step 2: Copy the app (read-only source)**

```bash
SRC=/c/Users/shado/Claude/home-dashboard
cp "$SRC/server.py" .
cp -r "$SRC/dashboard" "$SRC/web" "$SRC/scripts" "$SRC/tests" .
find . -name __pycache__ -type d -prune -exec rm -rf {} +
rm tests/test_content_chores.py tests/test_content_recipes.py
```

`scripts/check_links.py` still points at the old recipe file; Task 6 replaces it. `server.py` still reads `content/`; Task 5 replaces that. Do not run the server yet.

- [ ] **Step 3: Write `.gitignore`**

```text
data/
__pycache__/
*.pyc
.superpowers/
.impeccable/
.demo-data/
build/
dist/
.venv*/
```

- [ ] **Step 4: Run the baseline**

Run: `python -m unittest discover -s tests -t .`
Expected: `Ran 316 tests in ...s` then `OK (skipped=2)`.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: start from the single-household dashboard, minus household data"
```

- [ ] **Step 6: Push**

```bash
git push -u origin main
```

---

### Task 1: Cleaning plan generator

**Goal:** A pure function turns a household's rooms and a minutes goal into a Monday to Friday cleaning rotation with a per-day summary and warnings.

**Files:**
- Create: `dashboard/chores_gen.py`
- Test: `tests/test_chores_gen.py`

**Acceptance Criteria:**
- [ ] Rotation uses only Monday to Friday, one day per rule
- [ ] Low-use rooms get a single light-touch task
- [ ] Every room lands on exactly one day and load is balanced (busiest and lightest day differ by at most 12 minutes for a typical home)
- [ ] An overloaded week produces a plain-language warning
- [ ] Rule ids are unique and start with `gen-`; the same rooms always give the same rotation

**Verify:** `python -m unittest tests.test_chores_gen -v` -> 12 tests OK

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_chores_gen.py`:

```python
import unittest

from dashboard import chores_gen

HOME = [
    {"name": "Kitchen", "kind": "kitchen", "usage": "high"},
    {"name": "Primary bedroom", "kind": "bedroom", "usage": "high"},
    {"name": "Main bath", "kind": "bathroom", "usage": "high"},
    {"name": "Guest bath", "kind": "bathroom", "usage": "high"},
    {"name": "Living room", "kind": "living", "usage": "high"},
    {"name": "Office", "kind": "office", "usage": "low"},
    {"name": "Guest room", "kind": "bedroom", "usage": "low"},
]


class GenerateTests(unittest.TestCase):
    def test_only_weekdays_are_used(self):
        for rule in chores_gen.generate(HOME)["rules"]:
            self.assertEqual(rule["repeat"], "weekly")
            self.assertTrue(set(rule["days"]) <= set(chores_gen.WEEKDAYS))
            self.assertEqual(len(rule["days"]), 1)

    def test_tasks_are_titled_with_the_room_name(self):
        titles = [r["title"] for r in chores_gen.generate(HOME)["rules"]]
        self.assertIn("Kitchen: sweep and mop floor", titles)
        self.assertIn("Guest room: dust and vacuum", titles)

    def test_low_use_rooms_get_a_light_touch(self):
        rules = chores_gen.generate([{"name": "Spare", "kind": "kitchen", "usage": "low"}])["rules"]
        self.assertEqual([r["title"] for r in rules], ["Spare: wipe counters and sink"])

    def test_every_room_lands_on_exactly_one_day(self):
        result = chores_gen.generate(HOME)
        placed = [name for day in result["days"] for name in day["rooms"]]
        self.assertCountEqual(placed, [room["name"] for room in HOME])

    def test_load_is_balanced_across_the_week(self):
        minutes = [day["minutes"] for day in chores_gen.generate(HOME)["days"]]
        self.assertLessEqual(max(minutes) - min(minutes), 12)
        self.assertEqual(sum(minutes), 28 + 26 + 24 + 24 + 24 + 5 + 10)

    def test_normal_home_has_no_warnings(self):
        self.assertEqual(chores_gen.generate(HOME, 30)["warnings"], [])

    def test_overloaded_week_warns_in_plain_words(self):
        rooms = [{"name": f"Bath {i}", "kind": "bathroom", "usage": "high"} for i in range(10)]
        warnings = chores_gen.generate(rooms, 30)["warnings"]
        self.assertTrue(warnings)
        self.assertIn("minutes", warnings[0])

    def test_no_rooms_means_no_rules(self):
        result = chores_gen.generate([])
        self.assertEqual(result["rules"], [])
        self.assertEqual([d["minutes"] for d in result["days"]], [0, 0, 0, 0, 0])

    def test_one_room_goes_on_monday(self):
        result = chores_gen.generate([{"name": "Kitchen", "kind": "kitchen", "usage": "high"}])
        self.assertEqual(result["days"][0]["rooms"], ["Kitchen"])

    def test_rule_ids_are_unique_and_marked_generated(self):
        ids = [r["id"] for r in chores_gen.generate(HOME)["rules"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith("gen-") for i in ids))

    def test_same_rooms_give_the_same_rotation(self):
        self.assertEqual(chores_gen.generate(HOME), chores_gen.generate(HOME))

    def test_kind_choices_cover_every_kind(self):
        self.assertEqual({c["kind"] for c in chores_gen.kind_choices()}, set(chores_gen.ROOM_KINDS))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_chores_gen`
Expected: `ImportError` / `ModuleNotFoundError: cannot import name 'chores_gen'`.

- [ ] **Step 3: Implement**

Create `dashboard/chores_gen.py`:

```python
"""Builds a Monday-to-Friday cleaning rotation from a household's rooms."""

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"]
DAY_NAMES = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday"}
OVER_BY = 10  # a day may run this many minutes past the goal before we warn

# kind -> (label, full clean, light touch for low-use rooms); each task is (text, minutes)
ROOM_KINDS = {
    "kitchen": ("Kitchen",
                [("wipe counters and sink", 8), ("clean stovetop and microwave", 8), ("sweep and mop floor", 12)],
                [("wipe counters and sink", 8)]),
    "bathroom": ("Bathroom",
                 [("scrub tub or shower and toilet", 12), ("wipe sink and mirror", 6), ("mop floor", 6)],
                 [("quick wipe-down", 8)]),
    "bedroom": ("Bedroom",
                [("dust surfaces", 6), ("vacuum floor", 8), ("change sheets and start laundry", 12)],
                [("dust and vacuum", 10)]),
    "living": ("Living area",
               [("dust and wipe surfaces", 8), ("vacuum", 10), ("tidy up", 6)],
               [("dust and vacuum", 10)]),
    "office": ("Office", [("dust surfaces", 5), ("vacuum floor", 7)], [("quick dust", 5)]),
    "other": ("Other room", [("dust surfaces", 5), ("vacuum floor", 7)], [("quick dust", 5)]),
}


def kind_choices():
    return [{"kind": kind, "label": spec[0]} for kind, spec in ROOM_KINDS.items()]


def _tasks_for(room):
    _, full, light = ROOM_KINDS[room["kind"]]
    return light if room["usage"] == "low" else full


def generate(rooms, target_minutes=30):
    """Spread rooms over Mon-Fri, biggest first, always onto the lightest day.

    Returns {"rules": [...], "days": [{"day", "rooms", "minutes"}], "warnings": [...]}.
    Rule ids are 'gen-<room>-<task>' so a later regenerate can replace exactly these.
    """
    load = {day: 0 for day in WEEKDAYS}
    placed = {day: [] for day in WEEKDAYS}
    sized = [(sum(m for _, m in _tasks_for(room)), index, room) for index, room in enumerate(rooms)]
    for minutes, index, room in sorted(sized, key=lambda item: (-item[0], item[1])):
        day = min(WEEKDAYS, key=lambda d: (load[d], WEEKDAYS.index(d)))
        load[day] += minutes
        placed[day].append((index, room))
    rules = []
    for day in WEEKDAYS:
        for index, room in sorted(placed[day], key=lambda item: item[0]):
            for step, (text, _) in enumerate(_tasks_for(room), start=1):
                rules.append({"id": f"gen-{index + 1}-{step}", "title": f"{room['name']}: {text}",
                              "repeat": "weekly", "days": [day]})
    days = [{"day": day, "rooms": [room["name"] for _, room in sorted(placed[day], key=lambda i: i[0])], "minutes": load[day]}
            for day in WEEKDAYS]
    warnings = [f"{DAY_NAMES[d['day']]} is about {d['minutes']} minutes, over your {target_minutes}-minute goal. "
                "Remove a room or raise the goal." for d in days if d["minutes"] > target_minutes + OVER_BY]
    return {"rules": rules, "days": days, "warnings": warnings}
```

- [ ] **Step 4: Run the tests**

Run: `python -m unittest tests.test_chores_gen -v`
Expected: `Ran 12 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/chores_gen.py tests/test_chores_gen.py
git commit -m "feat: generate a weekday cleaning rotation from rooms"
```

---

### Task 2: Household config, packs loader, paths

**Goal:** Validated household configuration with atomic saving, backups and recovery; a starter-pack loader that builds each meal's recipe pool; the data-folder helper; and a placeholder example household.

**Files:**
- Create: `dashboard/paths.py`, `dashboard/packs.py`, `dashboard/household.py`, `examples/household.example.json`
- Modify: `dashboard/store.py` (adds shared `atomic_write_json`)
- Test: `tests/test_packs.py`, `tests/test_household.py`, `tests/test_examples.py`

**Acceptance Criteria:**
- [ ] `household.validate` returns a clean household or raises `ValueError` with a plain message; validating its own output changes nothing
- [ ] A missing `household.json` reads as `None` (first run); a corrupt or invalid one falls back to the newest valid backup; only the newest 10 backups are kept
- [ ] A meal's pool is the recipes of its packs carrying every chosen tag plus all of the household's own recipes
- [ ] Starter-pack recipe ids are namespaced `<pack>.<recipe>`; broken pack files are skipped, never fatal
- [ ] `store.py` keeps its behavior (existing `test_store` still passes)
- [ ] `examples/household.example.json` validates unchanged

**Verify:** `python -m unittest tests.test_packs tests.test_household tests.test_examples tests.test_store` -> OK

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_packs.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import packs


def recipe(rid="a", **extra):
    base = {"id": rid, "name": "Pasta", "url": "https://example.com/pasta", "minutes": 20, "tags": ["quick"]}
    return {**base, **extra}


def pack(pid="quick", recipes=None, **extra):
    return {"id": pid, "name": "Quick meals", "description": "Fast", "recipes": recipes if recipes is not None else [recipe()], **extra}


class CleanRecipeTests(unittest.TestCase):
    def test_accepts_a_good_recipe(self):
        self.assertEqual(packs.clean_recipe(recipe(), "p.a"),
                         {"id": "p.a", "name": "Pasta", "url": "https://example.com/pasta", "minutes": 20, "tags": ["quick"]})

    def test_minutes_and_tags_are_optional(self):
        got = packs.clean_recipe({"name": "Soup", "url": "http://x.co/s"}, "own-1")
        self.assertEqual((got["minutes"], got["tags"]), (None, []))

    def test_rejects_bad_input(self):
        for bad in (recipe(name=" "), recipe(url="javascript:alert(1)"), recipe(url="pasta.com"), recipe(minutes=0),
                    recipe(minutes="20"), recipe(minutes=True), recipe(tags=["spicy"]), recipe(tags="quick"), "nope"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                packs.clean_recipe(bad, "p.a")


class ParsePackTests(unittest.TestCase):
    def test_recipe_ids_are_namespaced_by_pack(self):
        self.assertEqual(packs.parse_pack(pack())["recipes"][0]["id"], "quick.a")

    def test_rejects_duplicate_recipe_ids_and_bad_pack_ids(self):
        with self.assertRaises(ValueError):
            packs.parse_pack(pack(recipes=[recipe("a"), recipe("a")]))
        with self.assertRaises(ValueError):
            packs.parse_pack(pack("Bad Id"))


class LoadPacksTests(unittest.TestCase):
    def test_loads_good_packs_sorted_and_skips_broken_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "b.json").write_text(json.dumps(pack("b", name="Zebra")), encoding="utf-8")
            Path(tmp, "a.json").write_text(json.dumps(pack("a", name="Apple")), encoding="utf-8")
            Path(tmp, "broken.json").write_text("{not json", encoding="utf-8")
            Path(tmp, "bad.json").write_text(json.dumps({"id": "x"}), encoding="utf-8")
            self.assertEqual([p["id"] for p in packs.load_packs(tmp)], ["a", "b"])

    def test_missing_directory_gives_no_packs(self):
        self.assertEqual(packs.load_packs(Path(tempfile.gettempdir()) / "no-such-packs-dir"), [])


class SlotRecipesTests(unittest.TestCase):
    def setUp(self):
        self.packs = {
            "p": packs.parse_pack(pack("p", recipes=[recipe("a", tags=["quick", "vegetarian"]), recipe("b", tags=["quick"])])),
            "q": packs.parse_pack(pack("q", recipes=[recipe("c", tags=["vegetarian"])])),
        }
        self.own = packs.clean_recipe({"name": "Gran's stew", "url": "https://e.com/s"}, "own-00000001")

    def ids(self, slot):
        return [r["id"] for r in packs.slot_recipes(slot, self.packs)]

    def test_pools_every_chosen_pack(self):
        self.assertEqual(self.ids({"packIds": ["p", "q"]}), ["p.a", "p.b", "q.c"])

    def test_tag_filter_requires_every_chosen_tag(self):
        self.assertEqual(self.ids({"packIds": ["p", "q"], "tagFilter": ["vegetarian"]}), ["p.a", "q.c"])
        self.assertEqual(self.ids({"packIds": ["p", "q"], "tagFilter": ["vegetarian", "quick"]}), ["p.a"])

    def test_own_recipes_are_always_included(self):
        self.assertEqual(self.ids({"packIds": ["p"], "tagFilter": ["vegetarian"], "ownRecipes": [self.own]}), ["p.a", "own-00000001"])

    def test_unknown_pack_is_ignored(self):
        self.assertEqual(self.ids({"packIds": ["gone"]}), [])


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_household.py`:

```python
import copy
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import household
from dashboard.household import ConfigStore, validate

GOOD = {
    "name": "Sample Household",
    "location": {"label": "Portland, Oregon", "lat": 45.52, "lon": -122.68, "alerts": True},
    "units": {"temperature": "F"},
    "modules": {"weather": True, "tasks": True, "plans": False},
    "rooms": [{"name": "Kitchen", "kind": "kitchen", "usage": "high"}],
    "choreMinutes": 30,
    "mealSlots": [{"name": "Dinner", "packIds": ["quick"], "tagFilter": ["quick"]}],
}


def bad(**changes):
    raw = copy.deepcopy(GOOD)
    raw.update(changes)
    return raw


class ValidateTests(unittest.TestCase):
    def test_fills_in_defaults_and_ids(self):
        got = validate(GOOD)
        self.assertEqual(got["schemaVersion"], 1)
        self.assertEqual(got["modules"], {"weather": True, "tasks": True, "plans": False, "shopping": True, "timers": True})
        slot = got["mealSlots"][0]
        self.assertEqual((slot["id"], slot["enabled"], slot["ownRecipes"]), ("dinner", True, []))

    def test_validating_twice_changes_nothing(self):
        once = validate(GOOD)
        self.assertEqual(validate(once), once)

    def test_slot_ids_are_unique_slugs(self):
        raw = bad(mealSlots=[{"name": "Kid's Snacks"}, {"name": "Kid's snacks"}, {"name": "!!!"}])
        self.assertEqual([s["id"] for s in validate(raw)["mealSlots"]], ["kid-s-snacks", "kid-s-snacks-2", "meals"])

    def test_rejects_bad_input_with_a_readable_message(self):
        cases = [
            bad(name="  "),
            bad(location=None),
            bad(location={"label": "X", "lat": 99, "lon": 0}),
            bad(location={"label": "X", "lat": 0, "lon": "1"}),
            bad(units={"temperature": "K"}),
            bad(choreMinutes=5),
            bad(choreMinutes=True),
            bad(rooms=[{"name": "A", "kind": "castle", "usage": "high"}]),
            bad(rooms=[{"name": "A", "kind": "kitchen", "usage": "medium"}]),
            bad(rooms=[{"name": "A", "kind": "kitchen", "usage": "high"}, {"name": "a", "kind": "other", "usage": "low"}]),
            bad(mealSlots=[{"name": ""}]),
            bad(mealSlots=[{"name": "D", "tagFilter": ["spicy"]}]),
            bad(mealSlots=[{"name": "D", "ownRecipes": [{"name": "X", "url": "ftp://x"}]}]),
            bad(mealSlots=[{"name": f"M{i}"} for i in range(7)]),
            "nope",
        ]
        for raw in cases:
            with self.assertRaises(ValueError, msg=repr(raw)):
                validate(raw)

    def test_known_pack_ids_are_enforced_only_when_given(self):
        validate(GOOD)
        validate(GOOD, known_pack_ids={"quick"})
        with self.assertRaises(ValueError):
            validate(GOOD, known_pack_ids={"other"})

    def test_own_recipes_get_stable_ids(self):
        raw = bad(mealSlots=[{"name": "Dinner", "ownRecipes": [{"name": "Stew", "url": "https://e.com/s"}]}])
        first = validate(raw)
        rid = first["mealSlots"][0]["ownRecipes"][0]["id"]
        self.assertRegex(rid, r"own-[0-9a-f]{8}")
        self.assertEqual(validate(first)["mealSlots"][0]["ownRecipes"][0]["id"], rid)


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = ConfigStore(self.dir / "household.json")

    def test_first_run_has_no_household(self):
        self.assertIsNone(self.store.load())

    def test_save_then_load_round_trips(self):
        self.store.save(validate(GOOD))
        self.assertEqual(self.store.load(), validate(GOOD))

    def test_corrupt_file_falls_back_to_the_last_backup(self):
        self.store.save(validate(GOOD))
        second = validate(bad(name="Second"))
        self.store.save(second)
        (self.dir / "household.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(self.store.load()["name"], "Sample Household")

    def test_invalid_but_parseable_file_also_falls_back(self):
        self.store.save(validate(GOOD))
        self.store.save(validate(bad(name="Second")))
        (self.dir / "household.json").write_text(json.dumps({"name": ""}), encoding="utf-8")
        self.assertEqual(self.store.load()["name"], "Sample Household")

    def test_only_the_newest_backups_are_kept(self):
        store = ConfigStore(self.dir / "household.json", keep=3)
        for i in range(8):
            store.save(validate(bad(name=f"Home {i}")))
        self.assertEqual(len(list((self.dir / "backups").glob("household-*.json"))), 3)

    def test_module_list_matches_what_the_dashboard_can_hide(self):
        self.assertEqual(household.MODULES, ("weather", "tasks", "plans", "shopping", "timers"))


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_examples.py`:

```python
import json
import unittest
from pathlib import Path

from dashboard import household

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "household.example.json"


class ExampleHouseholdTests(unittest.TestCase):
    def test_the_example_is_a_valid_household_that_validation_leaves_unchanged(self):
        raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(household.validate(raw), raw)

    def test_the_example_uses_placeholder_names_only(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("Sample Household", text)
        self.assertIn("example.com", text)
```

- [ ] **Step 2: Create the placeholder household**

Create `examples/household.example.json`:

```json
{
  "schemaVersion": 1,
  "name": "Sample Household",
  "location": {
    "label": "Portland, Oregon, United States",
    "lat": 45.52345,
    "lon": -122.67621,
    "alerts": true
  },
  "units": {
    "temperature": "F"
  },
  "modules": {
    "weather": true,
    "tasks": true,
    "plans": true,
    "shopping": true,
    "timers": true
  },
  "rooms": [
    {"name": "Kitchen", "kind": "kitchen", "usage": "high"},
    {"name": "Primary bedroom", "kind": "bedroom", "usage": "high"},
    {"name": "Bathroom", "kind": "bathroom", "usage": "high"},
    {"name": "Living room", "kind": "living", "usage": "high"},
    {"name": "Office", "kind": "office", "usage": "low"}
  ],
  "choreMinutes": 30,
  "mealSlots": [
    {
      "id": "dinner",
      "name": "Dinner",
      "enabled": true,
      "packIds": ["family-classics"],
      "tagFilter": [],
      "ownRecipes": []
    },
    {
      "id": "lunch",
      "name": "Lunch",
      "enabled": true,
      "packIds": ["quick-weeknight"],
      "tagFilter": ["vegetarian"],
      "ownRecipes": [
        {"id": "own-00000001", "name": "Gran's tomato soup", "url": "https://example.com/tomato-soup", "minutes": 30, "tags": ["vegetarian"]}
      ]
    }
  ]
}
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `python -m unittest tests.test_packs tests.test_household tests.test_examples`
Expected: import errors (`packs`, `household` do not exist).

- [ ] **Step 4: Implement**

Create `dashboard/paths.py`:

```python
import os
import sys
from pathlib import Path


def resource_root():
    """Folder that holds the bundled web/ and packs/ (the PyInstaller bundle when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def data_dir():
    """Where a household's own files live; reinstalling the app never touches it."""
    override = os.environ.get("HOME_DASHBOARD_DATA")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "HomeDashboard"
    return Path.home() / ".home-dashboard"
```

Replace the whole of `dashboard/store.py` (same behavior; the temp-file-then-rename write becomes a reusable function):

```python
import json
import os
import shutil
import tempfile
from pathlib import Path


def atomic_write_json(path, data):
    """Write JSON to a temp file beside `path`, then rename it into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Store:
    def __init__(self, path, backup_dir=None, keep=14):
        self.path = Path(path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.path.parent / "backups"
        self.keep = keep

    def load(self):
        if not self.path.exists():
            return self._recover()
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._recover()

    def _recover(self):
        if not self.backup_dir.exists():
            return {}
        for candidate in sorted(self.backup_dir.glob("data-*.json"), reverse=True):
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
        return {}

    def save(self, data):
        atomic_write_json(self.path, data)

    def backup(self, today):
        if not self.path.exists():
            return
        try:
            json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        dest = self.backup_dir / f"data-{today.isoformat()}.json"
        if not dest.exists():
            shutil.copyfile(self.path, dest)
        for old in sorted(self.backup_dir.glob("data-*.json"))[: -self.keep]:
            old.unlink()
```

Create `dashboard/packs.py`:

```python
import json
import re
from pathlib import Path

TAGS = ("vegetarian", "vegan", "low-carb", "gluten-free", "dairy-free", "quick", "family-friendly", "one-pan", "slow-cooker")
_ID = re.compile(r"[a-z0-9][a-z0-9-]*")


def clean_recipe(raw, recipe_id):
    """Normalise one recipe (from a pack or typed in by the household); raise ValueError if unusable."""
    if not isinstance(raw, dict):
        raise ValueError("Recipe must be an object")
    name = raw.get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > 100:
        raise ValueError("Give the recipe a name (100 characters max)")
    url = raw.get("url")
    url = url.strip() if isinstance(url, str) else ""
    if not re.match(r"https?://\S+$", url) or len(url) > 500:
        raise ValueError("The recipe link must start with http:// or https://")
    minutes = raw.get("minutes")
    if minutes is not None:
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 600:
            raise ValueError("Minutes must be a whole number from 1 to 600")
    tags = raw.get("tags", [])
    if not isinstance(tags, list) or any(t not in TAGS for t in tags):
        raise ValueError("Unknown recipe tag")
    return {"id": recipe_id, "name": name, "url": url, "minutes": minutes, "tags": [t for t in TAGS if t in tags]}


def parse_pack(raw):
    """Validate a starter pack and namespace its recipe ids as '<pack>.<recipe>'."""
    if not isinstance(raw, dict):
        raise ValueError("Pack must be an object")
    pack_id, name = raw.get("id"), raw.get("name")
    if not isinstance(pack_id, str) or not _ID.fullmatch(pack_id):
        raise ValueError("Pack needs a lowercase id")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Pack needs a name")
    recipes, seen = [], set()
    for item in raw.get("recipes", []):
        local = item.get("id") if isinstance(item, dict) else None
        if not isinstance(local, str) or not _ID.fullmatch(local) or local in seen:
            raise ValueError(f"Bad or duplicate recipe id in pack {pack_id}")
        seen.add(local)
        recipes.append(clean_recipe(item, f"{pack_id}.{local}"))
    description = raw.get("description")
    return {"id": pack_id, "name": name.strip(), "description": description.strip() if isinstance(description, str) else "", "recipes": recipes}


def load_packs(directory):
    """Every readable pack in `directory`, by name. A broken file is skipped, never fatal."""
    found = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            found.append(parse_pack(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return sorted(found, key=lambda p: p["name"].lower())


def slot_recipes(slot, packs_by_id):
    """A meal slot's pool: recipes from its packs that carry every chosen tag, plus the household's own."""
    wanted = set(slot.get("tagFilter", []))
    pool, seen = [], set()
    for pack_id in slot.get("packIds", []):
        for recipe in packs_by_id.get(pack_id, {}).get("recipes", []):
            if wanted <= set(recipe["tags"]) and recipe["id"] not in seen:
                seen.add(recipe["id"])
                pool.append(recipe)
    for recipe in slot.get("ownRecipes", []):
        if recipe["id"] not in seen:
            seen.add(recipe["id"])
            pool.append(recipe)
    return pool
```

Create `dashboard/household.py`:

```python
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from dashboard import chores_gen, packs as packs_mod
from dashboard.store import atomic_write_json

SCHEMA_VERSION = 1
MODULES = ("weather", "tasks", "plans", "shopping", "timers")
MAX_ROOMS, MAX_SLOTS, MAX_OWN = 20, 6, 100


def _text(value, message, limit):
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > limit:
        raise ValueError(f"{message} (up to {limit} characters)")
    return text


def _number(value, low, high, message):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ValueError(message)
    return float(value)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "meals"


def clean_location(raw):
    if not isinstance(raw, dict):
        raise ValueError("Choose where you live so we can show your weather")
    return {
        "label": _text(raw.get("label"), "Enter a place name", 100),
        "lat": _number(raw.get("lat"), -90, 90, "Latitude must be between -90 and 90"),
        "lon": _number(raw.get("lon"), -180, 180, "Longitude must be between -180 and 180"),
        "alerts": bool(raw.get("alerts", False)),
    }


def clean_rooms(raw):
    if not isinstance(raw, list) or len(raw) > MAX_ROOMS:
        raise ValueError(f"Add up to {MAX_ROOMS} rooms")
    rooms, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each room needs a name and a type")
        name = _text(item.get("name"), "Give each room a name", 40)
        if name.lower() in seen:
            raise ValueError("Each room needs its own name")
        seen.add(name.lower())
        if item.get("kind") not in chores_gen.ROOM_KINDS:
            raise ValueError("Pick a type for each room")
        if item.get("usage") not in ("high", "low"):
            raise ValueError("Say whether each room is used a lot or a little")
        rooms.append({"name": name, "kind": item["kind"], "usage": item["usage"]})
    return rooms


def _own_recipes(raw):
    if not isinstance(raw, list) or len(raw) > MAX_OWN:
        raise ValueError(f"Add up to {MAX_OWN} of your own recipes per meal")
    out = []
    for item in raw:
        given = item.get("id") if isinstance(item, dict) else None
        rid = given if isinstance(given, str) and re.fullmatch(r"own-[0-9a-f]{8}", given) else f"own-{uuid.uuid4().hex[:8]}"
        out.append(packs_mod.clean_recipe(item, rid))
    return out


def clean_slots(raw, known_pack_ids=None):
    if not isinstance(raw, list) or len(raw) > MAX_SLOTS:
        raise ValueError(f"Add up to {MAX_SLOTS} meals")
    slots, used = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each meal needs a name")
        name = _text(item.get("name"), "Give each meal a name", 40)
        given = item.get("id")
        wanted = given if isinstance(given, str) and re.fullmatch(r"[a-z0-9-]+", given) else slugify(name)
        slot_id, n = wanted, 2
        while slot_id in used:
            slot_id, n = f"{wanted}-{n}", n + 1
        used.add(slot_id)
        pack_ids = item.get("packIds", [])
        if not isinstance(pack_ids, list) or not all(isinstance(p, str) for p in pack_ids):
            raise ValueError("Pick recipe packs from the list")
        if known_pack_ids is not None and not set(pack_ids) <= set(known_pack_ids):
            raise ValueError("That recipe pack is not available")
        tag_filter = item.get("tagFilter", [])
        if not isinstance(tag_filter, list) or any(t not in packs_mod.TAGS for t in tag_filter):
            raise ValueError("Pick tags from the list")
        slots.append({
            "id": slot_id, "name": name, "enabled": bool(item.get("enabled", True)),
            "packIds": list(dict.fromkeys(pack_ids)),
            "tagFilter": [t for t in packs_mod.TAGS if t in tag_filter],
            "ownRecipes": _own_recipes(item.get("ownRecipes", [])),
        })
    return slots


def clean_minutes(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 10 <= value <= 120:
        raise ValueError("Cleaning minutes per day must be from 10 to 120")
    return value


def validate(raw, known_pack_ids=None):
    """Turn whatever the browser sent into a clean household, or raise ValueError with a plain message."""
    if not isinstance(raw, dict):
        raise ValueError("Household settings must be an object")
    units = raw.get("units") if isinstance(raw.get("units"), dict) else {}
    temperature = units.get("temperature", "F")
    if temperature not in ("F", "C"):
        raise ValueError("Choose Fahrenheit or Celsius")
    modules = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "name": _text(raw.get("name"), "Enter a name for your household", 60),
        "location": clean_location(raw.get("location")),
        "units": {"temperature": temperature},
        "modules": {m: bool(modules.get(m, True)) for m in MODULES},
        "rooms": clean_rooms(raw.get("rooms", [])),
        "choreMinutes": clean_minutes(raw.get("choreMinutes", 30)),
        "mealSlots": clean_slots(raw.get("mealSlots", []), known_pack_ids),
    }


class ConfigStore:
    """household.json: atomic saves, a few rolling backups, and recovery from them."""

    def __init__(self, path, backup_dir=None, keep=10):
        self.path = Path(path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.path.parent / "backups"
        self.keep = keep

    def _read(self, path):
        try:
            return validate(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    def load(self):
        """The saved household, or None when there is none yet (first run)."""
        found = self._read(self.path) if self.path.exists() else None
        if found is None and self.backup_dir.exists():
            for candidate in sorted(self.backup_dir.glob("household-*.json"), reverse=True):
                found = self._read(candidate)
                if found is not None:
                    break
        return found

    def save(self, household):
        if self.path.exists() and self._read(self.path) is not None:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            (self.backup_dir / f"household-{stamp}.json").write_bytes(self.path.read_bytes())
            for old in sorted(self.backup_dir.glob("household-*.json"))[: -self.keep]:
                old.unlink()
        atomic_write_json(self.path, household)
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_packs tests.test_household tests.test_examples tests.test_store -v`
Expected: all OK. Then the full suite: `python -m unittest discover -s tests -t .` -> OK.

- [ ] **Step 6: Commit**

```bash
git add dashboard/paths.py dashboard/store.py dashboard/packs.py dashboard/household.py examples tests/test_packs.py tests/test_household.py tests/test_examples.py
git commit -m "feat: household config, starter pack loader and data folder helper"
```

---

### Task 3: Place search and configurable weather/alerts

**Goal:** Weather and alerts use the household's chosen place and unit instead of fixed coordinates, and a geocoder can turn a typed town or ZIP code into coordinates.

**Files:**
- Create: `dashboard/geocode.py`
- Modify: `dashboard/weather.py`, `dashboard/alerts.py` (through a patch script)
- Test: `tests/test_geocode.py`, `tests/test_locations.py`

**Acceptance Criteria:**
- [ ] Forecast and air-quality URLs use the chosen latitude and longitude, `timezone=auto`, and Fahrenheit or Celsius
- [ ] `WeatherService.set_location` clears the cached forecast and the output carries `unit`
- [ ] With no location the real fetch reports `{available: False}` instead of crashing
- [ ] Alerts run only for a place that opted in (`alerts: true`); `set_location` forgets old alerts
- [ ] Geocoder parsing tolerates junk and skips rows without coordinates; network errors propagate

**Verify:** `python -m unittest tests.test_geocode tests.test_locations tests.test_weather tests.test_alerts` -> OK

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_geocode.py`:

```python
import unittest

from dashboard import geocode

SAMPLE = {"results": [
    {"name": "Portland", "admin1": "Oregon", "country": "United States", "country_code": "US", "latitude": 45.52, "longitude": -122.68},
    {"name": "Singapore", "admin1": "Singapore", "country": "Singapore", "country_code": "SG", "latitude": 1.29, "longitude": 103.85},
    {"name": "No coordinates", "country": "Nowhere"},
]}


class GeocodeTests(unittest.TestCase):
    def test_parse_builds_readable_labels_and_skips_bad_rows(self):
        self.assertEqual(geocode.parse(SAMPLE), [
            {"label": "Portland, Oregon, United States", "lat": 45.52, "lon": -122.68, "countryCode": "US"},
            {"label": "Singapore", "lat": 1.29, "lon": 103.85, "countryCode": "SG"},
        ])

    def test_parse_survives_junk(self):
        for junk in (None, {}, {"results": None}, {"results": "x"}, [], {"results": [5, None]}):
            self.assertEqual(geocode.parse(junk), [])

    def test_search_passes_the_trimmed_query_and_skips_tiny_ones(self):
        seen = []
        self.assertEqual(geocode.search("  Portland ", fetch=lambda q: seen.append(q) or SAMPLE)[0]["countryCode"], "US")
        self.assertEqual(seen, ["Portland"])
        self.assertEqual(geocode.search(" p ", fetch=lambda q: seen.append(q) or SAMPLE), [])
        self.assertEqual(seen, ["Portland"])

    def test_search_lets_network_errors_through(self):
        def offline(query):
            raise OSError("offline")

        with self.assertRaises(OSError):
            geocode.search("Portland", fetch=offline)


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_locations.py`:

```python
import unittest
from datetime import datetime, timezone

from dashboard import alerts, weather

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc).timestamp()
PLACE = {"label": "Portland, Oregon", "lat": 45.52, "lon": -122.68, "alerts": True}


class WeatherLocationTests(unittest.TestCase):
    def test_without_a_location_the_real_fetch_is_unavailable_not_a_crash(self):
        self.assertEqual(weather.WeatherService().get(), {"available": False})

    def test_urls_use_the_chosen_place_unit_and_automatic_timezone(self):
        urls = []
        original = weather._get_json
        weather._get_json = lambda url: urls.append(url) or {}
        self.addCleanup(setattr, weather, "_get_json", original)
        weather._http_fetch(PLACE, "C")
        self.assertIn("latitude=45.52&longitude=-122.68", urls[0])
        self.assertIn("temperature_unit=celsius", urls[0])
        self.assertIn("timezone=auto", urls[0])
        self.assertIn("latitude=45.52&longitude=-122.68", urls[1])
        weather._http_fetch(PLACE, "F")
        self.assertIn("temperature_unit=fahrenheit", urls[2])

    def test_set_location_clears_the_cached_forecast_and_reports_the_unit(self):
        calls = []
        svc = weather.WeatherService(fetch=lambda: calls.append(1) or SAMPLE, ttl=1800)
        svc.get()
        svc.set_location(PLACE, "C")
        out = svc.get()
        self.assertEqual(len(calls), 2)
        self.assertEqual(out["unit"], "C")


class AlertLocationTests(unittest.TestCase):
    def test_off_by_default_and_for_places_that_did_not_opt_in(self):
        svc = alerts.AlertService()
        self.assertEqual(svc.get(), [])
        svc.set_location({**PLACE, "alerts": False})
        self.assertEqual(svc.get(), [])
        self.assertFalse(svc.fresh)

    def test_url_points_at_the_chosen_place(self):
        self.assertEqual(alerts.URL.format(lat=45.52, lon=-122.68), "https://api.weather.gov/alerts/active?point=45.5200,-122.6800")

    def test_set_location_forgets_old_alerts(self):
        feature = {"properties": {"id": "urn:1", "event": "Tornado Warning", "status": "Actual", "messageType": "Alert",
                                  "ends": "2026-10-08T14:00:00-05:00", "expires": "2026-10-08T14:00:00-05:00",
                                  "headline": "h", "areaDesc": "Somewhere"}}
        svc = alerts.AlertService(fetch=lambda: {"features": [feature]}, now=lambda: NOW)
        self.assertEqual(len(svc.get()), 1)
        svc.set_location(None)
        self.assertEqual(svc._cache, [])


SAMPLE = {
    "current": {"temperature_2m": 61.2, "weather_code": 0, "time": "2026-10-08T12:00"},
    "daily": {
        "time": ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"],
        "weather_code": [0, 1, 3, 61], "temperature_2m_max": [70, 71, 72, 73],
        "temperature_2m_min": [50, 51, 52, 53], "precipitation_probability_max": [0, 10, 20, 30],
        "sunrise": ["2026-10-08T07:00"] * 4, "sunset": ["2026-10-08T19:00"] * 4,
    },
}


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_geocode tests.test_locations`
Expected: `ModuleNotFoundError` for `geocode`, and failures in `test_locations`.

- [ ] **Step 3: Add the geocoder**

Create `dashboard/geocode.py`:

```python
import json
import urllib.parse
import urllib.request

URL = "https://geocoding-api.open-meteo.com/v1/search?name={name}&count=6&language=en&format=json"


def parse(payload):
    """Open-Meteo geocoding results -> [{label, lat, lon, countryCode}]."""
    places = []
    results = payload.get("results") if isinstance(payload, dict) else None
    for item in results if isinstance(results, list) else []:
        try:
            parts = [p for p in (item.get("name"), item.get("admin1"), item.get("country")) if isinstance(p, str) and p]
            label = ", ".join(dict.fromkeys(parts))
            lat, lon = float(item["latitude"]), float(item["longitude"])
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if label:
            places.append({"label": label, "lat": lat, "lon": lon, "countryCode": item.get("country_code") or ""})
    return places


def _http_fetch(query):
    url = URL.format(name=urllib.parse.quote(query))
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def search(query, fetch=_http_fetch):
    """Look up a city or postal code. Needs the internet; raises OSError or ValueError when it cannot."""
    query = query.strip()
    if len(query) < 2:
        return []
    return parse(fetch(query))
```

- [ ] **Step 4: Patch weather and alerts**

Save as `_patch_weather_alerts.py`, run `python _patch_weather_alerts.py`, then delete it:

```python
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


patch("dashboard/weather.py", [
    ('''URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=34.73&longitude=-86.59"
    "&current=temperature_2m,weather_code&hourly=precipitation_probability"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,sunrise,sunset"
    "&temperature_unit=fahrenheit&timezone=America%2FChicago&forecast_days=4"
)
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=34.73&longitude=-86.59&current=us_aqi"
''', '''FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,weather_code&hourly=precipitation_probability"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,sunrise,sunset"
    "&temperature_unit={unit}&timezone=auto&forecast_days=4"
)
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi"
'''),
    ('''def _http_fetch():
    payload = _get_json(URL)
    try:
        payload["air"] = _get_json(AIR_URL)
''', '''def _http_fetch(location, unit):
    where = {"lat": location["lat"], "lon": location["lon"]}
    payload = _get_json(FORECAST_URL.format(unit="celsius" if unit == "C" else "fahrenheit", **where))
    try:
        payload["air"] = _get_json(AIR_URL.format(**where))
'''),
    ('''    def __init__(self, fetch=None, now=time.time, ttl=1800):
        self._fetch = fetch or _http_fetch
        self._now = now
        self._ttl = ttl
        self._cache = None
        self._fetched_at = 0.0
''', '''    def __init__(self, fetch=None, now=time.time, ttl=1800, location=None, unit="F"):
        self._custom_fetch = fetch
        self._now = now
        self._ttl = ttl
        self._location = location
        self._unit = unit
        self._cache = None
        self._fetched_at = 0.0

    def set_location(self, location, unit="F"):
        """Point the service at a new place (or None) and forget the old forecast."""
        self._location, self._unit = location, unit
        self._cache = None
        self._fetched_at = 0.0

    def _fetch(self):
        if self._custom_fetch:
            return self._custom_fetch()
        if not self._location:
            raise ValueError("No location chosen yet")
        return _http_fetch(self._location, self._unit)
'''),
    ('''        return {**self._cache, "stale": stale, "updatedAt": updated}''',
     '''        return {**self._cache, "stale": stale, "updatedAt": updated, "unit": self._unit}'''),
])

patch("dashboard/alerts.py", [
    ('''URL = "https://api.weather.gov/alerts/active?point=34.73,-86.59"''',
     '''URL = "https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"'''),
    ('''def _http_fetch():
    request = urllib.request.Request(URL, headers=HEADERS)''',
     '''def _http_fetch(location):
    request = urllib.request.Request(URL.format(lat=location["lat"], lon=location["lon"]), headers=HEADERS)'''),
    ('''    def __init__(self, fetch=None, now=time.time, ttl=300):
        self._fetch = fetch or _http_fetch
        self._now = now''', '''    def __init__(self, fetch=None, now=time.time, ttl=300, location=None):
        self._custom_fetch = fetch
        self._location = location if location and location.get("alerts") else None
        self._now = now'''),
    ('''    def get(self):
        with self._lock:
            return self._get()

    def _get(self):
        current = self._now()
''', '''    def set_location(self, location):
        """Alerts come from the US National Weather Service, so they only run for a US place the household opted into."""
        with self._lock:
            self._location = location if location and location.get("alerts") else None
            self._cache = []
            self._fetched_at = None
            self._retry_at = 0.0
            self.fresh = False

    def _fetch(self):
        return self._custom_fetch() if self._custom_fetch else _http_fetch(self._location)

    def get(self):
        with self._lock:
            return self._get()

    def _get(self):
        if self._custom_fetch is None and self._location is None:
            self.fresh = False
            return []
        current = self._now()
'''),
])

print("weather and alerts patched")
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_geocode tests.test_locations tests.test_weather tests.test_alerts -v`
Expected: all OK (the existing weather and alert tests are unchanged and must still pass).

- [ ] **Step 6: Commit**

```bash
git add dashboard/geocode.py dashboard/weather.py dashboard/alerts.py tests/test_geocode.py tests/test_locations.py
git commit -m "feat: place search, and weather and alerts for the household's own place"
```

---

### Task 4: Household API and generic meal slots

**Goal:** The API can save and read a household, preview and rebuild the cleaning plan, search places, and serves dinners for any number of named meal slots instead of two fixed ones.

**Files:**
- Modify: `dashboard/api.py` (through a patch script), `tests/test_api.py` (rename fixtures, one assertion)
- Modify (rename only): `tests/test_dinners.py`, `tests/test_server.py`, `tests/test_web_assets.py`
- Test: `tests/test_household_api.py`

**Acceptance Criteria:**
- [ ] `GET /api/state` reports `needsSetup`, `household`, `slots`, and `dinners` keyed by slot id
- [ ] `PUT /api/household` validates, saves, rebuilds each meal's recipes, repoints weather and alerts, and deals dinners; bad input returns 400 and changes nothing
- [ ] With `regenerateChores`, generated rules (`gen-...`) and today's unfinished generated tasks are replaced; finished tasks and hand-made rules stay
- [ ] `POST /api/chores/preview`, `GET /api/household/meta`, `POST /api/geocode` work; a failed place search is a gentle 502 mentioning the internet
- [ ] Swap, favorite, hide, restore and plan work on every meal; an unknown meal id is 404
- [ ] No test fixture still uses the original household's names

**Verify:** `python -m unittest tests.test_household_api tests.test_api` -> OK, then the full suite -> OK

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_household_api.py`:

```python
import random
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dashboard import packs as packs_mod
from dashboard.api import App
from dashboard.household import ConfigStore
from dashboard.store import Store


def make_pack():
    recipes = [
        {"id": f"r{i}", "name": f"Meal {i}", "url": f"https://example.com/{i}", "minutes": 20,
         "tags": ["quick", "vegetarian"] if i % 2 == 0 else ["quick"]}
        for i in range(6)
    ]
    return packs_mod.parse_pack({"id": "quick", "name": "Quick", "description": "Fast", "recipes": recipes})


class FakeWeather:
    def __init__(self):
        self.calls = []

    def get(self):
        return {"available": False}

    def set_location(self, location, unit="F"):
        self.calls.append((location, unit))


class FakeAlerts:
    fresh = False

    def __init__(self):
        self.locations = []

    def get(self):
        return []

    def set_location(self, location):
        self.locations.append(location)


def household(**changes):
    base = {
        "name": "Sample Household",
        "location": {"label": "Portland, Oregon", "lat": 45.52, "lon": -122.68, "alerts": True},
        "units": {"temperature": "F"},
        "rooms": [{"name": "Kitchen", "kind": "kitchen", "usage": "high"}],
        "choreMinutes": 30,
        "mealSlots": [{"name": "Dinner", "packIds": ["quick"]}],
    }
    base.update(changes)
    return base


class HouseholdApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.clock = [date(2026, 10, 5)]  # Monday
        self.places = [{"label": "Portland, Oregon, United States", "lat": 45.52, "lon": -122.68, "countryCode": "US"}]
        self.app = self.build()

    def build(self):
        self.weather, self.alerts = FakeWeather(), FakeAlerts()
        return App(Store(self.dir / "data.json", self.dir / "backups"), [], {}, self.weather,
                   clock=lambda: self.clock[0], rng=random.Random(1), alerts=self.alerts,
                   household_store=ConfigStore(self.dir / "household.json"), packs=[make_pack()],
                   geocoder=lambda q: self.places)

    def call(self, method, path, body=None):
        return self.app.handle(method, path, body)

    def save(self, regenerate=False, **changes):
        return self.call("PUT", "/api/household", {"household": household(**changes), "regenerateChores": regenerate})

    def test_first_run_needs_setup(self):
        _, state = self.call("GET", "/api/state")
        self.assertTrue(state["needsSetup"])
        self.assertIsNone(state["household"])
        self.assertEqual((state["slots"], state["dinners"]), ([], {}))

    def test_saving_a_household_finishes_setup_and_deals_dinners(self):
        status, state = self.save()
        self.assertEqual(status, 200)
        self.assertFalse(state["needsSetup"])
        self.assertEqual(state["household"]["name"], "Sample Household")
        self.assertEqual(state["slots"], [{"id": "dinner", "name": "Dinner"}])
        self.assertEqual(len(state["dinners"]["dinner"]["picks"]), 3)

    def test_household_survives_a_restart(self):
        self.save()
        again = self.build()
        _, state = again.handle("GET", "/api/state", {})
        self.assertFalse(state["needsSetup"])
        self.assertEqual(len(state["dinners"]["dinner"]["picks"]), 3)
        self.assertEqual(self.weather.calls[-1][0]["label"], "Portland, Oregon")

    def test_bad_household_is_rejected_and_nothing_changes(self):
        self.assertEqual(self.save(name=" ")[0], 400)
        self.assertEqual(self.save(mealSlots=[{"name": "Dinner", "packIds": ["nope"]}])[0], 400)
        self.assertEqual(self.call("PUT", "/api/household", {})[0], 400)
        self.assertTrue(self.call("GET", "/api/state")[1]["needsSetup"])

    def test_location_and_unit_reach_weather_and_alerts(self):
        self.save(units={"temperature": "C"})
        location, unit = self.weather.calls[-1]
        self.assertEqual((location["lat"], unit), (45.52, "C"))
        self.assertTrue(self.alerts.locations[-1]["alerts"])

    def test_disabled_meal_is_not_dealt(self):
        _, state = self.save(mealSlots=[{"name": "Dinner", "packIds": ["quick"]}, {"name": "Lunch", "enabled": False}])
        self.assertEqual([s["id"] for s in state["slots"]], ["dinner"])

    def test_tag_filter_narrows_the_pool(self):
        _, state = self.save(mealSlots=[{"name": "Dinner", "packIds": ["quick"], "tagFilter": ["vegetarian"]}])
        ids = {r["id"] for r in state["dinners"]["dinner"]["picks"]}
        self.assertTrue(ids <= {"quick.r0", "quick.r2", "quick.r4"})

    def test_own_recipes_join_the_pool_and_can_be_opened(self):
        own = {"name": "Gran stew", "url": "https://example.com/stew"}
        self.save(mealSlots=[{"name": "Dinner", "ownRecipes": [own]}])
        self.assertEqual(self.call("POST", "/api/open", {"url": "https://example.com/stew"})[0], 200)

    def test_every_meal_supports_swap_favorite_and_hide(self):
        _, state = self.save()
        pick = state["dinners"]["dinner"]["picks"][0]["id"]
        _, state = self.call("POST", "/api/dinners/dinner/favorite", {"recipeId": pick})
        self.assertEqual([r["id"] for r in state["dinners"]["dinner"]["favorites"]], [pick])
        _, state = self.call("POST", "/api/dinners/dinner/hide", {"recipeId": pick})
        self.assertEqual([r["id"] for r in state["dinners"]["dinner"]["hidden"]], [pick])
        self.assertEqual(self.call("POST", "/api/dinners/missing/swap", {"recipeId": pick})[0], 404)

    def test_regenerating_chores_adds_generated_rules_and_todays_tasks(self):
        _, state = self.save(regenerate=True)
        self.assertEqual([r["id"] for r in state["rules"]], ["gen-1-1", "gen-1-2", "gen-1-3"])
        self.assertEqual(len(state["tasks"]["today"]), 3)

    def test_saving_without_regenerate_leaves_chores_alone(self):
        _, state = self.save()
        self.assertEqual(state["rules"], [])

    def test_regenerating_again_replaces_generated_chores_and_keeps_custom_ones(self):
        self.save(regenerate=True)
        self.call("POST", "/api/rules", {"title": "Water plants", "repeat": "daily"})
        _, state = self.save(regenerate=True, rooms=[{"name": "Office", "kind": "office", "usage": "high"}])
        titles = [t["title"] for t in state["tasks"]["today"]]
        self.assertEqual(sorted(titles), ["Office: dust surfaces", "Office: vacuum floor", "Water plants"])
        self.assertEqual(sorted(r["title"] for r in state["rules"]), ["Office: dust surfaces", "Office: vacuum floor", "Water plants"])

    def test_finished_generated_tasks_are_kept_when_regenerating(self):
        _, state = self.save(regenerate=True)
        done = state["tasks"]["today"][0]
        self.call("POST", f"/api/tasks/{done['id']}/done")
        _, state = self.save(regenerate=True)
        self.assertIn(done["id"], [t["id"] for t in state["tasks"]["today"] if t["done"]])

    def test_chore_preview(self):
        rooms = [{"name": "Kitchen", "kind": "kitchen", "usage": "high"}]
        status, body = self.call("POST", "/api/chores/preview", {"rooms": rooms, "choreMinutes": 30})
        self.assertEqual(status, 200)
        self.assertEqual(body["days"][0]["rooms"], ["Kitchen"])
        self.assertEqual(body["tasks"][0], {"day": "mon", "title": "Kitchen: wipe counters and sink"})
        self.assertEqual(body["warnings"], [])
        self.assertEqual(self.call("POST", "/api/chores/preview", {"rooms": "x"})[0], 400)
        self.assertEqual(self.call("POST", "/api/chores/preview", {"rooms": [], "choreMinutes": 1})[0], 400)

    def test_meta_lists_packs_tags_and_room_kinds(self):
        status, meta = self.call("GET", "/api/household/meta")
        self.assertEqual(status, 200)
        self.assertEqual(meta["packs"], [{"id": "quick", "name": "Quick", "description": "Fast", "count": 6}])
        self.assertIn("vegetarian", meta["tags"])
        self.assertIn("kitchen", [k["kind"] for k in meta["roomKinds"]])

    def test_geocode(self):
        status, body = self.call("POST", "/api/geocode", {"q": "Portland"})
        self.assertEqual((status, body["places"][0]["countryCode"]), (200, "US"))
        self.assertEqual(self.call("POST", "/api/geocode", {"q": 5})[0], 400)

    def test_geocode_failure_is_a_gentle_502(self):
        def offline(query):
            raise OSError("offline")

        self.app.geocoder = offline
        status, body = self.call("POST", "/api/geocode", {"q": "Portland"})
        self.assertEqual(status, 502)
        self.assertIn("internet", body["error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_household_api`
Expected: errors (`App` has no `household_store` argument).

- [ ] **Step 3: Make the old test fixtures generic**

The copied tests used the original household's names as dinner-list keys. Save as `_rename_fixtures.py`, run `python _rename_fixtures.py` (it prints the files it changed), then delete it:

```python
"""Task 0: the copied tests used the first household's names as dinner-list keys. Make them generic."""
from pathlib import Path

KEEP = "@@KEEP@@"
SWAPS = [
    ('recipes("v", 9)', KEEP),
    ('"chris"', '"dinner"'),
    ('"v"', '"lunch"'),
    ("/api/dinners/chris/", "/api/dinners/dinner/"),
    ("/api/dinners/v/", "/api/dinners/lunch/"),
    (KEEP, 'recipes("v", 9)'),
]
for path in Path("tests").glob("*.py"):
    text = path.read_text(encoding="utf-8")
    new = text
    for old, replacement in SWAPS:
        new = new.replace(old, replacement)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print("renamed in", path.name)
```

- [ ] **Step 4: Patch the API**

Save as `_patch_api.py`, run, delete:

```python
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


patch("dashboard/api.py", [
    ('''from . import dates as dates_mod, dinners, plans as plans_mod, rules as rules_mod, shopping as shopping_mod, todo''',
     '''from . import (
    chores_gen, dates as dates_mod, dinners, geocode as geocode_mod, household as household_mod,
    packs as packs_mod, plans as plans_mod, rules as rules_mod, shopping as shopping_mod, todo,
)'''),
    ('''opener=webbrowser.open_new_tab, alerts=None):
        self.store = store''', '''opener=webbrowser.open_new_tab, alerts=None,
                 household_store=None, packs=None, geocoder=None):
        self.store = store'''),
    ('''        self._undo = None
        self._undo_seq = 0

    def _usable_rules''', '''        self._undo = None
        self._undo_seq = 0
        self.household_store = household_store
        self.packs = {p["id"]: p for p in (packs or [])}
        self.geocoder = geocoder or geocode_mod.search
        self.household = household_store.load() if household_store else None
        if household_store:
            self._rebuild_recipes()
            self._apply_location()

    def _rebuild_recipes(self):
        slots = (self.household or {}).get("mealSlots", [])
        self.recipes = {s["id"]: packs_mod.slot_recipes(s, self.packs) for s in slots if s["enabled"]}

    def _apply_location(self):
        household = self.household or {}
        location = household.get("location")
        unit = household.get("units", {}).get("temperature", "F")
        set_weather = getattr(self.weather, "set_location", None)
        if set_weather:
            set_weather(location, unit)
        set_alerts = getattr(self.alerts, "set_location", None)
        if set_alerts:
            set_alerts(location)

    def _ensure_dinners(self, today):
        for key, items in self.recipes.items():
            dinners.ensure_today(self.data, key, items, today, self.rng)

    def _apply_chores(self, today):
        """Replace the generated cleaning rules (ids 'gen-...') and today's unfinished tasks from them."""
        result = chores_gen.generate(self.household["rooms"], self.household["choreMinutes"])
        iso = today.isoformat()
        kept = [r for r in self.data.get("rules", []) if not str(r.get("id", "")).startswith("gen-")]
        self.data["rules"] = kept + [dict(r, paused=False) for r in result["rules"]]
        self.data["rulesSeeded"] = True
        self.data["generated"] = [
            k for k in self.data.get("generated", []) if not (k.startswith("gen-") and k.split("|")[-1] >= iso)
        ]
        self.data["tasks"] = [
            t for t in self.data.get("tasks", [])
            if not (str(t.get("ruleId") or "").startswith("gen-") and not t["done"] and t["date"] >= iso)
        ]

    def _save_household(self, body, today):
        if self.household_store is None:
            raise KeyError("household")
        cleaned = household_mod.validate(body.get("household"), known_pack_ids=set(self.packs))
        self.household_store.save(cleaned)
        self.household = cleaned
        self._rebuild_recipes()
        self._apply_location()
        if body.get("regenerateChores") is True:
            self._apply_chores(today)
        self._ensure_dinners(today)

    def _household_meta(self):
        return {
            "roomKinds": chores_gen.kind_choices(),
            "tags": list(packs_mod.TAGS),
            "packs": [{"id": p["id"], "name": p["name"], "description": p["description"], "count": len(p["recipes"])}
                      for p in self.packs.values()],
        }

    def _chores_preview(self, body):
        rooms = household_mod.clean_rooms(body.get("rooms", []))
        result = chores_gen.generate(rooms, household_mod.clean_minutes(body.get("choreMinutes", 30)))
        return {"days": result["days"], "warnings": result["warnings"],
                "tasks": [{"day": r["days"][0], "title": r["title"]} for r in result["rules"]]}

    def _geocode(self, query):
        if not isinstance(query, str):
            return 400, {"error": "Bad request"}
        try:
            return 200, {"places": self.geocoder(query)}
        except (OSError, ValueError):
            return 502, {"error": "Could not look that up. Check the internet connection, or type the coordinates yourself."}

    def _usable_rules'''),
    ('''        for key, items in self.recipes.items():
            dinners.ensure_today(self.data, key, items, today, self.rng)

    def _undo_view''', '''        self._ensure_dinners(today)

    def _undo_view'''),
    ('''            "dinners": {key: dinners.view(self.data, key, items) for key, items in self.recipes.items()},
''', '''            "dinners": {key: dinners.view(self.data, key, items) for key, items in self.recipes.items()},
            "slots": self._slots(),
            "household": self.household,
            "needsSetup": self.household_store is not None and self.household is None,
'''),
    ('''    def _undo_view(self):''', '''    def _slots(self):
        names = {s["id"]: s["name"] for s in (self.household or {}).get("mealSlots", [])}
        return [{"id": key, "name": names.get(key, key)} for key in self.recipes]

    def _undo_view(self):'''),
    ('''            if method == "PUT" and path == "/api/settings":''', '''            if method == "GET" and path == "/api/household/meta":
                return 200, self._household_meta()
            if method == "PUT" and path == "/api/household":
                return 200, self._run(lambda today: self._save_household(body, today))
            if method == "POST" and path == "/api/chores/preview":
                return 200, self._chores_preview(body)
            if method == "POST" and path == "/api/geocode":
                return self._geocode(body.get("q"))
            if method == "PUT" and path == "/api/settings":'''),
    ('''r"/api/dinners/(chris|v)/(swap|favorite|hide|restore|plan)"''', '''r"/api/dinners/([\\w-]+)/(swap|favorite|hide|restore|plan)"'''),
    ('''                if action in ("hide", "restore") and key != "v":
                    return 404, {"error": "Not found"}
''', ''),
])

print("api patched")
```

- [ ] **Step 5: Update the one test that expected only one list to allow hiding**

Save as `_patch_test_api.py`, run, delete:

```python
from pathlib import Path

p = Path("tests/test_api.py")
text = p.read_text(encoding="utf-8")
old = '        self.assertEqual(self.call("POST", "/api/dinners/dinner/hide", {"recipeId": pick})[0], 404)\n'
new = (
    '        self.assertEqual(self.call("POST", "/api/dinners/nope/swap", {"recipeId": pick})[0], 404)\n'
    '        _, state = self.call("POST", "/api/dinners/dinner/hide", {"recipeId": pick})\n'
    '        self.assertEqual([r["id"] for r in state["dinners"]["dinner"]["hidden"]], [pick])\n'
)
assert text.count(old) == 1, "expected the old hide assertion exactly once"
p.write_text(text.replace(old, new), encoding="utf-8")
print("test_api patched")
```

- [ ] **Step 6: Run the tests**

Run: `python -m unittest tests.test_household_api tests.test_api -v`
Expected: all OK. Then `python -m unittest discover -s tests -t .` -> OK.

- [ ] **Step 7: Commit**

```bash
git add dashboard/api.py tests
git commit -m "feat: household API and generic meal slots"
```

---

### Task 5: Server data folder and port fallback

**Goal:** The server reads and writes the household's own folder, starts with no household (first run), and takes the next free port when 8765 is busy.

**Files:**
- Modify: `server.py` (through a patch script)
- Test: `tests/test_server_ports.py`

**Acceptance Criteria:**
- [ ] `build_app()` uses `%APPDATA%\HomeDashboard` (or `HOME_DASHBOARD_DATA`) and bundled `packs/`; a fresh folder reports `needsSetup`
- [ ] `open_server` skips busy ports (including on Windows, where shared ports must be refused) and raises when none is free
- [ ] `python server.py` prints the address it is serving

**Verify:** `python -m unittest tests.test_server_ports tests.test_server` -> OK, then the full suite -> OK

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_server_ports.py`:

```python
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import server
from dashboard import paths


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class OpenServerTests(unittest.TestCase):
    def test_skips_a_busy_port(self):
        busy = socket.socket()
        self.addCleanup(busy.close)
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        spare = free_port()
        httpd = server.open_server(object(), ports=[busy.getsockname()[1], spare])
        self.addCleanup(httpd.server_close)
        self.assertEqual(httpd.server_address, ("127.0.0.1", spare))

    def test_raises_when_every_port_is_busy(self):
        busy = socket.socket()
        self.addCleanup(busy.close)
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        with self.assertRaises(OSError):
            server.open_server(object(), ports=[busy.getsockname()[1]])


class PathsTests(unittest.TestCase):
    def test_data_dir_honours_the_override(self):
        with mock.patch.dict(os.environ, {"HOME_DASHBOARD_DATA": "C:/somewhere"}):
            self.assertEqual(paths.data_dir(), Path("C:/somewhere"))

    def test_data_dir_uses_appdata_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "HOME_DASHBOARD_DATA"}
        env["APPDATA"] = "C:/Users/x/AppData/Roaming"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(paths.data_dir(), Path("C:/Users/x/AppData/Roaming/HomeDashboard"))

    def test_resource_root_holds_web_and_packs_when_running_from_source(self):
        self.assertTrue((paths.resource_root() / "web" / "index.html").is_file())


class BuildAppTests(unittest.TestCase):
    def test_a_fresh_data_dir_means_first_run(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME_DASHBOARD_DATA": tmp}):
            status, state = server.build_app().handle("GET", "/api/state", {})
        self.assertEqual(status, 200)
        self.assertTrue(state["needsSetup"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_server_ports`
Expected: `AttributeError: module 'server' has no attribute 'open_server'`.

- [ ] **Step 3: Patch the server**

Save as `_patch_server.py`, run, delete:

```python
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:60]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


patch("server.py", [
    ('''import json
import mimetypes
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dashboard.alerts import AlertService
from dashboard.api import App
from dashboard.store import Store
from dashboard.weather import WeatherService

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
HOST, PORT = "127.0.0.1", 8765
''', '''import json
import mimetypes
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dashboard import packs as packs_mod, paths
from dashboard.alerts import AlertService
from dashboard.api import App
from dashboard.household import ConfigStore
from dashboard.store import Store
from dashboard.weather import WeatherService

ROOT = paths.resource_root()
WEB = ROOT / "web"
HOST, PORT = "127.0.0.1", 8765
PORTS = range(PORT, PORT + 10)
'''),
    ('''def build_app():
    rules = json.loads((ROOT / "content" / "chores.json").read_text(encoding="utf-8"))["rules"]
    recipes = json.loads((ROOT / "content" / "recipes.json").read_text(encoding="utf-8"))
    store = Store(ROOT / "data" / "data.json", ROOT / "data" / "backups")
    return App(store, rules, recipes, WeatherService(), clock=_clock(), alerts=AlertService())
''', '''def build_app():
    data = paths.data_dir()
    return App(
        Store(data / "data.json", data / "backups"), [], {}, WeatherService(),
        clock=_clock(), alerts=AlertService(),
        household_store=ConfigStore(data / "household.json", data / "backups"),
        packs=packs_mod.load_packs(ROOT / "packs"),
    )


class DashboardServer(ThreadingHTTPServer):
    # Windows lets two sockets share a port when SO_REUSEADDR is set, which would defeat the port fallback.
    allow_reuse_address = False
    daemon_threads = True


def open_server(app, ports=PORTS):
    """Bind the first free local port in `ports`."""
    handler = make_handler(app)
    for port in ports:
        try:
            return DashboardServer((HOST, port), handler)
        except OSError:
            continue
    raise OSError(f"No free port from {ports[0]} to {ports[-1]}")
'''),
    ('''if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), make_handler(build_app())).serve_forever()
''', '''if __name__ == "__main__":
    httpd = open_server(build_app())
    print(f"Home Dashboard running at http://{HOST}:{httpd.server_address[1]}")
    httpd.serve_forever()
'''),
])
print("server patched")
```

- [ ] **Step 4: Run the tests**

Run: `python -m unittest tests.test_server_ports tests.test_server tests.test_web_assets -v`
Expected: all OK. Then the full suite -> OK.

- [ ] **Step 5: Start it for real**

```bash
export HOME_DASHBOARD_DATA="$(pwd -W)/.demo-data"
python server.py &
sleep 2
```

Expected: a line `Home Dashboard running at http://127.0.0.1:87xx`. Use that port: `curl -s http://127.0.0.1:<port>/api/state | head -c 200` shows `"needsSetup": true`. Stop the server (PowerShell, using the port it printed, never 8765):

```powershell
Get-NetTCPConnection -LocalPort <port> -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server_ports.py
git commit -m "feat: serve from the household's data folder, with port fallback"
```

---

### Task 6: Four starter packs and the link checker

**Goal:** Four curated starter packs of at least 20 recipes each ship in `packs/`, every link works, and none of the original household's recipes are used.

**Files:**
- Create: `packs/family-classics.json`, `packs/quick-weeknight.json`, `packs/vegetarian.json`, `packs/low-carb.json`
- Replace: `scripts/check_links.py`
- Test: `tests/test_content_packs.py`

**Acceptance Criteria:**
- [ ] Exactly four packs ship; each id matches its file name and each has a description and at least 20 recipes
- [ ] Every recipe has an https link, minutes and at least one tag from the fixed tag list; no link or name repeats anywhere across the packs
- [ ] `vegetarian` recipes carry `vegetarian` (or `vegan`), `low-carb` recipes carry `low-carb`, `quick-weeknight` recipes carry `quick` and take 30 minutes or less
- [ ] No recipe URL matches any URL in the original household's `content/recipes.json`
- [ ] `python scripts/check_links.py` reports 0 failures

**Verify:** `python -m unittest tests.test_content_packs` -> OK and `python scripts/check_links.py` -> `N links checked, 0 failures`

**Steps:**

- [ ] **Step 1: Write the pack tests and the new link checker**

Create `tests/test_content_packs.py`:

```python
import json
import unittest
from pathlib import Path

from dashboard import packs

PACK_DIR = Path(__file__).resolve().parent.parent / "packs"
EXPECTED = {"family-classics", "quick-weeknight", "vegetarian", "low-carb"}


class ShippedPacksTests(unittest.TestCase):
    def setUp(self):
        self.raw = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(PACK_DIR.glob("*.json"))}
        self.parsed = {name: packs.parse_pack(raw) for name, raw in self.raw.items()}

    def test_the_four_starter_packs_ship_and_ids_match_file_names(self):
        self.assertEqual(set(self.raw), EXPECTED)
        for name, pack in self.parsed.items():
            self.assertEqual(pack["id"], name)
            self.assertTrue(pack["description"], name)

    def test_every_pack_has_at_least_twenty_recipes(self):
        for name, pack in self.parsed.items():
            self.assertGreaterEqual(len(pack["recipes"]), 20, name)

    def test_recipes_are_https_links_with_time_and_tags(self):
        for name, pack in self.parsed.items():
            for recipe in pack["recipes"]:
                self.assertTrue(recipe["url"].startswith("https://"), recipe["id"])
                self.assertIsNotNone(recipe["minutes"], recipe["id"])
                self.assertTrue(recipe["tags"], recipe["id"])

    def test_links_and_names_are_not_repeated_anywhere(self):
        recipes = [r for pack in self.parsed.values() for r in pack["recipes"]]
        self.assertEqual(len({r["url"] for r in recipes}), len(recipes))
        self.assertEqual(len({r["name"].lower() for r in recipes}), len(recipes))

    def test_each_pack_keeps_its_promise(self):
        for recipe in self.parsed["vegetarian"]["recipes"]:
            self.assertTrue({"vegetarian"} & set(recipe["tags"]) or "vegan" in recipe["tags"], recipe["id"])
        for recipe in self.parsed["low-carb"]["recipes"]:
            self.assertIn("low-carb", recipe["tags"], recipe["id"])
        for recipe in self.parsed["quick-weeknight"]["recipes"]:
            self.assertIn("quick", recipe["tags"], recipe["id"])
            self.assertLessEqual(recipe["minutes"], 30, recipe["id"])

    def test_the_wizard_default_pack_exists(self):
        self.assertIn("family-classics", self.parsed)
```

Replace `scripts/check_links.py`:

```python
"""Opens every recipe link in packs/*.json and reports the ones that fail. Run before releasing a pack."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACKS = Path(__file__).resolve().parent.parent / "packs"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def check(url):
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status
        except urllib.error.HTTPError as error:
            if method == "GET":
                return error.code
        except Exception as error:
            if method == "GET":
                return str(error)
    return "unknown"


def main():
    checked = failures = 0
    for path in sorted(PACKS.glob("*.json")):
        pack = json.loads(path.read_text(encoding="utf-8"))
        for recipe in pack["recipes"]:
            checked += 1
            result = check(recipe["url"])
            if not (isinstance(result, int) and result < 400):
                failures += 1
                print(f"FAIL [{pack['id']}] {recipe['id']}: {result} {recipe['url']}")
    print(f"{checked} links checked, {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the pack tests and watch them fail**

Run: `python -m unittest tests.test_content_packs`
Expected: failure (no `packs/` folder yet).

- [ ] **Step 3: Write the four packs**

Each pack is one JSON file in `packs/`:

```json
{
  "id": "quick-weeknight",
  "name": "Quick weeknight",
  "description": "Dinners on the table in 30 minutes or less.",
  "recipes": [
    {"id": "short-lowercase-id", "name": "Recipe name in your own words", "url": "https://...", "minutes": 25, "tags": ["quick", "family-friendly"]}
  ]
}
```

Rules (the tests enforce most of them):

- Packs: `family-classics` (crowd-pleasing dinners, tag mostly `family-friendly`), `quick-weeknight` (every recipe tagged `quick`, 30 minutes or less), `vegetarian` (every recipe tagged `vegetarian` or `vegan`), `low-carb` (every recipe tagged `low-carb`). At least 20 recipes each, and no recipe appears in more than one pack.
- Tags come only from: vegetarian, vegan, low-carb, gluten-free, dairy-free, quick, family-friendly, one-pan, slow-cooker. Add every tag that is truly accurate (for example a vegetarian one-pan dish gets both), because households filter on them.
- Find real recipe pages with web search (a mix of well-known recipe sites keeps the packs from depending on one). Open each page to confirm it exists, note the total time it states (round to 5 minutes) and check the diet claim against the page. Link to the page itself; write the `name` in your own short words; do not copy descriptions, ingredients or steps. Prefer pages that are free to read.
- `id` values are lowercase letters, digits and hyphens, unique within the pack.

- [ ] **Step 4: Confirm none of the original household's recipes were used**

The original lists are private. Read them only to build an exclusion list (read-only; never copy anything from them):

```bash
python - <<'PY'
import json, glob
old = json.load(open(r"C:\Users\shado\Claude\home-dashboard\content\recipes.json", encoding="utf-8"))
private = {r["url"] for items in old.values() for r in items}
new = {r["url"] for path in glob.glob("packs/*.json") for r in json.load(open(path, encoding="utf-8"))["recipes"]}
print("overlap:", sorted(private & new))
PY
```

Expected: `overlap: []`. If any URL is listed, replace that recipe with a different one and re-run.

- [ ] **Step 5: Run the pack tests and the link checker**

```bash
python -m unittest tests.test_content_packs
python scripts/check_links.py
```

Expected: tests OK; `N links checked, 0 failures`. For any `FAIL` line, replace that recipe (a site that blocks scripts but works in a browser may be kept only if you confirm it opens in a browser), then re-run both.

- [ ] **Step 6: Flag for human review**

The choice of recipes needs the owner's review before the app is shared. Do not skip this in the final report.

- [ ] **Step 7: Commit**

```bash
git add packs scripts/check_links.py tests/test_content_packs.py
git commit -m "feat: four starter recipe packs and a link checker for them"
```

---

### Task 7: Dashboard meal sections, modules, scaling

**Goal:** The dashboard draws one section per meal from the household, shows the household name, hides switched-off modules, shows the chosen temperature unit, and scales itself to any window.

**Files:**
- Create: `web/household.js` (part 1), `tests/webcase.py`, `tests/test_household_web.py`
- Modify: `web/index.html`, `web/app.js`, `web/app.css`, `web/plans.js`, `tests/test_web_assets.py` (through patch scripts)

**Acceptance Criteria:**
- [ ] `index.html` has one empty `#dinners` container and no hardcoded dinner sections; the old dinner code is gone from `app.js`
- [ ] Each enabled meal renders three cards, a Favorites row and a Hidden recipes list; ribbon colors cycle through four
- [ ] Switched-off modules (weather, tasks, plans, shopping, timers) disappear and the rest expand; the weather shows the household's unit
- [ ] At 1920x1080 the page fits with no scrolling; at 1366x768 it is scaled (zoom about 0.71) and still fits
- [ ] No web file contains the original household's names, town or coordinates
- [ ] The six web-asset tests that pinned the old dinner markup are re-pointed and pass

**Verify:** `python -m unittest tests.test_household_web tests.test_web_assets` -> OK; browser check below

**Steps:**

- [ ] **Step 1: Write the shared web-test helper and the tests**

Create `tests/webcase.py`:

```python
import http.client
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import server
from dashboard.api import App
from dashboard.store import Store


class WebCase(unittest.TestCase):
    """Serves the real web/ folder from a throwaway server so tests can read the files as a browser would."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = App(Store(Path(tmp.name) / "d.json"), [], {}, None)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read().decode("utf-8")

    def css_rule(self, selector):
        """Declarations of the first rule for exactly `selector`, as a dict."""
        css = re.sub(r"/\*.*?\*/", "", self.get("/app.css")[2], flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            if " ".join(match.group(1).split()) == selector:
                pairs = (part.split(":", 1) for part in match.group(2).split(";") if ":" in part)
                return {k.strip(): "".join(v.split()) for k, v in pairs}
        self.fail(f"app.css has no rule for {selector!r}")

    def assert_scripts_safe(self, *names):
        for name in names:
            status, ctype, js = self.get("/" + name)
            self.assertEqual(status, 200, name)
            self.assertIn("javascript", ctype, name)
            for banned in ("innerHTML", "insertAdjacent", "outerHTML"):
                self.assertNotIn(banned, js, name)
```

Create `tests/test_household_web.py`:

```python
from tests.webcase import WebCase


class HouseholdWebTests(WebCase):
    def test_page_has_the_household_hooks_and_script_order(self):
        page = self.get("/")[2]
        for markup in ('id="dinners"', 'id="hh-name"', 'src="household.js"'):
            self.assertIn(markup, page)
        self.assertLess(page.index('src="alerts.js"'), page.index('src="household.js"'))
        self.assertLess(page.index('src="household.js"'), page.index('src="app.js"'))
        for old in ("Chris", "V's Dinner", 'id="chris"', 'id="v"', 'id="hidden-toggle"'):
            self.assertNotIn(old, page)

    def test_household_js_is_served_and_safe(self):
        self.assert_scripts_safe("household.js")

    def test_nothing_in_the_web_files_names_a_household_or_town(self):
        for name in ("index.html", "app.js", "app.css", "household.js", "plans.js", "shopping.js", "alerts.js", "timers.js"):
            text = self.get("/" + name)[2]
            for word in ("Chris", "Huntsville", "Alabama", "34.73"):
                self.assertNotIn(word, text, f"{word} in {name}")

    def test_household_js_dashboard_functions(self):
        js = self.get("/household.js")[2]
        for label in ("function renderHousehold", "function renderDinners", "function fitScreen", "function dinnerCard",
                      "Not tonight, show another", "Get the recipe", "Hidden recipes", "Favorites", "Plan this dinner"):
            self.assertIn(label, js)
        self.assertIn("document.documentElement.style.zoom", js)

    def test_app_js_renders_the_household_and_the_unit(self):
        js = self.get("/app.js")[2]
        self.assertIn("renderHousehold()", js)
        self.assertIn("weather.unit", js)
        self.assertNotIn("°F`", js)

    def test_scaling_and_stacking_rules_exist(self):
        css = self.get("/app.css")[2]
        self.assertNotIn("@media (max-width:1500px)", css)
        self.assertIn("html.stacked body", css)
        self.assertIn("repeat(var(--slots,2)", css)
        for n in "234":
            self.assertIn(f'.slot[data-ribbon="{n}"]', css)
        self.assertIn(".slot{--ribbon:var(--ribbon-1)", css)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_household_web`
Expected: failures (no `household.js`, no `id="dinners"`).

- [ ] **Step 3: Create `web/household.js`**

This is the first half of the file; Task 8 appends the second half.

```javascript
'use strict';

// The household layer: meal slots, module switches, the household name and the screen-fitting zoom. Loaded before app.js, so it only uses app.js helpers
// ($, el, glyph, api, act, state, setError ...) when a function runs, never at load time.

const hiddenOpen = new Set();
let slotSig = '';

// ---- Fit any screen: the page is drawn for 1920x1080 and scaled to the window; tall or narrow windows stack and scroll ----
function fitScreen() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const stacked = w <= h || w < 1280;
  const zoom = stacked ? Math.min(1.5, Math.max(0.5, w / 1100)) : Math.min(2, Math.max(0.5, Math.min(w / 1920, h / 1080)));
  document.documentElement.style.zoom = String(Math.round(zoom * 100) / 100);
  document.documentElement.classList.toggle('stacked', stacked);
}
window.addEventListener('resize', fitScreen);
fitScreen();

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function moduleOn(name) {
  const modules = state && state.household ? state.household.modules : null;
  return !modules || modules[name] !== false;
}

// ---- The dashboard: household name, module switches, one section per meal ----
function renderHousehold() {
  const household = state.household;
  $('#hh-name').textContent = household ? household.name : '';
  document.title = household ? `${household.name} - Home` : 'Home';
  const weatherOn = moduleOn('weather');
  $('#weather').hidden = !weatherOn;
  $('#outlook').hidden = !weatherOn;
  $('.top').classList.toggle('no-weather', !weatherOn);
  const tasksOn = moduleOn('tasks');
  $('.card.tasks').hidden = !tasksOn;
  $('main').classList.toggle('no-tasks', !tasksOn);
  $('main').classList.toggle('no-slots', !(state.slots || []).length);
  let shown = 0;
  for (const [name] of SCREENS) {
    const on = name === 'today' || moduleOn(name);
    if (name !== 'today') $('#tab-' + name).hidden = !on;
    if (on) shown += 1;
    else if (activeScreen === name) selectView('today', false);
  }
  $('#views').hidden = shown < 2;
}

function dinnerCard(slotId, recipe) {
  const planned = recipe.url && allPlans().find((plan) => plan.date === state.date && plan.url === recipe.url);
  const meta = [recipe.minutes ? `${recipe.minutes} min` : null, ...(recipe.tags || []).slice(0, 2)].filter(Boolean);
  const base = `/api/dinners/${slotId}`;
  const tools = el('div', {class: 'tools'},
    el('button', {
      class: 'icon' + (recipe.favorite ? ' on' : ''),
      'aria-label': recipe.favorite ? 'Remove from favorites' : 'Save as favorite',
      onclick: () => act('POST', `${base}/favorite`, {recipeId: recipe.id}),
    }, glyph('heart', recipe.favorite)),
    el('button', {class: 'icon', 'aria-label': 'Never show this again', onclick: () => act('POST', `${base}/hide`, {recipeId: recipe.id})}, glyph('x')));
  return el('article', {class: 'dinner' + (planned ? ' planned' : '')},
    el('h4', {}, recipe.name),
    planned ? el('p', {class: 'desc'}, 'Planned for tonight') : null,
    el('p', {class: 'meta'}, meta.map((text) => el('span', {class: 'tag'}, text))),
    el('div', {class: 'links'},
      recipeLink(recipe, {}, 'Get the recipe', glyph('arrow')),
      el('button', {
        type: 'button', class: 'icon' + (planned ? ' on' : ''), 'aria-label': planned ? "Open tonight's plan" : 'Plan this dinner',
        title: planned ? "Open tonight's plan" : 'Plan this dinner',
        onclick: () => (planned ? openPlan(planned.id) : planFromRecipe(slotId, recipe)),
      }, glyph('list'))),
    el('div', {class: 'row'},
      el('button', {class: 'ghost', onclick: () => act('POST', `${base}/swap`, {recipeId: recipe.id})}, 'Not tonight, show another'),
      tools));
}

function buildSlot(slot, index) {
  return el('section', {class: 'card slot', id: `slot-${slot.id}`, 'data-ribbon': String((index % 4) + 1)},
    el('h2', {}, slot.name),
    el('div', {class: 'cards'}),
    el('div', {class: 'favrow'}, el('h3', {}, 'Favorites'), el('div', {class: 'favs'})),
    el('button', {type: 'button', class: 'link hidden-toggle', hidden: true}),
    el('div', {class: 'hidden-panel', hidden: true}));
}

function fillSlot(slot) {
  const data = state.dinners[slot.id];
  const root = $(`#slot-${slot.id}`);
  if (!data || !root) return;
  root.querySelector('.cards').replaceChildren(...(data.picks.length
    ? data.picks.map((recipe) => dinnerCard(slot.id, recipe))
    : [el('p', {class: 'empty'}, 'No recipes to show yet. Add some in Settings, under Meals.')]));
  const favs = root.querySelector('.favs');
  favs.replaceChildren();
  if (!data.favorites.length) favs.append(el('span', {class: 'empty'}, 'Tap the heart on a dinner to save it here'));
  for (const recipe of data.favorites) favs.append(recipeLink(recipe, {class: 'chip'}, glyph('heart', true), recipe.name));
  const toggle = root.querySelector('.hidden-toggle');
  const panel = root.querySelector('.hidden-panel');
  toggle.hidden = data.hidden.length === 0;
  toggle.textContent = `Hidden recipes (${data.hidden.length})`;
  toggle.onclick = () => {
    if (hiddenOpen.has(slot.id)) hiddenOpen.delete(slot.id);
    else hiddenOpen.add(slot.id);
    renderDinners();
  };
  panel.hidden = !hiddenOpen.has(slot.id) || data.hidden.length === 0;
  panel.replaceChildren(...data.hidden.map((recipe) => el('div', {class: 'hrow'},
    el('span', {}, recipe.name),
    el('button', {class: 'ghost', onclick: () => act('POST', `/api/dinners/${slot.id}/restore`, {recipeId: recipe.id})}, 'Restore'))));
}

function renderDinners() {
  const slots = state.slots || [];
  const box = $('#dinners');
  const sig = JSON.stringify(slots);
  if (sig !== slotSig) {
    slotSig = sig;
    box.replaceChildren(...slots.map(buildSlot));
  }
  box.style.setProperty('--slots', String(Math.max(slots.length, 1)));
  box.hidden = slots.length === 0;
  for (const slot of slots) fillSlot(slot);
}
```

- [ ] **Step 4: Patch the page, script, styles and old tests**

Save as `_patch_web_a.py`, run, delete. It swaps the two hardcoded dinner sections for `#dinners`, removes the old dinner code from `app.js`, adds the household name, the unit and the module hooks, converts the old 1500px media queries into the `html.stacked` rules, and adds the ribbon and slot styles:

```python
"""Task 6: dinner slots, module switches, household name, screen scaling. Each replacement must match exactly once."""
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


# ---- index.html: one empty container replaces the two hardcoded dinner sections ----
html = Path("web/index.html").read_text(encoding="utf-8")
start = html.index('    <div class="dinners">')
end = html.index("  </main>")
Path("web/index.html").write_text(html[:start] + '    <div class="dinners" id="dinners" hidden></div>\n' + html[end:], encoding="utf-8")

patch("web/index.html", [
    ('<div class="stamp"><div id="time"></div>', '<div class="stamp"><div id="hh-name"></div><div id="time"></div>'),
    ('''  <script src="alerts.js"></script>
''', '''  <script src="alerts.js"></script>
  <script src="household.js"></script>
'''),
])

# ---- app.js: the old dinner code moves to household.js ----
js = Path("web/app.js").read_text(encoding="utf-8")
start = js.index("function dinnerCard(key, recipe) {")
end = js.index("function isNight() {")
Path("web/app.js").write_text(js[:start] + js[end:], encoding="utf-8")

patch("web/app.js", [
    ("let showHidden = false;\n", ""),
    ("el('div', {class: 'w-temp'}, `${weather.temp}°F`),", "el('div', {class: 'w-temp'}, `${weather.temp}°${weather.unit || 'F'}`),"),
    ('''  renderUndo();
  renderDinners();
''', '''  renderUndo();
  renderHousehold();
  renderDinners();
'''),
])

# ---- plans.js: arrow keys skip screens that are switched off ----
patch("web/plans.js", [
    ('''          const at = SCREENS.findIndex(([name]) => name === key);
          selectView(SCREENS[(at + step + SCREENS.length) % SCREENS.length][0], true);''',
     '''          const shown = SCREENS.filter(([name]) => !$('#tab-' + name).hidden);
          const at = shown.findIndex(([name]) => name === key);
          selectView(shown[(at + step + shown.length) % shown.length][0], true);'''),
])

# ---- app.css ----
patch("web/app.css", [
    ("--ribbon-chris:#2f5f93;--ribbon-v:#8c2f55;--ribbon-ink:#fff;",
     "--ribbon-1:#2f5f93;--ribbon-2:#8c2f55;--ribbon-3:#2f7a4b;--ribbon-4:#8a5a12;--ribbon-ink:#fff;"),
    ("--ribbon-chris:#3d6fa6;--ribbon-v:#a23a66;",
     "--ribbon-1:#3d6fa6;--ribbon-2:#a23a66;--ribbon-3:#3f8f5c;--ribbon-4:#b07a22;"),
    (".dinners{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:1fr 1fr;gap:20px;min-height:0}",
     ".dinners{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:repeat(var(--slots,2),minmax(330px,1fr));gap:20px;min-height:0;overflow:auto;scrollbar-width:thin}"),
    ("""#chris,#v{--ribbon:var(--ribbon-chris)}
#v{--ribbon:var(--ribbon-v);position:relative}
#chris h2,#v h2{""", """.slot{--ribbon:var(--ribbon-1);position:relative}
.slot[data-ribbon="2"]{--ribbon:var(--ribbon-2)}
.slot[data-ribbon="3"]{--ribbon:var(--ribbon-3)}
.slot[data-ribbon="4"]{--ribbon:var(--ribbon-4)}
.slot h2{"""),
    ("@media (max-width:1500px){.plans-view{grid-template-columns:minmax(0,1fr)}}", "html.stacked .plans-view{grid-template-columns:minmax(0,1fr)}"),
    ("#hidden-panel{position:absolute;", ".hidden-panel{position:absolute;"),
    ("#hidden-panel .hrow{", ".hidden-panel .hrow{"),
    ("""/* Smaller windows: stack and scroll instead of clipping (the kiosk itself never hits this) */
@media (max-width:1500px){
  html,body{height:auto}
  body{display:flex;flex-direction:column;overflow:auto}
  .top{grid-template-columns:1fr;gap:16px;padding:24px 32px}
  .outlook{justify-content:flex-start;flex-wrap:wrap}
  main{grid-template-columns:minmax(0,1fr)}
  .dinners{grid-template-rows:auto auto}
  .cards{grid-template-columns:minmax(0,1fr)}
  .scroll{overflow:visible}
}""", """/* Tall or narrow windows (household.js adds html.stacked): stack the cards and scroll. Wider windows keep the
   same layout, scaled by html zoom so one drawing fits a laptop, a TV or a tablet on its side. */
html.stacked,html.stacked body{height:auto}
html.stacked body{display:flex;flex-direction:column;overflow:auto}
html.stacked .top{grid-template-columns:1fr;gap:16px;padding:24px 32px}
html.stacked .outlook{justify-content:flex-start;flex-wrap:wrap}
html.stacked main{grid-template-columns:minmax(0,1fr)}
html.stacked .dinners{grid-template-rows:none;grid-auto-rows:auto;overflow:visible}
html.stacked .cards{grid-template-columns:minmax(0,1fr)}
html.stacked .scroll{overflow:visible}"""),
])

with open("web/app.css", "a", encoding="utf-8") as css:
    css.write("""
/* Household: header name and module switches */
#hh-name{font:italic 700 26px "Palatino Linotype",Palatino,Georgia,serif;color:var(--door-soft);margin-bottom:2px}
#hh-name:empty{display:none}
.top.no-weather{grid-template-columns:1fr}
main.no-tasks,main.no-slots{grid-template-columns:minmax(0,1fr)}
.cards>.empty{grid-column:1/-1;align-self:center}
""")
print("web part A patched")
```

Save as `_patch_tests_web.py`, run, delete. It re-points the six existing tests that asserted the old markup:

```python
"""Re-points the six web-asset tests that pinned the old hardcoded dinner markup."""
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


patch("tests/test_web_assets.py", [
    ('''        for label in ("Today's tasks", "Chris Dinner", "V's Dinner", "Favorites", "Add a task"):
            self.assertIn(label, body)''', '''        for label in ("Today's tasks", 'id="dinners"', "Add a task"):
            self.assertIn(label, body)'''),
    ('''        for label in ("Move to tomorrow", "Not tonight, show another", "Get the recipe", "From yesterday", "Hidden recipes"):
            self.assertIn(label, body)''', '''        for label in ("Move to tomorrow", "From yesterday"):
            self.assertIn(label, body)
        status, ctype, body = self.get("/household.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        for label in ("Not tonight, show another", "Get the recipe", "Hidden recipes", "Favorites"):
            self.assertIn(label, body)'''),
    ('''    def test_dinner_cards_show_net_carbs_between_protein_and_time(self):
        _, _, js = self.get("/app.js")
        self.assertRegex(js, r"protein \\? `\\$\\{recipe\\.protein\\}g protein` : null,\\s*`\\$\\{recipe\\.carbs\\}g carbs`,\\s*`\\$\\{recipe\\.minutes\\} min`")''',
     '''    def test_dinner_cards_show_minutes_then_up_to_two_tags(self):
        _, _, js = self.get("/household.js")
        self.assertRegex(js, r"recipe\\.minutes \\? `\\$\\{recipe\\.minutes\\} min` : null,\\s*\\.\\.\\.\\(recipe\\.tags \\|\\| \\[\\]\\)\\.slice\\(0, 2\\)")'''),
    ('''        _, _, js = self.get("/app.js")
        self.assertIn("'/api/open'", js)
        self.assertIn("preventDefault()", js)
        self.assertIn("window.open(", js)
        self.assertEqual(js.count("recipeLink("), 3)  # definition + card + favorite chip''', '''        _, _, js = self.get("/app.js")
        self.assertIn("'/api/open'", js)
        self.assertIn("preventDefault()", js)
        self.assertIn("window.open(", js)
        self.assertEqual(js.count("recipeLink("), 1)  # the definition
        self.assertEqual(self.get("/household.js")[2].count("recipeLink("), 2)  # card + favorite chip'''),
    ('''        app_js = self.get("/app.js")[2]
        for label in ("Plan this dinner", "planFromRecipe(", "renderNudge()", "list:"):
            self.assertIn(label, app_js)
        self.assertEqual(app_js.count("recipeLink("), 3)
        self.assertEqual(app_js.count("href: recipe.url"), 1)''', '''        app_js = self.get("/app.js")[2]
        for label in ("renderNudge()", "list:"):
            self.assertIn(label, app_js)
        household_js = self.get("/household.js")[2]
        for label in ("Plan this dinner", "planFromRecipe("):
            self.assertIn(label, household_js)
        self.assertEqual(app_js.count("recipeLink("), 1)
        self.assertEqual(app_js.count("href: recipe.url"), 1)'''),
    ('''    def test_planned_dinner_card_is_marked_and_opens_its_plan(self):
        js = self.get("/app.js")[2]''', '''    def test_planned_dinner_card_is_marked_and_opens_its_plan(self):
        js = self.get("/household.js")[2]'''),
    ('''                      "SCREENS.length", "ArrowUp", "ArrowLeft"):''', '''                      "shown.length", "ArrowUp", "ArrowLeft"):'''),
])
print("tests patched")
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_household_web tests.test_web_assets -v`
Expected: all OK (two node-based tests are skipped when node is not installed).
Then `python -m unittest discover -s tests -t .` -> OK.

- [ ] **Step 6: Look at it in a browser**

```bash
export HOME_DASHBOARD_DATA="$(pwd -W)/.demo-data"
mkdir -p "$HOME_DASHBOARD_DATA" && cp examples/household.example.json "$HOME_DASHBOARD_DATA/household.json"
python server.py &
sleep 2
```

Open the address it prints (not 8765). Expected: header shows "Sample Household" above the clock; two sections, **Dinner** (blue ribbon) and **Lunch** (rose ribbon), each with three cards showing minutes and up to two tags, a Favorites row, and no "Chris", "V" or town names anywhere; weather in °F. The page does not scroll at 1920x1080. Then check it scales, in the browser console:

```javascript
const de = document.documentElement; JSON.stringify({w: innerWidth, h: innerHeight, zoom: de.style.zoom, stacked: de.classList.contains('stacked'), scrollH: de.scrollHeight, clientH: de.clientHeight})
```

At 1920x1080: zoom `"1"`, `scrollH` equals `clientH`. At 1366x768: zoom `"0.71"`, `scrollH` equals `clientH`. Stop the server as in Task 5.

- [ ] **Step 7: Commit**

```bash
git add web tests/webcase.py tests/test_household_web.py tests/test_web_assets.py
git commit -m "feat: meal sections, module switches and scale-to-fit layout"
```

---

### Task 8: Household, Rooms and Meals settings tabs

**Goal:** Settings gains Household, Rooms and Meals tabs that edit one draft and save it together, with a location search, a weekly cleaning-plan preview, meal and own-recipe editing, and a guard against losing unsaved changes.

**Files:**
- Modify: `web/household.js` (append part 2), `web/index.html`, `web/app.js`, `web/app.css` (through a patch script)
- Test: `tests/test_household_settings_web.py`

**Acceptance Criteria:**
- [ ] Settings has six tabs: Appearance, Household, Rooms, Meals, Repeating tasks, Dates
- [ ] Household tab: name, place search (with a manual coordinates fallback), temperature unit, module switches, Save changes, Discard changes, Run setup again
- [ ] Rooms tab: rooms with type and use, minutes goal, Show weekly plan, Save rooms, Save and rebuild cleaning plan
- [ ] Meals tab: add or remove meals, tick packs, tag filters, own recipes; a meal that is switched off disappears from the dashboard
- [ ] Closing Settings with unsaved changes is refused with a plain message; the idle timeout still closes it
- [ ] All new controls are at least 52px tall

**Verify:** `python -m unittest tests.test_household_settings_web tests.test_household_web tests.test_web_assets` -> OK; browser check below

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_household_settings_web.py`:

```python
from tests.webcase import WebCase


class HouseholdSettingsWebTests(WebCase):
    def test_settings_has_the_household_panels(self):
        page = self.get("/")[2]
        for markup in ('id="panel-household"', 'id="panel-rooms"', 'id="panel-meals"', 'id="saved-note"'):
            self.assertIn(markup, page)

    def test_household_js_editors(self):
        js = self.get("/household.js")[2]
        for label in ("function locationPicker", "function roomsEditor", "function mealsEditor", "function modulesEditor",
                      "/api/household", "/api/chores/preview", "/api/geocode", "Show weekly plan", "Save and rebuild cleaning plan",
                      "Run setup again", "Enter coordinates yourself", "+ Add your own recipe", "Discard changes"):
            self.assertIn(label, js)

    def test_app_js_has_six_tabs_and_guards_unsaved_changes(self):
        js = self.get("/app.js")[2]
        for label in ("'Household'", "'Rooms'", "'Meals'", "SETTINGS_PANELS", "householdDirty()", "closeSettings(true)", "startDraft()", "endDraft()"):
            self.assertIn(label, js)

    def test_new_form_targets_stay_large(self):
        for selector in (".text-input,.sheet select", ".check-row", ".form-actions .ghost,.form-actions .primary"):
            rule = self.css_rule(selector)
            self.assertGreaterEqual(int(rule["min-height"].removesuffix("px")), 52, selector)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_household_settings_web`
Expected: failures (no panels yet).

- [ ] **Step 3: Append the editors and Settings code to `web/household.js`**

Add this to the **end** of `web/household.js` (after `renderDinners`). It defines the form pieces, location picker, rooms and meals editors, the weekly plan preview, and the draft handling. It calls `openWizard`, which Task 9 adds; that only runs when someone presses Run setup again.

```javascript

// ---- Household editors, shared by Settings and the setup wizard ----
const MODULE_LABELS = [['weather', 'Weather'], ['tasks', "Today's tasks"], ['plans', 'Dinner plans'], ['shopping', 'Shopping list'], ['timers', 'Timers']];
const ROOM_PRESETS = [['Kitchen', 'kitchen'], ['Bedroom', 'bedroom'], ['Bathroom', 'bathroom'], ['Living room', 'living'], ['Office', 'office']];
const MEAL_NAMES = ['Dinner', 'Lunch', 'Breakfast', 'Snacks', 'Dessert', 'Kids meal'];
const MAX_MEALS = 6;
const DAY_LONG = {mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday', thu: 'Thursday', fri: 'Friday'};
let metaCache = null;
let draft = null;
let focusAfter = null;
let savedTimer = null;

async function ensureMeta() {
  if (!metaCache) metaCache = await api('GET', '/api/household/meta');
  return metaCache;
}

// ---- Small form pieces shared by Settings and the wizard ----
function textInput(label, value, onInput, attrs = {}) {
  return el('input', {type: 'text', class: 'text-input', 'aria-label': label, value, autocomplete: 'off', ...attrs, oninput: (event) => onInput(event.target.value)});
}

function fieldBox(label, ...kids) {
  return el('div', {class: 'field'}, el('label', {}, label), ...kids);
}

function choiceGroup(label, options, current, onPick) {
  const group = el('div', {class: 'seg', role: 'group', 'aria-label': label});
  for (const [value, text] of options) {
    const button = el('button', {
      type: 'button', 'aria-pressed': String(value === current),
      onclick: () => {
        for (const other of group.children) other.setAttribute('aria-pressed', String(other === button));
        onPick(value);
      },
    }, text);
    group.append(button);
  }
  return group;
}

function toggleRow(text, checked, onChange) {
  return el('label', {class: 'check-row'},
    el('input', {type: 'checkbox', checked, onchange: (event) => onChange(event.target.checked)}), text);
}

function actionRow(...buttons) {
  return el('div', {class: 'form-actions'}, ...buttons);
}

function uniqueName(existing, base) {
  const taken = new Set(existing.map((name) => name.toLowerCase()));
  let name = base;
  for (let n = 2; taken.has(name.toLowerCase()); n += 1) name = `${base} ${n}`;
  return name;
}

// ---- Location ----
function locationPicker(model, rerender) {
  const status = el('p', {class: 'note', role: 'status'});
  const results = el('div', {class: 'place-results'});
  const say = () => {
    status.textContent = model.location
      ? `Showing weather for ${model.location.label}.${model.location.alerts ? ' Severe weather alerts are on.' : ''}`
      : 'Type a city or ZIP code, then press Find.';
  };
  say();
  const input = textInput('City or ZIP code', '', () => {}, {placeholder: 'e.g. Portland, or 97201', maxlength: '60'});
  const pick = (place) => {
    model.location = place;
    results.replaceChildren();
    say();
    if (rerender) rerender();
  };
  const manual = el('details', {class: 'manual'}, el('summary', {}, 'Enter coordinates yourself'));
  const manualName = textInput('Place name', '', () => {}, {placeholder: 'e.g. Home', maxlength: '60'});
  const manualLat = textInput('Latitude', '', () => {}, {placeholder: 'Latitude, e.g. 45.52', inputmode: 'decimal'});
  const manualLon = textInput('Longitude', '', () => {}, {placeholder: 'Longitude, e.g. -122.68', inputmode: 'decimal'});
  const manualUs = el('input', {type: 'checkbox'});
  manual.append(manualName, manualLat, manualLon,
    el('label', {class: 'check-row'}, manualUs, 'This place is in the United States (turns on severe weather alerts)'),
    el('button', {
      type: 'button', class: 'ghost',
      onclick: () => pick({label: manualName.value.trim() || 'My home', lat: Number(manualLat.value), lon: Number(manualLon.value), alerts: manualUs.checked}),
    }, 'Use these'));
  async function find() {
    const query = input.value.trim();
    results.replaceChildren();
    if (query.length < 2) { status.textContent = 'Type at least two letters.'; return; }
    status.textContent = 'Looking...';
    try {
      const {places} = await api('POST', '/api/geocode', {q: query});
      status.textContent = places.length ? 'Pick your town:' : 'No match. Try a nearby bigger town, or enter coordinates below.';
      results.replaceChildren(...places.map((place) => el('button', {
        type: 'button', class: 'ghost place',
        onclick: () => pick({label: place.label, lat: place.lat, lon: place.lon, alerts: place.countryCode === 'US'}),
      }, place.label)));
    } catch (error) {
      status.textContent = error.detail || GENERIC_ERROR;
      manual.open = true;
    }
  }
  input.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); find(); } });
  return el('div', {},
    el('div', {class: 'find-row'}, input, el('button', {type: 'button', class: 'primary', onclick: find}, 'Find')),
    status, results, manual);
}

// ---- Rooms and the weekly cleaning plan ----
function roomsEditor(model, meta, rerender) {
  const kinds = meta.roomKinds;
  const list = el('div', {class: 'room-list'});
  model.rooms.forEach((room, index) => {
    list.append(el('div', {class: 'room-row'},
      textInput('Room name', room.name, (value) => { room.name = value; }, {placeholder: 'e.g. Kitchen', maxlength: '40', 'data-room': String(index)}),
      el('select', {'aria-label': 'Room type', onchange: (event) => { room.kind = event.target.value; }},
        kinds.map((k) => el('option', {value: k.kind, selected: k.kind === room.kind}, k.label))),
      choiceGroup('How much is it used?', [['high', 'Used a lot'], ['low', 'Used a little']], room.usage, (value) => { room.usage = value; }),
      el('button', {type: 'button', class: 'icon', 'aria-label': `Remove ${room.name || 'this room'}`, onclick: () => { model.rooms.splice(index, 1); rerender(); }}, glyph('x'))));
  });
  if (!model.rooms.length) list.append(el('p', {class: 'note'}, 'No rooms yet. Add the rooms you want on your cleaning plan.'));
  const add = (name, kind) => {
    model.rooms.push({name: uniqueName(model.rooms.map((r) => r.name), name), kind, usage: 'high'});
    focusAfter = `[data-room="${model.rooms.length - 1}"]`;
    rerender();
  };
  const presets = el('div', {class: 'chips'}, ROOM_PRESETS.map(([name, kind]) => el('button', {type: 'button', class: 'ghost', onclick: () => add(name, kind)}, `+ ${name}`)),
    el('button', {type: 'button', class: 'ghost', onclick: () => add('', 'other')}, '+ Another room'));
  const minutes = el('input', {
    type: 'number', class: 'text-input minutes', min: '10', max: '120', step: '5', value: String(model.choreMinutes), 'aria-label': 'Cleaning minutes per day',
    oninput: (event) => { model.choreMinutes = Number(event.target.value); },
  });
  return el('div', {}, fieldBox('About how many minutes a day for cleaning?', minutes), fieldBox('Your rooms', list, presets));
}

function planPreview(preview) {
  if (!preview) return el('p', {class: 'note'}, 'Press Show weekly plan to see what each day looks like.');
  const byDay = {};
  for (const task of preview.tasks) (byDay[task.day] = byDay[task.day] || []).push(task.title);
  return el('div', {class: 'plan-days'},
    preview.warnings.map((text) => el('p', {class: 'warn-note'}, text)),
    preview.days.map((day) => el('div', {class: 'plan-day'},
      el('h4', {}, `${DAY_LONG[day.day]}: ${day.minutes ? `about ${day.minutes} minutes` : 'a free day'}`),
      byDay[day.day] ? el('ul', {}, byDay[day.day].map((title) => el('li', {}, title))) : null)));
}

async function loadPreview(model, into) {
  into.replaceChildren(el('p', {class: 'note'}, 'Working it out...'));
  try {
    const preview = await api('POST', '/api/chores/preview', {rooms: model.rooms, choreMinutes: model.choreMinutes});
    into.replaceChildren(planPreview(preview));
  } catch (error) {
    into.replaceChildren(el('p', {class: 'warn-note', role: 'alert'}, error.detail || GENERIC_ERROR));
  }
}

// ---- Meals ----
function mealsEditor(model, meta, rerender) {
  const box = el('div', {});
  model.mealSlots.forEach((slot, index) => {
    const packs = meta.packs.length
      ? meta.packs.map((pack) => toggleRow(`${pack.name} (${pack.count} recipes)`, slot.packIds.includes(pack.id), (on) => {
        slot.packIds = on ? [...slot.packIds, pack.id] : slot.packIds.filter((id) => id !== pack.id);
      }))
      : [el('p', {class: 'note'}, 'No starter packs are installed. Add your own recipes below.')];
    const tags = el('div', {class: 'chips'}, meta.tags.map((tag) => el('button', {
      type: 'button', class: 'ghost', 'aria-pressed': String(slot.tagFilter.includes(tag)),
      onclick: (event) => {
        slot.tagFilter = slot.tagFilter.includes(tag) ? slot.tagFilter.filter((t) => t !== tag) : [...slot.tagFilter, tag];
        event.currentTarget.setAttribute('aria-pressed', String(slot.tagFilter.includes(tag)));
      },
    }, tag)));
    const own = slot.ownRecipes.map((recipe, at) => el('div', {class: 'own-row'},
      textInput('Recipe name', recipe.name, (value) => { recipe.name = value; }, {placeholder: 'Recipe name', maxlength: '100', 'data-own': `${index}-${at}`}),
      textInput('Recipe link', recipe.url, (value) => { recipe.url = value; }, {placeholder: 'https://...', maxlength: '500'}),
      el('input', {
        type: 'number', class: 'text-input minutes', min: '1', max: '600', placeholder: 'Minutes', 'aria-label': 'Minutes', value: recipe.minutes == null ? '' : String(recipe.minutes),
        oninput: (event) => { recipe.minutes = event.target.value === '' ? null : Number(event.target.value); },
      }),
      el('button', {type: 'button', class: 'icon', 'aria-label': `Remove ${recipe.name || 'this recipe'}`, onclick: () => { slot.ownRecipes.splice(at, 1); rerender(); }}, glyph('x'))));
    box.append(el('section', {class: 'slot-edit'},
      el('div', {class: 'slot-head'},
        textInput('Meal name', slot.name, (value) => { slot.name = value; }, {placeholder: 'e.g. Dinner', maxlength: '40', 'data-meal': String(index)}),
        toggleRow('Show on the dashboard', slot.enabled !== false, (on) => { slot.enabled = on; }),
        el('button', {type: 'button', class: 'icon', 'aria-label': `Remove ${slot.name || 'this meal'}`, onclick: () => { model.mealSlots.splice(index, 1); rerender(); }}, glyph('x'))),
      fieldBox('Recipe packs', ...packs),
      fieldBox('Only show recipes that are (leave all off to see everything)', tags),
      fieldBox('Your own recipes', ...own,
        el('button', {type: 'button', class: 'ghost', onclick: () => {
          slot.ownRecipes.push({name: '', url: '', minutes: null, tags: []});
          focusAfter = `[data-own="${index}-${slot.ownRecipes.length - 1}"]`;
          rerender();
        }}, '+ Add your own recipe'))));
  });
  if (!model.mealSlots.length) box.append(el('p', {class: 'note'}, 'No meals yet. Add one to get dinner ideas on your dashboard.'));
  if (model.mealSlots.length < MAX_MEALS) {
    box.append(el('button', {type: 'button', class: 'ghost', onclick: () => {
      model.mealSlots.push({name: uniqueName(model.mealSlots.map((s) => s.name), MEAL_NAMES.find((n) => !model.mealSlots.some((s) => s.name === n)) || 'Meal'), enabled: true, packIds: [], tagFilter: [], ownRecipes: []});
      focusAfter = `[data-meal="${model.mealSlots.length - 1}"]`;
      rerender();
    }}, '+ Add a meal'));
  }
  return box;
}

function modulesEditor(model) {
  return el('div', {}, MODULE_LABELS.map(([key, label]) => toggleRow(label, model.modules[key] !== false, (on) => { model.modules[key] = on; })));
}

// ---- Settings tabs: Household, Rooms, Meals (all edit one draft, saved together) ----
function startDraft() {
  draft = state && state.household ? cloneJson(state.household) : null;
}

function endDraft() {
  draft = null;
}

function householdDirty() {
  return Boolean(draft && state && state.household && JSON.stringify(draft) !== JSON.stringify(state.household));
}

function rebuildPanel(id, build) {
  const panel = $(id);
  const top = panel.scrollTop;
  panel.replaceChildren(build());
  panel.scrollTop = top;
  if (focusAfter) {
    const target = panel.querySelector(focusAfter);
    focusAfter = null;
    if (target) target.focus();
  }
}

function renderHouseholdPanels() {
  if (!draft) return;
  ensureMeta().then((meta) => {
    if (!draft) return;
    rebuildPanel('#panel-household', () => householdPanel());
    rebuildPanel('#panel-rooms', () => roomsPanel(meta));
    rebuildPanel('#panel-meals', () => mealsPanel(meta));
  }).catch(() => setError(GENERIC_ERROR));
}

function showSaved() {
  const note = $('#saved-note');
  note.textContent = 'Saved';
  clearTimeout(savedTimer);
  savedTimer = setTimeout(() => { note.textContent = ''; }, 4000);
}

async function saveDraft(regenerate) {
  try {
    state = await api('PUT', '/api/household', {household: draft, regenerateChores: regenerate});
    setError('');
    render();
    startDraft();
    renderHouseholdPanels();
    showSaved();
    refreshWeather();
  } catch (error) {
    setError(error.detail || GENERIC_ERROR);
  }
}

function discardDraft() {
  startDraft();
  renderHouseholdPanels();
}

function saveRow(...extra) {
  return actionRow(
    el('button', {type: 'button', class: 'primary', onclick: () => saveDraft(false)}, 'Save changes'), ...extra,
    el('button', {type: 'button', class: 'ghost', onclick: discardDraft}, 'Discard changes'));
}

function householdPanel() {
  return el('div', {},
    fieldBox('Household name', textInput('Household name', draft.name, (value) => { draft.name = value; }, {placeholder: 'e.g. The Smith Family', maxlength: '60'})),
    fieldBox('Where do you live?', locationPicker(draft, null)),
    fieldBox('Temperature', choiceGroup('Temperature', [['F', 'Fahrenheit'], ['C', 'Celsius']], draft.units.temperature, (value) => { draft.units.temperature = value; })),
    fieldBox('Show on the dashboard', modulesEditor(draft)),
    saveRow(el('button', {type: 'button', class: 'ghost', onclick: () => { closeSettings(true); openWizard(true); }}, 'Run setup again')));
}

function roomsPanel(meta) {
  const preview = el('div', {class: 'preview'}, planPreview(null));
  return el('div', {},
    roomsEditor(draft, meta, () => rebuildPanel('#panel-rooms', () => roomsPanel(meta))),
    el('div', {class: 'form-actions'}, el('button', {type: 'button', class: 'ghost', onclick: () => loadPreview(draft, preview)}, 'Show weekly plan')),
    preview,
    el('p', {class: 'note'}, 'Rebuilding replaces the cleaning tasks made from your rooms, including any of them left unfinished today. Tasks you added yourself are kept.'),
    actionRow(
      el('button', {type: 'button', class: 'primary', onclick: () => saveDraft(false)}, 'Save rooms'),
      el('button', {type: 'button', class: 'ghost', onclick: () => saveDraft(true)}, 'Save and rebuild cleaning plan'),
      el('button', {type: 'button', class: 'ghost', onclick: discardDraft}, 'Discard changes')));
}

function mealsPanel(meta) {
  return el('div', {}, mealsEditor(draft, meta, () => rebuildPanel('#panel-meals', () => mealsPanel(meta))), saveRow());
}
```

- [ ] **Step 4: Patch the page, app script and styles**

Save as `_patch_web_b.py`, run, delete:

```python
"""Task 7: Household, Rooms and Meals settings tabs. Each replacement must match exactly once."""
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


patch("web/index.html", [
    ('''      <div class="panel" id="panel-appearance" role="tabpanel"></div>
''', '''      <div class="panel" id="panel-appearance" role="tabpanel"></div>
      <div class="panel" id="panel-household" role="tabpanel" hidden></div>
      <div class="panel" id="panel-rooms" role="tabpanel" hidden></div>
      <div class="panel" id="panel-meals" role="tabpanel" hidden></div>
'''),
    ('''      <div class="sheet-foot"><button type="button" class="primary" id="settings-done">Done</button></div>''',
     '''      <div class="sheet-foot"><span id="saved-note" class="saved-note" role="status"></span><button type="button" class="primary" id="settings-done">Done</button></div>'''),
])

patch("web/app.js", [
    ('''  $('#panel-appearance').hidden = name !== 'appearance';
  $('#panel-rules').hidden = name !== 'rules';
  $('#panel-dates').hidden = name !== 'dates';
''', '''  for (const id of SETTINGS_PANELS) $('#panel-' + id).hidden = id !== name;
'''),
    ('''function selectTab(name, focus) {''', '''const SETTINGS_PANELS = ['appearance', 'household', 'rooms', 'meals', 'rules', 'dates'];

function selectTab(name, focus) {'''),
    ('''  settingsIdle = settingsOpen ? setTimeout(closeSettings, 4 * 60 * 1000) : null;''',
     '''  settingsIdle = settingsOpen ? setTimeout(() => closeSettings(true), 4 * 60 * 1000) : null;'''),
    ('''  if (!$('#dates-list')) buildDates();
''', '''  if (!$('#dates-list')) buildDates();
  startDraft();
  renderHouseholdPanels();
'''),
    ('''function closeSettings() {
  if (!settingsOpen) return;
  settingsOpen = false;
''', '''function closeSettings(force) {
  if (!settingsOpen) return;
  if (force !== true && householdDirty()) {
    setError('You have changes that are not saved yet. Save or discard them first.');
    return;
  }
  settingsOpen = false;
  endDraft();
'''),
    ('''  const tabs = [['appearance', 'Appearance'], ['rules', 'Repeating tasks'], ['dates', 'Dates']];''',
     '''  const tabs = [['appearance', 'Appearance'], ['household', 'Household'], ['rooms', 'Rooms'], ['meals', 'Meals'], ['rules', 'Repeating tasks'], ['dates', 'Dates']];'''),
])

with open("web/app.css", "a", encoding="utf-8") as css:
    css.write("""
/* Household editors shared by Settings and the setup wizard */
.lead{font-size:26px;margin:0 0 18px}
.text-input,.sheet select{min-height:56px;border:2px solid var(--line-strong);border-radius:16px;padding:0 16px;background:var(--card);font-size:24px;min-width:0;max-width:100%}
.text-input:focus,.sheet select:focus{outline:3px solid var(--accent);outline-offset:0;border-color:transparent}
.text-input::placeholder{color:var(--muted);font-style:italic;opacity:1}
.text-input.minutes{width:130px}
.check-row{display:flex;align-items:center;gap:16px;min-height:56px;font-size:24px}
.check-row input{flex:none;width:30px;height:30px;accent-color:var(--accent)}
.find-row{display:flex;gap:12px;align-items:center}
.find-row .text-input{flex:1}
.place-results{display:flex;flex-direction:column;gap:8px;margin:8px 0}
.place-results .ghost{text-align:left;white-space:normal}
details.manual{margin:12px 0}
details.manual summary{cursor:pointer;font-size:22px;color:var(--accent);min-height:52px;display:flex;align-items:center}
details.manual .text-input{display:block;margin:0 0 10px;width:100%}
.room-row,.own-row,.slot-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:0 0 12px}
.room-row .text-input,.own-row .text-input:not(.minutes),.slot-head .text-input{flex:1 1 220px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 14px}
.chips .ghost[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.slot-edit{border:2px solid var(--line);border-radius:20px;padding:16px 20px;margin:0 0 18px;background:var(--paper)}
.form-actions{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0 4px}
.form-actions .ghost,.form-actions .primary{min-height:56px}
.plan-days{display:grid;gap:12px;margin:12px 0}
.plan-day{border:2px solid var(--line);border-radius:16px;padding:10px 16px;background:var(--paper)}
.plan-day h4{margin:0}
.plan-day ul{margin:6px 0 0 22px;padding:0;list-style:disc;font-size:21px}
.warn-note{background:var(--warn);color:var(--warn-ink);border-radius:14px;padding:10px 16px;font-size:21px;margin:8px 0}
.saved-note{margin-right:auto;align-self:center;color:var(--ok);font-size:24px;font-weight:700}
.tabs{flex-wrap:wrap}
""")
print("web part B patched")
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_household_settings_web tests.test_household_web tests.test_web_assets -v`
Expected: all OK. Then the full suite -> OK.

- [ ] **Step 6: Try it in a browser**

Start the server with the example household as in Task 7 Step 6 and open the printed address. Click the gear and check:

1. Six tabs fit on one row at 1366x768.
2. **Meals**: press `+ Add a meal`; a new meal named "Lunch" or the next free name appears and its name field has focus. Close Settings with the unsaved change: it stays open and shows "You have changes that are not saved yet. Save or discard them first." Tick a pack, press **Save changes**: "Saved" appears and the dashboard gains that section. Untick **Show on the dashboard** and save: the section disappears.
3. **Household**: choose Celsius, switch off Weather and Timers, save. The weather block and the Timers tab disappear and the header relaxes; temperatures show °C once the weather reloads.
4. **Rooms**: remove all rooms, press `+ Kitchen`, press **Show weekly plan** (Monday shows about 28 minutes, the other days "a free day"), then **Save and rebuild cleaning plan**. On a Monday the kitchen tasks appear in Today's tasks; on other days the list stays empty (they are Monday tasks).

Stop the server as in Task 5.

- [ ] **Step 7: Commit**

```bash
git add web tests/test_household_settings_web.py
git commit -m "feat: household, rooms and meals settings tabs"
```

---

### Task 9: Setup wizard

**Goal:** A first-run wizard walks a new household through name, place, rooms, the weekly cleaning plan, meals and modules, then opens their dashboard; the same wizard is reachable from Settings as Run setup again.

**Files:**
- Create: `web/wizard.js`, `tests/test_wizard_web.py`
- Modify: `web/index.html`, `web/app.js`, `web/app.css` (through a patch script)

**Acceptance Criteria:**
- [ ] A fresh data folder opens the wizard automatically and the background is locked (inert) while it is open
- [ ] Seven steps with Back and Next; Next on the name and place steps explains in plain words what is missing
- [ ] The place step searches by city or ZIP, lists matches, and offers manual coordinates if the lookup fails
- [ ] The plan step shows the Monday to Friday preview from the server; the meals step pre-selects the `family-classics` pack when it exists
- [ ] Finishing saves the household with `regenerateChores: true`, closes the wizard and shows the dashboard
- [ ] Re-running from Settings pre-fills everything, has Cancel (and Escape), and keeps favorites and hidden recipes

**Verify:** `python -m unittest tests.test_wizard_web` -> OK, full suite -> OK; browser walkthrough below

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_wizard_web.py`:

```python
from tests.webcase import WebCase


class WizardWebTests(WebCase):
    def test_wizard_markup_and_script_order(self):
        page = self.get("/")[2]
        for markup in ('id="wizard"', 'src="wizard.js"'):
            self.assertIn(markup, page)
        self.assertLess(page.index('src="household.js"'), page.index('src="wizard.js"'))
        self.assertLess(page.index('src="wizard.js"'), page.index('src="app.js"'))

    def test_wizard_js_is_served_and_safe(self):
        self.assert_scripts_safe("wizard.js")
        text = self.get("/wizard.js")[2]
        for word in ("Chris", "Huntsville", "Alabama"):
            self.assertNotIn(word, text)

    def test_wizard_js_steps(self):
        js = self.get("/wizard.js")[2]
        for label in ("WIZARD_STEPS", "Welcome! Let us set up your dashboard", "Where do you live?", "Which rooms should we clean?",
                      "Your weekly cleaning plan", "What meals do you want ideas for?", "Open my dashboard", "regenerateChores: true",
                      "inert"):
            self.assertIn(label, js)

    def test_first_run_opens_the_wizard(self):
        js = self.get("/app.js")[2]
        self.assertIn("state.needsSetup", js)
        self.assertIn("openWizard(false)", js)

    def test_wizard_buttons_stay_large(self):
        rule = self.css_rule(".wiz-nav .ghost,.wiz-nav .primary")
        self.assertGreaterEqual(int(rule["min-height"].removesuffix("px")), 52)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_wizard_web`
Expected: failures (no wizard).

- [ ] **Step 3: Create `web/wizard.js`**

```javascript
'use strict';

// The first-run setup wizard, also reached from Settings > Household > "Run setup again".
// Loaded before app.js; it uses household.js and app.js helpers only when a function runs.

const WIZARD_STEPS = ['welcome', 'place', 'rooms', 'plan', 'meals', 'modules', 'done'];
const WIZARD_LOCKED = ['.top', 'main', '#plans-view', '#shopping-view', '#timers-view'];
let wizard = null;

function blankHousehold() {
  return {
    name: '',
    location: null,
    units: {temperature: 'F'},
    modules: {weather: true, tasks: true, plans: true, shopping: true, timers: true},
    rooms: [
      {name: 'Kitchen', kind: 'kitchen', usage: 'high'},
      {name: 'Bedroom', kind: 'bedroom', usage: 'high'},
      {name: 'Bathroom', kind: 'bathroom', usage: 'high'},
      {name: 'Living room', kind: 'living', usage: 'high'},
    ],
    choreMinutes: 30,
    mealSlots: [{name: 'Dinner', enabled: true, packIds: [], tagFilter: [], ownRecipes: []}],
  };
}

function wizardLoading() {
  return el('p', {class: 'note'}, 'Loading...');
}

function wizardLead(text) {
  return el('p', {class: 'lead'}, text);
}

const WIZARD_BUILDERS = {
  welcome: () => ({
    title: wizard.rerun ? 'Update your household' : 'Welcome! Let us set up your dashboard',
    body: el('div', {},
      wizardLead('A few quick questions and your dashboard will be ready. You can change any answer later in Settings.'),
      fieldBox('What should we call your household?', textInput('Household name', wizard.model.name, (value) => { wizard.model.name = value; }, {
        placeholder: 'e.g. The Smith Family', maxlength: '60', onkeydown: (event) => { if (event.key === 'Enter') { event.preventDefault(); wizardNext(); } },
      }))),
    check: () => (wizard.model.name.trim() ? '' : 'Type a name for your household to continue.'),
  }),
  place: () => ({
    title: 'Where do you live?',
    body: el('div', {},
      wizardLead('We use this to show your weather.'),
      locationPicker(wizard.model, null),
      fieldBox('Temperature', choiceGroup('Temperature', [['F', 'Fahrenheit'], ['C', 'Celsius']], wizard.model.units.temperature, (value) => { wizard.model.units.temperature = value; }))),
    check: () => (wizard.model.location ? '' : 'Find your town and pick it from the list to continue.'),
  }),
  rooms: () => ({
    title: 'Which rooms should we clean?',
    body: wizard.meta
      ? el('div', {}, wizardLead('We spread them over Monday to Friday and keep weekends free.'), roomsEditor(wizard.model, wizard.meta, () => renderWizard(true)))
      : wizardLoading(),
    check: () => '',
  }),
  plan: () => {
    const holder = el('div', {});
    loadPreview(wizard.model, holder);
    return {
      title: 'Your weekly cleaning plan',
      body: el('div', {}, wizardLead('Here is what we built. Go back to change your rooms, or fine-tune it later in Settings.'), holder),
      check: () => '',
    };
  },
  meals: () => ({
    title: 'What meals do you want ideas for?',
    body: wizard.meta
      ? el('div', {}, wizardLead('Pick recipe packs for each meal, or add your own recipes.'), mealsEditor(wizard.model, wizard.meta, () => renderWizard(true)))
      : wizardLoading(),
    check: () => '',
  }),
  modules: () => ({
    title: 'What do you want on your dashboard?',
    body: el('div', {}, wizardLead('Turn off anything you will not use. Your meals are set up in the step before.'), modulesEditor(wizard.model)),
    check: () => '',
  }),
  done: () => {
    const model = wizard.model;
    const meals = model.mealSlots.filter((slot) => slot.enabled !== false).map((slot) => slot.name);
    return {
      title: 'All set',
      body: el('div', {},
        wizardLead('Here is your dashboard setup. Press the button to start using it.'),
        el('ul', {class: 'summary'},
          el('li', {}, `Household: ${model.name}`),
          el('li', {}, `Weather for ${model.location ? model.location.label : 'your town'}, in degrees ${model.units.temperature}`),
          el('li', {}, `${model.rooms.length} ${model.rooms.length === 1 ? 'room' : 'rooms'} on your cleaning plan`),
          el('li', {}, `Meals: ${meals.length ? meals.join(', ') : 'none'}`))),
      check: () => '',
    };
  },
};

async function openWizard(rerun) {
  if (wizard) return;
  wizard = {step: 0, rerun: Boolean(rerun), model: rerun && state.household ? cloneJson(state.household) : blankHousehold(), meta: null, error: '', current: null};
  for (const selector of WIZARD_LOCKED) $(selector).inert = true;
  document.documentElement.classList.add('locked');
  $('#wizard').hidden = false;
  renderWizard(false);
  try {
    const meta = await ensureMeta();
    if (!wizard) return;
    wizard.meta = meta;
    const first = wizard.model.mealSlots[0];
    if (!rerun && first && !first.packIds.length && meta.packs.length) {
      first.packIds = [(meta.packs.find((pack) => pack.id === 'family-classics') || meta.packs[0]).id];
    }
  } catch (error) {
    wizard.error = GENERIC_ERROR;
  }
  renderWizard(true);
}

function closeWizard() {
  wizard = null;
  $('#wizard').hidden = true;
  $('#wizard').replaceChildren();
  for (const selector of WIZARD_LOCKED) $(selector).inert = false;
  document.documentElement.classList.remove('locked');
  $('#gear').focus();
}

function renderWizard(keepFocus) {
  if (!wizard) return;
  const old = $('#wizard .wiz-body');
  const top = old ? old.scrollTop : 0;
  const last = wizard.step === WIZARD_STEPS.length - 1;
  wizard.current = WIZARD_BUILDERS[WIZARD_STEPS[wizard.step]]();
  const heading = el('h2', {tabindex: '-1'}, wizard.current.title);
  const back = wizard.step > 0
    ? el('button', {type: 'button', class: 'ghost', onclick: wizardBack}, 'Back')
    : wizard.rerun ? el('button', {type: 'button', class: 'ghost', onclick: closeWizard}, 'Cancel') : el('span');
  $('#wizard').replaceChildren(el('div', {class: 'sheet wizard-sheet', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Set up your dashboard'},
    el('p', {class: 'wiz-progress'}, `Step ${wizard.step + 1} of ${WIZARD_STEPS.length}`),
    heading,
    el('div', {class: 'wiz-body'}, wizard.current.body),
    wizard.error ? el('p', {class: 'warn-note', role: 'alert'}, wizard.error) : null,
    el('div', {class: 'wiz-nav'}, back, el('button', {type: 'button', class: 'primary', id: 'wiz-next', onclick: wizardNext}, last ? 'Open my dashboard' : 'Next'))));
  const body = $('#wizard .wiz-body');
  if (keepFocus) {
    body.scrollTop = top;
    const target = focusAfter ? body.querySelector(focusAfter) : null;
    focusAfter = null;
    if (target) target.focus();
  } else {
    heading.focus();
  }
}

function wizardBack() {
  if (!wizard || wizard.step === 0) return;
  wizard.error = '';
  wizard.step -= 1;
  renderWizard(false);
}

async function wizardNext() {
  if (!wizard) return;
  const problem = wizard.current.check();
  if (problem) {
    wizard.error = problem;
    renderWizard(true);
    return;
  }
  wizard.error = '';
  if (wizard.step < WIZARD_STEPS.length - 1) {
    wizard.step += 1;
    renderWizard(false);
    return;
  }
  $('#wiz-next').disabled = true;
  try {
    state = await api('PUT', '/api/household', {household: wizard.model, regenerateChores: true});
    closeWizard();
    setError('');
    render();
    refreshWeather();
  } catch (error) {
    wizard.error = error.detail || GENERIC_ERROR;
    renderWizard(true);
  }
}

document.addEventListener('keydown', (event) => {
  if (wizard && wizard.rerun && event.key === 'Escape') {
    event.preventDefault();
    closeWizard();
  }
});
```

- [ ] **Step 4: Patch the page, app script and styles**

Save as `_patch_web_c.py`, run, delete:

```python
"""Task 8: the setup wizard. Each replacement must match exactly once."""
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, f"{path}: expected one match for {old[:70]!r}, found {text.count(old)}"
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


patch("web/index.html", [
    ('''  <div id="error" class="error" role="alert" hidden></div>''', '''  <div id="wizard" class="overlay" hidden></div>
  <div id="error" class="error" role="alert" hidden></div>'''),
    ('''  <script src="household.js"></script>
''', '''  <script src="household.js"></script>
  <script src="wizard.js"></script>
'''),
])

patch("web/app.js", [
    ('''  renderHousehold();
  renderDinners();
''', '''  renderHousehold();
  renderDinners();
  if (state.needsSetup) openWizard(false);
'''),
])

with open("web/app.css", "a", encoding="utf-8") as css:
    css.write("""
/* Setup wizard */
.wizard-sheet{width:min(960px,100%)}
.wiz-progress{margin:0;font:italic 700 24px "Palatino Linotype",Palatino,Georgia,serif;color:var(--muted)}
.wiz-body{flex:1;min-height:0;overflow:auto;padding:4px 8px 0 4px;scrollbar-width:thin}
.wiz-nav{flex:none;display:flex;justify-content:space-between;gap:16px;padding-top:18px;border-top:2px dashed var(--line);margin-top:14px}
.wiz-nav .ghost,.wiz-nav .primary{min-height:64px;min-width:160px;font-size:26px}
.summary{margin:0 0 0 24px;padding:0;list-style:disc;font-size:26px;line-height:1.6}
""")
print("web part C patched")
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest discover -s tests -t .`
Expected: all OK.

- [ ] **Step 6: Walk through it in a browser (needs internet for the place search)**

Start the server with an **empty** data folder (do not copy the example household):

```bash
export HOME_DASHBOARD_DATA="$(pwd -W)/.demo-data"
rm -rf "$HOME_DASHBOARD_DATA" && mkdir -p "$HOME_DASHBOARD_DATA"
python server.py &
sleep 2
```

Open the printed address. Expected: the wizard opens full screen at "Step 1 of 7".

1. Type a household name, press Next. Press Next with the name empty first: it says "Type a name for your household to continue."
2. Type `Portland`, press Find: six matches starting with "Portland, Oregon, United States". Pick one: the note says severe weather alerts are on. Next.
3. Rooms: four example rooms are pre-filled. Next.
4. Plan: Monday about 28 minutes, Tuesday 26, Wednesday 24, Thursday 24, Friday a free day. Next.
5. Meals: "Dinner" with "Family classics" ticked. Next, Next.
6. Summary lists the name, "Weather for Portland, Oregon, United States, in degrees F", "4 rooms", "Meals: Dinner". Press **Open my dashboard**.
7. Expected: wizard closes; the tab title is "<name> - Home"; one Dinner section with three cards; weather matches the chosen town (not any other town).
8. Open Settings, Household, **Run setup again**: the wizard opens pre-filled with a Cancel button; Escape closes it.

Also check `%APPDATA%`-style data: `.demo-data/household.json` exists and holds the chosen place. Stop the server as in Task 5.

- [ ] **Step 7: Commit**

```bash
git add web tests/test_wizard_web.py
git commit -m "feat: first-run setup wizard"
```

---

### Task 10: Check the layout at four window sizes

**Goal:** The scaled and stacked layouts are confirmed (and fixed if needed) at wall-display, laptop, tablet and phone-sized windows, including a household with three meals.

**Files:**
- Modify (only if a check fails): `web/household.js`, `web/app.css`

**Acceptance Criteria:**
- [ ] 1920x1080: zoom 1, no scrolling
- [ ] 1366x768 and 1280x720: zoom about 0.71 and 0.67, no scrolling
- [ ] 1024x768 and 768x1024: stacked single column that scrolls vertically with no horizontal overflow
- [ ] With three meals at 1920x1080 the page itself does not scroll; the meal column scrolls inside itself and text size is unchanged
- [ ] A wizard step and a Settings tab are fully usable (nothing cut off) at 1366x768 and 768x1024

**Verify:** The console check below reports the expected values at each size

**Steps:**

- [ ] **Step 1: Start the example household** (as in Task 7 Step 6) and open it in a browser whose window or viewport can be set to specific sizes.

- [ ] **Step 2: Measure each size**

For each size below, set the viewport, reload, wait a second, then run in the console:

```javascript
const de = document.documentElement; JSON.stringify({w: innerWidth, h: innerHeight, zoom: de.style.zoom, stacked: de.classList.contains('stacked'), scrollH: de.scrollHeight, clientH: de.clientHeight, scrollW: de.scrollWidth, clientW: de.clientWidth})
```

| Size | Expected |
|---|---|
| 1920x1080 | `zoom "1"`, `stacked false`, `scrollH == clientH` |
| 1366x768 | `zoom "0.71"`, `stacked false`, `scrollH == clientH` |
| 1280x720 | `zoom "0.67"`, `stacked false`, `scrollH == clientH` |
| 1024x768 | `zoom "0.93"`, `stacked true`, `scrollW == clientW` |
| 768x1024 | `zoom "0.7"`, `stacked true`, `scrollW == clientW` (and `scrollH > clientH`: it scrolls) |

- [ ] **Step 3: Three meals**

In Settings, Meals, add a third meal with a pack ticked and save. At 1920x1080 run `document.querySelector('#dinners').scrollHeight > document.querySelector('#dinners').clientHeight` -> `true`, and confirm the page itself still has `scrollH == clientH`. Card text must look the same size as with two meals.

- [ ] **Step 4: Eyeball the screens**

At 1366x768 and 768x1024 open the wizard (Settings, Household, Run setup again) and each Settings tab. Nothing may be cut off, overlap, or need sideways scrolling; buttons stay easy to tap. Fix any problem in `web/app.css` (or `fitScreen` in `web/household.js`), keep the Step 2 numbers true, and re-run `python -m unittest discover -s tests -t .`.

- [ ] **Step 5: Reset and commit** (only if you changed files)

Reset the browser viewport to its normal size and stop the server (Task 5 Step 5).

```bash
git add web
git commit -m "fix: layout adjustments from the window-size check"
```

If nothing needed fixing, there is nothing to commit; note the measured values in the report.

---

### Task 11: Launcher

**Goal:** One entry point that the installed app runs: it starts the server if it is not already running, records its port, and opens the dashboard fullscreen in Edge (or the default browser).

**Files:**
- Create: `launcher.py`
- Test: `tests/test_launcher.py`

**Acceptance Criteria:**
- [ ] A second launch finds the running dashboard through `port.txt` and only opens the browser
- [ ] A stale, missing or garbage `port.txt` means nothing is running
- [ ] Edge starts with `--kiosk`, fullscreen and its own profile folder; without Edge the default browser is used
- [ ] `HOME_DASHBOARD_NO_BROWSER=1` opens nothing (used by the build smoke test)

**Verify:** `python -m unittest tests.test_launcher` -> 7 tests OK

**Steps:**

- [ ] **Step 1: Write the tests**

Create `tests/test_launcher.py`:

```python
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import launcher
import server


class LauncherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        patcher = mock.patch.dict(os.environ, {"HOME_DASHBOARD_DATA": self.dir})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_port_file_means_nothing_is_running(self):
        self.assertIsNone(launcher.running_port())

    def test_a_stale_or_garbage_port_file_means_nothing_is_running(self):
        Path(self.dir, "port.txt").write_text("not a number")
        self.assertIsNone(launcher.running_port())
        Path(self.dir, "port.txt").write_text("1")
        self.assertIsNone(launcher.running_port())

    def test_a_live_dashboard_is_found_through_the_port_file(self):
        httpd = launcher.open_server_and_record()
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.assertEqual(launcher.running_port(), httpd.server_address[1])
        self.assertEqual(Path(self.dir, "port.txt").read_text(), str(httpd.server_address[1]))

    def test_edge_is_started_fullscreen_with_its_own_profile(self):
        command = launcher.edge_command("msedge.exe", "http://127.0.0.1:8765", "C:/profile")
        self.assertEqual(command[:3], ["msedge.exe", "--kiosk", "http://127.0.0.1:8765"])
        self.assertIn("--edge-kiosk-type=fullscreen", command)
        self.assertIn("--user-data-dir=C:/profile", command)

    def test_without_edge_the_default_browser_is_used(self):
        with mock.patch.object(launcher, "edge_path", return_value=None), mock.patch.object(launcher.webbrowser, "open") as opened:
            launcher.open_fullscreen("http://127.0.0.1:8765")
        opened.assert_called_once_with("http://127.0.0.1:8765")

    def test_no_browser_switch_opens_nothing(self):
        with mock.patch.dict(os.environ, {"HOME_DASHBOARD_NO_BROWSER": "1"}),                 mock.patch.object(launcher.subprocess, "Popen") as popen, mock.patch.object(launcher.webbrowser, "open") as opened:
            launcher.open_fullscreen("http://127.0.0.1:8765")
        popen.assert_not_called()
        opened.assert_not_called()

    def test_second_launch_only_opens_the_browser(self):
        with mock.patch.object(launcher, "running_port", return_value=8770), \
                mock.patch.object(launcher, "open_fullscreen") as opened, \
                mock.patch.object(server, "build_app") as build:
            launcher.main()
        opened.assert_called_once_with("http://127.0.0.1:8770")
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m unittest tests.test_launcher`
Expected: `ModuleNotFoundError: No module named 'launcher'`.

- [ ] **Step 3: Implement**

Create `launcher.py`:

```python
"""What the installed app runs: start the dashboard server if it is not already running, then open it fullscreen."""
import os
import shutil
import subprocess
import threading
import urllib.request
import webbrowser
from pathlib import Path

import server
from dashboard import paths

EDGE_FALLBACKS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def port_file():
    return paths.data_dir() / "port.txt"


def is_dashboard(port):
    try:
        with urllib.request.urlopen(f"http://{server.HOST}:{port}/api/state", timeout=2) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def running_port():
    """The port of a dashboard that is already running for this household, or None."""
    try:
        port = int(port_file().read_text().strip())
    except (OSError, ValueError):
        return None
    return port if is_dashboard(port) else None


def edge_path():
    return shutil.which("msedge") or next((p for p in EDGE_FALLBACKS if Path(p).is_file()), None)


def edge_command(edge, url, profile_dir):
    return [edge, "--kiosk", url, "--edge-kiosk-type=fullscreen", "--no-first-run", f"--user-data-dir={profile_dir}"]


def open_fullscreen(url):
    if os.environ.get("HOME_DASHBOARD_NO_BROWSER"):  # lets the build smoke test run without a window
        return
    edge = edge_path()
    if edge:
        profile = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HomeDashboardKiosk"
        subprocess.Popen(edge_command(edge, url, profile))
    else:
        webbrowser.open(url)


def main():
    port = running_port()
    if port is not None:
        open_fullscreen(f"http://{server.HOST}:{port}")
        return
    httpd = open_server_and_record()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    open_fullscreen(f"http://{server.HOST}:{httpd.server_address[1]}")
    thread.join()


def open_server_and_record():
    httpd = server.open_server(server.build_app())
    port_file().parent.mkdir(parents=True, exist_ok=True)
    port_file().write_text(str(httpd.server_address[1]))
    return httpd


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests**

Run: `python -m unittest tests.test_launcher -v`
Expected: `Ran 7 tests`, `OK`.

- [ ] **Step 5: Commit**

```bash
git add launcher.py tests/test_launcher.py
git commit -m "feat: launcher that starts the server once and opens it fullscreen"
```

---

### Task 12: Packaging (PyInstaller and Inno Setup)

**Goal:** A build script produces a self-contained `HomeDashboard.exe` folder (and an installer when Inno Setup 6 is available), and a smoke test proves the built app serves the dashboard and asks for first-run setup.

**Files:**
- Create: `packaging/HomeDashboard.spec`, `packaging/build.ps1`, `packaging/smoke_test.ps1`, `packaging/installer.iss`

**Acceptance Criteria:**
- [ ] `build.ps1` makes `dist\HomeDashboard\HomeDashboard.exe` with the web files and packs bundled and no console window
- [ ] `smoke_test.ps1` prints `OK: ... served the page, asked for setup, and listed 4 starter packs` and leaves no process running
- [ ] The build never touches the global Python (uses `.venv-build`) and never writes inside the install or data folders
- [ ] If Inno Setup 6 is installed, `dist\HomeDashboard-Setup-1.0.0.exe` is produced; if not, the report says the installer script is uncompiled

**Verify:** `powershell -ExecutionPolicy Bypass -File packaging\smoke_test.ps1` -> `OK: http://127.0.0.1:87xx served the page, asked for setup, and listed 4 starter packs`

**Steps:**

- [ ] **Step 1: Create the packaging files**

Create `packaging/HomeDashboard.spec`:

```python
# PyInstaller spec: one folder holding HomeDashboard.exe (no console window) with the web files and starter packs.
# Build with packaging/build.ps1. SPECPATH is provided by PyInstaller.
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    datas=[(str(root / "web"), "web"), (str(root / "packs"), "packs")],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HomeDashboard", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="HomeDashboard")
```

Create `packaging/build.ps1`:

```powershell
# Builds dist\HomeDashboard\ (PyInstaller) and, when Inno Setup is installed, dist\HomeDashboard-Setup-<version>.exe.
# Usage: powershell -ExecutionPolicy Bypass -File packaging\build.ps1 [-Version 1.0.0]
param([string]$Version = "1.0.0")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

python -m pip install --quiet pyinstaller
python -m PyInstaller --noconfirm --distpath dist --workpath build packaging\HomeDashboard.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$candidates = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source,
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if ($candidates) {
    & $candidates[0] "/DAppVersion=$Version" packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    Write-Host "Installer: dist\HomeDashboard-Setup-$Version.exe"
} else {
    Write-Warning "Inno Setup 6 is not installed, so only dist\HomeDashboard\ was built. Install it with: winget install JRSoftware.InnoSetup"
}
```

Create `packaging/smoke_test.ps1`:

```powershell
# Starts the built app against a throwaway data folder and checks it serves the dashboard, then stops it.
# Usage: powershell -ExecutionPolicy Bypass -File packaging\smoke_test.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$exe = Join-Path $root "dist\HomeDashboard\HomeDashboard.exe"
if (-not (Test-Path $exe)) { throw "Build first: $exe not found" }

$data = Join-Path ([IO.Path]::GetTempPath()) ("hd-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $data | Out-Null
$env:HOME_DASHBOARD_DATA = $data
$env:HOME_DASHBOARD_NO_BROWSER = "1"
$process = Start-Process -FilePath $exe -PassThru
try {
    $portFile = Join-Path $data "port.txt"
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Test-Path $portFile) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }
    if (-not (Test-Path $portFile)) { throw "The app never wrote port.txt" }
    $base = "http://127.0.0.1:" + (Get-Content $portFile -Raw).Trim()

    $page = Invoke-WebRequest -UseBasicParsing "$base/"
    if ($page.Content -notmatch 'id="dinners"') { throw "The page is missing the dinners container" }
    $state = Invoke-RestMethod "$base/api/state"
    if (-not $state.needsSetup) { throw "A fresh data folder should need setup" }
    $meta = Invoke-RestMethod "$base/api/household/meta"
    if ($meta.packs.Count -lt 4) { throw "Expected at least 4 starter packs, found $($meta.packs.Count)" }
    Write-Host "OK: $base served the page, asked for setup, and listed $($meta.packs.Count) starter packs"
}
finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    Remove-Item -Recurse -Force $data -ErrorAction SilentlyContinue
}
```

Create `packaging/installer.iss`:

```ini
; Inno Setup script. Build with packaging\build.ps1 (it passes /DAppVersion=...).
; Installs for the current user (no administrator prompt), adds a Start Menu entry and a Startup entry so the
; dashboard opens at sign-in. A household's own files live in %APPDATA%\HomeDashboard and are never touched.
#define AppName "Home Dashboard"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B6E1C7A4-5D1F-4F0B-9C3A-6B7F1E2D8A10}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\HomeDashboard
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=HomeDashboard-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
CloseApplications=force
UninstallDisplayName={#AppName}

[Files]
Source: "..\dist\HomeDashboard\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\HomeDashboard.exe"
Name: "{userstartup}\{#AppName}"; Filename: "{app}\HomeDashboard.exe"

[Run]
Filename: "{app}\HomeDashboard.exe"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM HomeDashboard.exe"; Flags: runhidden; RunOnceId: "StopHomeDashboard"
```

- [ ] **Step 2: Build in an isolated virtualenv** (PowerShell)

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Version 1.0.0
```

Expected: `Build complete!` and a `dist\HomeDashboard\` folder of about 20 MB containing `HomeDashboard.exe`. Without Inno Setup the script ends with a warning that only the folder was built; that is fine for now.

- [ ] **Step 3: Smoke-test the built app** (PowerShell, same session)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\smoke_test.ps1
```

Expected: `OK: http://127.0.0.1:87xx served the page, asked for setup, and listed 4 starter packs`. If the live dashboard owns 8765 the port will be 8766 or higher: that is correct. Afterwards `Get-Process HomeDashboard` finds nothing.

- [ ] **Step 4: Compile the installer (ask the user first)**

Ask the user whether to install Inno Setup 6 (`winget install JRSoftware.InnoSetup`) so the installer script can be compiled. If they agree, install it, re-run `packaging\build.ps1 -Version 1.0.0` and confirm `dist\HomeDashboard-Setup-1.0.0.exe` exists. **Do not run that installer on this machine**: it would add Start Menu and Startup entries here. A real install test belongs on a clean Windows machine or VM (spec open item 1). If the user declines, record that `packaging\installer.iss` is uncompiled and untested.

- [ ] **Step 5: Commit**

```bash
git add packaging
git commit -m "feat: PyInstaller build, Inno Setup script and build smoke test"
```

---

### Task 13: Docs, scrub and release check

**Goal:** The repo is documented for developers and for households, contains nothing from the original household, and everything is pushed.

**Files:**
- Create: `README.md`, `PRODUCT.md`, `docs/INSTALL.md`

**Acceptance Criteria:**
- [ ] README explains what the app is, how to run, test and build it, and the folder layout; INSTALL.md walks a non-technical household through install and first run, including the SmartScreen warning
- [ ] A search of the repo (excluding `.git`, `docs/superpowers`, build output) finds the original household's names, town or coordinates only inside the two tests that assert their absence
- [ ] The full test suite passes
- [ ] `origin/main` has all commits

**Verify:** `python -m unittest discover -s tests -t .` -> OK; the scrub search below prints only the two allowed files

**Steps:**

- [ ] **Step 1: Write the docs**

Create `README.md`:

````markdown
# Household Dashboard

A calm, always-on screen for your household: today's weather, a daily to-do list with a cleaning plan built from your own rooms, and rotating dinner ideas. It runs on your own Windows computer. Nothing is sent to an account or a cloud service.

A first-run wizard sets everything up (name, town, rooms, meals). Settings, behind the gear icon, changes any of it later.

## What you get

- **Weather** for your town, with a 3-day outlook, an optional severe weather banner (US only), and automatic light and dark by sunrise and sunset.
- **Today's tasks**: repeating tasks, your weekly cleaning plan, one-off tasks, "Move to tomorrow", and an undo bar.
- **Meals**: any number of meals (Dinner, Lunch, ...), three ideas each per day, drawn from starter packs and your own recipes. Favorite, hide, or swap any idea.
- **Dinner plans, a shopping list and timers**, each of which can be switched off.
- Sized for a wall display, but it scales to a laptop, a TV or a tablet.

## For households: install it

See [docs/INSTALL.md](docs/INSTALL.md).

## For developers

Needs Python 3.11 or newer. The app itself uses only the standard library.

```bash
python server.py            # http://127.0.0.1:8765 (next free port up to 8774)
python -m unittest discover -s tests -t .
python scripts/check_links.py   # opens every recipe link in packs/
```

Your own data goes to `%APPDATA%\HomeDashboard`. To keep a test run separate, set `HOME_DASHBOARD_DATA` to any folder. `DASHBOARD_TODAY=2026-10-05` pins the date.

Build the installer (Windows):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Version 1.0.0
powershell -ExecutionPolicy Bypass -File packaging\smoke_test.ps1
```

`build.ps1` makes `dist\HomeDashboard\` with PyInstaller, and `dist\HomeDashboard-Setup-<version>.exe` too when Inno Setup 6 is installed (`winget install JRSoftware.InnoSetup`).

### Layout

| Path | What it holds |
|---|---|
| `launcher.py` | What the installed app runs |
| `server.py` | HTTP server and static files |
| `dashboard/` | Logic modules; `api.py` routes requests |
| `web/` | The page: `index.html`, `app.css`, `app.js`, `household.js`, `wizard.js`, ... |
| `packs/` | Starter recipe packs |
| `packaging/` | PyInstaller and Inno Setup files |
| `docs/superpowers/` | Design spec and implementation plan |

### Adding or changing a starter pack

Packs are plain JSON in `packs/`. Each recipe has an `id`, `name`, `url`, `minutes` and `tags` (from the list in `dashboard/packs.py`). Link to the original recipe page; do not copy recipe text. Run `python scripts/check_links.py` and the tests before release.
````

Create `PRODUCT.md`:

```markdown
# Product

## Users

The person at the screen all day: usually not a confident computer user, glancing from across the room, with occasional touch, mouse or keyboard use. The person who sets it up: a household member, not a developer.

## Purpose

A single-pane-of-glass household screen: weather, today's tasks (repeating chores plus one-offs), and rotating meal ideas. It resets itself every day with no upkeep. Success: it can be read from across the room, nothing has to be learned, and it never shows a blank or error screen.

## Character

Private, local, always-on, and tuned to each household's own routine (their town, their rooms, their meals), not a generic widget board. Calm and warm rather than busy.

## Principles

1. Readable first: very large type and large touch targets (at least 52px), generous spacing.
2. Nothing to learn: plain words, one obvious action per control, an undo bar instead of "are you sure".
3. Never blank, never alarming: stale data is shown with a small "Updated" note; errors are plain and gentle.
4. Never act on the household's behalf without their say: nothing moves, deletes or sends itself.
5. Setup is a conversation, not a form: one question per page, sensible defaults, everything changeable later.
6. Private by default: no accounts, no tracking, data stays on the computer.

## Features

- Weather with 3-day outlook, optional severe weather banner (US National Weather Service; opt-in by location), automatic light and dark.
- Today's tasks: repeating rules, a weekday cleaning plan built from the household's rooms, manual tasks (today, tomorrow or a chosen date), "From yesterday" carryover, undo, drag to reorder.
- Meals: any number of meal sections, three ideas each per day, "Not tonight, show another", favorites, "never show again" with a restore list.
- Dinner plans, shopping list and timers (each can be switched off).
- Settings: appearance, household, rooms, meals, repeating tasks, important dates.

## Style

Keep the existing visual language (the green "parlour" header, brass accents, ribbons on meal cards, serif type), labels and layout zones. Keep automatic light and dark by sunrise and sunset. New screens use the same card, type and colour system.
```

Create `docs/INSTALL.md`:

```markdown
# Installing Household Dashboard

You need a Windows 10 or 11 computer with the Edge browser (it comes with Windows) and an internet connection for the weather. About 5 minutes.

## 1. Run the installer

1. Double-click **HomeDashboard-Setup-x.y.z.exe** (the file you were sent).
2. Windows may show a blue box that says **"Windows protected your PC"**. This appears for any app that is new and not from a big company. To continue, click **More info**, then **Run anyway**.
3. Click **Next** through the installer and then **Finish**. It does not need an administrator password.

The dashboard starts by itself and fills the screen.

## 2. Answer a few questions

The first time, a short setup walks you through:

1. What to call your household.
2. Your town (type a city or ZIP code and pick it from the list).
3. Your rooms, and how much each is used. This builds a weekday cleaning plan; weekends stay free.
4. A look at the weekly plan.
5. Which meals you want ideas for, and which recipe packs to use.
6. What to show on the screen.

You can change every answer later.

## 3. Using it

- Tap a task's circle to tick it off. **Move to tomorrow** pushes it a day.
- On a dinner idea: the heart saves it, the X hides it for good, and **Not tonight, show another** swaps it.
- The small **gear** in the top right opens Settings. Change your town, rooms, meals, colors and more there. **Run setup again** (under Household) repeats the questions.
- To leave full screen, press **Alt+F4**. Opening Home Dashboard from the Start menu brings it back.

## 4. Starting automatically

The installer adds Home Dashboard to your Startup folder, so it opens when you sign in to Windows. To turn that off, open **Settings, Apps, Startup** and switch off Home Dashboard.

## Updating

When you are sent a newer installer, just run it. Your household's settings, tasks and favorites are kept.

## Where your information is kept

Everything stays on this computer in `%APPDATA%\HomeDashboard` (paste that into the File Explorer address bar). Copy that folder to keep a backup.

## If something is wrong

- **The weather says "unavailable"**: check the internet connection. The last forecast stays on screen when the connection drops.
- **Nothing opens after install**: open Home Dashboard from the Start menu.
- **Another program is using the same address**: the dashboard tries the next free one automatically; nothing for you to do.
- **To remove it**: Settings, Apps, Installed apps, Home Dashboard, Uninstall. Your data folder stays unless you delete it.
```

- [ ] **Step 2: Scrub check**

```bash
grep -rniE "chris|huntsville|alabama|34\.73|86\.59|gaaraofthefunk" . --exclude-dir=.git --exclude-dir=docs --exclude-dir=.venv-build --exclude-dir=dist --exclude-dir=build --exclude-dir=.demo-data -l
```

Expected: only `tests/test_household_web.py` and `tests/test_wizard_web.py` (they list those words to assert they are absent). Any other file: remove or genericize the reference and re-run.

- [ ] **Step 3: Full test run**

Run: `python -m unittest discover -s tests -t .`
Expected: `OK (skipped=2)` (the two skips are node-only tests).

- [ ] **Step 4: Commit**

```bash
git add README.md PRODUCT.md docs/INSTALL.md
git commit -m "docs: readme, product notes and household install guide"
```

- [ ] **Step 5: Push and report**

```bash
git push origin main
git log origin/main --oneline | head -20
```

In the final report, state plainly: the starter packs need the owner's review; `installer.iss` is uncompiled unless Inno Setup was installed in Task 12; and a real install on a clean Windows machine or VM has not been done.

---
