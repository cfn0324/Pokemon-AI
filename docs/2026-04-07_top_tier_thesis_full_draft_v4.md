# 面向长时序任务的纯 AI 决策游戏智能体
## 以 Pokemon Red 早期剧情自主推进为例

## 摘要

长时序游戏环境将部分可观测状态、稀疏里程碑、菜单式交互、跨场景导航与长期目标维护耦合在同一任务链上，因此适合检验生成式模型是否能够在较长时间尺度上承担连续决策责任。与短时控制型基准不同，`Pokemon Red` 的早期主线要求智能体在房间、城镇、道路、对话框与战斗菜单之间持续切换语义，同时避免局部循环、错误交互和剧情锁死。

本文研究一个运行于 `PyBoy` 模拟器上的大语言模型游戏智能体系统，并聚焦其中最严格的一种运行协议：普通回合不允许运行时确定性接管，不允许 AI 不可用时的动作重写，不允许隐藏的剧情脚本替代模型决策。系统仍保留一组可审计的运行时支持，包括 RAM 只读状态提取、地图记忆、上下文压缩、动作合法化、同回合同观测重试，以及两类显式标注并单独消融的窄域引导模块：故事引导与战斗引导。为避免把“纯 AI”写成口号，本文使用记录在报告中的 `ai_authored_ratio`、`fallback_ratio`、里程碑到达率和时间线一致性作为主指标，并将“无接管”与“100% AI authored”区分为不同强度的证据。

截至 2026 年 4 月 7 日，本文在统一起点 `checkpoint_196081` 上完成了新的结构化复验。当前最强的重复证据来自 3 次独立 `120` 回合纯 AI 批量实验：`3/3` 到达 `Route 1`，`2/3` 到达 `Viridian City`，`2/3` 进入 `Viridian Mart`，三次运行均满足 `fallback_ratio = 0`，且三次均达到 `ai_authored_ratio = 1.0`。以 Wilson 区间计，`Route 1` 到达率为 `100%`（95% CI: `43.9%-100.0%`），`Viridian City` 与 `Viridian Mart` 到达率均为 `66.7%`（95% CI: `20.8%-93.9%`）。作为补充压力测试，单次 `260` 回合长程运行虽然仍保持 `fallback_ratio = 0`，但仅推进至 `Route 1`，`ai_authored_ratio` 降至 `0.6154`，并出现 `94` 个 `ai_cooldown` 回合与 `6` 个 `ai_error` 回合，表明真实 provider 不稳定性会显著削弱长程运行质量。消融实验进一步表明，关闭故事引导后，单次 `120` 回合运行未能离开 Oak's Lab 周边循环；关闭战斗引导后，单次 `120` 回合运行仍可到达 `Viridian City` 并进入 `Viridian Mart`。这些结果共同支持如下更克制的结论：在固定起点、有限剧情窗口、显式边界与小样本条件下，`Pokemon Red` 早期主线中存在可审计的纯 AI 决策路径，并已观察到初步可复现性；但稳定性、泛化性与更长剧情覆盖仍有待进一步验证。

**关键词**：长时序任务；游戏智能体；大语言模型；Pokemon Red；纯 AI 决策；可复现实验

## Abstract

Long-horizon game environments are useful testbeds for agent research because they couple partial observability, sparse milestones, menu-heavy interaction, map transitions, and long-term goal maintenance within a single task chain. Compared with short-horizon control benchmarks, early-story progression in `Pokemon Red` requires an agent to switch repeatedly across room navigation, town traversal, dialogue advancement, battle menus, and event-triggered state changes without external intervention.

This paper studies a large-language-model game agent running on the `PyBoy` emulator and focuses on the strictest runtime protocol used in the project: ordinary turns do not allow deterministic runtime takeover, AI-unavailable action rewrites, or hidden route scripts that replace model decisions. The runtime still provides auditable support modules, including read-only RAM extraction, map memory, context compression, action normalization, same-observation retries, and two explicitly marked narrow guidance modules that are also ablated: story guidance and battle guidance. To avoid treating "pure AI" as a slogan, the paper uses logged `ai_authored_ratio`, `fallback_ratio`, milestone reach rates, and timeline-validity checks as primary evidence, and distinguishes between "no takeover" and "100% AI-authored" runs.

As of April 7, 2026, new structured reverification has been completed from the standardized start state `checkpoint_196081`. The strongest repeated evidence comes from three independent 120-turn pure-AI runs: all three reached `Route 1`, two reached `Viridian City`, and two entered `Viridian Mart`; all three had `fallback_ratio = 0`, and all three achieved `ai_authored_ratio = 1.0`. Using Wilson intervals, the observed reach rate is `100%` for `Route 1` (95% CI: `43.9%-100.0%`) and `66.7%` for both `Viridian City` and `Viridian Mart` (95% CI: `20.8%-93.9%`). A supplementary 260-turn stress run still maintained `fallback_ratio = 0`, but progressed only to `Route 1`, with `ai_authored_ratio = 0.6154`, `94` cooldown turns, and `6` AI-error turns, indicating that real provider instability materially degrades long-horizon behavior. Ablation results show that disabling story guidance prevents even Route 1 progress within 120 turns, while disabling battle guidance still permits progression to `Viridian City` and `Viridian Mart` in a 120-turn run. These results support a narrower claim: under a fixed start state, a limited early-story window, explicit runtime boundaries, and a small exploratory sample, there exists auditable evidence for pure-AI decision paths in early `Pokemon Red`, together with preliminary reproducibility rather than stable long-range closure.

---

## 第 1 章 绪论

### 1.1 研究背景

生成式模型近年的快速发展，使“单步问答是否正确”逐渐让位于“跨越更长时间尺度的连续行为是否一致”这一问题。长时序任务中的困难并不只是动作数量增加，更在于错误会跨回合传播：一次误判可能在几十步之后表现为迷路、剧情锁死、资源浪费或错误上下文累积。与纯文本环境相比，游戏环境更容易暴露此类问题，因为它们同时包含空间导航、UI 状态切换、图像观察、脚本触发和资源约束。

`Pokemon Red` 之所以适合作为研究对象，不是因为它“足够经典”，而是因为它将多种困难集成在一条紧凑的早期主线中。玩家需要离开 Oak's Lab、通过 Pallet Town 北口、穿越 Route 1、到达 Viridian City，并在 Viridian Mart 中完成关键交互。这个过程中既有门口对齐、路径转折、野战菜单、文本推进，也有局部死循环和伪开放区域。对于希望在长时序互动世界中承担连续决策责任的模型而言，这是一个足够具体又足够有挑战性的窗口。

### 1.2 研究问题

本文不把研究问题表述为“纯 AI 决策是否已经被证明”，而是把它拆解为两个可审计的问题：

`RQ1`：在固定起点、有限预算和显式禁止运行时接管的协议下，系统能否在 `Pokemon Red` 早期主线中完成非平凡推进，并留下可核验的结构化证据？

`RQ2`：哪些运行时支持能提升这种推进的稳定性，而又不直接替代模型承担普通回合控制权？

这两个问题要求论文同时回答“能走多远”和“是谁在做决定”。如果没有控制边界，任何剧情推进都可能被怀疑来自隐藏脚本；如果没有结构化证据，任何“纯 AI”叙述都可能只是演示性口号。

### 1.3 研究目标与贡献

围绕上述问题，本文的贡献收缩为以下三点。

`C1`：提出一个面向长时序 JRPG 的可审计运行时框架，明确区分只读观测、上下文组织、动作执行稳定化与被禁止的确定性接管。

`C2`：提出一套与项目日志直接对齐的评估协议，使用 `fallback_ratio`、`ai_authored_ratio`、里程碑到达率和时间线一致性描述“纯 AI 决策”的不同强度，而不是依赖单段叙事型展示。

`C3`：在 `checkpoint_196081` 的统一起点上，给出新的结构化存在性证据与初步重复证据，并通过故事引导与战斗引导消融，说明哪些支持模块对当前早期剧情窗口更关键。

### 1.4 论文结构

第 2 章讨论本文与生成式智能体、游戏智能体和可审计运行时研究的关系。第 3 章定义任务范围、评估口径与控制边界。第 4 章给出系统设计与复现实验配置。第 5 章说明状态构造、上下文组织、主决策模块以及两类引导模块。第 6 章说明实验协议、统计计划与证据组织原则。第 7 章报告主实验、历史基线对照和消融结果。第 8 章讨论本文能支持什么、不能支持什么，以及后续应如何扩展。第 9 章总结全文。

---

## 第 2 章 相关工作与方法定位

### 2.1 长时序生成式智能体

`Generative Agents` 强调长期记忆、摘要压缩与基于相关性的检索机制 [1]。其核心启发不在于社会模拟场景本身，而在于：若要维持跨时间的一致行为，系统不能只看当前瞬时输入，而必须持续维护与当前目标相关的历史上下文。`ReAct` 将推理链与行动链耦合，说明语言模型不仅可以“想”，还可以在外部环境中“做” [3]。`Reflexion` 和 `Voyager` 等工作进一步表明，语言模型可以结合自我回顾、技能积累和环境反馈逐步提升任务完成能力 [4][5]。

本文与这些工作的关系是继承而非复用。本文不研究多智能体社会模拟，不构建开放式技能库，也不试图在本文中比较多种 agentic prompting 范式。本文更聚焦于一个更狭窄但更可审计的问题：当运行时支持被压缩到只读状态、上下文组织和最小执行稳定化时，模型本身是否能在长时序游戏中承担普通回合决策责任。

### 2.2 游戏智能体与 Pokemon Red 研究环境

`Pokemon Red via Reinforcement Learning` 说明了该环境在地图探索、脚本触发、战斗系统、奖励稀疏性和长链任务组织上的复杂性 [2]。这类工作更多从强化学习训练角度说明环境难度，而本文则借用其对环境复杂性的论证，把 `Pokemon Red` 视为一个足以检验长时序生成式决策的互动世界。

与 Atari 等短程控制基准相比，`Pokemon Red` 更强调异构状态切换。系统必须在自由移动、对话脚本、战斗文本、战斗菜单和跨地图传送之间来回切换，而不是在单一低层动作空间中持续优化局部反应。这正是本文选择该环境的原因。

### 2.3 可审计运行时支持与控制边界

大量工程系统都会在模型外围增加缓存、规则、守卫和 fallback，但这些模块一旦越过边界，就会让“模型在做决定”与“脚本在替模型擦屁股”之间变得难以区分。本文的方法定位因此不是“完全裸模型”，而是“显式、可记录、可消融的运行时支持”。这与常见的“隐藏安全层 + 对外宣称 AI 自主”不同。

本文在方法定位上强调两点。第一，运行时支持不等于外部接管。RAM 提取、地图记忆、上下文摘要、合法动作约束和单按钮执行都属于支撑层，而非剧情脚本。第二，任何可能替代模型承担普通回合控制权的确定性逻辑，必须在主实验协议中关闭，并在日志中以 `fallback_ratio` 等字段显式记录。

### 2.4 本文的方法定位

因此，本文既不是强化学习训练论文，也不是脚本自动化论文，而是一篇运行时系统论文。其研究对象不是“如何得到最高成功率”，而是“在明确禁止接管的条件下，当前生成式模型能否形成可审计的早期剧情推进证据”。这一定义决定了本文必须比普通项目报告更克制：我们报告的是存在性和初步可复现性，而不是稳定闭环已经建立。

---

## 第 3 章 任务定义与证据边界

### 3.1 任务范围

本文覆盖的主任务窗口是 `Pokemon Red` 的早期剧情，从统一起点 `checkpoint_196081` 出发，预算为 `120` 或 `260` 回合，观察以下里程碑是否到达：

1. `reached_route1`
2. `reached_viridian_city`
3. `entered_viridian_mart`
4. `obtained_oaks_parcel`
5. `got_pokedex`
6. `reached_route2`
7. `reached_viridian_forest`

其中，`Route 1`、`Viridian City` 与 `Viridian Mart` 构成本论文当前最核心的结构化窗口；`Oak's Parcel` 及之后的节点只作为更远剧情的补充指标，不作为本轮主结论的必要前提。

### 3.2 形式化描述

可将该任务视为部分可观测马尔可夫决策过程 `M = (S, A, O, T)`。系统在每个回合获得观测 `o_t`，其内容包括截图、RAM 提取的高层语义状态、地图记忆摘要、导航摘要与上下文笔记；模型输出离散动作 `a_t in {up, down, left, right, a, b, start, select, wait}`。本文不直接估计环境回报，而使用到达事件、控制权归属和时间线有效性作为主评价对象。

### 3.3 评价口径

本文使用与运行报告直接对齐的三个主量。

1. `R_takeover = fallback_turns / total_turns`
2. `R_ai = ai_authored_turns / total_turns`
3. `Valid = timeline_turns_monotonic and final_state_matches_end_turn and timeline_last_turn_matches_end_turn`

据此定义两级证据：

1. `Pure-No-Takeover`：`Valid = true` 且 `R_takeover = 0`
2. `Strict-AI-Authored`：`Valid = true` 且 `R_takeover = 0` 且 `R_ai = 1.0`

前者说明没有确定性接管；后者进一步说明全部回合均由 AI 直接产出动作，而不是退化为 `ai_cooldown` 或 `ai_error` 等非 authored 回合。

### 3.4 允许支持与禁止接管

表 3-1 给出本文协议中的关键边界。该表并非写作性声明，而是与代码和实验开关一致的协议约束。

| 类别 | 是否允许 | 说明 |
| --- | --- | --- |
| RAM 只读状态提取 | 允许 | 作为观测层，不直接生成动作 |
| 地图记忆与导航摘要 | 允许 | 对历史走位做结构化压缩，服务于模型理解 |
| 上下文摘要、任务笔记 | 允许 | 降低长上下文漂移 |
| 合法动作归一化 | 允许 | 把模型输出约束到合法按钮集合 |
| ActionExecutor 单按钮执行 | 允许 | 在纯 AI 协议下避免把一个方向扩展成多次自动重试 |
| 同回合同观测重试 | 允许 | 对同一观测重发模型请求，不替模型规划新动作 |
| 故事引导 | 允许但需显式标注 | 属于窄域文本 cue，并在正文给出消融 |
| 战斗引导 | 允许但需显式标注 | 属于窄域战斗 cue，并在正文给出消融 |
| 确定性 stage controller | 禁止 | 主实验中关闭 |
| AI 不可用 fallback 重写 | 禁止 | `disable_runtime_fallbacks = true` |
| WAIT rewrite / guided navigation escape | 禁止 | 主实验中不允许替代普通回合控制 |
| Checkpoint 恢复 | 允许但不计入运行 | 仅用于统一 run 起点 |

### 3.5 关于“纯 AI”表述的边界

本文刻意不把“纯 AI”定义为“系统外没有任何程序逻辑”。更准确的说法是：在主实验协议中，不允许确定性逻辑替代模型完成普通回合决策。该定义允许存在可审计的观测组织与执行稳定化，但禁止隐藏策略层。即便如此，本文仍承认两点重要边界。第一，故事引导包含人工编写的早期剧情知识，因此它必须被单独分析。第二，RAM 观测属于特权观察，不等同于纯视觉主体。

---

## 第 4 章 系统总体设计与复现实验配置

### 4.1 系统概览

系统由模拟器层、状态构造层、上下文组织层、主决策层、动作执行层与评估层组成。模拟器层负责运行 `PokemonRed.gb`。状态构造层从 RAM 中读取位置、战斗、UI、事件与队伍信息，并与地图记忆结合，形成对当前回合更稳定的任务化文本状态。上下文组织层维护近期回合、历史摘要、任务笔记以及显式 guidance note。主决策层调用大语言模型输出动作。动作执行层将动作映射为合法按钮输入。评估层在每次 smoke run 后导出结构化 JSON 报告，并聚合为批量统计。

### 4.2 当前主实验的关键配置

表 4-1 汇总 2026 年 4 月 7 日本轮主实验口径中的关键信息。需要强调的是，正文以报告中的 `effective_settings` 和 `config_snapshot` 为准，而不是以仓库默认 `config.yaml` 文本为准。

| 项目 | 当前值 |
| --- | --- |
| 标准起点 | `checkpoint_196081` |
| 模型 | `gpt-5.4` |
| API Base URL | `https://api.ququ233.com/v1` |
| 主模型温度 | `0.0` |
| `pure_llm_mode` | `true` |
| `disable_runtime_fallbacks` | `true` |
| `llm_primary_mode` | `false` |
| `ai_full_control_mode` | `false` |
| 请求超时 | `25s` |
| 请求重试 | `1` 次 |
| 重试退避 | `0.5s` |
| 同回合重试上限 | `30` 次 |
| 同回合时间预算 | `60s` |
| 决策最大输出 | `256` tokens |
| 动作计划上限 | `3` |
| 故事引导 | 可开关，主实验为 `true` |
| 战斗引导 | 可开关，主实验为 `true` |
| 模拟器 | `PyBoy 2.6.1` |
| Python | `3.13.5` |
| 操作系统 | `Windows 11 10.0.26200`, `AMD64` |
| ROM | `PokemonRed.gb` |
| ROM SHA256 | `5CA7BA01642A3B27B0CC0B5349B52792795B62D3ED977E98A09390659AF96B7B` |

### 4.3 复现实验说明

本轮主实验采用 headless 模式运行，并在每份单次报告中记录 `environment`、`effective_settings`、`config_snapshot` 与 `report_validation`。这使得读者可以追踪：模型是谁、开关是什么、是否禁用了 runtime fallback、时间线是否完整、结尾状态是否与最后一回合一致。与 v3 相比，本文把这些信息前移到正文，而不是留在附录或口头说明中。

需要说明的一点是，当前自动导出的环境信息仍未完整覆盖 CPU/GPU 型号等硬件字段。这不是主结论的决定性前提，但从严格复现角度看仍是一个待补齐的工程缺口，本文在讨论章节中会明确说明。

---

## 第 5 章 核心方法与关键模块

### 5.1 GameState：从原始观测到任务化状态

`GameState` 将 RAM、UI 状态、截图元信息、队伍信息、事件位和地图记忆组合为任务化文本状态。这一层的作用不是决定下一步走哪，而是把模型本来难以在长上下文中稳定维护的局部事实显式化，例如当前位置、邻接方向是否被证实阻塞、当前是否仍处于战斗文本、当前 tile 的访问次数、最近 frontier 候选等。

这种状态组织与“纯视觉 + 原始字幕截图”的方案相比更可控，但它也引入了本文必须承认的边界：RAM 语义并不等价于原生玩家视觉。因此，本文从不把当前系统描述为纯视觉 agent，而是明确描述为“截图 + RAM 语义 + 上下文组织”的语言模型决策系统。

### 5.2 地图记忆与导航摘要

地图记忆模块持续记录已探索 tile、已知出口、确认阻塞方向、warps 与 frontier 候选。其输出仍然是摘要，而不是确定性代走脚本。对于模型而言，最重要的价值在于减少重复探索和局部循环，而不是直接替模型选择最终动作。主实验协议之所以仍可被称为“无接管”，就在于这些导航信息在纯 AI 模式下只作为状态输入，而不会自动升级为接管型 planner。

### 5.3 上下文压缩与任务笔记

长时序运行中，模型最容易丢失的不是单帧截图，而是“我现在为什么在这里”。因此系统显式保留近期回合、历史摘要和任务笔记。这一设计吸收了长期记忆型 agent 的通用思想 [1][4]，但本文避免把它宣传成更强的“反思”或“自我修复”系统。它的职责更接近上下文组织，而非高阶自学习。

### 5.4 主决策模块

主决策模块的目标是在约束输出格式的前提下，让模型直接生成下一个按键动作。运行日志中的 `decision_source`、`decision_path` 与 `ai_control_metrics` 使我们能够区分三种情况：真正由模型产出的 authored 决策、因 provider 不稳定而退化的 `ai_error`/`ai_cooldown`、以及被禁用的 fallback 路径。本文的主结论只建立在前两类被清楚区分、第三类为零的前提上。

### 5.5 ActionExecutor 与最小执行稳定化

执行层负责把动作映射为合法按钮。一个重要实现细节是：在 `pure_llm_mode` 下，非精确模式的方向动作不会被扩展为多次自动重试，而是尽量接近“一次模型决策对应一次按钮输入”。这减少了执行层暗中放大模型意图的风险。换言之，ActionExecutor 负责“把这个按钮按下去”，而不是“替模型把这一小段路走完”。

### 5.6 故事引导与战斗引导

当前系统包含两个可显式开关的引导模块。

故事引导根据早期地图位置和事件位生成窄域文本 cue。例如在 Oak's Lab 中，它会告诉模型出口位于 `y=11` 且门列为 `x=4` 或 `x=5`；在 Pallet Town 和 Route 1 中，它会给出早期主线的已验证走向。由此可见，故事引导包含人工编写的早期剧情知识，因此它不是中性的“记忆摘要”，而更接近窄域任务提示。本文把它视为允许但需要显式披露的运行时支持。

战斗引导则更多来自 RAM 战斗相位、菜单状态和可用招式信息。它通常只给出类似“当前是战斗文本，应继续按 A”或“菜单出现时优先 FIGHT，再选第一个可用伤害招式”之类的局部 cue。与故事引导相比，它对全局路径的决定作用较小，但会影响战斗文本推进和菜单语义理解。

### 5.7 同回合同观测重试

主实验仍允许同回合同观测重试：当模型调用遭遇短暂传输问题时，系统可以在同一观测上重新请求模型，直到达到次数或时间预算上限。该机制的设计目标是避免把一次瞬时 provider 故障直接放大为整段剧情失败。但它并不等同于脚本接管，因为它不会切换到确定性路线脚本，只是在同一状态上再次请求模型。如果重试耗尽，系统会留下 `ai_error` 回合而非伪装成 authored 决策。

---

## 第 6 章 实验设计与证据组织

### 6.1 研究问题与实验分层

实验围绕三个层次展开。

1. 主重复实验：检验在统一纯 AI 协议下，早期主线是否存在非零重复到达率。
2. 长程压力测试：检验在更长预算下，provider 不稳定性会如何影响无接管运行。
3. 消融实验：检验故事引导和战斗引导对当前窗口的相对贡献。

除上述三类新实验外，本文还保留 2026 年 4 月 5 日的历史基线摘要作为协议对照，但明确不将其纳入 2026 年 4 月 7 日主结论的核心统计。

### 6.2 当前主实验协议

表 6-1 总结了本轮论文正文使用的实验。

| 实验 | 日期 | 起点 | 每次预算 | 次数 `n` | 是否纳入主结论 |
| --- | --- | --- | --- | --- | --- |
| 纯 AI 重复实验，完整引导 | 2026-04-07 | `checkpoint_196081` | `120` | `3` | 是 |
| 纯 AI 长程压力测试，完整引导 | 2026-04-07 | `checkpoint_196081` | `260` | `1` | 仅作补充 |
| 纯 AI 消融：关闭故事引导 | 2026-04-07 | `checkpoint_196081` | `120` | `1` | 是，探索性 |
| 纯 AI 消融：关闭战斗引导 | 2026-04-07 | `checkpoint_196081` | `120` | `1` | 是，探索性 |
| 历史基线：`llm_primary + ai_full_control` | 2026-04-05 | `checkpoint_195913` | `120` | `3` | 否，辅助对照 |
| 历史基线：retry-fix 后同协议 | 2026-04-05 | `checkpoint_195913` | `120` | `3` | 否，辅助对照 |

### 6.3 统计计划

对于重复实验，本文报告二项比例与 Wilson 95% 区间；对于时延和比例类连续值，报告均值、中位数、标准差与极值；对于单次长程压力测试和单次消融，只作探索性描述，不作确认性统计推断。这样做的原因很简单：`n=3` 已足以表达“非零重复现象”和粗略不确定性，但远不足以支撑强统计主张；`n=1` 的消融只能用来提示机制，而不能用来下稳健结论。

### 6.4 视觉证据与结构化证据的关系

本文保留此前的演示视频与主图素材，但将其角色降级为补充说明。正文主结论只建立在 2026 年 4 月 7 日新的结构化报告之上。较早的“最佳展示 run”即便 visually 到达了 `Oak's Parcel`，也不再被当作当前正文的核心统计证据，而只作为原始画面补充。

---

## 第 7 章 实验结果与分析

### 7.1 主结果总表

表 7-1 给出本轮最重要的结构化结果。为避免 narrative 替代统计，正文优先报告里程碑、控制权归属和时延。

| 条件 | `n` | 预算 | `Route 1` | `Viridian City` | `Viridian Mart` | `Oak's Parcel` | `ai_authored_ratio` | `fallback_ratio` | 平均时延 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 完整引导，纯 AI 批量复验 | `3` | `120` | `3/3` (`100.0%`, 95% CI `43.9%-100.0%`) | `2/3` (`66.7%`, 95% CI `20.8%-93.9%`) | `2/3` (`66.7%`, 95% CI `20.8%-93.9%`) | `0/3` (`0.0%`, 95% CI `0.0%-56.2%`) | 均值 `1.0000` | 均值 `0.0000` | `6.04s` |
| 完整引导，纯 AI 长程压力测试 | `1` | `260` | 是 | 否 | 否 | 否 | `0.6154` | `0.0000` | `7.49s` |
| 关闭故事引导 | `1` | `120` | 否 | 否 | 否 | 否 | `0.9167` | `0.0000` | `6.95s` |
| 关闭战斗引导 | `1` | `120` | 是 | 是 | 是 | 否 | `1.0000` | `0.0000` | `5.97s` |

从表 7-1 可见，当前最强证据不是单次长程 run，而是 3 次独立 `120` 回合复验。它们共同满足三个条件：时间线有效、`fallback_ratio = 0`、早期里程碑出现非零重复到达率。尤其重要的是，这三次运行不仅“无接管”，而且都达到 `ai_authored_ratio = 1.0`，即全部回合都由模型直接产出动作。

### 7.2 对长程压力测试的诚实解释

单次 `260` 回合长程运行并没有给出更强结论，反而提醒我们必须收缩论文主张。该 run 虽然仍满足 `fallback_ratio = 0`，但只推进到 `Route 1`，同时出现 `94` 个 `ai_cooldown` 回合和 `6` 个 `ai_error` 回合，`ai_authored_ratio` 降至 `0.6154`。这意味着系统并未被确定性 fallback 接管，但真实 provider 的可用性和响应时间已经显著干扰了有效推进。

因此，本文不再把“更长 run”自动解读为“更强证据”。在当前论文口径下，这个 `260` 回合 run 的价值主要有两点：第一，它说明 `disable_runtime_fallbacks` 之后系统不会在 provider 抖动时偷偷退化为脚本接管；第二，它说明长程稳定性仍然是未解决问题，而非已完成结果。

### 7.3 历史基线对照

为避免只有“当前最好条件”的结果，表 7-2 给出历史协议对照。这里的对照并非同日同 checkpoint 的严格 apples-to-apples 比较，因此不纳入主结论，只用于说明控制协议差异的重要性。

| 条件 | 日期 | 起点 | `n` | 预算 | 主要协议 | 平均 `ai_authored_ratio` | 结果说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 历史基线 | 2026-04-05 | `checkpoint_195913` | `3` | `120` | `llm_primary = true`, `ai_full_control = true` | `0.0194` | AI 贡献几乎被 provider/transport 不稳定吞没 |
| 历史基线，retry-fix 后 | 2026-04-05 | `checkpoint_195913` | `3` | `120` | 同上 | `0.3000` | AI 占比回升，但仍未到达 `Route 1` |
| 当前纯 AI 复验 | 2026-04-07 | `checkpoint_196081` | `3` | `120` | `pure_llm = true`, `disable_runtime_fallbacks = true` | `1.0000` | `3/3 Route 1`, `2/3 Viridian City`, `2/3 Viridian Mart` |

表 7-2 的价值不在于证明“新协议绝对更优”，而在于指出：如果不明确控制接管边界，`ai_authored_ratio` 与剧情推进都很容易被运行时替代路径或 provider 问题掩盖。当前论文因此把历史基线保留为辅助对照，而把 2026 年 4 月 7 日的纯 AI 批量复验作为主要统计口径。

### 7.4 消融结果

故事引导与战斗引导是本轮重写中必须正面拆解的两个模块。表 7-3 给出当前消融结果。

| 条件 | `Route 1` | `Viridian City` | `Viridian Mart` | `ai_authored_ratio` | 额外现象 | 解释 |
| --- | --- | --- | --- | --- | --- | --- |
| 完整引导 | `3/3` | `2/3` | `2/3` | 均值 `1.0000` | 无 fallback | 当前最强重复证据 |
| 关闭故事引导 | 否 | 否 | 否 | `0.9167` | `10` 个 `ai_cooldown`，最终停留在 Oak's Lab 地图并出现 `2x2` 微循环警告 | 说明早期剧情定向 cue 对离开实验室和进入主线通道具有关键作用 |
| 关闭战斗引导 | 是 | 是 | 是 | `1.0000` | 单次 run 仍进入 `Viridian Mart` | 说明在当前窗口内，战斗引导不是主推进瓶颈，但对更长剧情仍不能据此下结论 |

这一结果对论文叙事有直接影响。首先，故事引导不能再被写成“普通上下文整理的一部分”，因为它显然影响了是否能离开实验室并对齐早期主线。其次，战斗引导在当前窗口中的作用较弱，这意味着“早期剧情是否能推进”主要受空间与脚本定位支配，而不是受普通野战菜单支配。换言之，当前系统的主要难点仍然在早期路径定位和剧情状态识别，而不是战斗本身。

### 7.5 结果强度的层级化解释

基于当前结构化结果，本文将结论强度分为三层。

第一层是“存在性证据”：完整引导下的重复实验已经表明，在严格禁止 fallback 接管的协议里，确实存在能够从统一起点推进到 `Viridian City` 和 `Viridian Mart` 的纯 AI 路径。

第二层是“初步可复现性证据”：`2/3` 的 `Viridian City` 与 `Viridian Mart` 到达率说明该现象不是孤立演示；但样本仍小，Wilson 区间仍宽，因此只能称为 preliminary reproducibility。

第三层是“长程稳定性证据”：当前还不成立。`260` 回合 run 的退化表现恰恰说明该层结论尚不能下。

### 7.6 成本、时延与运行可靠性

当前 3 次完整引导重复实验的平均单次请求时延为 `6.0363s`，中位数为 `6.1710s`，标准差约 `0.2950s`。相比之下，单次 `260` 回合压力测试的平均请求时延升至 `7.486s`，最大值达到 `42.084s`。这说明长程运行中的系统瓶颈并非仅来自游戏状态复杂化，也明显受外部模型服务稳定性影响。

这也是本文坚持区分 `fallback_ratio` 与 `ai_authored_ratio` 的原因。如果只报告“没有接管”，那么长程 run 会显得比实际更成功；如果只报告“到没到目的地”，那么网络抖动造成的非 authored 回合又会被掩盖。将两者同时记录，才能看见真实的系统状态。

### 7.7 小结

第 7 章的核心结论是：截至 2026 年 4 月 7 日，当前系统已经在统一起点、严格无接管协议和小样本条件下给出了可信的早期剧情存在性证据与初步重复证据；但它尚未证明长程闭环已经稳定，更未证明该能力可直接外推到更远剧情窗口。

---

## 第 8 章 讨论

### 8.1 本文最稳固的结论是什么

本文目前最稳固的结论只有两点。其一，在 `checkpoint_196081` 这一固定起点与 `120` 回合预算下，存在完全不依赖 deterministic fallback 的纯 AI 路径，可推进至 `Viridian City` 与 `Viridian Mart`。其二，这一路径并非只在单次演示中出现，而是在 3 次独立 run 中观察到了非零重复率。

### 8.2 本文不能宣称什么

本文不能宣称以下结论：

1. 不能宣称“长时序剧情闭环已经建立”。
2. 不能宣称“系统已经稳定复现 Oak's Parcel 或更远剧情”。
3. 不能宣称“当前能力不依赖人工任务知识”。
4. 不能宣称“该结果可直接外推到其他游戏或其他 provider”。

这四点中，第三点尤其重要。故事引导显然携带了早期地图与剧情知识，并且消融结果表明它对当前窗口有效。因此，任何把本文系统描述为“没有任务先验的纯模型自主体”的说法都是不准确的。

### 8.3 当前证据的主要局限

本文至少有五个需要正面承认的局限。

1. 任务窗口只覆盖早期剧情，主结论集中在 `Route 1` 到 `Viridian Mart`。
2. 重复实验样本量只有 `n=3`，统计区间依然很宽。
3. RAM 状态读取属于特权观测，不等价于纯视觉玩家主体。
4. 故事引导包含人工编写的早期任务知识，且其作用已被消融证实。
5. 长程运行对 provider 稳定性高度敏感，网络或服务抖动会显著拉低 `ai_authored_ratio`。

其中，第 4 点意味着本文不应该把“纯 AI”理解为“没有人工先验”，而应理解为“在明确给定的状态构造与窄域引导下，不由确定性脚本接管普通回合控制”。这是更窄、但也更诚实的定义。

### 8.4 外部有效性与下一阶段实验

若要把本文从“初步可复现”推向更高质量的实验论文，下一阶段至少需要补三类实验。

1. 同日同 checkpoint 的 fresh baseline，对比 `pure_llm` 与 `llm_primary + ai_full_control`。
2. 更大的重复样本，例如 `n >= 10` 的 `120` 回合批量复验。
3. 更远剧情窗口的复制，例如 `Oak's Parcel`、`Pokedex`、`Route 2` 与 `Viridian Forest`。

值得注意的是，这些工作不是为了“修饰已有成功”，而是为了检验当前结论能否保持。尤其是第一项 fresh baseline，目前正文只能使用 2026 年 4 月 5 日的历史基线作为辅助对照，这已经足以说明协议差异，但还不够构成最强对照证据。

### 8.5 对论文写作口径的影响

当前结果要求论文口径发生三个根本变化。

1. 从“已经建立纯 AI 剧情闭环”改为“观察到可审计的纯 AI 路径及其初步可复现性”。
2. 从“展示最佳 run”改为“以重复实验为主，单次长程 run 为补充”。
3. 从“把支持模块默认为中性工程细节”改为“正面拆解 story guidance 和 battle guidance 的性质与影响”。

这三个变化构成了 v4 相比 v3 的核心修正方向。

---

## 第 9 章 结论与展望

本文研究了一个运行于 `PyBoy` 上的 `Pokemon Red` 大语言模型智能体，并在更严格的口径下重新组织了其证据。通过显式区分可允许的运行时支持与被禁止的确定性接管，本文把“纯 AI 决策”从一个容易被误解的营销性标签，收缩为一组可由日志字段检验的运行协议。

截至 2026 年 4 月 7 日，本文最可信的主结果来自统一起点 `checkpoint_196081` 下的 3 次 `120` 回合纯 AI 批量复验：`3/3` 到达 `Route 1`，`2/3` 到达 `Viridian City`，`2/3` 进入 `Viridian Mart`，且三次运行均满足 `fallback_ratio = 0` 与 `ai_authored_ratio = 1.0`。这组结果支持如下有限结论：在固定起点、有限早期剧情窗口和显式边界下，存在可审计的纯 AI 决策路径，并已观察到初步可复现性。与此同时，单次 `260` 回合压力测试未能推进至 `Viridian City`，并暴露出 provider 不稳定性对长程运行的明显干扰；故事引导消融则表明，当前系统对窄域早期剧情知识仍有实质依赖。

因此，本文的价值不在于宣称“问题已经解决”，而在于给出一个更可信的研究起点：我们现在知道，在多大边界内、借助哪些明确支持、以什么样的统计口径，可以说已经观察到了纯 AI 决策路径；同时也知道，还不能把这一结果扩大解释为稳定长程闭环或普遍泛化能力。下一阶段工作的重点应是扩大重复样本、补 fresh baseline、延长剧情窗口，并继续压缩人工先验在故事引导中的作用。

---

## 参考文献

[1] PARK J S, O'BRIEN J, CAI C J, et al. Generative agents: Interactive simulacra of human behavior[C]//Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology. 2023.

[2] PLEINES M, ADDIS D, RUBINSTEIN D, et al. Pokemon Red via reinforcement learning[EB/OL]. arXiv:2502.19920, 2025.

[3] YAO S, ZHAO J, YU D, et al. ReAct: Synergizing reasoning and acting in language models[EB/OL]. arXiv:2210.03629, 2023.

[4] SHINN N, CASSANO F, LABASH B, et al. Reflexion: Language agents with verbal reinforcement[EB/OL]. arXiv:2303.11366, 2023.

[5] WANG G, XIONG W, WU Y, et al. Voyager: An open-ended embodied agent with large language models[EB/OL]. arXiv:2305.16291, 2023.

[6] COBBE K, KLISSAROV M, HESSEL M, et al. Leveraging procedural generation to benchmark reinforcement learning[C]//International Conference on Machine Learning. 2020.

[7] Pokemon-AI Project. Structured main evaluation under the standardized early-story pure-AI protocol[R]. 2026-04-07.

[8] Pokemon-AI Project. Three-run repeated evaluation under the standardized pure-AI protocol[R]. 2026-04-07.

[9] Pokemon-AI Project. Ablation report: no-story-guidance pure-AI run from checkpoint_196081[R]. 2026-04-07.

[10] Pokemon-AI Project. Ablation report: no-battle-guidance pure-AI run from checkpoint_196081[R]. 2026-04-07.

[11] Pokemon-AI Project. Historical baseline summary under `llm_primary + ai_full_control`[R]. 2026-04-05.

[12] Pokemon-AI Project. Historical retry-fix baseline summary under `llm_primary + ai_full_control`[R]. 2026-04-05.

[13] Pokemon-AI Project. Local test and API reverification logs[R]. 2026-04-07.

---

## 附录 A 本轮关键实验产物

| 产物 | 文件 |
| --- | --- |
| 单次 `260` 回合长程压力测试 | `docs/report_assets/2026-04-07_pure_ai_demo/reports/pure_ai_latest_260_v8.json` |
| `3 x 120` 完整引导重复实验汇总 | `tmp/real_ai_batches/2026-04-07_pure_ai_batch_checkpoint_196081_120t_fullguidance_v1/2026-04-07_pure_ai_batch_checkpoint_196081_120t_fullguidance_v1_summary.json` |
| 单次 `120` 回合关闭故事引导消融 | `docs/report_assets/2026-04-07_pure_ai_demo/reports/pure_ai_ablation_no_story_120_v1.json` |
| 单次 `120` 回合关闭战斗引导消融 | `docs/report_assets/2026-04-07_pure_ai_demo/reports/pure_ai_ablation_no_battle_120_v1.json` |
| 历史基线汇总 | `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline/2026-04-05_phase2_real_ai_baseline_summary.json` |
| 历史 retry-fix 基线汇总 | `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline_retryfix/2026-04-05_phase2_real_ai_baseline_retryfix_summary.json` |

## 附录 B 本版相对 v3 的主要修订点

1. 收缩了摘要、引言、讨论与结论中的过强主张，不再把当前结果描述为“已建立稳定长程闭环”。
2. 把 `effective_settings`、`environment`、`config_snapshot`、ROM 哈希与软件版本前移到正文。
3. 以 `3 x 120` 纯 AI 重复实验替代单次最佳 run 作为正文主证据。
4. 将 `260` 回合长程运行改写为压力测试，而非主成功案例。
5. 新增显式边界表、历史基线表与消融表。
6. 正面承认故事引导携带人工任务知识，并用单次消融结果支持这一点。
7. 明确区分 `fallback_ratio = 0` 与 `ai_authored_ratio = 1.0` 两种不同强度的“纯 AI”证据。

