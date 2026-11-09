# CacheDB 基础缓存数据库实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用 TDD 实现一个纯内存、仅支持字符串的 Python 缓存数据库 `CacheDB`，支持六个基本操作并通过 pytest 全量测试。

**Architecture:** 单个 `CacheDB` 类内部持有 `dict[str, str]`，只暴露 `set/get/delete/exists/keys/clear` 六个方法；每个方法先写失败测试再写最小实现，每完成一个方法提交一次。

**Tech Stack:** Python 3.12（要求 3.10+）、pytest 9.1.1、Git

**Spec:** `cachedb/specs/2026-11-09-basic-cache-design.md`

## Global Constraints

- 仅支持 `str` 类型的 key 和 value；非 `str` 一律抛 `TypeError`。
- 纯内存存储，不使用文件、数据库或第三方运行时依赖。
- 接口为 Python API，不提供命令行入口。
- `get` 对不存在的 key 返回 `None`；`delete` 对不存在的 key 返回 `False`。
- 文件路径固定：`cachedb/cacheDB.py`、`cachedb/test_cachedb.py`。
- 所有命令都在工作树根目录 `d:\Create\Project\Superpowers\.worktrees\feature-basic-cache` 执行。
- 当前分支：`feature/basic-cache`。

## Review Focus

以下输入或条件最容易被实现者忽略，每条都已在对应任务中安排测试：

1. 空字符串 key/value：必须合法存储和读取，不能当作缺失处理（Task 2、Task 3）。
2. value 为 `""` 与 key 不存在：`get` 返回 `""` 与 `None`，必须能用 `exists` 区分（Task 5）。
3. `keys()` 返回值被外部修改：不得影响内部数据（Task 6）。
4. 覆盖已有 key：必须返回最新值，且不改变插入顺序（Task 3、Task 6）。
5. 非 `str` 的 key/value：必须抛 `TypeError`，而不是静默存储（Task 2 至 Task 5）。

---

### Task 1: 创建 CacheDB 基础类框架

**Files:**
- Create: `cachedb/cacheDB.py`
- Create: `cachedb/test_cachedb.py`

**Interfaces:**
- Produces: `class CacheDB`，构造签名 `CacheDB() -> None`，内部状态 `_data: dict[str, str]`。

- [x] **Step 1: 写失败测试**

```python
from cacheDB import CacheDB


def test_new_cache_instance():
    db = CacheDB()
    assert isinstance(db, CacheDB)
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'cacheDB'`

- [x] **Step 3: 实现类框架**

在 `cachedb/cacheDB.py` 中创建 `CacheDB` 类，`__init__` 初始化空字典 `self._data: dict[str, str] = {}`，不添加任何方法。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v`
Expected: PASS，1 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 创建 CacheDB 基础类框架"
```

---

### Task 2: 实现 set()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Modify: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: Task 1 的 `CacheDB`
- Produces: `set(self, key: str, value: str) -> bool`；私有校验方法 `_require_str(value: object, name: str) -> None`（非 `str` 抛 `TypeError`）

- [x] **Step 1: 写失败测试**

```python
import pytest

from cacheDB import CacheDB


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
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "set"`
Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'set'`

- [x] **Step 3: 实现 set()**

新增 `_require_str` 做类型校验，`set` 校验 key 与 value 后执行 `self._data[key] = value` 并返回 `True`。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "set"`
Expected: PASS，6 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.set()"
```

---

### Task 3: 实现 get()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Modify: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `set(key, value)`、`_require_str`
- Produces: `get(self, key: str) -> str | None`

- [x] **Step 1: 写失败测试**

```python
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
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "get"`
Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'get'`

- [x] **Step 3: 实现 get()**

校验 key 后返回 `self._data.get(key)`。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "get"`
Expected: PASS，5 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.get()"
```

---

### Task 4: 实现 delete()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Modify: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `set`、`get`、`_require_str`
- Produces: `delete(self, key: str) -> bool`

- [x] **Step 1: 写失败测试**

```python
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
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "delete"`
Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'delete'`

- [x] **Step 3: 实现 delete()**

校验 key；存在则删除并返回 `True`，不存在返回 `False`。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "delete"`
Expected: PASS，4 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.delete()"
```

---

### Task 5: 实现 exists()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Modify: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `set`、`delete`、`_require_str`
- Produces: `exists(self, key: str) -> bool`

- [x] **Step 1: 写失败测试**

```python
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
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "exists"`
Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'exists'`

- [x] **Step 3: 实现 exists()**

校验 key 后返回 `key in self._data`。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "exists"`
Expected: PASS，5 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.exists()"
```

---

### Task 6: 实现 keys()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Modify: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `set`、`delete`
- Produces: `keys(self) -> list[str]`，按插入顺序返回新列表

- [x] **Step 1: 写失败测试**

```python
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
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "keys"`
Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'keys'`

- [x] **Step 3: 实现 keys()**

返回 `list(self._data.keys())`。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "keys"`
Expected: PASS，5 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.keys()"
```

---

### Task 7: 实现 clear()

**Files:**
- Modify: `cachedb/cacheDB.py`
- Modify: `cachedb/test_cachedb.py`

**Interfaces:**
- Consumes: `set`、`get`、`keys`
- Produces: `clear(self) -> bool`

- [x] **Step 1: 写失败测试**

```python
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
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "clear"`
Expected: FAIL，`AttributeError: 'CacheDB' object has no attribute 'clear'`

- [x] **Step 3: 实现 clear()**

调用 `self._data.clear()` 后返回 `True`。

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest cachedb/test_cachedb.py -v -k "clear"`
Expected: PASS，4 passed

- [x] **Step 5: 提交**

```bash
git add cachedb/cacheDB.py cachedb/test_cachedb.py
git commit -m "feat: 实现 CacheDB.clear()"
```

---

## 全量验证

- [x] 运行 `python -m pytest cachedb/test_cachedb.py -v`
  Expected: 全部通过，0 failed
- [x] 运行 `git status`，确认工作区干净
- [x] 运行 `git log --oneline`，确认 7 个任务共 7 次功能提交
