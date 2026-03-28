# AGENTS.md

## 仓库定位

当前工作区包含两个核心目录：

- `SlowRenju/`：外部 C/C++ 参考引擎
- `pyslow/`：Python 实现与后续 native 化主工程

本仓库的核心目标不是做一个演示程序，而是做一个有实际棋力、可持续演进的五子棋引擎，并在工程上保持：

- 语义可验证
- 模块边界清楚
- 能逐步迁移热点到 native，同时保留 Python fallback

## 代理工作的核心定位

在这个仓库里，agent 的工作重点是：

1. 以 `SlowRenju` 为 reference，对齐 `pyslow` 的关键行为语义
2. 在 `pyslow` 中实现和维护可测试、可回归、可演进的搜索/评估/战术模块
3. 在确认语义后，再推进 native 加速与执行层替换

agent 不应把自己当作“机械翻译器”。
应优先关注：

- 行为语义是否真的对齐
- 差异是否有直接证据
- 改动是否保留可回退和可测试的实现边界

## 文档分工

`AGENTS.md` 只负责说明仓库定位和工作规则。

具体阶段计划、当前优先级、native 分支状态、加速规则等，统一以 `docs/` 为准。

开始工作前，优先阅读：

1. [`docs/next-steps.md`](./docs/next-steps.md)
2. [`docs/acceleration-plan.md`](./docs/acceleration-plan.md)

规格类文档按任务需要阅读，例如：

- 搜索结构：[`docs/search-flow.md`](./docs/search-flow.md)
- 参数映射：[`docs/parameter-mapping.md`](./docs/parameter-mapping.md)
- 评估/棋形：[`docs/pattern-bucket-mapping.md`](./docs/pattern-bucket-mapping.md)
- 默认行为基线：[`docs/default-config-baselines.md`](./docs/default-config-baselines.md)
- VCF：[`docs/vcf-design.md`](./docs/vcf-design.md)

## 基本工程规则

- 新逻辑只在 `pyslow/` 中实现；`SlowRenju/` 用于 reference 阅读、最小 trace、必要的本地验证。
- 除非任务明确要求，不要修改 reference 的长期行为；若为了 trace 临时改动 reference，最终应回到干净状态。
- 所有搜索特性都必须保证落子、悔棋、哈希、缓存状态一致。
- 除非显式需要随机性，否则引擎行为应保持确定性。
- 每次修改尽量聚焦一个子系统，并补对应测试或最小复现。
- 不要只看“主流程看起来像”；reference 对齐时优先做最小局面、最小分叉点、分支级 trace。
- 只有在有直接源码证据或直接 trace 证据时，才能把“对齐 reference”的修复正式落地。

## reference 对齐规则

对齐 `SlowRenju` 时，优先级如下：

1. 先确认 reference 的真实行为
2. 再确认 `pyslow` 当前行为
3. 只在差异有证据时修改 `pyslow`

允许的证据类型：

- 直接源码证据
- 同一局面、同一搜索阶段下的直接 trace 证据

不允许把下面这些当成充分依据：

- “感觉这样更像”
- “这样棋力似乎更强”
- “改完样本结果更好”

如果某个 drift 只是实验性发现，应记录下来，但不要直接把它当成 reference 语义。

## native 工作规则

native 的目标是等价语义替换，不是单独发明另一套搜索器。

因此：

- native 必须以已确认的 Python 语义为基线
- Python reference/fallback 路径必须保留
- 不接受“更快但不完全一样”的近似替换进入主线
- 不接受“只搬循环、不搬数据路径”的薄封装 native 化

## 当前阶段约束

当前阶段的具体优先级和计划，以 `docs/next-steps.md` 为准。

`AGENTS.md` 只强调一条总规则：

- 先收口语义，再做性能和 native 硬化
