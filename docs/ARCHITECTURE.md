# Architecture Documentation

## System Overview

Pokemon AI Agent is a multi-agent AI system that autonomously plays Pokemon Red using advanced reasoning, memory management, and specialized sub-agents.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Orchestrator                        │
│                   (PokemonAIAgent)                          │
└───────────────┬────────────────────────────────────┬────────┘
                │                                     │
       ┌────────▼────────┐                  ┌────────▼────────┐
       │  Emulator Layer │                  │   AI Layer      │
       └────────┬────────┘                  └────────┬────────┘
                │                                     │
    ┌───────────┼───────────┐              ┌────────┼────────┐
    │           │           │              │        │        │
┌───▼───┐ ┌────▼─────┐ ┌──▼────┐    ┌────▼─┐ ┌───▼──┐ ┌──▼──┐
│PyBoy  │ │  Memory  │ │Vision │    │Main  │ │Path  │ │Critic│
│       │ │  Reader  │ │       │    │Agent │ │finder│ │      │
└───┬───┘ └────┬─────┘ └──┬────┘    └────┬─┘ └───┬──┘ └──┬──┘
    │          │           │              │       │       │
    └──────────┴───────────┴──────────────┴───────┴───────┘
                           │
                  ┌────────▼────────┐
                  │  State Manager  │
                  │  - Game State   │
                  │  - Map Memory   │
                  │  - Context Mgr  │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Tool Layer     │
                  │  - Goals        │
                  │  - Actions      │
                  │  - Progress     │
                  └─────────────────┘
```

## Component Details

### 1. Emulator Layer

#### GameBoyEmulator (`src/emulator/game_boy.py`)
- **Purpose**: Wraps PyBoy emulator for Pokemon Red
- **Key Features**:
  - Button press simulation
  - Screen capture (160x144 pixels)
  - Memory read/write access
  - Save state management
- **Dependencies**: PyBoy

**Key Methods**:
```python
press_button(button: str, duration: int)  # Simulate button press
get_screen_image() -> Image               # Capture screen
read_memory(address: int) -> int          # Read RAM
save_state(filename: str)                 # Save emulator state
```

#### MemoryReader (`src/emulator/memory_reader.py`)
- **Purpose**: Reads Pokemon Red game state from RAM
- **Key Features**:
  - Player position tracking
  - Badge status monitoring
  - Pokemon party reading
  - Battle detection
- **Data Source**: `data/memory_addresses.json`

**Key Methods**:
```python
read_player_position() -> Dict            # Get (x, y, map_id)
read_badges() -> Dict[str, bool]          # Badge status
read_party() -> List[Dict]                # Pokemon team data
get_game_state_summary() -> Dict          # Comprehensive state
```

### 2. State Layer

#### GameState (`src/state/game_state.py`)
- **Purpose**: Central state processor combining all data sources
- **Key Features**:
  - Merges memory data + visual analysis
  - Updates map memory
  - Generates text representation for AI
  - Turn tracking

**Data Flow**:
```
RAM Data ──┐
           ├──> GameState ──> Text Representation ──> AI
Vision ────┤
           │
Map Memory─┘
```

#### VisionProcessor (`src/state/vision.py`)
- **Purpose**: Analyzes game screen visually
- **Key Features**:
  - Grid overlay (16x16 tiles)
  - UI element detection (menus, text boxes, battles)
  - Screen description generation
  - Annotated screenshot saving

**Detection Logic**:
- Text boxes: Dark regions at bottom of screen
- Menus: High percentage of white pixels
- Battles: Specific layout patterns

#### MapMemory (`src/state/map_memory.py`)
- **Purpose**: Fog-of-war exploration tracking
- **Key Features**:
  - Tracks explored tiles per map
  - Identifies nearby unexplored areas
  - Persistence (JSON storage)
  - Exploration statistics

**Data Structure**:
```python
{
  map_id: Set[(x, y), (x, y), ...]  # Explored tiles
}
```

### 3. AI Agent Layer

#### MainAgent (`src/agents/main_agent.py`)
- **Purpose**: Primary decision-making agent
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.7 (configurable)

**Decision Loop**:
```
1. Receive game state
2. Get context (summaries + recent history)
3. Get current goals
4. Call Claude API with prompt
5. Parse response (reasoning + action)
6. Add to context
7. Return decision
```

**Response Format**:
```
REASONING: <analysis>
ACTION: <button to press>
GOAL_UPDATE: <goal changes or "none">
```

**Context Management**:
- Every 100 turns: Trigger summarization
- Keep last 20 turns in full detail
- Older turns compressed into summaries

#### PathfinderAgent (`src/agents/pathfinder.py`)
- **Purpose**: Specialized navigation and routing
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.3 (more deterministic)

**Use Cases**:
- Complex maze navigation
- Multi-map routing
- Obstacle avoidance
- Optimal path planning

**Input**:
```python
start: (map_id, x, y)
target: (map_id, x, y)
explored_tiles: List[(x, y)]
```

**Output**:
```python
path: ["up", "up", "right", "right", ...]
```

#### PuzzleSolverAgent (`src/agents/puzzle_solver.py`)
- **Purpose**: Solve Sokoban-style boulder puzzles
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.3

**Puzzle Types**:
- Strength boulder puzzles (push onto switches)
- Ice slide puzzles
- Complex switch sequences

**Approach**:
1. Analyze puzzle state
2. Identify goal configuration
3. Plan move sequence
4. Return solution

#### CriticAgent (`src/agents/critic.py`)
- **Purpose**: Evaluate strategy and identify issues
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.5

**Evaluation Criteria**:
- Repetitive actions (stuck states)
- Inefficient strategies
- Missed opportunities
- Poor battle decisions

**Output**:
```python
{
  'assessment': "Overall performance evaluation",
  'issues': "Specific problems identified",
  'suggestions': "Concrete improvements"
}
```

### 4. Memory Layer

#### ContextManager (`src/memory/context_manager.py`)
- **Purpose**: Long-term memory management
- **Key Features**:
  - Stores recent turns with full detail
  - Maintains summarized history
  - Prevents context window overflow
  - Persistence support

**Lifecycle**:
```
Turns 1-100:  Full detail stored
Turn 100:     Summarize turns 1-80, keep 81-100
Turns 101-200: Add new turns
Turn 200:     Summarize 101-180, keep 181-200
...
```

**Storage**:
```python
recent_turns: List[Turn]       # Last 20 turns (full)
summaries: List[str]           # Compressed history
```

#### Summarizer (`src/memory/summarizer.py`)
- **Purpose**: Compress turn history using AI
- **Features**:
  - Identifies key progress (badges, locations)
  - Maintains objective continuity
  - Reduces token usage

**Example Summary**:
```
"Turns 1-80: Started in Pallet Town, received Charmander from
Professor Oak, defeated Gary's Squirtle. Traveled to Viridian City,
purchased Pokeballs. Caught Pidgey and Rattata on Route 1."
```

### 5. Tools Layer

#### GoalManager (`src/tools/goal_manager.py`)
- **Purpose**: Multi-level goal tracking
- **Goal Hierarchy**:
  - **Primary**: Main objective (e.g., "Defeat Elite Four")
  - **Secondary**: Enabling goal (e.g., "Get to Pokemon League")
  - **Tertiary**: Opportunistic (e.g., "Catch Pokemon if seen")

**Benefits**:
- Maintains focus on primary objective
- Allows tactical flexibility
- Prevents goal drift

#### ActionExecutor (`src/tools/action_executor.py`)
- **Purpose**: Execute AI decisions on emulator
- **Features**:
  - Button press translation
  - Action validation
  - Stuck detection (10+ repeats)
  - Action history tracking

**Stuck Detection**:
```python
# If last 10 actions are identical
if len(set(last_10_actions)) == 1:
    trigger_stuck_handler()
```

#### ProgressTracker (`src/tools/progress_tracker.py`)
- **Purpose**: Monitor game advancement
- **Tracks**:
  - Badges earned (8 total)
  - Pokemon caught (unique species)
  - Key items obtained
  - Turn count and timing
  - Major milestones

**Metrics**:
```python
completion_percentage = (badges/8 * 80) +
                       (elite_four * 15) +
                       (champion * 5)
```

## Data Flow

### Main Loop Iteration

```
1. Tick Emulator (10 frames)
   ↓
2. Read Game State
   - RAM data (position, party, badges)
   - Screen capture
   - Visual analysis
   ↓
3. Update Map Memory
   - Mark current tile explored
   - Find nearby unexplored
   ↓
4. Build State Representation
   - Combine all data sources
   - Generate text description
   ↓
5. AI Decision
   - Check context size (summarize if needed)
   - Build prompt (context + goals + state)
   - Call Claude API
   - Parse response
   ↓
6. Execute Action
   - Validate action
   - Press button
   - Check for stuck
   ↓
7. Update Context
   - Add turn to history
   - Process goal updates
   ↓
8. Track Progress
   - Check for new badges
   - Update statistics
   ↓
9. Checkpoint (every 100 turns)
   - Save emulator state
   - Save agent state
   - Save progress
   ↓
10. Repeat
```

## Prompt Engineering

### System Prompt Structure

The main agent's system prompt includes:

1. **Role Definition**: "You are an AI agent playing Pokemon Red"
2. **Goal Statement**: "Complete the game by defeating Elite Four"
3. **Available Information**: State data, actions, context
4. **Action Space**: Button options
5. **Guidelines**:
   - Goal prioritization
   - Exploration strategy
   - Battle tactics
   - Stuck avoidance
6. **Response Format**: Structured output parsing

### Prompt Composition

Each turn, the prompt contains:

```
[SUMMARIES]
Previous activity summaries (compressed history)

[GOALS]
Primary: <goal>
Secondary: <goal>
Tertiary: <goal>

[RECENT TURNS]
Last 20 turns with full detail

[CURRENT STATE]
Position, badges, party, visual analysis, exploration

[REQUEST]
"Based on the above, decide your next action."
```

## Performance Optimization

### Token Usage Reduction

1. **Summarization**: Compress old turns
2. **Selective Detail**: Only keep recent history in full
3. **Efficient Encoding**: Text state instead of image tokens
4. **Model Selection**: Use Haiku for simple decisions

### Speed Optimization

1. **Unlimited Emulation**: `speed: 0`
2. **Minimal Delays**: Reduce action_delay_ms
3. **Headless Mode**: No rendering overhead
4. **Caching**: Reuse repeated prompts

### Cost Optimization

1. **Model Tiering**:
   - Main decisions: Sonnet
   - Pathfinding: Haiku
   - Summaries: Haiku
2. **Context Management**: Aggressive summarization
3. **Action Delays**: Fewer API calls per minute

## Checkpoint System

### Save Structure

```
data/checkpoints/checkpoint_TURN/
├── emulator.state       # PyBoy save state
├── context.json         # AI context + summaries
├── goals.json           # Current goals
└── progress.json        # Statistics
```

### Recovery

On crash or restart:
1. Load latest checkpoint
2. Restore emulator state
3. Restore AI context
4. Resume from saved turn

## Extensibility

### Adding New Agents

```python
# 1. Create agent class
class NewAgent:
    SYSTEM_PROMPT = "..."

    def process(self, input):
        # Call Claude API
        # Parse response
        return result

# 2. Initialize in main.py
self.new_agent = NewAgent()

# 3. Call when needed
if condition:
    result = self.new_agent.process(data)
```

### Custom Memory Addresses

Edit `data/memory_addresses.json`:

```json
{
  "new_feature": {
    "address": "0xABCD",
    "type": "uint8"
  }
}
```

Update `MemoryReader` to read it.

### Custom Prompts

Edit agent system prompts:
- `src/agents/main_agent.py`: Main gameplay
- `src/agents/pathfinder.py`: Navigation
- `src/agents/puzzle_solver.py`: Puzzles
- `src/agents/critic.py`: Strategy evaluation

## Testing Strategy

### Unit Tests

Test individual components:
```python
# Test memory reader
def test_memory_reader():
    reader = MemoryReader(emulator)
    badges = reader.read_badges()
    assert isinstance(badges, dict)
```

### Integration Tests

Test component interaction:
```python
# Test state pipeline
def test_state_pipeline():
    state = game_state.update()
    text = game_state.get_text_representation(state)
    assert len(text) > 0
```

### End-to-End Tests

Run agent for N turns:
```python
def test_agent_run():
    agent = PokemonAIAgent()
    for _ in range(100):
        agent._game_loop_iteration()
    assert agent.turn_count == 100
```

## Monitoring

### Logs

- `logs/Main_*.log`: Overall execution
- `logs/MainAgent_*.log`: AI decisions
- `logs/Emulator_*.log`: Emulator events
- `logs/MemoryReader_*.log`: State reading
- `logs/screenshots/`: Visual history

### Metrics

Track in `ProgressTracker`:
- Badges per hour
- Average turns per badge
- Stuck frequency
- API costs (tokens used)

## Future Enhancements

### Potential Improvements

1. **Vision Enhancement**:
   - OCR for text reading
   - CNN for battle UI detection
   - Object detection for NPCs

2. **Advanced Planning**:
   - Long-term route planning (A* across maps)
   - Battle strategy optimization
   - Team composition planning

3. **Learning**:
   - Reinforcement learning overlay
   - Strategy caching
   - Pattern recognition

4. **Multi-Modal**:
   - Direct image input to Claude (when available)
   - Reduce reliance on RAM reading

5. **Distributed**:
   - Parallel agent exploration
   - Cloud execution
   - Multi-instance testing

## Security Considerations

1. **API Key**: Store securely, never commit
2. **ROM File**: User must provide legally
3. **Sandboxing**: Emulator runs in isolated process
4. **Rate Limiting**: Respect API limits
5. **Resource Limits**: Monitor memory/CPU usage

## Conclusion

This architecture provides:
- **Modularity**: Independent, replaceable components
- **Scalability**: Handles long playthroughs
- **Extensibility**: Easy to add features
- **Reliability**: Checkpointing and recovery
- **Observability**: Comprehensive logging

The multi-agent approach allows specialized reasoning for different task types, while the memory management system enables sustainable long-context operations.
