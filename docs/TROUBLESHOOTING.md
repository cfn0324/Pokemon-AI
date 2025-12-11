# Troubleshooting Guide

Common issues and solutions for Pokemon AI Agent.

## Installation Issues

### Python Version Too Old

**Error:**
```
Python 3.9+ required, found 3.7
```

**Solution:**
- Install Python 3.9 or higher from [python.org](https://www.python.org/downloads/)
- Update PATH to use newer version
- Create new virtual environment with correct version

### Dependency Installation Fails

**Error:**
```
ERROR: Could not find a version that satisfies the requirement pyboy
```

**Solution:**
```bash
# Update pip
python -m pip install --upgrade pip

# Install dependencies one by one
pip install anthropic
pip install pyboy
pip install pillow numpy pyyaml colorlog opencv-python
```

**If PyBoy fails on Windows:**
```bash
# Install build tools
pip install wheel
# Then try again
pip install pyboy
```

### SDL2 Error (PyBoy)

**Error:**
```
SDL2 library not found
```

**Solution:**

**Windows:**
- PyBoy usually includes SDL2
- If not, download SDL2.dll from [libsdl.org](https://www.libsdl.org/)

**Linux:**
```bash
sudo apt-get install libsdl2-dev
```

**Mac:**
```bash
brew install sdl2
```

## API Issues

### API Key Not Found

**Error:**
```
ANTHROPIC_API_KEY environment variable not set
```

**Solution:**

**Temporary (current session only):**
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-...

# Linux/Mac
export ANTHROPIC_API_KEY='sk-ant-...'
```

**Permanent:**

Create `.env` file in project root:
```
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Or set system environment variable.

### API Authentication Failed

**Error:**
```
401 Unauthorized
```

**Solution:**
- Verify API key is correct
- Check API key hasn't expired
- Ensure no extra spaces in key
- Regenerate key at [console.anthropic.com](https://console.anthropic.com/)

### Rate Limit Exceeded

**Error:**
```
429 Too Many Requests
```

**Solution:**
- Wait a few minutes
- Add delays in `config.yaml`:
  ```yaml
  actions:
    delay_ms: 500  # Slow down actions
  ```
- Check your API rate limits

### High API Costs

**Issue:**
Running the agent is expensive.

**Solution:**

1. **Use Haiku instead of Sonnet:**
   ```yaml
   ai:
     model: "claude-haiku-20250307"  # Much cheaper
   ```

2. **Reduce context window:**
   ```yaml
   memory:
     max_context_turns: 50  # Lower = less tokens
     keep_recent_turns: 10
   ```

3. **Add delays:**
   ```yaml
   actions:
     delay_ms: 1000  # Slower = fewer API calls
   ```

4. **Set budget limit:**
   - Configure in Anthropic console
   - Stop agent when budget reached

## ROM Issues

### ROM Not Found

**Error:**
```
ROM file not found: PokemonRed.gb
```

**Solution:**
- Place `PokemonRed.gb` in project root directory
- Verify filename is exactly `PokemonRed.gb`
- Check file permissions

### ROM Won't Load

**Error:**
```
Failed to load ROM
```

**Solution:**
- Verify ROM is Pokemon Red (not Blue/Yellow)
- Check file size is 1MB (1,048,576 bytes)
- Try different ROM version (USA, Europe, etc.)
- Ensure ROM is not corrupted

### Wrong ROM Version

**Issue:**
Memory addresses don't match.

**Solution:**
- Use Pokemon Red (USA) version
- Update `data/memory_addresses.json` for your version
- Check ROM checksum

## Runtime Issues

### Agent Gets Stuck

**Issue:**
Agent repeats same action endlessly.

**Solution:**

1. **Automatic detection:**
   - Agent should detect stuck state after 10 repetitions
   - Critic agent will evaluate

2. **Manual intervention:**
   - Press Ctrl+C to stop
   - Load previous checkpoint
   - Adjust stuck threshold in config:
     ```yaml
     actions:
       stuck_threshold: 5  # Lower = faster detection
     ```

3. **Improve prompts:**
   - Edit `src/agents/main_agent.py`
   - Add more stuck-avoidance guidance

### Agent Makes Poor Decisions

**Issue:**
AI keeps making suboptimal choices.

**Solution:**

1. **Increase temperature:**
   ```yaml
   ai:
     temperature: 0.9  # More exploration
   ```

2. **Provide better context:**
   - Ensure memory management is working
   - Check summaries are informative

3. **Use Critic more frequently:**
   - Lower stuck threshold
   - Manually trigger critique

### Emulator Crashes

**Error:**
```
Segmentation fault
PyBoy crashed
```

**Solution:**
- Update PyBoy: `pip install --upgrade pyboy`
- Try headless mode:
  ```yaml
  game:
    headless: true
  ```
- Check for memory issues
- Restart from checkpoint

### Memory Issues (RAM)

**Error:**
```
MemoryError
Out of memory
```

**Solution:**
- Close other applications
- Reduce screenshot saving
- Lower context window size
- Increase system swap space
- Use headless mode

### Slow Performance

**Issue:**
Agent runs very slowly.

**Solution:**

1. **Speed up emulation:**
   ```yaml
   game:
     speed: 0  # Unlimited speed
   ```

2. **Reduce API calls:**
   - Add action delays
   - Cache decisions

3. **Use faster model:**
   ```yaml
   ai:
     model: "claude-haiku-20250307"  # Faster
   ```

4. **Disable logging:**
   ```yaml
   logging:
     level: "WARNING"  # Less verbose
     save_screenshots: false
   ```

## State Management Issues

### Checkpoints Won't Load

**Error:**
```
Failed to load checkpoint
```

**Solution:**
- Verify checkpoint directory exists
- Check file permissions
- Ensure all files present:
  - `emulator.state`
  - `context.json`
  - `goals.json`
  - `progress.json`
- Try loading older checkpoint

### Map Memory Corrupted

**Issue:**
Map exploration data is wrong.

**Solution:**
```bash
# Delete map memory
rm data/maps/map_memory.json

# Agent will rebuild from scratch
```

### Context Lost

**Issue:**
Agent forgets previous progress.

**Solution:**
- Check `max_context_turns` is reasonable (100)
- Verify summarization is working
- Load from checkpoint if available
- Check logs for summarization errors

## Gameplay Issues

### Can't Progress Past Obstacle

**Issue:**
Agent can't solve a puzzle or navigate area.

**Solution:**

1. **Use specialized agents:**
   - Manually trigger pathfinder
   - Use puzzle solver for boulder puzzles

2. **Manual intervention:**
   - Load game state
   - Manually complete section
   - Save state
   - Let agent continue

3. **Adjust goals:**
   - Set more specific secondary goals
   - Break down complex tasks

### Battles Are Lost

**Issue:**
Pokemon keep fainting.

**Solution:**

1. **Better strategy prompts:**
   - Edit battle instructions in main_agent.py
   - Emphasize HP management

2. **Manual training:**
   - Pause agent
   - Manually level up Pokemon
   - Resume

3. **Adjust party:**
   - Guide agent to catch better Pokemon
   - Set goals for team building

## Logging Issues

### Log Files Too Large

**Issue:**
Logs consuming too much disk space.

**Solution:**
- Reduce log level to WARNING or ERROR
- Disable screenshot saving
- Periodically archive old logs
- Use log rotation

### Can't Find Logs

**Issue:**
Where are the logs?

**Solution:**
Logs are in `logs/` directory:
- `Main_TIMESTAMP.log` - Main log
- `Emulator_TIMESTAMP.log` - Emulator log
- `MainAgent_TIMESTAMP.log` - AI decisions
- etc.

Configure log directory in `config.yaml`:
```yaml
logging:
  log_dir: "logs"
```

## Configuration Issues

### Config File Invalid

**Error:**
```
Error loading config: YAML parse error
```

**Solution:**
- Check YAML syntax (indentation, colons)
- Validate at [yamllint.com](http://www.yamllint.com/)
- Restore from backup:
  ```bash
  git checkout config.yaml
  ```

### Config Changes Ignored

**Issue:**
Changes to config.yaml don't take effect.

**Solution:**
- Restart the agent
- Verify you're editing correct config.yaml
- Check for syntax errors
- Delete cache: `rm -rf data/cache/*`

## Debug Strategies

### Enable Verbose Logging

```yaml
logging:
  level: "DEBUG"
debug:
  enabled: true
  verbose_state: true
  save_ram_dumps: true
```

### Monitor Specific Components

```python
# In main.py, add:
self.logger.debug(f"State: {current_state}")
self.logger.debug(f"Decision: {decision}")
```

### Step Through Manually

```python
# Add breakpoints:
import pdb; pdb.set_trace()
```

### Check Memory Addresses

```python
# Test memory reading:
from src.emulator.memory_reader import MemoryReader
# ... initialize ...
state = memory_reader.get_game_state_summary()
print(state)
```

## Getting Help

If issues persist:

1. **Check Logs:**
   - Review full logs in `logs/` directory
   - Look for ERROR or WARNING messages

2. **Run Test Script:**
   ```bash
   python test_setup.py
   ```

3. **Minimal Reproduction:**
   - Start fresh project
   - Minimal config
   - Test specific component

4. **Report Issue:**
   - Include Python version
   - Include full error message
   - Include relevant logs
   - Describe what you tried

5. **Community:**
   - GitHub Issues
   - Discord (if available)
   - Stack Overflow

## Emergency Recovery

### Complete Reset

```bash
# Backup important data
cp -r data/checkpoints backup/

# Clean everything
rm -rf data/maps/*.json
rm -rf data/cache/*
rm -rf logs/*

# Restart agent
python main.py
```

### Restore from Checkpoint

```bash
# Copy checkpoint files
cp data/checkpoints/checkpoint_1000/emulator.state .

# Load in PyBoy manually
# Or restart agent, it will auto-load
```

### Nuclear Option

```bash
# Complete reinstall
rm -rf venv/
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python test_setup.py
```

## Known Limitations

1. **Vision Processing:**
   - Current implementation is basic
   - May not detect all UI elements
   - Relies heavily on RAM data

2. **Pathfinding:**
   - Can struggle with complex mazes
   - May need manual intervention for Victory Road

3. **Battle Strategy:**
   - Not optimal
   - Doesn't use advanced tactics
   - May waste PP

4. **Cost:**
   - Can be expensive with Sonnet model
   - Monitor API usage closely

5. **Time:**
   - Takes hundreds of hours for full playthrough
   - Requires continuous running

## Performance Optimization Checklist

- [ ] Use Claude Haiku for cost savings
- [ ] Set `headless: true` to save resources
- [ ] Disable screenshot saving
- [ ] Lower `max_context_turns` to 50
- [ ] Reduce log level to WARNING
- [ ] Add action delays (500ms+)
- [ ] Close unnecessary applications
- [ ] Monitor API costs regularly
- [ ] Use checkpoints to prevent rework
- [ ] Consider pausing overnight if expensive

Happy troubleshooting!
