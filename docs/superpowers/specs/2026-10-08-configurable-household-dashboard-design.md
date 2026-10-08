# Configurable Household Dashboard — Design Spec

**Date:** 2026-10-08
**Status:** Approved design, reconciled with the existing v2.0 code (see section 11)
**Builds on:** the single-household Home Dashboard 2.0 (stdlib Python server, vanilla web UI). That app stays untouched; this project starts from a copy with all household-specific data removed.

## 1. Purpose

Turn the single-household home dashboard into a version that other households (friends and family) can install and configure themselves. A non-technical household member sets it up through a first-run wizard and changes it later from the in-app Settings. No JSON editing and no command line.

## 2. Decisions made in the interview

| Topic | Decision |
|---|---|
| Distribution | Local Windows installer (.exe), Python bundled. Everything stays on the household's machine |
| Audience | Friends and family. No licensing, payments, or accounts |
| Setup user | Non-technical household member |
| Configurable | Location and units, chores, dinner meal slots, which modules are shown |
| Chores | Rooms wizard that generates a weekday rotation |
| Dinner model | Flexible meal slots (any number, each with a name, packs and own recipes, tag filters) |
| Recipes | Curated starter packs (new lists) with name, link, time, tags. Households can add their own |
| Layout | Responsive to any screen size. Modules toggle on or off |
| Settings access | Small gear icon on the dashboard |
| Updates | Manual: send a new installer; user data survives reinstall |
| Approach | Refactor the existing app (stdlib Python server, vanilla web UI) |
| Existing data | None carries over. The original household's recipes, chores and settings are private. Placeholder examples demonstrate each configurable part |

## 3. Goals and non-goals

**Goals**
- A household installs, runs the wizard once, and has a working dashboard.
- Everything the original app hardcoded (location, chores, dinner lists, the two dinner modules) comes from one household config.
- Looks right from a 1920x1080 wall display down to a tablet.
- Config and state survive reinstall and corrupt files.

**Non-goals (v1)**
- Mac and Linux builds, auto-update, accounts, cloud sync.
- Drag-and-drop layout.
- Nutrition filtering and full recipe text.
- Editing starter packs inside the app (households can hide recipes and add their own).
- Code signing (the installer is unsigned; see 8).
- Severe weather alerts outside the United States (they use the US National Weather Service).

## 4. Architecture

```
Household-Dashboard/
  launcher.py          what the installed app runs: start the server if needed, open it fullscreen
  server.py            HTTP server, JSON API, static files (stdlib only)
  dashboard/           logic modules (todo, dinners, weather, alerts, plans, shopping, store, ...
                       plus household, packs, chores_gen, geocode, paths)
  web/                 index.html, app.css, app.js, household.js, wizard.js, plans.js, ...
  packs/               read-only starter packs (*.json)
  packaging/           PyInstaller spec, Inno Setup script, build and smoke-test scripts
  scripts/             check_links.py
  tests/
```

A household's own files live in `%APPDATA%\HomeDashboard\` (override with `HOME_DASHBOARD_DATA`), never in the install folder:

```
household.json    the household's configuration
data.json         runtime state (tasks, rules, picks, favorites, hidden, settings)
backups/          rolling copies of both files
port.txt          the port the running app chose
```

### 4.1 `household.json`

| Key | Contents |
|---|---|
| `schemaVersion` | `1` |
| `name` | Household name shown in the header |
| `location` | `label`, `lat`, `lon`, `alerts` (true only for a US place the household opted into) |
| `units` | `temperature`: `F` or `C` |
| `modules` | Booleans: `weather`, `tasks`, `plans`, `shopping`, `timers` |
| `rooms` | `[{name, kind, usage}]`; `kind` is kitchen, bathroom, bedroom, living, office or other; `usage` is `high` or `low` |
| `choreMinutes` | Cleaning goal per weekday, 10 to 120 (default 30) |
| `mealSlots` | `[{id, name, enabled, packIds[], tagFilter[], ownRecipes[]}]` |

The generated cleaning rotation is **not** stored here. It becomes ordinary repeating rules in `data.json` (ids start with `gen-`), so the existing Repeating tasks editor keeps working and tasks a household added by hand are never touched.

### 4.2 Units and boundaries

- **Server** — HTTP only: routing, file serving, JSON in and out. Picks the first free port from 8765 to 8774.
- **Household module** — validates what the browser sends, saves `household.json` atomically with rolling backups, recovers from them, and reports "needs setup" when there is none.
- **Packs module** — loads and validates starter packs; builds a meal slot's recipe pool (packs, tag filter, own recipes).
- **Chore generator** — pure function: rooms and a minutes goal in, a Monday to Friday rotation, a per-day summary and warnings out. Never produces weekend tasks.
- **Geocoder** — Open-Meteo place search (city or postal code), with a manual coordinates fallback.
- **Todo, Dinners, Plans, Shopping** — unchanged in behavior. Dinners are keyed by meal slot id instead of two fixed names.
- **Weather and Alerts services** — take their place and unit from the household; reconfigurable at runtime.
- **Store** — unchanged behavior; its atomic write is shared with the household module.
- **Web UI** — renders state from the API and sends actions. Holds no business logic.

Constraint: the runtime uses only the Python standard library. PyInstaller and Inno Setup are build-time tools.

## 5. First-run wizard and settings

### 5.1 Wizard

Shown full screen when there is no `household.json`. Large type, one step per page, Back and Next, defaults that need no typing.

1. Welcome and household name.
2. Location: type a city or ZIP code and pick from the matches; temperature unit. If the lookup fails (offline), coordinates can be typed instead.
3. Rooms: four example rooms are pre-filled; add, rename or remove; mark each used a lot or a little; cleaning minutes goal.
4. Weekly cleaning plan preview (Monday to Friday, with warnings if a day runs long).
5. Meals: one meal ("Dinner") with a starter pack pre-selected; add more meals, choose packs and tag filters, add own recipes.
6. Modules: turn weather, tasks, dinner plans, shopping list and timers on or off.
7. Summary and "Open my dashboard".

### 5.2 Settings screen

The existing gear icon opens Settings. Existing tabs stay: Appearance, Repeating tasks, Dates. New tabs: **Household** (name, location, unit, modules, "Run setup again"), **Rooms** (rooms, minutes goal, weekly plan preview, "Save and rebuild cleaning plan"), **Meals** (meal slots).

- The new tabs edit one draft and save it together. Closing Settings with unsaved changes is refused with a plain message (the idle timeout still closes).
- Rebuilding the cleaning plan replaces the generated rules and today's unfinished generated tasks; finished tasks and hand-made rules stay.
- "Run setup again" reopens the wizard pre-filled; favorites and hidden recipes are kept.

### 5.3 Safeguards

- The server validates every save and answers in plain language; invalid input changes nothing.
- Writes are atomic with backups. A broken `household.json` falls back to the newest valid backup instead of showing a blank screen.

## 6. Starter packs

Read-only files in `packs/`. Four packs of at least 20 recipes: `family-classics`, `quick-weeknight`, `vegetarian`, `low-carb`.

**Recipe fields:** `id`, `name`, `url`, `minutes`, `tags`. Recipes link out to the original page; no recipe text is copied. Tags come from one fixed list: vegetarian, vegan, low-carb, gluten-free, dairy-free, quick, family-friendly, one-pan, slow-cooker. The original household's recipe lists are not used.

A meal slot's pool is the recipes in its chosen packs that carry **every** selected tag, plus the household's own recipes (always included). Every meal supports a favorite heart, "never show again" with a restore list, and "Not tonight, show another". Links are checked with `scripts/check_links.py` before release.

## 7. Responsive layout

The page is drawn for 1920x1080. A small script scales it with CSS `zoom` to the window (never below 0.5 or above 2). Tall windows and windows narrower than 1280px switch to a stacked, scrolling single column. Disabled modules leave the layout and the rest expand. With more than two meals the meal area scrolls inside its column rather than shrinking text.

## 8. Packaging and updates

- PyInstaller bundles the server, web files and packs into one folder with `HomeDashboard.exe` (no console window).
- An Inno Setup installer installs for the current user (no administrator prompt), adds a Start Menu entry and a Startup entry, and opens the dashboard in Edge fullscreen. If the app is already running, a second launch only opens the browser.
- Reinstalling over an older version keeps `%APPDATA%\HomeDashboard`.
- The installer is unsigned, so Windows SmartScreen warns on first run. A one-page install guide shows how to choose "More info, Run anyway".
- Updates are manual: send the new installer.

## 9. Testing

- Unit tests (`unittest`, injectable clock): chore generator, household validation and recovery, packs, geocoder parsing, location handling in the weather and alert services, the household API (setup, regenerate, preview, geocode), generic meal slots, port fallback, launcher.
- Web-asset tests pin the markup and strings the UI depends on.
- Shipped packs are validated by a test (count, unique links, tag promises) and by the link checker.
- Manual: first run in the browser, settings edits, layout at four window sizes, fresh install on a clean Windows machine or VM, upgrade-over-install keeps data, reboot autostart, offline behavior.

## 10. Open items

1. Compile and test `installer.iss` on a machine with Inno Setup 6, and run the install on a clean Windows VM.
2. Starter pack content needs a human review of recipe choices before sharing.
3. Whether to code-sign the installer if the audience grows beyond friends and family.

## 11. Reconciliation with the original spec

The first draft of this spec predated a look at the real v2.0 code. Differences, all deliberate:

- Chores live in `data.json` rules (seeded once, edited in Settings), so the generated rotation becomes rules with `gen-` ids rather than a `chores` key in `household.json`.
- Rooms carry `kind` and `usage`; the minutes goal is one household-wide `choreMinutes`, not per room.
- `modules` is a map of booleans (plus per-meal `enabled`) rather than an ordered list.
- Location and modules share the Household tab (six settings tabs in all).
- No wind unit: the dashboard never shows wind.
- v2.0 features the first draft did not mention are kept: dinner plans, shopping list, timers (each can be switched off), and NWS severe weather alerts (US only, opt-in by location).
- Favorites, "never show again" and swap work for every meal, not only the second one.
- Port conflicts are resolved by trying 8765 to 8774.
