class CacheDB:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
