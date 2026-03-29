# pygomoku

`pygomoku` 是一个使用 Python 编写、并通过 native / Cython 加速关键热点的自由规则五子棋引擎项目。

项目目标不是做一个演示性质的小程序，而是做一个：

- 自由无禁手的五子棋引擎
- 具备较强实战能力、可持续迭代的搜索程序
- 以 Python 为主实现，同时保留明确的 native 加速路径
- 支持人机对战 GUI
- 支持 Gomocup 协议，可与其他 AI 对战

该项目的直接目的，是让 `pygomoku` 在实际对战中稳定战胜 `opponent/zhou/` 中的另一个五子棋程序 `zhou`。

本项目可以理解为一个以 `SlowRenju` 为核心参考、面向 Python/Cython 的自由规则五子棋引擎重实现。本文最后附有致谢说明。

本仓库以 GNU GPL v3.0 发布，完整文本见根目录 `LICENSE`。

## 特性概览

- 15x15 自由规则五子棋
- 当前主线引擎（仓库内部称 `classic`）
- 迭代加深 + Alpha-Beta + TT + 候选点裁剪
- VCF 战术搜索
- Cython 可选加速
- Pygame GUI 人机对战
- Gomocup 协议引擎入口
- 与仓库内 `zhou` 对手程序做固定开局对战测试
- 完整的单元测试、搜索测试、协议测试和集成测试

## 项目目标

这个仓库当前关注的是一条非常明确的工程路线：

1. 保持当前主线引擎（仓库内部称 `classic`）行为稳定、确定、可验证。
2. 在不破坏语义的前提下，持续提升实战速度。
3. 把热点逐步迁移到 Cython / native，加速搜索、评估和战术模块。
4. 通过 GUI、Gomocup 协议和固定开局对战来做实际验证。

## 坐标约定

本项目统一使用 `(x, y)` 坐标：

- `x` 表示列
- `y` 表示行

也就是说，坐标语义是“先列后行”。

这一点要特别注意，因为仓库内对手程序 `zhou` 的很多内部逻辑更习惯使用
`(row, col)`，也就是“先行后列”。两边在对战脚本里会做显式转换，但阅读日志、
分析开局和手工构造测试局面时，仍然要始终记住这个差异。

## 目录结构

仓库当前主要由以下几部分组成：

```text
gomoku-py/
├── pygomoku/                   # 主引擎代码
│   ├── search/                 # root / alphabeta / movegen / ordering / tt
│   ├── eval/                   # 局部评估、全局评估、缓存
│   ├── patterns/               # 棋型、bucket、线型工具
│   ├── threats/                # VCF / VCT / tactical board
│   ├── protocol/               # Gomocup 协议适配
│   ├── gomocup_engine.py       # Gomocup 协议命令行入口
│   └── gui.py                  # Pygame GUI 入口
├── opponent/
│   ├── run_pygomoku_vs_zhou.py # pygomoku vs zhou 对战脚本
│   └── zhou/                   # 仓库内对手程序
├── benchmarks/                 # 性能与自对弈烟雾测试
├── tests/                      # 测试
├── setup.py                    # Cython 扩展构建
└── pyproject.toml              # 项目配置
```

## 核心组成

### 1. 主引擎 `pygomoku/`

这是仓库的核心部分。

- `pygomoku/search/` 负责搜索主流程
- `pygomoku/eval/` 负责局面评估与增量缓存
- `pygomoku/patterns/` 负责棋型和 bucket 语义
- `pygomoku/threats/` 负责 VCF 等战术模块
- `pygomoku/protocol/` 负责 Gomocup 协议接入

### 2. GUI

`pygomoku/gui.py` 提供本地人机对战界面，当前只使用仓库内的主线引擎，不再依赖外部二进制引擎切换。

### 3. Gomocup 协议入口

`pygomoku/gomocup_engine.py` 提供标准输入输出式的 Gomocup 引擎入口，便于和其他 AI 进行协议对战。

### 4. 对手程序 `zhou`

`opponent/zhou/` 是当前仓库内保留的对手程序。

`opponent/run_pygomoku_vs_zhou.py` 用于固定开局批量对战，是当前阶段很重要的实战验证工具。

### 5. Cython 加速

仓库在多个热点模块中保留了 `.pyx` 扩展，例如：

- `patterns/_line_cy.pyx`
- `eval/_local_cy.pyx`
- `eval/_caches_cy.pyx`
- `search/_movegen_cy.pyx`
- `search/_ordering_cy.pyx`
- `threats/_threat_board_cy.pyx`

这些扩展是当前项目非常重要的一部分。

## 强烈建议 Cython 加速

这个项目**不编译 Cython 也可以运行**，因为 Python fallback 路径是保留的。

但是要明确：

- 不编译时，功能上可以工作
- 不编译时，速度通常会明显偏慢
- 在搜索、局部评估、候选生成、战术判断等热点上，纯 Python 版本的实战效率会差很多

仓库当前已经验证过这一点：把 `pygomoku/` 下已编译的 `.so` 临时移走后，
`tests/test_config.py` 与 `tests/test_search.py` 仍可通过，说明 fallback 到
Python 实现是可用的；只是速度明显不适合作为常态运行方式。

因此对实际使用来说：

- 如果你只是阅读代码、做少量功能验证，可以先不编译
- 如果你要跑较深搜索、GUI 实战、批量测试、与 `zhou` 对战，**强烈建议先编译 Cython**

简单说：

- Python fallback 是“能跑”
- Cython 编译是“能用得起来”

## 环境要求

建议环境：

- Python 3.11 或更高版本
- Linux 或 macOS
- 可用的 C/C++ 编译工具链
- `pip`

常用 Python 依赖：

- `Cython`
- `pytest`
- `pytest-xdist`
- `pygame`

## 安装

### 基础安装

推荐先用可编辑方式安装主包：

```bash
pip install -e .
```

如果你需要 GUI：

```bash
pip install -e ".[gui]"
```

如果你要做开发和测试，建议至少安装：

```bash
pip install -U pip setuptools wheel
pip install cython pytest pytest-xdist pygame
pip install -e ".[gui]"
```

完成上述安装后，README 里的大多数命令都可以直接运行，不需要额外加
`PYTHONPATH=.`。

## Cython 编译

### Linux

先准备编译环境。

Debian / Ubuntu 常见做法：

```bash
sudo apt update
sudo apt install -y build-essential python3-dev
python -m pip install -U pip setuptools wheel cython
```

然后在仓库根目录编译：

```bash
python setup.py build_ext --inplace
```

如果要跑对战，强烈建议把 `zhou` 的 Cython 扩展也编译出来，执行：

```bash
python opponent/zhou/setup.py build_ext --inplace
```

### macOS

先准备 Apple 的命令行编译工具：

```bash
xcode-select --install
python -m pip install -U pip setuptools wheel cython
```

然后在仓库根目录编译：

```bash
python setup.py build_ext --inplace
```

同时编译 `zhou`：

```bash
python opponent/zhou/setup.py build_ext --inplace
```

### 编译说明

编译完成后，热点模块会生成对应的本地扩展文件，运行时会优先尝试使用这些已编译模块。

如果你修改了 `.pyx` 文件，通常需要重新执行：

```bash
python setup.py build_ext --inplace
```

## GUI 运行

GUI 入口是：

```bash
python -m pygomoku.gui
```

也可以显式指定搜索参数：

```bash
python -m pygomoku.gui --depth 5 --width 20
```

如果没有安装 `pygame`，GUI 不会启动。

## Gomocup 协议运行

命令行协议入口：

```bash
python -m pygomoku.gomocup_engine
```

指定固定搜索参数：

```bash
python -m pygomoku.gomocup_engine --depth 5 --width 20
```

这一路径适合：

- 接入 Gomocup 协议环境
- 与其他 AI 做协议对战
- 被对战脚本作为引擎进程拉起

## 测试

### 推荐做法

仓库测试已经按用途做了分组，推荐优先使用并行运行。

全量回归：

```bash
python -m pytest -n auto -q
```

### 测试分组

快速测试：

```bash
python -m pytest -m fast -q
```

搜索 / 评估 / 战术相关测试：

```bash
python -m pytest -m alignment -n auto -q
```

协议 / GUI / 集成测试：

```bash
python -m pytest -m integration -n auto -q
```

### 基础 smoke 建议

如果你只是想快速确认主线没有坏：

```bash
python -m pytest tests/test_config.py tests/test_search.py tests/test_protocol.py -n auto -q
```

GUI 相关 smoke：

```bash
python -m pytest tests/test_gui.py -q
```

## 与 `zhou` 的对战测试

当前阶段一个非常重要的目标，是在对战中压过仓库内的 `zhou`。

对战脚本：

```bash
python opponent/run_pygomoku_vs_zhou.py --help
```

### 快速跑一组固定开局

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

这里的 `pygomoku-direct` 表示直接在进程内调用 Python 引擎入口，适合做本地快速验证。
这条路径已经做过最小实测。

### 使用 Gomocup 协议入口对战

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

这里的 `pygomoku` 表示通过 `python -m pygomoku.gomocup_engine` 拉起标准
Gomocup 协议引擎进程，更接近外部对战环境，但 Gomocup 协议链路目前还没有专门优化，所以速度会稍慢。这条路径也已经做过最小实测。

### 扩大到 9 个固定开局

```bash
python opponent/run_pygomoku_vs_zhou.py \
  --engine-type pygomoku-direct \
  --opening-set 9 \
  --pygomoku-depth 5 \
  --pygomoku-width 20 \
  --zhou-depth 5 \
  --parallel 18 \
  --colors both
```

### 固定开局集合说明

对战脚本使用的是首手固定开局，坐标采用 `(x, y)`，范围是 `0..14`。
也就是说 `(7, 7)` 是天元。

再次强调：这里的 `(x, y)` 是“列, 行”，不是 `zhou` 那边常见的“行, 列”。

`--opening-set 5` 包含这 5 个首手：

- `(7, 7)`
- `(4, 4)`
- `(4, 10)`
- `(10, 4)`
- `(10, 10)`

`--opening-set 9` 在上面 5 个基础上，再加 4 个更靠边角的位置：

- `(2, 2)`
- `(2, 12)`
- `(12, 2)`
- `(12, 12)`
- `(4, 4)`
- `(10, 4)`
- `(4, 10)`
- `(10, 10)`
- `(7, 7)`

如果再配合 `--colors both`，那么每个固定开局都会分别测试 `pygomoku` 执黑和执白两种情况。

### 输出结果

脚本默认会把黑白两边结果分别写到 `opponent/` 目录下的 JSON 文件，方便后续比较与分析。

### 常用参数说明

- `--engine-type`：选择 `pygomoku-direct` 或 `pygomoku`。前者直接调用 Python 引擎入口，后者通过 `python -m pygomoku.gomocup_engine` 拉起 Gomocup 协议进程。
- `--opening-set`：选择固定开局集合，目前支持 `5` 和 `9`。
- `--pygomoku-depth`：`pygomoku` 的搜索深度，默认5。
- `--pygomoku-width`：`pygomoku` 根节点候选宽度，默认20，通常越大搜索越多，但也越慢。
- `--zhou-depth`：`zhou` 的搜索深度，默认5。
- `--parallel`：并行对局进程数，决定批量测试速度，也会显著影响机器负载。
- `--colors`：选择只测 `black`、只测 `white`，或者 `both`。
- `--limit-openings`：只取前几个固定开局，适合快速 smoke。
- `--max-moves`：单局最大手数，默认120，用来避免极端情况下对局拖太久。
- `--output-black` / `--output-white`：分别指定黑方测试和白方测试的结果 JSON 输出路径。

## 性能与调试

仓库自带一些性能与冒烟脚本：

- `benchmarks/profile_search.py`
- `benchmarks/hotspot_report.py`
- `benchmarks/selfplay_smoke.py`
- `benchmarks/cache_audit.py`

例如：

```bash
python benchmarks/profile_search.py --depth 2 --width 12 --top 25
python benchmarks/hotspot_report.py --top 20
python benchmarks/selfplay_smoke.py
```

如果你还没有执行 `pip install -e .`，那么像 `profile_search.py` 这种直接从
子目录启动的脚本，可能需要这样运行：

```bash
PYTHONPATH=. python benchmarks/profile_search.py --depth 2 --width 12 --top 25
```

## 开发建议

- 优先把当前主线引擎当成唯一语义主线，仓库内部仍沿用 `classic` 这个名字。
- 性能优化前先保证语义稳定。
- 改热点时尽量保留 Python fallback。
- 不要把“感觉更强”当成充分证据，尽量让修改有测试、基准或实战结果支撑。
- 运行广泛测试时优先用并行：`python -m pytest -n auto -q`

## 致谢

感谢 GitHub 上的 [SlowRenju](https://github.com/wind23/SlowRenju) 项目。

虽然本项目当前已经收敛为自己的 Python 主线引擎，但它仍然可以理解为一个以 `SlowRenju` 为核心参考、面向 Python/Cython 的自由规则五子棋引擎重实现。
这个仓库的很多关键概念，并不是凭空设计出来的，而是在吸收和消化这些成熟经验之后逐步落地的。仓库内部仍沿用 `classic` 这个名字来指代这条主线。
