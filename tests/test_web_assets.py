import http.client
import json
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import server
from dashboard.api import App
from dashboard.store import Store


class WebAssetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = App(Store(Path(tmp.name) / "d.json"), [], {"chris": [], "v": []}, None)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read().decode("utf-8")

    def test_assets_served(self):
        status, ctype, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        for label in ("Today's tasks", "Chris Dinner", "V's Dinner", "Favorites", "Add a task"):
            self.assertIn(label, body)
        self.assertIn("text/css", self.get("/app.css")[1])
        status, ctype, body = self.get("/app.js")
        self.assertIn("javascript", ctype)
        for label in ("Move to tomorrow", "Not tonight, show another", "Get the recipe", "From yesterday", "Hidden recipes"):
            self.assertIn(label, body)

    def css_rule(self, selector):
        """Declarations of the first rule for exactly `selector`, as a dict."""
        css = re.sub(r"/\*.*?\*/", "", self.get("/app.css")[2], flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            if " ".join(match.group(1).split()) == selector:
                pairs = (part.split(":", 1) for part in match.group(2).split(";") if ":" in part)
                return {k.strip(): "".join(v.split()) for k, v in pairs}
        self.fail(f"app.css has no rule for {selector!r}")

    def test_dinner_cards_show_net_carbs_between_protein_and_time(self):
        _, _, js = self.get("/app.js")
        self.assertRegex(js, r"protein \? `\$\{recipe\.protein\}g protein` : null,\s*`\$\{recipe\.carbs\}g carbs`,\s*`\$\{recipe\.minutes\} min`")

    def test_recipe_links_open_in_the_default_browser_via_the_server(self):
        # Edge kiosk has no tabs, so target=_blank would open inside the kiosk. Links ask
        # the server to open them in the default browser and fall back to a new window.
        _, _, js = self.get("/app.js")
        self.assertIn("'/api/open'", js)
        self.assertIn("preventDefault()", js)
        self.assertIn("window.open(", js)
        self.assertEqual(js.count("recipeLink("), 3)  # definition + card + favorite chip
        self.assertEqual(js.count("href: recipe.url"), 1)  # only recipeLink builds recipe links

    def test_dinner_description_is_not_squeezed_mid_line(self):
        # At 1920x1080 the cards are short; a shrinkable clamped description gets cut
        # through the middle of a line. It must keep its height and end in an ellipsis.
        rule = self.css_rule(".dinner .desc")
        self.assertEqual(rule.get("flex"), "none")
        self.assertEqual(rule.get("-webkit-line-clamp"), "1")

    def test_dinner_cards_leave_room_for_two_line_titles(self):
        # The header band and card padding leave room for a two-line title.
        self.assertEqual(self.css_rule("body").get("grid-template-rows"), "222pxminmax(0,1fr)")
        rule = self.css_rule(".dinner")
        self.assertEqual(rule.get("padding"), "10px14px")
        self.assertEqual(rule.get("gap"), "0")

    def test_dinner_title_is_clamped_to_two_lines(self):
        # A long recipe name must truncate, not push the action row out of the card.
        rule = self.css_rule(".dinner h4")
        self.assertEqual(rule.get("flex"), "none")
        self.assertEqual(rule.get("overflow"), "hidden")
        self.assertEqual(rule.get("-webkit-line-clamp"), "2")

    def test_v_action_row_fits_without_clipping(self):
        # V cards carry swap + heart + X; the row must fit the ~326px card width (or wrap)
        # instead of clipping the X on the right.
        self.assertEqual(self.css_rule(".dinner .row").get("flex-wrap"), "wrap")
        icon = self.css_rule(".dinner .icon")
        self.assertLessEqual(int(icon["min-width"].removesuffix("px")), 44)
        ghost = self.css_rule(".dinner .ghost")
        self.assertLessEqual(int(ghost["font-size"].removesuffix("px")), 18)
        self.assertLessEqual(max(int(n) for n in re.findall(r"(\d+)px", ghost["padding"])), 8)

    def test_reorder_grip_progress_and_edit_present(self):
        js = self.get("/app.js")[2]
        for label in ("Drag to reorder", "/api/tasks/reorder", "'PATCH'", "setPointerCapture", "Task name", "lostpointercapture", "} done`", "isConnected"):
            self.assertIn(label, js)
        self.assertIn('id="progress"', self.get("/")[2])
        self.assertEqual(self.css_rule(".grip").get("touch-action"), "none")
        self.assertGreaterEqual(int(self.css_rule(".grip")["min-width"].removesuffix("px")), 52)

    def test_dates_comingup_carryover_and_undo_present(self):
        js = self.get("/app.js")[2]
        for label in ("/api/tasks/dismiss-carryover", "/api/undo", "Dismiss all", "Coming up (", "Added for ", "Pick a date",
                      "Tomorrow", "state.tasks.upcoming", "state.undo", "days)", "state.date"):
            self.assertIn(label, js)
        page = self.get("/")[2]
        for markup in ('id="undo"', 'id="upcoming-toggle"', 'id="upcoming-panel"', 'id="when"', 'id="added"'):
            self.assertIn(markup, page)
        # The error banner sits above the undo bar, never on top of it.
        error_bottom = int(self.css_rule(".error")["bottom"].removesuffix("px"))
        undo_bottom = int(self.css_rule(".undo")["bottom"].removesuffix("px"))
        self.assertGreater(error_bottom, undo_bottom)

    def test_touch_targets_stay_large(self):
        for selector in (".group-label.row .ghost", ".seg button"):
            rule = self.css_rule(selector)
            height = rule.get("min-height") or self.css_rule(".ghost")["min-height"]
            self.assertGreaterEqual(int(height.removesuffix("px")), 52, selector)

    def test_settings_panel_present(self):
        page = self.get("/")[2]
        self.assertRegex(page, r'<button[^>]*aria-label="Settings"')
        self.assertIn('id="settings"', page)
        js = self.get("/app.js")[2]
        for label in ("dataset.theme", "dataset.accent", "dataset.size", "state.settings", "state.rules",
                      "/api/settings", "/api/rules", "'PUT'", "'DELETE'", "'POST'", "Escape", "Repeating tasks",
                      "Add a repeating task", "Every other", "Monthly on the", "Paused", "Resume"):
            self.assertIn(label, js)
        for accent in ("blue", "green", "purple", "orange", "rose"):
            self.assertIn(f"'{accent}'", js)
        for repeat in ("daily", "weekdays", "weekly", "biweekly", "monthly"):
            self.assertIn(f"'{repeat}'", js)
        self.assertIn("gear:", js)
        self.assertIn(">Done<", page)

    def test_settings_css_overrides_and_targets(self):
        css = re.sub(r"/\*.*?\*/", "", self.get("/app.css")[2], flags=re.S)
        for accent in ("green", "purple", "orange", "rose"):
            self.assertIn(f'[data-accent="{accent}"]', css)
        self.assertIn('[data-size="large"]', css)
        self.assertIn('[data-theme="dark"][data-accent=', css)
        for selector in (".gear", ".seg button", ".swatch", ".daypick button", ".tab", ".rule-row .ghost", ".sheet .primary", ".rule-form .ghost"):
            rule = self.css_rule(selector)
            height = rule.get("min-height") or rule.get("height") or self.css_rule(".ghost")["min-height"]
            self.assertGreaterEqual(int(height.removesuffix("px")), 52, selector)

    def test_dinner_plans_screen_markup_and_script_order(self):
        page = self.get("/")[2]
        for markup in ('id="views"', 'id="plans-view"', 'id="plan-new"', 'id="plan-list"', 'id="plan-detail"', 'id="nudge"',
                       "New dinner plan", 'src="plans.js"', 'src="app.js"'):
            self.assertIn(markup, page)
        self.assertLess(page.index('src="plans.js"'), page.index('src="app.js"'))
        status, ctype, js = self.get("/plans.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        for label in ("Dinner plans", "selectView", "aria-selected", "initViews"):
            self.assertIn(label, js)
        self.assertIn("initViews()", self.get("/app.js")[2])

    def test_view_panels_are_labelled_by_their_tabs(self):
        page = self.get("/")[2]
        self.assertIn('<main id="today-view" role="tabpanel" aria-labelledby="tab-today">', page)
        self.assertIn('id="plans-view" role="tabpanel" aria-labelledby="tab-plans"', page)
        js = self.get("/plans.js")[2]
        for label in ("'tab-' + key", "aria-controls", "today-view", "plans-view", "activeScreen"):
            self.assertIn(label, js)

    def test_view_switch_and_plan_targets_stay_large(self):
        for selector in (".view-tab", ".nudge", ".plan-row"):
            rule = self.css_rule(selector)
            self.assertGreaterEqual(int(rule["min-height"].removesuffix("px")), 52, selector)

    def test_nudge_and_plan_this_dinner_present(self):
        plans_js = self.get("/plans.js")[2]
        for label in ("function renderNudge", "Start dinner at ", "Time to start dinner", "function planFromRecipe", "/plan`", "function openPlan"):
            self.assertIn(label, plans_js)
        app_js = self.get("/app.js")[2]
        for label in ("Plan this dinner", "planFromRecipe(", "renderNudge()", "list:"):
            self.assertIn(label, app_js)
        self.assertEqual(app_js.count("recipeLink("), 3)
        self.assertEqual(app_js.count("href: recipe.url"), 1)

    def test_dinner_links_row_does_not_grow_the_card(self):
        rule = self.css_rule(".dinner .links")
        self.assertEqual(rule.get("display"), "flex")
        self.assertEqual(rule.get("margin"), "-7px0")

    def test_plan_form_guards(self):
        js = self.get("/plans.js")[2]
        self.assertIn("const thisForm = planForm;", js)
        self.assertIn("if (planForm === thisForm) closeForm(", js)
        self.assertIn("if (!save.disabled) closeForm(null)", js)
        self.assertEqual(js.count("if (planFormOpen()) return;"), 3)
        self.assertIn("el('span', {class: 'name', title: plan.title}, plan.title)", js)
        self.assertIn("!Number.isInteger(minutes) || minutes < 1", js)

    def test_no_innerhtml_in_plans_js(self):
        self.assertNotIn("innerHTML", self.get("/plans.js")[2])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_rule_summary_and_ordinals(self):
        js = self.get("/app.js")[2]
        consts = re.search(r"const DAY_KEYS = .*?\nconst DAY_NAMES = .*?\n", js, flags=re.S).group(0)
        funcs = js[js.index("function joinNames"):js.index("function pressedGroup")]
        cases = {
            "ordinals": "[1,2,3,4,11,12,13,21,22,23,31].map(ordinal)",
            "summaries": "[{repeat:'daily'},{repeat:'weekdays'},{repeat:'weekly',days:['mon','wed','fri']},"
                         "{repeat:'weekly',days:['thu','mon']},{repeat:'biweekly',days:['wed']},"
                         "{repeat:'monthly',dayOfMonth:22},{repeat:'weekly',days:[]},{repeat:'monthly',dayOfMonth:40}].map(ruleSummary)",
        }
        script = consts + funcs + "console.log(JSON.stringify({" + ",".join(f"{k}:{v}" for k, v in cases.items()) + "}))"
        out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out["ordinals"], ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "31st"])
        self.assertEqual(out["summaries"], [
            "Every day", "Weekdays", "Every Monday, Wednesday and Friday", "Every Monday and Thursday",
            "Every other Wednesday", "Monthly on the 22nd", "Pick at least one day", "Pick a day from 1 to 31"])

    def test_resilience_and_skip_present(self):
        js = self.get("/app.js")[2]
        for label in ("AbortController", "signal:", "4 * 60 * 1000", "60 * 1000", "Skip this one", "/dismiss`", "state.undo.id"):
            self.assertIn(label, js)

    def test_plan_view_strings_and_endpoints_present(self):
        js = self.get("/plans.js")[2]
        for label in ("Today", "Coming up", "Earlier", "No dinner plans yet. Tap New dinner plan to start.", "Ingredients", "Steps",
                      "gathered", "steps done", "Ready around", "Cook again", "Delete this plan?", "/api/plans/",
                      "/check", "/copy", "recipeLink(", "aria-checked", "keepFocus"):
            self.assertIn(label, js)
        self.assertIn("renderPlans()", self.get("/app.js")[2])

    def test_plan_check_glyph_only_when_done(self):
        self.assertIn("item.done ? glyph('check') : null", self.get("/plans.js")[2])

    def test_plan_rows_are_large_and_lists_scroll_inside_the_card(self):
        self.assertGreaterEqual(int(self.css_rule(".step-row")["min-height"].removesuffix("px")), 64)
        self.assertEqual(self.css_rule(".plan-col .items").get("overflow"), "auto")
        self.assertEqual(self.css_rule(".plan-cols").get("min-height"), "0")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_plan_time_helpers(self):
        js = self.get("/plans.js")[2]
        funcs = js[js.index("function clock12"):js.index("function doneCount")]
        script = funcs + "console.log(JSON.stringify({c:['00:05','12:00','13:30','17:15'].map(clock12)," \
                         "a:[addMinutes('17:15',40),addMinutes('23:30',45),addMinutes('00:10',-20)]," \
                         "r:[readyLine({startTime:'17:15',prepMinutes:40}),readyLine({startTime:'',prepMinutes:40}),readyLine({startTime:'17:15',prepMinutes:null})]," \
                         "p:[prepLabel(5),prepLabel(60),prepLabel(90)]}))"
        out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out["c"], ["12:05 AM", "12:00 PM", "1:30 PM", "5:15 PM"])
        self.assertEqual(out["a"], ["17:55", "00:15", "23:50"])
        self.assertEqual(out["r"], ["Ready around 5:55 PM", "", ""])
        self.assertEqual(out["p"], ["5 min", "1 hr", "1 hr 30 min"])

    def test_no_innerhtml_with_data(self):
        self.assertNotIn("innerHTML", self.get("/app.js")[2])

    def test_plan_form_strings_and_behaviour_present(self):
        js = self.get("/plans.js")[2]
        for label in ("let planForm = null;", "function openForm", "function closeForm", "planFormOpen", "What are you making?",
                      "One ingredient per line", "One step per line", "Dinner at", "Prep time (minutes)", "Start time",
                      "Enter the prep time first", "'PUT'", "form-error", "Escape", "10 * 60 * 1000", "lineList"):
            self.assertIn(label, js)
        self.assertIn("planFormOpen()", self.get("/app.js")[2])

    def test_plan_form_targets_stay_large(self):
        for selector in (".plan-form input", ".plan-form textarea", ".plan-form .ghost", ".plan-form .primary"):
            rule = self.css_rule(selector)
            height = rule.get("min-height") or self.css_rule(".ghost")["min-height"]
            self.assertGreaterEqual(int(height.removesuffix("px")), 52 if "textarea" not in selector else 0, selector)

    def test_plan_form_textarea_inherits_text_colour(self):
        # A textarea does not inherit colour by itself; without this it is black on the dark theme.
        self.assertIn("color", self.css_rule(".plan-form textarea"))

    def test_shopping_screen_markup_and_script_order(self):
        page = self.get("/")[2]
        for markup in ('id="shopping-view" role="tabpanel" aria-labelledby="tab-shopping"', 'id="shopping-add"', 'id="shopping-input"',
                       'id="shopping-list"', 'id="shopping-count"', 'id="shopping-clear"', 'src="shopping.js"',
                       'placeholder="Add an item"', 'maxlength="200"', 'aria-label="Add an item"', "Shopping list", "Clear checked"):
            self.assertIn(markup, page)
        self.assertLess(page.index('src="plans.js"'), page.index('src="shopping.js"'))
        self.assertLess(page.index('src="shopping.js"'), page.index('src="app.js"'))
        plans_js = self.get("/plans.js")[2]
        for label in ("['shopping', 'Shopping list']", "shopping: 'shopping-view'", "$('#shopping-view').hidden = name !== 'shopping'",
                      "SCREENS.length", "ArrowUp", "ArrowLeft"):
            self.assertIn(label, plans_js)
        app_js = self.get("/app.js")[2]
        self.assertIn("renderShopping()", app_js)
        self.assertEqual(app_js.count("$('#shopping-view').inert"), 2)

    def test_shopping_js_strings_and_endpoints(self):
        status, ctype, js = self.get("/shopping.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        for label in ("function renderShopping", "function shoppingCall", "Nothing on the list. Type what you need above.",
                      "GENERIC_ERROR", "of ${", " bought", "Mark ${", "Remove ${", "aria-pressed", "/api/shopping",
                      "/check", "/api/shopping/clear", "keepFocus", "title:", "state.shopping"):
            self.assertIn(label, js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("insertAdjacent", js)
        self.assertNotIn("outerHTML", js)

    def test_shopping_add_only_clears_unchanged_input(self):
        js = self.get("/shopping.js")[2]
        self.assertIn("const sent = input.value", js)
        self.assertIn("if (input.value === sent) input.value = ''", js)

    def test_plan_title_clamps_to_two_lines_with_full_title_tooltip(self):
        self.assertIn("el('h2', {title: plan.title}, plan.title)", self.get("/plans.js")[2])
        rule = self.css_rule(".plan-top h2")
        self.assertEqual(rule.get("-webkit-line-clamp"), "2")
        self.assertEqual(rule.get("white-space"), "normal")
        self.assertEqual(rule.get("min-width"), "0")

    def test_view_tabs_sit_in_one_row(self):
        self.assertEqual(self.css_rule(".views").get("flex-direction"), "row")

    def test_shopping_targets_stay_large_and_list_scrolls_in_card(self):
        for selector in (".shopping-tick", ".shopping-remove", ".shopping-add button", ".shopping-clear"):
            rule = self.css_rule(selector)
            width = rule.get("min-height") or self.css_rule(".ghost")["min-height"]
            self.assertGreaterEqual(int(width.removesuffix("px")), 52, selector)
        for selector in (".shopping-tick", ".shopping-remove"):
            self.assertGreaterEqual(int(self.css_rule(selector)["min-width"].removesuffix("px")), 52, selector)
        self.assertEqual(self.css_rule(".shopping-list").get("overflow"), "auto")
        self.assertEqual(self.css_rule(".shopping-view").get("min-height"), "0")

    def test_plan_add_to_shopping_button_and_status(self):
        js = self.get("/plans.js")[2]
        for label in ("Add to shopping list", "/shopping`", "Already on the list", "Added 1 item", "Added ${", " items",
                      "role: 'status'", "plan-shop-status", "4000", "GENERIC_ERROR", "!item.done"):
            self.assertIn(label, js)
        self.assertNotIn("innerHTML", js)
        self.assertGreaterEqual(int(self.css_rule(".plan-actions .ghost")["min-height"].removesuffix("px")), 52)
        self.assertIn("plan-shop-status", self.get("/app.css")[2])

    def test_settings_has_a_close_button(self):
        self.assertIn('id="settings-close"', self.get("/")[2])
        self.assertIn("'#settings-close'", self.get("/app.js")[2])

    def test_settings_closes_on_outside_tap(self):
        js = self.get("/app.js")[2]
        self.assertIn("pressedOutside", js)
        self.assertEqual(js.count("backOutOfSettings"), 4)  # definition, X, outside tap, Esc

    def test_dates_markup_and_script(self):
        page = self.get("/")[2]
        for needle in ('id="soon"', 'id="panel-dates"'):
            self.assertIn(needle, page)
        js = self.get("/app.js")[2]
        for label in ("function renderSoon", "function buildDates", "/api/dates", "'Dates'"):
            self.assertIn(label, js)
        self.assertIn(".soon-item", self.get("/app.css")[2])

    def test_screen_dims_when_idle_at_night(self):
        js = self.get("/app.js")[2]
        for label in ("IDLE_DIM_MS", "function applyDim", "data-dim", "wokeByTap"):
            self.assertIn(label, js)
        self.assertEqual(self.css_rule("html[data-dim]").get("filter"), "brightness(.5)")

    def test_planned_dinner_card_is_marked_and_opens_its_plan(self):
        js = self.get("/app.js")[2]
        for label in ("Planned for tonight", "Open tonight's plan", "openPlan(planned.id)"):
            self.assertIn(label, js)
        self.assertIn(".dinner.planned", self.get("/app.css")[2])

    def test_timers_markup_script_order_and_safety(self):
        page = self.get("/")[2]
        for needle in ('id="timers-view"', 'id="timer-presets"', 'id="timer-list"'):
            self.assertIn(needle, page)
        self.assertLess(page.index('src="app.js"'), page.index('src="timers.js"'))  # timers.js uses el() and $()
        self.assertIn("'timers'", self.get("/plans.js")[2])
        js = self.get("/timers.js")[2]
        for label in ("function startTimer", "function tickTimers", "Time's up", "localStorage", "TIMER_MAX"):
            self.assertIn(label, js)
        for banned in ("innerHTML", "insertAdjacent", "outerHTML"):
            self.assertNotIn(banned, js)
        for selector in (".timer-preset", ".timer-x"):
            height = self.css_rule(selector).get("min-height") or self.css_rule(".ghost")["min-height"]
            self.assertGreaterEqual(int(height.removesuffix("px")), 52, selector)

    def test_alert_banner_markup_and_script_order(self):
        page = self.get("/")[2]
        self.assertIn('id="alert-bar"', page)
        self.assertRegex(page, r'<[^>]*id="alert-bar"[^>]*role="alert"|<[^>]*role="alert"[^>]*id="alert-bar"')
        self.assertLess(page.index('id="alert-bar"'), page.index('<header'))
        self.assertLess(page.index('src="plans.js"'), page.index('src="shopping.js"'))
        self.assertLess(page.index('src="shopping.js"'), page.index('src="alerts.js"'))
        self.assertLess(page.index('src="alerts.js"'), page.index('src="app.js"'))
        app_js = self.get("/app.js")[2]
        self.assertIn("pollAlerts", app_js)
        self.assertIn("2 * 60 * 1000", app_js)

    def test_alerts_js_strings_and_endpoints(self):
        status, ctype, js = self.get("/alerts.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        for label in ("function renderAlerts", "function pollAlerts", "function dismissAlert", "Dismiss", "GENERIC_ERROR",
                      " more", " until ", "clock12", "/api/alerts", "/api/alerts/dismiss", "has-alert", "aria-expanded"):
            self.assertIn(label, js)
        self.assertIn("That didn't work. Try again.", self.get("/app.js")[2])
        for banned in ("innerHTML", "insertAdjacent", "outerHTML"):
            self.assertNotIn(banned, js)

    def test_alerts_js_end_time_shows_weekday_when_not_today(self):
        js = self.get("/alerts.js")[2]
        self.assertIn("toLocaleDateString(undefined, {weekday: 'short'})", js)
        self.assertIn("getDate() === now.getDate()", js)
        self.assertIn("finally", js)

    def test_alert_targets_and_layout_rows(self):
        for selector in (".alert-dismiss", ".alert-more"):
            self.assertGreaterEqual(int(self.css_rule(selector)["min-height"].removesuffix("px")), 52, selector)
        self.assertTrue(self.css_rule("body.has-alert")["grid-template-rows"].startswith("auto"))
        css = self.get("/app.css")[2]
        self.assertIn("body.has-alert", css)
        self.assertIn("html[data-size=\"large\"] body.has-alert", css)
        self.assertIn(".alert-bar.watch", css)
        self.assertIn(".alert-bar.warning", css)
        self.assertIn("alert-bar[hidden]", css)


if __name__ == "__main__":
    unittest.main()
