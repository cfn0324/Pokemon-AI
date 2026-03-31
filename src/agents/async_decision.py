"""Async AI decision wrapper for non-blocking gameplay."""

import threading
import queue
import time
from typing import Dict, Any, Optional
from ..utils.logger import get_logger
from .main_agent import AIDecisionRetrySignal


class AsyncDecisionMaker:
    """Asynchronous AI decision maker to prevent UI blocking."""

    def __init__(self, main_agent):
        """Initialize async decision maker.

        Args:
            main_agent: MainAgent instance
        """
        self.main_agent = main_agent
        self.logger = get_logger('AsyncAI')

        # Thread communication
        self.request_queue = queue.Queue(maxsize=1)
        self.result_queue = queue.Queue(maxsize=1)
        self.worker_thread = None
        self.running = False

        # Current state
        self.is_thinking = False
        self.last_decision = None

    def start(self):
        """Start the worker thread."""
        if self.running:
            self.logger.warning("Worker thread already running")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.logger.info("Async decision maker started")

    def _worker_loop(self):
        """Worker thread main loop."""
        while self.running:
            try:
                # Wait for a decision request (blocking with timeout)
                request = self.request_queue.get(timeout=1.0)

                if request is None:  # Shutdown signal
                    break

                self.is_thinking = True
                current_state, state_text, screenshot_bytes = request

                # Make decision (this is the slow part)
                try:
                    decision = self._decide_with_retry(
                        current_state,
                        state_text,
                        screenshot_bytes=screenshot_bytes
                    )
                    # Ensure we never block the worker on a full result queue.
                    try:
                        self.result_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.result_queue.put(decision, block=False)
                    self.last_decision = decision
                except Exception as e:
                    self.logger.error(f"Error in decision making: {e}", exc_info=True)
                    # Put a default "wait" decision on error
                    try:
                        self.result_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.result_queue.put(
                        {
                            "action": "wait",
                            "reasoning": f"Async AI error: {str(e)}",
                            "goal_update": None,
                            "recorded_in_context": False,
                            "decision_source": "ai_error",
                            "decision_path": "ai",
                        },
                        block=False,
                    )

                self.is_thinking = False

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker thread error: {e}", exc_info=True)
                self.is_thinking = False

        self.logger.info("Worker thread stopped")

    def _decide_with_retry(
        self,
        current_state: Dict[str, Any],
        state_text: str,
        screenshot_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Retry transient model failures without blocking the main gameplay loop."""
        config = self.main_agent.config
        if not bool(config.get("decision.retry_same_turn_on_ai_error", True)):
            return self.main_agent.decide_action(
                current_state,
                state_text,
                screenshot_bytes=screenshot_bytes,
            )

        max_attempts = max(1, int(config.get("decision.same_turn_retry_max_attempts", 12) or 12))
        timeout_seconds = max(
            0.0,
            float(config.get("decision.same_turn_retry_timeout_seconds", 45) or 45),
        )
        min_delay_seconds = max(
            0.0,
            float(config.get("decision.same_turn_retry_min_delay_seconds", 0.25) or 0.25),
        )
        started_at = time.monotonic()
        attempt = 0

        while True:
            attempt += 1
            try:
                return self.main_agent.decide_action(
                    current_state,
                    state_text,
                    screenshot_bytes=screenshot_bytes,
                )
            except AIDecisionRetrySignal as exc:
                elapsed = time.monotonic() - started_at
                if attempt >= max_attempts or (timeout_seconds and elapsed >= timeout_seconds):
                    raise RuntimeError(
                        "Async same-turn AI retry budget exhausted "
                        f"after {attempt} attempts over {elapsed:.1f}s: {exc}"
                    ) from exc

                remaining_budget = None
                if timeout_seconds:
                    remaining_budget = max(0.0, timeout_seconds - elapsed)
                delay_seconds = max(min_delay_seconds, exc.retry_after_seconds)
                if remaining_budget is not None:
                    delay_seconds = min(delay_seconds, remaining_budget)

                self.logger.warning(
                    "Retrying async AI decision "
                    f"({exc.source}) in {delay_seconds:.1f}s "
                    f"[attempt {attempt}/{max_attempts}]"
                )
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

    def request_decision(
        self,
        current_state: Dict[str, Any],
        state_text: str,
        screenshot_bytes: Optional[bytes] = None
    ) -> bool:
        """Request a decision asynchronously.

        Args:
            current_state: Current game state
            state_text: Text representation of state
            screenshot_bytes: Optional PNG bytes for vision-enabled models

        Returns:
            True if request was queued, False if already processing
        """
        if self.is_thinking:
            return False  # Already processing a decision

        try:
            # Clear any old requests
            try:
                self.request_queue.get_nowait()
            except queue.Empty:
                pass
            # Clear any old results (prevents returning stale decisions)
            try:
                while True:
                    self.result_queue.get_nowait()
            except queue.Empty:
                pass

            # Queue the new request
            self.request_queue.put((current_state, state_text, screenshot_bytes), block=False)
            return True
        except queue.Full:
            return False

    def get_decision(self, timeout: float = 0.0) -> Optional[Dict[str, Any]]:
        """Get a decision if ready.

        Args:
            timeout: How long to wait for result (0 = non-blocking)

        Returns:
            Decision dict if ready, None otherwise
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_ready(self) -> bool:
        """Check if a decision is ready.

        Returns:
            True if decision is available
        """
        return not self.result_queue.empty()

    def stop(self):
        """Stop the worker thread."""
        if not self.running:
            return

        self.running = False
        self.request_queue.put(None)  # Shutdown signal

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)

        self.logger.info("Async decision maker stopped")
