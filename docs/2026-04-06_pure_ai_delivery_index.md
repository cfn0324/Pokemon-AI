# 2026-04-06 Pure-AI 交付索引

## 1. 一站式入口

- 主补充包：`docs/2026-04-06_pure_ai_demo_and_supplement_pack.md`
- 最佳演示视频：`docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v4.mp4`
- 视频文件夹：`docs/report_assets/2026-04-06_pure_ai_demo/videos/`
- 报告文件夹：`docs/report_assets/2026-04-06_pure_ai_demo/reports/`
- 图片文件夹：`docs/img/2026-04-06/`
- 重复批跑日志：`docs/thesis_logs/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1.md`

## 2. 本次新增内容

- 已把演示视频统一整理到 `docs/report_assets/2026-04-06_pure_ai_demo/videos/`
- 已把关键 JSON 和 batch 汇总统一整理到 `docs/report_assets/2026-04-06_pure_ai_demo/reports/`
- 已生成正文可用图片到 `docs/img/2026-04-06/main_figures/`
- 已补充单独的批跑日志文档和总补充包文档，便于论文和答辩直接引用

## 3. 建议答辩使用顺序

1. 先放 `pure_ai_demo_v4.mp4`，证明当前协议下是 pure-AI、无 runtime fallback takeover、无绿色框覆盖。
2. 再引用 `docs/2026-04-06_pure_ai_demo_and_supplement_pack.md`，对应补充消融表、延迟统计表、失败 taxonomy、方法定位图和复现实验清单。
3. 如果老师追问重复性，直接打开 `docs/thesis_logs/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1.md`。
4. 如果老师追问正文配图，直接用 `docs/img/2026-04-06_figure_index.md` 选图。

## 4. 当前可安全宣称的结论

- 最新 checkpoint 已能在 pure-AI、runtime fallback 关闭的协议下完成真实推进。
- 新 repeated batch 已达到 `3/3 Route 1`、`1/3 Viridian City`、`1/3 Viridian Mart`。
- `Oak's Parcel` 已在单次演示视频中拿到，但还不能宣称 repeated batch 稳定复现。
- 当前主要外部失败模式是 transport instability，不是脚本 takeover。

## 5. 当前最值得优先展示的文件

- `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v4.mp4`
- `docs/2026-04-06_pure_ai_demo_and_supplement_pack.md`
- `docs/thesis_logs/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1.md`
- `docs/img/2026-04-06_figure_index.md`
