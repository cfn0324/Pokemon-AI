# Pokemon AI Agent

一个基于 PyBoy、RAM 读取、可选视觉分析和通用 Messages 风格 AI 接口的宝可梦红版自动游玩项目。

这个仓库的目标不是做一个“示例脚本”，而是做一个能连续运行、能保存进度、能观察状态、能在接口切换后继续工作的长时任务 Agent。

## 项目现状

当前已经具备这些核心能力：

- 使用 PyBoy 驱动 `PokemonRed.gb`
- 通过内存地址读取位置、徽章、队伍、金钱、战斗状态
- 可选做像素级视觉分析，识别菜单、对话、战斗和地形特征
- 用主智能体逐回合输出动作
- 用寻路、谜题、评论三个辅助智能体处理特定问题
- 维护近期回合、摘要和目标层级
- 自动记录日志、截图、检查点和进度
- 提供实时 Web 仪表盘
- 用通用 `AIClient` 兼容不同 `/messages` 风格接口

## 你需要准备什么

- Python 3.9+
- 合法持有的 `PokemonRed.gb`
- 一个可用的 AI 接口，满足：
  - 可通过 HTTP 访问
  - 支持 `/messages` 风格请求
  - 能接受 `model`、`messages`、`max_tokens`
  - 返回内容能被当前 `AIClient` 解析

## 最快启动方式

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建 `.env`

项目根目录创建：

```env
AI_API_KEY=your-api-key
AI_MODEL=your-model-id
AI_BASE_URL=https://api.your-endpoint.com/v1

# 可选：某些代理或服务要求版本头
# AI_API_VERSION=2023-06-01
# AI_API_VERSION_HEADER=api-version
```

支持按智能体覆盖模型：

```env
AI_MAIN_MODEL=your-main-model-id
AI_PATHFINDER_MODEL=your-fast-model-id
AI_PUZZLE_SOLVER_MODEL=your-fast-model-id
AI_CRITIC_MODEL=your-review-model-id
```

### 3. 放 ROM

把文件放到项目根目录：

```text
PokemonRed.gb
```

### 4. 先做检查

```bash
python test_setup.py
```

只想先验证接口时：

```bash
python test_custom_api.py
```

### 5. 启动

```bash
python main.py
```

默认可视化地址通常是：

```text
http://localhost:5000
```

## 运行入口说明

### `python main.py`

最推荐的入口。

原因：

- 会自动读取 `.env`
- 与当前主流程完全一致
- 最少踩环境变量加载差异

### `run.sh`

适合 Linux / macOS。

特点：

- 会检查 `AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL`
- 在缺少环境变量时会尝试读取 `.env`

### `run.bat`

适合 Windows，但要注意：

- 它会检查当前终端里是否已经设置环境变量
- 它不会像 `main.py` 一样主动解析 `.env`

所以在 Windows 上，如果你没有先把环境变量注入 shell，直接用：

```powershell
python main.py
```

更稳。

## 配置文件

主配置在：

- `config.yaml`

### `game`

- `rom_path`：ROM 路径
- `speed`：模拟速度，`0` 表示尽量快
- `headless`：是否无窗口运行
- `save_state_dir`：检查点保存目录

### `ai`

- `model`：默认模型 ID
- `temperature`：默认温度
- `max_tokens`：最大输出长度
- `agents.main/pathfinder/puzzle_solver/critic.model`：按智能体覆盖模型

### `memory`

- `max_context_turns`：摘要触发阈值
- `summarization_enabled`：是否启用摘要
- `keep_recent_turns`：完整保留的最近回合数
- `map_memory_enabled`：是否启用地图记忆
- `save_interval`：地图记忆保存间隔

### `actions`

- `delay_ms`：动作之间延迟
- `timeout_seconds`：状态等待上限
- `stuck_threshold`：重复动作判定阈值
- `screenshot_interval`：截图频率
- `wait_frames`：`wait` 动作时推进的帧数

### `goals`

- `primary_goal`
- `secondary_goal`
- `tertiary_goal`
- `goal_update_interval`

### `logging`

- `level`
- `log_dir`
- `log_actions`
- `log_states`
- `log_decisions`
- `save_screenshots`
- `screenshot_dir`

### `progress`

- `checkpoint_interval`
- `track_badges`
- `track_pokemon`
- `track_items`
- `track_exploration`

### `performance`

- `enable_caching`
- `cache_dir`
- `parallel_agents`
- `async_decisions`

### `visualization`

- `enabled`
- `port`
- `update_screenshots`
- `update_interval`

### `debug`

- `enabled`
- `break_on_error`
- `verbose_state`
- `save_ram_dumps`

## 环境变量优先级

配置解析逻辑在：

- `src/utils/config.py`

当前优先级可以简单理解为：

1. 智能体级环境变量
2. `AI_MODEL`
3. `config.yaml` 中对应字段

具体覆盖关系：

- `AI_MODEL` 覆盖 `ai.model`
- `AI_MAIN_MODEL` 覆盖主智能体模型
- `AI_PATHFINDER_MODEL` 覆盖寻路智能体模型
- `AI_PUZZLE_SOLVER_MODEL` 覆盖谜题智能体模型
- `AI_CRITIC_MODEL` 覆盖评论智能体模型

## 架构总览

### 主循环

入口类在 `main.py` 中的 `PokemonAIAgent`。

每个回合大致做这些事：

1. 更新游戏状态
2. 抓当前截图
3. 识别屏幕类型
4. 必要时自动推进对话或退出文本输入
5. 生成状态文本
6. 请求 AI 决策
7. 执行动作
8. 更新仪表盘
9. 更新进度
10. 定期保存截图和检查点

### 模块分层

#### 模拟器层

- `src/emulator/game_boy.py`

负责：

- 启动 PyBoy
- 发送按键
- 获取截图
- 读写内存
- 保存/加载模拟器状态

#### 内存与状态层

- `src/emulator/memory_reader.py`
- `src/state/game_state.py`
- `src/state/map_memory.py`

负责：

- 读取 RAM 中的核心状态
- 维护地图探索信息
- 生成 AI 使用的统一状态表示

#### 视觉层

- `src/state/vision.py`

负责：

- 检测文本框、菜单、战斗 UI
- 推断当前屏幕类型
- 分析地形、对象、颜色和运动信息

#### 智能体层

- `src/agents/main_agent.py`
- `src/agents/pathfinder.py`
- `src/agents/puzzle_solver.py`
- `src/agents/critic.py`
- `src/agents/async_decision.py`

职责：

- 主智能体：默认动作决策
- 寻路智能体：处理复杂导航
- 谜题智能体：处理推石头等任务
- 评论智能体：策略诊断与卡死评论
- 异步决策器：后台线程请求模型，避免阻塞主循环

#### 记忆与目标层

- `src/memory/context_manager.py`
- `src/memory/summarizer.py`
- `src/tools/goal_manager.py`

职责：

- 保存近期回合
- 压缩长历史
- 维护主/次/临时目标

#### 执行与观察层

- `src/tools/action_executor.py`
- `src/tools/progress_tracker.py`
- `src/visualization/visualizer.py`
- `templates/dashboard.html`

职责：

- 执行动作
- 检测循环/卡死
- 记录进度与里程碑
- 提供实时可视化

## AI 接口兼容要求

项目不再依赖厂商 SDK，而是走：

- `src/utils/ai_client.py`

### 请求行为

如果 `AI_BASE_URL` 不以 `/messages` 结尾，会自动补成：

```text
AI_BASE_URL + /messages
```

默认请求头包括：

- `Content-Type: application/json`
- `x-api-key: <AI_API_KEY>`
- `Authorization: Bearer <AI_API_KEY>`

如果设置：

- `AI_API_VERSION`
- `AI_API_VERSION_HEADER`

还会带额外的版本头。

### 已支持的响应结构

当前会按顺序尝试从这些位置取文本：

- `content[].text`
- `output_text`
- `choices[0].message.content`
- `output[].content[].text`

如果你的接口结构不同，需要修改：

- `src/utils/ai_client.py`

重点是 `_extract_text()`。

## 测试脚本

### `python test_setup.py`

检查：

- Python 版本
- 依赖是否安装
- `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL`
- ROM 是否存在
- `config.yaml` 结构
- 目录结构
- AI 接口连通性

### `python test_custom_api.py`

更偏向单独验证接口：

- 打印当前读取到的接口配置
- 发一个最小测试请求
- 看当前接口是否真正能返回文本

## 仪表盘

可视化由：

- `src/visualization/visualizer.py`
- `templates/dashboard.html`

提供。

当前支持：

- 状态展示
- 实时截图
- 最新决策
- 目标列表
- 事件流
- 决策历史

后端路由包括：

- `/`
- `/api/state`
- `/api/decision`
- `/api/screenshot`
- `/api/history`
- `/api/goals`

Socket 事件包括：

- `state_update`
- `decision_update`
- `screenshot_update`
- `goals_update`
- `event`

## 检查点与持久化

项目会保存这些内容：

- 模拟器 state
- 上下文 JSON
- 目标 JSON
- 地图探索 JSON
- 进度 JSON
- 日志
- 截图

相关目录：

- `data/checkpoints/`
- `data/maps/`
- `logs/`

## 典型调参方案

### 速度优先

```yaml
game:
  speed: 0
  headless: true

ai:
  model: "your-fast-model-id"
  max_tokens: 2048

actions:
  delay_ms: 50

memory:
  max_context_turns: 50
  keep_recent_turns: 10
```

### 质量优先

```yaml
ai:
  model: "your-best-model-id"
  temperature: 0.7
  max_tokens: 8192

memory:
  max_context_turns: 200
  keep_recent_turns: 50

logging:
  level: "DEBUG"
```

### 成本优先

```yaml
ai:
  model: "your-low-cost-model-id"
  max_tokens: 2048

actions:
  delay_ms: 500

memory:
  max_context_turns: 50
  keep_recent_turns: 10
```

## 常见问题

### 1. 启动时提示缺少环境变量

最常见是这三个没有配好：

- `AI_API_KEY`
- `AI_MODEL`
- `AI_BASE_URL`

先检查 `.env`，再执行：

```bash
python test_setup.py
```

### 2. `run.bat` 能报错，`python main.py` 能启动

这是预期差异，不是 bug。

原因是：

- `main.py` 会 `load_dotenv()`
- `run.bat` 只检查当前 shell 里的变量

### 3. 接口 401 / 403

优先排查：

- 密钥错误
- 地址错误
- 版本头缺失
- 代理服务和 `/messages` 兼容性不一致

### 4. 窗口卡住或响应很差

优先保证：

- `performance.async_decisions: true`
- 尽量使用 `headless: true`
- 不要在 GUI 模式下调用太慢的模型

### 5. 仪表盘打不开

检查：

- `visualization.enabled`
- 端口是否占用
- 是否访问了正确端口

## 代码乱码检查结果

这次我额外检查了关键运行文件的编码情况。

### 已确认正常的关键文件

- `config.yaml`
- `main.py`
- `templates/dashboard.html`
- `src/state/vision.py`
- `src/visualization/visualizer.py`
- `src/emulator/memory_reader.py`

### 当前结论

- Markdown 文档已不再有旧乱码残留
- 关键运行路径文件没有再发现明显的中文乱码
- 代码里如果还有零星编码问题，规模已经不大，且不在当前主链路上

如果你后续还想继续做更严格的源码清洗，可以优先再扫：

- 所有日志文案
- 少量中文注释
- 前端模板中的业务字段命名一致性

## 项目文件布局

当前建议你关注这些：

```text
.
├─ README.md
├─ TODO.md
├─ main.py
├─ config.yaml
├─ .env.example
├─ requirements.txt
├─ run.bat
├─ run.sh
├─ test_setup.py
├─ test_custom_api.py
├─ templates/
├─ src/
├─ data/
└─ logs/
```

## 许可证

MIT
