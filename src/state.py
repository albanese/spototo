"""Persistent JSON state: Yoto OAuth tokens and the MYO card ID."""
import json
from pathlib import Path
from threading import Lock


class State:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {}
        with open(self.path, "r") as f:
            return json.load(f)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value):
        with self._lock:
            self._data[key] = value
            self._save()

    def update(self, **kwargs):
        with self._lock:
            self._data.update(kwargs)
            self._save()
