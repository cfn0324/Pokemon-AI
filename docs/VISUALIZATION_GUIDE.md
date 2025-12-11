# Pokemon AI Agent - 可视化仪表板使用指南

## 概述

Pokemon AI Agent 现已集成实时Web可视化仪表板，可以实时监控AI的决策过程、游戏状态和探索进度。

## 功能特性

### 实时数据展示

- **游戏画面**: 实时显示Game Boy模拟器屏幕（像素风格渲染）
- **AI决策**: 显示当前AI的行动和推理过程
- **游戏状态**: 徽章、Pokemon队伍、金钱、位置等信息
- **当前目标**: 主要、次要和第三目标的层级展示
- **探索进度**: 地图探索百分比和已探索区域统计
- **决策历史**: 滚动显示最近50条AI决策记录
- **事件日志**: 里程碑、成就和错误事件

### 实时更新

- 使用WebSocket技术实现毫秒级数据推送
- 游戏画面每回合实时更新
- AI决策立即显示推理过程
- 状态变化实时同步

## 如何使用

### 1. 启动程序

```bash
python main.py
```

程序启动后会显示：
```
Visualization dashboard available at http://localhost:5000
```

### 2. 打开仪表板

在浏览器中访问：
- **本地访问**: http://localhost:5000
- **局域网访问**: http://你的IP地址:5000

支持的浏览器：
- Chrome (推荐)
- Firefox
- Edge
- Safari

### 3. 仪表板布局

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pokemon AI Agent Dashboard                    │
│              Powered by Claude (Anthropic)                       │
│           Connected | Turn: XXX                                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────────────┬──────────────┐
│ Game State   │   Game Screen        │ Current Goals│
│              │                      │              │
│ Turn: XXX    │   ┌──────────────┐   │ PRIMARY:     │
│ Badges: X/8  │   │              │   │ Complete...  │
│ Money: $XXX  │   │  [Game Boy]  │   │              │
│ Party: X     │   │   Screen     │   │ SECONDARY:   │
│              │   │              │   │ Get starter  │
│ Position:    │   └──────────────┘   │              │
│ Map X (Y,Z)  │                      │ Events Log:  │
│              │   Latest Decision:   │ [Milestone]  │
│ Badges:      │   Action: DOWN       │ [Achievement]│
│ □□□□□□□□     │   Reasoning: ...     │              │
│              │                      │              │
│ Party:       │   Visual Analysis:   │              │
│ Pikachu Lv5  │   Menu is open       │              │
│ HP: 20/20    │   Elements: menu     │              │
│ ████████     │                      │              │
│              │                      │              │
│ Exploration: │                      │              │
│ Map: 25.5%   │                      │              │
│ Tiles: 51/200│                      │              │
└──────────────┴──────────────────────┴──────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Decision History                          │
│                                                                  │
│ Turn 42 | DOWN      | Moving south to exit house               │
│ Turn 41 | A         | Interacting with door                     │
│ Turn 40 | DOWN      | Approaching house exit                    │
│ ...                                                              │
└─────────────────────────────────────────────────────────────────┘
```

## 数据面板说明

### 左侧 - 游戏状态 (Game State)

**基础统计**
- Turn: 当前回合数
- Badges: 获得的徽章数量
- Money: 当前金钱
- Party: Pokemon队伍数量

**位置信息**
- Map ID: 当前地图编号
- Coordinates: 精确坐标

**徽章展示**
- 8个徽章的获取状态
- 已获得的徽章高亮显示

**Pokemon队伍**
- 显示每只Pokemon的：
  - 名称和等级
  - 当前HP/最大HP
  - HP百分比进度条（颜色根据HP变化）

**探索进度**
- 当前地图探索百分比
- 已探索/总区块数量

### 中央 - 游戏画面与决策 (Game Screen)

**实时游戏画面**
- Game Boy屏幕实时截图
- 像素完美渲染
- 每回合更新

**最新AI决策**
- 当前行动（大写显示）
- 详细推理过程
- 回合数和时间戳

**视觉分析**
- 屏幕内容描述
- 检测到的UI元素（菜单、文本框、战斗等）

### 右侧 - 目标与事件 (Goals & Events)

**当前目标**
- PRIMARY: 主要目标
- SECONDARY: 次要目标
- TERTIARY: 第三目标

**事件日志**
- 🟠 Milestone: 重要里程碑
- 🟢 Achievement: 成就事件
- 🔴 Error: 错误和问题

### 底部 - 决策历史 (Decision History)

- 显示最近50条AI决策
- 每条包括：
  - 回合数
  - 执行的行动
  - 完整推理过程
  - 时间戳
- 自动滚动，最新的在顶部

## 高级功能

### 实时监控

仪表板会实时显示：
- ✅ Connected: 已连接到AI Agent
- ⚠️ Disconnected: 连接断开（AI停止运行）

### 数据刷新

- WebSocket自动推送更新
- 无需手动刷新页面
- 连接状态实时监控

### 性能优化

- 只保留最近1000条决策历史（内存优化）
- 截图使用base64编码流式传输
- 异步非阻塞更新

## 配置选项

在 `config.yaml` 中配置可视化：

```yaml
visualization:
  enabled: true          # 启用/禁用可视化
  port: 5000            # Web服务器端口
  update_screenshots: true   # 是否更新截图
  update_interval: 1    # 更新频率（每N回合）
```

### 关闭可视化

如果不需要可视化功能：

```yaml
visualization:
  enabled: false
```

这将禁用Web服务器，节省资源。

### 修改端口

如果5000端口被占用：

```yaml
visualization:
  port: 8080  # 使用其他端口
```

## 故障排除

### 无法访问仪表板

**问题**: 浏览器显示"无法访问此网站"

**解决方案**:
1. 确认程序已启动并显示 "Visualization dashboard available"
2. 检查端口是否被占用：`netstat -ano | findstr :5000`
3. 尝试使用 http://127.0.0.1:5000 而不是 localhost
4. 检查防火墙设置

### 连接状态显示 "Disconnected"

**问题**: 仪表板显示已断开连接

**解决方案**:
1. 检查AI Agent是否正在运行
2. 刷新浏览器页面
3. 检查控制台是否有错误信息
4. 重启程序

### 画面不更新

**问题**: 游戏画面或数据不刷新

**解决方案**:
1. 检查 `visualization.enabled` 是否为 `true`
2. 打开浏览器开发者工具（F12）检查WebSocket连接
3. 查看控制台是否有JavaScript错误
4. 清除浏览器缓存后刷新

### 性能问题

**问题**: 仪表板运行缓慢或卡顿

**解决方案**:
1. 降低更新频率（增加 `update_interval`）
2. 关闭截图更新（`update_screenshots: false`）
3. 使用Chrome浏览器（性能更好）
4. 关闭浏览器其他标签页

## 多设备访问

### 在同一局域网内访问

1. 获取运行AI Agent的电脑IP地址：
   ```bash
   ipconfig  # Windows
   ```

2. 在其他设备浏览器中访问：
   ```
   http://192.168.x.x:5000
   ```

### 安全提示

- 可视化服务器运行在 `0.0.0.0`，允许局域网访问
- 不建议暴露到公网（无认证机制）
- 仅用于本地/内网监控

## API接口

仪表板还提供REST API用于自定义集成：

### GET /api/state
获取当前游戏状态
```json
{
  "turn": 42,
  "badges": 2,
  "party_size": 3,
  "money": 5000,
  "position": {"map_id": 1, "x": 10, "y": 5}
}
```

### GET /api/decision
获取最新AI决策
```json
{
  "turn": 42,
  "action": "down",
  "reasoning": "Moving south...",
  "timestamp": "2024-12-11T13:20:00"
}
```

### GET /api/history
获取决策历史
```json
{
  "decisions": [...],
  "total": 42
}
```

### GET /api/screenshot
获取最新截图（base64）
```json
{
  "image": "data:image/png;base64,..."
}
```

### GET /api/goals
获取当前目标
```json
{
  "goals": [
    {"type": "PRIMARY", "description": "Complete Pokemon Red"},
    {"type": "SECONDARY", "description": "Get first Pokemon"}
  ]
}
```

## 技术栈

- **后端**: Flask + Flask-SocketIO
- **前端**: 纯HTML/CSS/JavaScript
- **实时通信**: WebSocket (Socket.IO)
- **数据格式**: JSON
- **图像传输**: Base64编码

## 开发者提示

### 自定义仪表板

仪表板模板位于：`templates/dashboard.html`

可以修改：
- CSS样式（内嵌在`<style>`标签中）
- 布局结构
- JavaScript逻辑

### 添加新数据

在 `src/visualization/visualizer.py` 中：

```python
# 添加新的更新方法
def update_custom_data(self, data):
    if self.running:
        self.socketio.emit('custom_update', data)
```

在 `dashboard.html` 中接收：

```javascript
socket.on('custom_update', (data) => {
    console.log('Custom data:', data);
    // 处理数据
});
```

## 总结

可视化仪表板提供了：
- ✅ 实时监控AI决策过程
- ✅ 直观的游戏状态展示
- ✅ 完整的历史记录追踪
- ✅ 美观的现代化界面
- ✅ 多设备访问支持
- ✅ RESTful API接口

享受观看AI玩Pokemon Red的乐趣！🎮
