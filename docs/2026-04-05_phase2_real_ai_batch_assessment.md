# 2026-04-05 Phase 2 真实 AI 重复实验阶段评估

## 1. 本阶段目标

Phase 2 的目标不是直接解决 Oak Lab 决策质量，而是先建立“真实 AI 重复实验”的最小可信证据链：

- 固定 checkpoint
- 固定模型
- 固定参数
- 固定输出结构
- 能够把失败原因写清楚，而不是只保留单次成功样例

## 2. 本阶段新增工程改动

### 2.1 批量实验能力

新增：

- `scripts/autonomous_smoke_batch.py`

作用：

- 用统一协议批量运行 `autonomous_smoke.py`
- 自动输出原始报告、stdout/stderr、summary、manifest
- 为论文提供“同一协议多次运行”的可复核证据

### 2.2 smoke 摘要口径增强

改进：

- `scripts/smoke_report_summary.py`

新增能力：

- 统计 `obtained_oaks_parcel`
- 统计 `delivered_oaks_parcel`
- 统计 `reached_route1`
- 输出更适合论文表格的 `Progress` 字段

### 2.3 transient transport error 分类修复

改进：

- `src/agents/main_agent.py`
- `tests/test_main_agent_api_failures.py`

修复内容：

- 将 `ConnectionResetError(10054)` / `connection aborted` 从“长期不可达”中剥离
- 允许其进入同回合重试或短冷却路径
- 避免一次瞬时连接抖动把整段 run 变成 fallback 主导

## 3. 本阶段实验协议

统一协议如下：

- checkpoint：`checkpoint_195913`
- turns：`120`
- 模式：`llm-primary + ai-full-control`
- 参数：
  - `--reset-context`
  - `--decision-max-tokens 384`
  - `--action-plan-max-actions 3`
- 模型环境：
  - `AI_MODEL = gpt-5.4`
  - `AI_BASE_URL = https://api.ququ233.com/v1`

## 4. 关键实验与结果

### 4.1 修复前的第一轮固定协议 3 次 batch

文件：

- `docs/thesis_logs/2026-04-05_phase2_real_ai_baseline.md`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline/`

结果摘要：

- `3/3` completed
- `0/3` AI-dominant
- `avg_ai_authored_ratio = 0.0194`
- 大量 turn 被 `api_unavailable_field_interaction` 占据

结论：

- 这一轮结果不能当作正向能力证据
- 但它暴露了一个真实工程问题：transient transport failure 被放大成整段实验失真

### 4.2 修复后的单次 120 turn probe

文件：

- `docs/thesis_logs/2026-04-05_phase2_retryfix_probe.md`
- `tmp/real_ai_batches/2026-04-05_phase2_retryfix_probe/`

结果摘要：

- `1/1` completed
- `1/1` AI-dominant
- `ai_authored_ratio = 0.8417`
- 最终位置到达 `map 12`（Route 1）

结论：

- 修复是有效的
- transport 分类问题确实显著影响了真实 AI 参与比例

### 4.3 修复后的第二轮固定协议 3 次 batch

文件：

- `docs/thesis_logs/2026-04-05_phase2_real_ai_baseline_retryfix.md`
- `tmp/real_ai_batches/2026-04-05_phase2_real_ai_baseline_retryfix/`

结果摘要：

- `3/3` completed
- `1/3` AI-dominant
- `avg_ai_authored_ratio = 0.3000`
- `avg_main_model_ratio = 0.2778`
- 仍未取得 `got_pokedex` / `oak_got_parcel`

结论：

- 相比修复前，真实 AI 参与比例明显改善
- 但重复实验的方差仍然偏大
- 说明 transport 稳定性不是唯一问题，Oak Lab 局部决策质量仍是主瓶颈

## 5. 阶段结论

### 已完成部分

- 已建立真实 AI 批量实验能力
- 已建立标准化的 summary / manifest / raw JSON 证据结构
- 已定位并修复一项影响 real-AI 证据可信度的 transport 分类问题
- 已完成两轮固定协议 batch 与一轮修复后 probe

### 尚未完成部分

- 尚未稳定复现更强剧情里程碑
- 尚未把 repeated batch 推进到 `got_pokedex` 或 `oak_got_parcel`
- 尚未把 Oak Lab 关键瓶颈降到足够低

### 对 Phase 2 的正式判定

判定：`部分完成`

原因：

- “有无重复实验能力”这个问题已经解决
- “重复实验能否稳定证明更强剧情推进”这个问题还没有解决

## 6. 下一阶段建议

下一阶段不应继续无止境重复同协议 batch，而应转入：

- `Phase 3`：Oak Lab 局部决策质量提升

建议重点：

- 强化 NPC 邻接与朝向关系表达
- 降低脚本锁 / 局部阻挡 / 面向错误造成的试探
- 在不重新引入脚本主导的前提下，提升 `oak_got_parcel` / `got_pokedex` 成功率
