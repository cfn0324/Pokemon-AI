# 2026-04-07 论文修订执行清单

## 已完成

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 收缩摘要、引言、结论中的过强主张 | 已完成 | `v4` 统一改为“存在性 + 初步可复现性”口径 |
| 补充可复现信息 | 已完成 | 加入模型、API、超时、重试、ROM SHA256、PyBoy/Python/OS、checkpoint |
| 正文加入核心结果总表 | 已完成 | 见 `v4` 第 7 章表 7-1 |
| 正文加入基线表 | 已完成 | 见 `v4` 第 7 章表 7-2；当前使用 2026-04-05 历史基线，明确标注为辅助对照 |
| 正文加入消融表 | 已完成 | 见 `v4` 第 7 章表 7-3 |
| 澄清“纯 AI 决策”允许边界 | 已完成 | 见 `v4` 第 3 章表 3-1 |
| 正面拆解 story guidance / battle guidance | 已完成 | 见 `v4` 第 5 章与第 7 章 |
| 将单次 260 回合 run 降级为压力测试 | 已完成 | 不再作为主成功证据 |
| 用新的 3x120 重复实验替代旧叙事主证据 | 已完成 | 作为当前正文主结果 |

## 已完成的项目侧修改

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 新增 story/battle guidance 开关 | 已完成 | `config.yaml`, `main.py`, `game_state.py` |
| smoke 脚本支持 guidance 消融参数 | 已完成 | `autonomous_smoke.py`, `autonomous_smoke_batch.py` |
| 单次报告补充 reproducibility 字段 | 已完成 | 输出 `environment`, `effective_settings`, `config_snapshot` |
| 批量汇总补充里程碑与 Wilson 区间 | 已完成 | `smoke_report_summary.py` |
| 汇总 Markdown 非 ASCII 区间符修复 | 已完成 | 已改成 ASCII `-` |
| 相关测试 | 已完成 | `pytest` 全量与针对性测试均通过 |

## 已完成的复跑

| 实验 | 状态 | 产物 |
| --- | --- | --- |
| 纯 AI 完整引导 `3 x 120` | 已完成 | `tmp/real_ai_batches/2026-04-07_pure_ai_batch_checkpoint_196081_120t_fullguidance_v1/..._summary.json` |
| 纯 AI 完整引导 `1 x 260` | 已完成 | `docs/report_assets/2026-04-07_pure_ai_demo/reports/pure_ai_latest_260_v8.json` |
| 关闭故事引导 `1 x 120` | 已完成 | `docs/report_assets/2026-04-07_pure_ai_demo/reports/pure_ai_ablation_no_story_120_v1.json` |
| 关闭战斗引导 `1 x 120` | 已完成 | `docs/report_assets/2026-04-07_pure_ai_demo/reports/pure_ai_ablation_no_battle_120_v1.json` |

## 可选后续

| 项目 | 是否必须 | 原因 |
| --- | --- | --- |
| 同日同 checkpoint 的 fresh baseline | 否，但推荐 | 当前正文基线表使用 2026-04-05 历史对照，不是最强 apples-to-apples 对比 |
| 更大样本量重复实验 | 否，但推荐 | `n=3` 仍偏小，区间较宽 |
| 自动记录 CPU/GPU/内存硬件字段 | 否，但推荐 | 目前正文已有软件环境与 ROM 校验，但硬件记录仍不完整 |

