const state = {
    game: {},
    decision: {},
    goals: [],
    history: [],
    events: [],
    control: {},
    checkpoints: [],
    pollingTimer: null,
    toastTimer: null,
};

const els = {
    connectionPill: document.getElementById("connectionPill"),
    runPill: document.getElementById("runPill"),
    turnPillValue: document.getElementById("turnPillValue"),
    checkpointPillValue: document.getElementById("checkpointPillValue"),
    resumePillValue: document.getElementById("resumePillValue"),
    statusDetailPill: document.getElementById("statusDetailPill"),
    streamImage: document.getElementById("streamImage"),
    fallbackImage: document.getElementById("fallbackImage"),
    streamPlaceholder: document.getElementById("streamPlaceholder"),
    screenTypeTag: document.getElementById("screenTypeTag"),
    visionModeTag: document.getElementById("visionModeTag"),
    phaseTag: document.getElementById("phaseTag"),
    screenSummary: document.getElementById("screenSummary"),
    harnessSummary: document.getElementById("harnessSummary"),
    movementSummary: document.getElementById("movementSummary"),
    mapBoard: document.getElementById("mapBoard"),
    mapLegend: document.getElementById("mapLegend"),
    mapCurrentLabel: document.getElementById("mapCurrentLabel"),
    mapBoundsLabel: document.getElementById("mapBoundsLabel"),
    mapSizeValue: document.getElementById("mapSizeValue"),
    mapExploredValue: document.getElementById("mapExploredValue"),
    mapFrontierValue: document.getElementById("mapFrontierValue"),
    mapWarpValue: document.getElementById("mapWarpValue"),
    mapPlayerValue: document.getElementById("mapPlayerValue"),
    decisionAction: document.getElementById("decisionAction"),
    decisionTurn: document.getElementById("decisionTurn"),
    decisionScreenType: document.getElementById("decisionScreenType"),
    decisionTime: document.getElementById("decisionTime"),
    decisionReasoning: document.getElementById("decisionReasoning"),
    historyList: document.getElementById("historyList"),
    eventList: document.getElementById("eventList"),
    controlStateValue: document.getElementById("controlStateValue"),
    stepBudgetValue: document.getElementById("stepBudgetValue"),
    manualQueueValue: document.getElementById("manualQueueValue"),
    lastCommandValue: document.getElementById("lastCommandValue"),
    latestCheckpointInfo: document.getElementById("latestCheckpointInfo"),
    restoredCheckpointInfo: document.getElementById("restoredCheckpointInfo"),
    apiCooldownInfo: document.getElementById("apiCooldownInfo"),
    controlErrorInfo: document.getElementById("controlErrorInfo"),
    startupBanner: document.getElementById("startupBanner"),
    startupBannerText: document.getElementById("startupBannerText"),
    startupCheckpointList: document.getElementById("startupCheckpointList"),
    focusText: document.getElementById("focusText"),
    activeGoalsList: document.getElementById("activeGoalsList"),
    todoList: document.getElementById("todoList"),
    doneList: document.getElementById("doneList"),
    checkpointList: document.getElementById("checkpointList"),
    statTurn: document.getElementById("statTurn"),
    statBadges: document.getElementById("statBadges"),
    statMoney: document.getElementById("statMoney"),
    statParty: document.getElementById("statParty"),
    statMap: document.getElementById("statMap"),
    statCoords: document.getElementById("statCoords"),
    statExplore: document.getElementById("statExplore"),
    statFrontier: document.getElementById("statFrontier"),
    partyList: document.getElementById("partyList"),
    toast: document.getElementById("toast"),
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}

function formatTimestamp(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("zh-CN", {
        hour12: false,
    });
}

function formatMoney(value) {
    const num = Number(value ?? 0);
    return Number.isFinite(num) ? num.toLocaleString("zh-CN") : "0";
}

const ACTION_LABELS = {
    up: "上",
    down: "下",
    left: "左",
    right: "右",
    a: "A",
    b: "B",
    start: "开始",
    select: "选择",
    wait: "等待",
};

const SCREEN_TYPE_LABELS = {
    unknown: "未知",
    overworld: "大地图",
    battle: "战斗",
    dialogue: "对话",
    text_entry: "文本输入",
    menu: "菜单",
    pokemon_menu: "宝可梦菜单",
    item_menu: "道具菜单",
    save_menu: "存档菜单",
    options_menu: "选项菜单",
    startup: "启动过渡",
    startup_menu: "启动菜单",
    title: "标题画面",
    naming_screen: "命名界面",
};

const PHASE_LABELS = {
    "free exploration": "自由探索",
    battle: "战斗",
    "opening script": "开场脚本",
    "pre-world": "进入世界前",
};

const EVENT_TYPE_LABELS = {
    info: "信息",
    milestone: "里程碑",
    error: "错误",
};

const CHECKPOINT_FLAG_LABELS = {
    Latest: "最新",
    "Restore Source": "当前恢复源",
    "Startup Option": "启动候选",
    Saved: "已保存",
};

const CHECKPOINT_LABELS = {
    "Milestone: Oak's Lab": "里程碑：大木研究所",
    "Milestone: First Pokemon": "里程碑：获得第一只宝可梦",
    "Milestone: Route 1": "里程碑：1号道路",
    "Milestone: Viridian City": "里程碑：常青市",
};

const COMMAND_LABELS = {
    pause: "暂停",
    resume: "继续",
    step: "单步",
    checkpoint: "保存存档",
    load_latest_checkpoint: "读取最新",
    load_checkpoint: "读取存档",
    stop: "停止",
    manual_action: "手动操作",
};

function translateLabel(value, labels, fallback = null) {
    const raw = String(value ?? "").trim();
    const normalized = raw.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(labels, raw)) {
        return labels[raw];
    }
    if (Object.prototype.hasOwnProperty.call(labels, normalized)) {
        return labels[normalized];
    }
    return fallback ?? (raw || "-");
}

function translateAction(value) {
    const raw = String(value ?? "").trim().toLowerCase();
    if (!raw) return "等待";
    return translateLabel(raw, ACTION_LABELS, String(value ?? "").toUpperCase());
}

function translateScreenType(value) {
    return translateLabel(value, SCREEN_TYPE_LABELS, String(value ?? "未知"));
}

function translatePhase(value) {
    return translateLabel(value, PHASE_LABELS, String(value ?? "未知"));
}

function translateEventType(value) {
    return translateLabel(value, EVENT_TYPE_LABELS, String(value ?? "信息"));
}

function translateCheckpointFlag(value) {
    return translateLabel(value, CHECKPOINT_FLAG_LABELS, String(value ?? "已保存"));
}

function translateCommand(value) {
    return translateLabel(value, COMMAND_LABELS, String(value ?? "指令"));
}

function formatLastCommand(value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "-";
    const [command, detail] = raw.split(":", 2);
    if (!detail) {
        return translateCommand(command);
    }
    if (command === "manual") {
        return `手动操作：${translateAction(detail)}`;
    }
    if (command === "load_checkpoint") {
        return `读取存档：${detail}`;
    }
    return `${translateCommand(command)}：${detail}`;
}

function translateCheckpointLabel(value, fallbackName = "") {
    const raw = String(value ?? fallbackName ?? "").trim();
    if (!raw) return "存档";
    if (Object.prototype.hasOwnProperty.call(CHECKPOINT_LABELS, raw)) {
        return CHECKPOINT_LABELS[raw];
    }
    const turnMatch = raw.match(/^Turn\s+(\d+)$/i);
    if (turnMatch) {
        return `回合 ${turnMatch[1]}`;
    }
    const milestoneMatch = raw.match(/^Milestone:\s*(.+)$/i);
    if (milestoneMatch) {
        return `里程碑：${milestoneMatch[1]}`;
    }
    return raw;
}

function setConnection(ok, message) {
    els.connectionPill.textContent = message;
    els.connectionPill.dataset.tone = ok ? "success" : "danger";
}

function showDisconnectedRuntime(error) {
    const detail = error?.message ? `刷新失败：${error.message}` : "刷新失败";
    els.statusDetailPill.textContent = detail;
    els.streamPlaceholder.textContent =
        "当前没有连接到实时运行实例。如果你运行的是 scripts/autonomous_smoke.py，这是正常现象，因为该脚本默认关闭实时可视化。运行 python main.py 才会显示实时画面与模型状态。";
    els.streamPlaceholder.style.display = "grid";
    els.streamImage.hidden = true;
    els.fallbackImage.hidden = true;
    els.screenSummary.textContent = "当前没有实时游戏画面输入到大屏。";
    els.harnessSummary.textContent = "只有正在运行且开启可视化的实例，才会持续向页面推送状态。";
    els.movementSummary.textContent = "等待运行实例连接。";
    els.decisionReasoning.textContent =
        "当前没有实时模型推理输出。若你运行的是 smoke 测试，请查看终端输出或生成的 JSON 报告。";
}

function showToast(message) {
    if (!message) return;
    els.toast.textContent = message;
    els.toast.classList.add("is-visible");
    clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
        els.toast.classList.remove("is-visible");
    }, 2600);
}

async function fetchJSON(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
        throw new Error(`${url} ${response.status}`);
    }
    return response.json();
}

async function refreshAll() {
    try {
        const [
            game,
            decision,
            goals,
            history,
            events,
            control,
            checkpoints,
        ] = await Promise.all([
            fetchJSON("/api/state"),
            fetchJSON("/api/decision"),
            fetchJSON("/api/goals"),
            fetchJSON("/api/history"),
            fetchJSON("/api/events"),
            fetchJSON("/api/control/state"),
            fetchJSON("/api/checkpoints"),
        ]);

        state.game = game || {};
        state.decision = decision || {};
        state.goals = goals.goals || [];
        state.history = history.decisions || [];
        state.events = events.events || [];
        state.control = control || {};
        state.checkpoints = checkpoints.checkpoints || [];

        renderState();
        renderDecision();
        renderGoals();
        renderHistory();
        renderEvents();
        renderControl();
        renderCheckpoints();
        renderMap();
        renderParty();

        setConnection(true, "已连接");
    } catch (error) {
        setConnection(false, "已断开");
        showDisconnectedRuntime(error);
    }
}

function renderState() {
    const game = state.game || {};
    const visual = game.visual || {};
    const exploration = game.exploration || {};
    const navigation = game.navigation || {};
    const deltas = game.deltas || {};
    const position = game.position || {};
    const screenType =
        state.decision.screen_type || visual.screen_type || visual.ram_screen_type || "unknown";
    const localAnalysisEnabled = Boolean(visual.local_analysis_enabled);
    const partyCount = game.party_size ?? ((game.party || []).length || 0);

    els.turnPillValue.textContent = String(game.turn ?? state.control.turn ?? 0);
    els.statusDetailPill.textContent = `最近更新：${formatTimestamp(
        game.timestamp || state.decision.timestamp || state.control.last_command_at,
    )}`;

    els.screenTypeTag.textContent = `界面 ${translateScreenType(screenType)}`;
    els.visionModeTag.textContent = localAnalysisEnabled ? "像素启发式已启用" : "原始截图 + 内存";

    let phase = "free exploration";
    if (game.in_battle) phase = "battle";
    else if (game.pre_starter_script) phase = "opening script";
    else if (game.pre_world) phase = "pre-world";
    else if (game.phase_hint) phase = String(game.phase_hint);
    els.phaseTag.textContent = `阶段 ${translatePhase(phase)}`;

    els.screenSummary.textContent = visual.description || "等待画面描述。";
    els.harnessSummary.textContent = localAnalysisEnabled
        ? "已启用本地像素启发式，因此页面会展示更紧凑的视觉结果。"
        : "本地像素分析已关闭，模型当前依赖原始截图与内存状态。";
    els.movementSummary.textContent = deltas.stuck_hint
        ? `${deltas.stuck_hint}${deltas.position_changed ? "；本回合位置已变化。" : ""}`
        : "等待更多移动反馈。";

    els.statTurn.textContent = String(game.turn ?? 0);
    els.statBadges.textContent = `${game.badges ?? 0} / 8`;
    els.statMoney.textContent = formatMoney(game.money);
    els.statParty.textContent = String(partyCount);
    els.statMap.textContent = position.map_id ?? "-";
    els.statCoords.textContent =
        position.x != null && position.y != null ? `${position.x}, ${position.y}` : "-";
    els.statExplore.textContent = `${Number(exploration.exploration_percent ?? 0).toFixed(1)}%`;
    els.statFrontier.textContent = String(navigation.frontier_count ?? 0);
}

function renderDecision() {
    const decision = state.decision || {};
    const screenType = decision.screen_type || state.game.visual?.screen_type || "unknown";

    els.decisionAction.textContent = translateAction(decision.action || "wait");
    els.decisionTurn.textContent = decision.turn ?? "-";
    els.decisionScreenType.textContent = translateScreenType(screenType);
    els.decisionTime.textContent = formatTimestamp(decision.timestamp);
    els.decisionReasoning.textContent = decision.reasoning || "暂无模型解释。";
}

function renderMap() {
    const snapshot = state.game.navigation?.map_snapshot || {};
    const position = state.game.position || {};

    if (!els.mapBoard || !els.mapLegend || !els.mapCurrentLabel || !els.mapBoundsLabel) {
        return;
    }

    if (!snapshot.available || !Array.isArray(snapshot.rows) || !snapshot.rows.length) {
        els.mapBoard.innerHTML = "<div class=\"empty-state\">暂无地图快照。智能体获得自由移动后，这里会渲染反向探索地图。</div>";
        els.mapBoard.style.removeProperty("--map-cell-size");
        els.mapBoard.style.removeProperty("--map-gap");
        els.mapLegend.innerHTML = "";
        els.mapCurrentLabel.textContent = `地图 ${position.map_id ?? "-"}`;
        els.mapBoundsLabel.textContent = "边界 -";
        els.mapSizeValue.textContent = "-";
        els.mapExploredValue.textContent = "0";
        els.mapFrontierValue.textContent = "0";
        els.mapWarpValue.textContent = "0";
        els.mapPlayerValue.textContent =
            position.x != null && position.y != null ? `${position.x}, ${position.y}` : "-";
        return;
    }

    const cellTone = {
        " ": "unknown",
        ".": "explored",
        F: "frontier",
        "#": "wall",
        W: "warp",
        P: "player",
    };
    const bounds = snapshot.bounds || {};
    const width = Number(
        bounds.width ?? Math.max(...snapshot.rows.map((row) => String(row || "").length), 0),
    );
    const height = Number(bounds.height ?? snapshot.rows.length ?? 0);
    const largestSpan = Math.max(width, height, 1);
    const cellSize = Math.max(8, Math.min(18, Math.floor(280 / largestSpan)));
    const gapSize = cellSize <= 10 ? 1 : 2;
    const player = snapshot.player || {};

    els.mapBoard.style.setProperty("--map-cell-size", `${cellSize}px`);
    els.mapBoard.style.setProperty("--map-gap", `${gapSize}px`);

    els.mapBoard.innerHTML = snapshot.rows
        .map((row, rowIndex) => `
            <div class="map-row">
                ${Array.from(String(row || "")).map((cell, colIndex) => {
                    const tileX = Number(bounds.min_x ?? 0) + colIndex;
                    const tileY = Number(bounds.min_y ?? 0) + rowIndex;
                    const tileLabel = (snapshot.legend || {})[cell] || cell;
                    return `
                        <span
                            class="map-cell"
                            data-tone="${cellTone[cell] || "unknown"}"
                            title="${escapeHtml(`${tileLabel} (${tileX}, ${tileY})`)}"
                        ></span>
                    `;
                }).join("")}
            </div>
        `)
        .join("");

    els.mapCurrentLabel.textContent = `地图 ${snapshot.map_id ?? position.map_id ?? "-"}`;
    els.mapBoundsLabel.textContent =
        `x ${bounds.min_x ?? "-"}-${bounds.max_x ?? "-"} | y ${bounds.min_y ?? "-"}-${bounds.max_y ?? "-"}`;
    els.mapSizeValue.textContent = width > 0 && height > 0 ? `${width}x${height}` : "-";
    els.mapExploredValue.textContent = String(snapshot.explored_count ?? 0);
    els.mapFrontierValue.textContent = String(snapshot.frontier_count ?? 0);
    els.mapWarpValue.textContent = String(snapshot.warp_count ?? 0);
    els.mapPlayerValue.textContent =
        player.x != null && player.y != null
            ? `${player.x}, ${player.y}`
            : position.x != null && position.y != null
                ? `${position.x}, ${position.y}`
                : "-";

    els.mapLegend.innerHTML = `
        <span class="legend-pill"><span class="legend-dot" data-tone="player"></span>玩家</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="explored"></span>已探索</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="frontier"></span>前沿</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="wall"></span>墙壁</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="warp"></span>传送点</span>
    `;
}

function renderSimpleList(container, items, renderItem, emptyText) {
    if (!items || !items.length) {
        container.innerHTML = `<div class="list-item empty-state">${escapeHtml(emptyText)}</div>`;
        return;
    }

    container.innerHTML = items
        .map((item, index) => `<div class="list-item">${renderItem(item, index)}</div>`)
        .join("");
}

function renderGoals() {
    const grouped = {
        focus: null,
        active: [],
        todos: [],
        done: [],
    };

    for (const item of state.goals || []) {
        const type = String(item.type || "").toLowerCase();
        if (type === "focus") {
            grouped.focus = item.description;
        } else if (item.status === "completed" || type === "done") {
            grouped.done.push(item.description);
        } else if (type.startsWith("todo")) {
            grouped.todos.push(item.description);
        } else {
            grouped.active.push({
                label: item.type || "目标",
                description: item.description,
            });
        }
    }

    els.focusText.textContent = grouped.focus || "暂无当前焦点。";

    renderSimpleList(
        els.activeGoalsList,
        grouped.active,
        (item) => `<strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.description)}</p>`,
        "暂无活动目标。",
    );
    renderSimpleList(
        els.todoList,
        grouped.todos,
        (item, index) => `<strong>待办 ${index + 1}</strong><p>${escapeHtml(item)}</p>`,
        "暂无待办事项。",
    );
    renderSimpleList(
        els.doneList,
        grouped.done,
        (item) => `<strong>已完成</strong><p>${escapeHtml(item)}</p>`,
        "暂无已完成事项。",
    );
}

function renderHistory() {
    if (!state.history.length) {
        els.historyList.innerHTML = "<div class=\"list-item empty-state\">暂无决策历史。</div>";
        return;
    }

    els.historyList.innerHTML = state.history
        .slice()
        .reverse()
        .slice(0, 30)
        .map((item) => `
            <div class="list-item">
                <strong>第 ${escapeHtml(item.turn ?? "-")} 回合 | ${escapeHtml(translateAction(item.action || "wait"))}</strong>
                <p>${escapeHtml(item.reasoning || "未记录推理内容。")}</p>
                <p class="mono">${escapeHtml(translateScreenType(item.screen_type || "unknown"))} | ${escapeHtml(formatTimestamp(item.timestamp))}</p>
            </div>
        `)
        .join("");
}

function renderEvents() {
    if (!state.events.length) {
        els.eventList.innerHTML = "<div class=\"list-item empty-state\">等待运行事件...</div>";
        return;
    }

    els.eventList.innerHTML = state.events
        .slice()
        .reverse()
        .slice(0, 30)
        .map((item) => `
            <div class="list-item event-item" data-type="${escapeHtml(item.type || "info")}">
                <strong>${escapeHtml(translateEventType(item.type || "info"))}</strong>
                <p>${escapeHtml(item.message || "")}</p>
                <p class="mono">${escapeHtml(formatTimestamp(item.timestamp))}</p>
            </div>
        `)
        .join("");
}

function buildCheckpointCards(items, options = {}) {
    const {
        latest = null,
        restored = null,
        startupPending = false,
        emptyText = "暂无存档。",
    } = options;

    if (!items || !items.length) {
        return `
            <div class="checkpoint-card">
                <p class="empty-state">${escapeHtml(emptyText)}</p>
            </div>
        `;
    }

    return items.map((checkpoint) => {
        const flags = [];
        if (checkpoint.name === latest) flags.push("Latest");
        if (checkpoint.name === restored) flags.push("Restore Source");
        if (startupPending) flags.push("Startup Option");

        const pos = checkpoint.position || {};
        return `
            <div class="checkpoint-card">
                <div class="checkpoint-head">
                    <div>
                        <strong>${escapeHtml(translateCheckpointLabel(checkpoint.label || checkpoint.name || "checkpoint", checkpoint.name || ""))}</strong>
                        <p class="mono">${escapeHtml(checkpoint.name || "-")}</p>
                    </div>
                    <div class="tag-row">
                        ${(flags.length ? flags : ["Saved"])
                            .map((flag) => `<span class="tag">${escapeHtml(translateCheckpointFlag(flag))}</span>`)
                            .join("")}
                    </div>
                </div>
                <div class="checkpoint-meta">
                    <span class="tag">回合 ${escapeHtml(checkpoint.turn ?? "-")}</span>
                    <span class="tag">${escapeHtml(translateScreenType(checkpoint.screen_type || "unknown"))}</span>
                    <span class="tag">${escapeHtml(formatTimestamp(checkpoint.created_at))}</span>
                </div>
                <div class="checkpoint-body">
                    <p>位置：地图 ${escapeHtml(pos.map_id ?? "-")} | (${escapeHtml(pos.x ?? "-")}, ${escapeHtml(pos.y ?? "-")})</p>
                    <p>进度：徽章 ${escapeHtml(checkpoint.badges ?? 0)} | 队伍 ${escapeHtml(checkpoint.party_size ?? 0)} | 金钱 ${escapeHtml(formatMoney(checkpoint.money))}</p>
                    <p>焦点：${escapeHtml(checkpoint.focus || checkpoint.primary_goal || "未记录")}</p>
                </div>
                <div class="checkpoint-actions">
                    <button type="button" data-load-checkpoint="${escapeHtml(checkpoint.name || "")}">读取存档</button>
                </div>
            </div>
        `;
    }).join("");
}

function updateControlButtons(control) {
    const startupPending = Boolean(control.startup_selection_pending);
    const startupChoices = control.startup_checkpoint_choices || [];
    const loadLatestDisabled = startupPending
        ? !(startupChoices.length || state.checkpoints.length)
        : !state.checkpoints.length;

    document.querySelectorAll('[data-command="pause"]').forEach((button) => {
        button.disabled = startupPending || !control.running || control.paused;
    });
    document.querySelectorAll('[data-command="resume"]').forEach((button) => {
        button.disabled = startupPending ? false : (!control.running || !control.paused);
    });
    document.querySelectorAll('[data-command="step"]').forEach((button) => {
        button.disabled = startupPending || !control.running;
    });
    document.querySelectorAll('[data-command="load_latest_checkpoint"]').forEach((button) => {
        button.disabled = loadLatestDisabled;
    });

    document.querySelectorAll("[data-manual]").forEach((button) => {
        button.disabled = startupPending || !control.paused;
    });
}

function renderControl() {
    const control = state.control || {};
    const running = Boolean(control.running);
    const paused = Boolean(control.paused);
    const startupPending = Boolean(control.startup_selection_pending);

    els.checkpointPillValue.textContent = String(control.checkpoint_count ?? state.checkpoints.length ?? 0);
    els.resumePillValue.textContent = control.auto_resume_latest_checkpoint ? "开" : "关";

    document.body.classList.toggle("startup-pending", startupPending);

    if (startupPending) {
        els.runPill.textContent = "等待选择";
        els.runPill.dataset.tone = "warning";
        els.controlStateValue.textContent = "等待启动选择";
    } else if (!running) {
        els.runPill.textContent = "已停止";
        els.runPill.dataset.tone = "danger";
        els.controlStateValue.textContent = "已停止";
    } else if (paused) {
        els.runPill.textContent = "已暂停";
        els.runPill.dataset.tone = "warning";
        els.controlStateValue.textContent = "已暂停";
    } else {
        els.runPill.textContent = "运行中";
        els.runPill.dataset.tone = "success";
        els.controlStateValue.textContent = "自动运行";
    }

    els.stepBudgetValue.textContent = String(control.step_budget ?? 0);
    els.manualQueueValue.textContent = String(control.manual_queue_size ?? 0);
    els.lastCommandValue.textContent = formatLastCommand(control.last_command);
    els.latestCheckpointInfo.textContent = control.latest_checkpoint || "无";
    els.restoredCheckpointInfo.textContent = control.restored_checkpoint || "未恢复";
    els.apiCooldownInfo.textContent = control.api_cooldown_active
        ? `${Number(control.api_cooldown_remaining ?? 0).toFixed(1)}s`
        : "无";
    els.controlErrorInfo.textContent = control.last_error || "无";
    if (els.startupBanner) {
        els.startupBanner.hidden = !startupPending;
    }
    if (els.startupBannerText) {
        const defaultTarget = control.startup_default_checkpoint === "latest"
            ? "最新存档"
            : control.startup_default_checkpoint === "new"
                ? "新开局"
                : (control.startup_default_checkpoint || "最新存档");
        els.startupBannerText.textContent = startupPending
            ? `点击“读取最新”可从 ${defaultTarget} 继续，也可以在下方选择指定存档，或点击“继续”直接开始新开局。`
            : "可在下方选择存档，也可以读取最新存档或直接继续新开局。";
    }
    updateControlButtons(control);
}

function renderCheckpoints() {
    const control = state.control || {};
    const latest = control.latest_checkpoint;
    const restored = control.restored_checkpoint;
    const startupPending = Boolean(control.startup_selection_pending);
    const startupChoices = startupPending
        ? (control.startup_checkpoint_choices || state.checkpoints || [])
        : [];

    if (els.startupCheckpointList) {
        els.startupCheckpointList.innerHTML = buildCheckpointCards(startupChoices, {
            latest,
            restored,
            startupPending: true,
            emptyText: "当前没有可用于启动的存档。点击“直接新开局”即可开始。",
        });
    }

    els.checkpointList.innerHTML = buildCheckpointCards(state.checkpoints, {
        latest,
        restored,
        startupPending: false,
        emptyText: "当前还没有存档。运行若干回合后可在控制区保存存档。",
    });
}

function renderParty() {
    const party = state.game.party || [];

    if (!els.partyList) {
        return;
    }

    if (!party.length) {
        els.partyList.innerHTML = "<div class=\"list-item empty-state\">暂无已捕获宝可梦。</div>";
        return;
    }

    els.partyList.innerHTML = party.map((pokemon, index) => {
        const name = pokemon.display_name || pokemon.name || pokemon.species || "未知宝可梦";
        const currentHp = Number(pokemon.current_hp ?? pokemon.hp ?? 0);
        const maxHp = Number(pokemon.max_hp ?? 0);
        const hpRatio = maxHp > 0 ? Math.max(0, Math.min(1, currentHp / maxHp)) : 0;
        const hpPercent = maxHp > 0 ? `${Math.round(hpRatio * 100)}%` : "未知";
        const hpState = hpRatio <= 0.25 ? "danger" : hpRatio <= 0.5 ? "warning" : "healthy";

        return `
            <article class="party-card" data-hp-state="${hpState}">
                <div class="party-top">
                    <span class="party-slot mono">${String(index + 1).padStart(2, "0")}</span>
                    <div class="party-body">
                        <strong>${escapeHtml(name)}</strong>
                        <p>等级 ${escapeHtml(pokemon.level ?? "?")} | HP ${escapeHtml(currentHp)} / ${escapeHtml(maxHp || "?")}</p>
                    </div>
                    <span class="party-hp-pill">${escapeHtml(hpPercent)}</span>
                </div>
                <div class="hp-track"><span class="hp-fill" style="width:${(hpRatio * 100).toFixed(1)}%"></span></div>
            </article>
        `;
    }).join("");
}

async function sendControl(command, value = null) {
    try {
        const response = await fetch("/api/control", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command, value }),
        });
        const result = await response.json();

        if (!response.ok || result.ok === false) {
            throw new Error(result.message || `指令执行失败：${translateCommand(command)}`);
        }

        showToast(result.message || `已发送：${translateCommand(command)}`);
        await refreshAll();
    } catch (error) {
        showToast(error.message);
        await refreshAll();
    }
}

async function refreshFallbackScreenshot() {
    try {
        const data = await fetchJSON("/api/screenshot");
        if (!data.image) return;
        els.fallbackImage.src = data.image;
        els.fallbackImage.hidden = false;
        els.streamPlaceholder.style.display = "none";
    } catch (_error) {
        // Ignore screenshot refresh failures; the stream may still be active.
    }
}

function shouldConfirm(command) {
    return command === "stop";
}

function bindControls() {
    document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => {
            const command = button.dataset.command;
            if (shouldConfirm(command) && !window.confirm(`确认执行“${translateCommand(command)}”吗？`)) {
                return;
            }
            sendControl(command);
        });
    });

    document.querySelectorAll("[data-manual]").forEach((button) => {
        button.addEventListener("click", () => {
            sendControl("manual_action", button.dataset.manual);
        });
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        const checkpointName = target.getAttribute("data-load-checkpoint");
        if (!checkpointName) return;

        const startupPending = Boolean(state.control?.startup_selection_pending);
        if (!startupPending && !window.confirm(`确认读取存档 ${checkpointName} 吗？读取后会先暂停自动运行。`)) {
            return;
        }
        sendControl("load_checkpoint", checkpointName);
    });

    const refreshButton = document.getElementById("refreshButton");
        if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            await refreshAll();
            await refreshFallbackScreenshot();
            showToast("大屏数据已刷新");
        });
    }
}

function bindStreamHandlers() {
    els.streamImage.addEventListener("load", () => {
        els.streamPlaceholder.style.display = "none";
        els.streamImage.hidden = false;
        els.fallbackImage.hidden = true;
        setConnection(true, "串流在线");
    });

    els.streamImage.addEventListener("error", async () => {
        els.streamPlaceholder.textContent =
            "当前实时串流不可用，大屏已切换到截图回退模式。如果你运行的是 autonomous_smoke，这属于正常现象。";
        els.streamPlaceholder.style.display = "grid";
        els.streamImage.hidden = true;
        await refreshFallbackScreenshot();
    });
}

async function bootstrap() {
    bindControls();
    bindStreamHandlers();
    await refreshAll();
    await refreshFallbackScreenshot();

    state.pollingTimer = window.setInterval(async () => {
        await refreshAll();
        await refreshFallbackScreenshot();
    }, 1500);
}

bootstrap();
