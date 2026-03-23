"""Decision engine for routing between deterministic tools and AI fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class DecisionContext:
    """Runtime inputs for one control-cycle decision."""

    current_state: Dict[str, Any]
    state_text: str
    screen_type: Optional[str]
    screenshot_bytes: Optional[bytes] = None
    screen_hash: Optional[str] = None


DecisionHandler = Callable[[DecisionContext], Optional[Dict[str, Any]]]


class DecisionEngine:
    """Run ordered deterministic stages before falling back to the model."""

    def __init__(
        self,
        stages: Sequence[Tuple[str, DecisionHandler]],
        fallback: DecisionHandler,
    ):
        self.stages = list(stages)
        self.fallback = fallback

    def decide(self, context: DecisionContext) -> Dict[str, Any]:
        """Return the first matching decision, or the fallback decision."""
        trace: List[Dict[str, Any]] = []

        for stage_name, handler in self.stages:
            decision = handler(context)
            matched = bool(decision)
            trace.append({"stage": stage_name, "matched": matched})
            if not matched:
                continue

            enriched = dict(decision)
            enriched.setdefault("decision_path", "tool")
            enriched["decision_source"] = stage_name
            enriched["decision_trace"] = trace
            return enriched

        fallback = self.fallback(context) or {}
        enriched = dict(fallback)
        enriched.setdefault("decision_path", "ai")
        enriched.setdefault("decision_source", "ai")
        enriched["decision_trace"] = trace
        return enriched
