# Pokemon Red AI 智能体

一个由 Claude（Anthropic）驱动的自主AI智能体，使用高级推理、多智能体协作和记忆管理来玩宝可梦红版。

## 项目概述

本项目受Gemini 2.5 Pro玩宝可梦蓝版成就的启发，使用Claude API实现了类似的架构模式：

- **多智能体架构**：主智能体、寻路智能体、谜题解决智能体和评论智能体
- **高级记忆管理**：每100回合进行上下文摘要
- **空间感知**：战争迷雾地图系统追踪探索进度
- **视觉+数据融合**：屏幕分析结合RAM数据提取
- **目标导向规划**：主要、次要和第三目标管理

## 功能特性

- **自主游戏**：AI独立做出所有决策
- **先进推理**：使用Claude Sonnet 4.5进行复杂决策
- **强大记忆系统**：通过智能摘要防止重复循环
- **专业子智能体**：
  - 寻路智能体：处理复杂导航
  - 谜题解决智能体：处理岩石/开关谜题
  - 评论智能体：策略评估
- **实时进度追踪**：徽章、宝可梦队伍、道具监控
- **检查点系统**：保存/加载游戏状态以便恢复
- **全面日志记录**：完整的行动历史和决策追踪
- **实时Web可视化**：浏览器中查看AI决策过程和游戏状态
- **异步AI决策**：保持模拟器响应，避免窗口冻结

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    主AI智能体                            │
│              (Claude Sonnet 4.5)                        │
└─────────────┬───────────────────────────────────────────┘
              │
              ├─> 记忆管理器 (上下文摘要)
              ├─> 目标管理器 (主要/次要/第三)
              ├─> 地图记忆 (战争迷雾系统)
              │
              ├─> 专业子智能体:
              │   ├─> 寻路智能体
              │   ├─> 谜题解决智能体
              │   └─> 评论智能体
              │
              └─> 游戏接口
                  ├─> PyBoy 模拟器
                  ├─> RAM 读取器 (游戏状态)
                  ├─> 视觉系统 (截图)
                  └─> 行动执行器
```

## 安装

### 前置要求

- Python 3.9 或更高版本
- 宝可梦红版 ROM 文件 (PokemonRed.gb)
- Anthropic API密钥

### 设置步骤

1. 克隆仓库：
```bash
git clone <repository-url>
cd pokemon-ai-agent
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置API密钥：

创建 `.env` 文件：
```bash
ANTHROPIC_API_KEY=你的API密钥
ANTHROPIC_BASE_URL=https://api.ququ233.com/v1  # 可选：自定义API端点
```

4. 放置宝可梦红版ROM：
```bash
# 确保 PokemonRed.gb 在根目录
```

5. 运行智能体：
```bash
python main.py
```

6. 打开可视化仪表板：
```
访问 http://localhost:5000 查看实时游戏画面和AI决策
```

## 配置

编辑 `config.yaml` 来自定义：

- **AI模型**：选择Claude模型变体
- **游戏设置**：无头模式、速度控制
- **行动延迟**：控制游戏速度
- **记忆设置**：摘要频率
- **日志级别**：调试详细程度
- **检查点频率**：自动保存间隔
- **可视化**：Web仪表板端口和设置
- **性能**：异步决策、缓存等

## 项目结构

```
pokemon-ai-agent/
├── main.py                 # 主入口点
├── config.yaml             # 配置文件
├── requirements.txt        # Python依赖
├── .env                    # API密钥 (需创建)
├── PokemonRed.gb          # ROM文件 (需提供)
│
├── src/
│   ├── agents/            # AI智能体
│   │   ├── main_agent.py         # 主决策智能体
│   │   ├── pathfinder.py         # 寻路智能体
│   │   ├── puzzle_solver.py      # 谜题解决智能体
│   │   ├── critic.py             # 评论智能体
│   │   └── async_decision.py     # 异步决策包装器
│   │
│   ├── emulator/          # Game Boy模拟器
│   │   ├── game_boy.py           # PyBoy包装器
│   │   └── memory_reader.py      # RAM数据提取
│   │
│   ├── state/             # 游戏状态管理
│   │   ├── game_state.py         # 状态处理器
│   │   ├── vision.py             # 屏幕分析
│   │   └── map_memory.py         # 地图探索追踪
│   │
│   ├── memory/            # AI记忆系统
│   │   ├── context_manager.py    # 上下文窗口管理
│   │   └── summarizer.py         # 历史摘要
│   │
│   ├── tools/             # 工具模块
│   │   ├── goal_manager.py       # 目标管理
│   │   ├── action_executor.py    # 按钮输入
│   │   └── progress_tracker.py   # 进度监控
│   │
│   ├── visualization/     # Web可视化
│   │   └── visualizer.py         # 实时仪表板服务器
│   │
│   └── utils/             # 实用工具
│       ├── config.py             # 配置加载
│       └── logger.py             # 日志记录
│
├── templates/             # Web仪表板模板
│   └── dashboard.html            # 可视化界面
│
├── data/                  # 数据文件
│   ├── memory_addresses.json    # 宝可梦红版内存映射
│   ├── map_memory.json           # 探索进度持久化
│   └── checkpoints/              # 游戏状态检查点
│
├── logs/                  # 日志文件
│   └── screenshots/              # 游戏截图
│
└── docs/                  # 文档
    ├── ARCHITECTURE.md           # 架构深入解析
    ├── QUICK_START.md            # 快速开始指南
    ├── ADVANCED_USAGE.md         # 高级用法
    ├── TROUBLESHOOTING.md        # 故障排除
    ├── VISUALIZATION_GUIDE.md    # 可视化使用指南
    └── PYBOY_STABILITY.md        # PyBoy稳定性说明
```

## 核心组件

### 1. 主AI智能体
- 使用Claude Sonnet 4.5进行高层决策
- 管理目标层次结构
- 协调专业子智能体
- 维护对话上下文

### 2. 记忆系统
- **上下文管理器**：管理AI的对话窗口
- **摘要器**：每100回合压缩历史
- **地图记忆**：追踪已探索/未探索的区域

### 3. 状态观察
- **RAM读取器**：提取精确的游戏数据（位置、徽章、宝可梦）
- **视觉处理器**：分析游戏截图以检测UI元素
- **游戏状态**：融合RAM和视觉数据为统一状态

### 4. 专业智能体
- **寻路器**：处理复杂的导航挑战
- **谜题解决器**：解决岩石推动谜题
- **评论者**：评估策略并检测卡住情况

### 5. 可视化系统
- **实时仪表板**：浏览器中观看AI游戏
- **WebSocket流式传输**：即时数据更新
- **游戏截图**：实时Game Boy屏幕显示
- **决策历史**：追踪AI推理过程

### 6. 异步决策
- **非阻塞AI**：在等待API时保持模拟器响应
- **线程安全**：使用队列进行线程间通信
- **稳定性**：防止PyBoy窗口冻结

## 使用方法

### 基础用法

```bash
# 启动AI智能体
python main.py

# 在浏览器中访问可视化仪表板
# http://localhost:5000
```

### Web可视化仪表板

打开 `http://localhost:5000` 查看：

- 📺 **游戏画面**：实时Game Boy屏幕
- 🤖 **AI决策**：当前行动和推理
- 📊 **游戏状态**：徽章、队伍、金钱、位置
- 🎯 **当前目标**：主要/次要/第三目标
- 📜 **决策历史**：最近50条AI决策
- 🎪 **事件日志**：里程碑和成就

### 配置选项

**推荐设置（默认）**：
```yaml
game:
  headless: true          # 无PyBoy窗口，使用Web仪表板
  speed: 0                # 最高速度

performance:
  async_decisions: true   # 异步AI决策（保持响应）

visualization:
  enabled: true           # Web仪表板
  port: 5000
```

**如需显示PyBoy窗口**：
```yaml
game:
  headless: false         # 显示PyBoy窗口
  speed: 1                # 正常速度（推荐）

performance:
  async_decisions: true   # 必须保持启用！
```

### 高级功能

- **检查点恢复**：自动每100回合保存
- **决策历史**：完整的行动和推理日志
- **进度追踪**：监控徽章、宝可梦捕获、探索
- **评论系统**：检测卡住情况并调整策略
- **多设备访问**：在局域网内任何设备上查看仪表板

## 工作原理

1. **感知**：PyBoy读取游戏RAM + 视觉系统分析截图
2. **记忆**：上下文管理器维护最近20回合的历史 + 100回合摘要
3. **推理**：Claude分析状态并决定下一步行动
4. **行动**：执行器按下按钮并推进游戏
5. **学习**：评论者检测问题并提供反馈
6. **可视化**：仪表板实时显示所有数据

## 性能

- **决策速度**：每个行动6-8秒（API调用时间）
- **记忆效率**：每100回合自动摘要
- **资源使用**：~200MB RAM，25-35% CPU（headless模式）
- **稳定性**：异步决策确保PyBoy始终响应
- **可靠性**：检查点系统防止进度丢失

## 故障排除

### 常见问题

1. **API错误**：
   - 检查`.env`文件中的`ANTHROPIC_API_KEY`
   - 验证API端点（如使用自定义端点）

2. **ROM未找到**：
   - 确保`PokemonRed.gb`在根目录
   - 检查文件名大小写

3. **PyBoy窗口未响应**：
   - 使用`headless: true`（推荐）
   - 或确保`async_decisions: true`

4. **可视化无法访问**：
   - 检查端口5000是否被占用
   - 访问`http://127.0.0.1:5000`而不是`localhost`
   - 检查防火墙设置

5. **内存泄漏**：
   - 重启程序
   - 检查摘要设置

详细的故障排除指南：`docs/TROUBLESHOOTING.md`

## 文档

- **快速开始**：`docs/QUICK_START.md`
- **架构详解**：`docs/ARCHITECTURE.md`
- **高级用法**：`docs/ADVANCED_USAGE.md`
- **可视化指南**：`docs/VISUALIZATION_GUIDE.md`
- **稳定性说明**：`docs/PYBOY_STABILITY.md`

## 技术栈

- **AI**: Anthropic Claude Sonnet 4.5
- **模拟器**: PyBoy
- **视觉**: OpenCV, PIL
- **Web**: Flask, Flask-SocketIO
- **数据**: NumPy, Pandas
- **日志**: colorlog

## 致谢

本项目受以下启发：
- Gemini 2.5 Pro玩宝可梦蓝版的成就
- PyBoy Game Boy模拟器项目
- Anthropic Claude API

## 许可证

MIT License

## 贡献

欢迎贡献！请随时提交问题或拉取请求。

## 联系方式

如有问题或建议，请提交issue。

---

**享受观看AI玩宝可梦红版的乐趣！** 🎮✨

访问 http://localhost:5000 查看实时仪表板！
# Pokemon-AI
