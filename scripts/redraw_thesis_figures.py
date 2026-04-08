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

    draw.line((360, 240, 430, 240), fill=line_color, width=4)
    draw.line((730, 240, 800, 240), fill=line_color, width=4)
    draw.line((1100, 240, 1170, 240), fill=line_color, width=4)
    draw.line((1320, 320, 1320, 430), fill=line_color, width=4)
    draw.line((1320, 430, 400, 520), fill=line_color, width=4)
    draw.line((550, 600, 620, 600), fill=line_color, width=4)
    draw.line((920, 600, 990, 600), fill=line_color, width=4)

    draw.polygon([(430, 240), (415, 232), (415, 248)], fill=line_color)
    draw.polygon([(800, 240), (785, 232), (785, 248)], fill=line_color)
    draw.polygon([(1170, 240), (1155, 232), (1155, 248)], fill=line_color)
    draw.polygon([(400, 520), (408, 505), (416, 518)], fill=line_color)
    draw.polygon([(620, 600), (605, 592), (605, 608)], fill=line_color)
    draw.polygon([(990, 600), (975, 592), (975, 608)], fill=line_color)

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


if __name__ == "__main__":
    main()
