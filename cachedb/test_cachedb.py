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


def test_get_existing_value(db):
    db.set("name", "alice")
    assert db.get("name") == "alice"


def test_get_missing_returns_none(db):
    assert db.get("missing") is None


def test_get_empty_string_value(db):
    db.set("empty", "")
    assert db.get("empty") == ""


def test_get_after_overwrite_returns_latest(db):
    db.set("k", "v1")
    db.set("k", "v2")
    assert db.get("k") == "v2"


def test_get_rejects_non_string_key(db):
    with pytest.raises(TypeError):
        db.get(1)
