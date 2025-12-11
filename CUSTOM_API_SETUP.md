# 配置自定义 API 端点

您的项目现在已配置为使用自定义 API 端点！

## ✅ 已完成的配置

1. **创建 .env 文件**：
   - API Key: `sk-xaz4XmC20cXqqRbO6Kq8q4tXiw0lPk6zBmePWSsdgojNgxB5`
   - API 端点: `https://api.ququ233.com/v1`

2. **更新所有 AI 代理**以支持自定义端点：
   - MainAgent
   - PathfinderAgent
   - PuzzleSolverAgent
   - CriticAgent
   - Summarizer

3. **添加自动加载 .env 文件**的功能

## 🚀 快速开始

### 1. 确保安装了 python-dotenv

```bash
pip install python-dotenv
```

或者重新安装所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 验证配置

```bash
python test_setup.py
```

这会检查：
- ✅ API 密钥是否正确设置
- ✅ 能否连接到自定义 API 端点
- ✅ 所有依赖是否安装

### 3. 启动 AI 代理

```bash
python main.py
```

或使用快速启动脚本：

**Windows:**
```cmd
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

## 📝 配置详情

### .env 文件内容

```env
ANTHROPIC_API_KEY=sk-xaz4XmC20cXqqRbO6Kq8q4tXiw0lPk6zBmePWSsdgojNgxB5
ANTHROPIC_BASE_URL=https://api.ququ233.com/v1
```

### 工作原理

所有 AI 代理在初始化时会：

1. 检查是否设置了 `ANTHROPIC_BASE_URL` 环境变量
2. 如果设置了，使用自定义端点
3. 如果没有设置，使用默认的 Anthropic API

代码示例：
```python
import os
base_url = os.getenv('ANTHROPIC_BASE_URL')
if base_url:
    self.client = Anthropic(base_url=base_url)
else:
    self.client = Anthropic()
```

## ⚙️ 配置模型

如果您的自定义 API 支持不同的模型，可以在 `config.yaml` 中修改：

```yaml
ai:
  model: "claude-sonnet-4-5-20250929"  # 或您的 API 支持的其他模型
  temperature: 0.7
  max_tokens: 4096
```

## 🔍 测试 API 连接

运行测试脚本会自动测试 API 连接：

```bash
python test_setup.py
```

输出示例：
```
Testing API connection... OK
  Using custom endpoint: https://api.ququ233.com/v1
```

## 📊 监控

启动后，日志会显示使用的 API 端点：

```
2024-12-11 11:45:00 - MainAgent - INFO - Using custom API endpoint: https://api.ququ233.com/v1
```

## 🛠️ 故障排除

### 如果 API 连接失败

1. **检查端点 URL**：
   ```bash
   echo $ANTHROPIC_BASE_URL
   # 应该显示: https://api.ququ233.com/v1
   ```

2. **检查 API 密钥**：
   ```bash
   echo $ANTHROPIC_API_KEY
   # 应该显示您的密钥
   ```

3. **测试 API 直接访问**：
   ```bash
   curl https://api.ququ233.com/v1/messages \
     -H "x-api-key: sk-xaz4XmC20cXqqRbO6Kq8q4tXiw0lPk6zBmePWSsdgojNgxB5" \
     -H "anthropic-version: 2023-06-01" \
     -H "content-type: application/json" \
     -d '{
       "model": "claude-sonnet-4-5-20250929",
       "max_tokens": 1024,
       "messages": [{"role": "user", "content": "Hello"}]
     }'
   ```

### 如果 .env 未加载

确保 `python-dotenv` 已安装：

```bash
pip install python-dotenv
```

### 如果模型不支持

您的 API 可能使用不同的模型名称。检查 API 文档并更新 `config.yaml`：

```yaml
ai:
  model: "your-supported-model-name"
```

## 💡 提示

1. **保护 API 密钥**：
   - 不要提交 `.env` 文件到 Git
   - `.gitignore` 已配置忽略 `.env`

2. **备份配置**：
   - 保存 `.env` 文件的副本（安全位置）
   - 记录您的 API 端点和密钥

3. **成本监控**：
   - 监控您的 API 使用情况
   - 检查自定义 API 的计费

## ✨ 现在可以开始了！

所有配置已完成，您可以：

```bash
# 1. 测试设置
python test_setup.py

# 2. 启动 AI 代理
python main.py
```

AI 将开始玩 Pokemon Red，使用您的自定义 API 端点！

## 📚 相关文档

- **快速开始**: `docs/QUICK_START.md`
- **配置说明**: `docs/ADVANCED_USAGE.md`
- **故障排除**: `docs/TROUBLESHOOTING.md`
- **架构详情**: `docs/ARCHITECTURE.md`

祝您的 AI 代理玩得愉快！🎮🤖
