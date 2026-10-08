import copy
import uuid

MAX_ITEMS = 200
MAX_TEXT = 200
FULL = "The list is full. Clear some items first."


def _usable(item):
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str) and item["id"]
        and isinstance(item.get("text"), str) and item["text"].strip()
    )


def _stored(data):
    items = data.setdefault("shoppingList", [])
    if not isinstance(items, list):
        items = data["shoppingList"] = []
    return items


def _clean(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Enter an item")
    text = " ".join(text.split())
    if len(text) > MAX_TEXT:
        raise ValueError("Keep it under 200 characters")
    return text


def _key(text):
    return " ".join(text.split()).casefold()


def _match(items, text):
    wanted = _key(text)
    return next((i for i in items if _usable(i) and _key(i["text"]) == wanted), None)


def add(data, text):
    text = _clean(text)
    items = _stored(data)
    found = _match(items, text)
    if found is not None:
        found["done"] = False
        return found
    if sum(1 for i in items if _usable(i)) >= MAX_ITEMS:
        raise ValueError(FULL)
    item = {"id": uuid.uuid4().hex[:8], "text": text, "done": False}
    items.append(item)
    return item


def add_many(data, texts):
    items = _stored(data)
    cleaned, seen = [], set()
    for text in texts:
        try:
            text = _clean(text)
        except ValueError:
            continue
        if _key(text) not in seen:
            seen.add(_key(text))
            cleaned.append(text)
    fresh = [t for t in cleaned if _match(items, t) is None]
    if sum(1 for i in items if _usable(i)) + len(fresh) > MAX_ITEMS:
        raise ValueError(FULL)
    added = 0
    for text in cleaned:
        found = _match(items, text)
        if found is None:
            items.append({"id": uuid.uuid4().hex[:8], "text": text, "done": False})
            added += 1
        elif found.get("done"):
            found["done"] = False
            added += 1
    return added


def _find(data, item_id):
    for item in _stored(data):
        if _usable(item) and item["id"] == item_id:
            return item
    raise KeyError(item_id)


def check(data, item_id):
    item = _find(data, item_id)
    item["done"] = not item.get("done")
    return item


def remove(data, item_id):
    _stored(data).remove(_find(data, item_id))


def clear(data):
    items = _stored(data)
    gone = [i for i in items if _usable(i) and i.get("done")]
    data["shoppingList"] = [i for i in items if not (_usable(i) and i.get("done"))]
    return copy.deepcopy(gone)


def restore(data, record):
    items = _stored(data)
    saved_items = record.get("shopping", []) if isinstance(record, dict) else []
    if not isinstance(saved_items, list):
        return
    have = {i["id"] for i in items if _usable(i)}
    count = sum(1 for i in items if _usable(i))
    for saved in saved_items:
        if count >= MAX_ITEMS:
            break
        if _usable(saved) and saved["id"] not in have and _match(items, saved["text"]) is None:
            count += 1
            items.append(copy.deepcopy(saved))
            have.add(saved["id"])


def view(data):
    items = data.get("shoppingList")
    if not isinstance(items, list):
        return []
    shown = [
        {"id": i["id"], "text": i["text"], "done": bool(i.get("done"))}
        for i in items if _usable(i)
    ]
    return [i for i in shown if not i["done"]] + [i for i in shown if i["done"]]
