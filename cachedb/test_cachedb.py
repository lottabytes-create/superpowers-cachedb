import pytest

from cacheDB import CacheDB


def test_new_cache_instance():
    db = CacheDB()
    assert isinstance(db, CacheDB)


@pytest.fixture
def db():
    return CacheDB()


def test_set_returns_true(db):
    assert db.set("name", "alice") is True


def test_set_accepts_empty_string_key_and_value(db):
    assert db.set("", "") is True


@pytest.mark.parametrize(
    "key,value",
    [(1, "v"), ("k", 1), (None, "v"), ("k", None)],
)
def test_set_rejects_non_string(db, key, value):
    with pytest.raises(TypeError):
        db.set(key, value)
