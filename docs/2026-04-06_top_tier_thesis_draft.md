# 面向长时序任务的混合式大模型游戏智能体

## 以 Pokemon Red 早期剧情自主推进为例的系统设计、证据审计与实验分析

> 写作说明  
> 本稿按“顶刊风格、结论克制”的原则撰写。凡当前仓库尚未补齐的图表、实验或基线，一律用“[占位]”标注，明确说明缺失原因与补充要求；不以猜测、理想结果或未复现实验替代真实证据。

## 摘要

长时序视频游戏环境为通用智能体研究提供了高探索难度、多阶段任务耦合、稀疏关键里程碑与复杂人机交互界面等综合挑战。相比 Atari 一类短回合街机环境，`Pokemon Red` 的任务跨度更长，局部剧情锁、战斗菜单、地图导航、对话触发和资源管理紧密耦合，因此更适合检验“感知-记忆-规划-执行-恢复”闭环是否成立。本文围绕一个面向 `Pokemon Red` 的混合式大模型游戏智能体系统展开研究。该系统基于 `PyBoy` 模拟器接入，通过 RAM 读取构造主状态，通过可选像素视觉提供补充线索，并结合地图记忆、上下文摘要、目标管理、动作执行器、检查点恢复、可视化仪表盘以及标准化 smoke/batch 评估脚本，形成一个可长时运行、可复验、可解释的实验框架。

与纯强化学习代理不同，本文系统采用“受约束的生成式决策”路线：普通回合由大模型主智能体生成动作，规则控制器仅在启动、稳定 UI 恢复、剧情保护与安全边界上提供有限接管，从而兼顾 AI 主导性与运行时安全性。参考 Generative Agents 的 memory-reflection-planning 思路，本文将长期任务上下文组织为近期回合、摘要历史、任务笔记与目标层级的组合；同时参考 `Pokémon Red via Reinforcement Learning` 对环境复杂性的形式化方式，将本任务抽象为部分可观测长时序决策问题，并围绕 AI ownership、fallback 比例、剧情里程碑、时间线有效性和长程韧性构建评价协议。

截至 `2026-04-06` 的最新本地复验表明：当前仓库在正常权限环境下通过 `299 passed, 1 warning` 的全量测试，`test_setup.py` 为 `7/7` 通过，`test_custom_api.py` 可直连真实模型端点。既有证据显示，本系统已经具备完整工程闭环、标准化重复实验能力、真实 AI 主导短程回合证据，以及长程 resilience 证据。正向 real-AI 结果中，单次 120-turn short smoke 的 `ai_authored_ratio` 达到 `0.7667`；`Phase 3` 的 story guidance probe 将该比率提升至 `0.8917` 并实现 `Route 1` 到达；battle guidance probe 在 `ai_authored_ratio = 0.8417`、`fallback_turns = 0` 条件下，直接记录到 AI 在真实模型条件下做出 `FIGHT` 与 `Scratch` 的首个正确战斗菜单决策。另一方面，重复 batch 结果仍呈现较大方差，尚未稳定达到 `got_pokedex`、`oak_got_parcel` 或更高里程碑；外部 provider 在 `2026-04-05` 与 `2026-04-06` 均出现过可用性波动，这使得系统当前可以被严谨地表述为“具备完整工程闭环与早期剧情可行性验证的长时任务游戏智能体”，但尚不能被表述为“稳定完成中长程主线推进的成熟自治体”。

基于现有证据，本文的主要贡献为：  
1. 提出一个面向 `Pokemon Red` 的混合式大模型智能体框架，将 RAM 状态、可选视觉、地图记忆、任务记忆、规则控制与 LLM 决策整合为可长时运行的工程系统。  
2. 建立区分工程有效性、resilience evidence 与 real-AI evidence 的标准化实验管线，避免将 fallback 主导运行误写为 AI 主导结果。  
3. 通过批量实验与修复前后对比，揭示 transport/provider 异常与局部剧情理解不足是当前系统的两类核心瓶颈。  
4. 给出一份面向顶刊标准的论文草稿与证据边界说明，明确哪些结论已被证明，哪些仅被部分证明，哪些仍需新增实验支持。

**关键词**：长时序任务；大模型智能体；Pokemon Red；RAM 状态读取；地图记忆；实验可复现性；运行时韧性

## Abstract

Long-horizon video-game environments provide a stringent testbed for general-purpose agents because they couple sparse milestones, high exploration difficulty, UI-heavy interaction, and partially observable state transitions. Compared with short-horizon arcade benchmarks, `Pokemon Red` requires an agent to coordinate navigation, dialogue progression, battle choices, event triggers, memory, and recovery over extended trajectories. This paper studies a hybrid LLM-driven game agent for early-story progression in `Pokemon Red`. The system integrates emulator control, RAM-based state extraction, optional vision cues, map memory, context summarization, goal management, action execution, checkpoint recovery, and standardized smoke/batch evaluation into a closed-loop runtime.

Unlike a pure reinforcement-learning policy, the proposed system follows a constrained generative-agent paradigm: ordinary turn-by-turn decisions are owned by the language model, while deterministic controllers remain limited to bootstrap, safety, recovery, and story-guard roles. Inspired by Generative Agents, we organize long-term task context as recent turns, historical summaries, compact task notes, and hierarchical goals; inspired by recent RL work on `Pokemon Red`, we formalize the environment as a long-horizon partially observable control problem and evaluate it with AI ownership, fallback ratio, milestone reachability, timeline validity, and resilience metrics.

As of April 6, 2026, the latest local reverification shows `299 passed, 1 warning` in the full test suite under normal permissions, `7/7` environment checks, and successful direct API connectivity. Existing evidence demonstrates a complete engineering loop, repeated-evaluation capability, short-horizon AI-dominant runs, and long-horizon resilience. Positive real-AI probes reach AI-authored ratios up to `0.8917`, successfully enter `Route 1`, and explicitly produce the first correct actionable battle choices (`FIGHT`, `Scratch`) under real model conditions. However, repeated-batch variance remains high, stronger milestones such as `got_pokedex` and `oak_got_parcel` are not yet stable, and external provider availability fluctuates intra-day. Therefore, the current system can be rigorously claimed as a complete long-horizon game-agent framework with verified early-story feasibility, but not yet as a mature autonomous agent that stably completes medium-horizon story progression.

## 第 1 章 绪论

### 1.1 研究背景

长时序智能体研究正在从“短步长、单目标、低交互复杂度”的环境逐步转向“跨阶段、多目标、强上下文依赖”的环境。传统游戏 AI 基准如 Atari 强调快速反应、像素控制和稠密回报，但对于长期任务组织、剧情触发、菜单交互、外部工具调用和记忆管理的考察相对有限。相较之下，`Pokemon Red` 具有以下显著特征：

1. 任务链长。玩家必须在多个城镇、室内房间、对话节点、野战与训练家战之间不断切换，许多关键事件具有严格的先后依赖。
2. 状态部分可观测。单帧截图无法完整刻画地图结构，单步 RAM 状态也无法直接说明当前屏幕语义、场景阻挡或可视路径。
3. 行为空间异质。动作不仅包含方向移动，还包含菜单确认、取消、战斗技能选择、命名输入与剧情交互。
4. 失败模式复杂。一个失败样本既可能来自模型误解当前任务，也可能来自 API 超时、provider 波动、局部卡死、错误 cooldown 放大、错误路由或 UI 标志滞后。

因此，`Pokemon Red` 不仅是一个“能不能玩”的问题，更是一个“能否构造具备闭环观测、目标管理、上下文压缩、恢复能力和可复现实验路径的复杂智能体系统”的问题。

### 1.2 研究问题

本文聚焦以下三个研究问题：

1. 能否构造一个完整的、可长时运行的 `Pokemon Red` 混合式大模型智能体系统，使其在真实 API 条件下具备可观测、可恢复、可复验的工程闭环？
2. 在 `llm_primary_mode = true` 与 `ai_full_control_mode = true` 的条件下，真实 AI 是否已经能够主导早期剧情中的大多数普通回合，并在 `Route 1` 等关键局部场景中作出正确动作？
3. 当前系统未能稳定突破更强里程碑时，瓶颈主要来源于哪里：运行时恢复逻辑、局部剧情理解、实验协议方差，还是外部 provider 可用性？

### 1.3 研究目标与论文边界

本文的目标不是证明系统“已经稳定自主通关 `Pokemon Red`”，而是更克制也更严谨地证明以下命题：

- 系统工程层面已经成立：存在完整的感知、决策、执行、观察、恢复和评估闭环。
- 真实 AI 主导性已被局部证明：在若干短程实验中，AI 占据多数普通回合，并能推进至 `Route 1`，且能做出首个正确战斗菜单动作。
- 当前中程自主推进尚未被充分证明：`got_pokedex`、`oak_got_parcel`、`Viridian City` 之后的 repeated batch 仍明显不足。

### 1.4 主要贡献

本文的贡献不在于“提出全新基础模型”，而在于围绕复杂长时序环境，将大模型与运行时控制层、地图记忆、上下文管理和评估治理有机结合，并给出一套可落地、可审计的证据体系。与单纯展示成功视频不同，本文同时保留失败样本与负证据，以避免结论膨胀。

### 1.5 论文结构

第 2 章回顾相关工作与理论基础；第 3 章对任务进行形式化定义；第 4 章介绍系统设计与实现；第 5 章给出实验设计、评价指标与证据分类；第 6 章展示核心实验结果；第 7 章讨论证据边界、局限性与顶刊差距；第 8 章总结全文并给出后续工作方向。

## 第 2 章 相关工作与理论基础

### 2.1 生成式智能体与长期记忆架构

Park 等人在 Generative Agents 中提出了 memory、reflection 与 planning 三层协同的智能体架构 [1]。其核心思想不是单纯依赖一次性 prompt，而是维护持续增长的记忆流，并通过相关性、重要性与时间新近性组合检索有效上下文。其典型检索思想可以写为：

$$
\mathrm{score}_i=\alpha_r \cdot \mathrm{recency}_i+\alpha_i \cdot \mathrm{importance}_i+\alpha_s \cdot \mathrm{relevance}_i.
$$

这一公式的重要意义在于，它把“长期一致行为”的问题转化为“可检索、可压缩、可反思”的记忆组织问题。对本文的启发有两点：

1. 长时任务游戏智能体不能只看当前截图，而必须把近期行动结果、历史摘要和当前目标并入同一决策上下文。
2. 记忆组织不一定要完整复制 Generative Agents 的实现细节，也可以采用更工程可控的近似实现。

本文系统并未完整实现 [1] 中的社会模拟、多智能体反思与高层抽象推理链，而是以 `ContextManager + Summarizer + GoalManager + GameState` 为主线，构造适合 `Pokemon Red` 单智能体长时运行的任务记忆结构。这一点必须明确，否则容易造成理论借鉴与实际实现之间的错配。

### 2.2 Pokemon Red 作为长时序研究环境

Pleines 等人在 `Pokémon Red via Reinforcement Learning` 中把 `Pokemon Red` 定位为一个长时序、多任务耦合、高探索难度的研究环境 [2]。他们强调该环境同时包含：

- 2D 导航与地图探索；
- 战斗策略与资源管理；
- 菜单/界面交互；
- 长时序任务链与弱即时奖励。

这一定性与本文项目高度一致，但方法路线不同。[2] 采用的是 PPO 驱动的 DRL 训练代理，其优势在于可以给出标准 MDP、奖励塑形与样本效率分析；本文采用的则是在线 LLM 决策代理，其优势在于无需大规模训练、具备较强的语义先验与任务可解释性，但代价是受到上下文组织、provider 延迟、API 稳定性与局部 prompt 设计的显著影响。

因此，本文借用 [2] 的价值主要体现在两个层面：

1. 作为环境复杂性的外部论据，说明选择 `Pokemon Red` 并非偶然。
2. 作为问题形式化与实验撰写范式的参考，用于说明本文为何需要单独讨论长时序、多阶段里程碑和局部剧情瓶颈。

### 2.3 规则控制、工具调用与混合式智能体

纯脚本系统虽然具有强确定性，但难以扩展到开放剧情理解；纯大模型代理虽然灵活，但容易受 UI 误读、 provider 波动或局部循环影响。本文采用混合式设计：规则控制器负责启动流程、特殊剧情边界、稳定恢复与安全保护，普通场景下由主智能体生成动作。这一设计遵循“把确定性交给安全层，把开放式判断交给大模型”的原则。

这一思路并不等同于传统基于行为树或有限状态机的全脚本游戏 AI，也不同于端到端 DRL 策略。它更像一种 runtime-mediated agent：模型拥有普通决策主权，但运行时通过轻量路由、行动执行器与 fallback 机制限制灾难性失稳。

### 2.4 本文的方法定位

综合来看，本文方法位于三类方法的交叉区域：

1. 生成式智能体：借鉴记忆、规划与任务分层思想。
2. 游戏代理系统：强调模拟器接入、实时 UI/状态处理和动作回写。
3. 工程化实验平台：强调证据治理、重复实验、失败样本保留和图像/日志归档。

如果要用一句话概括本文方法定位，可以表述为：  
**本文提出的是一个面向长时序 JRPG 的混合式大模型运行时智能体框架，而不是一个已经完成大规模训练的最优策略模型。**

## 第 3 章 问题定义与形式化描述

### 3.1 部分可观测长时序决策问题

本文将 `Pokemon Red` 早期剧情推进过程建模为一个部分可观测马尔可夫决策过程（POMDP）：

$$
\mathcal{M}=(\mathcal{S}, \mathcal{A}, \mathcal{O}, T, \Omega, R, \gamma),
$$

其中：

- $\mathcal{S}$ 表示真实游戏状态，包括 RAM 内部事件位、地图、NPC 位置、战斗状态等；
- $\mathcal{A}$ 表示离散动作集合；
- $\mathcal{O}$ 表示可观测信息空间；
- $T$ 为状态转移；
- $\Omega$ 为观测函数；
- $R$ 为评价或任务推进上的外部指标；
- $\gamma$ 为折扣因子。

与 [2] 中使用训练期奖励塑形不同，本文主要关心运行时任务推进与证据评估，因此并不把 $R$ 作为在线优化目标，而是把它用作实验后评价量。

### 3.2 观测与动作定义

在本文系统中，单步观测可以写为：

$$
o_t = \big[x_t^{ram},\; x_t^{img},\; x_t^{nav},\; x_t^{ctx},\; x_t^{goal}\big],
$$

其中：

- $x_t^{ram}$：由 `MemoryReader` 从 RAM 中读取的位置、队伍、金钱、事件位、战斗状态等；
- $x_t^{img}$：当前截图以及可选视觉分析；
- $x_t^{nav}$：地图记忆与局部导航信息，包括已探索区域、frontier、已知出口、局部阻塞等；
- $x_t^{ctx}$：近期回合、摘要历史、任务笔记和指导注记；
- $x_t^{goal}$：当前 focus、todo 列表与长中短期目标。

动作空间定义为：

$$
\mathcal{A}=\{\texttt{up}, \texttt{down}, \texttt{left}, \texttt{right}, \texttt{a}, \texttt{b}, \texttt{start}, \texttt{select}\}.
$$

在执行层中，`ActionExecutor` 会把单步动作展开为具体按键按下、释放与 settle frames，从而把“高层动作 token”映射为模拟器可执行的时序事件。

### 3.3 混合式决策函数

系统决策函数不是单一策略网络，而是规则路由与大模型策略的组合：

$$
a_t=
\begin{cases}
a_t^{(k)}, & \exists k,\; C_k(o_t,h_t)\neq \varnothing, \\
\pi_\theta(o_t,h_t), & \text{otherwise},
\end{cases}
$$

其中 $C_k$ 表示第 $k$ 个确定性控制器，$h_t$ 表示运行历史与上下文，$\pi_\theta$ 表示大模型主智能体。该式意味着：当明确的启动、恢复或剧情保护条件满足时，控制器优先；否则由主智能体给出动作。

为了防止把“控制器接管”误写成“AI 主导”，本文进一步定义 AI ownership 指标：

$$
\rho_{\mathrm{main}}=\frac{N_{\mathrm{main}}}{N_{\mathrm{total}}}, \qquad
\rho_{\mathrm{AI}}=\frac{N_{\mathrm{main}}+N_{\mathrm{plan}}}{N_{\mathrm{total}}},
$$

$$
\rho_{\mathrm{fallback}}=\frac{N_{\mathrm{fallback}}}{N_{\mathrm{total}}},
$$

其中：

- $N_{\mathrm{main}}$ 为主模型直接生成动作的回合数；
- $N_{\mathrm{plan}}$ 为缓存 AI 计划所执行的回合数；
- $N_{\mathrm{fallback}}$ 为 fallback 占据的回合数；
- $N_{\mathrm{total}}$ 为总回合数。

这三个指标分别对应代码中的 `main_model_ratio`、`ai_authored_ratio` 与 `fallback_ratio`。

### 3.4 里程碑驱动的任务进展度量

由于本文并不训练策略网络，因此不使用累计回报作为核心结论，而采用剧情里程碑集合：

$$
\mathcal{K}=\{\texttt{got\_starter},\texttt{entered\_oaks\_lab},\texttt{reached\_route1},\texttt{got\_pokedex},\texttt{oak\_got\_parcel},\texttt{reached\_route2},\texttt{reached\_viridian\_forest}\}.
$$

为进行紧凑比较，可定义一个加权进展分数：

$$
P=\sum_{k \in \mathcal{K}} w_k \mathbf{1}[k\ \text{achieved}],
$$

其中 $w_k$ 反映里程碑的重要性。本文实际报告中主要使用“最佳故事进展”和关键布尔字段，而不夸大单一分数的统计意义。

### 3.5 证据有效性的判定条件

为了将论文证据与研发日志分开，本文规定一份 smoke 报告只有在满足以下条件时，才可被视为正式正证据：

1. `fatal_error = null`；
2. `timeline_valid = true`；
3. 运行模式明确；
4. AI ownership 与论文声称一致；
5. 参数、checkpoint 与环境元数据可追溯。

这一定义直接来自仓库中的评估文档与批量实验协议，而非事后口头解释。

## 第 4 章 系统设计与实现

### 4.1 总体架构

系统以 `main.py` 中的 `PokemonAIAgent` 作为主协调器，围绕模拟器、状态感知、决策控制、记忆目标、执行观察和实验评估六个层面组织。现有文档中已经提供了系统总体架构图、决策子系统图与实验取证链路图，这些图可直接用于论文正式版排版 [3]。

整体而言，系统遵循以下闭环：

1. 从模拟器读取 RAM 与截图；
2. 将其编码为结构化状态文本；
3. 由决策引擎先执行确定性路由，再在普通回合交由主智能体；
4. 由动作执行器将动作回写给模拟器；
5. 记录结果、截图、日志、检查点与指标；
6. 用 smoke/batch 工具将运行过程沉淀为可复验报告。

### 4.2 模拟器接入与 RAM 状态读取

`GameBoyEmulator` 负责启动 `PyBoy`、发送按键、读取截图、保存/加载状态；`MemoryReader` 则将底层内存地址解释为高层语义。当前 `MemoryReader` 已支持：

- 玩家坐标与地图 ID；
- 面向方向；
- 徽章、金钱、物品数量；
- 队伍信息与招式；
- 战斗状态；
- 少量关键剧情事件位，如 `got_pokedex`、`oak_got_parcel` 与 `got_oaks_parcel`。

这种设计相较仅依赖像素观测具有两个优势：

1. 关键状态读取稳定，可直接用于研究性日志记录与实验表格；
2. 在文本生成状态摘要时，可以把低层 RAM 量化为更适合大模型理解的高层描述。

但 RAM 读取并不能完全代替视觉，因为 UI 面板、菜单层级、障碍物可见性以及局部路径连续性仍需要截图补充判断。

### 4.3 游戏状态构造与文本化表示

`GameState` 是本文方法的核心桥梁。它将 RAM 状态、视觉提示、地图记忆、近期运动模式和战斗摘要组织为统一状态字典，并进一步通过 `get_text_representation()` 生成主智能体 prompt 的状态文本。

该状态文本并非简单罗列字段，而是包含以下多个专门子块：

- `POSITION`：地图、坐标、朝向与屏幕类型；
- `PARTY`：队伍等级、HP、招式与 PP；
- `BATTLE SUMMARY`：战斗阶段、敌方 HP 变化与 lead 信息；
- `BATTLE GUIDANCE`：战斗菜单选择提示；
- `STORY GUIDANCE`：早期剧情目标提示；
- `STATE DELTAS`：位置是否变化、金钱增量、battle toggled 等；
- `MOVEMENT PATTERN`：近期 movement box 与 loop warning；
- `NAVIGATION MEMORY`：已知出口、frontier、阻挡方向与局部地图信息。

这种设计的关键价值在于：它把“模型自己从杂乱状态中找重点”的难题，转化为“系统先把对当前任务最重要的结构线索提纯后再交给模型”。这也是 `Phase 3` 两轮增强能取得明显提升的直接原因之一。

### 4.4 Story Guidance 与 Battle Guidance 机制

为改善 Oak Lab 和 Route 1 的局部瓶颈，当前系统在 `GameState` 中引入了两个专门机制。

第一，`_build_story_guidance()` 会在特定剧情早期阶段发出窄域目标提示，例如：

- 离开 Oak's Lab；
- 沿 Pallet Town 东侧路径向北推进；
- 在对齐北出口时优先 `UP`；
- 不要把城镇横向漂移当作主要探索目标。

第二，`_build_battle_guidance()` 会在战斗 UI 中给出高优先级局部提示，例如：

- 文本框未结束时优先 `A` 推进；
- 四选一战斗菜单出现时优先 `FIGHT`；
- 招式列表出现时优先具备伤害的招式槽位；
- 低 HP 时避免无意义菜单游走。

在 prompt 侧，`MainAgent` 进一步显式规定：如果状态文本中存在 `BATTLE GUIDANCE`，则其为战斗期间最高优先级局部线索。该设计使系统从“到达战斗场景但停住”推进到“明确给出 `FIGHT` 和 `Scratch`”。

### 4.5 主智能体与上下文管理

`MainAgent` 负责构造系统提示词、拼接当前状态文本、近期行动历史、任务笔记和目标层级，并通过 `AIClient` 调用外部模型。相较随意式 prompt，当前系统提示词显式约束了：

- 局部任务优先级；
- 黑色区域不等于可走空间；
- 房间内优先找出口而非无目的探索；
- 多次方向失败后应切换策略；
- battle menu 与 naming screen 的具体处理规则；
- 仅能输出受限格式：`SCREEN_TYPE / REASONING / ACTION / ACTION_PLAN / GOAL_UPDATE`。

与此同时，`ContextManager` 维护近期回合、摘要历史、额外注记与任务笔记；`Summarizer` 负责摘要压缩；`GoalManager` 维护 long-term goal、focus 与 todo 列表。这一组合对应于 [1] 中记忆、规划与反思思想的工程化简化版。

为了更准确刻画这一结构，可以把当前 prompt 上下文近似写成：

$$
h_t = \mathrm{Concat}\big(H_t^{recent}, H_t^{summary}, H_t^{note}, G_t^{plan}\big),
$$

其中 $H_t^{recent}$ 是近期回合历史，$H_t^{summary}$ 是压缩摘要，$H_t^{note}$ 是任务笔记与避免重复策略，$G_t^{plan}$ 是目标结构。

### 4.6 决策路由与安全控制器

`DecisionEngine` 采用“顺序 stage + AI fallback”的路由模式。其逻辑很简单但非常关键：按顺序调用若干确定性 stage，一旦某个 stage 命中则直接返回；如果均未命中，则进入模型决策。

这一设计把运行时分成两类控制权：

1. **普通回合主控权**：由大模型持有；
2. **保护性接管权**：由规则控制器在极少数特定情形下持有。

当前系统中的控制器覆盖 Oak Lab pre-starter、starter、rival battle、early battle、post battle intro route、viridian parcel 等早期高风险阶段。值得强调的是，在 `ai_full_control_mode = true` 下，这些控制器并不是为了取代模型完成整个剧情，而是为了避免 UI 恢复、剧情锁、warp 或局部死循环把实验彻底污染。

### 4.7 动作执行、卡死检测与可观测性

`ActionExecutor` 并不简单地把动作 token 直接写进模拟器，而是会针对移动动作进行多次轻量重试，用以逼近“一个高层动作≈一个有效格点移动”的效果；同时通过 settle frames 让画面稳定后再采样下一帧。  
此外，执行器还具备卡死检测能力：当连续重复同一动作且不属于正常菜单/对话推进时，会触发 stuck warning。

在可观测性方面，`GameVisualizer` 提供实时仪表盘，显示状态、事件流、任务列表、最近决策和截图；`ProgressTracker`、日志系统和检查点系统共同构成实验可追溯性基础。  
这也是本文区别于“只给一个跑通视频”的重要地方：当前项目实际上已经具备完整的实验平台属性。

## 第 5 章 实验设计、证据分类与评价指标

### 5.1 实验目标

本文实验并不试图一次性回答“能否通关整部游戏”，而是分层回答：

1. 系统是否工程有效？
2. 真实 AI 是否真正参与并主导短程回合？
3. 重复实验能力是否建立？
4. 长程运行是否具备韧性？
5. 当前瓶颈位于何处？

### 5.2 证据分类原则

根据项目内部证据索引 [4]，本文将证据分为四类：

- **A 类：工程有效性与稳定性证据**。如 `pytest`、`test_setup.py`、`test_custom_api.py`。
- **B 类：resilience evidence**。如 1800/2600/4000 turn 长程 smoke，用于证明“不崩溃、可恢复、可持续运行”。
- **C 类：real-AI evidence**。要求真实模型参与且 AI ownership 达到可支撑结论的水平。
- **D 类：论文支持文档**。包括图号索引、架构图、批量评估、附录联系表等。

这一分类直接解决了很多项目答辩中常见的问题：同样都是“系统跑了很久”，但有的报告只能证明系统不崩溃，不能证明 AI 真正主导了关键决策。

### 5.3 实验协议

当前仓库已形成标准化评估工作流 [5]。核心 short smoke 协议为：

- checkpoint：`checkpoint_195913`
- turns：`120`
- 模式：`llm_primary + ai_full_control`
- 参数：`--reset-context --decision-max-tokens 384 --action-plan-max-actions 3`

批量实验协议则通过 `scripts/autonomous_smoke_batch.py` 固定：

- checkpoint；
- turns；
- runs；
- 模型与 endpoint；
- 输出 manifest、summary、raw JSON、stdout/stderr。

这使得论文可以在“同协议、同 checkpoint、同参数”的基础上比较修复前后结果，而不是拼接不同时间、不同模式的零散样本。

### 5.4 评价指标

本文使用以下核心指标：

1. **工程指标**
   - 全量测试通过数；
   - 环境检查通过数；
   - API 直连成功与否。
2. **控制权指标**
   - `main_model_ratio`
   - `ai_authored_ratio`
   - `fallback_turns`
   - `ai_dominant`
3. **有效性指标**
   - `fatal_error`
   - `timeline_valid`
4. **剧情里程碑**
   - `reached_route1`
   - `got_pokedex`
   - `oak_got_parcel`
   - `reached_route2`
   - `reached_viridian_forest`
5. **效率指标**
   - `ai_latency_summary.avg_seconds`
   - `ai_latency_summary.max_seconds`

### 5.5 图片证据组织

截至 `2026-04-06`，仓库内图像与图像文档已基本完成分层管理：

- `docs/img/` 下共 `312` 个文件；
- `docs/report_assets/` 下共 `150` 个原始图像文件；
- `docs/img/2026-04-05/main_figures/` 下有 `7` 张正文主图；
- `docs/img/2026-04-05/appendix_run_130/raw/` 下有 `130` 张逐 turn 原始截图；
- `docs/img/2026-04-05/appendix_run_130/contact_sheets/` 下有 `13` 张附录联系表。

从证据治理角度，这一组织已经明显优于普通课程项目；但从顶刊排版质量看，部分正文图仍只是未经标注的原始 Game Boy 小图，尚不足以作为正式发表图。

### 5.6 最新本地复验

为避免论文完全建立在历史文档上，本文纳入 `2026-04-06` 的本地复验记录 [6]：

- `pytest -q`：在正常权限环境下 `299 passed, 1 warning`；
- `python test_setup.py`：`7/7` 通过；
- `python test_custom_api.py`：成功。

需要注意的是，同日早些时候的审计文档曾记录到 provider 返回 `500 / 没有可用 token` 的失败案例 [7]。这说明 API 可用性在日内层面存在波动，必须单独作为实验噪声源讨论。

## 第 6 章 实验结果与分析

### 6.1 工程完整性与可运行性结果

从系统工程角度，当前结果已经足够强。第一，全量测试在正常权限环境下达到 `299 passed, 1 warning`，说明核心模块间没有出现明显回归。第二，`test_setup.py` 的 `7/7` 通过表明 Python、依赖、ROM、目录、配置与 API 基本连通条件均满足运行要求。第三，`test_custom_api.py` 成功说明本文不是在 dummy endpoint 或离线 mock 环境下写论文。

这三点使本文可以稳妥写出如下命题：  
**系统已具备真实环境下的可运行性、工程稳定性和最小实验闭环。**

### 6.2 正向 real-AI 证据

现有最关键的正向 short smoke 与阶段性 probe 如表 6-1 所示。

| 证据 | turns | `ai_authored_ratio` | `main_model_ratio` | `fallback_turns` | 关键里程碑 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `2026-04-05_real_ai_smoke_120.json` | 120 | 0.7667 | 0.7083 | 0 | `entered_oaks_lab` | 真实 AI 已主导大多数早期回合 |
| `phase3_field_recovery_probe.json` | 120 | 0.7000 | 0.6083 | 0 | 未到 `Route 1` | 恢复逻辑改善，去掉长 fallback 尾巴 |
| `phase3_story_guidance_probe.json` | 120 | 0.8917 | 0.7500 | 0 | `reached_route1 = true` | AI 已穿过 Pallet Town 北出口进入 `Route 1` |
| `phase3_battle_guidance_probe_shortcooldown.json` | 120 | 0.8417 | 0.7083 | 0 | `reached_route1 = true` | AI 在真实模型条件下做出 `FIGHT` 与 `Scratch` |

这组结果的重要意义在于：系统已经不只是“AI 有时能动一动”，而是已经产生连续的、可复述的、与真实剧情节点相对应的短程主导证据。

### 6.3 Route 1 到达与战斗决策能力

`Phase 3` 的最大进展体现在两个层次。

第一，story guidance 使系统从“停留在 Pallet Town 北缘徘徊”推进到“明确进入 `Route 1`”。这表明加入窄域剧情提示后，模型不再把横向 frontier 漫游误当作主要目标。

第二，battle guidance 使系统从“到达 Route 1 但卡在战斗中”推进到“战斗菜单出现后明确执行 `FIGHT`，进入招式列表后执行 `Scratch`”。这意味着 AI 已经能在真实战斗 UI 中完成首个有效可执行决策，而不是只靠脚本接管或 fallback 逃逸。

从证据强度上看，第二点比“仅到达 Route 1”更强，因为它直接触及游戏中的关键交互瓶颈：战斗文本、菜单层级与动作语义映射。

### 6.4 重复 batch：修复前后对比

`Phase 2` 的价值不在于制造一批漂亮成功样本，而在于建立“重复实验能力”和“失败原因可定位能力”。

修复前的第一轮固定协议 batch 结果为：

- `3/3` 完成；
- `0/3` AI-dominant；
- `avg_ai_authored_ratio = 0.0194`。

修复后的第二轮 batch 结果为：

- `3/3` 完成；
- `1/3` AI-dominant；
- `avg_ai_authored_ratio = 0.3000`；
- `avg_main_model_ratio = 0.2778`。

这说明 transport 错误分类修复确实显著影响 real-AI 证据可信度。换言之，先前极低 AI 占比并不全是“模型不会玩”，其中相当一部分是瞬时连接异常被放大成长时间 fallback。  
然而，这组结果也同时说明：即使 transport 问题得到缓解，Oak Lab 局部决策质量依旧是核心瓶颈，因为 repeated batch 仍未稳定推进到 `got_pokedex` 或 `oak_got_parcel`。

### 6.5 长程 resilience 证据

长程 smoke 报告显示，系统能够在 `1800`、`2600`、`4000` turn 下完成运行，并推进至 `Pokedex / Route 2 / Viridian Forest`。这证明：

1. 检查点恢复与运行时保护层是有效的；
2. 系统即使在 AI 占比很低时，也不会轻易崩溃；
3. 长程运行能力已经成立。

但这些报告的 `Avg AI-authored ratio` 仅约 `0.0022`，因此它们只能归入 resilience evidence，而不能被写作“真实 AI 已稳定主导长程剧情”。

这是当前论文必须坚守的一条红线：  
**不能因为系统跑到了更远地图，就自动把它解释为 AI 主导了更远地图。**

### 6.6 图片证据分析

通过对正文主图和附录联系表的直接抽检，可以得到如下判断：

1. `fig01_dashboard_desktop.png` 与 `fig07_route2_map_memory.png` 质量较高，适合作为正文主图。
2. `fig03_oaks_lab_departure.png`、`fig05_route1_battle_prebattle.png` 一类图虽然有真实取证价值，但仍保留 Game Boy 原始分辨率特征，适合做“证据图”，不适合直接做“发表级主图”。
3. `sheet_12.png` 一类 contact sheet 非常适合作为附录核验材料，但由于单帧太小，不适合作为正文核心视觉证据。

因此，图片层面的严格结论是：

- 当前图像体系足以支撑答辩与附录核验；
- 当前图像体系不足以支撑顶刊级主图表现；
- 需要新增 4 倍或 6 倍最近邻放大的局部关键图，并叠加箭头、框注与决策链标注。

### 6.7 当前哪些命题已被证实

截至目前，可以被严格证实的命题包括：

1. 系统已完成模拟器接入、RAM 读取、地图记忆、上下文管理、动作执行、检查点恢复、可视化与评估脚本组成的完整闭环。
2. 在真实模型条件下，AI 已能主导若干短程运行。
3. `Phase 3` 提示工程显著提高了 `Route 1` 到达率和战斗菜单首步决策质量。
4. 长程运行的韧性已得到验证。

### 6.8 当前哪些命题仅被部分证实

以下命题只有部分证据：

1. 系统具备 repeated batch 能力，但成功方差仍大。
2. AI 能到达 `Route 1` 并进入战斗，但后续战斗文本与 post-battle continuation 仍是瓶颈。
3. provider 异常与局部决策失误均会影响实验结果，但两者的精确贡献比例尚无正式统计表。

### 6.9 当前哪些命题尚未被证实

以下命题当前不能强写：

1. 系统已稳定拿到 `got_pokedex`；
2. 系统已稳定拿到 `oak_got_parcel`；
3. 系统已稳定完成 `Route 1 -> Viridian -> Parcel` 中程推进；
4. 系统已具备低方差高成功率的真实重复实验结果；
5. 系统已具备接近顶刊标准的完整对照与消融矩阵。

## 第 7 章 讨论：证据边界、局限性与顶刊差距

### 7.1 与 Generative Agents 的关系

本文系统与 [1] 的关系是“结构启发”，而非“严格复现”。二者共同点在于都重视长期记忆、任务规划和上下文组织；不同点在于：

- [1] 聚焦多智能体社会模拟与行为可信感；
- 本文聚焦单智能体游戏任务中的闭环执行与阶段推进；
- [1] 更强调反思生成高层社会性推断；
- 本文更强调状态提纯、任务提示和运行时保护。

因此，最合理的表述应是：  
**本文是把 Generative Agents 的记忆-规划思想迁移到游戏任务环境中的受约束工程化实例。**

### 7.2 与 RL 路线的关系

本文系统与 [2] 的关系则更像“问题共享、方法不同”。二者共同承认 `Pokemon Red` 的长时序复杂性，但解决路径不同：

- RL 路线依赖长期训练、奖励塑形与采样效率；
- 本文路线依赖预训练语言模型、结构化状态、上下文组织与运行时路由。

从研究贡献看，本文并不试图证明 LLM 路线必然优于 RL；它所证明的是：在没有大规模训练的前提下，依靠 RAM 状态文本、地图记忆和运行时工程，也可以建立一个具有真实 AI 主导短程证据的长时序代理框架。

### 7.3 外部服务可用性的实验噪声

这是本文必须严肃讨论的一点。  
在 `2026-04-05` 与 `2026-04-06` 的证据中，provider 既出现过 `500 / 没有可用 token` 的失败样本，也出现过同日稍后直连成功的复验结果。  
这意味着：

1. 实验结果不仅受模型能力影响，也受服务端负载和 token 可用性影响；
2. 如果不把失败样本保留下来，就会误把 provider 波动当作模型性能波动；
3. 顶刊级实验必须引入成本/延迟/错误次数统计表，而不仅仅给成功 run。

### 7.4 当前系统的真正贡献与真正短板

当前系统最强的地方不是“已经能通关”，而是：

- 已完成工程闭环；
- 已有真实 AI 主导短程证据；
- 已有失败样本归档；
- 已形成论文证据治理框架。

当前系统最弱的地方也很明确：

- 中程剧情推进不足；
- repeated batch 方差大；
- 正文图像质量不够发表级；
- 缺失正式消融表、成本表与人类/启发式基线。

### 7.5 顶刊目标下仍需补充的关键材料

若以顶刊标准而非本科答辩标准衡量，当前最需要补的不是更多零散文档，而是以下五类硬证据：

1. **更强 repeated batch**
   - 至少一组稳定推进到 `Viridian City` 或 `Oak's Parcel`。
2. **正式消融表**
   - `llm_primary` 开/关；
   - `ai_full_control` 开/关；
   - `story guidance` 开/关；
   - `battle guidance` 开/关。
3. **成本与延迟统计表**
   - 平均响应时延、最大时延、provider error 次数、fallback 比例。
4. **人类或启发式基线**
   - 至少比较里程碑步数与成功率。
5. **发表级图像重制**
   - 放大、标注、决策链可视化。

### 7.6 论文应如何控制结论强度

本文最重要的写作原则是：**不要把“已建立可行性”写成“已建立成熟自治性”。**  
如果以顶刊风格撰写，正确姿态不是夸张结果，而是明确边界：

- 已证实：工程闭环、短程 AI 主导、局部战斗决策成立。
- 部分证实：Route 1 推进与重复实验能力。
- 未证实：中程剧情稳定推进与低方差高成功率。

## 第 8 章 结论与展望

本文围绕 `Pokemon Red` 早期剧情推进问题，提出并分析了一个混合式大模型游戏智能体系统。该系统通过模拟器接入、RAM 读取、可选视觉、地图记忆、任务记忆、动作执行、检查点恢复和可视化，构成了完整的长时任务闭环。基于当前仓库和截至 `2026-04-06` 的最新复验结果，本文证明了以下几点：

1. 系统工程层面已经成熟到足以支撑本科毕设级乃至高质量研究型原型论文的程度；
2. 在真实模型条件下，AI 已经能够主导多数短程回合，并在 `Route 1` 的首个野战场景中做出正确可执行战斗动作；
3. transport/provider 异常、局部剧情理解不足与 post-battle continuation 是当前中程推进未稳定突破的三类关键瓶颈；
4. 长程 resilience 已被证明，但不应与 AI-led mid-horizon success 混为一谈。

从研究与工程两方面看，本文最重要的价值在于：它把一个“能不能让大模型玩老游戏”的演示问题，推进为一个“如何为长时序开放任务构造可审计、可复验、可解释的混合式智能体运行时系统”的研究问题。

未来工作可沿三条主线展开：

1. 强化中程剧情推进能力，优先突破 `Viridian City` 与 `Oak's Parcel`；
2. 完成正式消融、延迟成本统计与基线比较；
3. 将现有证据包升级为发表级材料包，包括高质量主图、失败 taxonomy 图、方法定位图和复现实验清单。

---

## 参考文献

[1] Joon Sung Park, Joseph C. O’Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein. *Generative Agents: Interactive Simulacra of Human Behavior*. UIST 2023.

[2] Marco Pleines, Daniel Addis, David Rubinstein, Frank Zimmer, Mike Preuss, Peter Whidden. *Pokémon Red via Reinforcement Learning*. arXiv:2502.19920, 2025.

[3] Pokemon-AI 项目内部文档. *2026-04-05 系统架构图*. `docs/2026-04-05_system_architecture_diagram.md`, 2026.

[4] Pokemon-AI 项目内部文档. *2026-04-05 论文证据索引*. `docs/2026-04-05_thesis_evidence_index.md`, 2026.

[5] Pokemon-AI 项目内部文档. *Evaluation Workflow*. `docs/evaluation_workflow.md`, 2026.

[6] Pokemon-AI 项目内部文档. *2026-04-06 本地复验记录*. `docs/thesis_logs/2026-04-06_local_reverification.md`, 2026.

[7] Pokemon-AI 项目内部文档. *2026-04-06 顶刊标准论文证据审计*. `docs/2026-04-06_top_tier_thesis_readiness_audit.md`, 2026.

[8] Pokemon-AI 项目内部文档. *2026-04-05 毕业设计总报告*. `docs/2026-04-05_graduation_design_full_evidence_report.md`, 2026.

[9] Pokemon-AI 项目内部文档. *2026-04-05 Phase 2 真实 AI 重复实验阶段评估*. `docs/2026-04-05_phase2_real_ai_batch_assessment.md`, 2026.

[10] Pokemon-AI 项目内部文档. *2026-04-05 Phase 3 Story Guidance Assessment*. `docs/2026-04-05_phase3_story_guidance_assessment.md`, 2026.

[11] Pokemon-AI 项目内部文档. *2026-04-05 Phase 3 Battle Guidance Assessment*. `docs/2026-04-05_phase3_battle_guidance_assessment.md`, 2026.

[12] Pokemon-AI 项目内部文档. *2026-04-05 论文图号索引*. `docs/img/2026-04-05_figure_index.md`, 2026.

[13] Pokemon-AI 项目内部文档. *2026-04-05 Thesis Image Manifest*. `docs/img/2026-04-05_manifest.md`, 2026.

---

## 附录 A 当前证据审计结论

### A.1 当前足够支撑正文的材料

1. 系统架构与模块设计。
2. 全量测试、环境检查与 API 直连结果。
3. short smoke 正向 real-AI 证据。
4. `Phase 2` 修复前后 batch 对比。
5. `Phase 3` 的 route1 与 battle guidance 改进链。
6. 长程 resilience 证据。

### A.2 当前只能支撑“部分正面结论”的材料

1. repeated batch 的部分恢复；
2. `Route 1` 到达；
3. 首个战斗菜单正确选择；
4. provider 故障下的恢复表现。

### A.3 当前不能强写的结论

1. 稳定 `got_pokedex`；
2. 稳定 `oak_got_parcel`；
3. 稳定中程剧情推进；
4. 低方差高成功率 repeated batch；
5. 顶刊级完整实证包。

---

## 附录 B 图表与实验占位符清单

以下占位符建议直接保留到论文正式版中，定稿前若仍缺失，则必须在答辩稿和论文中说明未完成原因，而不能伪造数据。

### [占位图 B-1] 论文版系统总体架构图

- 来源基础：`docs/2026-04-05_system_architecture_diagram.md`
- 当前状态：已有 Mermaid 草图，缺正式导出图片
- 要求：统一排版、英文标签或中英对照标签、矢量导出

### [占位图 B-2] 决策子系统与控制权路由图

- 目标：明确展示 deterministic stages 与 AI fallback 的关系
- 当前状态：已有 Mermaid 草图，缺论文风格渲染

### [占位图 B-3] Route 1 战斗决策链放大图

- 建议内容：`进入战斗 -> 四选一菜单 -> 选择 FIGHT -> 打开 move list -> 选择 Scratch`
- 当前状态：原始截图与 contact sheet 已有，缺 4x/6x 放大标注版

### [占位图 B-4] Oak Lab / Pallet / Route 1 关键节点放大图

- 当前状态：现有 `fig03`、`fig04`、`fig05` 分辨率过低
- 要求：最近邻放大、箭头标出角色位置、标出目标路径/阻挡关系

### [占位表 B-1] 模式消融实验表

- 维度：
  - `llm_primary` 开/关
  - `ai_full_control` 开/关
  - `story guidance` 开/关
  - `battle guidance` 开/关
- 当前状态：仓库中尚无完整正式表

### [占位表 B-2] 成本与延迟统计表

- 指标：
  - 平均延迟
  - 最大延迟
  - provider error 次数
  - fallback 比例
  - 平均 AI ownership
- 当前状态：原始字段已有，缺汇总表

### [占位表 B-3] 人类/启发式基线对比表

- 建议至少比较：
  - `Route 1`
  - `Viridian City`
  - `Oak's Parcel`
  - 步数/回合数
- 当前状态：缺失

### [占位图 B-5] 失败案例 taxonomy 图

- 分类建议：
  - provider failure
  - transport failure
  - Oak Lab local loop
  - battle intro stall
  - post-battle continuation stall
- 当前状态：文档已有文字分析，缺正式图

