import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RECIPES = Path(__file__).resolve().parent.parent / "content" / "recipes.json"
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
    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    failures = 0
    for key in ("chris", "v"):
        for recipe in data[key]:
            result = check(recipe["url"])
            ok = isinstance(result, int) and result < 400
            if not ok:
                failures += 1
                print(f"FAIL [{key}] {recipe['id']}: {result} {recipe['url']}")
    print(f"{failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
