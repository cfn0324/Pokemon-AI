import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import patches
from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR_20260405 = REPO_ROOT / "docs" / "img" / "2026-04-05" / "main_figures"
FIGURE_DIR_20260406 = REPO_ROOT / "docs" / "img" / "2026-04-06" / "main_figures"

FONT_REGULAR_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]
FONT_BOLD_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]


def pick_font_path(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No usable Chinese font was found in C:\\Windows\\Fonts")


REGULAR_FONT_PATH = pick_font_path(FONT_REGULAR_CANDIDATES)
BOLD_FONT_PATH = pick_font_path(FONT_BOLD_CANDIDATES)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = BOLD_FONT_PATH if bold else REGULAR_FONT_PATH
    return ImageFont.truetype(str(font_path), size)


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = char if not current else current + char
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = char
        else:
            lines.append(candidate)
            current = ""
    if current:
        lines.append(current)
    return lines or [text]


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    origin: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    max_width: int,
    line_gap: int = 6,
) -> int:
    x, y = origin
    line_height = font.size + line_gap
    for line in wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def paste_contained(base: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    contained = ImageOps.contain(image, (width, height), Image.LANCZOS)
    offset_x = x0 + (width - contained.width) // 2
    offset_y = y0 + (height - contained.height) // 2
    base.paste(contained, (offset_x, offset_y))


def crop_single_frame_to_gameplay(target: Path) -> None:
    source = Image.open(target).convert("RGB")
    gameplay = source.crop((0, 0, source.width, min(720, source.height)))
    gameplay.save(target)


def redraw_fig03_fig04_fig05() -> None:
    for name in [
        "fig03_route1_northbound.png",
        "fig04_viridian_mart_parcel.png",
        "fig05_post_parcel_mart_loop.png",
    ]:
        crop_single_frame_to_gameplay(FIGURE_DIR_20260406 / name)


def redraw_fig06() -> None:
    source_names = [
        "fig01_pallet_west_lane.png",
        "fig02_pallet_north_exit.png",
        "fig03_route1_northbound.png",
        "fig04_viridian_mart_parcel.png",
        "fig05_post_parcel_mart_loop.png",
    ]
    target = FIGURE_DIR_20260406 / "fig06_pure_ai_demo_progression.png"
    canvas = Image.new("RGB", (1040, 1400), "white")
    draw = ImageDraw.Draw(canvas)

    panel_w = 470
    panel_h = 423
    border_color = (190, 190, 190)
    positions = [
        (40, 40),
        (530, 40),
        (40, 487),
        (530, 487),
        ((1040 - panel_w) // 2, 934),
    ]

    for name, (x, y) in zip(source_names, positions):
        source = Image.open(FIGURE_DIR_20260406 / name).convert("RGB")
        gameplay_only = source.crop((0, 0, source.width, min(720, source.height)))
        paste_contained(canvas, gameplay_only, (x, y, x + panel_w, y + panel_h))
        draw.rectangle((x, y, x + panel_w, y + panel_h), outline=border_color, width=2)

    canvas.save(target)


def draw_bullet_block(
    draw: ImageDraw.ImageDraw,
    origin: tuple[int, int],
    max_width: int,
    bullets: list[str],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    bullet_gap: int,
) -> None:
    x, y = origin
    bullet_symbol = "- "
    symbol_width = int(draw.textlength(bullet_symbol, font=font))
    line_height = font.size + 10
    for bullet in bullets:
        wrapped_lines = wrap_text(draw, bullet, font, max_width - symbol_width)
        for index, line in enumerate(wrapped_lines):
            prefix = bullet_symbol if index == 0 else "  "
            draw.text((x, y), prefix + line, font=font, fill=fill)
            y += line_height
        y += bullet_gap


def draw_arrow_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
    width: int = 4,
    head_length: int = 18,
    head_half_width: int = 8,
) -> None:
    draw.line((*start, *end), fill=color, width=width)

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return

    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux
    base_x = end[0] - ux * head_length
    base_y = end[1] - uy * head_length
    left = (base_x + px * head_half_width, base_y + py * head_half_width)
    right = (base_x - px * head_half_width, base_y - py * head_half_width)
    draw.polygon(
        [
            (int(end[0]), int(end[1])),
            (int(left[0]), int(left[1])),
            (int(right[0]), int(right[1])),
        ],
        fill=color,
    )


def redraw_fig07() -> None:
    target = FIGURE_DIR_20260406 / "fig07_decision_chain_annotation.png"
    canvas = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(25, bold=True)
    body_font = load_font(18)
    outline = (43, 103, 150)
    fill = (233, 240, 248)
    line_color = (120, 120, 120)
    text_color = (58, 58, 58)

    boxes = [
        {
            "rect": (60, 160, 360, 320),
            "title": "1. 离开研究所",
            "lines": ["左、左、下、下", "沿已校验门列 x=4/5 出门"],
        },
        {
            "rect": (430, 160, 730, 320),
            "title": "2. 北上穿过真新镇",
            "lines": ["沿研究所前缘左移", "在 x=9 后连续上行"],
        },
        {
            "rect": (800, 160, 1100, 320),
            "title": "3. 进入 1 号道路",
            "lines": ["在北端右移对齐", "继续向上穿过关口"],
        },
        {
            "rect": (1170, 160, 1470, 320),
            "title": "4. 进入常磐市",
            "lines": ["沿树篱规避阻挡", "从南门进入城区"],
        },
        {
            "rect": (250, 520, 550, 680),
            "title": "5. 接近商店",
            "lines": ["在 x=19 上移", "在 y=16 右移后向下进入"],
        },
        {
            "rect": (620, 520, 920, 680),
            "title": "6. 领取包裹",
            "lines": ["在 (29,20) 上移", "推进店员对话，物品数增至 1"],
        },
        {
            "rect": (990, 520, 1290, 680),
            "title": "7. 剩余缺口",
            "lines": ["取得包裹后", "商店退出仍有局部抖动"],
        },
    ]

    for box in boxes:
        x0, y0, x1, y1 = box["rect"]
        draw.rounded_rectangle(box["rect"], radius=18, fill=fill, outline=outline, width=4)
        draw.text((x0 + 18, y0 + 18), box["title"], font=title_font, fill=text_color)
        y = y0 + 70
        for line in box["lines"]:
            y = draw_wrapped_text(
                draw,
                (x0 + 18, y),
                line,
                body_font,
                text_color,
                (x1 - x0) - 36,
                line_gap=4,
            )
            y += 10

    draw_arrow_line(draw, (360, 240), (430, 240), line_color)
    draw_arrow_line(draw, (730, 240), (800, 240), line_color)
    draw_arrow_line(draw, (1100, 240), (1170, 240), line_color)
    draw_arrow_line(draw, (1245, 320), (500, 520), line_color)
    draw_arrow_line(draw, (550, 600), (620, 600), line_color)
    draw_arrow_line(draw, (920, 600), (990, 600), line_color)

    canvas.save(target)


def redraw_fig08() -> None:
    target = FIGURE_DIR_20260406 / "fig08_method_positioning.png"
    svg_target = target.with_suffix(".svg")

    thesis_font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if not thesis_font_path.exists():
        thesis_font_path = REGULAR_FONT_PATH

    root_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=12)
    criterion_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=10)
    block_title_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=11)
    block_title_multiline_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=10)
    body_fp = fm.FontProperties(fname=str(thesis_font_path), size=7.8)
    branch_fp = fm.FontProperties(fname=str(thesis_font_path), size=8.0)
    note_fp = fm.FontProperties(fname=str(thesis_font_path), size=8.2)

    fig = plt.figure(figsize=(1600 / 180, 930 / 180), dpi=180, facecolor="white")
    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.08, top=0.96)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    line_color = "#202020"
    muted_text = "#5C5C5C"
    thesis_fill = "#ECECEC"
    normal_fill = "#FAFAFA"

    def box_left(xc: float, width: float) -> float:
        return xc - width / 2

    def box_right(xc: float, width: float) -> float:
        return xc + width / 2

    def diamond_left(xc: float, width: float) -> float:
        return xc - width / 2

    def diamond_right(xc: float, width: float) -> float:
        return xc + width / 2

    def add_box(
        xc: float,
        yc: float,
        width: float,
        height: float,
        title: str,
        body: str | None = None,
        highlight: bool = False,
        body_align: str = "center",
    ) -> None:
        x0 = xc - width / 2
        y0 = yc - height / 2
        patch = patches.FancyBboxPatch(
            (x0, y0),
            width,
            height,
            boxstyle="round,pad=0.010,rounding_size=0.010",
            linewidth=1.5 if highlight else 1.0,
            edgecolor=line_color,
            facecolor=thesis_fill if highlight else normal_fill,
        )
        ax.add_patch(patch)
        if body is None:
            ax.text(
                xc,
                yc,
                title,
                fontproperties=root_fp,
                color=line_color,
                ha="center",
                va="center",
                linespacing=1.25,
            )
            return
        title_lines = title.count("\n") + 1
        title_fp = block_title_multiline_fp if title_lines > 1 else block_title_fp
        title_y = y0 + height * 0.75
        body_y = y0 + height * 0.32
        ax.text(
            xc,
            title_y,
            title,
            fontproperties=title_fp,
            color=line_color,
            ha="center",
            va="center",
            linespacing=1.15,
        )
        ax.text(
            x0 + 0.02 if body_align == "left" else xc,
            body_y,
            body,
            fontproperties=body_fp,
            color=muted_text,
            ha=body_align,
            va="center",
            linespacing=1.22,
        )

    def add_diamond(xc: float, yc: float, width: float, height: float, label: str) -> None:
        vertices = [
            (xc, yc + height / 2),
            (xc + width / 2, yc),
            (xc, yc - height / 2),
            (xc - width / 2, yc),
        ]
        patch = patches.Polygon(
            vertices,
            closed=True,
            linewidth=1.1,
            edgecolor=line_color,
            facecolor="white",
        )
        ax.add_patch(patch)
        ax.text(
            xc,
            yc,
            label,
            fontproperties=criterion_fp,
            color=line_color,
            ha="center",
            va="center",
            linespacing=1.2,
        )

    def draw_polyline(points: list[tuple[float, float]]) -> None:
        ax.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            color=line_color,
            linewidth=1.2,
        )

    root_x, root_y, root_w, root_h = 0.11, 0.55, 0.16, 0.12
    policy_x, policy_y, policy_w, policy_h = 0.31, 0.55, 0.18, 0.16
    rl_x, rl_y, rl_w, rl_h = 0.64, 0.79, 0.26, 0.20
    env_x, env_y, env_w, env_h = 0.58, 0.35, 0.18, 0.16
    general_x, general_y, general_w, general_h = 0.855, 0.50, 0.24, 0.23
    thesis_x, thesis_y, thesis_w, thesis_h = 0.855, 0.18, 0.24, 0.26
    split1_x = 0.44
    split2_x = 0.70

    label_bbox = {"facecolor": "white", "edgecolor": "none", "pad": 0.15}

    add_box(root_x, root_y, root_w, root_h, "长时序任务中的\n决策智能体", body=None)
    add_diamond(policy_x, policy_y, policy_w, policy_h, "策略产生方式")
    add_box(
        rl_x,
        rl_y,
        rl_w,
        rl_h,
        "强化学习游戏代理",
        "状态张量输入\n奖励训练形成策略\n以回报与成功率评估",
    )
    add_diamond(env_x, env_y, env_w, env_h, "任务环境")
    add_box(
        general_x,
        general_y,
        general_w,
        general_h,
        "通用任务型\nLLM 智能体",
        "文本与工具反馈输入\n依赖语言规划与工具调用\n以任务案例评估",
    )
    add_box(
        thesis_x,
        thesis_y,
        thesis_w,
        thesis_h,
        "本文：LLM 决策\n游戏智能体",
        "RAM、截图与记忆摘要输入\nLLM 直接承担普通回合决策\n以时间线、图像与批量复验评估",
        highlight=True,
    )

    draw_polyline([(box_right(root_x, root_w), root_y), (diamond_left(policy_x, policy_w), policy_y)])
    draw_polyline(
        [
            (diamond_right(policy_x, policy_w), policy_y),
            (split1_x, policy_y),
            (split1_x, rl_y),
            (box_left(rl_x, rl_w), rl_y),
        ]
    )
    draw_polyline(
        [
            (diamond_right(policy_x, policy_w), policy_y),
            (split1_x, policy_y),
            (split1_x, env_y),
            (diamond_left(env_x, env_w), env_y),
        ]
    )
    draw_polyline(
        [
            (diamond_right(env_x, env_w), env_y),
            (split2_x, env_y),
            (split2_x, general_y),
            (box_left(general_x, general_w), general_y),
        ]
    )
    draw_polyline(
        [
            (diamond_right(env_x, env_w), env_y),
            (split2_x, env_y),
            (split2_x, thesis_y),
            (box_left(thesis_x, thesis_w), thesis_y),
        ]
    )

    ax.text(
        (split1_x + box_left(rl_x, rl_w)) / 2,
        rl_y + 0.037,
        "训练后执行",
        fontproperties=branch_fp,
        color=muted_text,
        ha="center",
        va="center",
        bbox=label_bbox,
    )
    ax.text(
        (split1_x + diamond_left(env_x, env_w)) / 2,
        env_y + 0.040,
        "在线语言推理",
        fontproperties=branch_fp,
        color=muted_text,
        ha="center",
        va="center",
        bbox=label_bbox,
    )
    ax.text(
        (split2_x + box_left(general_x, general_w)) / 2,
        general_y + 0.034,
        "开放任务",
        fontproperties=branch_fp,
        color=muted_text,
        ha="center",
        va="center",
        bbox=label_bbox,
    )
    ax.text(
        (split2_x + box_left(thesis_x, thesis_w)) / 2,
        thesis_y + 0.034,
        "游戏环境",
        fontproperties=branch_fp,
        color=muted_text,
        ha="center",
        va="center",
        bbox=label_bbox,
    )

    ax.text(
        0.02,
        0.06,
        "注：图中以“策略产生方式”和“任务环境”作为定位依据；灰底框表示本文研究对象。",
        fontproperties=note_fp,
        color=muted_text,
        ha="left",
        va="center",
    )

    fig.savefig(target, dpi=180, facecolor="white")
    fig.savefig(svg_target, facecolor="white")
    plt.close(fig)


def redraw_fig09() -> None:
    target = FIGURE_DIR_20260406 / "fig09_system_layered_architecture.png"
    svg_target = target.with_suffix(".svg")

    thesis_font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if not thesis_font_path.exists():
        thesis_font_path = REGULAR_FONT_PATH

    title_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=12)
    layer_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=10.0)
    body_fp = fm.FontProperties(fname=str(thesis_font_path), size=7.5)
    side_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=9.2)
    side_body_fp = fm.FontProperties(fname=str(thesis_font_path), size=7.4)
    note_fp = fm.FontProperties(fname=str(thesis_font_path), size=7.6)

    fig = plt.figure(figsize=(1680 / 180, 1180 / 180), dpi=180, facecolor="white")
    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.04, top=0.97)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    line_color = "#202020"
    text_color = "#1F1F1F"
    muted_text = "#5C5C5C"
    fill_a = "#FAFAFA"
    fill_b = "#F0F0F0"
    fill_highlight = "#E8E8E8"
    outer_fill = "#FFFFFF"

    runtime_x0, runtime_y0 = 0.20, 0.08
    runtime_w, runtime_h = 0.56, 0.84

    outer = patches.FancyBboxPatch(
        (runtime_x0, runtime_y0),
        runtime_w,
        runtime_h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=1.5,
        edgecolor=line_color,
        facecolor=outer_fill,
    )
    ax.add_patch(outer)

    ax.text(
        runtime_x0 + 0.02,
        runtime_y0 + runtime_h + 0.022,
        "PokemonAIAgent 运行时主协调器",
        fontproperties=title_fp,
        color=text_color,
        ha="left",
        va="bottom",
    )

    layers = [
        (
            "审计与评估层",
            "Logger / GameVisualizer / 批量评估脚本\n时间线校验、汇总统计与结构化报告输出",
            fill_a,
        ),
        (
            "执行与稳定化层",
            "ActionExecutor / 动作合法化 / 同回合同观测重试\n将模型动作稳定映射为模拟器可执行输入",
            fill_b,
        ),
        (
            "主决策层",
            "MainAgent / AIClient / DecisionEngine\n普通回合动作生成、请求发送与来源记录",
            fill_highlight,
        ),
        (
            "上下文与目标层",
            "ContextManager / Summarizer / GoalManager\n近期回合、摘要历史、任务焦点与待办组织",
            fill_b,
        ),
        (
            "状态构造层",
            "GameState / MapMemory / VisionProcessor\n将截图、RAM 与地图记忆整理为任务化状态",
            fill_a,
        ),
        (
            "环境接入层",
            "GameBoyEmulator / MemoryReader / 检查点恢复\nROM 运行、截图采样与 RAM 语义读取",
            fill_b,
        ),
    ]

    # Use explicit symmetric inner margins so the stacked boxes remain
    # visually centered inside the runtime frame after export.
    inner_margin_x = 0.040
    inner_margin_y = 0.074
    gap = 0.022
    layer_w = runtime_w - inner_margin_x * 2
    layer_x0 = runtime_x0 + inner_margin_x
    layer_h = (runtime_h - inner_margin_y * 2 - (len(layers) - 1) * gap) / len(layers)
    stack_bottom = runtime_y0 + inner_margin_y

    layer_boxes: list[tuple[float, float, float, float]] = []
    prev_bottom = None
    for idx, (title, body, fill) in enumerate(layers):
        y0 = stack_bottom + (len(layers) - 1 - idx) * (layer_h + gap)
        patch = patches.FancyBboxPatch(
            (layer_x0, y0),
            layer_w,
            layer_h,
            boxstyle="round,pad=0.008,rounding_size=0.010",
            linewidth=1.0 if title != "主决策层" else 1.4,
            edgecolor=line_color,
            facecolor=fill,
        )
        ax.add_patch(patch)
        ax.text(
            layer_x0 + 0.02,
            y0 + layer_h * 0.72,
            title,
            fontproperties=layer_fp,
            color=text_color,
            ha="left",
            va="center",
        )
        ax.text(
            layer_x0 + 0.02,
            y0 + layer_h * 0.28,
            body,
            fontproperties=body_fp,
            color=muted_text,
            ha="left",
            va="center",
            linespacing=1.32,
        )
        cx = layer_x0 + layer_w / 2
        cy = y0 + layer_h / 2
        layer_boxes.append((layer_x0, y0, layer_x0 + layer_w, y0 + layer_h))

        if prev_bottom is not None:
            arrow = patches.FancyArrowPatch(
                (cx, prev_bottom - 0.004),
                (cx, y0 + layer_h + 0.004),
                arrowstyle="-|>",
                mutation_scale=12,
                linewidth=1.1,
                color=line_color,
            )
            ax.add_patch(arrow)
        prev_bottom = y0

    def add_side_box(
        x0: float,
        y0: float,
        w: float,
        h: float,
        title: str,
        body: str,
    ) -> None:
        patch = patches.FancyBboxPatch(
            (x0, y0),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.010",
            linewidth=1.1,
            edgecolor=line_color,
            facecolor="#FBFBFB",
        )
        ax.add_patch(patch)
        ax.text(
            x0 + w / 2,
            y0 + h * 0.67,
            title,
            fontproperties=side_fp,
            color=text_color,
            ha="center",
            va="center",
            linespacing=1.2,
        )
        ax.text(
            x0 + w / 2,
            y0 + h * 0.30,
            body,
            fontproperties=side_body_fp,
            color=muted_text,
            ha="center",
            va="center",
            linespacing=1.22,
        )

    audit_box = layer_boxes[0]
    execute_box = layer_boxes[1]
    decision_box = layer_boxes[2]
    state_box = layer_boxes[4]
    access_box = layer_boxes[5]

    left_box_w, left_box_h = 0.13, 0.18
    right_box_w, right_box_h = 0.14, 0.16
    side_gap = 0.05
    left_box_x0 = runtime_x0 - side_gap - left_box_w
    right_box_x0 = runtime_x0 + runtime_w + side_gap

    env_center_y = ((state_box[1] + state_box[3]) / 2 + (access_box[1] + access_box[3]) / 2) / 2
    decision_center_y = (decision_box[1] + decision_box[3]) / 2
    audit_center_y = (audit_box[1] + audit_box[3]) / 2

    env_box = (left_box_x0, env_center_y - left_box_h / 2, left_box_w, left_box_h)
    model_box = (right_box_x0, decision_center_y - right_box_h / 2, right_box_w, right_box_h)
    output_box = (right_box_x0, audit_center_y - right_box_h / 2, right_box_w, right_box_h)

    add_side_box(*env_box, "PyBoy +\nPokemon Red", "游戏环境\n状态读取与动作写回")
    add_side_box(*model_box, "外部模型服务", "LLM API\n文本与图像输入")
    add_side_box(*output_box, "结构化证据输出", "JSON 报告 / 截图 / 视频\n批量汇总与正文主图")

    def connect(
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None = None,
        label_offset: tuple[float, float] = (0.0, 0.0),
        bidirectional: bool = False,
    ) -> None:
        arrow = patches.FancyArrowPatch(
            start,
            end,
            arrowstyle="<->" if bidirectional else "-|>",
            mutation_scale=12,
            linewidth=1.1,
            color=line_color,
            connectionstyle="arc3,rad=0.0",
        )
        ax.add_patch(arrow)
        if label:
            xm = (start[0] + end[0]) / 2 + label_offset[0]
            ym = (start[1] + end[1]) / 2 + label_offset[1]
            ax.text(
                xm,
                ym,
                label,
                fontproperties=note_fp,
                color=muted_text,
                ha="center",
                va="center",
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.10},
            )

    connect_direct = connect

    def connect_elbow(
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        elbow_x: float,
        label: str | None = None,
        label_pos: tuple[float, float] | None = None,
    ) -> None:
        points = [
            start,
            (elbow_x, start[1]),
            (elbow_x, end[1]),
            end,
        ]
        for p0, p1 in zip(points[:-2], points[1:-1]):
            ax.plot(
                [p0[0], p1[0]],
                [p0[1], p1[1]],
                color=line_color,
                linewidth=1.1,
                solid_capstyle="round",
            )
        arrow = patches.FancyArrowPatch(
            points[-2],
            points[-1],
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.1,
            color=line_color,
            connectionstyle="arc3,rad=0.0",
        )
        ax.add_patch(arrow)
        if label and label_pos is not None:
            ax.text(
                label_pos[0],
                label_pos[1],
                label,
                fontproperties=note_fp,
                color=muted_text,
                ha="center",
                va="center",
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.10},
            )

    env_right = env_box[0] + env_box[2]
    access_left = (layer_x0, (access_box[1] + access_box[3]) / 2)
    execute_left = (layer_x0, (execute_box[1] + execute_box[3]) / 2)
    env_upper_anchor = (env_right, env_box[1] + left_box_h * 0.72)
    env_lower_anchor = (env_right, access_left[1])
    env_write_channel_x = runtime_x0 - 0.030
    connect_elbow(
        execute_left,
        env_upper_anchor,
        elbow_x=env_write_channel_x,
        label="写回动作",
        label_pos=(env_write_channel_x - 0.006, (execute_left[1] + env_upper_anchor[1]) / 2 + 0.010),
    )
    connect_direct(
        env_lower_anchor,
        access_left,
        "读取状态",
        (0.0, -0.028),
    )

    decision_right = (layer_x0 + layer_w, decision_center_y)
    model_left = (model_box[0], model_box[1] + model_box[3] / 2)
    connect_direct(decision_right, model_left, "请求 / 返回", (0.00, 0.03), bidirectional=True)

    audit_right = (layer_x0 + layer_w, audit_center_y)
    output_left = (output_box[0], output_box[1] + output_box[3] / 2)
    connect_direct(audit_right, output_left, "沉淀证据", (0.0, 0.03))

    ax.text(
        runtime_x0 + runtime_w / 2,
        runtime_y0 - 0.03,
        "普通回合主路径：状态构造 → 上下文与目标 → 主决策 → 执行与稳定化 → 审计与评估",
        fontproperties=note_fp,
        color=muted_text,
        ha="center",
        va="top",
    )

    fig.savefig(target, dpi=180, facecolor="white")
    fig.savefig(svg_target, facecolor="white")
    plt.close(fig)


def redraw_fig10() -> None:
    target = FIGURE_DIR_20260406 / "fig10_system_overall_architecture.png"
    svg_target = target.with_suffix(".svg")

    thesis_font_path = pick_font_path(FONT_REGULAR_CANDIDATES)
    title_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=12)
    node_title_fp = fm.FontProperties(fname=str(BOLD_FONT_PATH), size=10.0)
    node_body_fp = fm.FontProperties(fname=str(thesis_font_path), size=7.4)
    note_fp = fm.FontProperties(fname=str(thesis_font_path), size=7.4)

    fig = plt.figure(figsize=(1840 / 200, 1180 / 200), dpi=200, facecolor="white")
    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.04, top=0.97)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    line_color = "#202020"
    text_color = "#1F1F1F"
    muted_text = "#555555"
    fill_panel = "#FAFAFA"
    fill_alt = "#F2F2F2"
    fill_focus = "#EAEAEA"

    runtime_x0, runtime_y0 = 0.23, 0.08
    runtime_w, runtime_h = 0.54, 0.80
    runtime = patches.FancyBboxPatch(
        (runtime_x0, runtime_y0),
        runtime_w,
        runtime_h,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        linewidth=1.5,
        edgecolor=line_color,
        facecolor="white",
    )
    ax.add_patch(runtime)
    ax.text(
        runtime_x0 + 0.02,
        runtime_y0 + runtime_h + 0.022,
        "PokemonAIAgent 运行时主协调器",
        fontproperties=title_fp,
        color=text_color,
        ha="left",
        va="bottom",
    )

    def add_box(
        x0: float,
        y0: float,
        w: float,
        h: float,
        title: str,
        body: str,
        *,
        fill: str = fill_panel,
    ) -> tuple[float, float, float, float]:
        patch = patches.FancyBboxPatch(
            (x0, y0),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            linewidth=1.1,
            edgecolor=line_color,
            facecolor=fill,
        )
        ax.add_patch(patch)
        ax.text(
        x0 + 0.016,
        y0 + h * 0.68,
        title,
        fontproperties=node_title_fp,
        color=text_color,
            ha="left",
            va="center",
        )
        ax.text(
        x0 + 0.016,
        y0 + h * 0.32,
        body,
        fontproperties=node_body_fp,
        color=muted_text,
            ha="left",
            va="center",
            linespacing=1.28,
        )
        return (x0, y0, x0 + w, y0 + h)

    def center_left(box: tuple[float, float, float, float]) -> tuple[float, float]:
        x0, y0, _, y1 = box
        return (x0, (y0 + y1) / 2)

    def center_right(box: tuple[float, float, float, float]) -> tuple[float, float]:
        _, y0, x1, y1 = box
        return (x1, (y0 + y1) / 2)

    def center_top(box: tuple[float, float, float, float]) -> tuple[float, float]:
        x0, _, x1, y1 = box
        return ((x0 + x1) / 2, y1)

    def center_bottom(box: tuple[float, float, float, float]) -> tuple[float, float]:
        x0, y0, x1, _ = box
        return ((x0 + x1) / 2, y0)

    def center_x(box: tuple[float, float, float, float]) -> float:
        x0, _, x1, _ = box
        return (x0 + x1) / 2

    def center_y(box: tuple[float, float, float, float]) -> float:
        _, y0, _, y1 = box
        return (y0 + y1) / 2

    def add_arrow(
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        style: str = "-|>",
        curve: float | None = None,
        linewidth: float = 1.1,
    ) -> None:
        kwargs = {
            "arrowstyle": style,
            "mutation_scale": 12,
            "linewidth": linewidth,
            "color": line_color,
        }
        if curve is not None:
            kwargs["connectionstyle"] = f"arc3,rad={curve}"
        ax.add_patch(patches.FancyArrowPatch(start, end, **kwargs))

    def add_vertical_flow(
        upper: tuple[float, float, float, float],
        lower: tuple[float, float, float, float],
    ) -> None:
        add_arrow(
            (center_x(upper), upper[1]),
            (center_x(lower), lower[3]),
            linewidth=1.2,
        )

    access = add_box(
        runtime_x0 + 0.12,
        runtime_y0 + 0.62,
        0.30,
        0.10,
        "环境接入层",
        "GameBoyEmulator + MemoryReader\nROM 运行、截图采样与 RAM 语义读取",
        fill=fill_alt,
    )
    state = add_box(
        runtime_x0 + 0.12,
        runtime_y0 + 0.48,
        0.30,
        0.10,
        "状态构造层",
        "GameState + MapMemory + VisionProcessor\n将截图、RAM 与地图记忆整理为任务化状态",
        fill=fill_panel,
    )
    memorygoal = add_box(
        runtime_x0 + 0.12,
        runtime_y0 + 0.34,
        0.30,
        0.10,
        "记忆与目标层",
        "ContextManager + Summarizer + GoalManager\n近期回合、摘要历史与任务焦点维护",
        fill=fill_panel,
    )
    decision = add_box(
        runtime_x0 + 0.12,
        runtime_y0 + 0.20,
        0.30,
        0.10,
        "决策路由层",
        "DecisionEngine + AsyncDecisionMaker + MainAgent\n模型调用、动作生成与来源记录",
        fill=fill_focus,
    )
    support = add_box(
        runtime_x0 + 0.12,
        runtime_y0 + 0.06,
        0.30,
        0.10,
        "执行与运行时支撑层",
        "ActionExecutor + ProgressTracker + Logger + GameVisualizer\n动作执行、检查点、日志与可视化",
        fill=fill_alt,
    )

    resources = add_box(
        0.03,
        0.69,
        0.16,
        0.12,
        "配置与运行资源",
        "config.yaml / .env / PokemonRed.gb\n检查点存档",
    )
    scripts = add_box(
        0.03,
        0.46,
        0.16,
        0.12,
        "实验脚本",
        "autonomous_smoke.py\ncapture_evidence_run.py\nsmoke_report_summary.py",
    )
    researcher = add_box(
        0.03,
        0.23,
        0.16,
        0.12,
        "研究者 / 控制端",
        "运行控制、过程观察\n与结果复核",
    )
    model = add_box(
        0.83,
        center_y(decision) - 0.06,
        0.14,
        0.12,
        "外部模型服务",
        "AIClient 调用的\n主模型推理接口",
    )
    outputs = add_box(
        0.83,
        center_y(support) - 0.07,
        0.14,
        0.14,
        "结构化证据输出",
        "JSON 报告 / Markdown 汇总\n截图 / 视频 / 正文主图",
    )

    add_vertical_flow(access, state)
    add_vertical_flow(state, memorygoal)
    add_vertical_flow(memorygoal, decision)
    add_vertical_flow(decision, support)

    add_arrow(center_right(resources), center_left(access), linewidth=1.1)
    add_arrow(center_right(scripts), center_left(state), linewidth=1.1)
    add_arrow(center_right(researcher), center_left(support), style="<|-|>", linewidth=1.1)
    add_arrow(center_right(decision), center_left(model), style="<|-|>", linewidth=1.1)
    add_arrow(center_right(support), center_left(outputs), linewidth=1.1)

    ax.text(
        runtime_x0 + runtime_w / 2,
        runtime_y0 - 0.032,
        "主路径按中轴自上而下展开，外部资源、脚本、模型服务与证据输出通过侧向接口接入。",
        fontproperties=note_fp,
        color=muted_text,
        ha="center",
        va="top",
    )

    fig.savefig(target, dpi=200, facecolor="white")
    fig.savefig(svg_target, facecolor="white")
    plt.close(fig)


def sanitize_fig01_dashboard() -> None:
    target = FIGURE_DIR_20260405 / "fig01_dashboard_desktop.png"
    canvas = Image.new("RGB", (1600, 1100), (9, 18, 31))
    draw = ImageDraw.Draw(canvas)

    gameplay = Image.open(FIGURE_DIR_20260405 / "fig05_route1_battle_prebattle.png").convert("RGB")
    map_image = Image.open(FIGURE_DIR_20260405 / "fig07_route2_map_memory.png").convert("RGB")

    title_font = load_font(34, bold=True)
    subtitle_font = load_font(14)
    card_label_font = load_font(13, bold=True)
    card_title_font = load_font(28, bold=True)
    body_font = load_font(16)
    small_font = load_font(14)
    metric_value_font = load_font(30, bold=True)
    metric_label_font = load_font(15)

    shell_fill = (14, 25, 40)
    panel_fill = (20, 35, 56)
    panel_inner = (10, 21, 35)
    card_fill = (25, 40, 61)
    tag_fill = (56, 72, 95)
    metric_fill = (15, 28, 46)
    outline = (36, 59, 86)
    accent = (84, 171, 255)
    text_fill = (236, 242, 248)
    muted_fill = (166, 181, 198)
    button_primary = (173, 132, 64)
    button_secondary = (53, 82, 112)
    button_danger = (129, 77, 70)

    def rounded(rect: tuple[int, int, int, int], fill: tuple[int, int, int], radius: int = 20) -> None:
        draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=2)

    rounded((20, 18, 1580, 88), shell_fill)
    draw.text((42, 34), "智能体运行大屏", font=title_font, fill=text_fill)
    draw.text((42, 66), "保留实时画面、探索地图与策略控制，适合作为桌面端总览图。", font=subtitle_font, fill=muted_fill)

    pill_specs = [
        ((980, 30, 1110, 66), "已连接", (40, 79, 70)),
        ((1130, 30, 1260, 66), "已暂停", (74, 58, 65)),
        ((1280, 30, 1420, 66), "回合 195913", metric_fill),
        ((1440, 30, 1560, 66), "存档 14", metric_fill),
    ]
    for rect, label, fill in pill_specs:
        draw.rounded_rectangle(rect, radius=18, fill=fill)
        draw.text((rect[0] + 22, rect[1] + 9), label, font=small_font, fill=text_fill)

    metric_specs = [
        ("回合", "195913"),
        ("徽章", "0 / 8"),
        ("金钱", "3,175"),
        ("队伍", "1"),
        ("地图", "40"),
        ("坐标", "4, 8"),
        ("探索度", "17.0%"),
    ]
    metric_w = 205
    metric_y0 = 112
    metric_y1 = 198
    for index, (label, value) in enumerate(metric_specs):
        x0 = 20 + index * (metric_w + 18)
        x1 = x0 + metric_w
        rounded((x0, metric_y0, x1, metric_y1), metric_fill, radius=18)
        draw.text((x0 + 18, metric_y0 + 14), label, font=metric_label_font, fill=muted_fill)
        draw.text((x0 + 18, metric_y0 + 38), value, font=metric_value_font, fill=text_fill)

    panels = {
        "stage": (20, 230, 740, 1070),
        "map": (770, 230, 1120, 1070),
        "strategy": (1150, 230, 1580, 1070),
    }
    for rect in panels.values():
        rounded(rect, panel_fill, radius=24)

    draw.text((44, 252), "实时画面", font=card_title_font, fill=text_fill)
    draw.text((794, 252), "探索地图", font=card_title_font, fill=text_fill)
    draw.text((1174, 252), "策略与控制", font=card_title_font, fill=text_fill)

    tag_specs = [
        ((256, 246, 346, 276), "运行截图"),
        ((356, 246, 470, 276), "桌面端总览"),
        ((960, 246, 1040, 276), "地图 40"),
        ((1048, 246, 1100, 276), "局部记忆"),
        ((1450, 246, 1550, 276), "最新决策"),
    ]
    for rect, label in tag_specs:
        draw.rounded_rectangle(rect, radius=14, fill=tag_fill)
        draw.text((rect[0] + 14, rect[1] + 7), label, font=small_font, fill=text_fill)

    screen_box = (40, 300, 720, 1040)
    map_box = (790, 300, 1100, 1040)
    rounded(screen_box, panel_inner, radius=18)
    rounded(map_box, panel_inner, radius=18)
    paste_contained(canvas, gameplay.resize((gameplay.width * 4, gameplay.height * 4), Image.NEAREST), (60, 340, 700, 980))
    paste_contained(canvas, map_image, (810, 330, 1080, 1020))

    card_rects = [
        (1170, 300, 1560, 430),
        (1170, 450, 1560, 560),
        (1170, 580, 1560, 790),
        (1170, 810, 1560, 1040),
    ]
    for rect in card_rects:
        rounded(rect, card_fill, radius=18)

    draw.text((1190, 320), "当前动作", font=card_label_font, fill=muted_fill)
    draw.text((1190, 350), "等待", font=load_font(42, bold=True), fill=text_fill)
    draw.text((1415, 320), "动作依据", font=card_label_font, fill=muted_fill)
    draw_wrapped_text(draw, (1415, 348), "暂无完整推理解释。", body_font, text_fill, 120, line_gap=4)

    meta_boxes = [
        (1190, 392, 1270, 420, "回合", "-"),
        (1280, 392, 1360, 420, "界面", "未知"),
        (1370, 392, 1450, 420, "时间", "-"),
    ]
    for x0, y0, x1, y1, label, value in meta_boxes:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=panel_fill)
        draw.text((x0 + 10, y0 + 5), label, font=small_font, fill=muted_fill)
        draw.text((x0 + 10, y0 + 18), value, font=small_font, fill=text_fill)

    draw.text((1190, 470), "当前焦点", font=card_label_font, fill=(241, 190, 90))
    draw_wrapped_text(
        draw,
        (1190, 500),
        "朝下一个必经检查点推进；若当前画面不够明确，则继续利用未探索格试探。",
        body_font,
        text_fill,
        340,
        line_gap=6,
    )

    draw.text((1190, 600), "决策轨迹", font=card_label_font, fill=muted_fill)
    trace_lines = [
        "1. 读取 RAM 状态与当前坐标。",
        "2. 对照地图记忆，筛出未探索方向。",
        "3. 保留主模型动作选择，记录证据输出。",
    ]
    y = 636
    for line in trace_lines:
        y = draw_wrapped_text(draw, (1190, y), line, body_font, text_fill, 340, line_gap=6)
        y += 10

    draw.text((1190, 830), "运行控制", font=card_label_font, fill=muted_fill)
    buttons = [
        ((1190, 866, 1310, 912), "暂停", button_secondary),
        ((1320, 866, 1440, 912), "继续", button_secondary),
        ((1450, 866, 1560, 912), "单步", button_secondary),
        ((1190, 922, 1310, 968), "保存存档", button_primary),
        ((1320, 922, 1440, 968), "读取最新", button_secondary),
        ((1450, 922, 1560, 968), "停止", button_danger),
    ]
    for rect, label, fill in buttons:
        draw.rounded_rectangle(rect, radius=14, fill=fill)
        text_x = rect[0] + (rect[2] - rect[0] - draw.textlength(label, font=small_font)) / 2
        draw.text((text_x, rect[1] + 13), label, font=small_font, fill=text_fill)

    status_boxes = [
        (1190, 982, 1325, 1022, "状态", "已暂停"),
        (1340, 982, 1450, 1022, "步预算", "0"),
        (1465, 982, 1560, 1022, "队列", "0"),
    ]
    for x0, y0, x1, y1, label, value in status_boxes:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=panel_fill)
        draw.text((x0 + 10, y0 + 6), label, font=small_font, fill=muted_fill)
        draw.text((x0 + 10, y0 + 20), value, font=small_font, fill=text_fill)

    draw.line((743, 230, 743, 1070), fill=(12, 21, 35), width=4)
    draw.line((1123, 230, 1123, 1070), fill=(12, 21, 35), width=4)
    draw.line((20, 214, 1580, 214), fill=(12, 21, 35), width=4)
    draw.line((40, 290, 720, 290), fill=accent, width=3)
    draw.line((790, 290, 1100, 290), fill=accent, width=3)
    draw.line((1170, 290, 1560, 290), fill=accent, width=3)

    canvas.save(target)


def main() -> None:
    sanitize_fig01_dashboard()
    redraw_fig03_fig04_fig05()
    redraw_fig06()
    redraw_fig07()
    redraw_fig08()
    redraw_fig09()
    redraw_fig10()


if __name__ == "__main__":
    main()
