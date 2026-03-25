"""增强的视觉处理系统 - 为AI决策提供详细的画面分析"""

from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageDraw
import numpy as np
from collections import Counter

from ..utils.logger import get_logger


class VisionProcessor:
    """处理游戏画面进行视觉理解 - 增强版"""

    # 网格覆盖设置
    GRID_SIZE = 16  # 宝可梦红版使用16x16图块
    SCREEN_WIDTH = 160
    SCREEN_HEIGHT = 144

    # 宝可梦红版调色板（Game Boy原生4色）
    # 实际颜色会因模拟器而异，这里使用常见的灰度值
    PALETTE_COLORS = {
        'white': (255, 255, 255),
        'light_gray': (192, 192, 192),
        'dark_gray': (96, 96, 96),
        'black': (0, 0, 0),
    }

    # 颜色范围定义（用于地形和对象识别）
    COLOR_RANGES = {
        'grass': {
            'lower': np.array([100, 150, 100]),  # 浅绿
            'upper': np.array([180, 255, 180])   # 深绿
        },
        'water': {
            'lower': np.array([100, 100, 150]),  # 浅蓝
            'upper': np.array([180, 180, 255])   # 深蓝
        },
        'building': {
            'lower': np.array([120, 100, 80]),   # 棕色/灰色
            'upper': np.array([180, 140, 120])
        },
        'road': {
            'lower': np.array([180, 180, 160]),  # 浅色路面
            'upper': np.array([230, 230, 220])
        },
        'dark': {
            'lower': np.array([0, 0, 0]),
            'upper': np.array([60, 60, 60])      # 深色区域
        },
        'light': {
            'lower': np.array([200, 200, 200]),
            'upper': np.array([255, 255, 255])   # 亮色区域
        }
    }

    def __init__(self):
        """初始化视觉处理器"""
        self.logger = get_logger('Vision')
        self.previous_frame = None  # 用于运动检测
        self.frame_counter = 0
        self.logger.info("增强视觉处理器已初始化")

    def analyze_screen(self, screen_image: Image.Image) -> Dict[str, Any]:
        """深度分析游戏画面

        参数:
            screen_image: PIL图像对象

        返回:
            包含详细视觉分析的字典
        """
        self.frame_counter += 1

        # 转换为numpy数组以便分析
        img_array = np.array(screen_image.convert('RGB'))

        # 多维度分析
        ui_elements = self._detect_ui_elements(img_array)
        terrain_info = self._analyze_terrain(img_array)
        objects = self._detect_objects(img_array)
        screen_type = self._identify_screen_type(img_array, ui_elements)
        color_analysis = self._analyze_colors(img_array)
        motion_info = self._detect_motion(img_array)
        navigation_hints = self._estimate_navigation_hints(img_array)

        # 生成详细描述
        description = self._generate_detailed_description(
            screen_type, ui_elements, terrain_info, objects, color_analysis
        )

        # 提取区域信息
        regions = self._divide_into_regions(img_array)

        # 保存当前帧用于下次运动检测
        self.previous_frame = img_array.copy()

        return {
            'screen_type': screen_type,
            'ui_elements': ui_elements,
            'terrain': terrain_info,
            'objects': objects,
            'color_distribution': color_analysis,
            'motion': motion_info,
            'navigation_hints': navigation_hints,
            'regions': regions,
            'description': description,
            'detailed_elements': self._format_elements_list(ui_elements, objects, terrain_info),
            'grid_position': (
                (self.SCREEN_WIDTH // 2) // self.GRID_SIZE,
                (self.SCREEN_HEIGHT // 2) // self.GRID_SIZE
            ),
            'screen_size': (screen_image.width, screen_image.height),
            'frame_number': self.frame_counter
        }

    def _identify_screen_type(self, img_array: np.ndarray, ui_elements: Dict) -> str:
        """识别当前屏幕类型"""
        # 战斗屏幕
        if ui_elements.get('battle_ui'):
            return 'battle'
        if ui_elements.get('options_menu'):
            return 'options_menu'
        if ui_elements.get('startup_menu'):
            return 'startup_menu'
        if ui_elements.get('naming_screen'):
            return 'naming_screen'

        # 对话屏幕
        if ui_elements.get('text_box') and not ui_elements.get('battle_ui'):
            return 'dialogue'

        # 菜单屏幕
        if ui_elements.get('menu_open'):
            if ui_elements.get('pokemon_menu'):
                return 'pokemon_menu'
            elif ui_elements.get('item_menu'):
                return 'item_menu'
            elif ui_elements.get('save_menu'):
                return 'save_menu'
            return 'menu'

        if ui_elements.get('title_screen'):
            return 'title'
        if self._is_startup_transition(img_array):
            return 'startup'

        # 文本输入/命名等全屏界面
        if ui_elements.get('text_entry'):
            return 'text_entry'

        # 标题屏幕（高对比度，简单布局）
        if self._is_title_screen(img_array):
            return 'title'

        # 室内场景
        if self._is_indoor(img_array):
            return 'indoor'

        # 默认为室外
        return 'overworld'

    def _detect_ui_elements(self, img_array: np.ndarray) -> Dict[str, bool]:
        """检测UI元素"""
        elements = {}
        h, w = img_array.shape[:2]
        white_ratio = self._calculate_color_ratio(img_array, 'light')
        dark_ratio = self._calculate_color_ratio(img_array, 'dark')
        border_row_count = self._count_full_width_dark_rows(img_array)

        # 检测文本框（底部深色区域）
        elements['menu_open'] = self._has_side_menu_box(img_array)
        elements['button_prompt'] = self._has_button_prompt(img_array)
        elements['hp_bars'] = self._detect_hp_bars(img_array)
        elements['options_menu'] = self._is_options_menu(
            img_array,
            white_ratio=white_ratio,
            dark_ratio=dark_ratio,
            border_row_count=border_row_count,
        )
        elements['startup_menu'] = self._is_startup_menu(
            img_array,
            white_ratio=white_ratio,
            dark_ratio=dark_ratio,
        )
        elements['title_screen'] = self._is_title_screen(
            img_array,
            white_ratio=white_ratio,
            border_row_count=border_row_count,
            button_prompt=elements['button_prompt'],
            side_menu_box=elements['menu_open'],
            hp_bars=elements['hp_bars'],
        )
        elements['naming_screen'] = self._is_naming_screen(
            img_array,
            white_ratio=white_ratio,
            border_row_count=border_row_count,
        )
        elements['menu_open'] = elements['menu_open'] or any(
            (
                elements['options_menu'],
                elements['startup_menu'],
                elements['title_screen'],
                elements['naming_screen'],
            )
        )

        bottom_region = img_array[int(h*0.7):, :, :]
        elements['text_box'] = self._has_text_box(
            bottom_region,
            full_img=img_array,
            border_row_count=border_row_count,
            options_menu=elements['options_menu'],
            startup_menu=elements['startup_menu'],
            title_screen=elements['title_screen'],
            naming_screen=elements['naming_screen'],
        )

        # 检测战斗UI（HP条、战斗菜单）
        elements['battle_ui'] = self._has_battle_ui(img_array)

        # 检测命名/文本输入屏（高白底 + 高文字密度）
        elements['text_entry'] = (
            self._is_text_entry_screen(img_array, white_ratio=white_ratio)
            and not elements['text_box']
            and not elements['battle_ui']
            and not elements['options_menu']
            and not elements['startup_menu']
            and not elements['title_screen']
            and not elements['naming_screen']
        )

        # 检测HP条
        elements['hp_bars'] = self._detect_hp_bars(img_array)

        # 检测特定菜单类型
        if elements['menu_open']:
            elements['pokemon_menu'] = self._is_pokemon_menu(img_array)
            elements['item_menu'] = self._is_item_menu(img_array)
            elements['save_menu'] = self._is_save_menu(img_array)

        return elements

    def _is_text_entry_screen(self, img_array: np.ndarray, white_ratio: Optional[float] = None) -> bool:
        """判断是否为“命名/文本输入”全屏界面。

        该类界面通常几乎全屏为白底，并在中部区域出现密集的字符/选项网格。
        使用“整体白底占比 + 中部深色像素密度”的轻量特征，避免把普通底部对话框误判为文本输入屏。
        """
        if white_ratio is None:
            white_ratio = self._calculate_color_ratio(img_array, 'light')

        # 命名界面几乎为“全屏白”，阈值故意设高以规避普通对话框
        if white_ratio < 0.86:
            return False

        dark_ratio = self._calculate_color_ratio(img_array, 'dark')
        if dark_ratio < 0.015:
            return False

        h, w = img_array.shape[:2]
        center = img_array[int(h * 0.25): int(h * 0.85), int(w * 0.05): int(w * 0.95), :]
        center_dark = self._calculate_color_ratio(center, 'dark')
        top = img_array[: int(h * 0.18), :, :]
        top_light = self._calculate_color_ratio(top, 'light')
        bottom = img_array[int(h * 0.75):, :, :]
        bottom_dark = self._calculate_color_ratio(bottom, 'dark')

        return center_dark > 0.04 and top_light > 0.80 and bottom_dark < 0.18

    def _analyze_terrain(self, img_array: np.ndarray) -> Dict[str, Any]:
        """分析地形构成"""
        terrain = {}

        # 计算各种地形的占比
        terrain['grass_coverage'] = self._calculate_color_ratio(img_array, 'grass')
        terrain['water_coverage'] = self._calculate_color_ratio(img_array, 'water')
        terrain['building_coverage'] = self._calculate_color_ratio(img_array, 'building')
        terrain['road_coverage'] = self._calculate_color_ratio(img_array, 'road')

        # 判断主要地形类型
        max_terrain = max(terrain.items(), key=lambda x: x[1])
        terrain['primary_terrain'] = max_terrain[0].replace('_coverage', '') if max_terrain[1] > 0.2 else 'mixed'

        # 检测边界（墙壁、栅栏等）
        terrain['has_boundaries'] = self._detect_boundaries(img_array)

        # 检测可通行区域
        terrain['walkable_areas'] = self._estimate_walkable_areas(img_array)

        return terrain

    def _detect_objects(self, img_array: np.ndarray) -> List[Dict[str, Any]]:
        """检测画面中的对象"""
        objects = []
        h, w = img_array.shape[:2]

        # 检测NPC（通过颜色聚类和形状）
        npcs = self._detect_npcs(img_array)
        objects.extend(npcs)

        # 检测可交互对象
        interactables = self._detect_interactables(img_array)
        objects.extend(interactables)

        # 检测玩家角色（通常在屏幕中心）
        player = self._detect_player(img_array)
        if player:
            objects.append(player)

        # 检测门
        doors = self._detect_doors(img_array)
        objects.extend(doors)

        # 检测物品球（红色圆形对象）
        items = self._detect_items(img_array)
        objects.extend(items)

        return objects

    def _estimate_navigation_hints(self, img_array: np.ndarray) -> Dict[str, Any]:
        """Estimate which movement directions look visually blocked."""
        player_box = self._estimate_player_bbox(img_array)
        if not player_box:
            return self._estimate_navigation_hints_from_view(img_array)

        px = int((player_box["x1"] + player_box["x2"]) / 2)
        py = int((player_box["y1"] + player_box["y2"]) / 2)
        directions = {
            "up": (0, -self.GRID_SIZE),
            "down": (0, self.GRID_SIZE),
            "left": (-self.GRID_SIZE, 0),
            "right": (self.GRID_SIZE, 0),
        }

        analyses: Dict[str, Dict[str, float]] = {}
        walkable: List[Tuple[str, float]] = []
        blocked: List[str] = []

        for direction, (dx, dy) in directions.items():
            sample = self._sample_square(img_array, px + dx, py + dy, radius=6)
            far_sample = self._sample_square(img_array, px + (dx * 2), py + (dy * 2), radius=6)
            if sample.size == 0:
                blocked.append(direction)
                analyses[direction] = {"void_ratio": 1.0, "score": -1.0}
                continue

            grayscale = np.mean(sample, axis=2)
            void_ratio = float(np.mean(grayscale < 16))
            dark_ratio = float(np.mean(grayscale < 48))
            contrast = float(np.std(grayscale)) / 255.0
            far_void_ratio = float(np.mean(np.mean(far_sample, axis=2) < 16)) if far_sample.size else 1.0
            far_dark_ratio = float(np.mean(np.mean(far_sample, axis=2) < 48)) if far_sample.size else 1.0
            combined_void_ratio = (void_ratio * 0.6) + (far_void_ratio * 0.4)
            combined_dark_ratio = (dark_ratio * 0.6) + (far_dark_ratio * 0.4)
            score = (1.0 - combined_void_ratio) + contrast - (combined_dark_ratio * 0.35)

            analyses[direction] = {
                "void_ratio": round(void_ratio, 3),
                "far_void_ratio": round(far_void_ratio, 3),
                "combined_void_ratio": round(combined_void_ratio, 3),
                "dark_ratio": round(dark_ratio, 3),
                "contrast": round(contrast, 3),
                "score": round(score, 3),
            }

            if combined_void_ratio > 0.45 or (combined_void_ratio > 0.3 and contrast < 0.08):
                blocked.append(direction)
            else:
                walkable.append((direction, score))

        walkable.sort(key=lambda item: item[1], reverse=True)
        unsafe = [
            direction
            for direction, values in analyses.items()
            if direction not in blocked and float(values.get("combined_void_ratio", values.get("void_ratio", 0.0))) >= 0.30
        ]

        return {
            "available": True,
            "player_box": player_box,
            "blocked_directions": blocked,
            "unsafe_directions": unsafe,
            "walkable_directions": [direction for direction, _ in walkable],
            "direction_scores": {direction: score for direction, score in walkable},
            "raw_direction_analysis": analyses,
        }

    def _estimate_navigation_hints_from_view(self, img_array: np.ndarray) -> Dict[str, Any]:
        """Fallback navigation hints using screen-center directional sectors."""
        h, w = img_array.shape[:2]
        cx = w // 2
        cy = h // 2
        sectors = {
            "up": img_array[max(0, cy - 20):cy, max(0, cx - 18):min(w, cx + 18)],
            "down": img_array[cy:min(h, cy + 28), max(0, cx - 18):min(w, cx + 18)],
            "left": img_array[max(0, cy - 18):min(h, cy + 18), max(0, cx - 28):cx],
            "right": img_array[max(0, cy - 18):min(h, cy + 18), cx:min(w, cx + 28)],
        }

        analyses: Dict[str, Dict[str, float]] = {}
        walkable: List[Tuple[str, float]] = []
        blocked: List[str] = []

        for direction, sample in sectors.items():
            grayscale = np.mean(sample, axis=2)
            void_ratio = float(np.mean(grayscale < 16))
            dark_ratio = float(np.mean(grayscale < 48))
            contrast = float(np.std(grayscale)) / 255.0
            if direction == "up":
                far_sample = img_array[max(0, cy - 36):max(0, cy - 12), max(0, cx - 16):min(w, cx + 16)]
            elif direction == "down":
                far_sample = img_array[min(h, cy + 12):min(h, cy + 40), max(0, cx - 16):min(w, cx + 16)]
            elif direction == "left":
                far_sample = img_array[max(0, cy - 16):min(h, cy + 16), max(0, cx - 40):max(0, cx - 12)]
            else:
                far_sample = img_array[max(0, cy - 16):min(h, cy + 16), min(w, cx + 12):min(w, cx + 40)]

            far_gray = np.mean(far_sample, axis=2) if far_sample.size else np.zeros((1, 1))
            far_void_ratio = float(np.mean(far_gray < 16)) if far_sample.size else 1.0
            far_dark_ratio = float(np.mean(far_gray < 48)) if far_sample.size else 1.0
            combined_void_ratio = (void_ratio * 0.6) + (far_void_ratio * 0.4)
            combined_dark_ratio = (dark_ratio * 0.6) + (far_dark_ratio * 0.4)
            score = (1.0 - combined_void_ratio) + contrast - (combined_dark_ratio * 0.25)
            analyses[direction] = {
                "void_ratio": round(void_ratio, 3),
                "far_void_ratio": round(far_void_ratio, 3),
                "combined_void_ratio": round(combined_void_ratio, 3),
                "dark_ratio": round(dark_ratio, 3),
                "contrast": round(contrast, 3),
                "score": round(score, 3),
            }

            if combined_void_ratio > 0.58:
                blocked.append(direction)
            else:
                walkable.append((direction, score))

        walkable.sort(key=lambda item: item[1], reverse=True)
        unsafe = [
            direction
            for direction, values in analyses.items()
            if direction not in blocked and float(values.get("combined_void_ratio", values.get("void_ratio", 0.0))) >= 0.30
        ]
        return {
            "available": True,
            "player_box": None,
            "blocked_directions": blocked,
            "unsafe_directions": unsafe,
            "walkable_directions": [direction for direction, _ in walkable],
            "direction_scores": {direction: score for direction, score in walkable},
            "raw_direction_analysis": analyses,
        }

    def _estimate_player_bbox(self, img_array: np.ndarray) -> Optional[Dict[str, int]]:
        """Estimate the player's on-screen bounding box from dark connected components."""
        grayscale = np.mean(img_array, axis=2)
        h, w = grayscale.shape
        search_mask = np.zeros((h, w), dtype=bool)
        search_mask[int(h * 0.2):int(h * 0.82), int(w * 0.18):int(w * 0.82)] = True
        dark_mask = (grayscale < 140) & (grayscale > 8) & search_mask

        best_box: Optional[Dict[str, int]] = None
        best_score = float("-inf")
        anchor_x = w * 0.45
        anchor_y = h * 0.58

        for component in self._connected_components(dark_mask):
            area = len(component)
            if area < 35 or area > 260:
                continue

            ys = [pos[0] for pos in component]
            xs = [pos[1] for pos in component]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            box_w = x2 - x1 + 1
            box_h = y2 - y1 + 1

            if box_w < 6 or box_w > 20 or box_h < 8 or box_h > 24:
                continue

            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            distance_penalty = abs(center_x - anchor_x) + abs(center_y - anchor_y)
            box = grayscale[y1:y2 + 1, x1:x2 + 1]
            contrast_bonus = float(np.std(box)) / 255.0
            score = contrast_bonus + (area / 220.0) - (distance_penalty / 120.0)

            if score > best_score:
                best_score = score
                best_box = {
                    "x1": int(x1),
                    "y1": int(y1),
                    "x2": int(x2),
                    "y2": int(y2),
                }

        return best_box

    def _connected_components(self, mask: np.ndarray) -> List[List[Tuple[int, int]]]:
        """Return 4-connected components for a boolean mask."""
        h, w = mask.shape
        visited = np.zeros((h, w), dtype=bool)
        components: List[List[Tuple[int, int]]] = []

        for y in range(h):
            for x in range(w):
                if not mask[y, x] or visited[y, x]:
                    continue

                stack = [(y, x)]
                visited[y, x] = True
                component: List[Tuple[int, int]] = []

                while stack:
                    cy, cx = stack.pop()
                    component.append((cy, cx))
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))

                components.append(component)

        return components

    def _sample_square(
        self,
        img_array: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int = 6,
    ) -> np.ndarray:
        """Sample a square around a pixel center."""
        h, w = img_array.shape[:2]
        x1 = max(0, center_x - radius)
        x2 = min(w, center_x + radius + 1)
        y1 = max(0, center_y - radius)
        y2 = min(h, center_y + radius + 1)
        return img_array[y1:y2, x1:x2]

    def _analyze_colors(self, img_array: np.ndarray) -> Dict[str, float]:
        """分析颜色分布"""
        # 计算主要颜色占比
        total_pixels = img_array.shape[0] * img_array.shape[1]

        color_dist = {}
        for color_name in self.COLOR_RANGES.keys():
            ratio = self._calculate_color_ratio(img_array, color_name)
            if ratio > 0.05:  # 只记录超过5%的颜色
                color_dist[color_name] = round(ratio, 3)

        # 计算平均亮度
        grayscale = np.mean(img_array, axis=2)
        color_dist['avg_brightness'] = round(float(np.mean(grayscale)) / 255, 3)

        # 计算对比度
        color_dist['contrast'] = round(float(np.std(grayscale)) / 255, 3)

        return color_dist

    def _detect_motion(self, current_frame: np.ndarray) -> Dict[str, Any]:
        """检测画面运动"""
        if self.previous_frame is None:
            return {'movement_detected': False, 'change_amount': 0.0}

        # 计算帧差
        diff = np.abs(current_frame.astype(float) - self.previous_frame.astype(float))
        change_amount = float(np.mean(diff)) / 255

        return {
            'movement_detected': change_amount > 0.1,
            'change_amount': round(change_amount, 3),
            'significant_change': change_amount > 0.3  # 场景切换
        }

    def _divide_into_regions(self, img_array: np.ndarray) -> Dict[str, Dict]:
        """将画面分为9个区域分析"""
        h, w = img_array.shape[:2]
        regions = {}

        region_names = [
            ['top_left', 'top_center', 'top_right'],
            ['mid_left', 'center', 'mid_right'],
            ['bottom_left', 'bottom_center', 'bottom_right']
        ]

        for i in range(3):
            for j in range(3):
                y_start = i * h // 3
                y_end = (i + 1) * h // 3
                x_start = j * w // 3
                x_end = (j + 1) * w // 3

                region = img_array[y_start:y_end, x_start:x_end]
                region_name = region_names[i][j]

                regions[region_name] = {
                    'avg_brightness': round(float(np.mean(region)) / 255, 2),
                    'has_content': np.std(region) > 20,  # 有内容的区域变化较大
                    'is_dark': np.mean(region) < 80
                }

        return regions

    def _generate_detailed_description(
        self,
        screen_type: str,
        ui_elements: Dict,
        terrain: Dict,
        objects: List[Dict],
        colors: Dict
    ) -> str:
        """生成详细的画面描述"""
        parts = []

        # 屏幕类型
        type_descriptions = {
            'battle': '战斗画面',
            'dialogue': '对话场景',
            'naming_screen': 'naming screen',
            'startup_menu': 'startup menu',
            'options_menu': 'options menu',
            'menu': '菜单界面',
            'pokemon_menu': '宝可梦菜单',
            'item_menu': '物品菜单',
            'title': '标题画面',
            'indoor': '室内场景',
            'overworld': '室外地图'
        }
        parts.append(type_descriptions.get(screen_type, '未知场景'))

        # UI元素
        if ui_elements.get('text_box'):
            parts.append('显示对话框')
        if ui_elements.get('naming_screen'):
            parts.append('naming keyboard visible')
        if ui_elements.get('startup_menu'):
            parts.append('startup menu visible')
        if ui_elements.get('options_menu'):
            parts.append('options menu visible')
        if ui_elements.get('battle_ui'):
            parts.append('战斗界面激活')
        if ui_elements.get('hp_bars'):
            parts.append('可见HP条')

        # 地形信息
        if terrain.get('primary_terrain') and screen_type == 'overworld':
            terrain_desc = {
                'grass': '草地为主',
                'water': '水域为主',
                'building': '建筑区域',
                'road': '道路',
                'mixed': '混合地形'
            }
            parts.append(terrain_desc.get(terrain['primary_terrain'], ''))

        # 对象
        if objects:
            obj_types = [obj['type'] for obj in objects]
            obj_counter = Counter(obj_types)
            for obj_type, count in obj_counter.items():
                obj_names = {
                    'player': '玩家角色',
                    'npc': 'NPC',
                    'door': '门',
                    'item': '物品',
                    'sign': '标志'
                }
                if obj_type in obj_names:
                    parts.append(f"{count}个{obj_names[obj_type]}")

        # 环境亮度
        brightness = colors.get('avg_brightness', 0.5)
        if brightness < 0.3:
            parts.append('昏暗环境')
        elif brightness > 0.7:
            parts.append('明亮环境')

        return '，'.join(parts)

    def _format_elements_list(
        self,
        ui_elements: Dict,
        objects: List[Dict],
        terrain: Dict
    ) -> List[str]:
        """格式化元素列表供Web界面显示"""
        elements = []

        # UI元素
        if ui_elements.get('text_box'):
            elements.append('对话框')
        if ui_elements.get('naming_screen'):
            elements.append('naming screen')
        if ui_elements.get('startup_menu'):
            elements.append('startup menu')
        if ui_elements.get('options_menu'):
            elements.append('options menu')
        if ui_elements.get('menu_open'):
            elements.append('菜单')
        if ui_elements.get('battle_ui'):
            elements.append('战斗UI')

        # 地形
        if terrain.get('primary_terrain') != 'mixed':
            elements.append(f"地形:{terrain['primary_terrain']}")

        # 对象
        for obj in objects[:5]:  # 最多显示5个对象
            elements.append(obj['type'])

        return elements if elements else ['无特殊元素']

    # ===== 辅助检测方法 =====

    def _calculate_color_ratio(self, img_array: np.ndarray, color_name: str) -> float:
        """计算特定颜色范围的像素占比"""
        if color_name not in self.COLOR_RANGES:
            return 0.0

        lower = self.COLOR_RANGES[color_name]['lower']
        upper = self.COLOR_RANGES[color_name]['upper']

        mask = np.all((img_array >= lower) & (img_array <= upper), axis=2)
        ratio = np.sum(mask) / (img_array.shape[0] * img_array.shape[1])
        return float(ratio)

    def _has_text_box(
        self,
        region: np.ndarray,
        full_img: Optional[np.ndarray] = None,
        border_row_count: Optional[int] = None,
        options_menu: bool = False,
        startup_menu: bool = False,
        title_screen: bool = False,
        naming_screen: bool = False,
    ) -> bool:
        """检测是否有文本框"""
        if options_menu or startup_menu or title_screen or naming_screen:
            return False

        # Pokémon 红版的对话框通常是底部的浅色（白底）矩形区域，
        # 带有黑色边框与深色文字；因此应同时满足“浅色占比较高 + 有一定深色像素”。
        light_ratio = self._calculate_color_ratio(region, "light")
        dark_ratio = self._calculate_color_ratio(region, "dark")
        if border_row_count is None and full_img is not None:
            border_row_count = self._count_full_width_dark_rows(full_img)
        if border_row_count is not None and not (4 <= border_row_count <= 8):
            return False
        return light_ratio > 0.25 and dark_ratio > 0.02

    def _has_battle_ui(self, img_array: np.ndarray) -> bool:
        """检测战斗UI"""
        h, w = img_array.shape[:2]

        # 检查底部是否有HP条区域（通常有特定的布局）
        bottom_third = img_array[int(h*0.66):, :, :]

        # 战斗界面底部有菜单选项
        dark_ratio = self._calculate_color_ratio(bottom_third, 'dark')
        light_ratio = self._calculate_color_ratio(bottom_third, 'light')

        # 战斗界面有明显的明暗对比
        return (dark_ratio > 0.2 and light_ratio > 0.2 and
                dark_ratio + light_ratio > 0.6)

    def _detect_hp_bars(self, img_array: np.ndarray) -> bool:
        """检测HP条"""
        h, w = img_array.shape[:2]
        top_region = img_array[:int(h*0.4), :, :]

        # HP条通常是水平的细长矩形
        # 简化检测：查找水平线条特征
        gray = np.mean(top_region, axis=2)

        # 检测水平边缘
        horizontal_edges = np.abs(np.diff(gray, axis=0))
        return np.max(horizontal_edges) > 50

    def _has_button_prompt(self, img_array: np.ndarray) -> bool:
        """检测按钮提示（如↓箭头）"""
        h, w = img_array.shape[:2]
        bottom_corner = img_array[int(h*0.85):, int(w*0.85):, :]

        # 按钮提示通常在右下角
        variance = np.var(bottom_corner)
        return variance > 500  # 有图案

    def _has_side_menu_box(self, img_array: np.ndarray) -> bool:
        """Detect a compact right-side menu box such as the Gen 1 START menu."""
        h, w = img_array.shape[:2]
        top = int(h * 0.04)
        bottom = int(h * 0.84)
        left = int(w * 0.56)
        right = int(w * 0.97)
        if bottom - top < 12 or right - left < 12:
            return False

        box = img_array[top:bottom, left:right, :]
        border = 2
        inner = box[border:-border, border:-border, :]
        if inner.size == 0:
            return False

        top_band = box[:border, :, :]
        bottom_band = box[-border:, :, :]
        left_band = box[:, :border, :]
        right_band = box[:, -border:, :]

        top_dark = self._calculate_color_ratio(top_band, 'dark')
        right_dark = self._calculate_color_ratio(right_band, 'dark')
        inner_light = self._calculate_color_ratio(inner, 'light')
        inner_dark = self._calculate_color_ratio(inner, 'dark')
        return top_dark > 0.35 and right_dark > 0.30 and inner_light > 0.80 and inner_dark < 0.18

    def _count_full_width_dark_rows(self, img_array: np.ndarray, threshold: float = 0.7) -> int:
        """Count rows that look like full-width menu borders."""
        gray = np.mean(img_array, axis=2)
        row_dark = np.mean(gray < 60, axis=1)
        return int(np.sum(row_dark > threshold))

    def _is_options_menu(
        self,
        img_array: np.ndarray,
        white_ratio: Optional[float] = None,
        dark_ratio: Optional[float] = None,
        border_row_count: Optional[int] = None,
    ) -> bool:
        """Detect the full-screen Pokemon options page."""
        if white_ratio is None:
            white_ratio = self._calculate_color_ratio(img_array, 'light')
        if dark_ratio is None:
            dark_ratio = self._calculate_color_ratio(img_array, 'dark')
        if border_row_count is None:
            border_row_count = self._count_full_width_dark_rows(img_array)

        if white_ratio < 0.6 or dark_ratio < 0.12:
            return False
        if border_row_count < 12:
            return False

        h = img_array.shape[0]
        upper = img_array[:int(h * 0.82), :, :]
        bottom = img_array[int(h * 0.75):, :, :]
        upper_dark = self._calculate_color_ratio(upper, 'dark')
        bottom_dark = self._calculate_color_ratio(bottom, 'dark')
        return upper_dark > 0.14 and bottom_dark < 0.18

    def _is_startup_menu(
        self,
        img_array: np.ndarray,
        white_ratio: Optional[float] = None,
        dark_ratio: Optional[float] = None,
    ) -> bool:
        """Detect the small NEW GAME / OPTION pre-game menu."""
        if white_ratio is None:
            white_ratio = self._calculate_color_ratio(img_array, 'light')
        if dark_ratio is None:
            dark_ratio = self._calculate_color_ratio(img_array, 'dark')

        if white_ratio < 0.90 or not (0.02 <= dark_ratio <= 0.12):
            return False

        h, w = img_array.shape[:2]
        top_left = img_array[:int(h * 0.30), :int(w * 0.45), :]
        rest = img_array[int(h * 0.30):, int(w * 0.45):, :]
        bottom = img_array[int(h * 0.65):, :, :]

        top_left_dark = self._calculate_color_ratio(top_left, 'dark')
        rest_dark = self._calculate_color_ratio(rest, 'dark')
        bottom_dark = self._calculate_color_ratio(bottom, 'dark')
        return top_left_dark > 0.12 and rest_dark < 0.03 and bottom_dark < 0.02

    def _is_naming_screen(
        self,
        img_array: np.ndarray,
        white_ratio: Optional[float] = None,
        border_row_count: Optional[int] = None,
    ) -> bool:
        """Detect the Gen 1 naming keyboard screen."""
        if white_ratio is None:
            white_ratio = self._calculate_color_ratio(img_array, 'light')
        if border_row_count is None:
            border_row_count = self._count_full_width_dark_rows(img_array)

        if white_ratio < 0.78 or not (4 <= border_row_count <= 8):
            return False

        h = img_array.shape[0]
        top = img_array[:int(h * 0.22), :, :]
        middle = img_array[int(h * 0.22):int(h * 0.75), :, :]
        bottom = img_array[int(h * 0.75):, :, :]

        top_dark = self._calculate_color_ratio(top, 'dark')
        middle_dark = self._calculate_color_ratio(middle, 'dark')
        bottom_dark = self._calculate_color_ratio(bottom, 'dark')
        middle_gray = np.mean(middle, axis=2)
        dark_columns = int(np.sum(np.mean(middle_gray < 60, axis=0) > 0.08))

        return (
            top_dark > 0.03
            and middle_dark > 0.09
            and 0.08 < bottom_dark < 0.18
            and dark_columns > 45
        )

    def _is_title_screen(
        self,
        img_array: np.ndarray,
        white_ratio: Optional[float] = None,
        border_row_count: Optional[int] = None,
        button_prompt: Optional[bool] = None,
        side_menu_box: Optional[bool] = None,
        hp_bars: Optional[bool] = None,
    ) -> bool:
        """检测标题画面"""
        if white_ratio is None:
            white_ratio = self._calculate_color_ratio(img_array, 'light')
        if border_row_count is None:
            border_row_count = self._count_full_width_dark_rows(img_array)
        if button_prompt is None:
            button_prompt = self._has_button_prompt(img_array)
        if side_menu_box is None:
            side_menu_box = self._has_side_menu_box(img_array)
        if hp_bars is None:
            hp_bars = self._detect_hp_bars(img_array)

        if hp_bars or side_menu_box or border_row_count >= 4 or not button_prompt:
            return False
        if not (0.60 <= white_ratio <= 0.88):
            return False

        # 标题画面通常有高对比度和简单布局
        contrast = np.std(img_array) / 255

        # 检查中心区域是否有大量亮色（标题文字）
        h, w = img_array.shape[:2]
        center = img_array[int(h*0.3):int(h*0.7), int(w*0.2):int(w*0.8), :]
        light_ratio = self._calculate_color_ratio(center, 'light')

        return contrast > 0.18 and light_ratio > 0.4

    def _is_startup_transition(
        self,
        img_array: np.ndarray,
        white_ratio: Optional[float] = None,
        dark_ratio: Optional[float] = None,
    ) -> bool:
        """Detect the nearly blank boot transition between title and menu."""
        if white_ratio is None:
            white_ratio = self._calculate_color_ratio(img_array, 'light')
        if dark_ratio is None:
            dark_ratio = self._calculate_color_ratio(img_array, 'dark')

        if white_ratio < 0.97 or dark_ratio > 0.01:
            return False

        contrast = np.std(img_array) / 255
        return contrast < 0.035

    def _is_indoor(self, img_array: np.ndarray) -> bool:
        """检测室内场景"""
        # 室内通常有较多的建筑材质和较暗的环境
        building_ratio = self._calculate_color_ratio(img_array, 'building')
        dark_ratio = self._calculate_color_ratio(img_array, 'dark')
        avg_brightness = np.mean(img_array) / 255

        return (building_ratio > 0.3 or dark_ratio > 0.3) and avg_brightness < 0.6

    def _is_pokemon_menu(self, img_array: np.ndarray) -> bool:
        """检测宝可梦菜单"""
        # 简化检测：检查是否有多个分隔的区域（宝可梦列表）
        gray = np.mean(img_array, axis=2)
        row_variance = np.var(gray, axis=1)

        # 宝可梦菜单有规律的行间变化
        peaks = np.where(row_variance > np.mean(row_variance))[0]
        return len(peaks) > 3

    def _is_item_menu(self, img_array: np.ndarray) -> bool:
        """检测物品菜单"""
        # 类似宝可梦菜单但布局略有不同
        return False  # 暂时简化

    def _is_save_menu(self, img_array: np.ndarray) -> bool:
        """检测存档菜单"""
        return False  # 暂时简化

    def _detect_boundaries(self, img_array: np.ndarray) -> bool:
        """检测边界（墙壁、栅栏）"""
        # 检测画面边缘的暗色区域
        edges = [
            img_array[0, :, :],      # 顶部
            img_array[-1, :, :],     # 底部
            img_array[:, 0, :],      # 左侧
            img_array[:, -1, :]      # 右侧
        ]

        dark_edges = sum(1 for edge in edges if np.mean(edge) < 100)
        return dark_edges >= 2

    def _estimate_walkable_areas(self, img_array: np.ndarray) -> float:
        """估算可行走区域比例"""
        # 草地、道路通常可行走，水域、建筑通常不可行走
        grass = self._calculate_color_ratio(img_array, 'grass')
        road = self._calculate_color_ratio(img_array, 'road')

        return round(grass + road, 2)

    def _detect_npcs(self, img_array: np.ndarray) -> List[Dict]:
        """检测NPC"""
        # 简化版：检测非背景的小块区域
        # 实际需要更复杂的图像处理
        return []

    def _detect_interactables(self, img_array: np.ndarray) -> List[Dict]:
        """检测可交互对象"""
        return []

    def _detect_player(self, img_array: np.ndarray) -> Optional[Dict]:
        """检测玩家角色"""
        # 玩家通常在屏幕中心
        h, w = img_array.shape[:2]
        center_region = img_array[
            int(h*0.4):int(h*0.6),
            int(w*0.4):int(w*0.6),
            :
        ]

        # 如果中心区域有特殊颜色模式，可能是玩家
        variance = np.var(center_region)
        if variance > 500:
            return {
                'type': 'player',
                'position': 'center',
                'confidence': 0.7
            }
        return None

    def _detect_doors(self, img_array: np.ndarray) -> List[Dict]:
        """检测门"""
        return []

    def _detect_items(self, img_array: np.ndarray) -> List[Dict]:
        """检测物品（精灵球等）"""
        return []

    # ===== 可视化方法 =====

    def add_grid_overlay(self, image: Image.Image) -> Image.Image:
        """添加网格覆盖用于可视化"""
        img_with_grid = image.copy()
        draw = ImageDraw.Draw(img_with_grid)

        # 绘制垂直线
        for x in range(0, self.SCREEN_WIDTH, self.GRID_SIZE):
            draw.line([(x, 0), (x, self.SCREEN_HEIGHT)], fill=(255, 0, 0), width=1)

        # 绘制水平线
        for y in range(0, self.SCREEN_HEIGHT, self.GRID_SIZE):
            draw.line([(0, y), (self.SCREEN_WIDTH, y)], fill=(255, 0, 0), width=1)

        # 高亮中心图块
        center_x = (self.SCREEN_WIDTH // 2) // self.GRID_SIZE * self.GRID_SIZE
        center_y = (self.SCREEN_HEIGHT // 2) // self.GRID_SIZE * self.GRID_SIZE

        draw.rectangle(
            [center_x, center_y, center_x + self.GRID_SIZE, center_y + self.GRID_SIZE],
            outline=(0, 255, 0),
            width=2
        )

        return img_with_grid

    def save_annotated_screenshot(self, image: Image.Image, filepath: str) -> None:
        """保存带注释的截图"""
        annotated = self.add_grid_overlay(image)
        annotated.save(filepath)
        self.logger.debug(f"已保存带注释的截图到 {filepath}")
