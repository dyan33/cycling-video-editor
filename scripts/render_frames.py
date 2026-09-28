"""阶段⑤：逐帧渲染 HUD（FIT 线性插值）→ work/hud_frames/clip_N/frame_XXXX.png"""

import argparse
import os
from datetime import datetime, timezone

from common import TZ, load_config, load_json, save_json, work_path
from fit_extract import parse_records
from render_hud import render_frame


def interp(records, key, ts, conv=lambda v: v, default=0.0):
    prev = next_ = None
    for r in records:
        if key not in r:
            continue
        if r["t"] <= ts:
            prev = r
        elif next_ is None:
            next_ = r
            break
    if prev is None:
        return conv(next_[key]) if next_ else default
    if next_ is None:
        return conv(prev[key])
    span = (next_["t"] - prev["t"]).total_seconds()
    frac = (ts - prev["t"]).total_seconds() / span if span > 0 else 0.0
    return conv(prev[key]) * (1 - frac) + conv(next_[key]) * frac


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
    for i, c in enumerate(selection["clips"]):
        out_dir = os.path.join(out_root, f"clip_{i}")
        os.makedirs(out_dir, exist_ok=True)
        dur = c.get("duration", cfg["selection"]["clip_seconds"])
        n_frames = int(round(dur * fps))
        base_epoch = inventory[c["file"]]["start_epoch"] + c["source_start"] + offset
        first = last = None
        for f in range(n_frames):
            ts = datetime.fromtimestamp(base_epoch + f / fps, tz=timezone.utc)
            values = {
                "speed": interp(records, "speed", ts, lambda v: v * 3.6, 20.0),
                "power": interp(records, "power", ts, default=120.0),
                "hr": interp(records, "heart_rate", ts, default=150.0),
            }
            if first is None:
                first = values
            last = values
            render_frame(W, H, cfg.get("style", {}), values).save(
                os.path.join(out_dir, f"frame_{f:04d}.png"))
        total += n_frames
        print(f"clip_{i}: {n_frames} 帧  速度 {first['speed']:.1f}->{last['speed']:.1f}  "
              f"功率 {first['power']:.0f}->{last['power']:.0f}  "
              f"心率 {first['hr']:.1f}->{last['hr']:.1f}")

    save_json(work_path(cfg, "hud_meta.json"), {"fps": fps, "frames_total": total})
    print(f"\n共 {total} 帧 @ {fps}fps → {out_root}")


if __name__ == "__main__":
    main()
