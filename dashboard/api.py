import re
import threading
import time
import webbrowser
from datetime import date

from . import dates as dates_mod, dinners, plans as plans_mod, rules as rules_mod, shopping as shopping_mod, todo

UNDO_SECONDS = 30
DEFAULT_SETTINGS = {"theme": "auto", "accent": "blue", "textSize": "normal"}
SETTING_CHOICES = {
    "theme": ("auto", "light", "dark"),
    "accent": ("blue", "green", "purple", "orange", "rose"),
    "textSize": ("normal", "large"),
}


class _NoAlerts:
    fresh = False

    def get(self):
        return []


def _title(body):
    title = body.get("title")
    return title if isinstance(title, str) else None


class App:
    def __init__(self, store, rules, recipes, weather, clock=date.today, rng=None, now=time.monotonic, opener=webbrowser.open_new_tab, alerts=None):
        self.store = store
        self.rules = rules
        self.recipes = recipes
        self.weather = weather
        self.alerts = alerts or _NoAlerts()
        self.clock = clock
        self.rng = rng
        self.now = now
        self.opener = opener
        self.lock = threading.Lock()
        self.data = store.load()
        self._backed_up = None
        self._undo = None
        self._undo_seq = 0

    def _usable_rules(self, today):
        usable = []
        for rule in self.data.get("rules", []):
            try:
                rules_mod.matches(rule, today)
                rule["id"], rule["title"]
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
            usable.append(rule)
        return usable

    def _prepare(self, today):
        if self._backed_up != today:
            self.store.backup(today)
            self._backed_up = today
        rules_mod.seed(self.data, self.rules)
        todo.generate_recurring(self.data, self._usable_rules(today), today)
        todo.prune(self.data, today)
        plans_mod.prune(self.data, today)
        dates_mod.prune(self.data, today)
        for key, items in self.recipes.items():
            dinners.ensure_today(self.data, key, items, today, self.rng)

    def _undo_view(self):
        if self._undo is None or self.now() - self._undo["stamp"] > UNDO_SECONDS:
            return None
        return {"label": self._undo["label"], "id": self._undo["id"]}

    def _snapshot(self, today):
        return {
            "date": today.isoformat(),
            "dateLabel": f"{today:%A, %B} {today.day}",
            "tasks": todo.view(self.data, today),
            "dinners": {key: dinners.view(self.data, key, items) for key, items in self.recipes.items()},
            "settings": dict(DEFAULT_SETTINGS, **self.data.get("settings", {})),
            "rules": self.data.get("rules", []),
            "plans": plans_mod.view(self.data, today),
            "shopping": shopping_mod.view(self.data),
            "dates": dates_mod.view(self.data, today),
            "undo": self._undo_view(),
        }

    def _run(self, action=None):
        with self.lock:
            today = self.clock()
            self._prepare(today)
            if action:
                action(today)
                todo.generate_recurring(self.data, self._usable_rules(today), today)
            self.store.save(self.data)
            return self._snapshot(today)

    def _task_ids(self, task_id, today):
        for entry in todo.view(self.data, today)["carryover"]:
            if task_id in entry["ids"]:
                return entry["ids"]
        return [task_id]

    def _undoable(self, label, act, ids):
        """Run act(today); on success record an undo snapshot taken beforehand."""
        def run(today):
            task_ids = ids(today)
            record = todo.snapshot_for_undo(self.data, label(task_ids) if callable(label) else label, task_ids)
            act(today)
            if task_ids:
                self._remember(record)
        return run

    def _remember(self, record):
        """Keep one undo record (the newest replaces the last)."""
        self._undo_seq += 1
        self._undo = {"record": record, "label": record["label"], "stamp": self.now(), "id": self._undo_seq}

    def _known_urls(self):
        return {r["url"] for items in self.recipes.values() for r in items}

    def _delete_plan(self, plan_id):
        def run(today):
            plan = plans_mod.delete(self.data, plan_id)
            self._remember({"label": "Plan deleted", "tasks": [], "plans": [plan]})
        return run

    def _plan_response(self, make):
        """Run make(today) like any action; the response also names the plan it made or found."""
        made = {}

        def run(today):
            made["plan"] = make(today)

        snapshot = self._run(run)
        snapshot["planId"] = made["plan"]["id"]
        return 200, snapshot

    def _clear_shopping(self, today):
        gone = shopping_mod.clear(self.data)
        if gone:
            self._remember({
                "label": f"Cleared {len(gone)} item{'' if len(gone) == 1 else 's'}",
                "tasks": [], "shopping": gone,
            })

    def _shopping_import(self, plan_id):
        made = {}

        def run(today):
            plan = plans_mod.find(self.data, plan_id)
            texts = [i["text"] for i in plan["ingredients"] if not i["done"]]
            made["added"] = shopping_mod.add_many(self.data, texts)

        snapshot = self._run(run)
        snapshot["added"] = made["added"]
        return 200, snapshot

    def _cleared_label(self):
        # The label counts what the user sees (grouped rows), not the underlying tasks.
        count = len(todo.view(self.data, self.clock())["carryover"])
        return f"Cleared {count} task{'' if count == 1 else 's'}"

    def _undo_action(self, today, undo_id=None):
        view = self._undo_view()
        if view is None or (undo_id is not None and undo_id != view["id"]):
            raise ValueError("Nothing to undo")
        todo.restore(self.data, self._undo["record"])
        plans_mod.restore(self.data, self._undo["record"])
        shopping_mod.restore(self.data, self._undo["record"])
        self._undo = None

    def _set_settings(self, body):
        for key, value in body.items():
            if key in SETTING_CHOICES and value not in SETTING_CHOICES[key]:
                raise ValueError("Pick one of the choices offered")
        stored = self.data.setdefault("settings", {})
        stored.update({k: v for k, v in body.items() if k in SETTING_CHOICES})

    def _open_recipe(self, url):
        # Only recipe pages the dashboard itself lists may be opened, never arbitrary addresses.
        known = self._known_urls()
        if not isinstance(url, str) or url not in known:
            return 400, {"error": "That link can't be opened"}
        try:
            opened = self.opener(url)
        except Exception:
            opened = False
        if not opened:
            return 500, {"error": "Couldn't open the browser"}
        return 200, {"ok": True}

    def _alerts_response(self, dismiss_id=None):
        try:
            active = self.alerts.get()  # network happens here, outside the lock
        except Exception:
            active = []
        with self.lock:
            stored = self.data.setdefault("alertsDismissed", [])
            if not isinstance(stored, list):
                stored = self.data["alertsDismissed"] = []
            before = list(stored)
            if dismiss_id is not None:
                if dismiss_id not in {a["id"] for a in active}:
                    raise KeyError(dismiss_id)
                if dismiss_id in stored:
                    stored.remove(dismiss_id)
                stored.append(dismiss_id)
                del stored[:-50]
            if getattr(self.alerts, "fresh", False):
                live = {a["id"] for a in active}
                stored[:] = [i for i in stored if i in live]
            if dismiss_id is not None or stored != before:
                self.store.save(self.data)
            return 200, {"alerts": [a for a in active if a["id"] not in stored]}

    def handle(self, method, path, body=None):
        if body is None:
            body = {}
        if not isinstance(body, dict):
            return 400, {"error": "Bad request"}
        try:
            if method == "GET" and path == "/api/state":
                return 200, self._run()
            if method == "GET" and path == "/api/weather":
                return 200, self.weather.get()
            if method == "GET" and path == "/api/alerts":
                return self._alerts_response()
            if method == "POST" and path == "/api/alerts/dismiss":
                alert_id = body.get("id")
                if not isinstance(alert_id, str) or not alert_id:
                    return 400, {"error": "Bad request"}
                return self._alerts_response(alert_id)
            if method == "POST" and path == "/api/open":
                return self._open_recipe(body.get("url"))
            if method == "PUT" and path == "/api/settings":
                return 200, self._run(lambda today: self._set_settings(body))
            if method == "POST" and path == "/api/undo":
                return 200, self._run(lambda today: self._undo_action(today, body.get("id")))
            if method == "POST" and path == "/api/rules":
                return 200, self._run(lambda today: rules_mod.create(self.data, body, today))
            if method == "POST" and path == "/api/plans":
                return self._plan_response(lambda today: plans_mod.create(self.data, body, today, self._known_urls()))
            if method == "POST" and path == "/api/dates":
                return 200, self._run(lambda today: dates_mod.add(self.data, body))
            if method == "POST" and path == "/api/shopping":
                return 200, self._run(lambda today: shopping_mod.add(self.data, body.get("text")))
            if method == "POST" and path == "/api/shopping/clear":
                return 200, self._run(self._clear_shopping)
            if method == "POST" and path == "/api/tasks":
                return 200, self._run(
                    lambda today: todo.add_task(self.data, _title(body), today, body.get("date"))
                )
            if method == "POST" and path == "/api/tasks/reorder":
                return 200, self._run(lambda today: todo.reorder(self.data, body.get("ids"), today))
            if method == "POST" and path == "/api/tasks/dismiss-carryover":
                return 200, self._run(self._undoable(
                    lambda ids: self._cleared_label(),
                    lambda today: todo.dismiss_carryover(self.data, today),
                    lambda today: [i for e in todo.view(self.data, today)["carryover"] for i in e["ids"]],
                ))

            match = re.fullmatch(r"/api/rules/([\w-]+)", path)
            if match:
                rule_id = match.group(1)
                if method == "PUT":
                    return 200, self._run(lambda today: rules_mod.update(self.data, rule_id, body, today))
                if method == "DELETE":
                    return 200, self._run(lambda today: rules_mod.delete(self.data, rule_id))

            match = re.fullmatch(r"/api/dates/(\w+)", path)
            if method == "DELETE" and match:
                return 200, self._run(lambda today: dates_mod.remove(self.data, match.group(1)))

            match = re.fullmatch(r"/api/shopping/(\w+)/check", path)
            if method == "POST" and match:
                return 200, self._run(lambda today: shopping_mod.check(self.data, match.group(1)))

            match = re.fullmatch(r"/api/shopping/(\w+)", path)
            if method == "DELETE" and match:
                return 200, self._run(lambda today: shopping_mod.remove(self.data, match.group(1)))

            match = re.fullmatch(r"/api/plans/(\w+)", path)
            if match:
                plan_id = match.group(1)
                if method == "PUT":
                    return 200, self._run(lambda today: plans_mod.update(self.data, plan_id, body, today, self._known_urls()))
                if method == "DELETE":
                    return 200, self._run(self._delete_plan(plan_id))

            match = re.fullmatch(r"/api/plans/(\w+)/(check|copy|shopping)", path)
            if method == "POST" and match:
                plan_id, action = match.groups()
                if action == "shopping":
                    return self._shopping_import(plan_id)
                if action == "check":
                    return 200, self._run(lambda today: plans_mod.check(self.data, plan_id, body.get("kind"), body.get("itemId")))
                return self._plan_response(lambda today: plans_mod.copy_plan(self.data, plan_id, today))

            match = re.fullmatch(r"/api/tasks/(\w+)/(done|move|dismiss)", path)
            if method == "POST" and match:
                task_id, action = match.groups()

                def ids(today):
                    return self._task_ids(task_id, today)

                actions = {
                    "done": lambda today: todo.toggle_done(self.data, task_id, today),
                    "move": self._undoable(
                        "Task moved to tomorrow", lambda today: todo.move_to_tomorrow(self.data, task_id, today), ids
                    ),
                    "dismiss": self._undoable(
                        "Task dismissed", lambda today: todo.dismiss(self.data, task_id, today), ids
                    ),
                }
                return 200, self._run(actions[action])

            match = re.fullmatch(r"/api/tasks/(\w+)", path)
            if match:
                task_id = match.group(1)
                if method == "DELETE":
                    return 200, self._run(self._undoable(
                        "Task removed", lambda today: todo.remove(self.data, task_id), lambda today: [task_id]
                    ))
                if method == "PATCH":
                    return 200, self._run(lambda today: todo.edit_title(self.data, task_id, _title(body)))

            match = re.fullmatch(r"/api/dinners/(chris|v)/(swap|favorite|hide|restore|plan)", path)
            if method == "POST" and match:
                key, action = match.groups()
                recipe_id = body.get("recipeId")
                items = self.recipes[key]
                if action in ("hide", "restore") and key != "v":
                    return 404, {"error": "Not found"}
                if action == "plan":
                    recipe = next((r for r in items if r["id"] == recipe_id), None)
                    if recipe is None:
                        raise KeyError(recipe_id)
                    return self._plan_response(lambda today: plans_mod.from_recipe(self.data, recipe, today))
                actions = {
                    "swap": lambda today: dinners.swap(self.data, key, items, today, recipe_id, self.rng),
                    "favorite": lambda today: dinners.toggle_favorite(self.data, key, recipe_id, items),
                    "hide": lambda today: dinners.hide(self.data, key, recipe_id, items, today, self.rng),
                    "restore": lambda today: dinners.restore(self.data, key, recipe_id),
                }
                return 200, self._run(actions[action])

            return 404, {"error": "Not found"}
        except KeyError:
            return 404, {"error": "Not found"}
        except ValueError as error:
            return 400, {"error": str(error)}
