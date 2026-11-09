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
