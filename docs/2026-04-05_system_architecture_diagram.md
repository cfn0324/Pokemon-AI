# 2026-04-05 系统架构图

本文档基于当前项目实际代码结构整理，主要对应以下模块：

- `main.py`
- `src/emulator/*`
- `src/state/*`
- `src/control/*`
- `src/agents/*`
- `src/memory/*`
- `src/tools/*`
- `src/runtime/checkpoints.py`
- `src/visualization/visualizer.py`
- `scripts/autonomous_smoke.py`
- `scripts/autonomous_smoke_batch.py`
- `scripts/capture_evidence_run.py`
- `scripts/smoke_report_summary.py`

可直接作为论文第 3 章“系统设计与实现”的架构图基础。

## 1. 总体系统架构图

```mermaid
flowchart LR
    user[研究者 / 答辩教师 / 控制端]
    config[config.yaml + .env]
    rom[PokemonRed.gb + save state]
    api[外部模型服务<br/>Messages / Chat Completions API]
    reports[JSON 报告 / Markdown 报告 / 截图证据]

    subgraph runtime[运行时主系统 main.py / PokemonAIAgent]
        coordinator[主协调器<br/>PokemonAIAgent]

        subgraph env[环境接入层]
            emulator[GameBoyEmulator]
            mem[MemoryReader]
        end

        subgraph state[状态感知层]
            vision[VisionProcessor]
            mapmem[MapMemory]
            gamestate[GameState]
        end

        subgraph decision[决策控制层]
            engine[DecisionEngine]
            controllers[规则/安全控制器<br/>Oak Lab / Battle / Parcel / Route 等]
            asyncai[AsyncDecisionMaker]
            mainagent[MainAgent]
            pathfinder[PathfinderAgent]
            puzzle[PuzzleSolverAgent]
            critic[CriticAgent]
        end

        subgraph memorygoal[记忆与目标层]
            context[ContextManager]
            summary[Summarizer]
            goals[GoalManager]
        end

        subgraph exec[执行与运行支撑层]
            executor[ActionExecutor]
            tracker[ProgressTracker]
            checkpoints[Checkpoint Metadata / Restore]
            visualizer[GameVisualizer]
            logger[Logger]
        end

        aiclient[AIClient]
    end

    rom --> emulator
    config --> coordinator
    config --> aiclient
    user <--> visualizer

    coordinator --> emulator
    emulator --> mem
    emulator --> gamestate
    mem --> gamestate
    vision --> gamestate
    mapmem --> gamestate

    gamestate --> engine
    engine --> controllers
    engine --> asyncai
    asyncai --> mainagent

    mainagent --> pathfinder
    mainagent --> puzzle
    mainagent --> critic
    mainagent --> context
    mainagent --> summary
    mainagent --> goals
    mainagent --> aiclient
    aiclient <--> api

    controllers --> executor
    mainagent --> executor
    executor --> emulator

    gamestate --> tracker
    gamestate --> checkpoints
    gamestate --> visualizer
    engine --> visualizer
    tracker --> visualizer
    checkpoints --> visualizer
    coordinator --> logger
    gamestate --> logger
    engine --> logger
    executor --> logger

    checkpoints --> reports
    tracker --> reports
    logger --> reports
```

## 2. 决策子系统架构图

这张图更适合放到论文“智能体决策链路设计”小节，用来说明系统不是单纯把截图丢给大模型，而是先经过规则控制层、再进入 AI 决策层。

```mermaid
flowchart TD
    obs[当前观测<br/>RAM 状态 + 截图 + 地图记忆 + 近期结果]
    state_text[结构化状态文本]
    screen[screen_type / UI 状态]

    subgraph route[DecisionEngine 决策路由]
        bootstrap[启动与已知 UI 阶段]
        recover[稳定 UI 恢复 / 对话恢复 / warp 防护]
        story[早期剧情控制器<br/>Oak Lab / Rival / Route / Parcel]
        nav[局部导航与 frontier 规划]
        ai_fallback[AI fallback]
    end

    subgraph ai[AI 决策层]
        asyncai[AsyncDecisionMaker]
        mainagent[MainAgent]
        prompt[系统提示词 + 状态文本]
        memory[ContextManager + Summarizer]
        goals[GoalManager]
        tools[Pathfinder / PuzzleSolver / Critic]
        api[AIClient -> 外部模型]
    end

    decision[统一决策输出<br/>action / reasoning / action_plan / goal_update]
    execute[ActionExecutor]
    game[模拟器执行]
    result[下一回合新观测]

    obs --> state_text
    obs --> screen
    obs --> route
    state_text --> route
    screen --> route

    route --> bootstrap
    route --> recover
    route --> story
    route --> nav
    route --> ai_fallback

    ai_fallback --> asyncai
    asyncai --> mainagent
    mainagent --> prompt
    mainagent --> memory
    mainagent --> goals
    mainagent --> tools
    mainagent --> api

    bootstrap --> decision
    recover --> decision
    story --> decision
    nav --> decision
    api --> decision

    decision --> execute
    execute --> game
    game --> result
    result --> obs
```

## 3. 实验与取证链路图

这张图适合放到论文“实验设计与证据组织”章节。

```mermaid
flowchart LR
    cp[checkpoint / 命名检查点]
    smoke[scripts/autonomous_smoke.py]
    batch[scripts/autonomous_smoke_batch.py]
    summary[scripts/smoke_report_summary.py]
    capture[scripts/capture_evidence_run.py]

    runtime[PokemonAIAgent 运行时]
    json[原始 JSON 报告]
    md[Markdown 汇总]
    assets[docs/report_assets]
    img[docs/img]
    thesis[论文总报告 / 图索引 / 附录图册]

    cp --> smoke
    cp --> capture
    smoke --> runtime
    batch --> smoke
    capture --> runtime

    runtime --> json
    json --> summary
    summary --> md
    runtime --> assets
    assets --> img
    md --> thesis
    img --> thesis
    json --> thesis
```

## 4. 论文中建议使用的图题

- 图 3-1 系统总体架构图
- 图 3-2 决策与控制子系统架构图
- 图 4-1 实验与证据采集流程图

## 5. 论文写作建议

如果只放一张图，建议优先使用“总体系统架构图”。

如果论文篇幅允许，建议按下面方式组合：

1. 第 3 章放“总体系统架构图”
2. 第 3 章决策设计小节放“决策子系统架构图”
3. 第 4 章实验设计小节放“实验与取证链路图”

## 6. 可直接引用的摘要说明

本系统以 `main.py` 中的 `PokemonAIAgent` 作为运行时主协调器，通过模拟器驱动、RAM 状态读取、可选视觉分析和地图记忆构造统一游戏状态，再由 `DecisionEngine` 将规则控制器与大模型主智能体结合，输出动作并通过 `ActionExecutor` 回写到模拟器。系统同时具备上下文记忆、目标管理、检查点恢复、实时可视化和标准化实验脚本，从而形成“感知-决策-执行-观测-评估”闭环。
