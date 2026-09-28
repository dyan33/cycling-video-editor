"""阶段④：按 selection.json 切片（旋转感知）→ work/clips/clip_N.mp4

目标尺寸 = 画布（selection 首段显示尺寸）。ffmpeg autorotate 先转正再恒等缩放，全帧保留零变形（坑0）。
输出 h264/yuv420p/16 倍数宽，规避 jianying-editor 的整段重转码（坑2）。
"""

import argparse
import os
import subprocess

from common import ffprobe_json, load_config, load_json, work_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    inventory = {os.path.basename(f["path"]): f
                 for f in load_json(work_path(cfg, "media_inventory.json"))["files"]}
    selection = load_json(work_path(cfg, "selection.json"))
    canvas = selection.get("canvas")
    if not canvas:
        first = inventory[selection["clips"][0]["file"]]
        canvas = {"width": first["display_width"], "height": first["display_height"]}
    w, h = canvas["width"], canvas["height"]
    if w % 16:
        w = round(w / 16) * 16  # 16 倍数宽，规避 wrapper normalize
    clip_s = cfg["selection"]["clip_seconds"]

    out_dir = work_path(cfg, "clips")
    os.makedirs(out_dir, exist_ok=True)
    for i, c in enumerate(selection["clips"]):
        src = inventory[c["file"]]["path"]
        out = os.path.join(out_dir, f"clip_{i}.mp4")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", str(c["source_start"]), "-t", str(c.get("duration", clip_s)), "-i", src,
               "-map", "0:v:0", "-map", "0:a?",
               "-vf", f"scale={w}:{h}:flags=lanczos,format=yuv420p",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"切片失败 clip_{i}: {proc.stderr}")
        got = ffprobe_json(out, "stream=width,height").get("streams", [{}])[0]
        print(f"clip_{i}.mp4  {c['file'][-16:]} @ {c['source_start']}s  "
              f"{got.get('width')}x{got.get('height')}  "
              f"({os.path.getsize(out) / 1024 / 1024:.1f}M)")
    print(f"\n切片完成: {out_dir}  画布 {w}x{h}")


if __name__ == "__main__":
    main()
