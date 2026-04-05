# 2026-04-05 论文证据索引

## 1. 目的

本文档用于把当前项目中与论文相关的关键证据按口径分类，避免写作和答辩时混用。

证据分类原则：

- `A 类`：工程有效性与回归稳定性证据
- `B 类`：resilience evidence，证明系统在 AI 不可用或异常时仍可持续运行
- `C 类`：real-AI evidence，证明 AI 在真实模型条件下参与并主导决策
- `D 类`：论文支持文档与阶段性结论材料

## 2. A 类：工程有效性与稳定性证据

### A1. 全量自动化测试

- 命令：`pytest -q`
- 最近结果：`296 passed, 1 warning`
- 作用：
  - 证明当前仓库的回归测试面稳定
  - 证明最近的脚本与主逻辑修改没有破坏整体运行

### A2. 环境与 API 检查

- 命令：
  - `python test_setup.py`
  - `python test_custom_api.py`
- 最近结果：
  - `test_setup.py`：`7/7` 通过
  - 真实 API 可连接
  - 当前模型可用：`gpt-5.4`

## 3. B 类：Resilience Evidence

这些证据可以用于证明：

- 系统在异常条件下不会轻易崩溃
- 长程自主运行具有恢复能力

但不能直接用于证明：

- AI 在真实模型条件下主导了关键剧情推进

### B1. 长程 resilience smoke

关键文件：

- `tmp/codex_smoke_1800_20260405_after_blackout_resume_fix.json`
- `tmp/codex_smoke_2600_20260405_after_dialogue_recovery_fix.json`
- `tmp/codex_smoke_4000_20260405_long_validation.json`

对应说明：

- `docs/thesis_logs/latest_smoke_summary.md`
- `docs/thesis_logs/2026-04-05_resilience_notes.md`

当前口径判断：

- 这些文件适合支撑“系统具备长程恢复与韧性”
- 不适合直接作为“AI 主导剧情决策成熟”的核心证据

## 4. C 类：Real-AI Evidence

这些证据可以用于证明：

- AI 确实在真实模型条件下参与决策
- AI 在一定范围内取得了主导权

### C1. 单次真实 AI 主导短程 smoke

关键文件：

- `tmp/2026-04-05_real_ai_smoke_120.json`

关键结论：

- `llm_primary_mode = true`
- `ai_full_control_mode = true`
- `ai_authored_ratio = 0.7667`
- `main_model_ratio = 0.7083`
- `ai_dominant = true`
- `fatal_error = null`

当前口径判断：

- 该文件可以证明“真实 AI 已经能够主导短程回合决策”
- 但不能单独证明“真实 AI 已稳定完成中程剧情推进”

### C2. 第一轮固定协议 3 次 batch：发现 transport 分类缺陷

关键文件：

- `docs/thesis_logs/2026-04-05_phase2_real_ai_baseline.md`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline/2026-04-05_phase2_real_ai_baseline_manifest.json`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline/2026-04-05_phase2_real_ai_baseline_summary.json`

关键结论：

- `3/3` 运行完成
- `0/3` AI-dominant
- `avg_ai_authored_ratio = 0.0194`
- 出现大量 `api_unavailable_field_interaction`

意义：

- 这组证据不适合作为“正向 AI 能力证明”
- 但它非常重要，因为它暴露出一个真实工程缺陷：
  - 单次 `ConnectionResetError(10054)` 被误判为长期不可达
  - 导致长时间 AI cooldown
  - 进而让整段实验被 fallback 主导

### C3. Transport 分类修复后的验证证据

关键代码证据：

- `src/agents/main_agent.py`
- `tests/test_main_agent_api_failures.py`

关键验证文件：

- `docs/thesis_logs/2026-04-05_phase2_retryfix_probe.md`
- `tmp/real_ai_batches/2026-04-05_phase2_retryfix_probe/2026-04-05_phase2_retryfix_probe_summary.json`

关键结论：

- 单次 120 turn 复测恢复到高 AI 参与
- `ai_dominant = true`
- `ai_authored_ratio = 0.8417`
- 最终位置到达 `map 12`，说明已走出 Oak Lab 并推进到 Route 1

意义：

- 证明 transport 分类修复是有效的
- 说明前一轮低 AI 占比并不完全来自 Oak Lab 决策本体

### C4. 修复后的第二轮固定协议 3 次 batch

关键文件：

- `docs/thesis_logs/2026-04-05_phase2_real_ai_baseline_retryfix.md`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline_retryfix/2026-04-05_phase2_real_ai_baseline_retryfix_manifest.json`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline_retryfix/2026-04-05_phase2_real_ai_baseline_retryfix_summary.json`

关键结论：

- `3/3` 运行完成
- `1/3` AI-dominant
- `avg_ai_authored_ratio = 0.3000`
- `avg_main_model_ratio = 0.2778`
- 仍未取得 `got_pokedex` / `oak_got_parcel`

当前口径判断：

- 这组证据已经比修复前明显更强
- 可以证明“真实 AI 重复实验能力已经建立，且 transport 问题的确影响了结果”
- 但仍不足以支撑“早期剧情已稳定推进到更强里程碑”的论文结论

### C5. Phase 3 Route 1 战斗决策增强证据

关键文件：

- `docs/2026-04-05_phase3_battle_guidance_assessment.md`
- `docs/thesis_logs/2026-04-05_phase3_battle_guidance_probe.md`
- `tmp/phase3_battle_guidance_probe_shortcooldown.json`

关键结论：

- `reached_route1 = true`
- `fallback_turns = 0`
- `ai_dominant = true`
- `ai_authored_ratio = 0.8417`
- AI 在真实模型条件下明确做出了：
  - `FIGHT`
  - `Scratch`

意义：

- 这组证据比“仅仅到达 Route 1 并停在战斗里”更强
- 它可以证明真实 AI 已经不只是到达战斗场景，而是能在早期野战中做出正确的首个战斗菜单决策
- 但它仍不足以直接证明“Route 1 到 Viridian 的连续推进已稳定完成”

### C6. 当前真实 AI 证据仍然缺少的部分

当前缺口：

- 缺少更高成功率的 Route 1 之后剧情推进
- 缺少稳定拿到 `got_pokedex` 或 `oak_got_parcel` 的 repeated batch
- 缺少更低方差的固定协议结果

## 5. D 类：论文支持文档

关键文件：

- `docs/evaluation_workflow.md`
- `docs/2026-04-05_project_readiness_assessment.md`
- `docs/2026-04-05_high_quality_graduation_design_backlog.md`
- `docs/2026-04-05_phase2_real_ai_batch_assessment.md`
- `docs/2026-04-05_phase3_battle_guidance_assessment.md`

作用：

- 固定实验流程
- 固定阶段性结论
- 固定问题清单、证据索引与下一阶段边界

## 6. 当前不建议直接作为“最终论文核心正证据”的文件

以下文件当前不应直接充当最终正面结论的核心支撑：

- 未区分 dummy / placeholder 环境与真实环境的旧 smoke 报告
- 仅能证明系统不崩溃、但 AI 占比极低的长程运行报告
- 尚未写清参数与运行模式的临时调试文件
- 第一轮修复前的 batch 结果

原因：

- 它们更适合作为研发排障记录或失败案例证据，而不是正向主结论材料

## 7. 后续证据归档规则

从现在开始，建议所有新增证据都按以下方式归档：

1. 明确写清运行模式：
   - `llm_primary_mode`
   - `ai_full_control_mode`
   - `pure_llm_mode`
2. 明确区分：
   - resilience
   - real-AI
   - ablation
3. 每份正式报告至少保留：
   - 原始 JSON 报告
   - 汇总 Markdown
   - 参数与环境说明
4. 只有同时满足以下条件的报告，才进入最终论文正证据组：
   - 参数明确
   - 运行模式明确
   - `timeline_valid = true`
   - 无 fatal error
   - AI 主导比例与论文表述一致

## 8. 当前阶段结论

截至目前：

- A 类证据充足
- B 类证据较强
- C 类证据已经从“只有单次 smoke”推进到“有批量实验、有失败诊断、有修复后复测”
- 但 C 类证据仍未强到可以支撑“稳定推进关键剧情”

因此，下一阶段最重要的工作不是继续堆积更多同质化实验，而是：

- 在 `Phase 3` 中直接提升 Oak Lab 局部决策质量
