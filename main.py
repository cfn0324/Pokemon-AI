"""宝可梦AI智能体的主入口点。"""

import os
import sys
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

# 从.env文件加载环境变量
from dotenv import load_dotenv
load_dotenv()

from src.utils.config import get_config
from src.utils.logger import get_logger
from src.emulator.game_boy import GameBoyEmulator
from src.emulator.memory_reader import MemoryReader
from src.state.game_state import GameState
from src.state.vision import VisionProcessor
from src.state.map_memory import MapMemory
from src.agents.main_agent import MainAgent
from src.agents.pathfinder import PathfinderAgent
from src.agents.puzzle_solver import PuzzleSolverAgent
from src.agents.critic import CriticAgent
from src.tools.action_executor import ActionExecutor
from src.tools.progress_tracker import ProgressTracker
from src.visualization.visualizer import GameVisualizer
from src.agents.async_decision import AsyncDecisionMaker


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

        # 初始化组件
        self._init_emulator()
        self._init_state_systems()
        self._init_agents()
        self._init_tools()

        # 运行时状态
        self.running = False
        self.turn_count = 0
        self.last_checkpoint_turn = 0

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
            self.map_memory
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

        self.action_executor = ActionExecutor(self.emulator)
        self.progress_tracker = ProgressTracker()

        # 初始化异步决策器以实现非阻塞AI
        self.async_ai = AsyncDecisionMaker(self.main_agent)
        if self.config.get('performance.async_decisions', True):
            self.async_ai.start()
            self.logger.info("异步AI决策已启用")

        # 初始化可视化器
        vis_port = self.config.get('visualization.port', 5000)
        self.visualizer = GameVisualizer(port=vis_port)

        # 如果启用则启动可视化器
        if self.config.get('visualization.enabled', True):
            self.visualizer.start()
            self.logger.info(f"可视化仪表板可访问：http://localhost:{vis_port}")

        self.logger.info("工具初始化完成")

    def run(self) -> None:
        """运行AI智能体。"""
        self.running = True
        self.logger.milestone("开始游戏")

        try:
            while self.running and self.emulator.is_running():
                self._game_loop_iteration()

        except KeyboardInterrupt:
            self.logger.info("被用户中断")
        except Exception as e:
            self.logger.error(f"致命错误: {e}", exc_info=True)
        finally:
            self._shutdown()

    def _game_loop_iteration(self) -> None:
        """游戏循环的单次迭代，使用异步AI以保持PyBoy响应。"""
        self.turn_count += 1

        # 更新游戏状态
        current_state = self.game_state.update()
        state_text = self.game_state.get_text_representation(current_state)

        # 使用当前状态更新可视化器
        if self.config.get('visualization.enabled', True):
            self.visualizer.update_state(current_state)
            # 每回合更新截图以实现实时显示
            screen_image = self.emulator.get_screen_image()
            self.visualizer.update_screenshot(screen_image)
            # 从主智能体更新目标
            if hasattr(self.main_agent, 'goal_manager') and self.main_agent.goal_manager:
                goals = self.main_agent.goal_manager.get_all_goals()
                self.visualizer.update_goals(goals)

        # 定期记录状态
        if self.turn_count % 10 == 0:
            self.logger.info(f"\n{state_text}")

        # 更新进度
        self.progress_tracker.update(self.turn_count, current_state)

        # 如果启用则保存截图
        if self.config.get('logging.save_screenshots') and self.turn_count % 50 == 0:
            self._save_screenshot()

        # 检查是否卡住
        if self.action_executor.is_stuck():
            self.logger.warning("智能体似乎卡住了 - 请求评论者评估")
            if self.config.get('visualization.enabled', True):
                self.visualizer.log_event('error', '智能体卡住 - 请求评论者评估')
            self._handle_stuck_state(current_state)
            self.action_executor.reset_stuck_detection()

        # 获取AI决策（使用异步支持以保持PyBoy响应）
        decision = self._get_ai_decision_responsive(current_state, state_text)

        # 使用决策更新可视化器
        if self.config.get('visualization.enabled', True):
            action = decision.get('action', 'wait')
            reasoning = decision.get('reasoning', '')
            self.visualizer.update_decision(action, reasoning, self.turn_count)

        # 执行行动
        action = decision.get('action', 'wait')
        success = self.action_executor.execute(action)

        if not success:
            self.logger.warning(f"行动失败: {action}")

        # 定期保存检查点
        checkpoint_interval = self.config.get('progress.checkpoint_interval', 100)
        if self.turn_count - self.last_checkpoint_turn >= checkpoint_interval:
            if self.config.get('visualization.enabled', True):
                self.visualizer.log_event('milestone', f'回合{self.turn_count}已保存检查点')
            self._save_checkpoint()
            self.last_checkpoint_turn = self.turn_count

        # Tick模拟器
        self.emulator.tick(10)

    def _get_ai_decision_responsive(self, current_state: dict, state_text: str) -> dict:
        """在保持PyBoy窗口响应的同时获取AI决策。

        参数:
            current_state: 当前游戏状态
            state_text: 状态的文本表示

        返回:
            包含行动和推理的决策字典
        """
        use_async = self.config.get('performance.async_decisions', True)

        if not use_async or not hasattr(self, 'async_ai'):
            # 回退到同步模式（会阻塞）
            return self.main_agent.decide_action(current_state, state_text)

        # 异步请求决策
        self.async_ai.request_decision(current_state, state_text)

        # 等待决策的同时保持PyBoy响应
        max_wait_time = 60.0  # 最多60秒
        start_time = time.time()
        tick_interval = 0.1  # 每100ms tick一次PyBoy

        while time.time() - start_time < max_wait_time:
            # 检查决策是否准备好
            decision = self.async_ai.get_decision(timeout=0.0)
            if decision:
                return decision

            # 通过tick保持PyBoy响应
            self.emulator.tick(6)  # 60fps时约100ms

            # 短暂休眠以防止CPU空转
            time.sleep(0.05)

        # 超时 - 返回等待行动
        self.logger.warning("AI决策超时 - 使用默认等待行动")
        return {'action': 'wait', 'reasoning': '决策超时'}


    def _handle_stuck_state(self, current_state: dict) -> None:
        """处理智能体卡住的情况。

        参数:
            current_state: 当前游戏状态
        """
        # 获取最近的行动历史
        history = self.action_executor.get_action_history(20)
        history_text = f"最近的行动: {', '.join(history)}"

        # 获取评论
        critique = self.critic.critique(history_text, current_state)

        self.logger.info(f"评论者评估: {critique['assessment']}")
        self.logger.info(f"评论者问题: {critique['issues']}")
        self.logger.info(f"评论者建议: {critique['suggestions']}")

        # 可以使用评论来调整策略
        # 目前只记录日志

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

        checkpoint_dir = Path(self.config.get('game.save_state_dir')) / f"checkpoint_{self.turn_count}"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # 保存模拟器状态
        self.emulator.save_state(str(checkpoint_dir / "emulator.state"))

        # 保存智能体状态
        self.main_agent.save_state(str(checkpoint_dir))

        # 保存地图记忆
        self.map_memory.save()

        # 保存进度
        self.progress_tracker.save(str(checkpoint_dir / "progress.json"))

        self.logger.info(f"检查点已保存到 {checkpoint_dir}")

        # 打印进度摘要
        self.logger.info("\n" + self.progress_tracker.get_progress_summary())

    def _signal_handler(self, sig, frame) -> None:
        """处理中断信号。"""
        self.logger.info("收到中断信号")
        self.running = False

    def _shutdown(self) -> None:
        """优雅地关闭。"""
        self.logger.info("正在关闭...")

        # 停止异步AI
        if hasattr(self, 'async_ai'):
            self.async_ai.stop()

        # 保存最终检查点
        self._save_checkpoint()

        # 停止可视化器
        if hasattr(self, 'visualizer'):
            self.visualizer.stop()

        # 停止模拟器
        self.emulator.stop()

        self.logger.milestone("宝可梦AI智能体已停止")
        self.logger.info(f"总回合数: {self.turn_count}")


def main():
    """主入口点。"""
    print("=" * 60)
    print("宝可梦AI智能体")
    print("由Claude (Anthropic)驱动")
    print("=" * 60)
    print()

    # 检查API密钥
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("错误: 未设置ANTHROPIC_API_KEY环境变量")
        print("请使用以下方式设置: export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)

    # 检查ROM
    if not os.path.exists('PokemonRed.gb'):
        print("错误: 当前目录未找到PokemonRed.gb")
        sys.exit(1)

    print("正在初始化...")
    print()

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
