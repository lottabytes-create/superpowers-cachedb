# Task 2 CacheDB 持久化功能设计规格

- 实验：实验 4 熟悉 Superpowers 的七步标准流程（Task 2）
- 阶段：步骤 1 需求澄清（brainstorming）
- 日期：2026-11-09
- 状态：已获确认，待进入开发计划
- 前置：Task 1 已合并到 `main`（e965ebb），六接口与 30 个测试通过

## 1. 目标

在现有 `CacheDB` 上增加 JSON 持久化能力，使数据在程序重启后恢复：

- `save()`：立即把内存数据写入 JSON 文件。
- `load()`：从 JSON 文件恢复数据。
- 启动加载：初始化时自动恢复已有数据。
- 定时持久化：按固定间隔自动保存，可配置、可关闭。
- 默认文件：当前工作目录下的 `cachedb_data.json`。

保留 Task 1 的 `set/get/delete/exists/keys/clear` 六个接口及其行为。

## 2. 范围

### 目标

- JSON 格式，单层对象 `{"key": "value"}`。
- 默认间隔 5 秒（指导书建议值）。
- 构造参数可开启/关闭定时保存。
- 启动加载独立于定时保存开关。
- 定时线程可停止、可回收，不泄漏。
- 六个原接口在并发保存时数据一致。

### 非目标

- 多进程、文件锁、分布式一致性。
- 原子写（临时文件 + rename）、崩溃恢复、备份轮转。
- 自定义序列化格式、压缩、加密。
- 命令行或网络接口。
- Task 1 六接口的行为变更。

## 3. 约束（来自实验指导书）

- Python 3.10+，pytest，Git。
- 存储格式 JSON；文件路径为当前工作目录，固定文件名 `cachedb_data.json`。
- 定时持久化间隔默认 5 秒；可通过构造参数开启/关闭。
- 交付物：更新 `cacheDB.py`、`test_cachedb.py`，更新 `specs/`、`plans/`。
- 分支名 `feature/persistence`。

说明：指导书写「从 feature/basic-cache 创建新分支」，用户要求从 `main` 创建。
`feature/basic-cache` 已合并进 `main`，内容一致，按用户要求从 `main` 创建。

## 4. 方案选择

| 方案 | 说明 | 结论 |
|---|---|---|
| A. `CacheDB` 内置守护线程 + `threading.Event` | 复用现有类，单线程循环，停止确定 | 采用 |
| B. `threading.Timer` 链式重排 | 每周期新建线程，停止/重排复杂，易泄漏 | 不采用 |
| C. 独立 `PersistenceManager` 类/模块 | 分层清晰，但本实验规模属于过度设计 | 不采用 |

## 5. 接口设计

```python
class CacheDB:
    def __init__(
        self,
        file_path: str = "cachedb_data.json",
        auto_save: bool = True,
        auto_save_interval: float = 5.0,
    ) -> None: ...

    # Task 1 原有接口，签名与行为不变
    def set(self, key: str, value: str) -> bool: ...
    def get(self, key: str) -> str | None: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def keys(self) -> list[str]: ...
    def clear(self) -> bool: ...

    # 新增
    def save(self) -> bool: ...
    def load(self) -> bool: ...
    def stop_auto_save(self) -> bool: ...
```

### 新增方法契约

| 方法 | 行为 | 返回值 | 异常 |
|---|---|---|---|
| `save()` | 把当前全部数据写入 `file_path`，UTF-8，`ensure_ascii=False`，`indent=2` | `True` | `OSError` 读写失败 |
| `load()` | 读取文件并**替换**内存数据；文件不存在时内存不变 | 成功 `True`；不存在 `False` | 内容非法 `ValueError`；读写失败 `OSError` |
| `stop_auto_save()` | 停止定时线程并 `join`，可重复调用 | 之前运行中 `True`，否则 `False` | 无 |

### 构造行为

1. 初始化 `_data = {}`、锁、停止事件。
2. 若 `auto_save_interval <= 0`，抛 `ValueError`。
3. 调用 `load()` 自动恢复（文件不存在时为空库）。
4. 若 `auto_save=True`，启动守护线程。
5. `auto_save=False` 时不创建线程，但启动加载仍执行。

## 6. 数据格式

```json
{
  "name": "alice",
  "empty": ""
}
```

- 顶层必须是 JSON 对象。
- value 必须是字符串；key 在 JSON 中天然为字符串。
- 空库保存为 `{}`。

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| 文件不存在（`load`/启动） | 返回 `False`，按空库继续 |
| JSON 语法错误 | 抛 `ValueError` |
| 顶层不是对象 | 抛 `ValueError` |
| value 不是字符串 | 抛 `ValueError` |
| 权限/磁盘等 IO 错误 | `save/load` 向外抛 `OSError` |
| 定时线程内 `save()` 失败 | 记录 `logging.warning`，线程继续下一周期 |
| `auto_save_interval <= 0` | 构造时抛 `ValueError` |

原则：手动调用失败要显式暴露；定时任务失败不能静默杀死线程，也不能丢诊断信息。
`clear()` 只清内存，不删除文件；下一次保存写入 `{}`。

## 8. 线程安全与资源回收

- 使用 `threading.RLock` 保护六个原方法、`load()` 与 `save()` 的快照步骤。
- `save()` 在锁内复制 `dict(self._data)`，锁外执行文件 IO，避免阻塞缓存操作。
- 定时线程：`threading.Thread(daemon=True)`，循环
  `while not self._stop_event.wait(interval): self.save()`。
- `stop_auto_save()` 置位事件并 `join()` 线程；重复调用安全。
- 明确不保证多实例同时读写同一文件的正确性。

## 9. 兼容性与测试隔离

现有测试使用无参 `CacheDB()`。引入持久化后：

- 启动加载可能读取工作目录残留的 `cachedb_data.json`，破坏测试前置条件。
- 默认开启定时线程会让每个测试遗留后台线程。

因此把测试 fixture 改为：

```python
@pytest.fixture
def db(tmp_path):
    return CacheDB(file_path=tmp_path / "cachedb_data.json", auto_save=False)
```

`test_new_cache_instance` 同样使用临时路径并关闭定时保存。Task 1 的测试断言与数量保持不变。

## 10. 测试策略

新增约 15 个用例：

- `save`：文件创建、JSON 内容正确、空库、中文。
- `load`：缺失返回 `False` 且不改内存、正常恢复、替换旧数据、
  损坏 JSON / 非对象 / 非字符串值抛 `ValueError`。
- 启动加载：已有文件自动恢复；无文件为空库。
- 定时保存：短间隔自动写盘、`stop_auto_save()` 后不再写、
  `auto_save=False` 不写文件、重复 stop 幂等。
- 集成：`save` → 新实例 → 数据完整恢复。
- 并发冒烟：定时保存期间持续写入不抛异常，最终文件可解析。
- 回归：原 30 个测试全部通过。

## 11. 文件组织

```
cachedb/
├── cacheDB.py                                  # 修改
├── test_cachedb.py                             # 修改
├── specs/2026-11-09-persistence-design.md      # 新增
└── plans/2026-11-09-persistence-plan.md        # 新增
```

## 12. Git 与流程

- 从 `main`（e965ebb）创建分支 `feature/persistence` 与工作树
  `.worktrees/feature-persistence`。
- 任务按 A–F 拆分，每个任务 TDD（RED → GREEN）后提交。
- 每任务独立评审，最后全分支评审，再合并到 `main`。
- 不修改 Task 1 的历史提交。

## 13. 报告留痕

- 本设计文档：需求、方案取舍、接口与错误处理决策。
- `plans/`：任务拆分与完成状态。
- 任务报告：每个任务的 RED/GREEN 真实输出。
- 评审包与评审结论。
- Git 分支、提交、合并记录。
- 最终全量测试输出。
