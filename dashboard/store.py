import json
import os
import shutil
import tempfile
from pathlib import Path


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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

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
