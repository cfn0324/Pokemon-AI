"""Real-time visualization server for Pokemon AI Agent."""

import io
import json
import base64
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from PIL import Image

from ..utils.logger import get_logger


class GameVisualizer:
    """Real-time web-based visualizer for AI gameplay."""

    def __init__(self, port: int = 5000):
        """Initialize visualizer.

        Args:
            port: Port for web server
        """
        self.logger = get_logger('Visualizer')
        self.port = port

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
        self.goal_stack = []
        self.exploration_data = {}

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

        @self.app.route('/api/history')
        def get_history():
            """Get decision history."""
            return jsonify({
                'decisions': self.decision_history[-50:],  # Last 50 decisions
                'total': len(self.decision_history)
            })

        @self.app.route('/api/goals')
        def get_goals():
            """Get current goals."""
            return jsonify({'goals': self.goal_stack})

    def start(self):
        """Start visualization server in background thread."""
        if self.running:
            self.logger.warning("Visualizer already running")
            return

        self.running = True
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

    def update_state(self, state: Dict[str, Any]):
        """Update current game state.

        Args:
            state: Game state dict
        """
        self.current_state = {
            'turn': state.get('turn', 0),
            'timestamp': datetime.now().isoformat(),
            'position': state.get('memory', {}).get('position', {}),
            'badges': state.get('memory', {}).get('badge_count', 0),
            'party_size': len(state.get('memory', {}).get('party', [])),
            'party': state.get('memory', {}).get('party', []),
            'money': state.get('memory', {}).get('money', 0),
            'in_battle': state.get('memory', {}).get('in_battle', False),
            'visual': state.get('visual', {}),
            'exploration': state.get('map_memory', {}),
        }

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('state_update', self.current_state)

    def update_decision(self, action: str, reasoning: str, turn: int):
        """Update latest AI decision.

        Args:
            action: Action taken
            reasoning: AI reasoning
            turn: Turn number
        """
        decision = {
            'turn': turn,
            'action': action,
            'reasoning': reasoning,
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

    def update_screenshot(self, image: Image.Image):
        """Update game screenshot.

        Args:
            image: PIL Image of game screen
        """
        try:
            # Convert PIL Image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            self.latest_screenshot = f"data:image/png;base64,{img_str}"

            # Broadcast to connected clients
            if self.running:
                self.socketio.emit('screenshot_update', {
                    'image': self.latest_screenshot
                })
        except Exception as e:
            self.logger.error(f"Error updating screenshot: {e}")

    def update_goals(self, goals: Dict[str, str]):
        """Update current goals.

        Args:
            goals: Dict of goal types to descriptions
        """
        self.goal_stack = [
            {'type': goal_type, 'description': description}
            for goal_type, description in goals.items()
        ]

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('goals_update', {'goals': self.goal_stack})

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

        # Broadcast to connected clients
        if self.running:
            self.socketio.emit('event', event)
            self.logger.info(f"Event [{event_type}]: {message}")

    def stop(self):
        """Stop visualization server."""
        self.running = False
        self.logger.info("Visualizer stopped")
