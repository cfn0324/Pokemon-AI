"""Async AI decision wrapper for non-blocking gameplay."""

import threading
import queue
import time
from typing import Dict, Any, Optional
from ..utils.logger import get_logger


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
                current_state, state_text = request

                # Make decision (this is the slow part)
                try:
                    decision = self.main_agent.decide_action(current_state, state_text)
                    self.result_queue.put(decision)
                    self.last_decision = decision
                except Exception as e:
                    self.logger.error(f"Error in decision making: {e}", exc_info=True)
                    # Put a default "wait" decision on error
                    self.result_queue.put({'action': 'wait', 'reasoning': f'Error: {str(e)}'})

                self.is_thinking = False

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker thread error: {e}", exc_info=True)
                self.is_thinking = False

        self.logger.info("Worker thread stopped")

    def request_decision(self, current_state: Dict[str, Any], state_text: str) -> bool:
        """Request a decision asynchronously.

        Args:
            current_state: Current game state
            state_text: Text representation of state

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

            # Queue the new request
            self.request_queue.put((current_state, state_text), block=False)
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
