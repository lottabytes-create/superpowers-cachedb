# Task 1 基础缓存数据库 CacheDB 设计规格

- 实验：实验 4 熟悉 Superpowers 的七步标准流程
- 阶段：步骤 1 需求澄清（brainstorming）
- 日期：2026-11-09
- 状态：已获确认，待进入开发计划

## 1. 目标

用 Python 实现一个类似 Redis 子集的内存缓存数据库 `CacheDB`，支持六个基本操作，
使用 pytest 测试。通过本任务完整走一遍 Superpowers 七步流程。

## 2. 范围

### 目标

- 纯内存存储，进程退出即丢失数据。
- 仅支持字符串类型的 key 和 value。
- 以 Python API 形式提供能力，不提供命令行接口。
- 提供 `set`、`get`、`delete`、`exists`、`keys`、`clear` 六个方法。
- 使用 pytest 编写自动化测试。

### 非目标

- 不实现 TTL/过期、容量上限、淘汰策略、并发控制。
- 不实现持久化（属于 Task 2）。
- 不提供命令行、网络服务或可视化界面。
- 不引入第三方运行时依赖。

## 3. 约束

来自实验指导书：

- 运行环境 Python 3.10+，测试框架 pytest，版本控制 Git。
- 数据类型仅字符串；接口方式 Python API。
- 错误处理：键不存在时 `get` 返回 `None`，其他错误抛出异常。
- 存储方式纯内存。
- 分支名固定为 `feature/basic-cache`。
- 交付物路径固定：
  - `cachedb/cacheDB.py`
  - `cachedb/test_cachedb.py`
  - `cachedb/specs/`
  - `cachedb/plans/`

当前环境实测：Python 3.12.4、pytest 9.1.1、git 2.55.0。

## 4. 方案选择

| 方案 | 说明 | 结论 |
|---|---|---|
| A. 单类组合 `dict` | `CacheDB` 内部持有 `_data: dict[str, str]`，只暴露六个方法 | 采用 |
| B. 继承 `dict` / `UserDict` | 代码更少，但暴露 `update`、`pop`、`items` 等非规范接口 | 不采用 |
| C. 抽象存储后端接口 | 为后续持久化预留抽象层 | 不采用，当前规模属于过度设计 |

选择理由：接口封闭、实现直白、行为容易测试，符合「不做不必要扩展」的要求。

## 5. 数据模型

```python
class CacheDB:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
```

- 唯一状态为 `_data`，保持 Python 3.7+ 的插入顺序。
- 不对外暴露 `_data`，避免外部绕过接口修改数据。

## 6. 接口契约

| 方法 | 输入 | 行为 | 返回值 | 异常 |
|---|---|---|---|---|
| `set(key, value)` | 两个 `str` | 写入；key 已存在时更新 value | `True` | key 或 value 非 `str` → `TypeError` |
| `get(key)` | `str` | 读取指定 key 的值 | value；不存在返回 `None` | key 非 `str` → `TypeError` |
| `delete(key)` | `str` | 存在则删除 | `True`；不存在 `False` | key 非 `str` → `TypeError` |
| `exists(key)` | `str` | 判断 key 是否存在 | `True` / `False` | key 非 `str` → `TypeError` |
| `keys()` | 无 | 返回所有 key 的快照 | 新的 `list[str]`，按插入顺序 | 无 |
| `clear()` | 无 | 清空缓存 | `True` | 无 |

## 7. 边界情况

- 空字符串 `""` 作为 key 或 value 合法。
- Unicode、含空格、较长字符串合法。
- 覆盖已有 key 只更新 value，不改变其在插入顺序中的位置。
- `delete` 不存在的 key 返回 `False`，不抛异常。
- 空库执行 `clear()` 返回 `True`。
- `keys()` 返回新列表，外部修改该列表不影响内部数据。
- value 为 `""` 时 `get` 返回 `""`（假值），需配合 `exists()` 区分「空值」与「不存在」。
- 非 `str` 的 key/value 一律抛 `TypeError`，依据「仅支持字符串」与「其他错误抛异常」。

## 8. 文件组织

```
cachedb/
├── cacheDB.py                              # CacheDB 主类
├── test_cachedb.py                         # pytest 测试
├── specs/2026-11-09-basic-cache-design.md  # 本文档
└── plans/2026-11-09-basic-cache-plan.md    # 步骤 3 生成
```

- 不创建 `__init__.py`，按指导书交付物保持扁平结构。
- pytest 会自动把测试文件所在目录加入 `sys.path`，测试中直接 `from cacheDB import CacheDB`。

## 9. 测试策略

- 使用 pytest，`fixture` 为每个用例创建独立 `CacheDB` 实例。
- 覆盖范围：
  - `set`：正常写入、覆盖更新、返回 `True`、类型错误。
  - `get`：存在、不存在、空字符串值、类型错误。
  - `delete`：存在删除、不存在返回 `False`、删除后不可读取、类型错误。
  - `exists`：存在、不存在、删除后、类型错误。
  - `keys`：空库、多键、插入顺序、返回副本、类型无关。
  - `clear`：清空数据、空库清空、清空后六个方法行为一致。
- 重复场景用 `pytest.mark.parametrize` 压缩。
- 每个方法按 TDD 执行 RED → GREEN → REFACTOR，最后运行全量测试。

## 10. Git 与流程

- 当前目录此前不是 Git 仓库，先 `git init`，默认分支 `main`。
- 使用 `using-git-worktrees` 在 `.worktrees/feature-basic-cache` 创建工作树，
  分支 `feature/basic-cache`，`.worktrees/` 加入 `.gitignore`。
- 开发任务按「骨架 + 六个方法」拆为 7 个小任务，每个任务一次提交。
- 六个方法在同一文件内，按顺序串行开发，不并行实现以避免冲突。
- 完成后合并 `feature/basic-cache` 到 `main`，删除工作树。
- Task 2 从 `main` 新建 `feature/persistence`。

## 11. 报告留痕

后续实验报告所需的证据，全部来自真实执行：

- 本文档：需求分析、方案取舍、接口设计。
- `plans/`：任务拆分与完成状态。
- pytest 输出：RED 阶段失败证据、GREEN 阶段通过证据、最终全量结果。
- Git：分支、提交记录、合并记录。
- 代码评审：检查项、发现的问题、修复记录。
- 最终验证：验证命令与真实输出。
