# Advanced Usage Guide

This guide covers advanced features and customization options for Pokemon AI Agent.

## Table of Contents

1. [Configuration Options](#configuration-options)
2. [Customizing AI Behavior](#customizing-ai-behavior)
3. [Working with Checkpoints](#working-with-checkpoints)
4. [Memory Management](#memory-management)
5. [Multi-Agent Coordination](#multi-agent-coordination)
6. [Performance Tuning](#performance-tuning)
7. [Extending the System](#extending-the-system)
8. [Debugging and Analysis](#debugging-and-analysis)

## Configuration Options

### Game Settings

```yaml
game:
  rom_path: "PokemonRed.gb"
  speed: 0                    # 0=unlimited, 1=normal, 2+=slower
  headless: false             # true=no window
  save_state_dir: "data/checkpoints"
```

**Speed Control**:
- `0`: Maximum speed (recommended for production)
- `1`: Normal Game Boy speed
- `2-10`: Progressively slower (useful for debugging)

**Headless Mode**:
- `true`: Better performance, no visual
- `false`: Watch AI play in real-time

### AI Model Selection

```yaml
ai:
  model: "claude-sonnet-4-5-20250929"  # Main model
  temperature: 0.7                      # Creativity level
  max_tokens: 4096                      # Response size

  agents:
    main:
      model: "claude-sonnet-4-5-20250929"
      temperature: 0.7
    pathfinder:
      model: "claude-sonnet-4-5-20250929"
      temperature: 0.3        # Lower for deterministic routing
    puzzle_solver:
      model: "claude-sonnet-4-5-20250929"
      temperature: 0.3
    critic:
      model: "claude-sonnet-4-5-20250929"
      temperature: 0.5
```

**Model Options**:
- `claude-sonnet-4-5-20250929`: Best quality, higher cost
- `claude-haiku-20250307`: Faster, cheaper (recommended for cost savings)
- `claude-opus-4-5-20250929`: Maximum capability (expensive)

**Temperature Guide**:
- `0.0-0.3`: Deterministic, consistent
- `0.4-0.7`: Balanced creativity
- `0.8-1.0`: High creativity (may be erratic)

### Memory Settings

```yaml
memory:
  max_context_turns: 100      # Summarize after N turns
  summarization_enabled: true # Enable summarization
  keep_recent_turns: 20       # Full detail for last N
  map_memory_enabled: true
  save_interval: 50           # Save map every N turns
```

**Tuning Considerations**:
- Higher `max_context_turns` = Better memory, more tokens
- Higher `keep_recent_turns` = Better recent context, more tokens
- Disable summarization only for debugging

### Action Settings

```yaml
actions:
  delay_ms: 100              # Delay between button presses
  timeout_seconds: 30        # Max wait for state change
  stuck_threshold: 10        # Repeat action N times = stuck
  screenshot_interval: 1     # Capture every N frames
```

**Stuck Detection**:
- Lower threshold = Faster detection, may false-alarm
- Higher threshold = More patience, slower recovery

### Logging

```yaml
logging:
  level: "INFO"              # DEBUG, INFO, WARNING, ERROR
  log_dir: "logs"
  log_actions: true
  log_states: true
  log_decisions: true
  save_screenshots: true
  screenshot_dir: "logs/screenshots"
```

**Log Levels**:
- `DEBUG`: Everything (verbose, large files)
- `INFO`: Normal operation (recommended)
- `WARNING`: Only issues
- `ERROR`: Only errors

## Customizing AI Behavior

### Modifying System Prompts

Edit the agent's decision-making by changing system prompts:

**Main Agent** (`src/agents/main_agent.py`):

```python
SYSTEM_PROMPT = """You are an AI agent playing Pokemon Red...

[Add custom instructions here]

Examples:
- "Always catch every Pokemon you encounter"
- "Prioritize leveling up before gym battles"
- "Avoid random trainer battles when possible"
"""
```

### Setting Custom Goals

Programmatically set goals:

```python
from src.tools.goal_manager import GoalManager

goals = GoalManager()

# Set specific goals
goals.set_primary_goal("Defeat Brock and earn Boulder Badge")
goals.set_secondary_goal("Catch a Geodude or Onix")
goals.set_tertiary_goal("Level Charmander to 15")
```

Or edit `config.yaml`:

```yaml
goals:
  primary_goal: "Your custom primary goal"
  secondary_goal: "Your custom secondary goal"
  tertiary_goal: null
```

### Adjusting Battle Strategy

Modify main agent prompt to emphasize battle tactics:

```python
SYSTEM_PROMPT = """...

Battle Guidelines:
1. Always use type advantages
2. Switch when HP < 30%
3. Preserve PP for important battles
4. Use status moves strategically
5. Catch weakened Pokemon instead of defeating them

...
"""
```

## Working with Checkpoints

### Manual Checkpointing

```python
# In main.py or custom script
agent = PokemonAIAgent()

# Save checkpoint
agent._save_checkpoint()

# Load checkpoint
checkpoint_dir = "data/checkpoints/checkpoint_1000"
agent.main_agent.load_state(checkpoint_dir)
agent.emulator.load_state(f"{checkpoint_dir}/emulator.state")
```

### Checkpoint Strategy

**Frequent Checkpoints**:
- Good: Less progress lost on crash
- Bad: More disk I/O, slower

**Infrequent Checkpoints**:
- Good: Faster execution
- Bad: More replay on crash

**Recommended**:
```yaml
progress:
  checkpoint_interval: 100  # Balance between safety and speed
```

### Recovering from Checkpoint

```bash
# List available checkpoints
ls data/checkpoints/

# Manually load specific checkpoint
# (Modify main.py to load specific checkpoint on start)
```

## Memory Management

### Understanding Summarization

Every `max_context_turns` turns:

1. Agent identifies turns to summarize (all but last `keep_recent_turns`)
2. Calls Summarizer to compress them
3. Adds summary to history
4. Discards detailed turns
5. Continues with summarized context

**Example**:

```
Turn 1-100: [full detail]
Turn 100: Summarize → "Started in Pallet Town, got Charmander, ..."
Turn 101-200: [full detail]
Turn 200: Summarize → "Traveled to Pewter City, defeated Brock, ..."
...
```

### Custom Summarization

Edit `src/memory/summarizer.py` to change summary style:

```python
prompt = f"""Summarize the following gameplay focusing on:
- Pokemon caught (species and levels)
- Items acquired
- Battles won/lost
- Locations explored
- Puzzles solved

{turn_data}
"""
```

### Disabling Summarization

For short sessions or debugging:

```yaml
memory:
  summarization_enabled: false
  max_context_turns: 1000  # Large number
```

**Warning**: Extremely high token usage!

## Multi-Agent Coordination

### When Agents Are Called

**Main Agent**: Every turn, makes all decisions

**Pathfinder**: Called by main agent when:
- Complex navigation needed
- Stuck in maze
- Multi-map routing required

**Puzzle Solver**: Called when:
- Boulder puzzle detected
- Ice puzzle encountered
- Complex switch mechanism

**Critic**: Called when:
- Stuck detected (10+ repeated actions)
- Manual trigger
- Periodic evaluation (optional)

### Manual Agent Invocation

```python
# In custom orchestration code
from src.agents.pathfinder import PathfinderAgent

pathfinder = PathfinderAgent()

# Find path
start = (40, 5, 10)   # (map_id, x, y)
target = (40, 15, 20)
explored = map_memory.get_explored_tiles(40)

path = pathfinder.find_path(start, target, explored)

# Execute path
for move in path:
    action_executor.execute(move)
```

### Coordinated Decision Making

Implement consensus or voting:

```python
# Get decisions from multiple agents
main_decision = main_agent.decide_action(state, state_text)
critic_eval = critic.critique(history, state)

# Combine decisions
if "stuck" in critic_eval['issues']:
    # Override with pathfinder
    path = pathfinder.find_path(...)
    action = path[0]
else:
    action = main_decision['action']
```

## Performance Tuning

### Optimizing for Speed

**Maximum Speed Configuration**:

```yaml
game:
  speed: 0             # Unlimited
  headless: true       # No rendering

ai:
  model: "claude-haiku-20250307"  # Faster model

actions:
  delay_ms: 50         # Minimal delay

logging:
  level: "WARNING"     # Less logging
  save_screenshots: false

memory:
  max_context_turns: 50
  keep_recent_turns: 10
```

### Optimizing for Cost

**Budget Configuration**:

```yaml
ai:
  model: "claude-haiku-20250307"  # Cheapest model
  max_tokens: 2048     # Lower token limit

memory:
  max_context_turns: 50
  keep_recent_turns: 10

actions:
  delay_ms: 500        # Fewer actions per minute
```

### Optimizing for Quality

**Maximum Quality Configuration**:

```yaml
ai:
  model: "claude-sonnet-4-5-20250929"
  temperature: 0.7
  max_tokens: 8192     # Longer responses

memory:
  max_context_turns: 200
  keep_recent_turns: 50

logging:
  level: "DEBUG"
  save_screenshots: true
```

## Extending the System

### Adding New Memory Addresses

1. Find address in Pokemon Red RAM map
2. Add to `data/memory_addresses.json`:

```json
{
  "custom_data": {
    "my_value": {
      "address": "0xD123",
      "type": "uint8"
    }
  }
}
```

3. Add reader method in `src/emulator/memory_reader.py`:

```python
def read_my_value(self) -> int:
    address = int(self.memory_map['custom_data']['my_value']['address'], 16)
    return self.emulator.read_memory(address)
```

4. Use in game state:

```python
my_value = self.memory_reader.read_my_value()
```

### Creating Custom Agents

```python
# src/agents/my_agent.py
from anthropic import Anthropic
from ..utils.logger import get_logger

class MyAgent:
    SYSTEM_PROMPT = """Your custom agent prompt"""

    def __init__(self):
        self.logger = get_logger('MyAgent')
        self.client = Anthropic()

    def process(self, input_data):
        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{"role": "user", "content": input_data}]
        )
        return response.content[0].text
```

### Adding New Tools

```python
# src/tools/my_tool.py
class MyTool:
    def __init__(self):
        self.logger = get_logger('MyTool')

    def do_something(self, params):
        # Your custom logic
        pass
```

### Custom Action Sequences

```python
# Define action macros
MACROS = {
    'open_menu': ['start'],
    'select_pokemon': ['start', 'down', 'a'],
    'use_item': ['start', 'down', 'down', 'a'],
}

# Execute macro
for action in MACROS['open_menu']:
    action_executor.execute(action)
```

## Debugging and Analysis

### Verbose State Logging

```python
# In main.py
def _game_loop_iteration(self):
    current_state = self.game_state.update()

    # Log full state
    self.logger.debug(f"Full state: {current_state}")

    # Log specific aspects
    self.logger.debug(f"Position: {current_state['memory']['position']}")
    self.logger.debug(f"Party: {current_state['memory']['party']}")
```

### Decision Tracing

```python
# Enable decision logging
self.config.set('logging.log_decisions', True)

# In agent, add detailed logging
self.logger.decision(
    action=decision['action'],
    reasoning=f"Full reasoning: {decision['reasoning']}"
)
```

### Action Replay

Save all actions:

```python
# In action_executor.py
self.action_history_file = open('action_replay.txt', 'w')

def execute(self, action):
    # Save action
    self.action_history_file.write(f"{action}\n")
    self.action_history_file.flush()
    # ... execute ...
```

Replay actions:

```python
with open('action_replay.txt', 'r') as f:
    for line in f:
        action = line.strip()
        action_executor.execute(action)
```

### Memory Dump Analysis

```python
# Dump raw memory
def dump_memory(self):
    with open('memory_dump.bin', 'wb') as f:
        for addr in range(0x10000):
            byte = self.emulator.read_memory(addr)
            f.write(bytes([byte]))
```

### Analyzing Checkpoints

```python
import json

# Load checkpoint
with open('data/checkpoints/checkpoint_1000/context.json', 'r') as f:
    context = json.load(f)

# Analyze
print(f"Summaries: {len(context['summaries'])}")
print(f"Recent turns: {len(context['recent_turns'])}")

# Print summaries
for summary in context['summaries']:
    print(summary)
```

## Advanced Techniques

### Curriculum Learning

Start with easier goals, progressively harder:

```python
goals = [
    "Leave Pallet Town",
    "Reach Viridian City",
    "Defeat Brock",
    "Reach Cerulean City",
    # ...
]

for goal in goals:
    goal_manager.set_primary_goal(goal)
    # Run until goal achieved
    while not goal_achieved():
        agent._game_loop_iteration()
```

### A/B Testing Strategies

```python
# Test different prompts
prompts = [
    "Aggressive strategy: ...",
    "Defensive strategy: ...",
    "Balanced strategy: ..."
]

for prompt in prompts:
    agent.main_agent.SYSTEM_PROMPT = prompt
    # Run for N turns
    # Compare performance
```

### Ensemble Agents

```python
# Get decisions from multiple agents
decisions = []
for agent in [agent1, agent2, agent3]:
    decision = agent.decide_action(state, state_text)
    decisions.append(decision)

# Vote or average
final_action = majority_vote(decisions)
```

## Best Practices

1. **Start Small**: Test with 10-100 turns before long runs
2. **Monitor Costs**: Check API usage regularly
3. **Use Checkpoints**: Save frequently to prevent data loss
4. **Review Logs**: Analyze decision quality
5. **Iterate Prompts**: Continuously improve based on results
6. **Track Metrics**: Monitor badges/hour, stuck frequency
7. **Version Control**: Git commit config changes
8. **Document Changes**: Note what works and what doesn't

## Troubleshooting Common Issues

See `docs/TROUBLESHOOTING.md` for detailed solutions.

## Further Reading

- `docs/ARCHITECTURE.md`: Technical architecture
- `docs/QUICK_START.md`: Getting started guide
- `docs/TROUBLESHOOTING.md`: Problem solving
- Source code documentation in `src/` modules

Happy Pokemon training!
