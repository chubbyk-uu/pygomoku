# Acceleration Plan

## 目标

这份文档定义 `pyslow` 后续加速工作的规则、优先级和验收标准。

当前前提：

- `pyslow` 的核心搜索、评估、VCF 主链已经基本可运行。
- 当前性能瓶颈已经通过 benchmark/profile 初步识别。
- 接下来允许做性能工作，但性能工作不能破坏当前参考项目对齐目标。
- 当前阶段已经不再以“小修小补”为目标，而是以显著提高搜索吞吐为目标。

这份文档是后续加速工作的规则书。

当前阶段目标：

- 保持当前 `pyslow` 已验证语义不变。
- 对热点子系统做大提速，而不是继续零碎微调。
- 将最热、边界最稳定的 Python 子系统连同数据路径一起下沉到 `Cython/C`。
- 推动实际可用搜索规模向至少 `depth=8 width=20` 靠近。

## 核心原则

后续任何加速工作，都必须同时满足下面 3 条：

1. 不能改变原始语义  
   加速只能改变实现方式，不能改变参考项目对齐后的行为语义、返回值语义、候选点顺序语义、缓存更新语义、搜索终止语义。

2. 必须可以 fallback  
   所有加速路径都必须保留纯 Python 基线实现，并允许在运行时或构建时退回 Python 实现。

3. 必须有证据  
   每一项加速都必须提供两类证据：
   - 语义证据：证明行为未改变
   - 性能证据：证明确实更快

如果一项优化不能同时满足这 3 条，就不能进入主线。

## 两条加速路线

当前允许两类加速路线并行存在。

### 1. Python 内部重写提速

这类优化不引入 native 模块，只改 Python 实现方式。

典型方式：

- 减少对象分配
- 减少临时 list/tuple 构造
- 减少重复扫描
- 减少 `Board.at()` 这种高频小函数开销
- 改善缓存快照/恢复的数据布局
- 合并热点循环
- 将“通用逻辑”改成“专门热点路径”

优点：

- 保持开发简单
- 不引入构建复杂度
- fallback 天然存在

限制：

- 提速上限有限
- 对 `depth=6~10` 的目标未必足够
- 不能把“仅搬循环、不搬数据”的半下沉方案误判成真正的 native 路线

### 2. Native 模块加速

这类优化会引入 Python 之外的实现，例如：

- `Cython`
- `PyO3` / Rust
- 小型 C/C++ 扩展

当前不优先考虑把整个搜索器整体迁到 native。
优先考虑只把“热点且边界稳定”的局部模块迁出去。

当前推荐方式不是“把少量 helper 包进 Cython”，而是：

- 选定一个热点家族
- 一起下沉它的数据布局、核心循环、批量写回路径
- 让 Python 只保留调度、配置、协议、GUI 和 fallback

优点：

- 对热点循环可能有数量级提升

限制：

- 构建复杂度更高
- 语义偏差风险更高
- 更需要严格对拍和 fallback

## 不允许做的事

以下做法在当前阶段禁止：

- 为了提速而改动搜索语义
- 为了提速而改动候选点顺序
- 为了提速而改动评估值、bucket 语义、战术搜索返回语义
- 在没有 benchmark 证据前，提前引入复杂 native 工程
- 移除纯 Python 基线实现
- 用“更快但不完全一样”的近似算法替代参考项目语义
- 用 fresh-per-move Gomocup replay 代替真实整局持久引擎会话，再据此判断棋力

## 当前热点结论

基于当前 benchmark/profile，主要热点集中在：

1. `pyslow/eval/local.py`
2. `pyslow/search/movegen.py`
3. `pyslow/eval/global_eval.py`
4. `pyslow/eval/caches.py`
5. `pyslow/threats/vcf.py`

其中最值得优先处理的具体函数包括：

- `local.value_wide_compute`
- `local.compute_direction_shape`
- `local.compute_bucket_and_attack`
- `movegen.generate_candidates`
- `global_eval.evaluate_board`
- `global_eval._evaluate_last5_branch`
- `global_eval._evaluate_next43_branch`
- `caches.restore_snapshot`
- `vcf._search_attacker`
- `vcf._search_defender`

## 优先级

加速优先级按下面顺序执行。

### 第一优先级：先做 Python 内部重写

先处理这些模块：

1. `pyslow/eval/local.py`
2. `pyslow/search/movegen.py`
3. `pyslow/eval/global_eval.py`
4. `pyslow/eval/caches.py`

原因：

- 这些模块最热
- 边界相对稳定
- 纯 Python 重写成本低
- 更容易保持语义不变

目标：

- 先把明显的 Python 层开销打掉
- 再重新测 `depth=5`
- 再判断是否能把实际可用搜索规模推向 `depth=8 width=20`
- 判断是否还必须上 native

补充说明：

- 当前已经有足够证据表明，后续很可能必须进入更重的 native 阶段
- 因此纯 Python 重写的价值主要在于澄清成本模型和收紧边界，而不是指望它单独完成目标吞吐

### 第二优先级：再做局部 native

只有当第一优先级完成后，`depth=6` 仍明显不可接受，才进入 native。

native 第一批候选模块：

1. `pyslow/eval/local.py`
2. `pyslow/search/movegen.py`
3. `pyslow/eval/global_eval.py`
4. `pyslow/threats/vcf.py`

当前 native 阶段的原则：

- 不做“只把循环搬到 Cython，数据仍留在 Python object graph 中”的薄封装实验
- 优先做“数据 + 热计算链”一起下沉的整段实现
- 允许为此进行较大的子系统级重构，但必须保持语义等价并保留 Python fallback

native 最后才考虑的模块：

- `root.py`
- `alphabeta.py`
- `protocol/`

原因：

- 搜索外壳控制逻辑复杂，且 Python 层分支很多
- 真正的重热点不在这里

## 设计约束

### 纯 Python 优化约束

Python 重写必须满足：

- 对外接口不变
- 输入输出语义不变
- 测试不需要改 expected behavior
- 允许只减少中间对象和重复计算

允许的手段：

- 更扁平的数据结构
- 预分配容器
- 更少的 helper 层级
- 专用热点路径

### Native 优化约束

native 路线必须满足：

- Python 基线实现保留
- native 实现作为可选 backend
- backend 切换不改变外部 API
- backend 切换后结果必须可对拍

推荐结构：

- `pyslow/patterns/line.py`
  - 保留 Python 版接口
  - 可选导入 `_line_native`
- `pyslow/eval/local.py`
  - 保留 Python 版接口
  - 可选导入 `_eval_native`
- `pyslow/threats/threat_board.py`
  - 保留 Python 版接口
  - 可选导入 `_threat_native`

不允许：

- 直接在搜索主干里硬编码依赖 native
- 没有 Python fallback 的单实现路径

## Fallback 规则

所有 native 或加速 backend 都必须支持 fallback。

最低要求：

- native 模块不可用时，自动回到 Python 实现
- 测试环境必须能强制使用 Python 基线
- benchmark 环境必须能显式切换 backend 做比较

建议方式：

- 在 `config.py` 或独立 runtime 选项中加入 backend 选择项
- 支持：
  - `python`
  - `native`
  - `auto`

其中：

- `python`：强制纯 Python
- `native`：强制 native，不可用则报错
- `auto`：优先 native，不可用则 fallback

## 协议与对战验证规则

对于 Gomocup 引擎、GUI 和外部对战脚本：

- 必须优先使用整局持久引擎会话
- 一局只初始化一次引擎
- 后续逐手应优先使用 `TURN`
- 只有在状态无法保证一致时，才允许退回 `BOARD` 全量同步

禁止：

- 每走一步就 `RESTART`
- 用 fresh-per-move 协议驱动结果替代真实对战结果

原因：

- 这会改变 searcher 生命周期
- 会改变 TT / 持久搜索状态
- 会导致结果和真实协议使用方式不等价

## 语义验证规则

每一项加速都必须提供语义验证。

最低要求：

1. 单元测试不回归  
   所有现有测试必须通过。

2. 关键模块对拍  
   对以下模块做 Python 基线 vs 优化版 对拍：
   - `line`
   - `ValueWide` 局部更新
   - `global_eval`
   - `threat_board`
   - `vcf`

3. 搜索结果对拍  
   在固定局面集上，对比：
   - best move
   - score
   - 候选点排序关键结果
   - VCF 是否 found/solved

4. 自对弈 smoke 不失真  
   在固定参数下，自对弈前几手结果应一致，或在明确允许范围内保持等价。

注意：

如果某个优化导致“更快但 best move 变了”，默认视为语义破坏，除非已经证明参考语义允许这种非确定性。

## 性能验证规则

每一项加速都必须提供性能验证。

最低要求：

1. 固定 benchmark 场景  
   至少覆盖：
   - `depth=2 width=8`
   - `depth=3 width=10`
   - `depth=6 width=10`

2. 固定 profile 场景  
   对同一 midgame 局面做 profile，对比热点函数耗时变化。

3. 输出前后对比  
   至少记录：
   - 总耗时
   - 平均每手耗时
   - 总节点数
   - 热点前 10 函数

4. 提速门槛  
   单项优化若没有可测得的正收益，不应保留复杂实现。

## 实施顺序

建议按下面顺序推进。

### 阶段 1：优化前基线固化

- 固定 benchmark 工具
- 固定 profile 工具
- 固定对拍测试入口

当前这一阶段已经开始，后续应继续扩充。

### 阶段 2：Python 内部重写

优先模块：

1. `line.py`
2. `local.py`
3. `threat_board.py`
4. `board.py`

每改一个模块都要：

- 跑对应测试
- 跑热点 benchmark
- 记录前后差异

### 阶段 3：评估是否需要 native

进入条件：

- Python 重写后，`depth=6` 仍明显过慢
- 且 profile 仍显示热点集中在局部循环，而不是搜索控制层

### 阶段 4：native 第一批

优先模块：

1. `line`
2. `local`
3. `threat_board`

`vcf` 是否进入第一批，要看前面 3 个模块优化后剩余热点。

### 阶段 5：再次验证

- 全量测试
- 语义对拍
- benchmark
- selfplay smoke

只有这一步通过，才允许保留 native 结果。

## 与 GUI 的关系

GUI 不应先于这份加速计划执行。

原因：

- 当前主要问题仍是核心引擎速度
- GUI 不解决搜索时延问题
- GUI 应建立在“引擎语义稳定、速度可接受”之后

因此，GUI 的优先级低于：

1. 语义对齐
2. 性能测量
3. 加速实现

## 当前结论

当前项目可以进入加速阶段，但必须遵守以下工作顺序：

1. 先测量
2. 先做 Python 内部重写
3. 仍慢再上 native
4. 始终保留 Python fallback
5. 始终用测试和 benchmark 证明“更快且没变”

这是后续所有性能工作的硬约束。
