"""骑行数据样式库：4 组含 距离/海拔/坡度 的 HUD 渲染器（确认后迁入 skill）。

values: {"speed": kmh, "power": W, "hr": bpm, "distance_km": km, "altitude_m": m, "grade_pct": %}
所有渲染器签名统一 render(W, H, v, ctx) -> RGBA Image；ctx 供样式 C 的海拔剖面使用。
"""

import math

from PIL import Image, ImageDraw, ImageFont

FONT_NUM = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_CN = "/System/Library/Fonts/STHeiti Medium.ttc"

C_WHITE = (255, 255, 255, 235)
C_TRACK = (255, 255, 255, 45)
C_PLATE = (0, 0, 0, 115)
C_GRAY = (200, 200, 200, 255)

THEME = {"speed": (255, 122, 0), "power": (0, 200, 255), "hr": (255, 59, 72),
         "grade": (255, 210, 80), "altitude": (170, 140, 255), "distance": (255, 210, 80)}


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


def _text_right(draw, xy, text, font, fill):
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((x - (bbox[2] - bbox[0]), y - (bbox[3] - bbox[1]) / 2 - bbox[1]),
              text, font=font, fill=fill)


def grade_color(g):
    ag = abs(g)
    if g < 0:
        return (90, 200, 255, 255)
    if ag < 3:
        return (255, 255, 255, 255)
    if ag < 6:
        return (255, 210, 80, 255)
    if ag < 9:
        return (255, 140, 40, 255)
    return (255, 59, 48, 255)


def _gauge_speed(draw, cx, cy, radius, value, color):
    """速度半圆盘（沿用 Mimo 结构）。"""
    margin = radius * 0.20
    draw.ellipse((cx - radius - margin, cy - radius - margin,
                  cx + radius + margin, cy + radius + margin), fill=C_PLATE)
    a0, sweep = 150, 240
    frac = max(0.0, min(1.0, value / 60.0))
    arc_w = int(radius * 0.146)
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.arc(box, a0, a0 + sweep, fill=C_TRACK, width=arc_w)
    if frac > 0.005:
        draw.arc(box, a0, a0 + sweep * frac, fill=color + (255,), width=arc_w)
    for i in range(5):
        ang = math.radians(a0 + sweep * i / 4)
        r1, r2 = radius * 0.83, radius * 0.74
        draw.line((cx + r1 * math.cos(ang), cy + r1 * math.sin(ang),
                   cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
                  fill=(255, 255, 255, 140), width=max(2, int(radius * 0.024)))
    txt = f"{value:.1f}"
    _text_center(draw, (cx, cy - radius * 0.05), txt,
                 _font(FONT_NUM, radius * 0.73 * min(1.0, 3.2 / max(len(txt), 3))), C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.49), "km/h", _font(FONT_NUM, radius * 0.21), C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.96), "速度", _font(FONT_CN, radius * 0.195), C_WHITE)


def _ring(draw, cx, cy, radius, value, vmax, color, label, unit, decimals=0):
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
    _text_center(draw, (cx, cy - radius * 0.22), txt,
                 _font(FONT_NUM, radius * 0.64 * min(1.0, 3.6 / max(len(txt), 3))), C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.34), unit, _font(FONT_NUM, radius * 0.30), C_WHITE)
    _text_center(draw, (cx, cy + radius * 0.98), label, _font(FONT_CN, radius * 0.34), C_WHITE)


# ---------- 样式 A：数据面板（码表面板风，6 行全字段） ----------
def render_panel(W, H, v, ctx=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x0, y0 = 0.035 * W, 0.04 * H
    pw, ph = 0.36 * W, 0.335 * H
    draw.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), radius=0.018 * W, fill=(0, 0, 0, 130))

    rows = [
        ("速度", f"{v['speed']:.1f}", "km/h", THEME["speed"]),
        ("功率", f"{v['power']:.0f}", "W", THEME["power"]),
        ("心率", f"{v['hr']:.0f}", "bpm", THEME["hr"]),
        ("坡度", f"{v['grade_pct']:+.1f}", "%", grade_color(v["grade_pct"])),
        ("海拔", f"{v['altitude_m']:.0f}", "m", THEME["altitude"]),
        ("距离", f"{v['distance_km']:.1f}", "km", THEME["distance"]),
    ]
    row_h = ph / len(rows)
    pad = 0.014 * W
    f_lab = _font(FONT_CN, 0.030 * H)
    f_val = _font(FONT_NUM, 0.036 * H)
    f_unit = _font(FONT_CN, 0.022 * H)
    for i, (lab, val, unit, color) in enumerate(rows):
        cy = y0 + row_h * (i + 0.5)
        r = 0.008 * W
        draw.ellipse((x0 + pad, cy - r, x0 + pad + 2 * r, cy + r), fill=color)
        draw.text((x0 + pad + 2.6 * r, cy), lab, font=f_lab, fill=C_WHITE, anchor="lm")
        # 数值+单位按实测宽度整体右对齐，保证不与标签/彼此重叠
        vw = draw.textlength(val, font=f_val)
        uw = draw.textlength(unit, font=f_unit)
        x_right = x0 + pw - pad
        draw.text((x_right - vw - uw - 0.006 * W, cy), val, font=f_val, fill=color, anchor="lm")
        draw.text((x_right - uw, cy), unit, font=f_unit, fill=(190, 190, 190, 255), anchor="lm")
    return img


# ---------- 样式 B：Mimo 表盘 + 坡度摆针 + 海拔/距离徽章 ----------
def render_gauges_gradebar(W, H, v, ctx=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy, r = 0.167 * W, 0.24 * H, 0.090 * W
    _gauge_speed(draw, cx, cy, r, v["speed"], THEME["speed"])
    rr = 0.056 * W  # 加大后的功率/心率环
    _ring(draw, 0.105 * W, 0.40 * H, rr, v["power"], 400, THEME["power"], "功率", "W")
    _ring(draw, 0.225 * W, 0.40 * H, rr, v["hr"], 190, THEME["hr"], "心率", "bpm", 1)

    # 坡度摆针条（下移避开圆环）：中心 0%，量程 ±15%，百分数放条右侧
    bx0, bx1, by = 0.055 * W, 0.295 * W, 0.53 * H
    draw.rounded_rectangle((bx0 - 0.012 * W, by - 0.028 * H, bx1 + 0.012 * W, by + 0.028 * H),
                           radius=0.01 * W, fill=(0, 0, 0, 110))
    draw.line((bx0, by, bx1, by), fill=(255, 255, 255, 90), width=max(2, int(0.004 * H)))
    draw.line(((bx0 + bx1) / 2, by - 0.012 * H, (bx0 + bx1) / 2, by + 0.012 * H),
              fill=(255, 255, 255, 160), width=max(2, int(0.003 * W)))
    g = max(-15.0, min(15.0, v["grade_pct"]))
    nx = (bx0 + bx1) / 2 + (g / 15.0) * (bx1 - bx0) / 2
    gc = grade_color(v["grade_pct"])
    draw.polygon([(nx, by - 0.014 * H), (nx - 0.007 * W, by - 0.026 * H),
                  (nx + 0.007 * W, by - 0.026 * H)], fill=gc)
    draw.text((bx1 + 0.025 * W, by), f"{v['grade_pct']:+.1f}%", font=_font(FONT_NUM, 0.028 * H),
              fill=gc, anchor="lm")
    draw.text((bx0, by + 0.034 * H), "坡度 %", font=_font(FONT_CN, 0.018 * H), fill=C_GRAY,
              anchor="la")

    # 徽章：海拔 / 距离
    for j, (lab, val, unit, color) in enumerate([
            ("海拔", f"{v['altitude_m']:.0f}", "m", THEME["altitude"]),
            ("距离", f"{v['distance_km']:.1f}", "km", THEME["distance"])]):
        byy = 0.60 * H + j * 0.062 * H
        draw.rounded_rectangle((0.055 * W, byy, 0.295 * W, byy + 0.05 * H),
                               radius=0.01 * W, fill=(0, 0, 0, 110))
        draw.text((0.068 * W, byy + 0.025 * H), lab, font=_font(FONT_CN, 0.024 * H),
                  fill=C_WHITE, anchor="lm")
        _text_right(draw, (0.245 * W, byy + 0.025 * H), val, _font(FONT_NUM, 0.030 * H), color)
        draw.text((0.252 * W, byy + 0.025 * H), unit, font=_font(FONT_CN, 0.020 * H),
                  fill=(190, 190, 190, 255), anchor="lm")
    return img


# ---------- 样式 C：坡度主角（大号坡度+坡道示意+海拔剖面） ----------
def render_climb_hero(W, H, v, ctx=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    g = v["grade_pct"]
    gc = grade_color(g)

    # 大号坡度 + 坡道斜面示意
    draw.text((0.05 * W, 0.10 * H), "坡度", font=_font(FONT_CN, 0.026 * H), fill=C_GRAY, anchor="la")
    _text_right(draw, (0.30 * W, 0.165 * H), f"{g:+.1f}%", _font(FONT_NUM, 0.105 * W), gc)
    tri_w, base_y = 0.21 * W, 0.30 * H
    ang = math.radians(max(-15.0, min(15.0, g)))
    dx, dy = tri_w, tri_w * math.tan(ang) * 1.6
    draw.polygon([(0.055 * W, base_y), (0.055 * W + dx, base_y - dy), (0.055 * W + dx, base_y)],
                 fill=gc[:3] + (70,))
    draw.line([(0.055 * W, base_y), (0.055 * W + dx, base_y - dy)], fill=gc,
              width=max(3, int(0.005 * W)))

    # 海拔剖面迷你图（全程轨迹 + 当前位置高亮）
    ctx = ctx or {}
    series, ride_span, now_epoch = ctx.get("altitude_series"), ctx.get("ride_span"), ctx.get("now_epoch")
    if series and ride_span:
        bx0, bx1, by0, by1 = 0.05 * W, 0.30 * W, 0.37 * H, 0.455 * H
        draw.rounded_rectangle((bx0 - 0.008 * W, by0 - 0.018 * H, bx1 + 0.008 * W, by1 + 0.030 * H),
                               radius=0.008 * W, fill=(0, 0, 0, 110))
        a_lo = min(a for _, a in series)
        a_hi = max(a for _, a in series)
        span = max(1e-6, ride_span[1] - ride_span[0])
        pts = [(bx0 + (t - ride_span[0]) / span * (bx1 - bx0),
                by1 - (a - a_lo) / max(1e-6, a_hi - a_lo) * (by1 - by0)) for t, a in series]
        draw.line(pts, fill=(170, 140, 255, 200), width=max(2, int(0.0035 * W)))
        if now_epoch is not None:
            frac = max(0.0, min(1.0, (now_epoch - ride_span[0]) / span))
            px = bx0 + frac * (bx1 - bx0)
            py = by1 - (v["altitude_m"] - a_lo) / max(1e-6, a_hi - a_lo) * (by1 - by0)
            pr = 0.007 * W
            draw.ellipse((px - pr, py - pr, px + pr, py + pr), fill=(255, 122, 0, 255))
        draw.text((bx0, by1 + 0.006 * H), "海拔剖面", font=_font(FONT_CN, 0.017 * H),
                  fill=C_GRAY, anchor="la")

    # 底部数据竖列：速度/功率/心率/距离（标签+彩色数值，逐行排布）
    rows = [
        ("速度", f"{v['speed']:.1f}", "km/h", THEME["speed"]),
        ("功率", f"{v['power']:.0f}", "W", THEME["power"]),
        ("心率", f"{v['hr']:.0f}", "bpm", THEME["hr"]),
        ("距离", f"{v['distance_km']:.1f}", "km", THEME["distance"]),
    ]
    f_lab = _font(FONT_CN, 0.020 * H)
    f_val = _font(FONT_NUM, 0.026 * H)
    f_unit = _font(FONT_CN, 0.016 * H)
    col_y = 0.505 * H
    row_h = 0.036 * H
    for i, (lab, val, unit, color) in enumerate(rows):
        cy = col_y + row_h * (i + 0.5)
        draw.text((0.05 * W, cy), lab, font=f_lab, fill=C_GRAY, anchor="lm")
        draw.text((0.115 * W, cy), val, font=f_val, fill=color, anchor="lm")
        uw = draw.textlength(val, font=f_val)
        draw.text((0.115 * W + uw + 0.006 * W, cy), unit, font=f_unit,
                  fill=(185, 185, 185, 255), anchor="lm")
    return img


# ---------- 样式 D：极简电传数据带（顶部横排 6 格） ----------
def render_telemetry_strip(W, H, v, ctx=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cells = [
        (f"{v['distance_km']:.1f}", "km", "距离", THEME["distance"]),
        (f"{v['speed']:.1f}", "km/h", "速度", THEME["speed"]),
        (f"{v['power']:.0f}", "W", "功率", THEME["power"]),
        (f"{v['hr']:.0f}", "bpm", "心率", THEME["hr"]),
        (f"{v['grade_pct']:+.1f}", "%", "坡度", grade_color(v["grade_pct"])),
        (f"{v['altitude_m']:.0f}", "m", "海拔", THEME["altitude"]),
    ]
    y0, strip_h = 0.022 * H, 0.085 * H
    draw.rounded_rectangle((0.015 * W, y0, 0.985 * W, y0 + strip_h), radius=0.012 * W,
                           fill=(0, 0, 0, 95))
    n = len(cells)
    cell_w = (0.985 - 0.015) * W / n
    base_val, base_unit = 0.036 * H, 0.018 * H
    f_lab = _font(FONT_CN, 0.019 * H)
    vy = y0 + strip_h * 0.36
    gap = 0.006 * W
    for i, (val, unit, lab, color) in enumerate(cells):
        cxm = 0.015 * W + cell_w * (i + 0.5)
        # 数值+单位按实测宽度整体居中；超宽自动缩字号，保证不重叠不越格
        f_val, f_unit = _font(FONT_NUM, base_val), _font(FONT_CN, base_unit)
        vw = draw.textlength(val, font=f_val)
        uw = draw.textlength(unit, font=f_unit)
        total = vw + gap + uw
        max_w = cell_w * 0.92
        if total > max_w:
            k = max_w / total
            f_val, f_unit = _font(FONT_NUM, base_val * k), _font(FONT_CN, base_unit * k)
            vw = draw.textlength(val, font=f_val)
            uw = draw.textlength(unit, font=f_unit)
            total = vw + gap + uw
        start = cxm - total / 2
        draw.text((start, vy), val, font=f_val, fill=color, anchor="lm")
        draw.text((start + vw + gap, vy), unit, font=f_unit, fill=(185, 185, 185, 255),
                  anchor="lm")
        _text_center(draw, (cxm, y0 + strip_h * 0.78), lab, f_lab, C_GRAY)
    return img


STYLES = {
    "panel": render_panel,
    "gauges_gradebar": render_gauges_gradebar,
    "climb_hero": render_climb_hero,
    "telemetry_strip": render_telemetry_strip,
}
