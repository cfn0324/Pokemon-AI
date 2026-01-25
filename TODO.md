# TODO

- [ ] 启动时自动恢复最新检查点，同时保留手动选择入口。
- [ ] 在 `GameBoyEmulator.get_sprite_positions` 实现 OAM 精灵提取，用于 NPC/障碍感知。
- [ ] 卡死处理增强：结合 critic 反馈自动重规划，重置 stuck 检测并尝试替代路径/动作。
- [ ] 增加日志/检查点保留与清理策略（结合 `logging.log_dir`），可用脚本定期删除超量文件。
- [ ] 扩展自动化测试：为 agents/visualizer 提供最小冒烟或单测，补充关键路径覆盖。
