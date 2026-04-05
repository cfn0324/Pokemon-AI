# 2026-04-05 毕业设计总报告

## 1. 报告目的

本报告的目标不是简单汇报“项目能跑”，而是把以下内容整理成一份可直接支撑毕业设计写作、答辩和附录归档的总材料：

- 本次实际复验中我亲自执行的命令、结果和结论。
- 仓库 `docs/` 与 `docs/thesis_logs/` 中已经形成的正式实验口径。
- 原始 JSON 报告、批量实验汇总、截图证据、可直接引用的论文结论边界。

本报告最终结论是：

- 如果论文题目定位为“基于大模型、RAM 读取、可选视觉分析与地图记忆的 Pokemon Red 早期剧情自主智能体设计与实现”，本项目截至 **2026-04-05** 已经具备完整工程系统、可复现实验路径、真实 AI 接入能力、短程 AI 主导证据和长程韧性证据，**足以支撑整篇本科毕业设计/毕业论文**。
- 如果论文结论试图写成“系统已经稳定自主完整通关”或“真实 AI 已能稳定完成中长程关键剧情推进”，**当前证据不足**，不应这样表述。

## 2. 本报告使用的依据

### 2.1 代码与配置

- `README.md`
- `config.yaml`
- `main.py`
- `scripts/autonomous_smoke.py`
- `scripts/autonomous_smoke_batch.py`
- `scripts/smoke_report_summary.py`

### 2.2 仓库内正式文档

- `docs/evaluation_workflow.md`
- `docs/2026-04-05_project_readiness_assessment.md`
- `docs/2026-04-05_phase2_real_ai_batch_assessment.md`
- `docs/2026-04-05_phase3_runtime_field_recovery_assessment.md`
- `docs/2026-04-05_phase3_story_guidance_assessment.md`
- `docs/2026-04-05_phase3_battle_guidance_assessment.md`
- `docs/2026-04-05_high_quality_graduation_design_backlog.md`
- `docs/2026-04-05_thesis_evidence_index.md`

### 2.3 本次复验环境

- 日期：`2026-04-05`
- 工作目录：`D:\bysj\p-ai`
- Shell：`PowerShell`
- Python：`3.13.5`
- 当前仓库提交：`7b48bbb`
- 实际模型端点：`https://api.ququ233.com/v1`
- 实际模型：`gpt-5.4`

## 3. 项目概述与论文定位

根据 `README.md` 与代码结构，本项目是一个面向 Pokemon Red 的长时运行自主智能体系统，核心特点如下：

- 通过 `PyBoy` 驱动 `PokemonRed.gb`。
- 通过 `RAM` 读取位置、队伍、战斗状态、事件进度等关键信息。
- 支持屏幕截图与可选视觉分析，但当前主链路强调 RAM 与运行时状态文本。
- 使用主智能体进行逐回合动作决策，并辅以寻路、谜题、评论等辅助智能体。
- 具备长期记忆、上下文摘要、地图记忆、检查点恢复、日志记录与 Web 仪表盘。
- 已形成标准化短程 smoke 评估脚本、批量实验脚本和实验汇总脚本。

从论文表达角度，最稳妥的研究问题不是“能否全自动通关整部游戏”，而是：

1. 能否设计并实现一个完整可运行的多模块游戏智能体系统。
2. 能否在真实模型条件下，让 AI 主导早期剧情中的多数决策。
3. 当真实 AI 无法稳定推进时，问题主要来自运行时恢复、模型局部理解，还是外部服务稳定性。

## 4. 系统结构与论文可写模块

下表可直接转化为论文“系统设计”章节的模块说明。

| 模块层 | 关键文件 | 主要职责 | 论文可写点 |
| --- | --- | --- | --- |
| 模拟器层 | `src/emulator/game_boy.py` | 启动模拟器、按键执行、截图、存档恢复 | 游戏环境接入方式 |
| 内存与状态层 | `src/emulator/memory_reader.py`、`src/state/game_state.py`、`src/state/map_memory.py` | 读取 RAM、维护统一状态表示、生成地图探索信息 | 状态建模、特征工程 |
| 视觉层 | `src/state/vision.py` | 文本框、菜单、战斗、地形等像素级分析 | 多模态输入与视觉补充 |
| 决策层 | `src/agents/main_agent.py`、`src/agents/pathfinder.py`、`src/agents/puzzle_solver.py`、`src/agents/critic.py`、`src/agents/async_decision.py` | 主决策、辅助推理、异步请求模型 | 主智能体与工具层协作 |
| 记忆与目标层 | `src/memory/context_manager.py`、`src/memory/summarizer.py`、`src/tools/goal_manager.py` | 上下文压缩、长期目标、短期目标 | 长时任务代理设计 |
| 执行与观察层 | `src/tools/action_executor.py`、`src/tools/progress_tracker.py`、`src/visualization/visualizer.py` | 动作执行、进度跟踪、事件流、Web 可视化 | 闭环控制与可观测性 |
| 评估层 | `scripts/autonomous_smoke.py`、`scripts/autonomous_smoke_batch.py`、`scripts/smoke_report_summary.py` | 单次复验、重复实验、论文风格汇总 | 可复现性与实验治理 |

## 5. 本次实际执行的复验工作

本次没有直接长时间人工运行 `python main.py` 做开放式演示，而是遵循 `docs/evaluation_workflow.md` 推荐的、**更适合论文取证的可复现路径**：

```powershell
pytest -q
python test_setup.py
python test_custom_api.py
python scripts/autonomous_smoke.py `
  --checkpoint checkpoint_195913 `
  --turns 120 `
  --llm-primary `
  --ai-full-control `
  --reset-context `
  --decision-max-tokens 384 `
  --action-plan-max-actions 3 `
  --output tmp/2026-04-05_codex_fresh_real_ai_smoke_120.json
```

### 5.1 自动化测试

最终有效结果：

- `pytest -q`
- 结果：`299 passed, 1 warning`

说明：

- 第一次在沙箱内执行时，`pytest` 的一个用例因为 Windows 临时目录权限被限制而失败。
- 该失败不是业务逻辑断言失败，而是 `tempfile.TemporaryDirectory()` 在当前沙箱权限模型下无法写入临时子目录。
- 将命令放到沙箱外复跑后，全量测试通过，说明**项目真实代码状态是通过的**。

### 5.2 环境与 API 检查

实际结果：

- `python test_setup.py`：`7/7` 通过
- `python test_custom_api.py`：返回 `API connection successful!`
- 模型：`gpt-5.4`
- 端点：`https://api.ququ233.com/v1`

这证明：

- 本仓库不是只停留在“离线结构正确”。
- 当前环境确实具备真实 API、真实模型、真实 ROM 的运行条件。

### 5.3 本次 fresh smoke 复验

实际执行文件：

- `tmp/2026-04-05_codex_fresh_real_ai_smoke_120.json`

协议：

- checkpoint：`checkpoint_195913`
- turns：`120`
- 模式：`llm_primary_mode = true`
- 控制权：`ai_full_control_mode = true`
- 参数：`--reset-context --decision-max-tokens 384 --action-plan-max-actions 3`

结果摘要：

- `completed_requested_turns = true`
- `fatal_error = null`
- `timeline_valid = true`
- `ai_authored_ratio = 0.025`
- `main_model_ratio = 0.025`
- `fallback_turns = 97`
- `best_story_progress = entered_oaks_lab`
- 最终位置：`map 40, (9,11)`

这次 run 的价值不是“正向成功”，而是**复现了真实 provider 稳定性问题**：

- 开局即出现 `status 500: 没有可用 token`
- 之后大量 turn 被 `wait_rewrite_ai_cooldown` 与 `api_unavailable_field_interaction` 吞掉
- AI 仅真正主导了 `3` 个 turn

因此，这次 fresh run 应作为论文中的**失败案例与外部依赖分析**使用，而不是作为正向能力主证据。

## 6. 可直接用于论文的工程有效性结论

### 6.1 工程完整性

当前项目已经具备完整闭环：

- 模拟器驱动
- RAM 状态读取
- 地图记忆
- AI 决策链
- 动作执行
- 进度记录
- 可视化仪表盘
- 检查点恢复
- smoke 实验与批量评估

这已经明显超出“课程作业级 demo”，达到了本科毕设应有的系统规模。

### 6.2 工程稳定性

由本次复验与既有文档共同支持的稳定性结论：

- 全量单元测试 `299 passed, 1 warning`
- 环境检查 `7/7` 通过
- API 可真实连接
- 长程 smoke 可完成 `1800/2600/4000` turn
- 多份报告满足 `fatal_error = null` 与 `timeline_valid = true`

因此，论文中可以安全写出：

- “系统已经具备完整运行能力和较高工程稳定性。”
- “系统支持检查点恢复、长程运行和标准化实验复现。”

## 7. 实验证据总表

### 7.1 工程与入口验证

| 证据 | 文件或命令 | 结果 | 可支撑结论 |
| --- | --- | --- | --- |
| 全量单元测试 | `pytest -q` | `299 passed, 1 warning` | 代码级回归稳定 |
| 环境检查 | `python test_setup.py` | `7/7` 通过 | Python、依赖、ROM、配置、目录、API 均正常 |
| API 单独检查 | `python test_custom_api.py` | `API connection successful!` | 真实端点与模型可用 |
| 当前 fresh smoke | `tmp/2026-04-05_codex_fresh_real_ai_smoke_120.json` | 完成 120 turn，但受 provider token 问题干扰 | 外部服务稳定性会直接影响 AI 占比 |

### 7.2 正向 Real-AI 证据

| 证据文件 | turns | AI authored | Main model | Fallback | 关键里程碑 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `tmp/2026-04-05_real_ai_smoke_120.json` | 120 | 76.67% | 70.83% | 0 | `entered_oaks_lab` | 真实 AI 已能主导大多数早期回合 |
| `tmp/phase3_field_recovery_probe.json` | 120 | 70.00% | 60.83% | 0 | 未到 Route 1 | 运行时恢复问题已明显改善 |
| `tmp/phase3_story_guidance_probe.json` | 120 | 89.17% | 75.00% | 0 | `reached_route1 = true` | 引导信息增强后已能冲出 Pallet Town 到达 Route 1 |
| `tmp/phase3_battle_guidance_probe_shortcooldown.json` | 120 | 84.17% | 70.83% | 0 | `reached_route1 = true`，最终在 battle | AI 不仅到达 Route 1，还做出了首个正确战斗菜单决策 |
| `tmp/real_ai_batches/2026-04-05_phase2_retryfix_probe/..._run01.json` | 120 | 84.17% | 70.83% | 0 | Route 1 | transport 分类修复后可恢复高 AI 占比 |

### 7.3 重复实验与方差证据

| 批次 | 运行数 | 完成数 | AI-dominant | 平均 AI authored | 平均 main model | 主要结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2026-04-05_phase2_real_ai_baseline` | 3 | 3 | 0 | 1.94% | 1.67% | 修复前，真实 AI 证据几乎被 provider/transport 问题吞没 |
| `2026-04-05_phase2_real_ai_baseline_retryfix` | 3 | 3 | 1 | 30.00% | 27.78% | 修复后 AI 占比明显回升，但方差仍较大 |

### 7.4 长程韧性证据

| 证据文件 | turns | fatal error | timeline valid | 里程碑 | AI 占比 | 结论 |
| --- | ---: | --- | --- | --- | --- | --- |
| `tmp/codex_smoke_1800_20260405_after_blackout_resume_fix.json` | 1800 | 无 | 是 | `Pokedex / Route2 / Forest` | 近似 0 | 证明系统能长期运行，但不证明 AI 主导 |
| `tmp/codex_smoke_2600_20260405_after_dialogue_recovery_fix.json` | 2600 | 无 | 是 | `Pokedex / Route2 / Forest` | 近似 0 | 证明恢复与长程韧性 |
| `tmp/codex_smoke_4000_20260405_long_validation.json` | 4000 | 无 | 是 | `Pokedex / Route2 / Forest` | 近似 0 | 证明系统可持续运行到更长时间 |

说明：

- 这些长程报告的汇总显示 `Avg AI-authored ratio = 0.0022`、`Avg main-model ratio = 0.0`。
- 因此它们应被归类为 **resilience evidence**，不能在论文中误写成“真实 AI 已稳定主导长程剧情”。
- 旧长程报告里 `reached_route1 = 0` 并不代表没有经过 Route 1，而是说明旧报告口径未统一记录该字段；由于它们已经达到 `Route2 / Viridian Forest`，路径上必然早已经过 Route 1。

## 8. 关键实验链条解释

### 8.1 Phase 2：从“批量实验缺失”到“批量实验已建立”

`docs/2026-04-05_phase2_real_ai_batch_assessment.md` 与对应 batch 文件表明：

- 统一协议 batch 已经建立。
- 修复前：
  - `3/3` 完成
  - `0/3` AI-dominant
  - `avg_ai_authored_ratio = 0.0194`
- 修复后：
  - `3/3` 完成
  - `1/3` AI-dominant
  - `avg_ai_authored_ratio = 0.3000`

这证明一件很重要的事：

- 早期低 AI 占比并不全是“模型不会玩”，其中相当一部分是 transport/provider 异常被错误放大。

### 8.2 Phase 3：从恢复质量到故事引导，再到战斗决策

`Phase 3` 三份文档展示了一条非常适合论文叙述的递进链：

1. `phase3_field_recovery_probe`
   - `ai_authored_ratio = 0.7000`
   - `fallback_turns = 0`
   - 说明运行时恢复逻辑不再轻易塌缩成长时间 fallback。
2. `phase3_story_guidance_probe`
   - `ai_authored_ratio = 0.8917`
   - `reached_route1 = true`
   - 说明故事引导信息增强后，AI 已能主动穿过 Pallet Town 北出口。
3. `phase3_battle_guidance_probe_shortcooldown`
   - `ai_authored_ratio = 0.8417`
   - `reached_route1 = true`
   - `fallback_turns = 0`
   - 说明 AI 在 Route 1 不只是“到达后卡住”，而是开始做正确战斗选择。

### 8.3 Route 1 战斗决策的直接证据

在 `tmp/phase3_battle_guidance_probe_shortcooldown.json` 中，关键时间线如下：

- `turn 196025`
  - AI 判断画面是标准 battle command menu
  - 明确选择 `FIGHT`
- `turn 196026`
  - AI 判断 move list 已打开
  - 明确选择 `Scratch`

这组证据可以直接支撑论文中的一句关键结论：

> 在 `ai_full_control_mode = true` 条件下，系统已经能够在真实模型环境中完成 Route 1 第一场野战的首个正确战斗菜单决策，而不是依赖隐藏脚本接管。

## 9. 本次 fresh run 的失败价值

这次我亲自补跑的 `tmp/2026-04-05_codex_fresh_real_ai_smoke_120.json` 虽然不是正向样本，但对于毕业论文反而非常重要，因为它提供了**当前系统最真实的失败案例之一**：

- 相同 checkpoint
- 相同 turns
- 相同模型
- 相同 `llm-primary + ai-full-control` 协议

但结果从正向样本的 `76.67%` AI 占比，跌到了 `2.5%`。

原因不是代码崩溃，也不是 timeline 异常，而是外部 provider 反复返回：

- `status 500`
- `没有可用 token`

从时间线上可以清晰看到：

- `195914` 和 `195928` 就已出现 AI request error
- 随后大量 turn 进入 `wait_rewrite_ai_cooldown`
- 最终 `97` 个 turn 被 `api_unavailable_field_interaction` 吞掉

这段失败案例可以直接写进论文“局限性与误差来源”章节，说明：

1. 真实 AI 实验不仅受模型能力影响，也受服务端资源可用性影响。
2. 当 provider 不稳定时，系统会退化到 fallback 驱动而不是直接崩溃。
3. 因此论文中必须区分“决策质量问题”和“服务可用性问题”。

## 10. 截图证据

说明：

- 下列截图均已集中复制到 `docs/report_assets/2026-04-05/`。
- 其中 dashboard 预览图来自仓库现有界面资产；headless smoke 模式默认关闭 live dashboard，因此本次实验主链使用 smoke 报告取证、用现有 dashboard 预览图补充界面证据。

### 图 1. Web 仪表盘桌面端总览

![图1 Web 仪表盘桌面端总览](report_assets/2026-04-05/dashboard_preview.png)

用途：

- 证明项目具备可视化控制台、目标区域、事件流、运行控制、决策展示等前端界面。

### 图 2. Web 仪表盘移动端预览

![图2 Web 仪表盘移动端预览](report_assets/2026-04-05/dashboard_preview_mobile.png)

用途：

- 证明可视化页面不仅是桌面单端布局，也考虑了移动端适配。

### 图 3. 大木研究所阶段截图

![图3 大木研究所阶段截图](report_assets/2026-04-05/milestone_oaks_lab.png)

用途：

- 对应早期关键剧情阶段，可作为 Oak Lab 局部决策问题与里程碑截图证据。

### 图 4. Route 1 场景截图

![图4 Route 1 场景截图](report_assets/2026-04-05/route1_top_probe.png)

用途：

- 对应 `Phase 3` 中“从 Pallet Town 成功推进到 Route 1”的正向证据。

### 图 5. Route 1 战斗/交互前画面

![图5 Route 1 战斗前画面](report_assets/2026-04-05/battle_debug_196989.png)

用途：

- 对应 battle guidance 相关实验，可作为 AI 即将进入首个野战场景的截图。

### 图 6. 地图探索与局部导航截图

![图6 地图探索与局部导航截图](report_assets/2026-04-05/turn_196650.png)

用途：

- 反映运行时保存的局部地图/探索状态，可配合论文解释地图记忆、前沿探索与局部路径选择。

### 图 7. Route 2 全局地图记忆示意图

![图7 Route 2 全局地图记忆示意图](report_assets/2026-04-05/route2_full_map_grid.png)

用途：

- 证明系统不是简单按键脚本，而是已经维护了较大范围的地图探索与路径信息。

## 11. 论文中可以直接写的结论

以下结论目前证据充分，可以安全写入论文正文：

1. 系统已经实现了从模拟器接入、状态读取、AI 决策、动作执行、进度追踪到可视化与检查点恢复的完整技术闭环。
2. 截至 `2026-04-05`，系统在真实 API 与真实模型条件下可正常运行，环境检查与接口检查通过。
3. 全量自动化测试通过，说明近期工程改动没有破坏整体代码稳定性。
4. 在 `llm-primary + ai-full-control` 条件下，系统已产生多份真实 AI 主导短程运行证据，AI authored ratio 可达到 `70%` 到 `89%`。
5. 通过 `Phase 3` 的状态文本增强，系统已经从“只在 Oak Lab 内局部试探”推进到“到达 Route 1 并做出首个正确战斗菜单决策”。
6. 系统具备长程韧性，即使在 AI 占比很低时，也能依靠恢复机制与保护逻辑长时间持续运行，并推进到 `Pokedex / Route2 / Viridian Forest`。
7. 外部 provider 的 token 可用性会显著影响真实 AI 实验结果，因此论文必须单独分析服务稳定性对 AI 占比的影响。

## 12. 当前不要写进论文的结论

以下说法当前证据不够，建议不要写：

1. “系统已经稳定自主通关 Pokemon Red。”
2. “真实 AI 已能稳定完成中长程关键剧情推进。”
3. “在重复实验下，真实 AI 已稳定取得 `got_pokedex`、`oak_got_parcel` 或更高剧情里程碑。”
4. “外部服务波动对实验结果影响很小。”

## 13. 这份报告如何支撑整篇毕业论文

### 13.1 可以支撑的论文结构

如果论文题目边界控制得当，这份报告已经足以支撑完整写作：

- 第 1 章 绪论
  - 说明研究问题：大模型游戏智能体、长时任务、早期剧情推进难点。
- 第 2 章 相关技术
  - 说明 PyBoy、RAM 读取、视觉分析、LLM `/messages` 接口、长上下文与地图记忆。
- 第 3 章 系统设计与实现
  - 直接使用本报告第 4 节的模块表。
- 第 4 章 实验设计与结果分析
  - 直接使用本报告第 7 节、第 8 节、第 9 节和截图证据。
- 第 5 章 总结与展望
  - 写“早期剧情可行性验证已经成立，但 Oak Lab 局部决策质量、重复实验方差、服务稳定性仍需继续优化”。

### 13.2 最适合的论文题目方向

建议题目不要写得过大，以下方向最稳妥：

- 基于大模型与 RAM/视觉融合状态的 Pokemon Red 自主智能体设计与实现
- 面向早期剧情推进的 Pokemon Red 多模态 AI Agent 系统研究
- 结合地图记忆、检查点恢复与大模型决策的游戏智能体框架设计

## 14. 若想把论文做成“高质量版本”，还应补哪些实验

按优先级排序，建议继续补：

1. `P0`：再做 `3-5` 组统一协议 real-AI 重复实验，争取至少一组稳定达到 `got_pokedex` 或 `oak_got_parcel`。
2. `P0`：补一张正式消融表，例如：
   - `llm_primary=false` vs `true`
   - `ai_full_control=false` vs `true`
   - 有/无 story guidance
   - 有/无 battle guidance
3. `P1`：补一张延迟/成功率/AI 占比统计表。
4. `P1`：补一张论文版系统结构图与数据流图。
5. `P1`：清理旧实验资产，只保留最可信的正式证据集。

这些工作会显著提高“优秀毕业设计”的说服力，但**并不影响当前项目已经具备完成本科毕业设计写作的基础**。

## 15. 原始证据索引

### 15.1 本次直接复验产物

- `tmp/2026-04-05_codex_fresh_real_ai_smoke_120.json`
- `docs/thesis_logs/2026-04-05_fresh_real_ai_smoke_summary.md`

### 15.2 工程与入口

- `README.md`
- `config.yaml`
- `docs/evaluation_workflow.md`

### 15.3 正向 Real-AI 证据

- `tmp/2026-04-05_real_ai_smoke_120.json`
- `tmp/phase3_field_recovery_probe.json`
- `tmp/phase3_story_guidance_probe.json`
- `tmp/phase3_battle_guidance_probe_shortcooldown.json`
- `docs/thesis_logs/2026-04-05_phase2_retryfix_probe.md`
- `docs/thesis_logs/2026-04-05_phase3_field_recovery_probe.md`
- `docs/thesis_logs/2026-04-05_phase3_story_guidance_probe.md`
- `docs/thesis_logs/2026-04-05_phase3_battle_guidance_probe.md`

### 15.4 批量实验与方差证据

- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline/2026-04-05_phase2_real_ai_baseline_summary.json`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline_retryfix/2026-04-05_phase2_real_ai_baseline_retryfix_summary.json`
- `docs/thesis_logs/2026-04-05_phase2_real_ai_baseline.md`
- `docs/thesis_logs/2026-04-05_phase2_real_ai_baseline_retryfix.md`
- `docs/2026-04-05_phase2_real_ai_batch_assessment.md`

### 15.5 长程韧性证据

- `tmp/codex_smoke_1800_20260405_after_blackout_resume_fix.json`
- `tmp/codex_smoke_2600_20260405_after_dialogue_recovery_fix.json`
- `tmp/codex_smoke_4000_20260405_long_validation.json`
- `docs/thesis_logs/latest_smoke_summary.md`
- `docs/thesis_logs/2026-04-05_resilience_recheck_summary.md`

### 15.6 截图证据

- `docs/report_assets/2026-04-05/dashboard_preview.png`
- `docs/report_assets/2026-04-05/dashboard_preview_mobile.png`
- `docs/report_assets/2026-04-05/milestone_oaks_lab.png`
- `docs/report_assets/2026-04-05/route1_top_probe.png`
- `docs/report_assets/2026-04-05/battle_debug_196989.png`
- `docs/report_assets/2026-04-05/turn_196650.png`
- `docs/report_assets/2026-04-05/route2_full_map_grid.png`

## 16. 总结

截至 **2026-04-05**，这套 Pokemon Red AI Agent 项目已经同时具备：

- 完整工程系统
- 可复现实验脚本
- 全量测试通过
- 真实 API 与真实模型接入
- 真实 AI 主导短程证据
- 长程韧性证据
- 失败案例与局限性分析材料
- 可直接进入论文的截图与实验表

因此，只要论文边界控制在“早期剧情阶段的系统设计、可行性验证与瓶颈分析”，这份报告已经足以作为整篇毕业设计的实验与证据主文件。
