class CacheDB:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def _require_str(self, value: object, name: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be str, got {type(value).__name__}")

    def set(self, key: str, value: str) -> bool:
        self._require_str(key, "key")
        self._require_str(value, "value")
        self._data[key] = value
        return True

    def get(self, key: str) -> str | None:
        self._require_str(key, "key")
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        self._require_str(key, "key")
        if key in self._data:
            del self._data[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        self._require_str(key, "key")
        return key in self._data

    def keys(self) -> list[str]:
        return list(self._data.keys())
