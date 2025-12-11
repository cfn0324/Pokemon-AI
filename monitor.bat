@echo off
REM Pokemon AI Agent 监控脚本 (Windows)

echo ==========================================
echo Pokemon AI Agent 运行状态监控
echo ==========================================
echo.

REM 检查进程
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *main.py*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ✓ 状态: 运行中
) else (
    echo × 状态: 未运行
    exit /b 1
)

echo.
echo 📊 最新日志 (最后 10 行):
echo ------------------------------------------
if exist pokemon_ai.log (
    powershell -Command "Get-Content pokemon_ai.log -Tail 10"
)

echo.
echo 🎮 AI 最新决策:
echo ------------------------------------------
if exist logs\MainAgent_*.log (
    findstr /C:"DECISION:" logs\MainAgent_*.log | powershell -Command "$input | Select-Object -Last 3"
)

echo.
echo 📈 进度统计:
echo ------------------------------------------
if exist data\checkpoints\checkpoint_*\progress.json (
    type data\checkpoints\checkpoint_*\progress.json | findstr /C:"total_turns" /C:"badge"
) else (
    echo 暂无检查点数据
)

echo.
echo 💾 最新检查点:
echo ------------------------------------------
dir /B /O:D data\checkpoints | powershell -Command "$input | Select-Object -Last 3"

echo.
echo ==========================================
echo 监控脚本运行完毕
echo ==========================================
pause
