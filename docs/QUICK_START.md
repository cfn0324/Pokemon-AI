# Quick Start Guide

This guide will help you get the Pokemon AI Agent running quickly.

## Prerequisites

1. **Python 3.9+** - [Download Python](https://www.python.org/downloads/)
2. **Anthropic API Key** - [Get one here](https://console.anthropic.com/)
3. **Pokemon Red ROM** - You must legally own this

## Installation Steps

### 1. Set up API Key

**Option A: Environment Variable (Recommended)**

Windows:
```cmd
set ANTHROPIC_API_KEY=your-api-key-here
```

Linux/Mac:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

**Option B: .env File**

Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your-api-key-here
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or use virtual environment (recommended):

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Add Pokemon Red ROM

Place `PokemonRed.gb` in the project root directory.

### 4. Test Setup

```bash
python test_setup.py
```

This will verify:
- Python version
- Dependencies
- API key
- ROM file
- Configuration
- API connection

### 5. Run the Agent

**Windows:**
```cmd
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

**Or directly:**
```bash
python main.py
```

## What to Expect

When you run the agent, you'll see:

1. **Initialization**: Loading all components
2. **Game Start**: Emulator window opens (unless headless mode)
3. **AI Decisions**: Colored log output showing:
   - Green: Info messages
   - Yellow: Warnings
   - Red: Errors
   - Cyan: Debug info

4. **Progress Updates**: Every 10 turns, you'll see:
   - Current position
   - Badge count
   - Pokemon party status
   - Exploration progress

5. **Checkpoints**: Auto-saved every 100 turns

## Configuration

Edit `config.yaml` to customize:

### Speed Control
```yaml
game:
  speed: 0  # 0=unlimited, 1=normal, 2+=slower
  headless: false  # true to run without window
```

### AI Model
```yaml
ai:
  model: "claude-sonnet-4-5-20250929"
  temperature: 0.7  # Higher = more creative
```

### Memory Management
```yaml
memory:
  max_context_turns: 100  # Summarize after N turns
  keep_recent_turns: 20   # Keep last N in detail
```

### Logging
```yaml
logging:
  level: "INFO"  # DEBUG for more detail
  save_screenshots: true
```

## Monitoring Progress

### Log Files
All logs are saved to `logs/` directory:
- `Main_TIMESTAMP.log` - Main execution log
- `MainAgent_TIMESTAMP.log` - AI decision log
- etc.

### Screenshots
If enabled, screenshots saved to `logs/screenshots/`:
- `turn_XXXXXX.png` - Screen with grid overlay

### Checkpoints
Saved to `data/checkpoints/checkpoint_TURN/`:
- `emulator.state` - Emulator save state
- `context.json` - AI context
- `goals.json` - Current goals
- `progress.json` - Progress statistics

### Progress Tracking
Check `data/checkpoints/latest/progress.json` for:
- Badges earned
- Pokemon caught
- Total turns
- Milestone turns

## Common First-Run Issues

### "Module not found"
```bash
pip install -r requirements.txt
```

### "API key not set"
Make sure to export the environment variable or create `.env` file.

### "ROM file not found"
Place `PokemonRed.gb` in project root (same directory as `main.py`).

### Emulator window doesn't open
Set `headless: false` in config.yaml.

### Agent is very slow
- Increase `speed` in config.yaml
- Use faster model (haiku instead of sonnet)
- Disable screenshot saving

### High API costs
- Lower `max_context_turns` to reduce token usage
- Use Claude Haiku instead of Sonnet (cheaper)
- Add delays: `delay_ms: 500`

## Stopping the Agent

Press `Ctrl+C` to gracefully stop.

The agent will:
1. Save a final checkpoint
2. Close the emulator
3. Print final statistics

## Next Steps

Once running:
1. Monitor the logs to see AI reasoning
2. Check progress every 100 turns
3. Watch badge acquisition
4. Review checkpoints to see advancement

## Getting Help

- Check `docs/TROUBLESHOOTING.md`
- Review logs in `logs/` directory
- Open an issue on GitHub

## Performance Expectations

Based on Gemini project benchmarks:
- **Time to first badge**: ~10-50 hours
- **Full game completion**: ~400-800 hours
- **Token usage**: Millions of tokens
- **Cost**: Varies with model (Sonnet vs Haiku)

The agent runs 24/7, so actual calendar time depends on your setup.

Enjoy watching your AI play Pokemon!
