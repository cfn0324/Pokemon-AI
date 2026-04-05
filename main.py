"""宝可梦AI智能体的主入口点。"""

import os
import sys
import time
import signal
import queue
import threading
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from io import BytesIO
import numpy as np
from PIL import Image

# 从.env文件加载环境变量
from dotenv import load_dotenv
load_dotenv()

from src.utils.config import get_config
from src.utils.env import apply_env_aliases
from src.utils.logger import get_logger
from src.emulator.game_boy import GameBoyEmulator
from src.emulator.memory_reader import MemoryReader
from src.state.game_state import GameState
from src.state.vision import VisionProcessor
from src.state.map_memory import MapMemory
from src.agents.main_agent import AIDecisionRetrySignal, MainAgent
from src.agents.pathfinder import PathfinderAgent
from src.agents.puzzle_solver import PuzzleSolverAgent
from src.agents.critic import CriticAgent
from src.tools.action_executor import ActionExecutor
from src.tools.progress_tracker import ProgressTracker
from src.visualization.visualizer import GameVisualizer
from src.agents.async_decision import AsyncDecisionMaker
from src.control.decision_engine import DecisionContext, DecisionEngine
from src.control.early_battle_controller import EarlyBattleController
from src.control.oak_lab_pre_starter import OakLabPreStarterController
from src.control.oak_lab_post_starter import OakLabPostStarterController
from src.control.oak_lab_rival_battle import OakLabRivalBattleController
from src.control.oak_lab_starter import OakLabStarterController
from src.control.post_battle_intro_route import PostBattleIntroRouteController
from src.control.post_pokedex_departure_controller import PostPokedexDepartureController
from src.control.viridian_parcel_controller import ViridianParcelController
from src.runtime.checkpoints import (
    build_checkpoint_metadata,
    list_checkpoints,
    list_startup_checkpoints,
    load_checkpoint_metadata,
    prune_old_checkpoints,
    write_checkpoint_metadata,
)

apply_env_aliases()


class PokemonAIAgent:
    """宝可梦AI智能体的主协调器。"""

    def __init__(self, config_path: str = "config.yaml"):
        """初始化AI智能体系统。

        参数:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = get_config(config_path)
        self.logger = get_logger('Main',
                                log_dir=self.config.get('logging.log_dir'),
                                level=self.config.get('logging.level'))

        self.logger.milestone("宝可梦AI智能体启动中")

        # 运行时状态
        self.running = False
        self.turn_count = 0
        self.max_turns = max(0, int(self.config.get("testing.max_turns", 0) or 0))
        self.last_checkpoint_turn = 0
        self._restored_checkpoint_name: Optional[str] = None
        self._prev_screen_type = None
        self._dialogue_exit_grace = 0
        self._text_entry_step = 0
        self._screen_type_streak = 0
        self._last_observed_state: Optional[Dict[str, Any]] = None
        self._last_action: Optional[str] = None
        self._last_action_reasoning: str = ""
        self._last_action_source: Optional[str] = None
        self._recent_warp_exit: Optional[Dict[str, Any]] = None
        self._planned_actions: List[str] = []
        self._planned_target: Optional[tuple] = None
        self._planned_reasoning: str = ""
        self._pending_trigger_tile: Optional[Dict[str, tuple]] = None
        self._temporarily_avoided_frontiers: Dict[tuple, int] = {}
        self._temporarily_avoided_moves: Dict[tuple, int] = {}
        self._last_guidance_turn = 0
        self._last_screen_signature: Optional[tuple] = None
        self._stable_screen_turns = 0
        self._active_landmark_checkpoints: set[str] = set()
        self._scripted_ui_actions: List[str] = []
        self._scripted_ui_reasoning: str = ""
        self._scripted_bootstrap_steps: List[Dict[str, str]] = []
        self._scripted_bootstrap_reasoning: str = ""
        self._last_fatal_error: Optional[str] = None
        self._recent_battle_visual_grace_turns = 0
        self.oak_lab_pre_starter = OakLabPreStarterController()
        self.oak_lab_starter = OakLabStarterController()
        self.oak_lab_post_starter = OakLabPostStarterController()
        self.oak_lab_rival_battle = OakLabRivalBattleController()
        self.early_battle_controller = EarlyBattleController()
        self.post_battle_intro_route = PostBattleIntroRouteController()
        self.viridian_parcel_controller = ViridianParcelController()
        self.post_pokedex_departure_controller = PostPokedexDepartureController()

        # 可视化控制状态
        self._control_lock = threading.Lock()
        self._paused = False
        self._step_budget = 0
        self._checkpoint_requested = False
        self._manual_actions: queue.Queue[str] = queue.Queue(maxsize=32)
        self._last_control_command = ""
        self._last_control_timestamp = None
        self._last_control_error = None
        self._phase_hint_turns_remaining = 0
        self._startup_selection_pending = False

        # 初始化组件
        self._init_emulator()
        self._init_state_systems()
        self._init_agents()
        self._init_tools()
        self._maybe_restore_initial_checkpoint()

        # 设置信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)

        self.logger.info("宝可梦AI智能体初始化成功")

    def _init_emulator(self) -> None:
        """初始化模拟器。"""
        self.logger.info("正在初始化模拟器...")

        rom_path = self.config.get('game.rom_path')
        headless = self.config.get('game.headless')
        speed = self.config.get('game.speed')

        self.emulator = GameBoyEmulator(rom_path, headless, speed)
        self.memory_reader = MemoryReader(self.emulator)

        self.logger.info("模拟器初始化完成")

    def _init_state_systems(self) -> None:
        """初始化状态观察系统。"""
        self.logger.info("正在初始化状态系统...")

        self.vision = VisionProcessor()
        self.map_memory = MapMemory()

        self.game_state = GameState(
            self.emulator,
            self.memory_reader,
            self.vision,
            self.map_memory,
            visual_enabled=self.config.get('performance.visual_enabled', False)
        )

        self.logger.info("状态系统初始化完成")

    def _init_agents(self) -> None:
        """初始化AI智能体。"""
        self.logger.info("正在初始化AI智能体...")

        self.main_agent = MainAgent()
        self.pathfinder = PathfinderAgent()
        self.puzzle_solver = PuzzleSolverAgent()
        self.critic = CriticAgent()

        self.logger.info("AI智能体初始化完成")

    def _init_tools(self) -> None:
        """初始化工具。"""
        self.logger.info("正在初始化工具...")

        self.action_executor = ActionExecutor(self.emulator, self.memory_reader)
        self.progress_tracker = ProgressTracker()

        # 初始化异步决策器以实现非阻塞AI
        self.async_ai = AsyncDecisionMaker(self.main_agent)
        if self.config.get('performance.async_decisions', True):
            self.async_ai.start()
            self.logger.info("异步AI决策已启用")

        # 初始化可视化器
        vis_port = self.config.get('visualization.port', 5000)
        self.visualizer = GameVisualizer(port=vis_port)
        self.visualizer.set_control_handler(self)
        self.visualizer.set_frame_source(self.emulator)
        self._init_decision_engine()

        # 如果启用则启动可视化器
        if self.config.get('visualization.enabled', True):
            self.visualizer.start()
            self.visualizer.update_checkpoints(self.get_available_checkpoints())
            self.logger.info(f"可视化仪表板可访问：http://localhost:{vis_port}")
            self._broadcast_control_state()

        self.logger.info("工具初始化完成")

    def _init_decision_engine(self) -> None:
        """Initialize the control-layer decision router."""
        if self._pure_llm_mode_enabled():
            self.decision_engine = DecisionEngine(
                stages=[],
                fallback=self._stage_ai_decision,
            )
            return

        self.decision_engine = DecisionEngine(
            stages=self._get_decision_stage_specs(),
            fallback=self._stage_ai_decision,
        )

    def _config_get(self, key: str, default=None):
        """Read a config value safely for lightweight tests that bypass __init__."""
        config = getattr(self, "config", None)
        if config is None or not hasattr(config, "get"):
            return default
        return config.get(key, default)

    def _pure_llm_mode_enabled(self) -> bool:
        """Return whether deterministic control helpers should be disabled."""
        return bool(self._config_get("decision.pure_llm_mode", False))

    def _llm_primary_mode_enabled(self) -> bool:
        """Return whether the runtime should prefer model decisions over tool routing."""
        return bool(self._config_get("decision.llm_primary_mode", False))

    def _llm_primary_action_plan_enabled(self) -> bool:
        """Return whether LLM-primary mode may reuse short AI movement plans."""
        return bool(self._config_get("decision.llm_primary_action_plan_enabled", True))

    def _ai_full_control_mode_enabled(self) -> bool:
        """Return whether AI should own normal gameplay while deterministic logic stays safety-only."""
        return bool(self._config_get("decision.ai_full_control_mode", False))

    def _llm_driven_mode_enabled(self) -> bool:
        """Return whether the main model should own ordinary turn-by-turn control."""
        return bool(
            self._pure_llm_mode_enabled()
            or self._llm_primary_mode_enabled()
        )

    def _research_mode_enabled(self) -> bool:
        """Return whether fixed route-script controllers should be disabled."""
        return bool(self._config_get("decision.research_mode", False))

    def _get_decision_stage_specs(self) -> List[tuple]:
        """Build the deterministic stage list for the current runtime mode."""
        ai_owned_stage_names = {
            "oak_lab_pre_starter",
            "oak_lab_starter",
            "oak_lab_post_starter",
            "oak_lab_rival_battle",
            "early_battle",
            "post_battle_intro_route",
            "viridian_parcel",
            "post_pokedex_departure",
        }
        stage_specs = [
            ("bootstrap", self._stage_bootstrap_decision),
            ("known_ui", self._stage_known_ui_decision),
            ("stable_ui_recovery", self._stage_stable_ui_recovery_decision),
            ("oak_lab_starter", self._stage_oak_lab_starter_decision),
            ("oak_lab_pre_starter", self._stage_oak_lab_pre_starter_decision),
            ("oak_lab_post_starter", self._stage_oak_lab_post_starter_decision),
            ("oak_lab_rival_battle", self._stage_oak_lab_rival_battle_decision),
            ("early_battle", self._stage_early_battle_decision),
            ("post_battle_intro_route", self._stage_post_battle_intro_route_decision),
            ("viridian_parcel", self._stage_viridian_parcel_decision),
            ("post_pokedex_departure", self._stage_post_pokedex_departure_decision),
            ("dialogue_timing", self._stage_dialogue_timing_decision),
            ("post_warp_reentry_guard", self._stage_post_warp_reentry_guard_decision),
            ("navigation_plan", self._stage_navigation_plan_decision),
            ("pre_starter_recovery", self._stage_pre_starter_recovery_decision),
            ("early_story_interaction", self._stage_early_story_interaction_decision),
            ("dialogue_auto_advance", self._stage_dialogue_auto_advance_decision),
            ("menu_auto_close", self._stage_menu_auto_close_decision),
            ("text_entry_api_cooldown", self._stage_text_entry_api_cooldown_decision),
        ]
        if self._llm_primary_mode_enabled():
            llm_primary_specs = [
                ("bootstrap", self._stage_bootstrap_decision),
                ("minimal_known_ui", self._stage_minimal_known_ui_decision),
                ("post_warp_reentry_guard", self._stage_post_warp_reentry_guard_decision),
                ("early_battle", self._stage_early_battle_decision),
                ("post_battle_intro_route", self._stage_post_battle_intro_route_decision),
                ("viridian_parcel", self._stage_viridian_parcel_decision),
                ("post_pokedex_departure", self._stage_post_pokedex_departure_decision),
                ("recent_warp_buffer_guard", self._stage_recent_warp_buffer_guard_decision),
                ("guided_navigation_escape", self._stage_guided_navigation_escape_decision),
                ("cached_ai_plan", self._stage_cached_ai_plan_decision),
                ("stable_ui_recovery", self._stage_stable_ui_recovery_decision),
                ("menu_auto_close", self._stage_menu_auto_close_decision),
                ("text_entry_api_cooldown", self._stage_text_entry_api_cooldown_decision),
            ]
            if self._ai_full_control_mode_enabled():
                return [
                    item
                    for item in llm_primary_specs
                    if item[0] not in ai_owned_stage_names
                ]
            return llm_primary_specs

        if self._ai_full_control_mode_enabled():
            stage_specs = [
                item
                for item in stage_specs
                if item[0] not in ai_owned_stage_names
            ]

        if not self._research_mode_enabled():
            return stage_specs

        disabled = {
            "oak_lab_pre_starter",
            "oak_lab_starter",
            "oak_lab_post_starter",
            "oak_lab_rival_battle",
            "post_battle_intro_route",
            "post_pokedex_departure",
        }
        return [item for item in stage_specs if item[0] not in disabled]

    def _checkpoint_writes_enabled(self) -> bool:
        """Return whether the current run is allowed to write checkpoints."""
        return bool(self.config.get("testing.write_checkpoints", True))

    def _same_turn_retry_enabled(self) -> bool:
        """Retry transient AI failures without spending a gameplay turn in pure-LLM mode."""
        return bool(
            self._llm_driven_mode_enabled()
            and self.config.get("decision.retry_same_turn_on_ai_error", True)
        )

    def _decide_action_for_current_turn(self, context: DecisionContext) -> dict:
        """Request a decision, retrying transient pure-LLM failures on the same observation."""
        if not self._same_turn_retry_enabled():
            return self.decision_engine.decide(context)

        max_attempts = max(1, int(self.config.get("decision.same_turn_retry_max_attempts", 12) or 12))
        timeout_seconds = max(
            0.0,
            float(self.config.get("decision.same_turn_retry_timeout_seconds", 45) or 45),
        )
        min_delay_seconds = max(
            0.0,
            float(self.config.get("decision.same_turn_retry_min_delay_seconds", 0.25) or 0.25),
        )
        started_at = time.monotonic()
        attempt = 0

        while True:
            attempt += 1
            try:
                return self.decision_engine.decide(context)
            except AIDecisionRetrySignal as exc:
                elapsed = time.monotonic() - started_at
                if attempt >= max_attempts or (timeout_seconds and elapsed >= timeout_seconds):
                    return self._build_same_turn_retry_exhausted_decision(
                        context,
                        exc,
                        attempt,
                        elapsed,
                    )

                remaining_budget = None
                if timeout_seconds:
                    remaining_budget = max(0.0, timeout_seconds - elapsed)
                delay_seconds = max(min_delay_seconds, exc.retry_after_seconds)
                if remaining_budget is not None:
                    delay_seconds = min(delay_seconds, remaining_budget)

                self.logger.warning(
                    "Retrying same-turn AI decision "
                    f"({exc.source}) on agent turn {self.turn_count} "
                    f"in {delay_seconds:.1f}s [attempt {attempt}/{max_attempts}]"
                )
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

    def _build_same_turn_retry_exhausted_decision(
        self,
        context: DecisionContext,
        exc: AIDecisionRetrySignal,
        attempt: int,
        elapsed: float,
    ) -> dict:
        """Degrade to deterministic recovery instead of aborting the whole run."""
        detail = (
            "Same-turn AI retry budget exhausted "
            f"after {attempt} attempts over {elapsed:.1f}s: {exc}"
        )
        self.logger.error(detail)
        self._clear_planned_actions()
        return {
            "action": "wait",
            "reasoning": detail,
            "goal_update": None,
            "recorded_in_context": False,
            "decision_source": "ai_error",
            "decision_path": "ai",
            "screen_type": context.screen_type,
            "decision_trace": [f"same_turn_retry_exhausted:{exc.source}"],
        }

    def _stage_bootstrap_decision(self, context: DecisionContext) -> Optional[dict]:
        return self._get_pre_starter_bootstrap_decision(
            context.current_state,
            context.screen_type,
        )

    def _stage_known_ui_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_known_ui_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_minimal_known_ui_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_minimal_known_ui_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_cached_ai_plan_decision(self, context: DecisionContext) -> Optional[dict]:
        return self._get_cached_ai_plan_decision(
            context.current_state,
            context.screen_type,
        )

    def _stage_stable_ui_recovery_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_stable_ui_recovery_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_dialogue_timing_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_dialogue_timing_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_post_warp_reentry_guard_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_post_warp_reentry_guard_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_recent_warp_buffer_guard_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_recent_warp_buffer_guard_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_guided_navigation_escape_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_guided_navigation_escape_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_oak_lab_pre_starter_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.oak_lab_pre_starter.maybe_decide(
            context.current_state,
            context.screen_type,
            context.screen_hash,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_oak_lab_starter_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.oak_lab_starter.maybe_decide(
            context.current_state,
            context.screen_hash,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_oak_lab_post_starter_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.oak_lab_post_starter.maybe_decide(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_oak_lab_rival_battle_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.oak_lab_rival_battle.maybe_decide(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_early_battle_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.early_battle_controller.maybe_decide(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_post_battle_intro_route_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.post_battle_intro_route.maybe_decide(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_viridian_parcel_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.viridian_parcel_controller.maybe_decide(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_post_pokedex_departure_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self.post_pokedex_departure_controller.maybe_decide(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_navigation_plan_decision(self, context: DecisionContext) -> Optional[dict]:
        return self._get_navigation_plan_decision(
            context.current_state,
            context.screen_type,
        )

    def _stage_pre_starter_recovery_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_pre_starter_recovery_move_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_early_story_interaction_decision(self, context: DecisionContext) -> Optional[dict]:
        decision = self._get_early_story_interaction_decision(
            context.current_state,
            context.screen_type,
        )
        if decision:
            self._clear_planned_actions()
        return decision

    def _stage_dialogue_auto_advance_decision(self, context: DecisionContext) -> Optional[dict]:
        if context.screen_type != "dialogue" or not self._should_auto_advance_dialogue():
            return None
        self._clear_planned_actions()
        return {
            "action": "a",
            "reasoning": "自动处理：推进当前对话",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _stage_menu_auto_close_decision(self, context: DecisionContext) -> Optional[dict]:
        if not self._should_auto_close_menu(context.current_state, context.screen_type):
            return None
        self._clear_planned_actions()
        return {
            "action": "b",
            "reasoning": f"自动处理：关闭早期流程中的 {context.screen_type} 界面，回到主场景",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _stage_text_entry_api_cooldown_decision(self, context: DecisionContext) -> Optional[dict]:
        if context.screen_type != "text_entry" or not self.main_agent.is_in_api_cooldown():
            return None
        self._clear_planned_actions()
        return {
            "action": "b",
            "reasoning": "自动处理：检测到文本输入界面且 API 正在冷却，执行保守恢复",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _stage_ai_decision(self, context: DecisionContext) -> Optional[dict]:
        return self._get_ai_decision_responsive(
            context.current_state,
            context.state_text,
            context.screenshot_bytes,
        )

    def _decorate_api_fallback_decision(
        self,
        decision: Optional[dict],
        decision_source: str,
    ) -> Optional[dict]:
        """Normalize a deterministic fallback chosen after an AI transport failure."""
        if not isinstance(decision, dict):
            return None

        reasoning = " ".join(str(decision.get("reasoning") or "").split()).strip()
        if reasoning:
            decision["reasoning"] = f"Auto fallback while AI is unavailable: {reasoning}"
        else:
            decision["reasoning"] = "Auto fallback while AI is unavailable"
        decision["goal_update"] = decision.get("goal_update")
        decision["recorded_in_context"] = False
        decision["decision_source"] = decision_source
        decision["decision_path"] = "fallback"
        return decision

    def _get_local_safe_exploration_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Pick a conservative field-movement fallback when the model is unavailable."""
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            return None

        memory = current_state.get("memory", {}) or {}
        if memory.get("in_battle"):
            return None

        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", 0) or 0)
        x = int(position.get("x", 0) or 0)
        y = int(position.get("y", 0) or 0)
        start_key = (map_id, x, y)

        navigation = current_state.get("navigation", {}) or {}
        movement_pattern = current_state.get("movement_pattern", {}) or {}
        frontier_guidance = navigation.get("frontier_guidance", {}) or {}
        current_visit_count = int(navigation.get("current_visit_count", 0) or 0)
        config = getattr(self, "config", None)
        loop_visit_threshold = max(
            1,
            int(
                (config.get("navigation.local_fallback_force_plan_visit_threshold", 8) if config else 8)
                or 8
            ),
        )
        if (
            bool(movement_pattern.get("micro_loop_warning"))
            or current_visit_count >= loop_visit_threshold
            or bool(frontier_guidance.get("prefer_leave_current_frontier"))
        ):
            planned_escape = self._get_navigation_plan_decision(
                current_state,
                screen_type,
                force=True,
            )
            if planned_escape:
                return {
                    "action": planned_escape.get("action"),
                    "reasoning": (
                        "Use the learned frontier route instead of probing another weak local loop"
                    ),
                    "goal_update": None,
                    "recorded_in_context": False,
                }

        vision = current_state.get("visual", {}).get("navigation_hints", {}) or {}
        blocked = set(navigation.get("blocked_directions", []))
        blocked.update(vision.get("blocked_directions", []))
        blocked.update(
            direction
            for direction in ("up", "down", "left", "right")
            if self._is_temporarily_avoided_move(start_key, direction)
        )
        retryable_directions = self._get_retryable_field_directions(current_state)

        candidates: List[str] = []
        nearby_unexplored = current_state.get("exploration", {}).get("nearby_unexplored", []) or []
        if nearby_unexplored:
            target = nearby_unexplored[0]
            if isinstance(target, (list, tuple)) and len(target) >= 2:
                tx = int(target[0] or 0)
                ty = int(target[1] or 0)
                dx = tx - x
                dy = ty - y
                if abs(dx) >= abs(dy):
                    if dx:
                        candidates.append("right" if dx > 0 else "left")
                    if dy:
                        candidates.append("down" if dy > 0 else "up")
                else:
                    if dy:
                        candidates.append("down" if dy > 0 else "up")
                    if dx:
                        candidates.append("right" if dx > 0 else "left")

        nearest_frontier = navigation.get("nearest_frontier") or {}
        if tuple(nearest_frontier.get("target") or ()) == (x, y):
            candidates.extend(nearest_frontier.get("unknown_directions", []) or [])

        for frontier in navigation.get("frontier_candidates", []) or []:
            if tuple(frontier.get("target") or ()) == (x, y):
                candidates.extend(frontier.get("unknown_directions", []) or [])

        candidates.extend(vision.get("walkable_directions", []) or [])
        candidates.extend(["up", "left", "right", "down"])

        seen: set[str] = set()
        for direction in candidates:
            normalized = str(direction or "").strip().lower()
            if normalized not in {"up", "down", "left", "right"}:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            if normalized not in retryable_directions:
                continue
            return {
                "action": normalized,
                "reasoning": f"Use local navigation hints to keep exploring via {normalized}",
                "goal_update": None,
                "recorded_in_context": False,
            }

        return None

    def _get_retryable_field_directions(self, current_state: dict) -> set[str]:
        """Return field directions that are still worth retrying despite stale blocked memory."""
        navigation = current_state.get("navigation", {}) or {}
        adjacent_tiles = navigation.get("adjacent_tiles", {}) or {}
        vision = current_state.get("visual", {}).get("navigation_hints", {}) or {}
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        start_key = (
            int(position.get("map_id", 0) or 0),
            int(position.get("x", 0) or 0),
            int(position.get("y", 0) or 0),
        )
        memory_blocked = {
            str(direction or "").strip().lower()
            for direction in navigation.get("blocked_directions", []) or []
            if str(direction or "").strip().lower() in {"up", "down", "left", "right"}
        }
        vision_blocked = {
            str(direction or "").strip().lower()
            for direction in vision.get("blocked_directions", []) or []
            if str(direction or "").strip().lower() in {"up", "down", "left", "right"}
        }

        retryable: set[str] = set()
        for direction in ("up", "down", "left", "right"):
            info = adjacent_tiles.get(direction) or {}
            status = str(info.get("status") or "").strip().lower()
            if info.get("target_is_warp") or info.get("step_triggers_warp"):
                continue
            if self._is_temporarily_avoided_move(start_key, direction):
                continue
            if status == "confirmed_blocked":
                continue
            if status in {"known_exit", "adjacent_explored"}:
                retryable.add(direction)
                continue
            if direction in vision_blocked:
                continue
            if direction in memory_blocked or status == "blocked_once":
                continue
            retryable.add(direction)

        return retryable

    def _get_temporarily_avoided_field_recovery_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Retry a single known-safe local step before degrading into blind interaction probing."""
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            return None

        memory = current_state.get("memory", {}) or {}
        if memory.get("in_battle"):
            return None
        if self._get_retryable_field_directions(current_state):
            return None

        navigation = current_state.get("navigation", {}) or {}
        adjacent_tiles = navigation.get("adjacent_tiles", {}) or {}
        vision = current_state.get("visual", {}).get("navigation_hints", {}) or {}
        position = memory.get("position", {}) or {}
        start_key = (
            int(position.get("map_id", 0) or 0),
            int(position.get("x", 0) or 0),
            int(position.get("y", 0) or 0),
        )
        vision_blocked = {
            str(direction or "").strip().lower()
            for direction in vision.get("blocked_directions", []) or []
            if str(direction or "").strip().lower() in {"up", "down", "left", "right"}
        }

        candidates: List[str] = []
        for direction in ("up", "down", "left", "right"):
            if direction in vision_blocked:
                continue
            if not self._is_temporarily_avoided_move(start_key, direction):
                continue
            info = adjacent_tiles.get(direction) or {}
            status = str(info.get("status") or "").strip().lower()
            if status not in {"known_exit", "adjacent_explored"}:
                continue
            if info.get("target_is_warp") or info.get("step_triggers_warp"):
                continue
            candidates.append(direction)

        if len(candidates) != 1:
            return None

        direction = candidates[0]
        return {
            "action": direction,
            "reasoning": (
                "Ordinary local retries are exhausted, but exactly one previously successful "
                f"non-warp path remains; retry {direction} before blind interaction probing"
            ),
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _get_blocked_field_interaction_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Probe likely hidden interactions when field movement is fully blocked."""
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            return None

        memory = current_state.get("memory", {}) or {}
        if memory.get("in_battle"):
            return None

        navigation = current_state.get("navigation", {}) or {}
        vision = current_state.get("visual", {}).get("navigation_hints", {}) or {}
        blocked = set(navigation.get("blocked_directions", []))
        blocked.update(vision.get("blocked_directions", []))
        if self._get_retryable_field_directions(current_state):
            return None
        if {"up", "down", "left", "right"} - blocked:
            return None

        try:
            repeat_a = bool(hasattr(self, "action_executor") and self._recent_actions_are_same("a", 4))
        except Exception:
            repeat_a = False

        action = "b" if repeat_a else "a"
        return {
            "action": action,
            "reasoning": (
                "All field directions are currently blocked, so probe the stuck scene with "
                f"{action.upper()} instead of idling"
            ),
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _get_safe_battle_progress_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Use conservative default inputs to keep battle-like screens moving without AI."""
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        battle = memory.get("battle", {}) or {}
        battle_summary = current_state.get("battle_summary", {}) or {}
        normalized_screen = str(screen_type or "").strip().lower()
        battle_phase = str(battle_summary.get("phase") or "").strip().lower()
        active_battle = (
            normalized_screen == "battle"
            or bool(memory.get("in_battle"))
            or battle_phase in {
                "entered_battle",
                "battle_in_progress",
                "post_battle_dialogue",
                "battle_just_ended",
            }
        )
        if not active_battle:
            return None

        enemy_hp_raw = battle.get("enemy_current_hp")
        try:
            enemy_hp = None if enemy_hp_raw is None else int(enemy_hp_raw)
        except (TypeError, ValueError):
            enemy_hp = None

        if ui_state.get("text_box_active") or battle_phase == "post_battle_dialogue":
            return {
                "action": "a",
                "reasoning": "Advance the visible battle dialogue until the next actionable prompt appears",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if ui_state.get("menu_active"):
            if enemy_hp is not None and enemy_hp <= 0:
                return {
                    "action": "b",
                    "reasoning": "Close the stale post-faint battle menu so the victory text can continue",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
            return {
                "action": "a",
                "reasoning": "Accept the default battle choice so the encounter keeps moving",
                "goal_update": None,
                "recorded_in_context": False,
            }

        return {
            "action": "a",
            "reasoning": "Advance the battle scene until the next menu or text prompt appears",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _get_ai_unavailable_fallback_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Choose a deterministic fallback when the model request failed or is cooling down."""
        normalized_screen = str(screen_type or "").strip().lower() or None
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}

        ui_recovery = self._get_stable_ui_recovery_decision(
            current_state,
            normalized_screen,
        )
        if ui_recovery:
            return self._decorate_api_fallback_decision(
                ui_recovery,
                "api_unavailable_ui_recovery",
            )

        battle_decision = self._get_safe_battle_progress_decision(
            current_state,
            normalized_screen,
        )
        if battle_decision:
            return self._decorate_api_fallback_decision(
                battle_decision,
                "api_unavailable_battle_fallback",
            )

        field_like_screen = normalized_screen in {"overworld", "indoor", "memory_only", "unknown", None}
        if (
            int(getattr(self, "_dialogue_exit_grace", 0) or 0) > 0
            and field_like_screen
            and not ui_state.get("text_box_active")
            and not ui_state.get("menu_active")
        ):
            replacement = self._get_local_safe_exploration_decision(
                current_state,
                normalized_screen,
            )
            if not replacement:
                replacement = {
                    "action": self._choose_recovery_move(current_state),
                    "reasoning": "Leave the just-closed dialogue tile before probing anything else",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
            return self._decorate_api_fallback_decision(
                replacement,
                "api_unavailable_dialogue_exit_recovery",
            )

        if normalized_screen == "dialogue":
            return self._decorate_api_fallback_decision(
                {
                    "action": "a",
                    "reasoning": "Continue the visible dialogue safely until control returns",
                    "goal_update": None,
                },
                "api_unavailable_dialogue_fallback",
            )

        if normalized_screen in {"menu", "pokemon_menu", "item_menu", "save_menu", "options_menu"}:
            return self._decorate_api_fallback_decision(
                {
                    "action": "b",
                    "reasoning": f"Close the {normalized_screen} UI and return to the field",
                    "goal_update": None,
                },
                "api_unavailable_menu_fallback",
            )

        if normalized_screen == "text_entry":
            return self._decorate_api_fallback_decision(
                {
                    "action": "b",
                    "reasoning": "Back out of text entry while the model is unavailable",
                    "goal_update": None,
                },
                "api_unavailable_text_entry_fallback",
            )

        if self._llm_primary_mode_enabled():
            recovery_decision = self._get_temporarily_avoided_field_recovery_decision(
                current_state,
                screen_type,
            )
            if recovery_decision:
                return self._decorate_api_fallback_decision(
                    recovery_decision,
                    "api_unavailable_field_recovery",
                )
            blocked_interaction = self._get_blocked_field_interaction_decision(
                current_state,
                screen_type,
            )
            if blocked_interaction:
                return self._decorate_api_fallback_decision(
                    blocked_interaction,
                    "api_unavailable_field_interaction",
                )
            return None

        navigation_decision = self._get_navigation_plan_decision(
            current_state,
            screen_type,
            force=True,
        )
        if navigation_decision:
            return self._decorate_api_fallback_decision(
                navigation_decision,
                "api_unavailable_navigation_fallback",
            )

        recovery_decision = self._get_pre_starter_recovery_move_decision(
            current_state,
            screen_type,
        )
        if recovery_decision:
            return self._decorate_api_fallback_decision(
                recovery_decision,
                "api_unavailable_pre_starter_fallback",
            )

        local_decision = self._get_local_safe_exploration_decision(
            current_state,
            screen_type,
        )
        if local_decision:
            return self._decorate_api_fallback_decision(
                local_decision,
                "api_unavailable_local_exploration",
            )

        recovery_decision = self._get_temporarily_avoided_field_recovery_decision(
            current_state,
            screen_type,
        )
        if recovery_decision:
            return self._decorate_api_fallback_decision(
                recovery_decision,
                "api_unavailable_field_recovery",
            )

        blocked_interaction = self._get_blocked_field_interaction_decision(
            current_state,
            screen_type,
        )
        if blocked_interaction:
            return self._decorate_api_fallback_decision(
                blocked_interaction,
                "api_unavailable_field_interaction",
            )

        return None

    def _apply_ai_unavailable_fallback(
        self,
        decision: dict,
        current_state: dict,
        screen_type: Optional[str],
    ) -> dict:
        """Replace ai_error/ai_cooldown waits with deterministic field-safe actions."""
        if self._pure_llm_mode_enabled():
            return decision

        source = str(decision.get("decision_source") or "").strip().lower()
        if source not in {"ai_error", "ai_cooldown"}:
            return decision

        fallback = self._get_ai_unavailable_fallback_decision(
            current_state,
            screen_type,
        )
        return fallback or decision

    def _should_preserve_ai_wait_in_full_control_mode(
        self,
        *,
        source: str,
        current_state: dict,
        normalized_screen: Optional[str],
    ) -> bool:
        """Keep ordinary field WAITs owned by the main model in AI-full-control mode."""
        if not self._ai_full_control_mode_enabled():
            return False
        if source != "ai":
            return False
        if normalized_screen not in {"", "unknown", "overworld", "indoor", "memory_only"}:
            return False

        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        if memory.get("in_battle"):
            return False
        if ui_state.get("text_box_active") or ui_state.get("menu_active"):
            return False
        return True

    def _rewrite_wait_decision(
        self,
        decision: dict,
        current_state: dict,
        screen_type: Optional[str],
    ) -> dict:
        """Replace model-origin WAIT actions with progress-preserving behavior."""
        if not isinstance(decision, dict):
            return decision
        if decision.get("executor") == "async_background_wait":
            return decision
        if (
            decision.get("executor") == "bootstrap"
            and decision.get("bootstrap_kind") == "wait"
        ):
            return decision
        if decision.get("allow_wait"):
            return decision

        action = str(decision.get("action") or "").strip().lower()
        if action != "wait":
            return decision

        normalized_screen = str(
            decision.get("screen_type") or screen_type or ""
        ).strip().lower()
        ui_state = current_state.get("memory", {}).get("ui", {}) or {}
        source = str(decision.get("decision_source") or "decision").strip().lower() or "decision"
        field_like_screen = normalized_screen in {"", "unknown", "overworld", "indoor", "memory_only"}

        if self._should_preserve_ai_wait_in_full_control_mode(
            source=source,
            current_state=current_state,
            normalized_screen=normalized_screen,
        ):
            return decision

        replacement: Optional[dict] = None
        if normalized_screen == "title":
            replacement = {
                "action": "start",
                "reasoning": "Auto: replace WAIT with START to keep title flow moving",
                "goal_update": None,
                "recorded_in_context": False,
            }
        elif normalized_screen == "startup":
            replacement = self._build_passive_progress_decision(
                "Auto: advance the startup transition without exposing WAIT",
                source="startup_progress",
            )
        elif normalized_screen == "startup_menu":
            replacement = {
                "action": "a",
                "reasoning": "Auto: confirm the startup menu instead of idling on WAIT",
                "goal_update": None,
                "recorded_in_context": False,
            }
        elif normalized_screen == "options_menu":
            replacement = {
                "action": "b",
                "reasoning": "Auto: back out of the options menu instead of idling on WAIT",
                "goal_update": None,
                "recorded_in_context": False,
            }
        elif (
            normalized_screen == "battle"
            or current_state.get("memory", {}).get("in_battle")
            or str(
                (current_state.get("battle_summary", {}) or {}).get("phase") or ""
            ).strip().lower() in {
                "entered_battle",
                "battle_in_progress",
                "post_battle_dialogue",
                "battle_just_ended",
            }
        ):
            replacement = self._get_safe_battle_progress_decision(
                current_state,
                normalized_screen or screen_type,
            )
        elif field_like_screen and ui_state.get("text_box_active") and not ui_state.get("menu_active"):
            replacement = self._get_local_safe_exploration_decision(
                current_state,
                normalized_screen or screen_type,
            )
            if not replacement:
                replacement = self._get_temporarily_avoided_field_recovery_decision(
                    current_state,
                    normalized_screen or screen_type,
                )
            if not replacement:
                replacement = self._get_blocked_field_interaction_decision(
                    current_state,
                    normalized_screen or screen_type,
                )
            if not replacement:
                replacement = {
                    "action": "a",
                    "reasoning": "Auto: advance the likely lingering field script instead of idling on WAIT",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
        elif normalized_screen in {
            "dialogue",
            "cutscene",
            "text_entry",
        } or ui_state.get("text_box_active"):
            replacement = {
                "action": "a",
                "reasoning": "Auto: advance the active text/script instead of idling on WAIT",
                "goal_update": None,
                "recorded_in_context": False,
            }
        elif normalized_screen in {
            "menu",
            "pokemon_menu",
            "item_menu",
            "save_menu",
        } or ui_state.get("menu_active"):
            replacement = {
                "action": "b",
                "reasoning": "Auto: close the open menu instead of idling on WAIT",
                "goal_update": None,
                "recorded_in_context": False,
            }
        else:
            replacement = self._get_local_safe_exploration_decision(
                current_state,
                normalized_screen or screen_type,
            )
            if not replacement:
                replacement = self._get_temporarily_avoided_field_recovery_decision(
                    current_state,
                    normalized_screen or screen_type,
                )
            if not replacement:
                replacement = self._get_blocked_field_interaction_decision(
                    current_state,
                    normalized_screen or screen_type,
                )
            if not replacement and normalized_screen in {"", "unknown", "overworld", "indoor", "memory_only"}:
                replacement = {
                    "action": self._choose_recovery_move(current_state),
                    "reasoning": "Auto: replace WAIT with a recovery move to keep field exploration moving",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
            if not replacement:
                replacement = self._build_passive_progress_decision(
                    "Auto: keep the emulator advancing instead of emitting WAIT",
                    source="passive_progress",
                )

        rewritten = dict(replacement)
        rewritten.setdefault("goal_update", decision.get("goal_update"))
        rewritten.setdefault("screen_type", decision.get("screen_type") or normalized_screen or None)
        rewritten.setdefault("decision_path", "tool")
        rewritten.setdefault("decision_source", f"wait_rewrite_{source}")
        rewritten.setdefault("decision_trace", decision.get("decision_trace", []))

        prior_reasoning = " ".join(str(decision.get("reasoning") or "").split()).strip()
        new_reasoning = " ".join(str(rewritten.get("reasoning") or "").split()).strip()
        if prior_reasoning:
            rewritten["reasoning"] = f"{new_reasoning}. Original WAIT reasoning: {prior_reasoning}"
        else:
            rewritten["reasoning"] = new_reasoning

        if rewritten.get("executor") == "async_background_wait":
            rewritten["recorded_in_context"] = True

        return rewritten

    def _get_cached_ai_plan_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Consume the next queued AI movement step when the field state is still stable enough."""
        if not self._planned_actions:
            return None
        if not self._llm_primary_mode_enabled() or not self._llm_primary_action_plan_enabled():
            self._clear_planned_actions()
            return None
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            self._clear_planned_actions()
            return None
        if self._recent_result_invalidates_cached_plan():
            self._clear_planned_actions()
            return None

        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        if (
            current_state.get("pre_world")
            or current_state.get("pre_starter_script")
            or memory.get("in_battle")
            or ui_state.get("text_box_active")
            or ui_state.get("menu_active")
            or int(current_state.get("deltas", {}).get("movement_stall_turns", 0) or 0) >= 2
        ):
            self._clear_planned_actions()
            return None
        navigation = current_state.get("navigation", {}) or {}
        if int(navigation.get("current_visit_count", 0) or 0) >= 4:
            self._clear_planned_actions()
            return None

        action = self._planned_actions.pop(0)
        if not self._cached_plan_step_matches_live_state(action, current_state):
            self._clear_planned_actions()
            return None
        return {
            "action": action,
            "reasoning": self._planned_reasoning or "AI short plan: continue the current movement route",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _cache_ai_action_plan(
        self,
        decision: Optional[dict],
        current_state: dict,
        screen_type: Optional[str],
    ) -> None:
        """Cache a short AI-generated follow-up plan into the existing planner queue."""
        if self._pure_llm_mode_enabled():
            return
        if self._llm_primary_mode_enabled() and not self._llm_primary_action_plan_enabled():
            return
        if not bool(self.config.get("ai.action_plan_enabled", True)):
            return
        if not isinstance(decision, dict):
            return
        if decision.get("decision_source") != "ai":
            return
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            return
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        if memory.get("in_battle"):
            return
        if ui_state.get("text_box_active") or ui_state.get("menu_active"):
            return
        if self._llm_primary_mode_enabled() and (
            current_state.get("pre_world")
            or current_state.get("pre_starter_script")
            or int(current_state.get("deltas", {}).get("movement_stall_turns", 0) or 0) >= 2
        ):
            return
        navigation = current_state.get("navigation", {}) or {}
        if int(navigation.get("current_visit_count", 0) or 0) >= 4:
            return
        movement_pattern = current_state.get("movement_pattern", {}) or {}
        if bool(movement_pattern.get("micro_loop_warning")):
            return

        action = str(decision.get("action") or "").strip().lower()
        if self._llm_primary_mode_enabled():
            allowed_actions = {"up", "down", "left", "right"}
        else:
            allowed_actions = {"up", "down", "left", "right", "a", "b", "start", "select"}
        if action not in allowed_actions:
            return

        plan = [
            step
            for step in (decision.get("action_plan") or [])
            if step in allowed_actions
        ]
        if not plan:
            return

        if plan[0] != action:
            plan.insert(0, action)

        max_actions = max(1, int(self.config.get("ai.action_plan_max_actions", 5) or 5))
        plan = plan[:max_actions]
        if len(plan) <= 1:
            return

        self._planned_actions = list(plan[1:])
        self._planned_target = None

        reasoning = " ".join(str(decision.get("reasoning") or "").split()).strip()
        preview = ", ".join(plan)
        if reasoning:
            self._planned_reasoning = f"AI plan: {reasoning} | follow {preview}"
        else:
            self._planned_reasoning = f"AI plan: follow {preview}"
        self.logger.debug(f"Cached AI action plan: {self._planned_actions}")

    def _cached_plan_step_matches_live_state(
        self,
        action: str,
        current_state: dict,
    ) -> bool:
        """Only reuse a cached step when live navigation still supports it."""
        normalized = str(action or "").strip().lower()
        if normalized not in {"up", "down", "left", "right"}:
            return True

        navigation = current_state.get("navigation", {}) or {}
        hints = (current_state.get("visual", {}) or {}).get("navigation_hints", {}) or {}
        if not navigation and not hints:
            return True

        position = (current_state.get("memory", {}) or {}).get("position", {}) or {}
        start_key = (
            int(position.get("map_id", 0) or 0),
            int(position.get("x", 0) or 0),
            int(position.get("y", 0) or 0),
        )
        blocked = {
            str(direction or "").strip().lower()
            for direction in navigation.get("blocked_directions", []) or []
        }
        blocked.update(
            str(direction or "").strip().lower()
            for direction in hints.get("blocked_directions", []) or []
        )
        if self._is_temporarily_avoided_move(start_key, normalized):
            blocked.add(normalized)
        if normalized in blocked:
            return False

        def _frontier_matches(frontier: Optional[dict]) -> bool:
            if not isinstance(frontier, dict):
                return False
            target = tuple(frontier.get("target") or frontier.get("position") or ())
            if target == start_key[1:]:
                unknown = {
                    str(direction or "").strip().lower()
                    for direction in frontier.get("unknown_directions", []) or []
                }
                if unknown:
                    return normalized in unknown
            path = [
                str(step or "").strip().lower()
                for step in (frontier.get("path") or [])
                if str(step or "").strip()
            ]
            return bool(path and path[0] == normalized)

        if _frontier_matches(navigation.get("nearest_frontier")):
            return True
        for frontier in navigation.get("frontier_candidates", []) or []:
            if _frontier_matches(frontier):
                return True
        walkable = {
            str(direction or "").strip().lower()
            for direction in hints.get("walkable_directions", []) or []
        }
        if walkable:
            return normalized in walkable
        return False

    def _recent_result_invalidates_cached_plan(self) -> bool:
        """Stop reusing a short AI plan after a scene transition or a failed cached step."""
        main_agent = getattr(self, "main_agent", None)
        recent_turns = getattr(getattr(main_agent, "context", None), "recent_turns", None) or []
        if not recent_turns:
            return False

        last_turn = recent_turns[-1]
        last_result = " ".join(str(last_turn.result or "").split()).strip().lower()
        if not last_result:
            return False

        if (
            str(last_turn.decision_source or "").strip().lower() == "cached_ai_plan"
            and any(token in last_result for token in ("position did not change", "no visible state change"))
        ):
            return True

        transition_tokens = (
            "warped from",
            "entered battle",
            "battle ended",
            "text box opened",
            "text box closed",
            "menu opened",
            "menu closed",
            "screen changed",
        )
        return any(token in last_result for token in transition_tokens)

    def run(self) -> None:
        """运行AI智能体。"""
        self.running = True
        self._last_fatal_error = None
        self._broadcast_control_state()
        self.logger.milestone("开始游戏")

        try:
            while self.running and self.emulator.is_running():
                if self.max_turns > 0 and self.turn_count >= self.max_turns:
                    self.logger.info(f"Reached testing.max_turns={self.max_turns}; stopping run loop")
                    self.running = False
                    break
                if self._process_control_cycle():
                    continue
                self._game_loop_iteration()

        except KeyboardInterrupt:
            self.logger.info("被用户中断")
        except Exception as e:
            self._last_fatal_error = str(e)
            self.logger.error(f"致命错误: {e}", exc_info=True)
        finally:
            self._finalize_pending_action_outcome()
            self._shutdown()

    def _extract_map_id_from_runtime_state(self, state: Optional[dict]) -> Optional[int]:
        """Read a map id from a stored runtime-state snapshot."""
        if not isinstance(state, dict):
            return None

        position = state.get("memory", {}).get("position", {}) or {}
        map_id = position.get("map_id")
        if map_id is None:
            return None
        try:
            return int(map_id)
        except (TypeError, ValueError):
            return None

    def _extract_position_from_runtime_state(
        self,
        state: Optional[dict],
    ) -> Optional[tuple[int, int, int]]:
        """Read map/x/y from a stored runtime-state snapshot."""
        if not isinstance(state, dict):
            return None

        position = state.get("memory", {}).get("position", {}) or {}
        map_id = position.get("map_id")
        x = position.get("x")
        y = position.get("y")
        if map_id is None or x is None or y is None:
            return None
        try:
            return int(map_id), int(x), int(y)
        except (TypeError, ValueError):
            return None

    def _get_known_warp_destination(
        self,
        source_position: tuple[int, int, int],
        destination_map_id: int,
    ) -> Optional[tuple[int, int, int]]:
        """Return a learned warp destination when map memory already knows it."""
        warp_points = getattr(getattr(self, "map_memory", None), "warp_points", {}) or {}
        warp = warp_points.get(source_position)
        if not isinstance(warp, dict):
            return None

        try:
            dest_map = int(warp.get("dest_map"))
            dest_x = int(warp.get("dest_x"))
            dest_y = int(warp.get("dest_y"))
        except (TypeError, ValueError):
            return None

        if dest_map != int(destination_map_id):
            return None
        return dest_map, dest_x, dest_y

    def _maybe_settle_after_map_transition(self) -> None:
        """Advance a few frames after a cross-map warp before capturing the next screenshot."""
        previous_position = self._extract_position_from_runtime_state(
            getattr(self, "_last_observed_state", None)
        )
        if previous_position is None or not hasattr(self, "memory_reader"):
            return

        try:
            memory_state = self.memory_reader.get_game_state_summary()
        except Exception:
            return

        current_position = self._extract_position_from_runtime_state({"memory": memory_state})
        if current_position is None or current_position[0] == previous_position[0]:
            return

        settle_frames = max(
            0,
            int(self.config.get("actions.map_transition_settle_frames", 16) or 16),
        )
        if settle_frames <= 0:
            return

        expected_destination = self._get_known_warp_destination(
            previous_position,
            current_position[0],
        )
        if expected_destination is None:
            self.emulator.tick(settle_frames)
            return

        step_frames = max(
            1,
            int(self.config.get("actions.map_transition_settle_step_frames", 4) or 4),
        )
        remaining = settle_frames
        while remaining > 0 and current_position != expected_destination:
            tick_frames = min(step_frames, remaining)
            self.emulator.tick(tick_frames)
            remaining -= tick_frames
            try:
                memory_state = self.memory_reader.get_game_state_summary()
            except Exception:
                break
            updated_position = self._extract_position_from_runtime_state({"memory": memory_state})
            if updated_position is None:
                break
            current_position = updated_position

    def _classify_runtime_observation(
        self,
        screen_image,
    ) -> tuple[dict, Optional[str], Optional[str], Optional[str]]:
        """Normalize one captured frame into current_state plus screen classifications."""
        screen_hash = self._compute_exact_screen_hash(screen_image)
        current_state = self.game_state.update(screen_image=screen_image)

        if self._pure_llm_mode_enabled():
            if isinstance(current_state.get("visual"), dict) and screen_hash:
                current_state["visual"]["screen_hash"] = screen_hash
            return current_state, screen_hash, None, None

        screen_type = self._apply_screen_type_hint(current_state, screen_image)
        if isinstance(current_state.get("visual"), dict) and screen_hash:
            current_state["visual"]["screen_hash"] = screen_hash
        control_screen_type = self._get_control_screen_type(current_state, screen_type)
        if isinstance(current_state.get("visual"), dict) and control_screen_type:
            visual_state = current_state["visual"]
            observed = visual_state.get("screen_type")
            if observed and observed != control_screen_type:
                visual_state["observed_screen_type"] = observed
            visual_state["screen_type"] = control_screen_type
        self._normalize_ui_flags_for_control(current_state, control_screen_type)
        return current_state, screen_hash, screen_type, control_screen_type

    def _maybe_resettle_visual_after_map_transition(
        self,
        screen_image,
        current_state: dict,
        screen_hash: Optional[str],
        screen_type: Optional[str],
        control_screen_type: Optional[str],
    ):
        """After a cross-map warp, keep sampling until the control screen type leaves the old scene."""
        previous_state = getattr(self, "_last_observed_state", None)
        previous_position = self._extract_position_from_runtime_state(previous_state)
        current_position = self._extract_position_from_runtime_state(current_state)
        if previous_position is None or current_position is None:
            return screen_image, current_state, screen_hash, screen_type, control_screen_type
        if previous_position[0] == current_position[0]:
            return screen_image, current_state, screen_hash, screen_type, control_screen_type

        previous_visual = (previous_state or {}).get("visual", {}) or {}
        previous_control_screen_type = str(
            previous_visual.get("screen_type") or ""
        ).strip().lower()
        current_control = str(control_screen_type or "").strip().lower()
        if not previous_control_screen_type:
            return screen_image, current_state, screen_hash, screen_type, control_screen_type
        if current_control and current_control not in {"unknown", previous_control_screen_type}:
            return screen_image, current_state, screen_hash, screen_type, control_screen_type

        settle_frames = max(
            0,
            int(self.config.get("actions.post_transition_visual_settle_frames", 8) or 8),
        )
        if settle_frames <= 0:
            return screen_image, current_state, screen_hash, screen_type, control_screen_type

        step_frames = max(
            1,
            int(self.config.get("actions.post_transition_visual_settle_step_frames", 4) or 4),
        )
        latest = (screen_image, current_state, screen_hash, screen_type, control_screen_type)
        remaining = settle_frames
        while remaining > 0:
            tick_frames = min(step_frames, remaining)
            self.emulator.tick(tick_frames)
            remaining -= tick_frames
            latest_image = self._capture_observation_frame()
            (
                latest_state,
                latest_hash,
                latest_screen_type,
                latest_control_screen_type,
            ) = self._classify_runtime_observation(latest_image)
            latest = (
                latest_image,
                latest_state,
                latest_hash,
                latest_screen_type,
                latest_control_screen_type,
            )
            latest_control = str(latest_control_screen_type or "").strip().lower()
            if latest_control and latest_control not in {"unknown", previous_control_screen_type}:
                break

        return latest

    def _observe_runtime_state(self):
        """Capture one normalized runtime observation without consuming another turn."""
        self._prepare_phase_hint_for_update()
        self._maybe_settle_after_map_transition()
        screen_image = self._capture_observation_frame()
        current_state, screen_hash, screen_type, control_screen_type = (
            self._classify_runtime_observation(screen_image)
        )
        self._consume_phase_hint_after_update()
        screen_image, current_state, screen_hash, screen_type, control_screen_type = (
            self._maybe_resettle_visual_after_map_transition(
                screen_image,
                current_state,
                screen_hash,
                screen_type,
                control_screen_type,
            )
        )

        return screen_image, current_state, screen_hash, screen_type, control_screen_type

    def _synchronize_runtime_turn_state(self, current_state: Optional[dict]) -> dict:
        """Force runtime snapshots to use the agent's real gameplay turn counter."""
        normalized = current_state or {}
        turn_value = int(getattr(self, "turn_count", 0) or 0)
        normalized["turn"] = turn_value
        if hasattr(self, "game_state") and hasattr(self.game_state, "turn_count"):
            self.game_state.turn_count = turn_value
        return normalized

    def _finalize_pending_action_outcome(self) -> None:
        """Refresh the final post-action state so shutdown/reporting is not one step stale."""
        if not getattr(self, "_last_observed_state", None) or not getattr(self, "_last_action", None):
            return
        if not all(hasattr(self, attr) for attr in ("game_state", "progress_tracker", "config")):
            return

        try:
            screen_image, current_state, _screen_hash, _screen_type, control_screen_type = self._observe_runtime_state()
        except Exception as exc:
            self.logger.warning(f"Failed to finalize pending action outcome: {exc}")
            return

        current_state = self._synchronize_runtime_turn_state(current_state)
        self._record_last_action_outcome(current_state, control_screen_type)
        self._last_observed_state = current_state
        self.progress_tracker.update(self.turn_count, current_state)
        if self.config.get("visualization.enabled", True):
            self._publish_visualizer_state(current_state, screen_image)
        self._last_action = None
        self._last_action_reasoning = ""
        self._last_action_source = None
        self._last_action_source = None

    def _game_loop_iteration(self) -> None:
        """Run a single gameplay loop iteration."""
        self.turn_count += 1

        screen_image, current_state, screen_hash, screen_type, control_screen_type = self._observe_runtime_state()
        current_state = self._synchronize_runtime_turn_state(current_state)
        self._record_last_action_outcome(current_state, control_screen_type)
        self._update_screen_stability(current_state, screen_image, control_screen_type)

        if control_screen_type != "text_entry":
            self._text_entry_step = 0

        if self._pure_llm_mode_enabled():
            self._prev_screen_type = None
            self._screen_type_streak = 0
            self._dialogue_exit_grace = 0
        else:
            previous_screen_type = self._prev_screen_type
            self._prev_screen_type = control_screen_type
            if control_screen_type and control_screen_type == previous_screen_type:
                self._screen_type_streak += 1
            else:
                self._screen_type_streak = 1 if control_screen_type else 0
            if previous_screen_type == "dialogue" and control_screen_type != "dialogue":
                self._dialogue_exit_grace = 2
            elif self._dialogue_exit_grace > 0:
                self._dialogue_exit_grace -= 1

        state_text = self.game_state.get_text_representation(current_state)
        screenshot_bytes = None
        if screen_image:
            scale = int(self.config.get("ai.screenshot_scale", 4) or 4)
            ai_image = screen_image
            if scale > 1:
                resample = (
                    Image.Resampling.NEAREST
                    if hasattr(Image, "Resampling")
                    else Image.NEAREST
                )
                ai_image = screen_image.resize(
                    (screen_image.width * scale, screen_image.height * scale),
                    resample=resample,
                )

            buffer = BytesIO()
            ai_image.save(buffer, format="PNG")
            screenshot_bytes = buffer.getvalue()

        self._publish_visualizer_state(current_state, screen_image)

        if self.turn_count % 10 == 0:
            self.logger.info(f"\n{state_text}")

        self.progress_tracker.update(self.turn_count, current_state)
        self._maybe_save_landmark_checkpoints(current_state)

        if self.config.get("logging.save_screenshots") and self.turn_count % 50 == 0:
            self._save_screenshot()

        ui_state = current_state.get("memory", {}).get("ui", {}) or {}
        if self._is_early_fixed_route_state(current_state):
            self.action_executor.reset_stuck_detection()
        elif self.action_executor.is_stuck(control_screen_type, ui_state):
            if control_screen_type in {"dialogue", "text_entry"}:
                self.action_executor.reset_stuck_detection()
            elif self._pure_llm_mode_enabled():
                self.logger.warning("Agent appears stuck in pure-LLM mode")
                self._clear_planned_actions()
                self.action_executor.reset_stuck_detection()
            elif self.config.get("testing.disable_stuck_critique", False):
                self.logger.warning("Agent appears stuck; skipping critique in testing mode")
                self._clear_planned_actions()
                self.action_executor.reset_stuck_detection()
            else:
                self.logger.warning("Agent appears stuck; requesting critique")
                if self.config.get("visualization.enabled", True):
                    self.visualizer.log_event("error", "智能体疑似卡住，正在请求纠偏")
                self._handle_stuck_state(current_state)
                self.action_executor.reset_stuck_detection()

        self._maybe_add_guidance_note(current_state, control_screen_type)

        decision_context = DecisionContext(
            current_state=current_state,
            state_text=state_text,
            screen_type=control_screen_type,
            screenshot_bytes=screenshot_bytes,
            screen_hash=screen_hash,
        )
        decision = self._decide_action_for_current_turn(decision_context)
        decision = self._apply_ai_unavailable_fallback(
            decision,
            current_state,
            control_screen_type,
        )
        decision = self._rewrite_wait_decision(
            decision,
            current_state,
            control_screen_type,
        )

        ui_state = current_state.get("memory", {}).get("ui", {}) or {}
        if (
            not self._llm_driven_mode_enabled()
            and decision.get("decision_source") == "ai"
            and self._dialogue_exit_grace > 0
            and decision.get("action") in {"a", "b", "start", "select"}
            and not ui_state.get("text_box_active")
            and (screen_type or "").strip().lower() != "dialogue"
            and (decision.get("screen_type") or "").strip().lower() != "dialogue"
        ):
            if (
                decision.get("recorded_in_context")
                and self.main_agent.context.recent_turns
                and self.main_agent.context.recent_turns[-1].turn_number == current_state["turn"]
            ):
                self.main_agent.context.recent_turns.pop()
            move = self._choose_recovery_move(current_state)
            decision = {
                "action": move,
                "reasoning": f"自动处理：对话结束后先离开当前位置（已压制 {decision.get('action')}）",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_path": "tool",
                "decision_source": "dialogue_exit_grace_recovery",
                "decision_trace": decision.get("decision_trace", []),
            }

        self._cache_ai_action_plan(decision, current_state, control_screen_type)

        if self._pure_llm_mode_enabled():
            self._set_transient_phase_hint(None, ttl_turns=0)
        else:
            self._set_phase_hint_from_decision(decision, screen_type)

        if self.config.get("visualization.enabled", True):
            action = decision.get("action", "wait")
            reasoning = decision.get("reasoning", "")
            self.visualizer.update_decision(
                action,
                reasoning,
                self.turn_count,
                screen_type=decision.get("screen_type") or control_screen_type or screen_type,
                source=decision.get("decision_source"),
                trace=decision.get("decision_trace"),
            )

        action = decision.get("action", "wait")
        reasoning = decision.get("reasoning", "")
        if not decision.get("recorded_in_context"):
            self.main_agent.record_external_decision(
                current_state,
                action=action,
                reasoning=reasoning,
                goal_update=decision.get("goal_update"),
                screen_type=decision.get("screen_type") or control_screen_type or screen_type,
                decision_source=decision.get("decision_source"),
                decision_path=decision.get("decision_path"),
            )
            decision["recorded_in_context"] = True

        self._last_observed_state = current_state
        self._last_action = action
        self._last_action_reasoning = reasoning
        self._last_action_source = decision.get("decision_source")

        if decision.get("executor") == "bootstrap":
            success = self._execute_bootstrap_action(decision)
        elif decision.get("executor") == "async_background_wait":
            success = self._execute_async_background_wait()
        else:
            success = self.action_executor.execute(
                action,
                precise=self._should_use_precise_direction_execution(decision, action),
                settle_frames_override=self._get_action_settle_override(
                    decision,
                    action,
                    current_state=current_state,
                ),
            )
        if not success:
            self.logger.warning(f"Action failed: {action}")
        else:
            self._publish_post_action_screenshot()

        checkpoint_interval = self.config.get("progress.checkpoint_interval", 100)
        if (
            self._checkpoint_writes_enabled()
            and self.turn_count - self.last_checkpoint_turn >= checkpoint_interval
        ):
            if self.config.get("visualization.enabled", True):
                self.visualizer.log_event("milestone", f"第 {self.turn_count} 回合已自动保存检查点")
            self._save_checkpoint()
            self.last_checkpoint_turn = self.turn_count

    def _record_last_action_outcome(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> None:
        """Record what the previous action actually caused."""
        if not self._last_observed_state or not self._last_action:
            return

        result = self._summarize_action_outcome(
            self._last_observed_state,
            current_state,
            self._last_action,
            screen_type,
        )
        if result:
            self.main_agent.record_action_outcome(result)

        self._update_trigger_tile_memory(
            self._last_observed_state,
            current_state,
            self._last_action,
        )
        self._update_recent_warp_exit_guard(
            self._last_observed_state,
            current_state,
            self._last_action,
        )

        if self._last_action in {"up", "down", "left", "right"}:
            prev_pos = self._last_observed_state.get("memory", {}).get("position", {})
            curr_pos = current_state.get("memory", {}).get("position", {})
            prev_direction = self._last_observed_state.get("memory", {}).get("direction")
            curr_direction = current_state.get("memory", {}).get("direction")
            same_tile = (
                prev_pos.get("map_id"),
                prev_pos.get("x"),
                prev_pos.get("y"),
            ) == (
                curr_pos.get("map_id"),
                curr_pos.get("x"),
                curr_pos.get("y"),
            )
            blocked_ui = {
                "dialogue",
                "text_entry",
                "startup",
                "title",
                "startup_menu",
                "options_menu",
                "naming_screen",
                "menu",
                "pokemon_menu",
                "item_menu",
                "save_menu",
            }
            turned_in_place = (
                prev_direction != self._last_action
                and curr_direction == self._last_action
            )
            deterministic_move_attempt = getattr(self, "_last_action_source", None) in {
                "cached_ai_plan",
                "navigation_plan",
                "guided_navigation_escape",
                "post_warp_reentry_guard",
                "recent_warp_buffer_guard",
            }
            if not deterministic_move_attempt:
                deterministic_move_attempt = str(
                    getattr(self, "_last_action_source", "") or ""
                ).startswith("wait_rewrite_")
            if (
                same_tile
                and (not turned_in_place or deterministic_move_attempt)
                and screen_type not in blocked_ui
                and not current_state.get("memory", {}).get("in_battle")
            ):
                self.map_memory.record_failed_move(
                    int(prev_pos.get("map_id", 0)),
                    int(prev_pos.get("x", 0)),
                    int(prev_pos.get("y", 0)),
                    self._last_action,
                )
                self._clear_planned_actions()

    def _update_recent_warp_exit_guard(
        self,
        previous_state: dict,
        current_state: dict,
        action: Optional[str],
    ) -> None:
        """Remember the reverse action that would likely step back through a just-used warp."""
        action = str(action or "").strip().lower()
        opposites = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }
        if action not in opposites:
            return

        previous_position = self._extract_position_from_runtime_state(previous_state)
        current_position = self._extract_position_from_runtime_state(current_state)
        if not previous_position or not current_position:
            return
        if previous_position[0] == current_position[0]:
            return

        warp_trigger_recorder = getattr(
            getattr(self, "map_memory", None),
            "record_warp_trigger_action",
            None,
        )
        if callable(warp_trigger_recorder):
            warp_trigger_recorder(
                int(previous_position[0]),
                int(previous_position[1]),
                int(previous_position[2]),
                action,
            )

        ttl = max(
            1,
            int(self.config.get("navigation.recent_warp_guard_turns", 4) or 4),
        )
        radius = max(
            0,
            int(self.config.get("navigation.recent_warp_guard_radius", 2) or 2),
        )
        self._recent_warp_exit = {
            "map_id": int(current_position[0]),
            "anchor": (int(current_position[1]), int(current_position[2])),
            "blocked_action": opposites[action],
            "source_map": int(previous_position[0]),
            "expires_turn": int(getattr(self, "turn_count", 0) or 0) + ttl,
            "radius": radius,
        }

    def _update_trigger_tile_memory(
        self,
        previous_state: dict,
        current_state: dict,
        action: Optional[str],
    ) -> None:
        """Remember immediate retreat loops and avoid re-targeting the same losing step."""
        directions = {"up", "down", "left", "right"}
        prev_memory = previous_state.get("memory", {}) or {}
        curr_memory = current_state.get("memory", {}) or {}
        prev_pos = prev_memory.get("position", {}) or {}
        curr_pos = curr_memory.get("position", {}) or {}
        prev_ui = prev_memory.get("ui", {}) or {}
        curr_ui = curr_memory.get("ui", {}) or {}
        prev_visual = previous_state.get("visual", {}) or {}
        curr_visual = current_state.get("visual", {}) or {}
        prev_screen = (
            prev_visual.get("screen_type")
            or prev_visual.get("ram_screen_type")
        )
        curr_screen = (
            curr_visual.get("screen_type")
            or curr_visual.get("ram_screen_type")
        )
        blocked_ui = {
            "dialogue",
            "text_entry",
            "startup",
            "title",
            "startup_menu",
            "options_menu",
            "naming_screen",
            "menu",
            "pokemon_menu",
            "item_menu",
            "save_menu",
        }
        prev_tuple = (
            int(prev_pos.get("map_id", 0) or 0),
            int(prev_pos.get("x", 0) or 0),
            int(prev_pos.get("y", 0) or 0),
        )
        curr_tuple = (
            int(curr_pos.get("map_id", 0) or 0),
            int(curr_pos.get("x", 0) or 0),
            int(curr_pos.get("y", 0) or 0),
        )
        moved = prev_tuple != curr_tuple
        pending = getattr(self, "_pending_trigger_tile", None)

        if pending:
            origin = pending.get("origin")
            trigger = pending.get("trigger")
            retreated_to_origin = prev_tuple == trigger and curr_tuple == origin
            if curr_memory.get("in_battle"):
                self._pending_trigger_tile = None
            elif retreated_to_origin:
                trigger_direction = self._direction_between_positions(origin, trigger)
                if trigger_direction:
                    self._mark_temporarily_avoided_move(origin, trigger_direction)
                    ui_driven_retreat = (
                        bool(prev_ui.get("text_box_active"))
                        or bool(curr_ui.get("text_box_active"))
                        or bool(prev_ui.get("menu_active"))
                        or bool(curr_ui.get("menu_active"))
                        or prev_screen in blocked_ui
                        or curr_screen in blocked_ui
                    )
                    if not ui_driven_retreat:
                        self._record_failed_move_evidence(origin, trigger_direction, attempts=2)
                self._mark_temporarily_avoided_frontier(origin)
                self._mark_temporarily_avoided_frontier(trigger)
                self._pending_trigger_tile = None
                return
            elif moved and curr_tuple != trigger:
                self._pending_trigger_tile = None

        if (
            action in directions
            and moved
            and not curr_memory.get("in_battle")
        ):
            self._pending_trigger_tile = {
                "origin": prev_tuple,
                "trigger": curr_tuple,
            }
        elif action in directions and moved:
            self._pending_trigger_tile = None

    def _direction_between_positions(
        self,
        origin: Optional[tuple],
        target: Optional[tuple],
    ) -> Optional[str]:
        """Return the cardinal step from origin to target when they are adjacent."""
        if not origin or not target or len(origin) != 3 or len(target) != 3:
            return None
        if int(origin[0]) != int(target[0]):
            return None

        dx = int(target[1]) - int(origin[1])
        dy = int(target[2]) - int(origin[2])
        mapping = {
            (0, -1): "up",
            (0, 1): "down",
            (-1, 0): "left",
            (1, 0): "right",
        }
        return mapping.get((dx, dy))

    def _record_failed_move_evidence(
        self,
        origin: Optional[tuple],
        direction: Optional[str],
        *,
        attempts: int = 1,
    ) -> None:
        """Promote repeated retreat loops into persistent blocked-move evidence."""
        recorder = getattr(getattr(self, "map_memory", None), "record_failed_move", None)
        if not callable(recorder):
            return
        if not origin or len(origin) != 3:
            return

        normalized = (direction or "").strip().lower()
        if normalized not in {"up", "down", "left", "right"}:
            return

        count = max(1, int(attempts or 1))
        for _ in range(count):
            recorder(
                int(origin[0]),
                int(origin[1]),
                int(origin[2]),
                normalized,
            )

    def _summarize_action_outcome(
        self,
        previous_state: dict,
        current_state: dict,
        action: str,
        current_screen_type: Optional[str],
    ) -> str:
        """Summarize the observable outcome of the previous action."""
        prev_memory = previous_state.get("memory", {})
        curr_memory = current_state.get("memory", {})
        prev_pos = prev_memory.get("position", {})
        curr_pos = curr_memory.get("position", {})
        prev_ui = prev_memory.get("ui", {}) or {}
        curr_ui = curr_memory.get("ui", {}) or {}
        prev_screen = previous_state.get("visual", {}).get("screen_type")
        curr_screen = current_screen_type or current_state.get("visual", {}).get("screen_type")

        parts: List[str] = [f"After {action}:"]

        prev_tuple = (prev_pos.get("map_id"), prev_pos.get("x"), prev_pos.get("y"))
        curr_tuple = (curr_pos.get("map_id"), curr_pos.get("x"), curr_pos.get("y"))
        if prev_tuple != curr_tuple:
            if prev_pos.get("map_id") != curr_pos.get("map_id"):
                parts.append(
                    f"warped from map {prev_pos.get('map_id')} ({prev_pos.get('x')},{prev_pos.get('y')}) "
                    f"to map {curr_pos.get('map_id')} ({curr_pos.get('x')},{curr_pos.get('y')})"
                )
            else:
                parts.append(
                    f"moved from ({prev_pos.get('x')},{prev_pos.get('y')}) "
                    f"to ({curr_pos.get('x')},{curr_pos.get('y')}) on map {curr_pos.get('map_id')}"
                )
        elif action in {"up", "down", "left", "right"}:
            parts.append("position did not change")

        if prev_memory.get("in_battle") != curr_memory.get("in_battle"):
            parts.append("entered battle" if curr_memory.get("in_battle") else "battle ended")

        if prev_screen != curr_screen and curr_screen:
            parts.append(f"screen changed from {prev_screen or 'unknown'} to {curr_screen}")

        if prev_ui.get("text_box_active") != curr_ui.get("text_box_active"):
            parts.append("text box opened" if curr_ui.get("text_box_active") else "text box closed")

        if prev_ui.get("menu_active") != curr_ui.get("menu_active"):
            parts.append("menu opened" if curr_ui.get("menu_active") else "menu closed")

        money_delta = int(curr_memory.get("money", 0)) - int(prev_memory.get("money", 0))
        if money_delta:
            parts.append(f"money delta {money_delta:+d}")

        badge_delta = int(curr_memory.get("badge_count", 0)) - int(prev_memory.get("badge_count", 0))
        if badge_delta > 0:
            parts.append(f"earned {badge_delta} new badge(s)")

        party_delta = len(curr_memory.get("party", [])) - len(prev_memory.get("party", []))
        if party_delta > 0:
            parts.append(f"party size increased by {party_delta}")
        elif party_delta < 0:
            parts.append(f"party size decreased by {abs(party_delta)}")

        if len(parts) == 1:
            if curr_ui.get("text_box_active"):
                parts.append("text box remains active")
            elif curr_ui.get("menu_active"):
                parts.append("menu remains active")
            else:
                parts.append("no visible state change")

        return "; ".join(parts)

    def _get_planned_or_ai_decision(
        self,
        current_state: dict,
        state_text: str,
        screenshot_bytes: Optional[bytes],
        screen_type: Optional[str],
    ) -> dict:
        """Use a navigation plan when reliable, otherwise ask the main agent."""
        planned = self._get_navigation_plan_decision(current_state, screen_type)
        if planned:
            return planned
        return self._get_ai_decision_responsive(current_state, state_text, screenshot_bytes)

    def _prune_temporarily_avoided_frontiers(self) -> None:
        """Drop expired temporary frontier blacklists."""
        avoided = getattr(self, "_temporarily_avoided_frontiers", None) or {}
        now = int(getattr(self, "turn_count", 0) or 0)
        self._temporarily_avoided_frontiers = {
            key: expiry
            for key, expiry in avoided.items()
            if int(expiry) > now
        }

    def _prune_temporarily_avoided_moves(self) -> None:
        """Drop expired temporary movement blacklists."""
        avoided = getattr(self, "_temporarily_avoided_moves", None) or {}
        now = int(getattr(self, "turn_count", 0) or 0)
        self._temporarily_avoided_moves = {
            key: expiry
            for key, expiry in avoided.items()
            if int(expiry) > now
        }

    def _mark_temporarily_avoided_frontier(self, target: tuple) -> None:
        """Temporarily stop the planner from re-targeting a looping trigger tile."""
        if not isinstance(target, tuple) or len(target) != 3:
            return

        self._prune_temporarily_avoided_frontiers()
        ttl = max(1, int(self.config.get("navigation.trigger_tile_avoid_turns", 120) or 120))
        self._temporarily_avoided_frontiers[target] = int(getattr(self, "turn_count", 0) or 0) + ttl
        self._clear_planned_actions()
        self.logger.info(
            "Temporarily avoiding frontier tile %s after an immediate trigger-tile retreat loop",
            target,
        )

    def _mark_temporarily_avoided_move(
        self,
        origin: tuple,
        direction: str,
    ) -> None:
        """Temporarily stop the planner from repeating a looping trigger step."""
        if not isinstance(origin, tuple) or len(origin) != 3:
            return
        normalized = (direction or "").strip().lower()
        if normalized not in {"up", "down", "left", "right"}:
            return

        self._prune_temporarily_avoided_moves()
        ttl = max(1, int(self.config.get("navigation.trigger_tile_avoid_turns", 120) or 120))
        key = (
            int(origin[0]),
            int(origin[1]),
            int(origin[2]),
            normalized,
        )
        self._temporarily_avoided_moves[key] = int(getattr(self, "turn_count", 0) or 0) + ttl
        self._clear_planned_actions()
        self.logger.info(
            "Temporarily avoiding move %s from %s after an immediate trigger-tile retreat loop",
            normalized,
            origin,
        )

    def _is_temporarily_avoided_frontier(
        self,
        map_id: int,
        target: Any,
    ) -> bool:
        """Return whether a frontier target is temporarily blacklisted."""
        self._prune_temporarily_avoided_frontiers()
        if not isinstance(target, (tuple, list)) or len(target) < 2:
            return False
        key = (
            int(map_id or 0),
            int(target[0] or 0),
            int(target[1] or 0),
        )
        return key in self._temporarily_avoided_frontiers

    def _is_temporarily_avoided_move(
        self,
        position: Any,
        direction: str,
    ) -> bool:
        """Return whether a local step is temporarily blacklisted."""
        self._prune_temporarily_avoided_moves()
        if not isinstance(position, tuple) or len(position) != 3:
            return False
        normalized = (direction or "").strip().lower()
        if normalized not in {"up", "down", "left", "right"}:
            return False
        key = (
            int(position[0]),
            int(position[1]),
            int(position[2]),
            normalized,
        )
        return key in self._temporarily_avoided_moves

    @staticmethod
    def _frontier_plan_priority_key(frontier: dict) -> tuple:
        """Return a stable frontier preference key where lower is better."""
        target = frontier.get("target") or frontier.get("position") or (999, 999)
        tx = int(target[0]) if isinstance(target, (tuple, list)) and len(target) >= 2 else 999
        ty = int(target[1]) if isinstance(target, (tuple, list)) and len(target) >= 2 else 999
        return (
            -float(frontier.get("priority_score", 0.0) or 0.0),
            len(frontier.get("path", []) or []),
            int(frontier.get("local_visit_pressure", 0) or 0),
            int(frontier.get("visit_count", 0) or 0),
            -int(frontier.get("global_novelty_distance", 0) or 0),
            int(frontier.get("distance", 999) or 999),
            ty,
            tx,
        )

    def _get_recent_map_transition(self, current_state: dict) -> Optional[dict]:
        """Return the most recent cross-map movement if the current turn just warped."""
        previous_position = self._extract_position_from_runtime_state(
            getattr(self, "_last_observed_state", None)
        )
        current_position = self._extract_position_from_runtime_state(current_state)
        if not previous_position or not current_position:
            return None
        if previous_position[0] == current_position[0]:
            return None

        return {
            "from_map": previous_position[0],
            "from_x": previous_position[1],
            "from_y": previous_position[2],
            "to_map": current_position[0],
            "to_x": current_position[1],
            "to_y": current_position[2],
        }

    def _get_active_recent_warp_exit(self, current_state: dict) -> Optional[dict]:
        """Return the short-lived reentry guard after a recent warp exit, clearing it when stale."""
        guard = getattr(self, "_recent_warp_exit", None)
        if not isinstance(guard, dict):
            return None

        current_position = self._extract_position_from_runtime_state(current_state)
        if not current_position:
            self._recent_warp_exit = None
            return None

        guard_map_id = guard.get("map_id")
        if guard_map_id is None or int(current_position[0]) != int(guard_map_id):
            self._recent_warp_exit = None
            return None

        expires_turn_raw = guard.get("expires_turn")
        expires_turn = -1 if expires_turn_raw is None else int(expires_turn_raw)
        if int(getattr(self, "turn_count", 0) or 0) > expires_turn:
            self._recent_warp_exit = None
            return None

        anchor = guard.get("anchor") or ()
        if not isinstance(anchor, (tuple, list)) or len(anchor) != 2:
            self._recent_warp_exit = None
            return None

        radius_raw = guard.get("radius")
        radius = 0 if radius_raw is None else int(radius_raw)
        distance = abs(int(current_position[1]) - int(anchor[0])) + abs(
            int(current_position[2]) - int(anchor[1])
        )
        if distance > radius:
            self._recent_warp_exit = None
            return None

        guard["distance"] = distance
        return guard

    def _choose_post_warp_escape_direction(
        self,
        current_state: dict,
        guarded_warp_directions: List[str],
        *,
        allow_frontier_steps: bool = True,
    ) -> Optional[str]:
        """Pick a non-warp step that immediately leaves a doorway/return-warp fringe."""
        navigation = current_state.get("navigation", {}) or {}
        adjacent_tiles = navigation.get("adjacent_tiles", {}) or {}
        vision = current_state.get("visual", {}).get("navigation_hints", {}) or {}
        memory_blocked = set(navigation.get("blocked_directions", []))
        vision_blocked = set(vision.get("blocked_directions", []))
        guarded = {
            str(direction or "").strip().lower()
            for direction in guarded_warp_directions
            if str(direction or "").strip().lower() in {"up", "down", "left", "right"}
        }
        current_tile_warp = navigation.get("current_tile_warp") or {}
        current_tile_trigger_action = str(
            current_tile_warp.get("trigger_action") or ""
        ).strip().lower()
        if current_tile_trigger_action in {"up", "down", "left", "right"}:
            guarded.add(current_tile_trigger_action)
        else:
            current_tile_trigger_action = ""
        protect_current_warp_tile = bool(current_tile_warp and current_tile_trigger_action)
        opposites = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }
        frontier_guidance = navigation.get("frontier_guidance", {}) or {}
        preferred_direction = str(
            frontier_guidance.get("escape_direction")
            or frontier_guidance.get("recommended_direction")
            or ""
        ).strip().lower() or None
        fallback_frontier_direction = str(
            frontier_guidance.get("recommended_direction") or ""
        ).strip().lower() or None

        ordered_candidates: List[str] = []

        def add(direction: Optional[str]) -> None:
            normalized = str(direction or "").strip().lower()
            if normalized and normalized not in ordered_candidates:
                ordered_candidates.append(normalized)

        if current_tile_warp:
            for allowed_status in ("known_exit", "adjacent_explored"):
                for direction in ("up", "left", "right", "down"):
                    info = adjacent_tiles.get(direction) or {}
                    status = str(info.get("status") or "").strip().lower()
                    if status != allowed_status:
                        continue
                    if info.get("target_is_warp") or info.get("step_triggers_warp"):
                        continue
                    add(direction)

        for direction in guarded:
            add(opposites.get(direction))
        add(preferred_direction)
        add(fallback_frontier_direction)
        for direction in vision.get("walkable_directions", []) or []:
            add(direction)
        for direction in ("up", "left", "right", "down"):
            info = adjacent_tiles.get(direction) or {}
            if info.get("status") in {"frontier", "known_exit", "adjacent_explored"}:
                add(direction)
        for direction in ("up", "down", "left", "right"):
            add(direction)

        position = current_state.get("memory", {}).get("position", {}) or {}
        start_key = (
            int(position.get("map_id", 0) or 0),
            int(position.get("x", 0) or 0),
            int(position.get("y", 0) or 0),
        )
        for direction in ordered_candidates:
            info = adjacent_tiles.get(direction) or {}
            status = str(info.get("status") or "").strip().lower()
            is_safe_step_off = (
                bool(current_tile_warp)
                and status in {"known_exit", "adjacent_explored"}
                and not info.get("target_is_warp")
                and not info.get("step_triggers_warp")
            )
            if direction in guarded:
                continue
            if not allow_frontier_steps and not is_safe_step_off:
                continue
            if direction in vision_blocked:
                continue
            if (
                direction in memory_blocked
                and not is_safe_step_off
                and not (protect_current_warp_tile and status == "blocked_once")
            ):
                continue
            if self._is_temporarily_avoided_move(start_key, direction):
                continue
            if info.get("step_triggers_warp"):
                continue
            if info.get("target_is_warp"):
                continue
            if status == "confirmed_blocked":
                continue
            if (
                status == "blocked_once"
                and not is_safe_step_off
                and not protect_current_warp_tile
            ):
                continue
            return direction

        return None

    def _get_post_warp_reentry_guard_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Immediately step away from a just-used return warp before ordinary planning resumes."""
        if screen_type not in {"overworld", "indoor", "unknown", None}:
            return None

        memory = current_state.get("memory", {}) or {}
        if memory.get("in_battle"):
            return None

        transition = self._get_recent_map_transition(current_state)
        if not transition:
            return None

        warp_cautions = current_state.get("navigation", {}).get("warp_cautions", []) or []
        guarded_warp_directions = []
        for caution in warp_cautions:
            destination = caution.get("destination") or {}
            try:
                destination_map_id = int(destination.get("map_id"))
            except (TypeError, ValueError):
                continue
            if destination_map_id != int(transition["from_map"]):
                continue
            guarded_warp_directions.append(str(caution.get("direction") or "").strip().lower())

        if not guarded_warp_directions:
            return None

        current_tile_warp = current_state.get("navigation", {}).get("current_tile_warp") or {}
        if not current_tile_warp:
            reasoning = (
                "Guard: just warped from map "
                f"{transition['from_map']} to map {transition['to_map']}; doorway exits can auto-step "
                "one tile after the map transition. Wait briefly so the exit settles before choosing a "
                "safe direction away from the return warp."
            )
            return {
                "action": "wait",
                "reasoning": reasoning,
                "goal_update": None,
                "recorded_in_context": False,
                "allow_wait": True,
                "decision_source": "post_warp_reentry_guard",
                "decision_path": "tool",
            }

        action = self._choose_post_warp_escape_direction(
            current_state,
            guarded_warp_directions,
        )
        if not action:
            return None

        warp_text = ", ".join(guarded_warp_directions)
        reasoning = (
            "Guard: just warped from map "
            f"{transition['from_map']} to map {transition['to_map']}; avoid stepping "
            f"{warp_text} onto the adjacent return warp. Move {action} first to leave the doorway "
            "before normal exploration resumes."
        )
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
            "decision_source": "post_warp_reentry_guard",
            "decision_path": "tool",
        }

    def _get_recent_warp_buffer_guard_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """For a few turns after a warp exit, keep blocking the reverse re-entry action."""
        if screen_type not in {"overworld", "indoor", "unknown", None}:
            return None
        if current_state.get("memory", {}).get("in_battle"):
            return None

        guard = self._get_active_recent_warp_exit(current_state)
        if not guard:
            return None

        blocked_action = str(guard.get("blocked_action") or "").strip().lower()
        if blocked_action not in {"up", "down", "left", "right"}:
            return None

        action = self._choose_post_warp_escape_direction(
            current_state,
            [blocked_action],
        )
        if not action:
            return None

        reasoning = (
            "Guard: recently warped into this map; avoid the reverse re-entry action "
            f"{blocked_action} until you move away from the doorway. Move {action} instead."
        )
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
            "decision_source": "recent_warp_buffer_guard",
            "decision_path": "tool",
        }

    def _get_guided_navigation_escape_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Use deterministic navigation only when live state says the current fringe is weak/stalled."""
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            return None
        if current_state.get("memory", {}).get("in_battle"):
            return None
        if current_state.get("pre_world") or current_state.get("pre_starter_script"):
            return None

        navigation = current_state.get("navigation", {}) or {}
        frontier_guidance = navigation.get("frontier_guidance", {}) or {}
        warp_cautions = navigation.get("warp_cautions", []) or []
        current_tile_warp = navigation.get("current_tile_warp") or {}
        movement_pattern = current_state.get("movement_pattern", {}) or {}
        deltas = current_state.get("deltas", {}) or {}
        current_visit_count = int(navigation.get("current_visit_count", 0) or 0)
        stall_turns = int(deltas.get("movement_stall_turns", 0) or 0)
        blocked_count = len(navigation.get("blocked_directions", []) or [])
        loop_warning = bool(movement_pattern.get("micro_loop_warning"))
        recent_warp_guard = self._get_active_recent_warp_exit(current_state)

        should_intervene = False
        if current_tile_warp and (
            recent_warp_guard
            or loop_warning
            or stall_turns >= 1
            or current_visit_count >= 2
        ):
            should_intervene = True
        elif frontier_guidance.get("prefer_leave_current_frontier") and (
            loop_warning
            or stall_turns >= 2
            or (blocked_count >= 2 and current_visit_count >= 4)
        ):
            should_intervene = True
        elif warp_cautions and (
            loop_warning
            or stall_turns >= 2
            or (blocked_count >= 1 and current_visit_count >= 3)
        ):
            should_intervene = True

        if not should_intervene:
            return None

        decision = self._get_navigation_plan_decision(
            current_state,
            screen_type,
            force=True,
        )
        if not decision:
            return None

        base_reasoning = str(decision.get("reasoning") or "").strip()
        prefix = "Planner guard: current local navigation is stalled, looping, or sitting on a risky warp fringe."
        decision["reasoning"] = f"{prefix} {base_reasoning}".strip()
        decision["decision_source"] = "guided_navigation_escape"
        decision["decision_path"] = "tool"
        return decision

    def _get_navigation_frontier_plan(self, current_state: dict) -> Optional[dict]:
        """Return the best reachable frontier plan after temporary trigger-tile filtering."""
        navigation = current_state.get("navigation", {}) or {}
        vision_hints = current_state.get("visual", {}).get("navigation_hints", {}) or {}
        position = current_state.get("memory", {}).get("position", {}) or {}
        map_id = int(position.get("map_id", 0) or 0)
        x = int(position.get("x", 0) or 0)
        y = int(position.get("y", 0) or 0)
        start = (x, y)
        start_key = (map_id, x, y)
        max_depth = int(self.config.get("navigation.max_plan_path_length", 24) or 24)
        blocked_first_steps = set(navigation.get("blocked_directions", []))
        blocked_first_steps.update(vision_hints.get("blocked_directions", []))

        preferred = navigation.get("nearest_frontier")
        preferred_path = list((preferred or {}).get("path", []) or [])
        preferred_first_step = preferred_path[0] if preferred_path else None
        if (
            preferred
            and preferred_first_step not in blocked_first_steps
            and not self._is_temporarily_avoided_frontier(map_id, preferred.get("target"))
            and not self._is_temporarily_avoided_move(start_key, preferred_first_step or "")
        ):
            return preferred

        frontier_reader = getattr(self.map_memory, "get_frontier_tiles", None)
        pathfinder = getattr(self.map_memory, "find_shortest_path", None)
        if not frontier_reader or not pathfinder:
            return None

        best: Optional[dict] = None
        for frontier in frontier_reader(map_id, current_position=start):
            target = frontier.get("position")
            if self._is_temporarily_avoided_frontier(map_id, target):
                continue

            path = pathfinder(map_id, start, target, max_depth=max_depth)
            if path is None and tuple(target or ()) != start:
                continue
            if path and path[0] in blocked_first_steps:
                continue
            if path and self._is_temporarily_avoided_move(start_key, path[0]):
                continue

            candidate = {
                "target": target,
                "path": path or [],
                "unknown_directions": frontier.get("unknown_directions", []),
                "visit_count": frontier.get("visit_count", 0),
                "distance": frontier.get("distance", 999),
                "local_visit_pressure": frontier.get("local_visit_pressure", 0),
                "global_novelty_distance": frontier.get("global_novelty_distance", 0),
                "priority_score": frontier.get("priority_score", 0.0),
                "novelty_label": frontier.get("novelty_label", "unknown"),
            }

            if best is None:
                best = candidate
                continue

            candidate_key = self._frontier_plan_priority_key(candidate)
            best_key = self._frontier_plan_priority_key(best)
            if candidate_key < best_key:
                best = candidate

        return best

    def _get_navigation_plan_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
        force: bool = False,
    ) -> Optional[dict]:
        """Return a deterministic frontier-following step when the route is obvious."""
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            self._clear_planned_actions()
            return None

        if current_state.get("memory", {}).get("in_battle"):
            self._clear_planned_actions()
            return None

        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", 0) or 0)
        if map_id == 40 and not (memory.get("party") or memory.get("in_battle")):
            self._clear_planned_actions()
            return None

        stall_turns = int(current_state.get("deltas", {}).get("movement_stall_turns", 0) or 0)
        threshold = int(self.config.get("navigation.auto_plan_stall_turns", 3) or 3)

        if self._planned_actions:
            action = self._planned_actions.pop(0)
            return {
                "action": action,
                "reasoning": self._planned_reasoning or "Planner: continue current route",
                "goal_update": None,
                "recorded_in_context": False,
            }

        navigation = current_state.get("navigation", {})
        badge_count = int(current_state.get("memory", {}).get("badge_count", 0) or 0)
        current_visit_count = int(navigation.get("current_visit_count", 0) or 0)
        proactive_before_first_badge = bool(
            self.config.get("navigation.proactive_frontier_before_first_badge", True)
        )
        proactive_visit_threshold = max(
            1,
            int(self.config.get("navigation.proactive_frontier_visit_threshold", 4) or 4),
        )
        proactive_plan = (
            not current_state.get("pre_world")
            and not current_state.get("pre_starter_script")
            and (
                (
                    proactive_before_first_badge
                    and badge_count == 0
                )
                or
                    current_visit_count >= proactive_visit_threshold
            )
        )
        if not force and not proactive_plan and stall_turns < threshold:
            return None

        position = current_state.get("memory", {}).get("position", {}) or {}
        x = int(position.get("x", 0) or 0)
        y = int(position.get("y", 0) or 0)
        current_tile = (x, y)
        current_tile_warp = navigation.get("current_tile_warp") or {}

        for _ in range(2):
            frontier_plan = self._get_navigation_frontier_plan(current_state)
            if not frontier_plan:
                return None

            path = list(frontier_plan.get("path", []))
            target = frontier_plan.get("target")
            self._planned_target = tuple(target) if isinstance(target, (list, tuple)) else target
            movement_pattern = current_state.get("movement_pattern", {}) or {}
            loop_warning = bool(movement_pattern.get("micro_loop_warning"))
            loop_visit_threshold = max(
                1,
                int(self.config.get("navigation.loop_warning_visit_threshold", 12) or 12),
            )
            frontier_guidance = current_state.get("navigation", {}).get("frontier_guidance", {}) or {}
            guided_escape_direction = None
            if frontier_guidance.get("prefer_leave_current_frontier"):
                guided_escape_direction = self._choose_post_warp_escape_direction(
                    current_state,
                    [],
                )
            current_tile_trigger_action = str(
                current_tile_warp.get("trigger_action") or ""
            ).strip().lower()
            if current_tile_trigger_action not in {"up", "down", "left", "right"}:
                current_tile_trigger_action = ""
            if not path and tuple(target or ()) == current_tile and current_tile_warp:
                guarded_actions = [current_tile_trigger_action] if current_tile_trigger_action else []
                warp_escape_direction = self._choose_post_warp_escape_direction(
                    current_state,
                    guarded_actions,
                    allow_frontier_steps=bool(current_tile_trigger_action),
                )
                if warp_escape_direction:
                    destination = current_tile_warp.get("destination") or {}
                    destination_text = ""
                    if destination:
                        destination_text = (
                            f" to map {destination.get('map_id', '?')} "
                            f"({destination.get('x', '?')}, {destination.get('y', '?')})"
                        )
                    return {
                        "action": warp_escape_direction,
                        "reasoning": (
                            "Planner: current tile is a known warp source"
                            f"{destination_text}; step off it via {warp_escape_direction} "
                            "before probing local frontier directions."
                        ),
                        "goal_update": None,
                        "recorded_in_context": False,
                    }
                self._clear_planned_actions()
                return None
            if (
                bool(self.config.get("navigation.defer_to_ai_on_loop_warning", True))
                and loop_warning
                and current_visit_count >= loop_visit_threshold
                and not path
                and tuple(target or ()) == current_tile
                and not guided_escape_direction
            ):
                self._clear_planned_actions()
                return None

            if path:
                self._planned_actions = path[1:]
                route_preview = ", ".join(path[:10])
                novelty = frontier_plan.get("novelty_label", "unknown")
                self._planned_reasoning = (
                    f"Planner: follow learned route toward frontier {self._planned_target} "
                    f"(novelty={novelty}, pressure={frontier_plan.get('local_visit_pressure', 0)}) "
                    f"via {route_preview}"
                )
                return {
                    "action": path[0],
                    "reasoning": self._planned_reasoning,
                    "goal_update": None,
                    "recorded_in_context": False,
                }

            if guided_escape_direction:
                reasoning = (
                    f"Planner: leave the weaker local frontier via {guided_escape_direction}. "
                    f"{frontier_guidance.get('summary') or 'A stronger frontier exists elsewhere on this map.'}"
                )
                return {
                    "action": guided_escape_direction,
                    "reasoning": reasoning,
                    "goal_update": None,
                    "recorded_in_context": False,
                }

            frontier_direction = self._choose_frontier_direction(
                current_state,
                frontier_plan.get("unknown_directions", []),
            )
            if frontier_direction:
                novelty = frontier_plan.get("novelty_label", "unknown")
                if (
                    frontier_guidance.get("prefer_leave_current_frontier")
                    and str(frontier_guidance.get("recommended_direction") or "").strip().lower()
                    == frontier_direction
                ):
                    guidance_summary = frontier_guidance.get("summary") or "leave the weaker local frontier"
                    reasoning = (
                        f"Planner: leave the weaker local frontier via {frontier_direction}. "
                        f"{guidance_summary}"
                    )
                else:
                    reasoning = (
                        f"Planner: current tile is already a frontier; test unexplored direction "
                        f"{frontier_direction} from {self._planned_target} "
                        f"(novelty={novelty}, pressure={frontier_plan.get('local_visit_pressure', 0)})"
                    )
                return {
                    "action": frontier_direction,
                    "reasoning": reasoning,
                    "goal_update": None,
                    "recorded_in_context": False,
                }

            if tuple(target or ()) == current_tile:
                self._mark_temporarily_avoided_frontier((map_id, x, y))
                continue

        return None

    def _choose_frontier_direction(
        self,
        current_state: dict,
        candidate_directions: List[str],
    ) -> Optional[str]:
        """Choose the safest frontier step using visual navigation hints."""
        if not candidate_directions:
            return None

        vision = current_state.get("visual", {}).get("navigation_hints", {})
        navigation = current_state.get("navigation", {}) or {}
        frontier_guidance = navigation.get("frontier_guidance", {}) or {}
        adjacent_tiles = navigation.get("adjacent_tiles", {}) or {}
        current_tile_warp = navigation.get("current_tile_warp") or {}
        memory_blocked = set(navigation.get("blocked_directions", []))
        position = current_state.get("memory", {}).get("position", {}) or {}
        start_key = (
            int(position.get("map_id", 0) or 0),
            int(position.get("x", 0) or 0),
            int(position.get("y", 0) or 0),
        )
        vision_blocked = set(vision.get("blocked_directions", []))
        current_tile_trigger_action = str(
            current_tile_warp.get("trigger_action") or ""
        ).strip().lower()
        if current_tile_trigger_action in {"up", "down", "left", "right"}:
            memory_blocked.add(current_tile_trigger_action)
        avoided = {
            direction
            for direction in candidate_directions
            if self._is_temporarily_avoided_move(start_key, direction)
        }
        blocked = memory_blocked | vision_blocked | avoided
        preferred_direction = None
        discouraged_directions: set[str] = set()
        if frontier_guidance.get("prefer_leave_current_frontier"):
            preferred_direction = str(
                frontier_guidance.get("recommended_direction") or ""
            ).strip().lower() or None
            discouraged_directions = {
                str(direction or "").strip().lower()
                for direction in frontier_guidance.get("discouraged_directions", []) or []
            }
        safe_candidates = [
            direction
            for direction in candidate_directions
            if (
                direction not in blocked
                and direction not in discouraged_directions
                and not (adjacent_tiles.get(direction) or {}).get("target_is_warp")
                and not (adjacent_tiles.get(direction) or {}).get("step_triggers_warp")
            )
        ]

        if preferred_direction and preferred_direction in safe_candidates:
            return preferred_direction

        last_action = getattr(self, "_last_action", None)
        if (
            last_action in safe_candidates
            and current_state.get("deltas", {}).get("position_changed")
        ):
            return last_action

        for direction in vision.get("walkable_directions", []):
            if direction in safe_candidates:
                return direction

        for direction in safe_candidates:
            return direction

        if (
            preferred_direction
            and preferred_direction in candidate_directions
            and preferred_direction not in blocked
            and not (adjacent_tiles.get(preferred_direction) or {}).get("target_is_warp")
            and not (adjacent_tiles.get(preferred_direction) or {}).get("step_triggers_warp")
        ):
            return preferred_direction

        for direction in vision.get("walkable_directions", []):
            if (
                direction in candidate_directions
                and direction not in blocked
                and not (adjacent_tiles.get(direction) or {}).get("target_is_warp")
                and not (adjacent_tiles.get(direction) or {}).get("step_triggers_warp")
            ):
                return direction

        for direction in candidate_directions:
            if (
                direction not in blocked
                and not (adjacent_tiles.get(direction) or {}).get("target_is_warp")
                and not (adjacent_tiles.get(direction) or {}).get("step_triggers_warp")
            ):
                return direction

        return None

    def _clear_planned_actions(self) -> None:
        """Clear the current deterministic navigation plan."""
        self._planned_actions = []
        self._planned_target = None
        self._planned_reasoning = ""

    def _maybe_add_guidance_note(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> None:
        """Periodically ask the critic for a short correction note."""
        if self._pure_llm_mode_enabled():
            return
        if self.main_agent.is_in_api_cooldown():
            return
        raw_interval = self.config.get("ai.guidance_interval_turns", 25)
        interval = 25 if raw_interval is None else int(raw_interval)
        if interval <= 0:
            return
        if self.turn_count - self._last_guidance_turn < interval:
            return
        ui_state = current_state.get("memory", {}).get("ui", {}) or {}
        if ui_state.get("text_box_active") or ui_state.get("menu_active"):
            return
        if self._is_early_fixed_route_state(current_state):
            return
        if screen_type in {"dialogue", "text_entry", "startup", "title", "startup_menu", "options_menu", "naming_screen"}:
            return

        critique = self.critic.critique(self._build_critic_history_text(), current_state)
        note_parts = []
        if critique.get("issues"):
            note_parts.append(f"Issues: {critique['issues']}")
        if critique.get("suggestions"):
            note_parts.append(f"Suggestions: {critique['suggestions']}")
        if not note_parts and critique.get("assessment"):
            note_parts.append(critique["assessment"])

        note = " | ".join(" ".join(part.split()) for part in note_parts).strip()
        if not note:
            return

        self.main_agent.add_guidance_note(note[:600], source="critic")
        self._last_guidance_turn = self.turn_count

    def _is_early_fixed_route_state(self, current_state: dict) -> bool:
        """Return True when deterministic early-game routing should not trigger critique logic."""
        if (
            self._research_mode_enabled()
            or self._pure_llm_mode_enabled()
            or self._ai_full_control_mode_enabled()
        ):
            return False
        guided_controllers = (
            getattr(self, "post_battle_intro_route", None),
            getattr(self, "viridian_parcel_controller", None),
            getattr(self, "post_pokedex_departure_controller", None),
        )
        for route_controller in guided_controllers:
            if not route_controller or not hasattr(route_controller, "is_guided_state"):
                continue
            try:
                if route_controller.is_guided_state(current_state):
                    return True
            except Exception:
                pass
        memory = current_state.get("memory", {}) or {}
        if memory.get("in_battle"):
            return False
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False
        if int(memory.get("item_count", 0) or 0) != 0:
            return False
        events = memory.get("events", {}) or {}
        if any(
            bool(events.get(name))
            for name in ("got_oaks_parcel", "oak_got_parcel", "got_pokedex")
        ):
            return False

        position = memory.get("position", {}) or {}
        map_id_raw = position.get("map_id", -1)
        x_raw = position.get("x", -1)
        y_raw = position.get("y", -1)
        map_id = int(-1 if map_id_raw is None else map_id_raw)
        x = int(-1 if x_raw is None else x_raw)
        y = int(-1 if y_raw is None else y_raw)
        if map_id in {0, 12, 40}:
            return True
        if map_id == 1 and (
            (x == 21 and 30 <= y <= 35)
            or (x == 20 and 28 <= y <= 30)
            or (x == 19 and y == 28)
        ):
            return True
        return False

    def _should_use_precise_direction_execution(
        self,
        decision: dict,
        action: str,
    ) -> bool:
        """Let deterministic tool routing complete one real step in llm-primary mode."""
        normalized = str(action or "").strip().lower()
        if normalized not in {"up", "down", "left", "right"}:
            return False
        if self._pure_llm_mode_enabled():
            return False
        if not self._llm_primary_mode_enabled():
            return False

        source = str(decision.get("decision_source") or "").strip().lower()
        return source not in {"ai", "cached_ai_plan"}

    def _get_action_settle_override(
        self,
        decision: dict,
        action: str,
        current_state: Optional[dict] = None,
    ) -> Optional[int]:
        """Return an action-specific settle override for fragile scripted states."""
        normalized = str(action or "").strip().lower()
        if normalized not in {"a", "b"}:
            return None

        source = str(decision.get("decision_source") or "").strip().lower()
        if source != "early_battle":
            memory = (current_state or {}).get("memory", {}) or {}
            ui_state = memory.get("ui", {}) or {}
            battle_phase = str(
                ((current_state or {}).get("battle_summary", {}) or {}).get("phase") or ""
            ).strip().lower()
            battle_text_active = bool(ui_state.get("text_box_active")) and (
                bool(memory.get("in_battle"))
                or battle_phase in {
                    "entered_battle",
                    "battle_in_progress",
                    "post_battle_dialogue",
                    "battle_just_ended",
                }
            )
            if not battle_text_active:
                return None
            return max(
                0,
                int(
                    self.config.get("actions.ai_battle_text_button_settle_frames", 24) or 24
                ),
            )

        return max(
            0,
            int(self.config.get("actions.early_battle_button_settle_frames", 30) or 30),
        )

    def _build_critic_history_text(self, limit_chars: int = 8000) -> str:
        """Build a bounded history string for the critic."""
        history = self.main_agent.context.get_context_for_ai()
        if len(history) > limit_chars:
            return history[-limit_chars:]
        return history

    def _process_control_cycle(self) -> bool:
        """Process queued dashboard controls before the next AI turn."""
        if self._consume_checkpoint_request():
            self._save_checkpoint()
            return True

        manual_action = self._pop_manual_action()
        if manual_action:
            self._execute_manual_action(manual_action)
            return True

        if self._consume_step_request():
            self._game_loop_iteration()
            return True

        if self._is_paused():
            time.sleep(0.05)
            return True

        return False

    def _apply_screen_type_hint(self, current_state: dict, screen_image) -> Optional[str]:
        """Patch memory-only visual state with lightweight UI heuristics."""
        if self._pure_llm_mode_enabled():
            return None
        screen_type = self._detect_screen_type(screen_image)
        if isinstance(current_state.get("visual"), dict) and screen_type:
            current_state["visual"]["screen_type"] = screen_type
        return screen_type

    def _prepare_phase_hint_for_update(self) -> None:
        """Clear expired transient phase hints before the next state update."""
        if self._phase_hint_turns_remaining <= 0:
            self.game_state.set_phase_hint(None)

    def _consume_phase_hint_after_update(self) -> None:
        """Consume one use of the transient phase hint after a state update."""
        if self._phase_hint_turns_remaining <= 0:
            return
        self._phase_hint_turns_remaining -= 1
        if self._phase_hint_turns_remaining <= 0:
            self.game_state.set_phase_hint(None)

    def _set_transient_phase_hint(self, phase_hint: Optional[str], ttl_turns: int) -> None:
        """Store a short-lived UI hint for the next few update cycles."""
        normalized = (phase_hint or "").strip().lower()
        if not normalized or ttl_turns <= 0:
            self._phase_hint_turns_remaining = 0
            self.game_state.set_phase_hint(None)
            return
        self._phase_hint_turns_remaining = int(ttl_turns)
        self.game_state.set_phase_hint(normalized)

    def _set_phase_hint_from_decision(self, decision: dict, observed_screen_type: Optional[str]) -> None:
        """Refresh the next-turn UI hint only from strong sources."""
        explicit = (decision.get("screen_type") or "").strip().lower()
        if explicit:
            self._set_transient_phase_hint(explicit, ttl_turns=3)
            return

        observed = (observed_screen_type or "").strip().lower()
        if observed in {
            "startup",
            "dialogue",
            "text_entry",
            "naming_screen",
            "menu",
            "pokemon_menu",
            "item_menu",
            "save_menu",
            "options_menu",
            "startup_menu",
            "title",
            "battle",
        }:
            self._set_transient_phase_hint(observed, ttl_turns=2)
            return

        self._set_transient_phase_hint(None, ttl_turns=0)

    def _has_stale_battle_screen_flag(
        self,
        current_state: dict,
        observed_screen_type: Optional[str],
    ) -> bool:
        """Detect false battle classifications after control has clearly returned to the field."""
        screen_type = (observed_screen_type or "").strip().lower()
        if screen_type != "battle":
            return False

        memory = current_state.get("memory", {}) or {}
        if memory.get("in_battle"):
            return False

        remaining_grace = int(getattr(self, "_recent_battle_visual_grace_turns", 0) or 0)
        if remaining_grace > 0:
            self._recent_battle_visual_grace_turns = max(0, remaining_grace - 1)
            return False

        battle_summary = current_state.get("battle_summary", {}) or {}
        battle_phase = str(battle_summary.get("phase") or "").strip().lower()
        if battle_phase not in {"", "not_in_battle"}:
            return False

        if current_state.get("pre_world") or current_state.get("pre_starter_script"):
            return False

        ui_state = memory.get("ui", {}) or {}
        if ui_state.get("text_box_active"):
            return False

        position = memory.get("position", {}) or {}
        map_id = position.get("map_id")
        x = position.get("x")
        y = position.get("y")
        return map_id is not None and x is not None and y is not None

    def _infer_field_screen_type(
        self,
        phase_hint: Optional[str],
    ) -> str:
        """Pick a field-like control screen type after filtering a false UI classification."""
        previous = str(getattr(self, "_prev_screen_type", "") or "").strip().lower()
        if previous in {"overworld", "indoor", "memory_only"}:
            return previous

        hint = str(phase_hint or "").strip().lower()
        if hint in {"overworld", "indoor", "memory_only"}:
            return hint

        return "overworld"

    def _get_recent_battle_visual_grace_limit(self) -> int:
        """Return the short grace window that protects recent battle frames from false field overrides."""
        config = getattr(self, "config", None)
        if config is None or not hasattr(config, "get"):
            return 2
        return max(0, int(config.get("actions.recent_battle_visual_grace_turns", 2) or 2))

    def _get_control_screen_type(
        self,
        current_state: dict,
        observed_screen_type: Optional[str],
    ) -> Optional[str]:
        """Resolve the control-layer screen type used by safeguards and tool routing."""
        screen_type = (observed_screen_type or "").strip().lower() or None
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        phase_hint = str(current_state.get("phase_hint") or "").strip().lower() or None

        if memory.get("in_battle"):
            self._recent_battle_visual_grace_turns = self._get_recent_battle_visual_grace_limit()
            return "battle"
        if screen_type != "battle":
            self._recent_battle_visual_grace_turns = 0
        if (
            screen_type == "naming_screen"
            and self._should_override_false_naming_screen(current_state, phase_hint)
        ):
            if phase_hint in {"dialogue", "battle", "indoor"}:
                return phase_hint
            return "dialogue"
        if self._has_stale_battle_screen_flag(current_state, screen_type):
            return self._infer_field_screen_type(phase_hint)
        if screen_type in {
            "startup",
            "dialogue",
            "text_entry",
            "naming_screen",
            "menu",
            "pokemon_menu",
            "item_menu",
            "save_menu",
            "options_menu",
            "startup_menu",
            "title",
        }:
            return screen_type

        if ui_state.get("menu_active") and phase_hint in {
            "menu",
            "pokemon_menu",
            "item_menu",
            "save_menu",
            "options_menu",
            "startup_menu",
        }:
            return phase_hint

        if self._has_stale_text_box_flag(current_state, screen_type):
            return screen_type or None

        if ui_state.get("text_box_active") and phase_hint in {"dialogue", "text_entry"}:
            return phase_hint

        return screen_type or phase_hint

    def _should_override_false_naming_screen(
        self,
        current_state: dict,
        phase_hint: Optional[str],
    ) -> bool:
        """Ignore early Oak Lab naming-screen false positives when dialogue evidence is stronger."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", 0) or 0)
        badge_count = int(memory.get("badge_count", 0) or 0)
        party_size = len(memory.get("party", []) or [])
        ui_state = memory.get("ui", {}) or {}

        if map_id != 40 or badge_count != 0 or party_size != 0:
            return False

        return bool(ui_state.get("text_box_active") or phase_hint in {"dialogue", "battle", "indoor"})

    def _has_stale_text_box_flag(
        self,
        current_state: dict,
        observed_screen_type: Optional[str],
    ) -> bool:
        """Treat RAM text flags as stale once the Oak-lab handoff has proven movement."""
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        if not ui_state.get("text_box_active") or ui_state.get("menu_active"):
            return False

        screen_type = (observed_screen_type or "").strip().lower()
        if screen_type not in {"indoor", "overworld"}:
            return False

        deltas = current_state.get("deltas", {}) or {}
        if deltas.get("position_changed"):
            return True
        if memory.get("party") and not memory.get("in_battle"):
            return True

        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", 0) or 0)
        x = int(position.get("x", 0) or 0)
        y = int(position.get("y", 0) or 0)
        return map_id == 40 and not (memory.get("party") or memory.get("in_battle")) and (x, y) != (5, 3)

    def _has_stale_menu_flag(
        self,
        current_state: dict,
        observed_screen_type: Optional[str],
    ) -> bool:
        """Treat RAM menu flags as stale once the screenshot is clearly back on a field map."""
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        if not ui_state.get("menu_active") or ui_state.get("text_box_active"):
            return False
        if memory.get("in_battle"):
            return False

        screen_type = (observed_screen_type or "").strip().lower()
        if screen_type not in {"indoor", "overworld", "memory_only"}:
            return False

        if current_state.get("pre_world") or current_state.get("pre_starter_script"):
            return False

        position = memory.get("position", {}) or {}
        return (
            position.get("map_id") is not None
            and position.get("x") is not None
            and position.get("y") is not None
        )

    def _refresh_movement_deltas_after_ui_clear(self, current_state: dict) -> None:
        """Recompute stall hints after stale UI flags are stripped from a free-movement scene."""
        memory = current_state.get("memory", {}) or {}
        deltas = current_state.get("deltas", {}) or {}
        if memory.get("in_battle"):
            self.game_state._movement_stall_turns = 0
            deltas["movement_stall_turns"] = 0
            deltas["stuck_hint"] = "moving or in battle"
            return

        if deltas.get("position_changed"):
            self.game_state._movement_stall_turns = 0
            deltas["movement_stall_turns"] = 0
            deltas["stuck_hint"] = "moving or in battle"
            return

        self.game_state._movement_stall_turns += 1
        stall_turns = int(self.game_state._movement_stall_turns)
        deltas["movement_stall_turns"] = stall_turns
        deltas["stuck_hint"] = (
            "possibly stuck - explore a different direction or unseen tile"
            if stall_turns >= 2
            else "slight stall"
        )

    def _normalize_ui_flags_for_control(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> None:
        """Clear RAM UI flags once the current scene is clearly free movement."""
        memory = current_state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        if not isinstance(ui_state, dict):
            return

        visual_state = current_state.get("visual", {}) or {}
        observed_screen_type = (
            visual_state.get("observed_screen_type")
            or visual_state.get("screen_type")
            or screen_type
        )
        cleared_ui_flag = False
        if (
            self._has_stale_battle_screen_flag(current_state, observed_screen_type)
            and ui_state.get("menu_active")
            and not ui_state.get("text_box_active")
        ):
            ui_state["stale_menu_flag"] = True
            ui_state["menu_active"] = False
            visual_state["stale_battle_screen_flag"] = True
            cleared_ui_flag = True

        if self._has_stale_menu_flag(current_state, screen_type):
            ui_state["stale_menu_flag"] = True
            ui_state["menu_active"] = False
            cleared_ui_flag = True

        if self._has_stale_text_box_flag(current_state, screen_type):
            if ui_state.get("text_box_active"):
                ui_state["stale_text_box_flag"] = True
            ui_state["text_box_active"] = False
            cleared_ui_flag = True

        if not cleared_ui_flag:
            return

        self._refresh_movement_deltas_after_ui_clear(current_state)

    def _publish_visualizer_state(self, current_state: dict, screen_image) -> None:
        """Push state, screenshot, goals, and control status to the dashboard."""
        if not self.config.get('visualization.enabled', True):
            return

        if hasattr(self.main_agent, 'goals') and self.main_agent.goals:
            self.main_agent.goals.sync_with_game_state(current_state)

        self.visualizer.update_state(current_state)
        if screen_image:
            self.visualizer.update_screenshot(screen_image)
        if hasattr(self.main_agent, 'goals') and self.main_agent.goals:
            self.visualizer.update_goals(self.main_agent.goals.get_dashboard_items())
        self._broadcast_control_state()

    def _capture_startup_preview_frame(self, warmup_frames: int = 0):
        """Capture a startup preview frame before the main turn loop begins."""
        screen_image = self.emulator.get_screen_image()
        remaining = max(0, int(warmup_frames or 0))
        step = 12

        while remaining > 0 and self._is_transition_frame(screen_image):
            tick_frames = min(step, remaining)
            self.emulator.tick(max(1, tick_frames))
            remaining -= tick_frames
            screen_image = self.emulator.get_screen_image()

        if self._is_transition_frame(screen_image):
            return self._capture_observation_frame()
        return screen_image

    def _publish_visualizer_preview(self, warmup_frames: int = 0) -> None:
        """Publish one non-turn-consuming snapshot for the dashboard."""
        if not self.config.get('visualization.enabled', True):
            return
        if not all(hasattr(self, attr) for attr in ("visualizer", "emulator", "game_state", "main_agent")):
            return
        if not hasattr(self.visualizer, "update_state") or not hasattr(self.visualizer, "update_screenshot"):
            return

        screen_image = self._capture_startup_preview_frame(warmup_frames=warmup_frames)
        current_state = self.game_state.update(screen_image=screen_image)
        current_state = self._synchronize_runtime_turn_state(current_state)
        self._last_observed_state = current_state

        try:
            if hasattr(self.main_agent, 'goals') and self.main_agent.goals:
                self.main_agent.goals.sync_with_game_state(current_state)

            self.visualizer.update_state(current_state)
            if screen_image:
                self.visualizer.update_screenshot(screen_image, force=True)
            if hasattr(self.main_agent, 'goals') and self.main_agent.goals and hasattr(self.visualizer, "update_goals"):
                self.visualizer.update_goals(self.main_agent.goals.get_dashboard_items())
            self._broadcast_control_state()
        finally:
            self.game_state.reset_tracking(turn_count=self.turn_count)

    def _publish_post_action_screenshot(self) -> None:
        """Push the latest post-action frame so the dashboard is not one action behind."""
        if not self.config.get('visualization.enabled', True):
            return

        latest_image = self._capture_observation_frame()
        if latest_image:
            self.visualizer.update_screenshot(latest_image)

    def _capture_observation_frame(self):
        """Capture a stable frame, skipping transient black/white transition frames."""
        screen_image = self.emulator.get_screen_image()
        max_retries = int(self.config.get('actions.observation_retry_frames', 4) or 4)
        settle_ticks = int(self.config.get('actions.observation_retry_tick_frames', 2) or 2)

        for _ in range(max_retries):
            if not self._is_transition_frame(screen_image):
                return screen_image
            self.emulator.tick(max(1, settle_ticks))
            screen_image = self.emulator.get_screen_image()

        return screen_image

    def _is_transition_frame(self, screen_image) -> bool:
        """Detect mostly blank transition frames that are poor inputs for AI and UI."""
        if not screen_image:
            return False

        img_array = np.array(screen_image.convert("RGB"))
        brightness = float(np.mean(img_array)) / 255.0
        contrast = float(np.std(img_array)) / 255.0

        too_dark = brightness < 0.04 and contrast < 0.05
        too_bright = brightness > 0.96 and contrast < 0.05
        return too_dark or too_bright

    def _execute_manual_action(self, action: str) -> None:
        """Execute one manual action while AI autoplay is paused."""
        self.turn_count += 1
        self.logger.info(f"执行手动操作: {action}")

        success = self.action_executor.execute(action)
        if not success:
            self.logger.warning(f"手动操作失败: {action}")
            self._record_control_event(f"manual:{action}", error="manual action failed")
            self._broadcast_control_state()
            return

        screen_image = self._capture_observation_frame()
        current_state = self.game_state.update(screen_image=screen_image)
        self._apply_screen_type_hint(current_state, screen_image)
        current_state = self._synchronize_runtime_turn_state(current_state)
        self._publish_visualizer_state(current_state, screen_image)
        self.progress_tracker.update(self.turn_count, current_state)
        self.visualizer.update_decision(action, f"手动控制：{action}", self.turn_count)
        self.visualizer.log_event('info', f'手动操作: {action}')
        self._last_observed_state = current_state
        self._last_action = None
        self._last_action_reasoning = ""
        self._last_action_source = None
        self._clear_planned_actions()

    def _record_control_event(self, command: str, error: Optional[str] = None) -> None:
        """Record the latest dashboard command outcome."""
        self._last_control_command = command
        self._last_control_timestamp = datetime.now().isoformat()
        self._last_control_error = error

    def _broadcast_control_state(self) -> None:
        """Broadcast the latest dashboard control state if visualization is active."""
        if hasattr(self, 'visualizer') and self.config.get('visualization.enabled', True):
            self.visualizer.update_control_state(self.get_visualizer_control_state())

    def _is_paused(self) -> bool:
        """Return whether autoplay is currently paused."""
        with self._control_lock:
            return self._paused

    def _consume_step_request(self) -> bool:
        """Consume one queued single-step request."""
        with self._control_lock:
            if self._step_budget <= 0:
                return False
            self._step_budget -= 1
            return True

    def _consume_checkpoint_request(self) -> bool:
        """Consume a pending checkpoint request."""
        with self._control_lock:
            if not self._checkpoint_requested:
                return False
            self._checkpoint_requested = False
            return True

    def _pop_manual_action(self) -> Optional[str]:
        """Pop one queued manual action if any."""
        try:
            return self._manual_actions.get_nowait()
        except queue.Empty:
            return None

    def get_visualizer_control_state(self) -> dict:
        """Expose dashboard control state for the web UI."""
        checkpoints = self.get_available_checkpoints(limit=1)
        latest_checkpoint = checkpoints[0]["name"] if checkpoints else None
        with self._control_lock:
            return {
                "running": self.running and self.emulator.is_running(),
                "paused": self._paused,
                "step_budget": self._step_budget,
                "manual_queue_size": self._manual_actions.qsize(),
                "last_command": self._last_control_command,
                "last_command_at": self._last_control_timestamp,
                "last_error": self._last_control_error,
                "checkpoint_count": len(self.get_available_checkpoints(limit=None)),
                "latest_checkpoint": latest_checkpoint,
                "restored_checkpoint": self._restored_checkpoint_name,
                "auto_resume_latest_checkpoint": bool(
                    self.config.get("game.auto_resume_latest_checkpoint", False)
                ),
                "turn": self.turn_count,
            }

    def handle_visualizer_command(self, command: str, value: Optional[str] = None) -> dict:
        """Handle a dashboard-issued control command."""
        normalized = (command or "").strip().lower()
        value = (value or "").strip().lower() if isinstance(value, str) else value

        if normalized == "pause":
            with self._control_lock:
                self._paused = True
                self._record_control_event("pause")
            self.logger.info("已从仪表板暂停自动运行")
            self.visualizer.log_event('info', '已暂停自动运行')
        elif normalized == "resume":
            with self._control_lock:
                self._paused = False
                self._step_budget = 0
                self._record_control_event("resume")
            self.logger.info("已从仪表板恢复自动运行")
            self.visualizer.log_event('info', '已恢复自动运行')
        elif normalized == "step":
            with self._control_lock:
                self._paused = True
                self._step_budget += 1
                self._record_control_event("step")
            self.logger.info("已从仪表板请求单步执行")
        elif normalized == "checkpoint":
            with self._control_lock:
                self._checkpoint_requested = True
                self._record_control_event("checkpoint")
            self.logger.info("已从仪表板请求保存检查点")
            self.visualizer.log_event('milestone', '已请求保存检查点')
        elif normalized == "stop":
            with self._control_lock:
                self.running = False
                self._record_control_event("stop")
            self.logger.warning("已从仪表板请求停止运行")
            self.visualizer.log_event('error', '已请求停止运行')
        elif normalized == "manual_action":
            if value not in ActionExecutor.VALID_ACTIONS:
                self._record_control_event("manual", error=f"invalid action: {value}")
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": f"无效动作: {value}",
                    "state": self.get_visualizer_control_state(),
                }
            with self._control_lock:
                if not self._paused:
                    self._record_control_event(f"manual:{value}", error="pause required")
                    self._broadcast_control_state()
                    return {
                        "ok": False,
                        "message": "请先暂停自动运行，再发送手动操作",
                        "state": self.get_visualizer_control_state(),
                    }
            try:
                self._manual_actions.put_nowait(value)
            except queue.Full:
                self._record_control_event(f"manual:{value}", error="manual queue full")
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": "手动操作队列已满，请稍后重试",
                    "state": self.get_visualizer_control_state(),
                }
            self._record_control_event(f"manual:{value}")
            self.logger.info(f"已从仪表板排队手动操作: {value}")
        else:
            self._record_control_event(normalized or "unknown", error="unknown command")
            self._broadcast_control_state()
            return {
                "ok": False,
                "message": f"未知控制命令: {command}",
                "state": self.get_visualizer_control_state(),
            }

        self._broadcast_control_state()
        return {
            "ok": True,
            "message": "命令已接受",
            "state": self.get_visualizer_control_state(),
        }

    def _detect_screen_type(self, screen_image) -> Optional[str]:
        """轻量识别当前屏幕类型（对话/菜单/战斗/标题等）。"""
        if not screen_image or not hasattr(self, "vision") or not self.vision:
            return None
        try:
            import numpy as np

            img_array = np.array(screen_image.convert("RGB"))
            ui = self.vision._detect_ui_elements(img_array)
            if ui.get("options_menu"):
                return "options_menu"
            if ui.get("startup_menu"):
                return "startup_menu"
            if ui.get("naming_screen"):
                return "naming_screen"
            if ui.get("pokemon_menu"):
                return "pokemon_menu"
            if ui.get("item_menu"):
                return "item_menu"
            if ui.get("save_menu"):
                return "save_menu"
            if ui.get("menu_open"):
                return "menu"
            if ui.get("title_screen"):
                return "title"
            if ui.get("text_box") and not ui.get("battle_ui"):
                return "dialogue"
            if self._has_visible_dialogue_box(screen_image) and not ui.get("battle_ui"):
                return "dialogue"
            if ui.get("text_entry"):
                return "text_entry"
            return self.vision._identify_screen_type(img_array, ui)
        except Exception:
            return None

    def _has_visible_dialogue_box(self, screen_image) -> bool:
        """Fallback detector for the large Gen-1 dialogue panel at the bottom of the screen."""
        if not screen_image:
            return False

        img = np.array(screen_image.convert("L"))
        if img.ndim != 2 or img.shape[0] < 60 or img.shape[1] < 120:
            return False

        box = img[-50:-2, 2:-2]
        interior = box[6:-6, 6:-6]
        border = np.concatenate(
            [
                box[:3, :].ravel(),
                box[-3:, :].ravel(),
                box[:, :3].ravel(),
                box[:, -3:].ravel(),
            ]
        )
        bright_ratio = float(np.mean(interior > 170))
        border_dark_ratio = float(np.mean(border < 90))
        top_dark_ratio = float(np.mean(box[:3, :] < 90))
        left_dark_ratio = float(np.mean(box[:, :3] < 90))
        return (
            bright_ratio > 0.75
            and border_dark_ratio > 0.45
            and top_dark_ratio > 0.20
            and left_dark_ratio > 0.30
        )

    def _compute_exact_screen_hash(self, screen_image) -> Optional[str]:
        """Compute a stable frame hash for narrow deterministic scene handlers."""
        if not screen_image:
            return None
        return hashlib.md5(screen_image.convert("L").tobytes()).hexdigest()

    def _compute_screen_signature(self, screen_image) -> Optional[bytes]:
        """Build a small image signature for deadlock detection."""
        if not screen_image:
            return None

        resample = (
            Image.Resampling.NEAREST
            if hasattr(Image, "Resampling")
            else Image.NEAREST
        )
        thumb = screen_image.convert("L").resize((20, 18), resample=resample)
        arr = np.array(thumb, dtype=np.uint8)
        return (arr // 16).astype(np.uint8).tobytes()

    def _update_screen_stability(
        self,
        current_state: dict,
        screen_image,
        screen_type: Optional[str],
    ) -> None:
        """Track how long the observed UI has remained effectively unchanged."""
        signature = self._compute_screen_signature(screen_image)
        if signature is None:
            self._last_screen_signature = None
            self._stable_screen_turns = 0
            return

        memory = current_state.get("memory", {})
        position = memory.get("position", {})
        memory_signature = (
            position.get("map_id"),
            position.get("x"),
            position.get("y"),
            memory.get("in_battle"),
            len(memory.get("party", [])),
            memory.get("money"),
        )
        combined = (screen_type, memory_signature, signature)
        if combined == self._last_screen_signature:
            self._stable_screen_turns += 1
        else:
            self._stable_screen_turns = 1
        self._last_screen_signature = combined

    def _recent_actions_are_same(self, action: str, count: int = 6) -> bool:
        """Return True when the recent action history is the same button repeatedly."""
        history = self.action_executor.get_action_history(count)
        return len(history) >= count and all(item == action for item in history[-count:])

    def _clear_scripted_ui_actions(self) -> None:
        """Clear any queued deterministic UI macro."""
        self._scripted_ui_actions = []
        self._scripted_ui_reasoning = ""

    def _clear_scripted_bootstrap_actions(self) -> None:
        """Clear any queued deterministic early-game bootstrap macro."""
        self._scripted_bootstrap_steps = []
        self._scripted_bootstrap_reasoning = ""

    def _load_scripted_bootstrap(
        self,
        steps: List[Dict[str, str]],
        reasoning: str,
    ) -> None:
        """Load a deterministic early-game bootstrap macro."""
        self._scripted_bootstrap_steps = list(steps)
        self._scripted_bootstrap_reasoning = reasoning

    def _get_pre_starter_bootstrap_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Handle the known bedroom SNES deadlock and the immediate stairs descent deterministically."""
        memory = current_state.get("memory", {})
        if memory.get("party") or memory.get("in_battle"):
            self._clear_scripted_bootstrap_actions()
            return None

        position = memory.get("position", {})
        map_id = int(position.get("map_id", -1))
        x = int(position.get("x", -1))
        y = int(position.get("y", -1))

        if not self._scripted_bootstrap_steps:
            if map_id == 38 and x == 3 and y == 6 and screen_type == "dialogue":
                steps: List[Dict[str, str]] = []
                for _ in range(19):
                    steps.append({"kind": "wait", "action": "wait"})
                    steps.append({"kind": "press", "action": "a"})
                steps.extend(
                    [
                        {"kind": "wait", "action": "wait"},
                        {"kind": "press", "action": "a"},
                        {"kind": "wait", "action": "wait"},
                        {"kind": "press", "action": "a"},
                        {"kind": "wait", "action": "wait"},
                        {"kind": "wait", "action": "wait"},
                        {"kind": "press", "action": "a"},
                        {"kind": "press", "action": "down"},
                        {"kind": "press", "action": "down"},
                        {"kind": "wait", "action": "wait"},
                    ]
                )
                steps.extend(
                    {"kind": "step", "action": action}
                    for action in ["up", "right", "up", "up", "up", "up", "up", "up", "right", "up"]
                )
                self._load_scripted_bootstrap(
                    steps,
                    "Bootstrap: clear the bedroom SNES dialogue loop and descend the stairs",
                )
            elif map_id == 37 and x == 7 and y == 1:
                self._load_scripted_bootstrap(
                    [{"kind": "step", "action": action} for action in ["down", "up", "down", "up", "down", "up", "left", "up", "left", "up", "down"]],
                    "Bootstrap: descend from the upstairs landing to the house main floor",
                )
            else:
                return None

        step = self._scripted_bootstrap_steps.pop(0)
        is_wait_step = step["kind"] == "wait"
        return {
            "action": "progress" if is_wait_step else step["action"],
            "reasoning": self._scripted_bootstrap_reasoning,
            "goal_update": None,
            "recorded_in_context": True if is_wait_step else False,
            "executor": "bootstrap",
            "bootstrap_kind": step["kind"],
        }

    def _execute_bootstrap_action(self, decision: dict) -> bool:
        """Execute a deterministic bootstrap step using raw emulator control."""
        action = decision.get("action", "wait")
        kind = decision.get("bootstrap_kind", "press")

        if kind == "wait":
            wait_frames = int(self.config.get("actions.wait_frames", 30) or 30)
            settle_frames = int(self.config.get("actions.wait_settle_frames", 2) or 2)
            self.emulator.tick(max(1, wait_frames))
            self.emulator.tick(max(0, settle_frames))
            time.sleep(0.05)
            return True

        if kind == "step":
            before = self.memory_reader.read_player_position()
            wait_frames = int(self.config.get("actions.wait_frames", 30) or 30)
            settle_frames = int(self.config.get("actions.wait_settle_frames", 2) or 2)
            for _ in range(12):
                self.emulator.press_button(action)
                after = self.memory_reader.read_player_position()
                if (
                    before.get("map_id"),
                    before.get("x"),
                    before.get("y"),
                ) != (
                    after.get("map_id"),
                    after.get("x"),
                    after.get("y"),
                ):
                    return True
                self.emulator.tick(max(1, wait_frames))
                self.emulator.tick(max(0, settle_frames))
            return True

        self.emulator.press_button(action)
        return True

    def _build_pending_ai_decision(self) -> dict:
        """Return a lightweight placeholder while the model thinks in the background."""
        return {
            "action": "thinking",
            "reasoning": "AI is thinking in the background while the main loop keeps advancing.",
            "goal_update": None,
            "recorded_in_context": True,
            "executor": "async_background_wait",
            "async_pending": True,
            "decision_source": "async_pending",
            "decision_path": "tool",
        }

    def _build_passive_progress_decision(self, reasoning: str, *, source: str) -> dict:
        """Advance frames without surfacing WAIT as a visible gameplay action."""
        return {
            "action": "progress",
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": True,
            "executor": "async_background_wait",
            "decision_source": source,
            "decision_path": "tool",
        }

    def _execute_async_background_wait(self) -> bool:
        """Advance a few frames without blocking the game loop on the model."""
        wait_frames = int(self.config.get("actions.async_wait_frames", 2) or 2)
        sleep_ms = float(self.config.get("actions.async_wait_sleep_ms", 33) or 33)
        self.action_executor.reset_stuck_detection()
        self.emulator.tick(max(1, wait_frames))
        if sleep_ms > 0:
            time.sleep(max(0.0, sleep_ms / 1000.0))
        return True

    def _get_minimal_known_ui_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Handle only the safest non-gameplay UI states in LLM-primary mode."""
        if screen_type == "title":
            return {
                "action": "start",
                "reasoning": "Auto: leave the title screen",
                "goal_update": None,
                "recorded_in_context": False,
            }
        if screen_type == "startup":
            return self._build_passive_progress_decision(
                "Auto: let the boot transition finish while the loop keeps advancing",
                source="startup_progress",
            )
        if screen_type == "startup_menu":
            return {
                "action": "a",
                "reasoning": "Auto: confirm the new-game menu",
                "goal_update": None,
                "recorded_in_context": False,
            }
        if screen_type == "options_menu":
            return {
                "action": "b",
                "reasoning": "Auto: leave the options menu",
                "goal_update": None,
                "recorded_in_context": False,
            }
        return None

    def _get_known_ui_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Handle known deterministic startup/configuration screens without the LLM."""
        if screen_type != "naming_screen":
            self._clear_scripted_ui_actions()

        if screen_type == "title":
            return {
                "action": "start",
                "reasoning": "自动处理：越过标题画面",
                "goal_update": None,
                "recorded_in_context": False,
            }
        if screen_type == "startup":
            return self._build_passive_progress_decision(
                "Auto: advance startup frames without exposing WAIT",
                source="startup_progress",
            )
        if screen_type == "startup_menu":
            return {
                "action": "a",
                "reasoning": "自动处理：确认开局菜单中的新游戏",
                "goal_update": None,
                "recorded_in_context": False,
            }
        if screen_type == "options_menu":
            return {
                "action": "b",
                "reasoning": "自动处理：退出设置菜单",
                "goal_update": None,
                "recorded_in_context": False,
            }
        if screen_type == "naming_screen":
            memory = current_state.get("memory", {}) or {}
            position = memory.get("position", {}) or {}
            map_id = int(position.get("map_id", 0) or 0)
            badge_count = int(memory.get("badge_count", 0) or 0)
            party_size = len(memory.get("party", []) or [])
            if map_id == 40 and badge_count == 0 and party_size <= 1:
                self._clear_scripted_ui_actions()
                return {
                    "action": "b",
                    "reasoning": "Auto: skip Oak Lab nickname entry and keep the starter's default name",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
            if not self._scripted_ui_actions:
                self._scripted_ui_actions = ["up", "up", "a", "start"]
                self._scripted_ui_reasoning = "自动处理：输入一个简短单字名并确认"
            action = self._scripted_ui_actions.pop(0)
            return {
                "action": action,
                "reasoning": self._scripted_ui_reasoning,
                "goal_update": None,
                "recorded_in_context": False,
            }
        return None

    def _should_auto_advance_dialogue(self) -> bool:
        """Avoid blind A-spam when a dialogue classification is not producing change."""
        return not (
            self._stable_screen_turns >= 8
            and self._recent_actions_are_same("a", 6)
        )

    def _get_dialogue_timing_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Drive dialogue pages deterministically instead of relying on blind A-spam."""
        if screen_type != "dialogue":
            return None

        wait_streak = 0
        for action in reversed(self.action_executor.get_action_history(8)):
            if action != "wait":
                break
            wait_streak += 1

        local_analysis_enabled = bool(
            current_state.get("visual", {}).get("local_analysis_enabled", False)
        )
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", -1) or -1)
        party_size = len(memory.get("party", []) or [])
        badge_count = int(memory.get("badge_count", 0) or 0)
        in_battle = bool(memory.get("in_battle"))

        if (
            map_id == 40
            and party_size == 1
            and badge_count == 0
            and not in_battle
            and not local_analysis_enabled
        ):
            return {
                "action": "a",
                "reasoning": "Auto: fast-advance Oak Lab's post-starter dialogue until the rival battle handoff is complete",
                "goal_update": None,
                "recorded_in_context": False,
            }
        if current_state.get("pre_starter_script") and not local_analysis_enabled:
            return {
                "action": "a",
                "reasoning": "自动处理：快速推进获得第一只宝可梦前的开场对话",
                "goal_update": None,
                "recorded_in_context": False,
            }
        required_wait_streak = 2 if local_analysis_enabled else 1

        if wait_streak >= required_wait_streak:
            return {
                "action": "a",
                "reasoning": "自动处理：当前页渲染完成后，定期推进对话",
                "goal_update": None,
                "recorded_in_context": False,
            }

        motion = current_state.get("visual", {}).get("motion", {})
        change_amount = float(motion.get("change_amount", 0.0) or 0.0)
        if self._last_action == "a" or change_amount > 0.003 or self._stable_screen_turns <= 2:
            return self._build_passive_progress_decision(
                "Auto: let the current dialogue page finish rendering before the next confirm",
                source="dialogue_render_progress",
            )
        return {
            "action": "a",
            "reasoning": "自动处理：文本稳定后推进当前对话页",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _get_early_story_interaction_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """When the agent has no Pokemon and is stalled indoors, try interacting first."""
        memory = current_state.get("memory", {})
        if memory.get("party") or memory.get("in_battle"):
            return None
        if screen_type not in {"indoor", "overworld", "memory_only", None}:
            return None
        if self._dialogue_exit_grace > 0:
            return None

        stall_turns = int(current_state.get("deltas", {}).get("movement_stall_turns", 0) or 0)
        if stall_turns < 6:
            return None
        if self._recent_actions_are_same("a", 3):
            return None

        navigation = current_state.get("navigation", {})
        if navigation.get("nearest_frontier") or current_state.get("exploration", {}).get("nearby_unexplored"):
            return None
        if int(navigation.get("current_visit_count", 0) or 0) >= 8:
            return None

        return {
            "action": "a",
            "reasoning": "自动处理：早期流程无宝可梦且停滞，尝试与当前阻挡物或目标交互",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _get_pre_starter_recovery_move_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """When the model is unreliable early on, keep exploring instead of idling forever."""
        memory = current_state.get("memory", {})
        if memory.get("party") or memory.get("in_battle"):
            return None
        if current_state.get("pre_world"):
            return None
        if screen_type not in {"overworld", "indoor", "memory_only", None}:
            return None

        stall_turns = int(current_state.get("deltas", {}).get("movement_stall_turns", 0) or 0)
        if stall_turns < 2:
            return None

        vision = current_state.get("visual", {}).get("navigation_hints", {})
        blocked = set(current_state.get("navigation", {}).get("blocked_directions", []))
        blocked.update(vision.get("blocked_directions", []))

        for direction in vision.get("walkable_directions", []):
            if direction not in blocked:
                return {
                    "action": direction,
                    "reasoning": f"自动处理：开局前恢复阶段，沿可见可通行方向 {direction} 继续探索",
                    "goal_update": None,
                    "recorded_in_context": False,
                }

        for direction in ["up", "left", "right", "down"]:
            if direction not in blocked:
                return {
                    "action": direction,
                    "reasoning": f"自动处理：开局前恢复阶段，尝试方向 {direction}，避免原地空转",
                    "goal_update": None,
                    "recorded_in_context": False,
                }

        return None

    def _get_stable_ui_recovery_decision(
        self,
        current_state: dict,
        screen_type: Optional[str],
    ) -> Optional[dict]:
        """Choose a safe escape action when the UI is stable but button presses do nothing."""
        if int(getattr(self, "_stable_screen_turns", 0) or 0) < 8:
            return None

        if screen_type == "dialogue" and self._recent_actions_are_same("a", 6):
            return {
                "action": "b",
                "reasoning": "自动处理：连续按 A 后对话界面未变化，先返回以摆脱误判的对话状态",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if screen_type in {"menu", "pokemon_menu", "item_menu", "save_menu", "text_entry"}:
            if self._recent_actions_are_same("a", 6):
                return {
                    "action": "b",
                    "reasoning": "自动处理：连续按 A 后当前界面无变化，尝试取消或返回",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
            if self._recent_actions_are_same("b", 6):
                return {
                    "action": "start",
                    "reasoning": "自动处理：连续按 B 后当前界面无变化，尝试用 Start 作为第二逃逸手段",
                    "goal_update": None,
                    "recorded_in_context": False,
                }

        return None

    def _should_auto_close_menu(self, current_state: dict, screen_type: Optional[str]) -> bool:
        """Auto-close clearly harmful early-game menus without calling the LLM."""
        if screen_type not in {"menu", "pokemon_menu", "item_menu", "save_menu"}:
            return False
        if self._screen_type_streak < 2:
            return False

        memory = current_state.get("memory", {})
        if memory.get("in_battle"):
            return False
        if memory.get("party"):
            return False

        return True

    def _choose_recovery_move(self, current_state: dict) -> str:
        """选择一个简单的移动动作，用于打破反复对话/交互循环。"""
        try:
            pos = current_state.get("memory", {}).get("position", {})
            x = int(pos.get("x", 0))
            y = int(pos.get("y", 0))
            tiles = current_state.get("exploration", {}).get("nearby_unexplored", [])
            if tiles:
                tx, ty = tiles[0]
                dx = tx - x
                dy = ty - y
                if abs(dy) >= abs(dx):
                    return "down" if dy > 0 else "up"
                return "right" if dx > 0 else "left"
        except Exception:
            pass
        return "down"

    def _get_ai_decision_responsive(
        self,
        current_state: dict,
        state_text: str,
        screenshot_bytes: Optional[bytes] = None
    ) -> dict:
        """在保持PyBoy窗口响应的同时获取AI决策。

        参数:
            current_state: 当前游戏状态
            state_text: 状态的文本表示
            screenshot_bytes: 当前屏幕的PNG字节（用于视觉模型）

        返回:
            包含行动和推理的决策字典
        """
        if self._pure_llm_mode_enabled():
            return self.main_agent.decide_action(
                current_state,
                state_text,
                screenshot_bytes=screenshot_bytes
            )

        use_async = bool(self.config.get('performance.async_decisions', True))
        if (
            not use_async
            or not hasattr(self, 'async_ai')
            or not getattr(self.async_ai, 'running', False)
        ):
            # 回退到同步模式（会阻塞）
            return self.main_agent.decide_action(
                current_state,
                state_text,
                screenshot_bytes=screenshot_bytes
            )

        decision = self.async_ai.get_decision(timeout=0.0)
        if decision:
            return decision

        if not self.async_ai.is_thinking:
            queued = self.async_ai.request_decision(current_state, state_text, screenshot_bytes)
            if not queued:
                self.logger.debug("Async decision request could not be queued; keeping realtime fallback active")

        return self._build_pending_ai_decision()


    def _handle_stuck_state(self, current_state: dict) -> None:
        """Handle a stuck state by asking the critic for correction."""
        if self._pure_llm_mode_enabled():
            self._clear_planned_actions()
            return
        if self.main_agent.is_in_api_cooldown():
            self.logger.info("Skipping stuck critique while the main API client is cooling down")
            return
        history = self.action_executor.get_action_history(20)
        history_text = f"Recent actions: {', '.join(history)}"

        critique = self.critic.critique(history_text, current_state)
        self._clear_planned_actions()

        self.logger.info(f"Critic assessment: {critique['assessment']}")
        self.logger.info(f"Critic issues: {critique['issues']}")
        self.logger.info(f"Critic suggestions: {critique['suggestions']}")

        note_parts = []
        if critique.get("issues"):
            note_parts.append(f"Issues: {critique['issues']}")
        if critique.get("suggestions"):
            note_parts.append(f"Suggestions: {critique['suggestions']}")
        note = " | ".join(" ".join(part.split()) for part in note_parts).strip()
        if note:
            self.main_agent.add_guidance_note(note[:600], source="critic-stuck")

    def _checkpoint_root(self) -> Path:
        """Return the configured checkpoint directory."""
        return Path(self.config.get("game.save_state_dir"))

    def get_available_checkpoints(self, limit: Optional[int] = 20) -> List[Dict[str, Any]]:
        """Return recent checkpoints sorted from newest to oldest."""
        return list_checkpoints(self._checkpoint_root(), limit=limit)

    def _resolve_checkpoint_dir(self, checkpoint_name: Optional[str]) -> Path:
        """Resolve a checkpoint name or alias to a directory."""
        checkpoint_name = (checkpoint_name or "latest").strip()
        root = self._checkpoint_root()

        if checkpoint_name.lower() == "latest":
            checkpoints = self.get_available_checkpoints(limit=1)
            if not checkpoints:
                raise FileNotFoundError(f"在 {root} 中未找到任何存档")
            return Path(checkpoints[0]["path"])

        candidate = root / checkpoint_name
        if candidate.exists():
            return candidate

        if checkpoint_name.isdigit():
            candidate = root / f"checkpoint_{checkpoint_name}"
            if candidate.exists():
                return candidate

        raise FileNotFoundError(f"未找到存档：{checkpoint_name}")

    def _maybe_restore_initial_checkpoint(self) -> None:
        """Auto-resume from a configured checkpoint when requested."""
        requested = self.config.get("game.resume_checkpoint")
        auto_latest = bool(self.config.get("game.auto_resume_latest_checkpoint", False))
        if requested:
            self._load_checkpoint(str(requested), pause_after_load=False)
            return
        if auto_latest and self.get_available_checkpoints(limit=1):
            self._load_checkpoint("latest", pause_after_load=False)

    def _load_checkpoint(self, checkpoint_name: str = "latest", pause_after_load: bool = False) -> Dict[str, Any]:
        """Restore emulator and agent state from a checkpoint."""
        checkpoint_dir = self._resolve_checkpoint_dir(checkpoint_name)
        emulator_state = checkpoint_dir / "emulator.state"
        if not emulator_state.exists():
            raise FileNotFoundError(f"存档缺少 emulator.state 文件：{checkpoint_dir}")

        metadata = load_checkpoint_metadata(checkpoint_dir)

        self.logger.info(f"正在从 {checkpoint_dir} 读取存档")
        self.emulator.load_state(str(emulator_state))
        self.main_agent.load_state(str(checkpoint_dir))

        map_memory_path = checkpoint_dir / "map_memory.json"
        if map_memory_path.exists():
            self.map_memory.load(str(map_memory_path))
        else:
            self.map_memory.load()

        progress_path = checkpoint_dir / "progress.json"
        if progress_path.exists():
            self.progress_tracker.load(str(progress_path))

        restored_turn = int(metadata.get("turn", 0) or 0)
        self.turn_count = restored_turn
        self.last_checkpoint_turn = restored_turn
        self.game_state.reset_tracking(turn_count=restored_turn)
        self.action_executor.reset_stuck_detection()
        self._clear_planned_actions()
        self._clear_scripted_ui_actions()
        self._clear_scripted_bootstrap_actions()
        self.oak_lab_pre_starter.reset()
        self.oak_lab_starter.reset()
        self.oak_lab_post_starter.reset()
        self.oak_lab_rival_battle.reset()
        self.early_battle_controller.reset()
        self.post_battle_intro_route.reset()
        self.viridian_parcel_controller.reset()
        self.post_pokedex_departure_controller.reset()
        self._last_observed_state = None
        self._last_action = None
        self._last_action_reasoning = ""
        self._last_action_source = None
        self._recent_warp_exit = None
        self._prev_screen_type = metadata.get("screen_type")
        self._stable_screen_turns = 0
        self._last_screen_signature = None
        self._phase_hint_turns_remaining = 0
        self._recent_battle_visual_grace_turns = 0
        self._restored_checkpoint_name = checkpoint_dir.name
        self._active_landmark_checkpoints = set()
        self._startup_selection_pending = False

        if pause_after_load:
            with self._control_lock:
                self._paused = True

        if self.config.get("visualization.enabled", True):
            self.visualizer.update_checkpoints(self.get_available_checkpoints())
            self._publish_visualizer_preview(warmup_frames=0)
            self.visualizer.log_event("milestone", f"已恢复存档 {checkpoint_dir.name}")
            self._broadcast_control_state()

        self.logger.milestone(f"已恢复存档 {checkpoint_dir.name}")
        return metadata

    def _save_screenshot(self) -> None:
        """保存带注释的截图。"""
        screenshot_dir = Path(self.config.get('logging.screenshot_dir'))
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        filename = screenshot_dir / f"turn_{self.turn_count:06d}.png"

        screen = self.emulator.get_screen_image()
        self.vision.save_annotated_screenshot(screen, str(filename))

    def _save_checkpoint(self) -> None:
        """保存检查点。"""
        self.logger.info(f"正在保存回合{self.turn_count}的检查点")

        checkpoint_dir = self._checkpoint_root() / f"checkpoint_{self.turn_count}"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # 保存模拟器状态
        self.emulator.save_state(str(checkpoint_dir / "emulator.state"))

        # 保存智能体状态
        self.main_agent.save_state(str(checkpoint_dir))

        # 保存地图记忆
        self.map_memory.save()
        self.map_memory.save(str(checkpoint_dir / "map_memory.json"))

        # 保存进度
        self.progress_tracker.save(str(checkpoint_dir / "progress.json"))

        primary_goal = None
        if getattr(self.main_agent, "goals", None) and self.main_agent.goals.primary_goal:
            primary_goal = self.main_agent.goals.primary_goal.description
        focus = getattr(getattr(self.main_agent, "goals", None), "focus", None)
        metadata = build_checkpoint_metadata(
            name=checkpoint_dir.name,
            turn=self.turn_count,
            current_state=self._last_observed_state,
            focus=focus,
            primary_goal=primary_goal,
        )
        write_checkpoint_metadata(checkpoint_dir, metadata)

        max_checkpoints = int(self.config.get("game.max_checkpoints", 0) or 0)
        removed = prune_old_checkpoints(self._checkpoint_root(), max_checkpoints) if max_checkpoints else []
        for removed_path in removed:
            self.logger.info(f"已删除旧回合存档 {removed_path.name}")

        if self.config.get("visualization.enabled", True):
            self.visualizer.update_checkpoints(self.get_available_checkpoints())

        self.logger.info(f"检查点已保存到 {checkpoint_dir}")

        # 打印进度摘要
        self.logger.info("\n" + self.progress_tracker.get_progress_summary())

    def get_startup_checkpoint_choices(self) -> List[Dict[str, Any]]:
        """Return checkpoint candidates worth presenting at startup."""
        recent_limit = int(self.config.get("game.startup_checkpoint_recent_limit", 8) or 8)
        return list_startup_checkpoints(
            self._checkpoint_root(),
            recent_turn_limit=recent_limit,
        )

    def _dashboard_startup_selection_enabled(self) -> bool:
        """Prefer the dashboard for startup checkpoint selection when visualization is active."""
        return bool(
            self.config.get("game.prompt_for_checkpoint_on_start", False)
            and self.config.get("visualization.enabled", True)
        )

    def _set_startup_selection_pending(self, pending: bool) -> None:
        """Track whether the runtime is waiting for an operator startup choice."""
        self._startup_selection_pending = bool(pending)

    def _maybe_restore_initial_checkpoint(self) -> None:
        """Restore immediately or pause for dashboard-based startup selection."""
        if self._dashboard_startup_selection_enabled():
            with self._control_lock:
                self._paused = True
            self._set_startup_selection_pending(True)
            if self.config.get("visualization.enabled", True):
                self._publish_visualizer_preview(warmup_frames=240)
                self.visualizer.update_checkpoints(self.get_available_checkpoints())
                self.visualizer.log_event(
                    "milestone",
                    "等待选择启动点：请在大屏中读取存档，或点击继续开始新开局",
                )
                self._broadcast_control_state()
            return

        requested = self.config.get("game.resume_checkpoint")
        auto_latest = bool(self.config.get("game.auto_resume_latest_checkpoint", False))
        if requested:
            self._load_checkpoint(str(requested), pause_after_load=False)
            return
        if auto_latest and self.get_available_checkpoints(limit=1):
            self._load_checkpoint("latest", pause_after_load=False)

    def get_visualizer_control_state(self) -> dict:
        """Expose dashboard control state for the web UI."""
        checkpoints = self.get_available_checkpoints(limit=1)
        latest_checkpoint = checkpoints[0]["name"] if checkpoints else None
        cooldown_active = False
        cooldown_remaining = 0.0
        if hasattr(self, "main_agent") and hasattr(self.main_agent, "is_in_api_cooldown"):
            try:
                cooldown_active = bool(self.main_agent.is_in_api_cooldown())
                if hasattr(self.main_agent, "api_cooldown_remaining_seconds"):
                    cooldown_remaining = float(self.main_agent.api_cooldown_remaining_seconds())
            except Exception:
                cooldown_active = False
                cooldown_remaining = 0.0

        with self._control_lock:
            return {
                "running": self.running and self.emulator.is_running(),
                "paused": self._paused,
                "step_budget": self._step_budget,
                "manual_queue_size": self._manual_actions.qsize(),
                "last_command": self._last_control_command,
                "last_command_at": self._last_control_timestamp,
                "last_error": self._last_control_error,
                "checkpoint_count": len(self.get_available_checkpoints(limit=None)),
                "latest_checkpoint": latest_checkpoint,
                "restored_checkpoint": self._restored_checkpoint_name,
                "auto_resume_latest_checkpoint": bool(
                    self.config.get("game.auto_resume_latest_checkpoint", False)
                ),
                "api_cooldown_active": cooldown_active,
                "api_cooldown_remaining": cooldown_remaining,
                "startup_selection_pending": self._startup_selection_pending,
                "startup_checkpoint_choices": self.get_startup_checkpoint_choices()
                if self._startup_selection_pending
                else [],
                "startup_default_checkpoint": _startup_checkpoint_default_label(self.config),
                "turn": self.turn_count,
            }

    def _get_landmark_checkpoint_specs(self) -> List[Dict[str, Any]]:
        """Normalize configured named checkpoint specs."""
        if not self.config.get("game.landmark_checkpoints_enabled", False):
            return []

        raw_specs = self.config.get("game.landmark_checkpoints", {}) or {}
        specs: List[Dict[str, Any]] = []

        if isinstance(raw_specs, dict):
            items = raw_specs.items()
        elif isinstance(raw_specs, list):
            items = [(item.get("name"), item) for item in raw_specs if isinstance(item, dict)]
        else:
            items = []

        for default_name, raw_spec in items:
            if not isinstance(raw_spec, dict):
                continue
            spec = dict(raw_spec)
            spec_name = str(spec.get("name") or default_name or "").strip()
            if not spec_name:
                continue
            spec["name"] = spec_name
            spec["label"] = str(spec.get("label") or spec_name).strip()
            specs.append(spec)

        return specs

    def _checkpoint_spec_matches(
        self,
        spec: Dict[str, Any],
        current_state: Optional[Dict[str, Any]],
    ) -> bool:
        """Return whether the current observation matches a named checkpoint spec."""
        if not spec or not current_state:
            return False

        memory = current_state.get("memory", {}) or {}
        visual = current_state.get("visual", {}) or {}
        position = memory.get("position", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        party_size = len(memory.get("party", []) or [])
        badge_count = int(memory.get("badge_count", 0) or 0)

        equality_checks = (
            ("map_id", position.get("map_id")),
            ("x", position.get("x")),
            ("y", position.get("y")),
            ("screen_type", visual.get("screen_type")),
            ("pre_world", current_state.get("pre_world")),
            ("pre_starter_script", current_state.get("pre_starter_script")),
            ("in_battle", memory.get("in_battle")),
            ("text_box_active", ui_state.get("text_box_active")),
        )
        for key, actual_value in equality_checks:
            expected = spec.get(key)
            if expected is None:
                continue
            if key in {"map_id", "x", "y"}:
                if int(actual_value if actual_value is not None else -1) != int(expected):
                    return False
                continue
            if isinstance(expected, bool):
                if bool(actual_value) != expected:
                    return False
                continue
            if str(actual_value or "").strip().lower() != str(expected).strip().lower():
                return False

        direction = spec.get("direction")
        if direction is not None:
            current_direction = str(memory.get("direction") or "").strip().lower()
            if current_direction != str(direction).strip().lower():
                return False

        min_party_size = spec.get("min_party_size")
        if min_party_size is not None and party_size < int(min_party_size):
            return False
        max_party_size = spec.get("max_party_size")
        if max_party_size is not None and party_size > int(max_party_size):
            return False

        min_badges = spec.get("min_badges")
        if min_badges is not None and badge_count < int(min_badges):
            return False
        max_badges = spec.get("max_badges")
        if max_badges is not None and badge_count > int(max_badges):
            return False

        return True

    def _maybe_save_landmark_checkpoints(self, current_state: Optional[Dict[str, Any]]) -> None:
        """Save stable named checkpoints when the run reaches configured milestones."""
        if not self._checkpoint_writes_enabled():
            return

        matched_now: set[str] = set()
        for spec in self._get_landmark_checkpoint_specs():
            checkpoint_name = str(spec.get("name") or "").strip()
            if not checkpoint_name:
                continue
            if not self._checkpoint_spec_matches(spec, current_state):
                continue

            matched_now.add(checkpoint_name)
            if checkpoint_name in self._active_landmark_checkpoints:
                continue

            checkpoint_dir, _metadata = self._write_checkpoint_bundle(
                checkpoint_name,
                kind="named",
                label=str(spec.get("label") or checkpoint_name),
                current_state=current_state,
            )
            self.logger.info(f"已保存里程碑存档 {checkpoint_dir.name}")
            if self.config.get("visualization.enabled", True):
                self.visualizer.log_event("milestone", f"已保存里程碑存档 {checkpoint_dir.name}")

        self._active_landmark_checkpoints = matched_now

    def _write_checkpoint_bundle(
        self,
        checkpoint_name: str,
        *,
        kind: str,
        label: Optional[str] = None,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> tuple[Path, Dict[str, Any]]:
        """Write emulator, agent, map, progress, and metadata into one checkpoint directory."""
        checkpoint_dir = self._checkpoint_root() / checkpoint_name
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.emulator.save_state(str(checkpoint_dir / "emulator.state"))
        self.main_agent.save_state(str(checkpoint_dir))
        self.map_memory.save()
        self.map_memory.save(str(checkpoint_dir / "map_memory.json"))
        self.progress_tracker.save(str(checkpoint_dir / "progress.json"))

        primary_goal = None
        if getattr(self.main_agent, "goals", None) and self.main_agent.goals.primary_goal:
            primary_goal = self.main_agent.goals.primary_goal.description
        focus = getattr(getattr(self.main_agent, "goals", None), "focus", None)
        metadata = build_checkpoint_metadata(
            name=checkpoint_dir.name,
            turn=self.turn_count,
            current_state=current_state or self._last_observed_state,
            focus=focus,
            primary_goal=primary_goal,
            label=label,
            kind=kind,
        )
        write_checkpoint_metadata(checkpoint_dir, metadata)

        if self.config.get("visualization.enabled", True):
            self.visualizer.update_checkpoints(self.get_available_checkpoints())

        return checkpoint_dir, metadata

    def _save_checkpoint(self) -> None:
        """Save a regular turn checkpoint and prune older turn slots."""
        checkpoint_dir, _metadata = self._write_checkpoint_bundle(
            f"checkpoint_{self.turn_count}",
            kind="turn",
            label=f"回合 {self.turn_count}",
        )

        max_checkpoints = int(self.config.get("game.max_checkpoints", 0) or 0)
        removed = prune_old_checkpoints(self._checkpoint_root(), max_checkpoints) if max_checkpoints else []
        if removed and self.config.get("visualization.enabled", True):
            self.visualizer.update_checkpoints(self.get_available_checkpoints())

        for removed_path in removed:
            self.logger.info(f"已删除旧回合存档 {removed_path.name}")

        self.last_checkpoint_turn = self.turn_count
        self.logger.info(f"检查点已保存到 {checkpoint_dir}")
        self.logger.info("\n" + self.progress_tracker.get_progress_summary())

    def handle_visualizer_command(self, command: str, value: Optional[str] = None) -> dict:
        """Handle a dashboard-issued control command."""
        normalized = (command or "").strip().lower()
        raw_value = (value or "").strip() if isinstance(value, str) else value
        manual_value = raw_value.lower() if isinstance(raw_value, str) else raw_value

        if normalized == "pause":
            with self._control_lock:
                self._paused = True
                self._record_control_event("pause")
            self.logger.info("已从仪表盘暂停自动运行")
            self.visualizer.log_event("info", "已从仪表盘暂停自动运行")
        elif normalized == "resume":
            with self._control_lock:
                self._paused = False
                self._step_budget = 0
                self._record_control_event("resume")
            self._set_startup_selection_pending(False)
            self.logger.info("已从仪表盘恢复自动运行")
            self.visualizer.log_event("info", "已从仪表盘恢复自动运行")
        elif normalized == "step":
            with self._control_lock:
                self._paused = True
                self._step_budget += 1
                self._record_control_event("step")
            self._set_startup_selection_pending(False)
            self.logger.info("已从仪表盘请求单步执行")
        elif normalized == "checkpoint":
            with self._control_lock:
                self._checkpoint_requested = True
                self._record_control_event("checkpoint")
            self.logger.info("已从仪表盘请求保存检查点")
            self.visualizer.log_event("milestone", "已从仪表盘请求保存检查点")
        elif normalized == "load_latest_checkpoint":
            try:
                metadata = self._load_checkpoint("latest", pause_after_load=True)
            except Exception as exc:
                self._record_control_event("load_latest_checkpoint", error=str(exc))
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": f"读取最新存档失败：{exc}",
                    "state": self.get_visualizer_control_state(),
                }
            with self._control_lock:
                self._step_budget = 0
            while self._pop_manual_action() is not None:
                pass
            self._set_startup_selection_pending(False)
            self._record_control_event("load_latest_checkpoint")
            self.logger.info(f"已读取最新存档 {metadata.get('name') or self._restored_checkpoint_name}")
            self.visualizer.log_event(
                "milestone",
                f"已读取最新存档 {metadata.get('name') or self._restored_checkpoint_name}",
            )
        elif normalized == "load_checkpoint":
            if not raw_value:
                self._record_control_event("load_checkpoint", error="必须提供存档名称")
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": "必须提供存档名称",
                    "state": self.get_visualizer_control_state(),
                }
            try:
                metadata = self._load_checkpoint(str(raw_value), pause_after_load=True)
            except Exception as exc:
                self._record_control_event("load_checkpoint", error=str(exc))
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": f"读取存档 {raw_value} 失败：{exc}",
                    "state": self.get_visualizer_control_state(),
                }
            with self._control_lock:
                self._step_budget = 0
            while self._pop_manual_action() is not None:
                pass
            self._set_startup_selection_pending(False)
            self._record_control_event(f"load_checkpoint:{raw_value}")
            self.logger.info(f"已读取存档 {metadata.get('name') or raw_value}")
            self.visualizer.log_event("milestone", f"已读取存档 {metadata.get('name') or raw_value}")
        elif normalized == "stop":
            with self._control_lock:
                self.running = False
                self._record_control_event("stop")
            self.logger.warning("已从仪表盘请求停止运行")
            self.visualizer.log_event("error", "已从仪表盘请求停止运行")
        elif normalized == "manual_action":
            if manual_value not in ActionExecutor.VALID_ACTIONS:
                self._record_control_event("manual", error=f"无效手动动作：{raw_value}")
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": f"无效手动动作：{raw_value}",
                    "state": self.get_visualizer_control_state(),
                }
            with self._control_lock:
                if not self._paused:
                    self._record_control_event(f"manual:{manual_value}", error="需要先暂停自动运行")
                    self._broadcast_control_state()
                    return {
                        "ok": False,
                        "message": "请先暂停自动运行，再加入手动动作",
                        "state": self.get_visualizer_control_state(),
                    }
            try:
                self._manual_actions.put_nowait(manual_value)
            except queue.Full:
                self._record_control_event(f"manual:{manual_value}", error="手动动作队列已满")
                self._broadcast_control_state()
                return {
                    "ok": False,
                    "message": "手动动作队列已满",
                    "state": self.get_visualizer_control_state(),
                }
            self._set_startup_selection_pending(False)
            self._record_control_event(f"manual:{manual_value}")
            self.logger.info(f"已从仪表盘加入手动动作：{manual_value}")
        else:
            self._record_control_event(normalized or "unknown", error="未知控制指令")
            self._broadcast_control_state()
            return {
                "ok": False,
                "message": f"未知控制指令：{command}",
                "state": self.get_visualizer_control_state(),
            }

        self._broadcast_control_state()
        return {
            "ok": True,
            "message": "指令已发送",
            "state": self.get_visualizer_control_state(),
        }

    def _signal_handler(self, sig, frame) -> None:
        """处理中断信号。"""
        self.logger.info("收到中断信号")
        self.running = False
        self._broadcast_control_state()

    def _shutdown(self) -> None:
        """优雅地关闭。"""
        self.logger.info("正在关闭...")
        self._broadcast_control_state()

        # 停止异步AI
        if hasattr(self, 'async_ai'):
            self.async_ai.stop()

        # 保存最终检查点
        if self._checkpoint_writes_enabled():
            self._save_checkpoint()
        else:
            self.logger.info("Skipping checkpoint write on shutdown for this testing run")

        # 停止可视化器
        if hasattr(self, 'visualizer'):
            self.visualizer.stop()

        # 停止模拟器
        self.emulator.stop()

        self.logger.milestone("宝可梦AI智能体已停止")
        self.logger.info(f"总回合数: {self.turn_count}")

def _startup_checkpoint_default_label(config) -> str:
    """Describe the current startup restore behavior."""
    requested = config.get("game.resume_checkpoint")
    if requested:
        return str(requested)
    if config.get("game.auto_resume_latest_checkpoint", False):
        return "latest"
    return "new"


def _startup_checkpoint_display_label(value: str) -> str:
    """Translate startup shortcut values into Chinese labels for terminal prompts."""
    normalized = str(value or "").strip().lower()
    if normalized == "latest":
        return "最新存档"
    if normalized == "new":
        return "新开局"
    return str(value or "")


def _checkpoint_kind_label(kind: str) -> str:
    """Translate checkpoint kind labels for terminal display."""
    normalized = str(kind or "").strip().lower()
    if normalized == "turn":
        return "回合存档"
    if normalized == "named":
        return "里程碑存档"
    return str(kind or "未知")


def _prompt_for_startup_checkpoint(config) -> None:
    """Optionally let the operator choose a checkpoint before agent startup."""
    if not config.get("game.prompt_for_checkpoint_on_start", False):
        return
    if config.get("visualization.enabled", True):
        return
    if not getattr(sys.stdin, "isatty", lambda: False)():
        return

    choices = list_startup_checkpoints(
        config.get("game.save_state_dir"),
        recent_turn_limit=int(config.get("game.startup_checkpoint_recent_limit", 8) or 8),
    )
    if not choices:
        return

    default_label = _startup_checkpoint_display_label(_startup_checkpoint_default_label(config))
    print("可选启动存档：")
    for index, checkpoint in enumerate(choices, start=1):
        position = checkpoint.get("position", {}) or {}
        checkpoint_label = checkpoint.get("label") or checkpoint.get("name") or f"checkpoint-{index}"
        print(
            f"  {index}. {checkpoint_label} "
            f"[{checkpoint.get('name')}] "
            f"(回合 {checkpoint.get('turn', 0)}, 地图 {position.get('map_id')}, "
            f"坐标 {position.get('x')},{position.get('y')}, 类型 {_checkpoint_kind_label(checkpoint.get('kind', 'unknown'))})"
        )
    print(f"直接回车可保持默认启动方式：{default_label}")
    print("可输入序号、精确存档名、latest，或输入 new 开始新开局。")

    lookup = {
        str(checkpoint.get("name")): str(checkpoint.get("name"))
        for checkpoint in choices
        if checkpoint.get("name")
    }

    while True:
        try:
            raw_choice = input("启动存档> ").strip()
        except EOFError:
            return

        if not raw_choice:
            return

        normalized = raw_choice.lower()
        if normalized in {"n", "new", "none"}:
            config.set("game.resume_checkpoint", None)
            config.set("game.auto_resume_latest_checkpoint", False)
            return
        if normalized == "latest":
            config.set("game.resume_checkpoint", None)
            config.set("game.auto_resume_latest_checkpoint", True)
            return
        if raw_choice.isdigit():
            choice_index = int(raw_choice) - 1
            if 0 <= choice_index < len(choices):
                config.set("game.resume_checkpoint", str(choices[choice_index]["name"]))
                config.set("game.auto_resume_latest_checkpoint", False)
                return
        if raw_choice in lookup:
            config.set("game.resume_checkpoint", lookup[raw_choice])
            config.set("game.auto_resume_latest_checkpoint", False)
            return

        print("输入无效，请输入列表序号、存档名、latest 或 new。")


def main():
    """主入口点。"""
    print("=" * 60)
    print("宝可梦AI智能体")
    print("由已配置 AI 模型驱动")
    print("=" * 60)
    print()

    # 检查API密钥
    if not os.getenv('AI_API_KEY'):
        print("错误: 未设置 API 密钥环境变量")
        print("请设置 AI_API_KEY")
        sys.exit(1)

    if not os.getenv('AI_BASE_URL'):
        print("错误: 未设置 AI 接口地址环境变量")
        print("请设置 AI_BASE_URL")
        sys.exit(1)

    # 检查ROM
    if not os.path.exists('PokemonRed.gb'):
        print("错误: 当前目录未找到PokemonRed.gb")
        sys.exit(1)

    try:
        config = get_config()
    except Exception as e:
        print(f"错误: 配置校验失败: {e}")
        sys.exit(1)

    if not config.get('ai.model'):
        print("错误: 未配置 AI 模型")
        print("请在 config.yaml 中设置 ai.model，或设置 AI_MODEL")
        sys.exit(1)

    print("正在初始化...")
    print()

    _prompt_for_startup_checkpoint(config)

    try:
        agent = PokemonAIAgent()
        agent.run()
    except Exception as e:
        print(f"\n致命错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
