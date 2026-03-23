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
    return date.toLocaleString("en-GB", {
        hour12: false,
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function formatMoney(value) {
    const num = Number(value ?? 0);
    return Number.isFinite(num) ? num.toLocaleString("en-US") : "0";
}

function setConnection(ok, message) {
    els.connectionPill.textContent = message;
    els.connectionPill.dataset.tone = ok ? "success" : "danger";
}

function showDisconnectedRuntime(error) {
    const detail = error?.message ? `Refresh failed: ${error.message}` : "Refresh failed";
    els.statusDetailPill.textContent = detail;
    els.streamPlaceholder.textContent =
        "No live runtime is connected. If you started scripts/autonomous_smoke.py this is expected, because that script disables live visualization. Run python main.py to see the real-time feed and model state.";
    els.streamPlaceholder.style.display = "grid";
    els.streamImage.hidden = true;
    els.fallbackImage.hidden = true;
    els.screenSummary.textContent = "No live game screen is currently feeding the dashboard.";
    els.harnessSummary.textContent = "The dashboard updates only while an active visualized runtime is pushing state.";
    els.movementSummary.textContent = "Waiting for a runtime instance to connect.";
    els.decisionReasoning.textContent =
        "No live model reasoning is available. For smoke runs, check the terminal output or the generated JSON report.";
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

        setConnection(true, "Connected");
    } catch (error) {
        setConnection(false, "Disconnected");
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
    els.statusDetailPill.textContent = `Last update: ${formatTimestamp(
        game.timestamp || state.decision.timestamp || state.control.last_command_at,
    )}`;

    els.screenTypeTag.textContent = `SCREEN_TYPE ${screenType}`;
    els.visionModeTag.textContent = localAnalysisEnabled ? "pixel heuristics on" : "raw screenshot + RAM";

    let phase = "free exploration";
    if (game.in_battle) phase = "battle";
    else if (game.pre_starter_script) phase = "opening script";
    else if (game.pre_world) phase = "pre-world";
    else if (game.phase_hint) phase = String(game.phase_hint);
    els.phaseTag.textContent = phase;

    els.screenSummary.textContent = visual.description || "Waiting for a screen description";
    els.harnessSummary.textContent = localAnalysisEnabled
        ? "Local pixel heuristics are enabled, so the page shows compact vision results."
        : "Local pixel analysis is disabled. The model is relying on the raw screenshot plus RAM.";
    els.movementSummary.textContent = deltas.stuck_hint
        ? `${deltas.stuck_hint}${deltas.position_changed ? "; position changed this turn." : ""}`
        : "Waiting for more movement deltas.";

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

    els.decisionAction.textContent = String(decision.action || "wait").toUpperCase();
    els.decisionTurn.textContent = decision.turn ?? "-";
    els.decisionScreenType.textContent = screenType;
    els.decisionTime.textContent = formatTimestamp(decision.timestamp);
    els.decisionReasoning.textContent = decision.reasoning || "No model explanation yet.";
}

function renderMap() {
    const snapshot = state.game.navigation?.map_snapshot || {};
    const position = state.game.position || {};

    if (!els.mapBoard || !els.mapLegend || !els.mapCurrentLabel || !els.mapBoundsLabel) {
        return;
    }

    if (!snapshot.available || !Array.isArray(snapshot.rows) || !snapshot.rows.length) {
        els.mapBoard.innerHTML = "<div class=\"empty-state\">No map snapshot is available yet. Once the agent can move freely, this panel will render the reverse exploration map.</div>";
        els.mapBoard.style.removeProperty("--map-cell-size");
        els.mapBoard.style.removeProperty("--map-gap");
        els.mapLegend.innerHTML = "";
        els.mapCurrentLabel.textContent = `map ${position.map_id ?? "-"}`;
        els.mapBoundsLabel.textContent = "bounds -";
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

    els.mapCurrentLabel.textContent = `map ${snapshot.map_id ?? position.map_id ?? "-"}`;
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
        <span class="legend-pill"><span class="legend-dot" data-tone="player"></span>Player</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="explored"></span>Explored</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="frontier"></span>Frontier</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="wall"></span>Wall</span>
        <span class="legend-pill"><span class="legend-dot" data-tone="warp"></span>Warp</span>
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
                label: item.type || "goal",
                description: item.description,
            });
        }
    }

    els.focusText.textContent = grouped.focus || "No live focus yet.";

    renderSimpleList(
        els.activeGoalsList,
        grouped.active,
        (item) => `<strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.description)}</p>`,
        "No active goals.",
    );
    renderSimpleList(
        els.todoList,
        grouped.todos,
        (item, index) => `<strong>TODO ${index + 1}</strong><p>${escapeHtml(item)}</p>`,
        "No pending tasks.",
    );
    renderSimpleList(
        els.doneList,
        grouped.done,
        (item) => `<strong>Done</strong><p>${escapeHtml(item)}</p>`,
        "No completed items yet.",
    );
}

function renderHistory() {
    if (!state.history.length) {
        els.historyList.innerHTML = "<div class=\"list-item empty-state\">No decision history yet.</div>";
        return;
    }

    els.historyList.innerHTML = state.history
        .slice()
        .reverse()
        .slice(0, 30)
        .map((item) => `
            <div class="list-item">
                <strong>Turn ${escapeHtml(item.turn ?? "-")} | ${escapeHtml(String(item.action || "wait").toUpperCase())}</strong>
                <p>${escapeHtml(item.reasoning || "No reasoning recorded.")}</p>
                <p class="mono">${escapeHtml(item.screen_type || "unknown")} | ${escapeHtml(formatTimestamp(item.timestamp))}</p>
            </div>
        `)
        .join("");
}

function renderEvents() {
    if (!state.events.length) {
        els.eventList.innerHTML = "<div class=\"list-item empty-state\">Waiting for runtime events.</div>";
        return;
    }

    els.eventList.innerHTML = state.events
        .slice()
        .reverse()
        .slice(0, 30)
        .map((item) => `
            <div class="list-item event-item" data-type="${escapeHtml(item.type || "info")}">
                <strong>${escapeHtml(item.type || "info")}</strong>
                <p>${escapeHtml(item.message || "")}</p>
                <p class="mono">${escapeHtml(formatTimestamp(item.timestamp))}</p>
            </div>
        `)
        .join("");
}

function updateControlButtons(control) {
    const pauseButton = document.querySelector('[data-command="pause"]');
    const resumeButton = document.querySelector('[data-command="resume"]');
    const stepButton = document.querySelector('[data-command="step"]');
    const loadLatestButton = document.querySelector('[data-command="load_latest_checkpoint"]');

    if (pauseButton) pauseButton.disabled = !control.running || control.paused;
    if (resumeButton) resumeButton.disabled = !control.running || !control.paused;
    if (stepButton) stepButton.disabled = !control.running;
    if (loadLatestButton) loadLatestButton.disabled = !state.checkpoints.length;
}

function renderControl() {
    const control = state.control || {};
    const running = Boolean(control.running);
    const paused = Boolean(control.paused);

    els.checkpointPillValue.textContent = String(control.checkpoint_count ?? state.checkpoints.length ?? 0);
    els.resumePillValue.textContent = control.auto_resume_latest_checkpoint ? "On" : "Off";

    if (!running) {
        els.runPill.textContent = "Stopped";
        els.runPill.dataset.tone = "danger";
        els.controlStateValue.textContent = "Stopped";
    } else if (paused) {
        els.runPill.textContent = "Paused";
        els.runPill.dataset.tone = "warning";
        els.controlStateValue.textContent = "Paused";
    } else {
        els.runPill.textContent = "Running";
        els.runPill.dataset.tone = "success";
        els.controlStateValue.textContent = "Auto";
    }

    els.stepBudgetValue.textContent = String(control.step_budget ?? 0);
    els.manualQueueValue.textContent = String(control.manual_queue_size ?? 0);
    els.lastCommandValue.textContent = control.last_command || "-";
    els.latestCheckpointInfo.textContent = control.latest_checkpoint || "None";
    els.restoredCheckpointInfo.textContent = control.restored_checkpoint || "Not restored";
    els.apiCooldownInfo.textContent = control.api_cooldown_active
        ? `${Number(control.api_cooldown_remaining ?? 0).toFixed(1)}s`
        : "None";
    els.controlErrorInfo.textContent = control.last_error || "None";
    updateControlButtons(control);
}

function renderCheckpoints() {
    const control = state.control || {};
    const latest = control.latest_checkpoint;
    const restored = control.restored_checkpoint;

    if (!state.checkpoints.length) {
        els.checkpointList.innerHTML = `
            <div class="checkpoint-card">
                <p class="empty-state">No checkpoints yet. Run a few turns and save one from the control panel.</p>
            </div>
        `;
        return;
    }

    els.checkpointList.innerHTML = state.checkpoints.map((checkpoint) => {
        const flags = [];
        if (checkpoint.name === latest) flags.push("Latest");
        if (checkpoint.name === restored) flags.push("Restore Source");

        const pos = checkpoint.position || {};
        return `
            <div class="checkpoint-card">
                <div class="checkpoint-head">
                    <div>
                        <strong>${escapeHtml(checkpoint.label || checkpoint.name || "checkpoint")}</strong>
                        <p class="mono">${escapeHtml(checkpoint.name || "-")}</p>
                    </div>
                    <div class="tag-row">
                        ${(flags.length ? flags : ["Saved"])
                            .map((flag) => `<span class="tag">${escapeHtml(flag)}</span>`)
                            .join("")}
                    </div>
                </div>
                <div class="checkpoint-meta">
                    <span class="tag">turn ${escapeHtml(checkpoint.turn ?? "-")}</span>
                    <span class="tag">${escapeHtml(checkpoint.screen_type || "unknown")}</span>
                    <span class="tag">${escapeHtml(formatTimestamp(checkpoint.created_at))}</span>
                </div>
                <div class="checkpoint-body">
                    <p>Position: map ${escapeHtml(pos.map_id ?? "-")} | (${escapeHtml(pos.x ?? "-")}, ${escapeHtml(pos.y ?? "-")})</p>
                    <p>Progress: badges ${escapeHtml(checkpoint.badges ?? 0)} | party ${escapeHtml(checkpoint.party_size ?? 0)} | money ${escapeHtml(formatMoney(checkpoint.money))}</p>
                    <p>Focus: ${escapeHtml(checkpoint.focus || checkpoint.primary_goal || "Not recorded")}</p>
                </div>
                <div class="checkpoint-actions">
                    <button type="button" data-load-checkpoint="${escapeHtml(checkpoint.name || "")}">Load checkpoint</button>
                </div>
            </div>
        `;
    }).join("");
}

function renderParty() {
    const party = state.game.party || [];

    if (!els.partyList) {
        return;
    }

    if (!party.length) {
        els.partyList.innerHTML = "<div class=\"list-item empty-state\">No Pokemon captured yet.</div>";
        return;
    }

    els.partyList.innerHTML = party.map((pokemon, index) => {
        const name = pokemon.display_name || pokemon.name || pokemon.species || "Unknown Pokemon";
        const currentHp = Number(pokemon.current_hp ?? pokemon.hp ?? 0);
        const maxHp = Number(pokemon.max_hp ?? 0);
        const hpRatio = maxHp > 0 ? Math.max(0, Math.min(1, currentHp / maxHp)) : 0;
        const hpPercent = maxHp > 0 ? `${Math.round(hpRatio * 100)}%` : "N/A";
        const hpState = hpRatio <= 0.25 ? "danger" : hpRatio <= 0.5 ? "warning" : "healthy";

        return `
            <article class="party-card" data-hp-state="${hpState}">
                <div class="party-top">
                    <span class="party-slot mono">${String(index + 1).padStart(2, "0")}</span>
                    <div class="party-body">
                        <strong>${escapeHtml(name)}</strong>
                        <p>Lv ${escapeHtml(pokemon.level ?? "?")} | HP ${escapeHtml(currentHp)} / ${escapeHtml(maxHp || "?")}</p>
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
            throw new Error(result.message || `Command failed: ${command}`);
        }

        showToast(result.message || `Sent ${command}`);
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
    return command === "stop" || command === "load_latest_checkpoint";
}

function bindControls() {
    document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => {
            const command = button.dataset.command;
            if (shouldConfirm(command) && !window.confirm(`Confirm ${command}?`)) {
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

        if (!window.confirm(`Load checkpoint ${checkpointName}? This will pause auto play.`)) {
            return;
        }
        sendControl("load_checkpoint", checkpointName);
    });

    const refreshButton = document.getElementById("refreshButton");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            await refreshAll();
            await refreshFallbackScreenshot();
            showToast("Dashboard data refreshed");
        });
    }
}

function bindStreamHandlers() {
    els.streamImage.addEventListener("load", () => {
        els.streamPlaceholder.style.display = "none";
        els.streamImage.hidden = false;
        els.fallbackImage.hidden = true;
        setConnection(true, "Stream online");
    });

    els.streamImage.addEventListener("error", async () => {
        els.streamPlaceholder.textContent =
            "The live stream is currently unavailable, so the dashboard switched to screenshot fallback mode. This is expected for autonomous_smoke runs.";
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
