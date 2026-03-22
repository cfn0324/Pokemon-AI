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
    return date.toLocaleString("zh-CN", {
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
    return Number.isFinite(num) ? num.toLocaleString("zh-CN") : "0";
}

function setConnection(ok, message) {
    els.connectionPill.textContent = message;
    els.connectionPill.dataset.tone = ok ? "success" : "danger";
}

function showDisconnectedRuntime(error) {
    const detail = error?.message ? `最近更新失败: ${error.message}` : "最近更新失败";
    els.statusDetailPill.textContent = detail;
    els.streamPlaceholder.textContent = "未连接到实时运行。若你启动的是 scripts/autonomous_smoke.py，这是正常现象；该脚本会关闭可视化并限制回合数。想看实时画面和模型状态，请运行 python main.py。";
    els.streamPlaceholder.style.display = "grid";
    els.streamImage.hidden = true;
    els.fallbackImage.hidden = true;
    els.screenSummary.textContent = "当前没有游戏画面输入到仪表盘。";
    els.harnessSummary.textContent = "仪表盘只会在运行中的可视化实例推送状态时更新。";
    els.movementSummary.textContent = "等待新的运行实例连接。";
    els.decisionReasoning.textContent = "当前没有实时模型状态。若只是做 checkpoint 烟测，请看终端输出或生成的 JSON 报告。";
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
        renderParty();

        setConnection(true, "数据已连接");
    } catch (error) {
        setConnection(false, "数据连接断开");
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
    const screenType = state.decision.screen_type || visual.screen_type || visual.ram_screen_type || "unknown";
    const localAnalysisEnabled = Boolean(visual.local_analysis_enabled);

    els.turnPillValue.textContent = String(game.turn ?? state.control.turn ?? 0);
    els.statusDetailPill.textContent = `最近更新: ${formatTimestamp(game.timestamp || state.decision.timestamp || state.control.last_command_at)}`;

    els.screenTypeTag.textContent = `SCREEN_TYPE ${screenType}`;
    els.visionModeTag.textContent = localAnalysisEnabled ? "pixel heuristics on" : "raw screenshot + RAM";

    let phase = "自由探索";
    if (game.in_battle) phase = "战斗中";
    else if (game.pre_starter_script) phase = "开场脚本";
    else if (game.pre_world) phase = "前世界状态";
    else if (game.phase_hint) phase = String(game.phase_hint);
    els.phaseTag.textContent = phase;

    els.screenSummary.textContent = visual.description || "等待画面描述";
    els.harnessSummary.textContent = localAnalysisEnabled
        ? "本地像素启发已启用，页面只展示紧凑结果。"
        : "未启用本地像素分析，依赖原始截图和 RAM，由大模型自行识别画面。";
    els.movementSummary.textContent = deltas.stuck_hint
        ? `${deltas.stuck_hint}${deltas.position_changed ? "；本回合有位置变化。" : ""}`
        : "等待更多状态变化。";

    els.statTurn.textContent = String(game.turn ?? 0);
    els.statBadges.textContent = `${game.badges ?? 0} / 8`;
    els.statMoney.textContent = formatMoney(game.money);
    els.statParty.textContent = String(game.party_size ?? (game.party || []).length || 0);
    els.statMap.textContent = position.map_id ?? "-";
    els.statCoords.textContent = position.x != null && position.y != null
        ? `${position.x}, ${position.y}`
        : "-";
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
    els.decisionReasoning.textContent = decision.reasoning || "当前还没有模型解释。";
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

    els.focusText.textContent = grouped.focus || "暂无即时焦点，等待模型更新。";
    renderSimpleList(
        els.activeGoalsList,
        grouped.active,
        (item) => `<strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.description)}</p>`,
        "暂无活动目标。",
    );
    renderSimpleList(
        els.todoList,
        grouped.todos,
        (item, index) => `<strong>TODO ${index + 1}</strong><p>${escapeHtml(item)}</p>`,
        "暂无待办。",
    );
    renderSimpleList(
        els.doneList,
        grouped.done,
        (item) => `<strong>已完成</strong><p>${escapeHtml(item)}</p>`,
        "暂无已完成记录。",
    );
}

function renderHistory() {
    if (!state.history.length) {
        els.historyList.innerHTML = `<div class="list-item empty-state">还没有决策记录。</div>`;
        return;
    }

    els.historyList.innerHTML = state.history
        .slice()
        .reverse()
        .slice(0, 30)
        .map((item) => `
            <div class="list-item">
                <strong>回合 ${escapeHtml(item.turn ?? "-")} · ${escapeHtml(String(item.action || "wait").toUpperCase())}</strong>
                <p>${escapeHtml(item.reasoning || "无解释")}</p>
                <p class="mono">${escapeHtml(item.screen_type || "unknown")} · ${escapeHtml(formatTimestamp(item.timestamp))}</p>
            </div>
        `)
        .join("");
}

function renderEvents() {
    if (!state.events.length) {
        els.eventList.innerHTML = `<div class="list-item empty-state">等待运行事件。</div>`;
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
    els.resumePillValue.textContent = control.auto_resume_latest_checkpoint ? "开启" : "关闭";

    if (!running) {
        els.runPill.textContent = "已停止";
        els.runPill.dataset.tone = "danger";
        els.controlStateValue.textContent = "停止";
    } else if (paused) {
        els.runPill.textContent = "已暂停";
        els.runPill.dataset.tone = "warning";
        els.controlStateValue.textContent = "暂停";
    } else {
        els.runPill.textContent = "运行中";
        els.runPill.dataset.tone = "success";
        els.controlStateValue.textContent = "自动运行";
    }

    els.stepBudgetValue.textContent = String(control.step_budget ?? 0);
    els.manualQueueValue.textContent = String(control.manual_queue_size ?? 0);
    els.lastCommandValue.textContent = control.last_command || "-";
    els.latestCheckpointInfo.textContent = control.latest_checkpoint || "暂无";
    els.restoredCheckpointInfo.textContent = control.restored_checkpoint || "尚未恢复";
    els.apiCooldownInfo.textContent = control.api_cooldown_active
        ? `${Number(control.api_cooldown_remaining ?? 0).toFixed(1)}s`
        : "无";
    els.controlErrorInfo.textContent = control.last_error || "无";
    updateControlButtons(control);
}

function renderCheckpoints() {
    const control = state.control || {};
    const latest = control.latest_checkpoint;
    const restored = control.restored_checkpoint;

    if (!state.checkpoints.length) {
        els.checkpointList.innerHTML = `
            <div class="checkpoint-card">
                <p class="empty-state">暂无检查点。运行几回合后可保存并恢复。</p>
            </div>
        `;
        return;
    }

    els.checkpointList.innerHTML = state.checkpoints.map((checkpoint) => {
        const flags = [];
        if (checkpoint.name === latest) flags.push("最新");
        if (checkpoint.name === restored) flags.push("当前恢复源");
        const pos = checkpoint.position || {};
        return `
            <div class="checkpoint-card">
                <div class="checkpoint-head">
                    <div>
                        <strong>${escapeHtml(checkpoint.label || checkpoint.name || "checkpoint")}</strong>
                        <p class="mono">${escapeHtml(checkpoint.name || "-")}</p>
                    </div>
                    <div class="tag-row">
                        ${(flags.length ? flags : ["存档"]).map((flag) => `<span class="tag">${escapeHtml(flag)}</span>`).join("")}
                    </div>
                </div>
                <div class="checkpoint-meta">
                    <span class="tag">turn ${escapeHtml(checkpoint.turn ?? "-")}</span>
                    <span class="tag">${escapeHtml(checkpoint.screen_type || "unknown")}</span>
                    <span class="tag">${escapeHtml(formatTimestamp(checkpoint.created_at))}</span>
                </div>
                <div class="checkpoint-body">
                    <p>位置: map ${escapeHtml(pos.map_id ?? "-")} · (${escapeHtml(pos.x ?? "-")}, ${escapeHtml(pos.y ?? "-")})</p>
                    <p>进度: 徽章 ${escapeHtml(checkpoint.badges ?? 0)} · 队伍 ${escapeHtml(checkpoint.party_size ?? 0)} · 金钱 ${escapeHtml(formatMoney(checkpoint.money))}</p>
                    <p>焦点: ${escapeHtml(checkpoint.focus || checkpoint.primary_goal || "未记录")}</p>
                </div>
                <div class="checkpoint-actions">
                    <button type="button" data-load-checkpoint="${escapeHtml(checkpoint.name || "")}">加载此检查点</button>
                </div>
            </div>
        `;
    }).join("");
}

function renderParty() {
    const party = state.game.party || [];
    if (!party.length) {
        els.partyList.innerHTML = `<div class="list-item empty-state">尚未获得宝可梦。</div>`;
        return;
    }

    els.partyList.innerHTML = party.map((pokemon) => `
        <div class="list-item">
            <div class="party-entry">
                <div>
                    <strong>${escapeHtml(pokemon.name || "未知宝可梦")}</strong>
                    <p>HP ${escapeHtml(pokemon.hp ?? "?")} / ${escapeHtml(pokemon.max_hp ?? "?")}</p>
                </div>
                <div class="party-level">Lv ${escapeHtml(pokemon.level ?? "?")}</div>
            </div>
        </div>
    `).join("");
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
            throw new Error(result.message || `命令失败: ${command}`);
        }
        showToast(result.message || `已发送 ${command}`);
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
            if (shouldConfirm(command) && !window.confirm(`确认执行 ${command} ?`)) {
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
        if (!window.confirm(`确认加载检查点 ${checkpointName} ? 加载后会暂停自动运行。`)) {
            return;
        }
        sendControl("load_checkpoint", checkpointName);
    });

    const refreshButton = document.getElementById("refreshButton");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            await refreshAll();
            await refreshFallbackScreenshot();
            showToast("已刷新页面数据");
        });
    }
}

function bindStreamHandlers() {
    els.streamImage.addEventListener("load", () => {
        els.streamPlaceholder.style.display = "none";
        els.streamImage.hidden = false;
        els.fallbackImage.hidden = true;
        setConnection(true, "实时流在线");
    });

    els.streamImage.addEventListener("error", async () => {
        els.streamPlaceholder.textContent = "实时流暂不可用，已切换到截图回退。若你运行的是 scripts/autonomous_smoke.py，这属于预期行为。";
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

