#!/bin/bash
# Pokemon AI Agent 监控脚本

echo "=========================================="
echo "Pokemon AI Agent 运行状态监控"
echo "=========================================="
echo ""

# 检查进程
if pgrep -f "python main.py" > /dev/null; then
    echo "✅ 状态: 运行中"
else
    echo "❌ 状态: 未运行"
    exit 1
fi

echo ""
echo "📊 最新日志 (最后 10 行):"
echo "------------------------------------------"
tail -10 pokemon_ai.log

echo ""
echo "🎮 AI 最新决策:"
echo "------------------------------------------"
grep "DECISION:" logs/MainAgent_*.log | tail -3

echo ""
echo "📈 进度统计:"
echo "------------------------------------------"
if [ -f "data/checkpoints/checkpoint_*/progress.json" ]; then
    cat data/checkpoints/checkpoint_*/progress.json | grep -E "total_turns|badge"
else
    echo "暂无检查点数据"
fi

echo ""
echo "💾 检查点:"
echo "------------------------------------------"
ls -lh data/checkpoints/ | tail -5

echo ""
echo "📁 日志文件:"
echo "------------------------------------------"
ls -lh logs/*.log | tail -5

echo ""
echo "=========================================="
echo "监控脚本运行完毕"
echo "=========================================="
