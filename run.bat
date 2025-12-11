@echo off
echo ========================================
echo Pokemon AI Agent - Quick Start
echo ========================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Check for API key
if not defined ANTHROPIC_API_KEY (
    echo ERROR: ANTHROPIC_API_KEY environment variable not set
    echo.
    echo Please set it with:
    echo   set ANTHROPIC_API_KEY=your-api-key-here
    echo.
    echo Or create a .env file with:
    echo   ANTHROPIC_API_KEY=your-api-key-here
    echo.
    pause
    exit /b 1
)

REM Check for ROM
if not exist "PokemonRed.gb" (
    echo ERROR: PokemonRed.gb not found
    echo Please place the Pokemon Red ROM in this directory
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting Pokemon AI Agent...
echo.
python main.py

pause
