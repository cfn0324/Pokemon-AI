# Pokemon AI Agent 阶段记录

## 记录信息

- 记录日期：2026-03-31
- 项目目录：`D:\bysj\p-ai`
- 阶段主题：LLM 主决策运行时改造与 Oak Lab 实机验证
- 本阶段目标：尽可能减少工具侧固定兜底，让大模型承担多数回合决策，并验证这种模式在《Pokemon Red》开场阶段的可行性

## 阶段摘要（可直接写入论文）

本阶段工作的核心目标，是把系统从“工具优先、模型补充”调整为“模型优先、工具仅保留最小安全保护”的运行方式。与此前依赖固定导航、固定剧情推进和自动对话工具的方案相比，本阶段更强调让多模态大模型直接根据截图、RAM 状态和导航记忆做逐回合决策，从而验证大模型在长时序游戏控制中的真实能力边界。

实现结果表明，系统已经可以稳定进入 LLM 主决策模式，且在实机 smoke test 中，大多数回合确实由 AI 决定，而不是由预设工具链抢先执行。以 `milestone_oaks_lab` 检查点为例，60 个测试回合全部来自 AI 决策；以 `milestone_first_pokemon` 检查点为例，最终版 20 回合测试中有 18 个回合来自 AI，仅有 2 个回合由最小 UI 安全层处理启动过渡。这说明系统在运行时层面已经完成了从“脚本主导”到“模型主导”的关键切换。

但实验同样表明，当前瓶颈已经不再是 API 连通性或固定路线脚本，而是大模型在 Oak Lab 场景下对“NPC 阻挡、剧情触发锁、可通行方向、昵称界面确认流程”的理解仍然不够稳定。也就是说，本阶段成功把系统问题从“工程路由抢决策”前移到了“模型本身能否在复杂局部场景中做出正确行动”这一更具有研究价值的层面。

## 阶段背景

在此前版本中，系统虽然能够推进部分开场流程，但运行时存在两个明显问题：

- 问题一：大量固定控制阶段会在模型之前抢先做决定，例如自动导航、固定剧情控制器、自动对话推进等，导致看起来像“AI 在玩”，但实际上很多关键步骤由规则直接完成。
- 问题二：一旦关闭这些规则，模型又容易在 Oak Lab、剧情切换、命名界面等局部场景中走入死循环，因此难以判断瓶颈究竟来自模型能力不足，还是来自工程层对模型的过度替代。

因此，本阶段的研究重点不是继续堆叠更长的规则脚本，而是先构造一个“LLM 优先但不完全裸奔”的运行模式，让系统只保留最小限度的 UI 安全保护，把普通移动、剧情推进和局部探索尽可能交还给模型。

## 本阶段的主要代码改动

### 1. 新增 LLM 主决策模式

本阶段在 `decision` 配置段中新增并启用了：

- `decision.llm_primary_mode: true`

对应实现位于：

- `main.py`
- `config.yaml`

该模式的设计目标不是完全关闭所有控制层，而是在保持系统仍可运行的前提下，尽可能让 AI 负责普通回合决策。

### 2. 收缩控制层阶段，只保留最小安全保护

在 `LLM-primary` 模式下，控制层阶段被裁剪为仅保留以下几类：

- `bootstrap`
- `minimal_known_ui`
- `stable_ui_recovery`
- `menu_auto_close`
- `text_entry_api_cooldown`

被移除出优先链的主要阶段包括：

- `navigation_plan`
- `dialogue_timing`
- `dialogue_auto_advance`
- `early_story_interaction`
- `pre_starter_recovery`
- Oak Lab 固定路线控制器

这意味着普通移动、房间探索和大多数剧情推进都不再由工具层先行决定，而是直接交给主模型。

### 3. 同步等待模型并启用同回合重试

为了避免异步占位 `wait` 抢掉模型回合，本阶段将 `LLM-primary` 模式纳入“LLM 驱动运行时”的统一逻辑中：

- 直接同步调用主模型
- API 暂时失败时，允许同一观测上进行重试
- 不把网络抖动直接转化为游戏内无意义等待

这部分改动主要位于：

- `main.py`
- `src/agents/main_agent.py`

### 4. 执行层改为单次按键

此前方向键执行可能被扩展为多次按压，以提高移动成功率。但在 LLM 主决策模式下，这会污染模型的动作反馈，因为模型只想“试一步”，执行层却可能替它多走几步。

因此本阶段把 `LLM-primary` 模式也纳入单次按键执行逻辑：

- 模型输出一个方向
- 执行层只按一次该方向
- 让下一回合观测真实反映该单步动作的结果

对应文件：

- `src/tools/action_executor.py`

### 5. 缩减 AI 不可用时的兜底策略

本阶段没有彻底取消 AI 失效后的安全处理，但显著收缩了其作用范围。在 `LLM-primary` 模式下，AI 请求失败后不再调用完整导航兜底、局部探索兜底和早期剧情恢复兜底，而是只保留极少数安全处理。

这样做的目的，是避免系统在“表面上启用大模型”时，实际上又被工具层接管。

### 6. 修正 Oak Lab 命名界面控制逻辑

本阶段围绕 `naming_screen` 做了两轮修正：

- 第一轮：修正 Oak Lab 真实命名界面被误判为 `dialogue` 的问题
- 第二轮：撤销错误的 `B` 键自动兜底，因为测试证明该兜底会在命名场景中反复空转

最终策略是：

- `LLM-primary` 模式下，不再让最小安全层直接接管命名流程
- 让模型自行处理 `YES/NO` 选择以及命名确认
- 仅保留 `startup` 类过渡界面的安全等待

### 7. 强化提示词中的 Oak Lab 约束

为了避免模型在 Oak Lab 中反复把“剧情锁定场景”误判为“自由探索场景”，本阶段补充了提示约束，强调：

- 被剧情弹回时，应理解为 Oak 触发而不是可探索失败
- Oak 或 rival 附近多方向连续失败时，应优先视为 NPC 或剧情阻挡
- 导航记忆中的 `blocked_directions` 比单帧视觉直觉更可靠

对应文件：

- `src/agents/main_agent.py`

## 实验设置

### 模型与接口

- 主模型：`gpt-5.4`
- 接口形式：兼容 OpenAI `/chat/completions` 风格的代理接口
- 本地已验证 API 可用

### 关键运行配置

- `decision.llm_primary_mode = true`
- `decision.pure_llm_mode = false`
- `performance.async_decisions = false`（smoke test 中显式关闭）
- `ai.decision_max_tokens = 1200`
- `ai.request_timeout_seconds = 120`（默认配置）

### 主要验证方式

- 单元测试
- 基于检查点的 headless smoke test

本阶段重点使用了以下 smoke 报告：

- `tmp/autonomous_smoke_oaks_lab_llm_primary.json`
- `tmp/autonomous_smoke_first_pokemon_llm_primary.json`
- `tmp/autonomous_smoke_first_pokemon_llm_primary_v5.json`

## 实验结果

### 1. 单元测试结果

本阶段新增和修正了以下测试方向：

- `LLM-primary` 模式是否强制走同步主模型路径
- `LLM-primary` 模式下动作执行是否为单次按键
- `LLM-primary` 模式下是否启用同回合重试
- `LLM-primary` 模式下的阶段裁剪是否正确
- Oak Lab `naming_screen` 识别逻辑是否正确

最终结果：

- `38` 项测试全部通过

### 2. Oak Lab 初始检查点测试

测试命令对应报告：

- `tmp/autonomous_smoke_oaks_lab_llm_primary.json`

结果如下：

- 测试回合数：60
- `decision_source_counts = {"ai": 60}`
- `decision_path_counts = {"ai": 60}`
- 最终位置：`map_id = 40, x = 1, y = 4`
- 测试窗口内唯一位置数：4
- 实际发生“position changed”的有效推进回合数：0

结论：

- 运行时层面已经实现“全 AI 决策”
- 但模型仍在 Oak Lab 局部区域内来回试探，没有形成有效剧情推进

### 3. 已获得首只宝可梦检查点测试

测试命令对应报告：

- `tmp/autonomous_smoke_first_pokemon_llm_primary.json`

结果如下：

- 测试回合数：40
- `decision_source_counts = {"ai": 38, "minimal_known_ui": 2}`
- 最终位置：`map_id = 40, x = 5, y = 3`
- 对话相关回合：21
- 工具层干预回合：2
- 测试窗口内唯一位置数：1

结论：

- 模型能处理大部分对话和昵称相关流程
- 但离开 Oak Lab 的阶段仍然完全没有位置推进
- 这说明核心问题已经集中在 Oak、rival 与桌面布局附近的局部行动判断

### 4. 最终短程验证结果

最终版本的短程验证报告：

- `tmp/autonomous_smoke_first_pokemon_llm_primary_v5.json`

结果如下：

- 测试回合数：20
- `decision_source_counts = {"ai": 18, "minimal_known_ui": 2}`
- 模型成功使用 `start` 跳过命名输入，而不是反复输入字符
- `minimal_known_ui` 仅用于 `startup` 过渡等待
- 最终仍停留在 `map_id = 40, x = 5, y = 3`
- 当前 tile 的 `blocked_directions` 最终记录为 `["down", "left", "right"]`

这一结果说明：

- 命名场景的错误兜底已经被消除
- 模型比之前更可靠地完成了“不给昵称并继续流程”
- 但拿到 Charmander 之后，模型仍然无法在 Oak Lab 的脚本锁定场景中走出有效一步

## 本阶段的核心结论

### 结论一：运行时主导权已经切换到大模型

从多个 smoke report 可以明确看出，本阶段已经把系统从“工具主导”切换到了“模型主导”。这不是抽象上的配置变化，而是可以通过 `decision_source_counts` 和 `decision_path_counts` 直接验证的工程结果。

### 结论二：当前瓶颈已经从工程兜底转移为模型决策质量

本阶段最重要的研究价值，不是“让系统立刻打通开局全部流程”，而是明确了当前失败的原因已经不再主要来自脚本控制链、异步占位、API 连通性或错误兜底，而是模型在局部受限场景中的状态理解不足。

换言之，系统已经成功把问题暴露为一个更纯粹的 Agent 决策问题。

### 结论三：Oak Lab 是当前最关键的研究场景

Oak Lab 同时包含以下困难因素：

- NPC 阻挡
- 剧情触发锁
- 局部地形狭窄
- 截图可见空间有限
- RAM 与视觉状态存在短暂错位
- 命名界面和过渡界面混杂

因此，Oak Lab 既是当前失败点，也是论文中最有价值的典型分析场景。

## 当前存在的问题

### 1. 模型对剧情锁和 NPC 阻挡的理解仍不足

虽然提示词已经强化了“多方向失败时应怀疑剧情阻挡”，但从最终 smoke 结果看，模型仍倾向于继续把 Oak Lab 当作普通可探索房间，而不是把 Oak 或 rival 识别为当前的交互焦点。

### 2. 单帧视觉判断仍会覆盖已有导航记忆

即使状态中已经给出 `blocked_directions`，模型有时仍会根据截图中的“看起来像能走”做出错误判断。这说明当前状态表达还不够强，导航记忆在提示中的优先级仍不足以完全压过视觉直觉。

### 3. Oak Lab 缺少结构化的局部环境描述

当前系统能给出：

- 位置
- blocked directions
- frontier
- exploration percent

但还缺少对“玩家四邻格是否被 NPC / 桌子 / 墙体占用”的直接结构化描述。这使得模型只能凭截图推断，而 Oak Lab 恰好是截图推断最容易出错的场景之一。

## 对论文写作有用的表述建议

可以把本阶段的结论概括为：

> 本阶段通过引入 `LLM-primary` 运行时模式，将游戏控制主导权从工具链迁移至多模态大模型，仅保留启动过渡、菜单关闭和极少数死锁保护作为最小安全层。实验结果表明，系统已经能够在多数回合中由大模型直接给出动作决策，说明运行时路由层面的“伪智能”问题得到了显著削弱。然而，在 Oak Lab 等高度受限的剧情锁定场景中，大模型仍然难以稳定识别 NPC 阻挡、局部不可通行方向和剧情交互触发条件，导致系统虽已实现 LLM 主决策，却尚未在关键开局场景中形成可靠推进。这表明当前瓶颈已从工程层兜底逻辑转移为模型在局部复杂状态下的决策质量问题。 

## 下一阶段建议

- 在状态文本中增加玩家四邻格的结构化占用信息，而不是只给截图和 blocked directions
- 针对 Oak Lab 增加“NPC 阻挡 / 剧情锁定”专门状态标记，但避免扩展成长脚本
- 继续保留 `LLM-primary`，不要回退到大段固定路线控制器
- 将 Oak Lab 作为后续论文中的重点失败案例与改进案例
- 对比“工具优先”和“LLM 优先”两种模式下的 `decision_source_counts`、推进距离和剧情完成度，形成消融实验

## 可直接引用的实验材料

- `tmp/autonomous_smoke_oaks_lab_llm_primary.json`
- `tmp/autonomous_smoke_first_pokemon_llm_primary.json`
- `tmp/autonomous_smoke_first_pokemon_llm_primary_v5.json`
- `tests/test_runtime_safeguards.py`
- `tests/test_async_runtime.py`
- `tests/test_action_executor.py`
- `tests/test_same_turn_retry.py`
- `main.py`
- `src/agents/main_agent.py`
- `src/tools/action_executor.py`
- `config.yaml`
