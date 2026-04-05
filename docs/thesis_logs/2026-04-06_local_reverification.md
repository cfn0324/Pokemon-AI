# 2026-04-06 本地复验记录

## 1. 目的

本记录用于补齐 `2026-04-06` 当天对当前仓库状态的最新复验口径，避免论文草稿只引用 `2026-04-05` 的历史报告。

## 2. 复验环境

- 日期：`2026-04-06`
- 工作目录：`D:\bysj\p-ai`
- Python：`D:\anaconda\python.exe`
- 远端仓库：`git@github.com:cfn0324/Pokemon-AI.git`

## 3. 执行命令与结果

### 3.1 全量测试

执行：

```powershell
pytest -q
```

结果分两次：

1. 沙箱内执行：
   - `1 failed, 298 passed, 4 warnings`
   - 唯一失败来自 `tests/test_autonomous_smoke_batch.py`
   - 失败根因不是业务逻辑断言，而是 Windows 临时目录写入权限受限，`tempfile.TemporaryDirectory()` 无法在受限环境中创建/清理目录
2. 沙箱外复验：
   - `299 passed, 1 warning`

结论：

- 当前仓库在正常权限环境下通过全量测试
- 论文正文若引用“截至 2026-04-06 全量测试通过”，应注明这是在非受限权限环境下复验得到的结果

### 3.2 环境检查

执行：

```powershell
python test_setup.py
```

结果：

- `7/7` 通过
- Python、依赖、ROM、配置、目录、API 连接均正常

### 3.3 API 直连检查

执行：

```powershell
python test_custom_api.py
```

结果：

- 返回 `API connection successful!`
- 端点：`https://api.ququ233.com/v1`
- 模型：`gpt-5.4`

## 4. 与既有文档的关系

需要特别说明的是：

- `docs/2026-04-06_top_tier_thesis_readiness_audit.md` 记录了同一天较早时间点的一次 provider `500 / 没有可用 token` 失败样例
- 本次稍后复验中，`test_custom_api.py` 已成功

这并不矛盾，反而说明：

- 外部 provider 在同一天内具有明显波动
- “接口可配置连通”与“任意时间都稳定可用”是两件不同的事
- 论文中必须把外部服务可用性视作重要实验噪声源，而不能简单忽略

## 5. 论文可直接引用的最新口径

截至 `2026-04-06` 当前复验：

- 全量测试：`299 passed, 1 warning`
- 环境检查：`7/7` 通过
- API 直连：成功

因此，最新论文口径应写为：

1. 当前代码在正常权限环境下通过全量测试。
2. 当前本地环境满足真实 API、真实 ROM 和真实模型运行条件。
3. 外部 provider 在日内层面存在波动，应在局限性章节单独讨论。
