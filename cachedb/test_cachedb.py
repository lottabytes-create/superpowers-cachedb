import json
import time

import pytest

from cacheDB import CacheDB


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_new_cache_instance(tmp_path):
    db = CacheDB(file_path=tmp_path / "cachedb_data.json", auto_save=False)
    assert isinstance(db, CacheDB)


@pytest.fixture
def db(tmp_path):
    return CacheDB(file_path=tmp_path / "cachedb_data.json", auto_save=False)


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


def test_keys_empty_on_new_cache(db):
    assert db.keys() == []


def test_keys_returns_insertion_order(db):
    db.set("b", "2")
    db.set("a", "1")
    db.set("c", "3")
    assert db.keys() == ["b", "a", "c"]


def test_keys_returns_copy(db):
    db.set("a", "1")
    result = db.keys()
    result.append("injected")
    assert db.keys() == ["a"]


def test_keys_after_delete(db):
    db.set("a", "1")
    db.set("b", "2")
    db.delete("a")
    assert db.keys() == ["b"]


def test_keys_order_unchanged_after_overwrite(db):
    db.set("a", "1")
    db.set("b", "2")
    db.set("a", "3")
    assert db.keys() == ["a", "b"]


def test_clear_returns_true(db):
    assert db.clear() is True


def test_clear_removes_all_data(db):
    db.set("a", "1")
    db.set("b", "2")
    db.clear()
    assert db.keys() == []
    assert db.get("a") is None


def test_clear_on_empty_cache_returns_true(db):
    assert db.clear() is True


def test_cache_usable_after_clear(db):
    db.set("a", "1")
    db.clear()
    db.set("b", "2")
    assert db.get("b") == "2"


def test_save_creates_file(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("name", "alice")
    assert db.save() is True
    assert path.exists()


def test_save_writes_json_content(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("name", "alice")
    db.set("empty", "")
    db.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "name": "alice",
        "empty": "",
    }


def test_save_empty_cache_writes_empty_object(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_save_preserves_unicode(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("城市", "厦门")
    db.save()
    assert json.loads(path.read_text(encoding="utf-8")) == {"城市": "厦门"}


def test_save_raises_oserror_for_missing_directory(tmp_path):
    path = tmp_path / "missing" / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    with pytest.raises(OSError):
        db.save()


def test_load_missing_file_returns_false(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    assert db.load() is False


def test_load_restores_data(tmp_path):
    path = tmp_path / "cachedb_data.json"
    path.write_text('{"name": "alice", "empty": ""}', encoding="utf-8")
    db = CacheDB(file_path=path, auto_save=False)
    assert db.load() is True
    assert db.get("name") == "alice"
    assert db.get("empty") == ""


def test_load_replaces_existing_data(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("old", "1")
    path.write_text('{"new": "2"}', encoding="utf-8")
    assert db.load() is True
    assert db.keys() == ["new"]


def test_load_empty_object_clears_data(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("old", "1")
    path.write_text("{}", encoding="utf-8")
    assert db.load() is True
    assert db.keys() == []


def test_load_invalid_json_raises_value_error(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        db.load()


def test_load_non_object_raises_value_error(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    path.write_text('["a", "b"]', encoding="utf-8")
    with pytest.raises(ValueError):
        db.load()


def test_load_non_string_value_raises_value_error(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    path.write_text('{"k": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        db.load()


def test_init_auto_loads_existing_file(tmp_path):
    path = tmp_path / "cachedb_data.json"
    path.write_text('{"name": "alice"}', encoding="utf-8")
    db = CacheDB(file_path=path, auto_save=False)
    assert db.get("name") == "alice"


def test_init_without_file_starts_empty(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    assert db.keys() == []


def test_init_with_corrupt_file_raises_value_error(tmp_path):
    path = tmp_path / "cachedb_data.json"
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError):
        CacheDB(file_path=path, auto_save=False)


def test_auto_save_writes_periodically(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=True, auto_save_interval=0.05)
    try:
        db.set("k", "v")
        assert _wait_until(lambda: _read_json(path) == {"k": "v"})
    finally:
        db.stop_auto_save()


def test_auto_save_disabled_does_not_write(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("k", "v")
    time.sleep(0.15)
    assert not path.exists()


def test_stop_auto_save_stops_further_writes(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=True, auto_save_interval=0.05)
    db.set("a", "1")
    assert _wait_until(lambda: _read_json(path) == {"a": "1"})
    assert db.stop_auto_save() is True
    db.set("b", "2")
    time.sleep(0.2)
    assert _read_json(path) == {"a": "1"}


def test_stop_auto_save_returns_false_when_not_running(tmp_path):
    db = CacheDB(file_path=tmp_path / "cachedb_data.json", auto_save=False)
    assert db.stop_auto_save() is False
    assert db.stop_auto_save() is False


def test_non_positive_interval_rejected(tmp_path):
    with pytest.raises(ValueError):
        CacheDB(
            file_path=tmp_path / "cachedb_data.json",
            auto_save=False,
            auto_save_interval=0,
        )


def test_data_survives_restart(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=False)
    db.set("a", "1")
    db.set("中文", "厦门")
    db.save()
    restarted = CacheDB(file_path=path, auto_save=False)
    assert restarted.get("a") == "1"
    assert restarted.get("中文") == "厦门"
    assert restarted.keys() == ["a", "中文"]


def test_default_file_path_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = CacheDB(auto_save=False)
    db.set("a", "1")
    db.save()
    assert (tmp_path / "cachedb_data.json").exists()


def test_concurrent_writes_during_auto_save(tmp_path):
    path = tmp_path / "cachedb_data.json"
    db = CacheDB(file_path=path, auto_save=True, auto_save_interval=0.01)
    expected = {f"k{i}": str(i) for i in range(300)}
    try:
        for key, value in expected.items():
            db.set(key, value)
        assert _wait_until(lambda: _read_json(path) == expected, timeout=3.0)
    finally:
        db.stop_auto_save()
