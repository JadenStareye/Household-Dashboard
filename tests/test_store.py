import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dashboard.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.store = Store(self.dir / "data.json", self.dir / "backups", keep=3)

    def test_load_missing_returns_empty(self):
        self.assertEqual(self.store.load(), {})

    def test_save_then_load_roundtrip(self):
        self.store.save({"a": 1})
        self.assertEqual(self.store.load(), {"a": 1})

    def test_save_leaves_no_temp_files(self):
        self.store.save({"a": 1})
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_backup_once_per_day(self):
        self.store.save({"n": 1})
        self.store.backup(date(2026, 10, 6))
        self.store.save({"n": 2})
        self.store.backup(date(2026, 10, 6))
        backup = json.loads((self.dir / "backups" / "data-2026-10-06.json").read_text())
        self.assertEqual(backup, {"n": 1})

    def test_backup_retention_keeps_newest(self):
        self.store.save({"n": 1})
        for day in range(1, 6):
            self.store.backup(date(2026, 10, day))
        names = sorted(p.name for p in (self.dir / "backups").glob("data-*.json"))
        self.assertEqual(names, ["data-2026-10-03.json", "data-2026-10-04.json", "data-2026-10-05.json"])

    def test_corrupt_file_recovers_from_newest_valid_backup(self):
        backups = self.dir / "backups"
        backups.mkdir()
        (backups / "data-2026-10-01.json").write_text('{"n": 1}')
        (backups / "data-2026-10-02.json").write_text("{not json")
        (self.dir / "data.json").write_text("garbage")
        self.assertEqual(self.store.load(), {"n": 1})

    def test_backup_skips_corrupt_file(self):
        (self.dir / "data.json").write_text("garbage")
        self.store.backup(date(2026, 10, 6))
        self.assertEqual(list((self.dir / "backups").glob("data-*.json")) if (self.dir / "backups").exists() else [], [])


if __name__ == "__main__":
    unittest.main()
