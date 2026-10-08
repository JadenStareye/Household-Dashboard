import random

PICKS = 3


def _state(data, key):
    lists = data.setdefault("dinners", {})
    return lists.setdefault(key, {"queue": [], "day": None, "picks": [], "favorites": [], "hidden": []})


def _refill(state, ids, rng):
    hidden = set(state["hidden"])
    pool = [i for i in ids if i not in hidden]
    pool += [f for f in state["favorites"] if f in pool]
    rng.shuffle(pool)
    state["queue"] = pool


def _draw(state, ids, exclude, rng):
    valid = set(ids) - set(state["hidden"])
    for _ in range(3):
        while state["queue"]:
            candidate = state["queue"].pop(0)
            if candidate in valid and candidate not in exclude:
                return candidate
        _refill(state, ids, rng)
    return None


def ensure_today(data, key, recipes, today, rng=None):
    rng = rng or random.Random()
    state = _state(data, key)
    iso = today.isoformat()
    ids = [r["id"] for r in recipes]
    if state["day"] == iso:
        # A recipe list edited mid-day can retire today's picks; replace them instead of showing fewer cards.
        valid = set(ids) - set(state["hidden"])
        state["picks"] = [i for i in state["picks"] if i in valid]
        while len(state["picks"]) < PICKS:
            pick = _draw(state, ids, set(state["picks"]), rng)
            if pick is None:
                break
            state["picks"].append(pick)
        return state
    state["picks"] = []
    for _ in range(PICKS):
        pick = _draw(state, ids, set(state["picks"]), rng)
        if pick is None:
            break
        state["picks"].append(pick)
    state["day"] = iso
    return state


def swap(data, key, recipes, today, recipe_id, rng=None):
    rng = rng or random.Random()
    state = ensure_today(data, key, recipes, today, rng)
    if recipe_id not in state["picks"]:
        raise KeyError(recipe_id)
    ids = [r["id"] for r in recipes]
    replacement = _draw(state, ids, set(state["picks"]), rng)
    if replacement is not None:
        state["picks"][state["picks"].index(recipe_id)] = replacement
    return state


def _require(recipes, recipe_id):
    if recipe_id not in {r["id"] for r in recipes}:
        raise KeyError(recipe_id)


def toggle_favorite(data, key, recipe_id, recipes):
    _require(recipes, recipe_id)
    favorites = _state(data, key)["favorites"]
    if recipe_id in favorites:
        favorites.remove(recipe_id)
    else:
        favorites.append(recipe_id)


def hide(data, key, recipe_id, recipes, today, rng=None):
    rng = rng or random.Random()
    _require(recipes, recipe_id)
    state = ensure_today(data, key, recipes, today, rng)
    if recipe_id not in state["hidden"]:
        state["hidden"].append(recipe_id)
    if recipe_id in state["favorites"]:
        state["favorites"].remove(recipe_id)
    if recipe_id in state["picks"]:
        ids = [r["id"] for r in recipes]
        index = state["picks"].index(recipe_id)
        replacement = _draw(state, ids, set(state["picks"]), rng)
        if replacement is None:
            del state["picks"][index]
        else:
            state["picks"][index] = replacement
    return state


def restore(data, key, recipe_id):
    hidden = _state(data, key)["hidden"]
    if recipe_id in hidden:
        hidden.remove(recipe_id)


def view(data, key, recipes):
    state = _state(data, key)
    by_id = {r["id"]: r for r in recipes}

    def card(recipe_id):
        recipe = dict(by_id[recipe_id])
        recipe["favorite"] = recipe_id in state["favorites"]
        return recipe

    return {
        "picks": [card(i) for i in state["picks"] if i in by_id],
        "favorites": [card(i) for i in state["favorites"] if i in by_id],
        "hidden": [by_id[i] for i in state["hidden"] if i in by_id],
    }
