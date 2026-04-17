# AGENTS.md

## 项目概述

`pygomoku` 是一个 **Python + Cython** 的自由规则五子棋引擎项目，目标不是教学 demo，而是维护一条可验证、可持续优化、具备实战能力的 `classic` 主线引擎。

核心能力：

- 15x15 自由规则五子棋引擎
- 迭代加深 + Alpha-Beta + TT + 候选点裁剪
- VCF 战术搜索
- 可选 Cython 热点加速
- Pygame GUI 人机对战
- Gomocup 协议引擎入口
- 与仓库内基线对手 `opponent/zhou` 的固定开局批量对战

**关键**：本项目当前最重要的工程目标，是在不破坏 `classic` 语义的前提下，持续提升速度和实战强度，并在对战中稳定压过 `zhou`。

技术栈：

- Python 3.11+
- setuptools / editable install
- Cython 可选扩展
- pytest + pytest-xdist
- pygame（GUI 可选）

## 快速开始

基础安装：

```bash
python -m pip install -U pip setuptools wheel
python -m pip install -e .
```

安装 GUI 依赖：

```bash
python -m pip install -e ".[gui]"
```

开发常用依赖：

```bash
python -m pip install cython pytest pytest-xdist pygame
python -m pip install -e ".[gui]"
```

## 开发命令

### 安装与构建

编译主项目 Cython 扩展：

```bash
python setup.py build_ext --inplace
```

编译 `zhou` 的 Cython 扩展：

```bash
python opponent/zhou/setup.py build_ext --inplace
```

⚠️ **警告**：项目支持 Python fallback，但搜索、局部评估、候选生成、战术模块在未编译 Cython 时会明显变慢。做深搜索、GUI 实战或批量对战前，优先编译扩展。

### 运行引擎

启动 GUI：

```bash
python -m pygomoku.gui
```

带固定参数启动 GUI：

```bash
python -m pygomoku.gui --depth 5 --width 20
```

启动 Gomocup 协议引擎：

```bash
python -m pygomoku.gomocup_engine
```

带固定参数启动 Gomocup 引擎：

```bash
python -m pygomoku.gomocup_engine --depth 5 --width 20
```

### 测试命令

全量回归：

```bash
python -m pytest -n auto -q
```

快速测试：

```bash
python -m pytest -m fast -q
```

搜索 / 评估 / 战术回归：

```bash
python -m pytest -m alignment -n auto -q
```

协议 / GUI / 集成测试：

```bash
python -m pytest -m integration -n auto -q
```

最小 smoke：

```bash
python -m pytest tests/test_config.py tests/test_search.py tests/test_protocol.py -n auto -q
```

单文件调试：

```bash
python -m pytest tests/test_search.py -q
python -m pytest tests/test_vcf.py -q
python -m pytest tests/test_protocol.py -q
```

⚠️ **警告**：如果本地未安装 `pytest-xdist`，把命令里的 `-n auto` 去掉。

### 性能与对战

搜索性能分析：

```bash
python benchmarks/profile_search.py --depth 2 --width 12 --top 25
```

热点报告：

```bash
python benchmarks/hotspot_report.py --top 20
```

自对弈 smoke：

```bash
python benchmarks/selfplay_smoke.py
```

缓存审计：

```bash
python benchmarks/cache_audit.py
```

如果未执行 editable install，可显式加 `PYTHONPATH`：

```bash
PYTHONPATH=. python benchmarks/profile_search.py --depth 2 --width 12 --top 25
```

对战 `zhou`，直接调用本进程引擎：

```bash
python opponent/run_pygomoku_vs_zhou.py \
  --engine-type pygomoku-direct \
  --opening-set 5 \
  --pygomoku-depth 5 \
  --pygomoku-width 20 \
  --zhou-depth 5 \
  --parallel 10 \
  --colors both
```

对战 `zhou`，走 Gomocup 协议链路：

```bash
python opponent/run_pygomoku_vs_zhou.py \
  --engine-type pygomoku \
  --opening-set 5 \
  --pygomoku-depth 5 \
  --pygomoku-width 20 \
  --zhou-depth 5 \
  --parallel 10 \
  --colors both
```

## 项目结构

```text
pygomoku/
├── pygomoku/
│   ├── board.py               # 棋盘状态、play/undo、winner、zobrist_key
│   ├── config.py              # 默认参数表、运行时配置、root search 默认值
│   ├── constants.py           # 15x15、BLACK/WHITE/EMPTY、搜索常量
│   ├── gui.py                 # Pygame GUI 入口
│   ├── gomocup_engine.py      # Gomocup CLI 入口
│   ├── protocol/              # Gomocup 协议适配
│   ├── search/                # root / alphabeta / movegen / ordering / tt
│   ├── eval/                  # 局部评估、全局评估、缓存、Cython fallback
│   ├── patterns/              # line、shape、bucket、shape table
│   ├── threats/               # threat board、VCF / VCT
│   └── zobrist.py             # Zobrist 哈希表
├── opponent/
│   ├── run_pygomoku_vs_zhou.py # 固定开局批量对战入口
│   └── zhou/                   # 仓库内对手基线
├── benchmarks/                 # 性能、热点、自对弈、缓存检查
├── tests/                      # fast / alignment / integration 测试
├── setup.py                    # Cython 扩展构建
├── pyproject.toml              # 项目元数据与 pytest 配置
└── README.md                   # 项目说明与标准命令
```

核心职责：

- `board.py`：唯一可信棋盘状态机，任何搜索、协议、GUI 都依赖它。
- `search/`：主搜索语义核心，修改时优先考虑行为稳定性。
- `eval/`：增量评估缓存与全局评分逻辑，性能敏感且容易引入隐蔽回归。
- `threats/`：VCF 战术模块，常在根节点和搜索中作为捷径或过滤器。
- `protocol/`：协议兼容层，要求稳健、可恢复、对非法输入有明确处理。
- `opponent/run_pygomoku_vs_zhou.py`：当前最重要的实战验证工具之一。

## 项目特有约定

### 坐标与数据表示

**关键**：项目统一使用 `(x, y)`，即 `(列, 行)`，不是 `(row, col)`。

- `x` 表示列
- `y` 表示行
- `Move` 是扁平化整数索引
- 使用 `xy_to_move()` / `move_to_xy()` 做转换

⚠️ **警告**：`opponent/zhou` 大量内部逻辑使用 `(row, col)`。跨模块、跨引擎传坐标时必须显式转换，不能靠默认习惯猜测。

### 棋盘与颜色约定

- `BOARD_SIZE = 15`
- `BLACK = 1`
- `WHITE = -1`
- `EMPTY = 0`

不要引入与现有常量体系不兼容的布尔值、枚举映射或替代 side 编码。

### `classic` 主线语义

本项目不是“随便找个更强搜索器替换掉”。

- 以当前 `classic` 行为为主语义
- 优先保持确定性、可回归、可比较
- 性能优化必须尽量不改变已有语义
- 修改热点时，优先保留 Python fallback

### Cython 设计约束

- `.pyx` 是热点加速层，不是语义分叉层
- Python 实现应保持可运行、可测试
- 修改 `patterns`、`eval`、`search`、`threats` 的 Python 逻辑后，检查对应 Cython 路径是否也要同步

## 代码规范

### 命名与风格

- 模块、函数、变量使用 `snake_case`
- 类使用 `PascalCase`
- 常量使用 `UPPER_SNAKE_CASE`
- 优先使用显式类型标注
- 优先使用 `dataclass` 表达结构化数据
- 公共模块保留简洁 docstring，避免无信息量注释

### 编码要求

- 优先复用已有常量、辅助函数和缓存结构
- 搜索代码中不要绕过 `Board.play()` / `Board.undo()` 直接修改正式局面
- 仅在评估探测这种明确的临时分支场景下，才允许像 `global_eval.py` 那样做受控的直接 grid 写入，并且必须成对恢复
- 改动缓存逻辑时，必须同时考虑 `snapshot()` / `restore_snapshot()` 路径
- 改动协议逻辑时，必须同时考虑 `START`、`RESTART`、`BOARD`、`TURN`、`TAKEBACK` 这些状态转换

### 提交前自检

至少运行：

```bash
python -m pytest tests/test_config.py tests/test_search.py tests/test_protocol.py -q
```

如果改动了搜索、评估、候选点、VCF 或 Cython 对应模块，再运行：

```bash
python -m pytest -m alignment -n auto -q
```

如果改动了协议入口或 GUI，再运行：

```bash
python -m pytest -m integration -n auto -q
```

## 测试策略

测试框架：

- `pytest`
- `pytest-xdist`

测试分层：

- `fast`：基础结构和小型单元回归，适合高频运行
- `alignment`：搜索、评估、战术、classic 语义对齐
- `integration`：协议、子进程、GUI 入口

**关键**：这个项目的测试不只验证“能跑”，还在验证 `classic` 兼容行为和固定局面语义。修改以下模块时必须假设自己可能引入语义回归：

- `pygomoku/search/*`
- `pygomoku/eval/*`
- `pygomoku/threats/*`
- `pygomoku/protocol/*`

覆盖要求：

- 新功能必须附带对应测试
- 修 bug 必须优先补回归测试
- 改动搜索排序、TT、VCF、缓存恢复逻辑时，不接受“只有手工验证，没有自动测试”

## Agent 工作建议

适合本仓库的工作顺序：

1. 先读 `README.md` 与相关模块测试。
2. 改动前确认是否涉及 `(x, y)` 与 `(row, col)` 转换。
3. 先保语义，再做性能优化。
4. 先跑最小 smoke，再跑对应分层测试。
5. 搜索强度改动尽量补一组固定局面回归或 `zhou` 对战结果。

优先参考文件：

- `README.md`
- `pygomoku/search/root.py`
- `pygomoku/search/alphabeta.py`
- `pygomoku/eval/local.py`
- `pygomoku/eval/global_eval.py`
- `pygomoku/threats/vcf.py`
- `tests/test_search.py`
- `tests/test_eval.py`
- `tests/test_vcf.py`
- `tests/test_protocol.py`

⚠️ **警告**：不要把 `zhou` 的实现习惯直接搬到 `pygomoku` 主线。它是对手基线和参考对象，不是当前主引擎的语义来源。
