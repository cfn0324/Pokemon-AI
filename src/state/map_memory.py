"""Map memory system with fog-of-war tracking and a learned navigation graph."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger


Position = Tuple[int, int]
Node = Tuple[int, int, int]


class MapMemory:
    """Tracks explored tiles plus learned navigation structure."""

    CARDINALS: Dict[str, Position] = {
        "up": (0, -1),
        "down": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
    }

    def __init__(self, save_dir: str = "data/maps"):
        """Initialize map memory."""
        self.logger = get_logger("MapMemory")
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.explored_tiles: Dict[int, Set[Position]] = defaultdict(set)
        self.visit_counts: Dict[int, Dict[Position, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.edges: Dict[int, Dict[Position, Dict[str, Position]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self.blocked_moves: Dict[int, Dict[Position, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self.warp_points: Dict[Node, Dict[str, int]] = {}
        self.map_properties: Dict[int, Dict[str, Any]] = {}

        self.current_map: Optional[int] = None
        self.current_position: Optional[Position] = None

        self.load()
        self.logger.info("Map memory initialized")

    def update_position(
        self,
        map_id: int,
        x: int,
        y: int,
        previous_position: Optional[Dict[str, int]] = None,
    ) -> None:
        """Update current position, visit counts, and discovered transitions."""
        current = (x, y)
        self.current_map = map_id
        self.current_position = current

        self.explored_tiles[map_id].add(current)
        self.visit_counts[map_id][current] += 1

        if not previous_position:
            return

        prev_map = int(previous_position.get("map_id", map_id))
        prev = (int(previous_position.get("x", x)), int(previous_position.get("y", y)))

        if prev_map == map_id and prev == current:
            return

        self.explored_tiles[prev_map].add(prev)
        self.visit_counts[prev_map][prev] += 0

        if prev_map != map_id:
            self._record_warp(prev_map, prev, map_id, current)
            return

        direction = self._infer_direction(prev, current)
        if direction:
            self.edges[map_id][prev][direction] = current
            self.blocked_moves[map_id][prev].pop(direction, None)

    def record_failed_move(self, map_id: int, x: int, y: int, direction: str) -> None:
        """Remember a movement direction that appeared blocked from a tile."""
        direction = (direction or "").strip().lower()
        if direction not in self.CARDINALS:
            return

        pos = (x, y)
        blocked = self.blocked_moves[map_id][pos]
        blocked[direction] = int(blocked.get(direction, 0)) + 1

    def is_tile_explored(self, map_id: int, x: int, y: int) -> bool:
        """Check if a tile has been explored."""
        return (x, y) in self.explored_tiles.get(map_id, set())

    def get_explored_tiles(self, map_id: int) -> List[Position]:
        """Return all explored tiles for a map."""
        return list(self.explored_tiles.get(map_id, set()))

    def get_visit_count(self, map_id: int, x: int, y: int) -> int:
        """Return how many times a tile has been visited."""
        return int(self.visit_counts.get(map_id, {}).get((x, y), 0))

    def get_unexplored_adjacent(
        self,
        map_id: int,
        x: int,
        y: int,
        radius: int = 5,
    ) -> List[Position]:
        """Get unexplored coordinates near a position."""
        unexplored: List[Position] = []
        explored_set = self.explored_tiles.get(map_id, set())

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                pos = (x + dx, y + dy)
                if pos in explored_set:
                    continue
                if 0 <= pos[0] <= 255 and 0 <= pos[1] <= 255:
                    unexplored.append(pos)

        unexplored.sort(key=lambda p: abs(p[0] - x) + abs(p[1] - y))
        return unexplored

    def _get_map_centroid(self, explored: Set[Position]) -> Optional[Tuple[float, float]]:
        """Return the centroid of explored tiles for rough global novelty estimates."""
        if not explored:
            return None

        total_x = sum(pos[0] for pos in explored)
        total_y = sum(pos[1] for pos in explored)
        count = len(explored)
        return (total_x / count, total_y / count)

    def _get_local_visit_pressure(
        self,
        map_id: int,
        position: Position,
        radius: int = 2,
    ) -> int:
        """Measure how heavily a frontier's surrounding area has already been revisited."""
        visits = self.visit_counts.get(map_id, {})
        total = 0
        px, py = position
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                total += int(visits.get((px + dx, py + dy), 0))
        return total

    @staticmethod
    def _score_frontier_candidate(
        *,
        visit_count: int,
        distance: Optional[int],
        local_visit_pressure: int,
        global_novelty_distance: int,
        unknown_direction_count: int,
    ) -> float:
        """Balance path cost against escaping highly revisited local regions."""
        return round(
            (unknown_direction_count * 8.0)
            + (global_novelty_distance * 1.75)
            - (local_visit_pressure * 1.25)
            - (visit_count * 4.0)
            - ((distance or 0) * 0.35),
            2,
        )

    @staticmethod
    def _label_frontier_novelty(priority_score: float) -> str:
        """Bucket a frontier score into a prompt-friendly novelty label."""
        if priority_score >= 4.0:
            return "high"
        if priority_score >= -10.0:
            return "medium"
        return "low"

    @staticmethod
    def _frontier_plan_sort_key(frontier: Dict[str, Any]) -> Tuple[Any, ...]:
        """Return a stable sort key where lower is better."""
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

    def get_frontier_tiles(
        self,
        map_id: int,
        current_position: Optional[Position] = None,
    ) -> List[Dict[str, Any]]:
        """Return explored tiles that still border unknown space."""
        explored = self.explored_tiles.get(map_id, set())
        if not explored:
            return []

        current_position = current_position or self.current_position
        frontier_tiles: List[Dict[str, Any]] = []
        centroid = self._get_map_centroid(explored)

        for pos in explored:
            unknown_dirs: List[str] = []
            known_edges = self.edges.get(map_id, {}).get(pos, {})
            blocked = self.blocked_moves.get(map_id, {}).get(pos, {})

            for direction, (dx, dy) in self.CARDINALS.items():
                if direction in known_edges:
                    continue
                if int(blocked.get(direction, 0)) >= 2:
                    continue
                neighbor = (pos[0] + dx, pos[1] + dy)
                if neighbor not in explored:
                    unknown_dirs.append(direction)

            if not unknown_dirs:
                continue

            distance = None
            if current_position:
                distance = abs(pos[0] - current_position[0]) + abs(pos[1] - current_position[1])

            visit_count = int(self.visit_counts.get(map_id, {}).get(pos, 0))
            local_visit_pressure = self._get_local_visit_pressure(map_id, pos, radius=2)
            global_novelty_distance = 0
            if centroid:
                global_novelty_distance = int(
                    round(abs(pos[0] - centroid[0]) + abs(pos[1] - centroid[1]))
                )
            priority_score = self._score_frontier_candidate(
                visit_count=visit_count,
                distance=distance,
                local_visit_pressure=local_visit_pressure,
                global_novelty_distance=global_novelty_distance,
                unknown_direction_count=len(unknown_dirs),
            )

            frontier_tiles.append(
                {
                    "position": pos,
                    "unknown_directions": unknown_dirs,
                    "visit_count": visit_count,
                    "distance": distance,
                    "local_visit_pressure": local_visit_pressure,
                    "global_novelty_distance": global_novelty_distance,
                    "priority_score": priority_score,
                    "novelty_label": self._label_frontier_novelty(priority_score),
                }
            )

        frontier_tiles.sort(key=self._frontier_plan_sort_key)
        return frontier_tiles

    def find_shortest_path(
        self,
        map_id: int,
        start: Position,
        target: Position,
        max_depth: int = 64,
    ) -> Optional[List[str]]:
        """Find a movement path over the learned directed graph."""
        if start == target:
            return []

        queue: Deque[Tuple[Position, List[str]]] = deque([(start, [])])
        visited = {start}

        while queue:
            pos, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            for direction, neighbor in self.edges.get(map_id, {}).get(pos, {}).items():
                if neighbor in visited:
                    continue
                next_path = path + [direction]
                if neighbor == target:
                    return next_path
                visited.add(neighbor)
                queue.append((neighbor, next_path))

        return None

    def find_path_to_nearest_frontier(
        self,
        map_id: int,
        x: int,
        y: int,
        max_depth: int = 40,
    ) -> Optional[Dict[str, Any]]:
        """Find a path to a reachable frontier tile on the current map."""
        start = (x, y)
        frontier_tiles = self.get_frontier_tiles(map_id, current_position=start)
        if not frontier_tiles:
            return None

        best: Optional[Dict[str, Any]] = None
        for frontier in frontier_tiles:
            target = frontier["position"]
            path = self.find_shortest_path(map_id, start, target, max_depth=max_depth)
            if path is None and target != start:
                continue

            candidate = {
                "target": target,
                "path": path or [],
                "unknown_directions": frontier["unknown_directions"],
                "visit_count": frontier["visit_count"],
                "distance": frontier["distance"],
                "local_visit_pressure": frontier.get("local_visit_pressure", 0),
                "global_novelty_distance": frontier.get("global_novelty_distance", 0),
                "priority_score": frontier.get("priority_score", 0.0),
                "novelty_label": frontier.get("novelty_label", "unknown"),
            }

            if best is None:
                best = candidate
                continue

            current_key = self._frontier_plan_sort_key(candidate)
            best_key = self._frontier_plan_sort_key(best)
            if current_key < best_key:
                best = candidate

        return best

    def get_navigation_advice(self, map_id: int, x: int, y: int) -> Dict[str, Any]:
        """Return a structured navigation summary for the current tile and map."""
        pos = (x, y)
        current_edges = self.edges.get(map_id, {}).get(pos, {})
        blocked = self.blocked_moves.get(map_id, {}).get(pos, {})
        frontier_tiles = self.get_frontier_tiles(map_id, current_position=pos)
        frontier_plan = self.find_path_to_nearest_frontier(map_id, x, y)
        warps = self._get_map_warps(map_id)
        current_tile_warp = self._build_current_tile_warp(
            map_id=map_id,
            current_position=pos,
            known_warps=warps,
        )
        adjacent_tiles = self.describe_adjacent_tiles(
            map_id,
            x,
            y,
            frontier_tiles=frontier_tiles,
            frontier_plan=frontier_plan,
            known_warps=warps,
            current_tile_warp=current_tile_warp,
        )
        warp_cautions = self._build_warp_cautions(adjacent_tiles, warps)
        frontier_guidance = self._build_frontier_guidance(
            current_position=pos,
            frontier_tiles=frontier_tiles,
            adjacent_tiles=adjacent_tiles,
        )

        return {
            "current_visit_count": int(self.visit_counts.get(map_id, {}).get(pos, 0)),
            "known_exits": {
                direction: {"x": target[0], "y": target[1]}
                for direction, target in current_edges.items()
            },
            "blocked_directions": [
                direction
                for direction, count in sorted(blocked.items())
                if int(count) >= 1
            ],
            "frontier_count": len(frontier_tiles),
            "nearest_frontier": frontier_plan,
            "frontier_candidates": [
                {
                    "target": item["position"],
                    "unknown_directions": list(item.get("unknown_directions", [])),
                    "visit_count": int(item.get("visit_count", 0) or 0),
                    "distance": item.get("distance"),
                    "local_visit_pressure": int(item.get("local_visit_pressure", 0) or 0),
                    "global_novelty_distance": int(item.get("global_novelty_distance", 0) or 0),
                    "priority_score": float(item.get("priority_score", 0.0) or 0.0),
                    "novelty_label": item.get("novelty_label", "unknown"),
                }
                for item in frontier_tiles[:3]
            ],
            "adjacent_tiles": adjacent_tiles,
            "current_tile_warp": current_tile_warp,
            "warp_cautions": warp_cautions,
            "frontier_guidance": frontier_guidance,
            "known_warps": warps[:6],
            "local_map": self.render_local_map(map_id, x, y),
            "map_snapshot": self.build_map_snapshot(map_id, current_position=pos),
        }

    def describe_adjacent_tiles(
        self,
        map_id: int,
        x: int,
        y: int,
        *,
        frontier_tiles: Optional[List[Dict[str, Any]]] = None,
        frontier_plan: Optional[Dict[str, Any]] = None,
        known_warps: Optional[List[Dict[str, int]]] = None,
        current_tile_warp: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Describe the four neighboring tiles around the player using learned map memory."""
        pos = (x, y)
        explored = self.explored_tiles.get(map_id, set())
        visits = self.visit_counts.get(map_id, {})
        current_edges = self.edges.get(map_id, {}).get(pos, {})
        blocked = self.blocked_moves.get(map_id, {}).get(pos, {})
        frontier_tiles = frontier_tiles or self.get_frontier_tiles(map_id, current_position=pos)
        frontier_plan = frontier_plan or self.find_path_to_nearest_frontier(map_id, x, y)
        known_warps = known_warps or self._get_map_warps(map_id)

        current_frontier = next(
            (item for item in frontier_tiles if tuple(item.get("position") or ()) == pos),
            None,
        )
        frontier_directions = {
            str(direction or "").strip().lower()
            for direction in (current_frontier or {}).get("unknown_directions", []) or []
        }
        preferred_direction = None
        if frontier_plan and tuple(frontier_plan.get("target") or ()) == pos:
            path = frontier_plan.get("path") or []
            if path:
                preferred_direction = str(path[0] or "").strip().lower()
        current_tile_warp = current_tile_warp or self._build_current_tile_warp(
            map_id=map_id,
            current_position=pos,
            known_warps=known_warps,
        )
        current_tile_trigger_action = str(
            (current_tile_warp or {}).get("trigger_action") or ""
        ).strip().lower()
        if current_tile_trigger_action not in self.CARDINALS:
            current_tile_trigger_action = ""
        warp_positions = {
            (int(item["src_x"]), int(item["src_y"]))
            for item in known_warps
        }

        adjacent: Dict[str, Dict[str, Any]] = {}
        for direction, (dx, dy) in self.CARDINALS.items():
            target = (x + dx, y + dy)
            blocked_attempts = int(blocked.get(direction, 0) or 0)
            known_exit = current_edges.get(direction)
            target_pos = tuple(known_exit) if known_exit else target
            target_explored = target_pos in explored
            target_is_warp = target_pos in warp_positions
            target_visit_count = int(visits.get(target_pos, 0) or 0)
            step_triggers_warp = direction == current_tile_trigger_action
            status = "unknown"
            summary = "No reliable map-memory evidence yet; use the screenshot to verify this step."

            if known_exit:
                status = "known_exit"
                summary = (
                    f"This move previously succeeded and led to explored tile "
                    f"({target_pos[0]}, {target_pos[1]})."
                )
            elif blocked_attempts >= 2:
                status = "confirmed_blocked"
                summary = (
                    f"This move failed {blocked_attempts} times from the current tile; "
                    "treat it as a wall or solid blocker until evidence changes."
                )
            elif blocked_attempts == 1:
                status = "blocked_once"
                summary = (
                    "This move already failed once from the current tile; "
                    "avoid repeating it blindly."
                )
            elif direction in frontier_directions:
                status = "frontier"
                summary = "This is an unexplored adjacent direction from the current frontier."
            elif target_explored:
                status = "adjacent_explored"
                summary = (
                    f"Neighbor tile ({target_pos[0]}, {target_pos[1]}) has been explored, "
                    "but this exact step is not yet confirmed from the current tile."
                )

            if step_triggers_warp:
                destination = (current_tile_warp or {}).get("destination") or {}
                destination_text = ""
                if destination:
                    destination_text = (
                        f" to map {destination.get('map_id', '?')} "
                        f"({destination.get('x', '?')}, {destination.get('y', '?')})"
                    )
                status = "warp_trigger"
                summary = (
                    "This step previously triggered a map transition from the current tile"
                    f"{destination_text}; do not use it unless you intentionally want to change maps."
                )

            if target_is_warp and status in {"known_exit", "adjacent_explored"}:
                summary += " The target tile is also a known warp point."
            if preferred_direction and direction == preferred_direction and status == "frontier":
                summary += " This is also the first step of the best-known frontier route."

            adjacent[direction] = {
                "target": {"x": int(target_pos[0]), "y": int(target_pos[1])},
                "status": status,
                "blocked_attempts": blocked_attempts,
                "target_visit_count": target_visit_count,
                "target_known_explored": bool(target_explored),
                "target_is_warp": bool(target_is_warp),
                "step_triggers_warp": bool(step_triggers_warp),
                "is_frontier_direction": direction in frontier_directions,
                "is_preferred_frontier_step": direction == preferred_direction,
                "summary": summary,
            }

        return adjacent

    def _build_current_tile_warp(
        self,
        *,
        map_id: int,
        current_position: Position,
        known_warps: Optional[List[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """Describe when the current tile itself is a learned warp source."""
        known_warps = known_warps or []
        warp_lookup = {
            (int(item["src_x"]), int(item["src_y"])): item
            for item in known_warps
        }
        warp = warp_lookup.get(tuple(current_position))
        if not warp:
            return None

        destination = {
            "map_id": int(warp.get("dest_map", 0) or 0),
            "x": int(warp.get("dest_x", 0) or 0),
            "y": int(warp.get("dest_y", 0) or 0),
        }
        trigger_action = str(warp.get("trigger_action") or "").strip().lower()
        trigger_action_source = "learned"
        if trigger_action not in self.CARDINALS:
            trigger_action = None
            trigger_action_source = None

        if not trigger_action:
            known_exits = self.edges.get(map_id, {}).get(tuple(current_position), {})
            blocked = self.blocked_moves.get(map_id, {}).get(tuple(current_position), {})
            remaining_directions = [
                direction
                for direction in self.CARDINALS
                if direction not in known_exits and int(blocked.get(direction, 0) or 0) < 1
            ]
            if len(remaining_directions) == 1:
                trigger_action = remaining_directions[0]
                trigger_action_source = "inferred"

        summary = (
            f"Current tile ({current_position[0]}, {current_position[1]}) is a known warp source "
            f"to map {destination['map_id']} ({destination['x']}, {destination['y']})"
        )
        if trigger_action:
            if trigger_action_source == "inferred":
                summary += (
                    f"; the likely trigger action is {trigger_action} because other local moves already failed. "
                    "Step off this tile before probing unknown directions unless you intentionally want to change maps."
                )
            else:
                summary += (
                    f"; the learned trigger action is {trigger_action}. "
                    "Step off this tile before probing unknown directions unless you intentionally want to change maps."
                )
        else:
            summary += (
                "; the exact trigger action is not yet confirmed. "
                "Step off this tile carefully instead of blindly probing unknown directions."
            )

        return {
            "source": {
                "x": int(current_position[0]),
                "y": int(current_position[1]),
            },
            "destination": destination,
            "trigger_action": trigger_action,
            "trigger_action_source": trigger_action_source,
            "count": int(warp.get("count", 1) or 1),
            "summary": summary,
        }

    def _build_warp_cautions(
        self,
        adjacent_tiles: Dict[str, Dict[str, Any]],
        known_warps: List[Dict[str, int]],
    ) -> List[Dict[str, Any]]:
        """Surface adjacent warp tiles as explicit re-entry/change-map cautions."""
        warp_lookup = {
            (int(item["src_x"]), int(item["src_y"])): item
            for item in known_warps
        }
        cautions: List[Dict[str, Any]] = []

        for direction in self.CARDINALS:
            info = adjacent_tiles.get(direction) or {}
            if not info.get("target_is_warp"):
                continue

            target = info.get("target") or {}
            tx = int(target.get("x", 0) or 0)
            ty = int(target.get("y", 0) or 0)
            warp = warp_lookup.get((tx, ty), {})
            destination = None
            if warp:
                destination = {
                    "map_id": int(warp.get("dest_map", 0) or 0),
                    "x": int(warp.get("dest_x", 0) or 0),
                    "y": int(warp.get("dest_y", 0) or 0),
                }

            summary = f"{direction} is a known warp tile at ({tx}, {ty})"
            if destination:
                summary += (
                    f" leading to map {destination['map_id']} "
                    f"({destination['x']}, {destination['y']})"
                )
            summary += "; do not step on it unless you intentionally want to change maps."

            existing_summary = str(info.get("summary") or "").strip()
            extra = "Avoid stepping on it unless you intentionally want to warp."
            if extra not in existing_summary:
                info["summary"] = f"{existing_summary} {extra}".strip()

            cautions.append(
                {
                    "direction": direction,
                    "target": {"x": tx, "y": ty},
                    "destination": destination,
                    "summary": summary,
                }
            )

        return cautions

    def _build_frontier_guidance(
        self,
        *,
        current_position: Position,
        frontier_tiles: List[Dict[str, Any]],
        adjacent_tiles: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Warn when the current frontier is locally exhausted versus stronger alternatives."""
        guidance: Dict[str, Any] = {
            "current_tile_is_frontier": False,
            "prefer_leave_current_frontier": False,
            "recommended_direction": None,
            "escape_direction": None,
            "discouraged_directions": [],
            "stronger_frontier_target": None,
            "current_priority_score": None,
            "stronger_priority_score": None,
            "priority_gap": 0.0,
            "summary": None,
        }
        if not frontier_tiles:
            return guidance

        current_frontier = next(
            (
                item
                for item in frontier_tiles
                if tuple(item.get("position") or ()) == current_position
            ),
            None,
        )
        if not current_frontier:
            return guidance

        guidance["current_tile_is_frontier"] = True
        current_score = float(current_frontier.get("priority_score", 0.0) or 0.0)
        current_visits = int(current_frontier.get("visit_count", 0) or 0)
        current_pressure = int(current_frontier.get("local_visit_pressure", 0) or 0)
        guidance["current_priority_score"] = current_score

        best_alternative = next(
            (
                item
                for item in frontier_tiles
                if tuple(item.get("position") or ()) != current_position
            ),
            None,
        )
        if not best_alternative:
            return guidance

        alternative_target = tuple(best_alternative.get("position") or ())
        if len(alternative_target) != 2:
            return guidance

        alternative_score = float(best_alternative.get("priority_score", 0.0) or 0.0)
        priority_gap = round(alternative_score - current_score, 2)
        guidance["stronger_frontier_target"] = {
            "x": int(alternative_target[0]),
            "y": int(alternative_target[1]),
        }
        guidance["stronger_priority_score"] = alternative_score
        guidance["priority_gap"] = priority_gap

        candidate_directions = [
            str(direction or "").strip().lower()
            for direction in current_frontier.get("unknown_directions", []) or []
            if str(direction or "").strip().lower() in self.CARDINALS
        ]
        recommended_direction, discouraged_directions = self._choose_escape_directions(
            current_position,
            alternative_target,
            candidate_directions,
            adjacent_tiles,
        )
        guidance["recommended_direction"] = recommended_direction
        guidance["discouraged_directions"] = discouraged_directions
        escape_candidate_directions = [
            direction
            for direction in self.CARDINALS
            if (adjacent_tiles.get(direction) or {}).get("status") in {
                "frontier",
                "known_exit",
                "adjacent_explored",
            }
            and not (adjacent_tiles.get(direction) or {}).get("target_is_warp")
        ]
        escape_direction, _escape_discouraged = self._choose_escape_directions(
            current_position,
            alternative_target,
            escape_candidate_directions,
            adjacent_tiles,
        )
        guidance["escape_direction"] = escape_direction

        should_leave = priority_gap >= 6.0 and (
            current_visits >= 2
            or current_pressure >= 8
            or str(current_frontier.get("novelty_label") or "").strip().lower() == "low"
        )
        if not should_leave:
            return guidance

        guidance["prefer_leave_current_frontier"] = True
        target_text = f"({alternative_target[0]}, {alternative_target[1]})"
        preferred_direction = escape_direction or recommended_direction
        if preferred_direction:
            guidance["summary"] = (
                "Current tile is a weaker local frontier "
                f"(score {current_score}, pressure {current_pressure}, visits {current_visits}). "
                f"A stronger frontier at {target_text} scores {alternative_score}; "
                f"prefer {preferred_direction} instead of probing every adjacent unknown here."
            )
        else:
            guidance["summary"] = (
                "Current tile is a weaker local frontier "
                f"(score {current_score}, pressure {current_pressure}, visits {current_visits}). "
                f"A stronger frontier at {target_text} scores {alternative_score}; "
                "leave this fringe instead of probing every adjacent unknown here."
            )
        return guidance

    def _choose_escape_directions(
        self,
        current_position: Position,
        target_position: Position,
        candidate_directions: List[str],
        adjacent_tiles: Dict[str, Dict[str, Any]],
    ) -> Tuple[Optional[str], List[str]]:
        """Rank frontier directions by whether they move toward a stronger alternative."""
        if not candidate_directions:
            return None, []

        base_distance = abs(current_position[0] - target_position[0]) + abs(
            current_position[1] - target_position[1]
        )
        ranked: List[Tuple[float, str, int]] = []
        direction_order = {
            direction: index
            for index, direction in enumerate(candidate_directions)
        }

        for direction in candidate_directions:
            delta = self.CARDINALS.get(direction)
            if not delta:
                continue

            info = adjacent_tiles.get(direction) or {}
            target = info.get("target") or {}
            next_position = (
                int(target.get("x", current_position[0] + delta[0]) or 0),
                int(target.get("y", current_position[1] + delta[1]) or 0),
            )
            distance = abs(next_position[0] - target_position[0]) + abs(
                next_position[1] - target_position[1]
            )
            warp_penalty = 100 if info.get("target_is_warp") else 0
            revisit_penalty = float(info.get("target_visit_count", 0) or 0) * 0.25
            ranked.append((distance + warp_penalty + revisit_penalty, direction, distance))

        if not ranked:
            return None, []

        ranked.sort(key=lambda item: (item[0], direction_order.get(item[1], 999)))
        best_score, best_direction, best_distance = ranked[0]
        recommended_direction = best_direction if best_distance <= base_distance else None
        discouraged = [
            direction
            for score, direction, _distance in ranked[1:]
            if score > best_score
        ]
        return recommended_direction, discouraged

    def get_navigation_text(self, map_id: int, x: int, y: int) -> str:
        """Return a compact prompt-friendly text summary."""
        advice = self.get_navigation_advice(map_id, x, y)
        lines = [
            "NAVIGATION ADVISOR:",
            f"- Current tile visit count: {advice['current_visit_count']}",
        ]

        known_exits = advice.get("known_exits", {})
        if known_exits:
            exits_text = ", ".join(
                f"{direction}->({target['x']},{target['y']})"
                for direction, target in known_exits.items()
            )
            lines.append(f"- Known successful exits from this tile: {exits_text}")
        else:
            lines.append("- Known successful exits from this tile: none yet")

        blocked = advice.get("blocked_directions", [])
        lines.append(
            f"- Known blocked directions from this tile: {', '.join(blocked) if blocked else 'none recorded'}"
        )
        adjacent_tiles = advice.get("adjacent_tiles", {})
        if adjacent_tiles:
            lines.append("- Adjacent tile summary:")
            for direction in self.CARDINALS:
                info = adjacent_tiles.get(direction, {})
                target = info.get("target", {})
                lines.append(
                    "- "
                    f"{direction}: {info.get('status', 'unknown')} "
                    f"-> ({target.get('x', '?')},{target.get('y', '?')})"
                )

        frontier = advice.get("nearest_frontier")
        if frontier:
            path = frontier.get("path", [])
            target = frontier.get("target")
            unknown_dirs = ", ".join(frontier.get("unknown_directions", [])) or "none"
            novelty = frontier.get("novelty_label", "unknown")
            local_pressure = frontier.get("local_visit_pressure", 0)
            novelty_distance = frontier.get("global_novelty_distance", 0)
            if path:
                lines.append(
                    f"- Suggested route to the current best frontier tile {target}: {', '.join(path[:12])}"
                )
            else:
                lines.append(
                    f"- You are already standing on a frontier tile {target}; unexplored directions from here: {unknown_dirs}"
                )
            lines.append(
                f"- Frontier novelty: {novelty}; local revisit pressure={local_pressure}; global novelty distance={novelty_distance}"
            )
        else:
            lines.append("- No reachable frontier route is currently known on this map.")

        alternatives = advice.get("frontier_candidates", [])
        if alternatives:
            lines.append("- Top frontier candidates:")
            for item in alternatives:
                lines.append(
                    "- "
                    f"{tuple(item.get('target', ())) or 'unknown'} "
                    f"novelty={item.get('novelty_label', 'unknown')} "
                    f"pressure={item.get('local_visit_pressure', 0)} "
                    f"unknown={','.join(item.get('unknown_directions', [])) or 'none'}"
                )

        for caution in advice.get("warp_cautions", []):
            lines.append(f"- Warp caution: {caution.get('summary')}")

        current_tile_warp = advice.get("current_tile_warp") or {}
        if current_tile_warp:
            lines.append(f"- Current-tile warp caution: {current_tile_warp.get('summary')}")

        frontier_guidance = advice.get("frontier_guidance", {}) or {}
        if frontier_guidance.get("prefer_leave_current_frontier"):
            lines.append(
                f"- Frontier caution: {frontier_guidance.get('summary')}"
            )

        warps = advice.get("known_warps", [])
        if warps:
            warp_text = ", ".join(
                f"({warp['src_x']},{warp['src_y']}) -> map {warp['dest_map']} ({warp['dest_x']},{warp['dest_y']})"
                for warp in warps
            )
            lines.append(f"- Known warp points on this map: {warp_text}")

        lines.append("- Local explored map window:")
        lines.extend(f"  {row}" for row in advice.get("local_map", []))
        return "\n".join(lines)

    def render_local_map(self, map_id: int, x: int, y: int, radius: int = 4) -> List[str]:
        """Render a small text map around the player."""
        explored = self.explored_tiles.get(map_id, set())
        frontiers = {
            item["position"] for item in self.get_frontier_tiles(map_id, current_position=(x, y))
        }
        warp_positions = {
            (warp["src_x"], warp["src_y"]) for warp in self._get_map_warps(map_id)
        }

        rows: List[str] = []
        for py in range(y - radius, y + radius + 1):
            chars: List[str] = []
            for px in range(x - radius, x + radius + 1):
                pos = (px, py)
                if pos == (x, y):
                    chars.append("P")
                elif pos in warp_positions:
                    chars.append("W")
                elif pos in frontiers:
                    chars.append("F")
                elif pos in explored:
                    chars.append(".")
                else:
                    chars.append("?")
            rows.append("".join(chars))
        return rows

    def build_map_snapshot(
        self,
        map_id: int,
        current_position: Optional[Position] = None,
        *,
        padding: int = 2,
        max_width: int = 32,
        max_height: int = 24,
    ) -> Dict[str, Any]:
        """Build a bounded explored-map snapshot for UI and prompt consumption."""
        explored = set(self.explored_tiles.get(map_id, set()))
        current_position = current_position or (
            self.current_position if self.current_map == map_id else None
        )
        frontiers = {
            item["position"] for item in self.get_frontier_tiles(map_id, current_position=current_position)
        }
        warp_positions = {
            (warp["src_x"], warp["src_y"]) for warp in self._get_map_warps(map_id)
        }
        blocked_positions: Set[Position] = set()
        for pos, blocked in self.blocked_moves.get(map_id, {}).items():
            for direction, count in blocked.items():
                if int(count) < 2:
                    continue
                delta = self.CARDINALS.get(direction)
                if not delta:
                    continue
                blocked_pos = (pos[0] + delta[0], pos[1] + delta[1])
                if blocked_pos in explored or blocked_pos in warp_positions:
                    continue
                blocked_positions.add(blocked_pos)

        interesting = set(explored) | set(frontiers) | set(warp_positions) | set(blocked_positions)
        if current_position:
            interesting.add(current_position)

        if not interesting:
            return {
                "available": False,
                "map_id": map_id,
                "rows": [],
                "bounds": None,
                "player": None,
                "prompt_rows": [],
                "explored_count": 0,
                "frontier_count": 0,
                "blocked_count": 0,
                "warp_count": 0,
            }

        min_x = min(pos[0] for pos in interesting) - padding
        max_x = max(pos[0] for pos in interesting) + padding
        min_y = min(pos[1] for pos in interesting) - padding
        max_y = max(pos[1] for pos in interesting) + padding

        min_x, max_x = self._fit_bounds(min_x, max_x, max_width, current_position[0] if current_position else None)
        min_y, max_y = self._fit_bounds(min_y, max_y, max_height, current_position[1] if current_position else None)

        rows: List[str] = []
        for py in range(min_y, max_y + 1):
            chars: List[str] = []
            for px in range(min_x, max_x + 1):
                pos = (px, py)
                if current_position and pos == current_position:
                    chars.append("P")
                elif pos in warp_positions:
                    chars.append("W")
                elif pos in frontiers:
                    chars.append("F")
                elif pos in explored:
                    chars.append(".")
                elif pos in blocked_positions:
                    chars.append("#")
                else:
                    chars.append(" ")
            rows.append("".join(chars))

        return {
            "available": True,
            "map_id": map_id,
            "rows": rows,
            "prompt_rows": [row.replace(" ", "?") for row in rows],
            "bounds": {
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
                "width": max_x - min_x + 1,
                "height": max_y - min_y + 1,
            },
            "player": {
                "x": current_position[0],
                "y": current_position[1],
            } if current_position else None,
            "explored_count": len(explored),
            "frontier_count": len(frontiers),
            "blocked_count": len(blocked_positions),
            "warp_count": len(warp_positions),
            "legend": {
                " ": "unknown",
                ".": "explored",
                "F": "frontier",
                "#": "confirmed wall",
                "W": "warp",
                "P": "player",
            },
        }

    def _fit_bounds(
        self,
        minimum: int,
        maximum: int,
        limit: int,
        anchor: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Clamp a coordinate span to a maximum size while keeping the player in view."""
        if maximum < minimum:
            return minimum, maximum

        width = maximum - minimum + 1
        if width <= limit:
            return minimum, maximum

        if anchor is None:
            anchor = (minimum + maximum) // 2

        half = limit // 2
        new_min = max(minimum, min(anchor - half, maximum - limit + 1))
        new_max = new_min + limit - 1
        return new_min, new_max

    def get_exploration_status(self, map_id: int) -> Dict[str, Any]:
        """Get exploration statistics for a map."""
        explored = self.explored_tiles.get(map_id, set())
        nearby_unexplored: List[Position] = []
        navigation = None

        if self.current_map == map_id and self.current_position:
            nearby_unexplored = self.get_unexplored_adjacent(
                map_id,
                self.current_position[0],
                self.current_position[1],
                radius=5,
            )
            navigation = self.get_navigation_advice(
                map_id,
                self.current_position[0],
                self.current_position[1],
            )

        estimated_total = max(len(explored), 200)
        return {
            "map_id": map_id,
            "explored_count": len(explored),
            "total_tiles": estimated_total,
            "exploration_percent": len(explored) / estimated_total * 100 if estimated_total else 0.0,
            "nearby_unexplored": nearby_unexplored[:10],
            "frontier_count": len(self.get_frontier_tiles(map_id, current_position=self.current_position)),
            "navigation": navigation,
        }

    def get_all_explored_maps(self) -> List[int]:
        """Get list of all explored map IDs."""
        return list(self.explored_tiles.keys())

    def save(self, filepath: Optional[str] = None) -> None:
        """Save map memory to disk."""
        save_file = Path(filepath) if filepath else self.save_dir / "map_memory.json"
        save_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "explored_tiles": {
                str(map_id): [list(pos) for pos in sorted(tiles)]
                for map_id, tiles in self.explored_tiles.items()
            },
            "visit_counts": {
                str(map_id): {
                    self._position_key(pos): count
                    for pos, count in positions.items()
                }
                for map_id, positions in self.visit_counts.items()
            },
            "edges": {
                str(map_id): {
                    self._position_key(pos): {
                        direction: list(target)
                        for direction, target in directions.items()
                    }
                    for pos, directions in positions.items()
                }
                for map_id, positions in self.edges.items()
            },
            "blocked_moves": {
                str(map_id): {
                    self._position_key(pos): directions
                    for pos, directions in positions.items()
                    if directions
                }
                for map_id, positions in self.blocked_moves.items()
            },
            "warp_points": [
                {
                    "src_map": src[0],
                    "src_x": src[1],
                    "src_y": src[2],
                    "dest_map": dest["dest_map"],
                    "dest_x": dest["dest_x"],
                    "dest_y": dest["dest_y"],
                    "count": dest.get("count", 1),
                    "trigger_action": dest.get("trigger_action"),
                }
                for src, dest in self.warp_points.items()
            ],
            "map_properties": self.map_properties,
        }

        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.logger.debug(f"Saved map memory to {save_file}")

    def load(self, filepath: Optional[str] = None) -> None:
        """Load map memory from disk."""
        save_file = Path(filepath) if filepath else self.save_dir / "map_memory.json"
        if not save_file.exists():
            self.logger.info("No saved map memory found, starting fresh")
            return

        try:
            with open(save_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.explored_tiles = defaultdict(set)
            for map_id_str, tiles in data.get("explored_tiles", {}).items():
                map_id = int(map_id_str)
                self.explored_tiles[map_id] = {tuple(pos) for pos in tiles}

            self.visit_counts = defaultdict(lambda: defaultdict(int))
            for map_id_str, positions in data.get("visit_counts", {}).items():
                map_id = int(map_id_str)
                for pos_key, count in positions.items():
                    self.visit_counts[map_id][self._parse_position_key(pos_key)] = int(count)

            self.edges = defaultdict(lambda: defaultdict(dict))
            for map_id_str, positions in data.get("edges", {}).items():
                map_id = int(map_id_str)
                for pos_key, directions in positions.items():
                    pos = self._parse_position_key(pos_key)
                    self.edges[map_id][pos] = {
                        direction: tuple(target)
                        for direction, target in directions.items()
                    }

            self.blocked_moves = defaultdict(lambda: defaultdict(dict))
            for map_id_str, positions in data.get("blocked_moves", {}).items():
                map_id = int(map_id_str)
                for pos_key, directions in positions.items():
                    self.blocked_moves[map_id][self._parse_position_key(pos_key)] = {
                        direction: int(count)
                        for direction, count in directions.items()
                    }

            self.warp_points = {}
            for warp in data.get("warp_points", []):
                src = (
                    int(warp["src_map"]),
                    int(warp["src_x"]),
                    int(warp["src_y"]),
                )
                self.warp_points[src] = {
                    "dest_map": int(warp["dest_map"]),
                    "dest_x": int(warp["dest_x"]),
                    "dest_y": int(warp["dest_y"]),
                    "count": int(warp.get("count", 1)),
                }
                trigger_action = str(warp.get("trigger_action") or "").strip().lower()
                if trigger_action in self.CARDINALS:
                    self.warp_points[src]["trigger_action"] = trigger_action

            self.map_properties = data.get("map_properties", {})
            self.logger.info(f"Loaded map memory: {len(self.explored_tiles)} maps explored")
        except Exception as exc:
            self.logger.error(f"Failed to load map memory: {exc}")

    def reset_map(self, map_id: int) -> None:
        """Reset exploration for a specific map."""
        self.explored_tiles.pop(map_id, None)
        self.visit_counts.pop(map_id, None)
        self.edges.pop(map_id, None)
        self.blocked_moves.pop(map_id, None)
        self.map_properties.pop(map_id, None)
        self.warp_points = {
            src: dest for src, dest in self.warp_points.items() if src[0] != map_id
        }
        self.logger.info(f"Reset exploration for map {map_id}")

    def reset_all(self) -> None:
        """Reset all exploration data."""
        self.explored_tiles.clear()
        self.visit_counts.clear()
        self.edges.clear()
        self.blocked_moves.clear()
        self.warp_points.clear()
        self.map_properties.clear()
        self.logger.info("Reset all map memory")

    def _record_warp(
        self,
        src_map: int,
        src_pos: Position,
        dest_map: int,
        dest_pos: Position,
    ) -> None:
        """Record a known warp transition."""
        key = (src_map, src_pos[0], src_pos[1])
        existing = self.warp_points.get(key, {})
        self.warp_points[key] = {
            "dest_map": dest_map,
            "dest_x": dest_pos[0],
            "dest_y": dest_pos[1],
            "count": int(existing.get("count", 0)) + 1,
        }
        trigger_action = str(existing.get("trigger_action") or "").strip().lower()
        if trigger_action in self.CARDINALS:
            self.warp_points[key]["trigger_action"] = trigger_action

    def record_warp_trigger_action(
        self,
        src_map: int,
        x: int,
        y: int,
        action: str,
    ) -> None:
        """Remember which action on a source tile triggered a learned warp."""
        normalized = str(action or "").strip().lower()
        if normalized not in self.CARDINALS:
            return

        key = (int(src_map), int(x), int(y))
        existing = self.warp_points.get(key)
        if not existing:
            return

        existing["trigger_action"] = normalized

    def _get_map_warps(self, map_id: int) -> List[Dict[str, int]]:
        """Return known warps originating on a map."""
        warps: List[Dict[str, int]] = []
        for src, dest in self.warp_points.items():
            if src[0] != map_id:
                continue
            warps.append(
                {
                    "src_map": src[0],
                    "src_x": src[1],
                    "src_y": src[2],
                    "dest_map": int(dest["dest_map"]),
                    "dest_x": int(dest["dest_x"]),
                    "dest_y": int(dest["dest_y"]),
                    "count": int(dest.get("count", 1)),
                }
            )
            trigger_action = str(dest.get("trigger_action") or "").strip().lower()
            if trigger_action in self.CARDINALS:
                warps[-1]["trigger_action"] = trigger_action
        warps.sort(key=lambda item: (item["src_y"], item["src_x"], item["dest_map"]))
        return warps

    def _infer_direction(self, previous: Position, current: Position) -> Optional[str]:
        """Infer the movement direction between adjacent tiles."""
        dx = current[0] - previous[0]
        dy = current[1] - previous[1]
        for direction, delta in self.CARDINALS.items():
            if (dx, dy) == delta:
                return direction
        return None

    def _position_key(self, position: Position) -> str:
        """Serialize a position tuple."""
        return f"{position[0]},{position[1]}"

    def _parse_position_key(self, value: str) -> Position:
        """Deserialize a serialized position tuple."""
        x_str, y_str = value.split(",", 1)
        return int(x_str), int(y_str)
