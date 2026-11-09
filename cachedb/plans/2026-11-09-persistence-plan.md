# CacheDB 持久化功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 CacheDB 上增加 JSON 持久化、启动自动加载和可停止的定时自动保存，同时保持 Task 1 六接口与 30 个测试不变。

**Architecture:** 在 `CacheDB` 内组合 `dict` 与 `threading.RLock`，新增 `save/load/stop_auto_save`；构造参数控制文件路径、定时开关与间隔；单个守护线程按 `Event.wait(interval)` 周期调用 `save()`。

**Tech Stack:** Python 3.10+、标准库 `json`/`threading`/`logging`/`pathlib`、pytest。

**Spec:** `cachedb/specs/2026-11-09-persistence-design.md`

## Global Constraints

- 仅支持字符串 key/value；非 str 抛 `TypeError`（Task 1 行为不变）。
- 默认文件路径为当前工作目录 `cachedb_data.json`；JSON 顶层为对象。
- `save()` 返回 `True`；`load()` 成功 `True`、文件不存在 `False`；`stop_auto_save()` 之前运行中 `True`、否则 `False`。
- `load()` 遇到损坏 JSON、非对象、非字符串值抛 `ValueError`；IO 错误抛 `OSError`。
- 默认 `auto_save=True`，默认间隔 5.0 秒；`auto_save_interval <= 0` 构造时抛 `ValueError`。
- 定时线程必须可停止且幂等；线程内保存失败只记录 warning，不中断循环。
- 只修改 `cachedb/cacheDB.py` 与 `cachedb/test_cachedb.py`。
- 每个任务结束运行 `python -m pytest cachedb/test_cachedb.py -v` 并提交。

## Review Focus

- 定时器停止后不再写盘、重复 stop 安全：Task D 的 `test_stop_auto_save_stops_further_writes`、`test_stop_auto_save_returns_false_when_not_running`。
- 损坏 JSON / 非对象 / 非字符串值不得静默丢数据：Task B 的三个 `ValueError` 用例与 Task C 的启动损坏用例。
- 并发写入期间保存不得抛出字典迭代错误：Task E 的 `test_concurrent_writes_during_auto_save`。
- 默认构造不得读写到测试临时目录之外的残留文件：Task A 的 fixture 隔离与 Task E 的 `test_default_file_path_in_cwd`。
- IO 失败必须显式暴露：Task A 的 `test_save_raises_oserror_for_missing_directory`。
- 空串与中文经 JSON 往返保持不变：Task A 的 `test_save_preserves_unicode` 与 Task B 的恢复用例。

---

### Task A: 构造参数、锁与 save()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Test: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: Task 1 的 `_data: dict[str, str]`。
- Produces:
  - `CacheDB(file_path: str | Path = "cachedb_data.json", auto_save: bool = True, auto_save_interval: float = 5.0)`
  - `save(self) -> bool`
  - 私有 `_lock: threading.RLock`，六个原方法在同一把锁下执行。

- [ ] **Step 1: 修改测试文件顶部与 fixture**

在 `test_cachedb.py` 顶部加入 `import json` 与 `from pathlib import Path`（若未使用可省略），并将实例测试与 fixture 改为：

```python
def test_new_cache_instance(tmp_path):
    db = CacheDB(file_path=tmp_path / "cachedb_data.json", auto_save=False)
    assert isinstance(db, CacheDB)


@pytest.fixture
def db(tmp_path):
    return CacheDB(file_path=tmp_path / "cachedb_data.json", auto_save=False)
```

Task 1 其余测试的断言一律不改。

- [ ] **Step 2: 追加 save() 的失败测试**

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -k "save" -v`

Expected: FAIL，`TypeError`（构造参数不存在）或 `AttributeError: 'CacheDB' object has no attribute 'save'`。

- [ ] **Step 4: 实现构造参数与 save()**

在 `cacheDB.py` 顶部加入 `import json`、`import threading`、`from pathlib import Path`。

构造函数：

```python
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
```

不要在此任务启动线程或自动加载。

`save()`：在锁内复制 `dict(self._data)` 快照，锁外以 UTF-8、`ensure_ascii=False`、`indent=2` 写入 `self._file_path`，返回 `True`。

把 `set/get/delete/exists/keys/clear` 的方法体放进 `with self._lock:`；返回值与异常行为保持不变。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v`

Expected: 35 passed（原 30 + 新增 5）。

- [ ] **Step 6: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 支持持久化构造参数并实现 CacheDB.save()"
```

---

### Task B: 实现 load()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Test: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `self._file_path: Path`、`self._data`、`self._lock`。
- Produces: `load(self) -> bool`。

- [ ] **Step 1: 追加 load() 的失败测试**

```python
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
    path.write_text("{not json", encoding="utf-8")
    db = CacheDB(file_path=path, auto_save=False)
    with pytest.raises(ValueError):
        db.load()


def test_load_non_object_raises_value_error(tmp_path):
    path = tmp_path / "cachedb_data.json"
    path.write_text('["a", "b"]', encoding="utf-8")
    db = CacheDB(file_path=path, auto_save=False)
    with pytest.raises(ValueError):
        db.load()


def test_load_non_string_value_raises_value_error(tmp_path):
    path = tmp_path / "cachedb_data.json"
    path.write_text('{"k": 1}', encoding="utf-8")
    db = CacheDB(file_path=path, auto_save=False)
    with pytest.raises(ValueError):
        db.load()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -k "load" -v`

Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'load'`。

- [ ] **Step 3: 实现 load()**

文件不存在返回 `False` 且不改内存；其余步骤：

1. `json.load`，捕获 `json.JSONDecodeError` 并抛 `ValueError`（保留 `from exc`）。
2. 顶层不是 `dict` → `ValueError`。
3. 任一 value 不是 `str` → `ValueError`。
4. 在 `with self._lock:` 内用 `dict(data)` 替换 `self._data`，返回 `True`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v`

Expected: 42 passed。

- [ ] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.load()"
```

---

### Task C: 启动自动加载

**Files:**
- Modify: `cachedb/cacheDB.py`
- Test: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `load() -> bool`。
- Produces: `__init__` 在完成字段初始化后调用 `self.load()`，文件不存在时保持空库。

- [ ] **Step 1: 追加启动加载测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -k "init" -v`

Expected: 前两个 FAIL（数据未恢复 / 无差别则可能通过），损坏文件用例 FAIL（未抛异常）。

- [ ] **Step 3: 在 __init__ 中调用 load()**

字段初始化完成后、启动定时线程之前调用 `self.load()`。本任务不启动线程。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v`

Expected: 45 passed。

- [ ] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 启动时自动加载缓存数据"
```

---

### Task D: 定时自动保存与停止

**Files:**
- Modify: `cachedb/cacheDB.py`
- Test: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `save() -> bool`、`self._auto_save_enabled`、`self._auto_save_interval`。
- Produces:
  - `stop_auto_save(self) -> bool`
  - 私有 `_auto_save_loop()`、`_start_auto_save()`，使用 `threading.Event` 与守护线程。

- [ ] **Step 1: 追加定时器测试与辅助函数**

在测试文件顶部加入 `import time`，并添加：

```python
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
```

测试：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -k "auto_save or interval" -v`

Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'stop_auto_save'` 或文件未生成。

- [ ] **Step 3: 实现定时线程**

在 `__init__` 中新增 `self._stop_event = threading.Event()` 与 `self._thread: threading.Thread | None = None`，并在 `self.load()` 之后调用 `self._start_auto_save()`。

```python
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
```

顶部加入 `import logging`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v`

Expected: 50 passed。

- [ ] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现定时自动保存与停止"
```

---

### Task E: 集成与并发防护测试

**Files:**
- Modify: `cachedb/test_cachedb.py`（只加测试）
- Production code: 预期无需修改；若并发用例失败，回报后修复。

**Interfaces:**
- Consumes: Task A–D 的全部接口。

- [ ] **Step 1: 追加集成测试**

```python
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
```

- [ ] **Step 2: 运行测试**

Run: `python -m pytest cachedb/test_cachedb.py -k "restart or default_file or concurrent" -v`

Expected: PASS。若失败，记录失败输出，不改测试来迁就实现。

- [ ] **Step 3: 运行全量测试**

Run: `python -m pytest cachedb/test_cachedb.py -v`

Expected: 53 passed。

- [ ] **Step 4: 提交**

```bash
git add cachedb/test_cachedb.py
git commit -m "test: 增加持久化集成与并发测试"
```

---

### Task F: 全量回归与计划收尾

**Files:**
- Modify: `cachedb/plans/2026-11-09-persistence-plan.md`（勾选复选框）

- [ ] **Step 1: 运行全量测试并记录输出**

Run: `python -m pytest cachedb/test_cachedb.py -v`

Expected: 53 passed，0 failed。

- [ ] **Step 2: 确认 Task 1 测试数量未减少**

Run: `python -m pytest cachedb/test_cachedb.py -v --collect-only`

Expected: 收集到 53 个测试，其中原六个接口用例的断言未被修改。

- [ ] **Step 3: 勾选本计划全部复选框并提交**

```bash
git add cachedb/plans/2026-11-09-persistence-plan.md
git commit -m "docs: 标记 Task 2 实施计划全部完成"
```

---

## Self-Review

- Spec 覆盖：save（A）、load（B）、启动加载（C）、定时与停止（D）、集成/并发（E）、回归（F）；线程安全锁在 A 引入，E 验证。
- 类型一致性：`file_path: str | Path`、`save/load/stop_auto_save -> bool` 在所有任务中一致。
- Review Focus 每项都有对应测试（A、B、C、D、E）。
- 未覆盖：权限错误与磁盘满无法在跨平台测试中稳定模拟，由 `test_save_raises_oserror_for_missing_directory` 代表 IO 失败路径。
