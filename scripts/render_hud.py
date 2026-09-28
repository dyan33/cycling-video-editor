"""HUD 表盘绘制库（参数化：画布/位置/缩放/主题色/小数位）。

mimo preset：速度 240° 半圆盘（大数字）+ 功率/心率 360° 圆环。
布局以画布宽高比例定义，position 四角预设镜像。
"""

import math

from PIL import Image, ImageDraw, ImageFont

FONT_NUM = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_CN = "/System/Library/Fonts/STHeiti Medium.ttc"

C_WHITE = (255, 255, 255, 235)
C_TRACK = (255, 255, 255, 45)
C_PLATE = (0, 0, 0, 115)
DEFAULT_THEME = {"speed": (255, 122, 0), "power": (0, 200, 255), "hr": (255, 59, 72)}


def _font(path, size):
    try:
        return ImageFont.truetype(path, int(size))
    except OSError:
        return ImageFont.load_default()


def _text_center(draw, xy, text, font, fill):
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((x - (bbox[2] - bbox[0]) / 2 - bbox[0], y - (bbox[3] - bbox[1]) / 2 - bbox[1]),
              text, font=font, fill=fill)


def layout(W, H, position="left_top", scale=1.0):
    """基准（left_top，竖屏 1440x1920 实测值比例化）→ 各表盘圆心与半径。"""
    sx, sy = 0.167 * W, 0.24 * H
    r_speed = 0.090 * W * scale
    r1x, r1y = 0.115 * W, 0.417 * H
    r2x, r2y = 0.208 * W, 0.417 * H
    r_ring = 0.0444 * W * scale

    mirror_x, mirror_y = (position in ("right_top", "right_bottom"),
                          position in ("left_bottom", "right_bottom"))
    def mx(x):
        return W - x if mirror_x else x
    def my(y):
        # bottom 预设：把整个表盘块上移镜像（以最高元素为轴近似）
        return H - y if mirror_y else y

    return {
        "speed": (mx(sx), my(sy), r_speed),
        "power": (mx(r1x), my(r1y), r_ring),
        "hr": (mx(r2x), my(r2y), r_ring),
    }


def gauge_speed(draw, center, radius, value, theme, decimals=1):
    cx, cy = center
    margin = radius * 0.20
    draw.ellipse((cx - radius - margin, cy - radius - margin,
                  cx + radius + margin, cy + radius + margin), fill=C_PLATE)
    a0, sweep = 150, 240
    frac = max(0.0, min(1.0, value / 60.0))
    arc_w = int(radius * 0.146)
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.arc(box, a0, a0 + sweep, fill=C_TRACK, width=arc_w)
    if frac > 0.005:
        draw.arc(box, a0, a0 + sweep * frac, fill=theme["speed"] + (255,), width=arc_w)
    for i in range(5):
        ang = math.radians(a0 + sweep * i / 4)
        r1, r2 = radius * 0.83, radius * 0.74
        draw.line((cx + r1 * math.cos(ang), cy + r1 * math.sin(ang),
                   cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
                  fill=(255, 255, 255, 140), width=max(2, int(radius * 0.024)))
    txt = f"{value:.{decimals}f}"
    f_num = _font(FONT_NUM, radius * 0.73 * min(1.0, 3.2 / max(len(txt), 3)))
    f_unit = _font(FONT_NUM, radius * 0.21)
    f_lab = _font(FONT_CN, radius * 0.195)
    _text_center(draw, (cx, cy - radius * 0.05), txt, f_num, C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.49), "km/h", f_unit, C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.96), "速度", f_lab, C_WHITE)


def ring_gauge(draw, center, radius, value, vmax, color, label, unit, decimals=0):
    cx, cy = center
    margin = radius * 0.32
    draw.ellipse((cx - radius - margin, cy - radius - margin,
                  cx + radius + margin, cy + radius + margin), fill=C_PLATE)
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    frac = max(0.0, min(1.0, value / vmax))
    arc_w = int(radius * 0.24)
    draw.arc(box, 90, 450, fill=C_TRACK, width=arc_w)
    if frac > 0.005:
        draw.arc(box, 90, 90 + 360 * frac, fill=color + (255,), width=arc_w)
    txt = f"{value:.{decimals}f}"
    f_num = _font(FONT_NUM, radius * 0.64 * min(1.0, 3.6 / max(len(txt), 3)))
    f_unit = _font(FONT_NUM, radius * 0.30)
    f_lab = _font(FONT_CN, radius * 0.34)
    _text_center(draw, (cx, cy - radius * 0.22), txt, f_num, C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.34), unit, f_unit, C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.98), label, f_lab, C_WHITE)


def render_frame(W, H, style, values):
    """values: {"speed": kmh, "power": W, "hr": bpm} → RGBA HUD 层。"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lay = layout(W, H, style.get("position", "left_top"), float(style.get("scale", 1.0)))
    theme = {k: tuple(v) for k, v in {**DEFAULT_THEME, **(style.get("theme") or {})}.items()}
    dec = style.get("decimals", {})
    ranges = {"speed": 60.0, "power": 400.0, "hr": 190.0, **(style.get("ranges") or {})}

    fields = style.get("fields", ["speed", "power", "hr"])
    if "speed" in fields and values.get("speed") is not None:
        gauge_speed(draw, lay["speed"][:2], lay["speed"][2], values["speed"], theme,
                    int(dec.get("speed", 1)))
    if "power" in fields and values.get("power") is not None:
        ring_gauge(draw, lay["power"][:2], lay["power"][2], values["power"], ranges["power"],
                   theme["power"], "功率", "W", int(dec.get("power", 0)))
    if "hr" in fields and values.get("hr") is not None:
        ring_gauge(draw, lay["hr"][:2], lay["hr"][2], values["hr"], ranges["hr"],
                   theme["hr"], "心率", "bpm", int(dec.get("hr", 1)))
    return img
