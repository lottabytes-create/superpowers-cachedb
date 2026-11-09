import json
import logging
import threading
from pathlib import Path


class CacheDB:
    def __init__(
        self,
        file_path: str | Path = "cachedb_data.json",
        auto_save: bool = True,
        auto_save_interval: float = 5.0,
    ) -> None:
        if auto_save_interval <= 0:
            raise ValueError("auto_save_interval must be positive")
        self._file_path = Path(file_path)
        self._auto_save_enabled = auto_save
        self._auto_save_interval = auto_save_interval
        self._data: dict[str, str] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.load()
        self._start_auto_save()

    def _require_str(self, value: object, name: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be str, got {type(value).__name__}")

    def set(self, key: str, value: str) -> bool:
        with self._lock:
            self._require_str(key, "key")
            self._require_str(value, "value")
            self._data[key] = value
            return True

    def get(self, key: str) -> str | None:
        with self._lock:
            self._require_str(key, "key")
            return self._data.get(key)

    def delete(self, key: str) -> bool:
        with self._lock:
            self._require_str(key, "key")
            if key in self._data:
                del self._data[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        with self._lock:
            self._require_str(key, "key")
            return key in self._data

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> bool:
        with self._lock:
            self._data.clear()
            return True

    def save(self) -> bool:
        with self._lock:
            snapshot = dict(self._data)
        content = json.dumps(snapshot, ensure_ascii=False, indent=2)
        self._file_path.write_text(content, encoding="utf-8")
        return True

    def load(self) -> bool:
        if not self._file_path.exists():
            return False
        with open(self._file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {self._file_path}") from exc
        if not isinstance(data, dict):
            raise ValueError("top-level JSON value must be an object")
        for value in data.values():
            if not isinstance(value, str):
                raise ValueError("all values must be strings")
        with self._lock:
            self._data = dict(data)
        return True

    def _auto_save_loop(self) -> None:
        while not self._stop_event.wait(self._auto_save_interval):
            try:
                self.save()
            except OSError as exc:
                logging.getLogger(__name__).warning("auto save failed: %s", exc)

    def _start_auto_save(self) -> None:
        if not self._auto_save_enabled:
            return
        self._thread = threading.Thread(
            target=self._auto_save_loop,
            name="cachedb-autosave",
            daemon=True,
        )
        self._thread.start()

    def stop_auto_save(self) -> bool:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return False
        self._stop_event.set()
        thread.join()
        return True
