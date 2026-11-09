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


def test_delete_existing_returns_true(db):
    db.set("k", "v")
    assert db.delete("k") is True


def test_delete_missing_returns_false(db):
    assert db.delete("missing") is False


def test_delete_removes_value(db):
    db.set("k", "v")
    db.delete("k")
    assert db.get("k") is None


def test_delete_rejects_non_string_key(db):
    with pytest.raises(TypeError):
        db.delete(1)


def test_exists_true_after_set(db):
    db.set("k", "v")
    assert db.exists("k") is True


def test_exists_false_for_missing(db):
    assert db.exists("missing") is False


def test_exists_false_after_delete(db):
    db.set("k", "v")
    db.delete("k")
    assert db.exists("k") is False


def test_exists_distinguishes_empty_value_from_missing(db):
    db.set("empty", "")
    assert db.exists("empty") is True
    assert db.exists("missing") is False


def test_exists_rejects_non_string_key(db):
    with pytest.raises(TypeError):
        db.exists(1)
