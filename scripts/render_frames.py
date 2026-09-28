"""阶段⑤：逐帧渲染 HUD（FIT 线性插值）→ work/hud_frames/clip_N/frame_XXXX.png

values 含 speed/power/hr/distance_km/altitude_m/grade_pct；preset 由 style.preset 决定。
"""

import argparse
import os
from datetime import datetime, timezone

from common import load_config, load_json, save_json, work_path
from fit_extract import grade_series, parse_records
from render_hud import render_frame


def interp(series, ts, conv=lambda v: v, default=0.0):
    """series: [(epoch_sec, value)] 在 ts(epoch_sec) 处线性插值。"""
    prev = next_ = None
    for rt, val in series:
        if rt <= ts:
            prev = (rt, val)
        elif next_ is None:
            next_ = (rt, val)
            break
    if prev is None:
        return conv(next_[1]) if next_ else default
    if next_ is None:
        return conv(prev[1])
    span = next_[0] - prev[0]
    frac = (ts - prev[0]) / span if span > 0 else 0.0
    return conv(prev[1]) * (1 - frac) + conv(next_[1]) * frac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    inventory = {os.path.basename(f["path"]): f
                 for f in load_json(work_path(cfg, "media_inventory.json"))["files"]}
    selection = load_json(work_path(cfg, "selection.json"))
    records = parse_records(cfg["fit_file"])
    offset = float(cfg.get("time_offset_seconds", 0))
    fps = int(cfg["selection"].get("fps", 15))
    canvas = selection.get("canvas")
    if not canvas:
        first = inventory[selection["clips"][0]["file"]]
        canvas = {"width": first["display_width"], "height": first["display_height"]}
    W, H = canvas["width"], canvas["height"]

    out_root = work_path(cfg, "hud_frames")
    os.makedirs(out_root, exist_ok=True)
    total = 0

    # 全字段序列（距离/海拔/坡度），供 panel 等全字段 preset 使用
    gpts = grade_series(records)
    series = {k: [(r["t"].timestamp(), r[k]) for r in records if k in r]
              for k in ("speed", "power", "heart_rate", "distance", "altitude")}
    alt_series = [(t, interp(series["altitude"], t)) for t, _ in gpts[::20]]
    ride_span = (records[0]["t"].timestamp(), records[-1]["t"].timestamp())

    for i, c in enumerate(selection["clips"]):
        out_dir = os.path.join(out_root, f"clip_{i}")
        os.makedirs(out_dir, exist_ok=True)
        dur = c.get("duration", cfg["selection"]["clip_seconds"])
        n_frames = int(round(dur * fps))
        base_epoch = inventory[c["file"]]["start_epoch"] + c["source_start"] + offset
        first = last = None
        for f in range(n_frames):
            ts = base_epoch + f / fps
            values = {
                "speed": interp(series["speed"], ts, lambda v: v * 3.6, 20.0),
                "power": interp(series["power"], ts, default=120.0),
                "hr": interp(series["heart_rate"], ts, default=150.0),
                "distance_km": interp(series["distance"], ts, lambda v: v / 1000, 0.0),
                "altitude_m": interp(series["altitude"], ts, default=0.0),
                "grade_pct": interp(gpts, ts, default=0.0),
            }
            if first is None:
                first = values
            last = values
            ctx = {"altitude_series": alt_series, "ride_span": ride_span, "now_epoch": ts}
            render_frame(W, H, cfg.get("style", {}), values, ctx).save(
                os.path.join(out_dir, f"frame_{f:04d}.png"))
        total += n_frames
        print(f"clip_{i}: {n_frames} 帧  速度 {first['speed']:.1f}->{last['speed']:.1f}  "
              f"功率 {first['power']:.0f}->{last['power']:.0f}  "
              f"心率 {first['hr']:.1f}->{last['hr']:.1f}  "
              f"坡度 {first['grade_pct']:+.1f}->{last['grade_pct']:+.1f}")

    save_json(work_path(cfg, "hud_meta.json"), {"fps": fps, "frames_total": total})
    print(f"\n共 {total} 帧 @ {fps}fps -> {out_root}")


if __name__ == "__main__":
    main()
