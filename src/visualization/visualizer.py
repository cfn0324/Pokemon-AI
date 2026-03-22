"""Real-time visualization server for Pokemon AI Agent."""

import io
import base64
import threading
import time
import zlib
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime
from flask import Flask, Response, jsonify, render_template, request
from flask_socketio import SocketIO
from PIL import Image

from ..utils.config import get_config
from ..utils.logger import get_logger


def make_json_serializable(obj):
    """将对象转换为JSON可序列化的格式

    处理numpy类型、datetime等特殊对象
    """
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()  # 转换numpy数字为Python原生类型
    elif isinstance(obj, np.ndarray):
        return obj.tolist()  # 转换numpy数组为列表
    elif isinstance(obj, np.bool_):
        return bool(obj)  # 转换numpy布尔值为Python布尔值
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        # 尝试转换为字符串
        try:
            return str(obj)
        except:
            return None


class GameVisualizer:
    """Real-time web-based visualizer for AI gameplay."""

    def __init__(self, port: int = 5000):
        """Initialize visualizer.

        Args:
            port: Port for web server
        """
        self.config = get_config()
        self.logger = get_logger('Visualizer')
        self.port = port
        self.update_screenshots = bool(
            self.config.get('visualization.update_screenshots', True)
        )
        max_fps = float(self.config.get('visualization.max_fps', 8) or 8)
        self.screenshot_min_interval = 0.0 if max_fps <= 0 else 1.0 / max_fps
        self.stream_enabled = bool(self.config.get('visualization.stream_enabled', True))
        self.stream_fps = float(self.config.get('visualization.stream_fps', 15) or 15)
        self.stream_scale = max(1, int(self.config.get('visualization.stream_scale', 3) or 3))
        self.stream_quality = max(30, min(95, int(self.config.get('visualization.stream_quality', 80) or 80)))
        self._last_screenshot_emit_at = 0.0
        self._last_screenshot_signature = None
        self._last_stream_signature = None
        self._stream_frame = None
        self._stream_frame_version = 0
        self._stream_condition = threading.Condition()
        self._stream_thread = None
        self.frame_source = None

        # Create Flask app
        self.app = Flask(__name__,
                         template_folder='../../templates',
                         static_folder='../../static')
        self.app.config['SECRET_KEY'] = 'pokemon-ai-secret'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Data storage
        self.current_state = {}
        self.latest_decision = {}
        self.latest_screenshot = None
        self.decision_history = []
        self.event_history = []
        self.goal_stack = []
        self.checkpoints = []
        self.exploration_data = {}
        self.control_handler = None
        self.control_state = {
            'running': False,
            'paused': False,
            'step_budget': 0,
            'manual_queue_size': 0,
            'last_command': '',
            'last_command_at': None,
            'last_error': None,
            'turn': 0,
        }

        # Setup routes
        self._setup_routes()

        # Server thread
        self.server_thread = None
        self.running = False

        self.logger.info(f"Visualizer initialized on port {port}")

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Main dashboard page."""
            return render_template('dashboard.html')

        @self.app.route('/api/state')
        def get_state():
            """Get current game state."""
            return jsonify(self.current_state)

        @self.app.route('/api/decision')
        def get_decision():
            """Get latest AI decision."""
            return jsonify(self.latest_decision)

        @self.app.route('/api/screenshot')
        def get_screenshot():
            """Get latest game screenshot."""
            if self.latest_screenshot:
                return jsonify({'image': self.latest_screenshot})
            return jsonify({'image': None})

        @self.app.route('/stream')
        @self.app.route('/stream.mjpg')
        def stream_screenshot():
            """Stream emulator frames as multipart images for smooth browser playback."""
            response = Response(
                self._stream_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame',
            )
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

        @self.app.route('/api/history')
        def get_history():
            """Get decision history."""
            return jsonify({
                'decisions': self.decision_history[-50:],  # Last 50 decisions
                'total': len(self.decision_history)
            })

        @self.app.route('/api/events')
        def get_events():
            """Get recent dashboard events."""
            return jsonify({
                'events': self.event_history[-100:],
                'total': len(self.event_history),
            })

        @self.app.route('/api/goals')
        def get_goals():
            """Get current goals."""
            return jsonify({'goals': self.goal_stack})

        @self.app.route('/api/control/state')
        def get_control_state():
            """Get current dashboard control state."""
            return jsonify(self._resolve_control_state())

        @self.app.route('/api/checkpoints')
        def get_checkpoints():
            """Get recent checkpoint summaries for the dashboard."""
            return jsonify({'checkpoints': self._resolve_checkpoints()})

        @self.app.route('/api/control', methods=['POST'])
        def post_control():
            """Handle dashboard control actions."""
            if not self.control_handler:
                return jsonify({
                    'ok': False,
                    'message': '当前未注册控制处理器',
                    'state': self.control_state,
                }), 503

            payload = request.get_json(silent=True) or {}
            command = payload.get('command')
            value = payload.get('value')
            result = self.control_handler.handle_visualizer_command(command, value)
            status_code = 200 if result.get('ok') else 400
            state = result.get('state')
            if isinstance(state, dict):
                self.update_control_state(state)
            checkpoints = result.get('checkpoints')
            if isinstance(checkpoints, list):
                self.update_checkpoints(checkpoints)
            return jsonify(result), status_code

    def set_control_handler(self, handler: Any) -> None:
        """Register the object that handles dashboard control commands."""
        self.control_handler = handler
        self.control_state = self._resolve_control_state()

    def set_frame_source(self, frame_source: Any) -> None:
        """Register the emulator-like object used for smooth frame streaming."""
        self.frame_source = frame_source

    def _resolve_control_state(self) -> Dict[str, Any]:
        """Read control state from the handler when available."""
        if self.control_handler and hasattr(self.control_handler, 'get_visualizer_control_state'):
            try:
                state = self.control_handler.get_visualizer_control_state()
                if isinstance(state, dict):
                    self.control_state = make_json_serializable(state)
            except Exception as exc:
                self.logger.warning(f"Failed to resolve control state: {exc}")
        return self.control_state

    def _resolve_checkpoints(self):
        """Read checkpoint summaries from the handler when available."""
        if self.control_handler and hasattr(self.control_handler, 'get_available_checkpoints'):
            try:
                checkpoints = self.control_handler.get_available_checkpoints()
                if isinstance(checkpoints, list):
                    self.checkpoints = make_json_serializable(checkpoints)
            except Exception as exc:
                self.logger.warning(f"Failed to resolve checkpoints: {exc}")
        return self.checkpoints

    def start(self):
        """Start visualization server in background thread."""
        if self.running:
            self.logger.warning("Visualizer already running")
            return

        self.running = True
        if self.stream_enabled and self.frame_source and not self._stream_thread:
            self._stream_thread = threading.Thread(
                target=self._capture_stream_frames,
                daemon=True,
            )
            self._stream_thread.start()
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.server_thread.start()
        self.logger.info(f"Visualizer server started on http://localhost:{self.port}")

    def _run_server(self):
        """Run Flask server."""
        try:
            self.socketio.run(self.app,
                            host='0.0.0.0',
                            port=self.port,
                            debug=False,
                            use_reloader=False,
                            allow_unsafe_werkzeug=True)
        except Exception as e:
            self.logger.error(f"Visualizer server error: {e}")

    def _encode_stream_image(self, image: Image.Image) -> bytes:
        """Encode a browser-friendly stream frame."""
        stream_image = image.convert("RGB")
        if self.stream_scale > 1:
            resample = (
                Image.Resampling.NEAREST
                if hasattr(Image, "Resampling")
                else Image.NEAREST
            )
            stream_image = stream_image.resize(
                (stream_image.width * self.stream_scale, stream_image.height * self.stream_scale),
                resample=resample,
            )

        buffered = io.BytesIO()
        stream_image.save(
            buffered,
            format="JPEG",
            quality=self.stream_quality,
            optimize=False,
        )
        return buffered.getvalue()

    def _publish_stream_frame(
        self,
        image: Image.Image,
        *,
        signature=None,
        force: bool = False,
    ) -> None:
        """Publish a new frame for the multipart stream."""
        if not self.stream_enabled or not image:
            return

        frame_signature = signature or self._get_image_signature(image)
        if not force and frame_signature == self._last_stream_signature:
            return

        frame_bytes = self._encode_stream_image(image)
        with self._stream_condition:
            self._stream_frame = frame_bytes
            self._stream_frame_version += 1
            self._stream_condition.notify_all()

        self._last_stream_signature = frame_signature

    def _capture_stream_frames(self) -> None:
        """Continuously sample the emulator framebuffer for smooth browser playback."""
        last_seen_frame_count = None
        interval = 1.0 / max(1.0, self.stream_fps)

        while self.running:
            if not self.frame_source:
                time.sleep(0.2)
                continue

            try:
                frame_count = getattr(self.frame_source, "frame_count", None)
                if self._stream_frame is not None and frame_count == last_seen_frame_count:
                    time.sleep(interval)
                    continue

                image = self.frame_source.get_screen_image()
                if image:
                    signature = self._get_image_signature(image)
                    self._publish_stream_frame(image, signature=signature)
                last_seen_frame_count = frame_count
            except Exception as exc:
                self.logger.debug(f"Stream capture tick failed: {exc}")
                time.sleep(0.2)
                continue

            time.sleep(interval)

    def _stream_frames(self):
        """Yield multipart frames to connected browsers."""
        last_version = -1

        while self.running:
            with self._stream_condition:
                if self._stream_frame_version == last_version:
                    self._stream_condition.wait(timeout=1.0)
                frame = self._stream_frame
                version = self._stream_frame_version

            if not frame or version == last_version:
                continue

            last_version = version
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                + frame
                + b"\r\n"
            )

    def update_state(self, state: Dict[str, Any]):
        """Update current game state.

        Args:
            state: Game state dict
        """
        # 清理数据以确保JSON可序列化
        self.current_state = make_json_serializable({
            'turn': state.get('turn', 0),
            'timestamp': datetime.now().isoformat(),
            'position': state.get('memory', {}).get('position', {}),
            'badges': state.get('memory', {}).get('badge_count', 0),
            'party_size': len(state.get('memory', {}).get('party', [])),
            'party': state.get('memory', {}).get('party', []),
            'money': state.get('memory', {}).get('money', 0),
            'in_battle': state.get('memory', {}).get('in_battle', False),
            'pre_world': state.get('pre_world', False),
            'pre_starter_script': state.get('pre_starter_script', False),
            'phase_hint': state.get('phase_hint'),
            'visual': state.get('visual', {}),
            'exploration': state.get('map_memory', {}),
            'navigation': state.get('navigation', {}),
            'deltas': state.get('deltas', {}),
        })

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('state_update', self.current_state)

    def update_decision(
        self,
        action: str,
        reasoning: str,
        turn: int,
        screen_type: Optional[str] = None,
        source: Optional[str] = None,
        trace: Optional[Any] = None,
    ):
        """Update latest AI decision.

        Args:
            action: Action taken
            reasoning: AI reasoning
            turn: Turn number
            screen_type: Model or harness classification of the current screen
            source: Decision source or stage name
            trace: Ordered stage trace from the decision engine
        """
        decision = {
            'turn': turn,
            'action': action,
            'reasoning': reasoning,
            'screen_type': screen_type,
            'source': source,
            'trace': make_json_serializable(trace),
            'timestamp': datetime.now().isoformat()
        }

        self.latest_decision = decision
        self.decision_history.append(decision)

        # Keep only last 1000 decisions in memory
        if len(self.decision_history) > 1000:
            self.decision_history = self.decision_history[-1000:]

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('decision_update', decision)

    def _get_image_signature(self, image: Image.Image):
        """Build a cheap in-memory signature for screenshot de-duplication."""
        rgb_image = image.convert("RGB")
        return (
            rgb_image.size,
            zlib.adler32(rgb_image.tobytes()),
        )

    def update_screenshot(self, image: Image.Image, force: bool = False):
        """Update game screenshot.

        Args:
            image: PIL Image of game screen
            force: Bypass de-duplication/throttling for interactive updates
        """
        if not image or not self.update_screenshots:
            return

        try:
            signature = self._get_image_signature(image)
            now = time.monotonic()

            if not force:
                if signature == self._last_screenshot_signature:
                    return
                if (
                    self.screenshot_min_interval > 0
                    and (now - self._last_screenshot_emit_at) < self.screenshot_min_interval
                ):
                    return

            # Convert PIL Image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            self.latest_screenshot = f"data:image/png;base64,{img_str}"
            self._last_screenshot_signature = signature
            self._last_screenshot_emit_at = now
            self._publish_stream_frame(image, signature=signature, force=force)

            # Broadcast to connected clients
            if self.running:
                self.socketio.emit('screenshot_update', {
                    'image': self.latest_screenshot
                })
        except Exception as e:
            self.logger.error(f"Error updating screenshot: {e}")

    def update_goals(self, goals):
        """Update current goals.

        Args:
            goals: Either dashboard-ready list items or a dict of goal types to descriptions
        """
        if isinstance(goals, list):
            self.goal_stack = [
                {
                    'type': item.get('type', 'goal'),
                    'description': item.get('description'),
                    'status': item.get('status', 'active'),
                }
                for item in goals
                if isinstance(item, dict) and item.get('description')
            ]
        else:
            self.goal_stack = [
                {'type': goal_type, 'description': description, 'status': 'active'}
                for goal_type, description in (goals or {}).items()
                if description
            ]

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('goals_update', {'goals': self.goal_stack})

    def update_control_state(self, state: Dict[str, Any]):
        """Update and broadcast dashboard control state."""
        self.control_state = make_json_serializable(state or {})
        if self.running:
            self.socketio.emit('control_state_update', self.control_state)

    def update_checkpoints(self, checkpoints):
        """Update and broadcast checkpoint summaries."""
        self.checkpoints = make_json_serializable(checkpoints or [])
        if self.running:
            self.socketio.emit('checkpoints_update', {'checkpoints': self.checkpoints})

    def update_exploration(self, exploration_data: Dict[str, Any]):
        """Update exploration data.

        Args:
            exploration_data: Exploration statistics
        """
        self.exploration_data = exploration_data

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('exploration_update', exploration_data)

    def log_event(self, event_type: str, message: str):
        """Log a special event.

        Args:
            event_type: Type of event (milestone, error, achievement, etc.)
            message: Event message
        """
        event = {
            'type': event_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }

        self.event_history.append(event)
        if len(self.event_history) > 500:
            self.event_history = self.event_history[-500:]

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('event', event)
            self.logger.info(f"Event [{event_type}]: {message}")

    def stop(self):
        """Stop visualization server."""
        self.running = False
        with self._stream_condition:
            self._stream_condition.notify_all()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=1.0)
        self._stream_thread = None
        self.logger.info("Visualizer stopped")
