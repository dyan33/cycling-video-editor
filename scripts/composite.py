"""阶段⑥：HUD 帧序列 overlay 烧录 → work/hud_clips/clip_N.mp4"""

import argparse
import os
import subprocess

from common import load_config, load_json, work_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    selection = load_json(work_path(cfg, "selection.json"))
    fps = int(cfg["selection"].get("fps", 15))
    frames_root = work_path(cfg, "hud_frames")
    clips_dir = work_path(cfg, "clips")
    out_dir = work_path(cfg, "hud_clips")
    os.makedirs(out_dir, exist_ok=True)

    if not cfg.get("style", {}).get("enabled", True):
        print("style.enabled=false，跳过烧录，直接复用 clips/")
        for f in os.listdir(clips_dir):
            os.link(os.path.join(clips_dir, f), os.path.join(out_dir, f))
        return

    n = len(selection["clips"])
    for i in range(n):
        src = os.path.join(clips_dir, f"clip_{i}.mp4")
        frames = os.path.join(frames_root, f"clip_{i}", "frame_%04d.png")
        out = os.path.join(out_dir, f"clip_{i}.mp4")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-i", src, "-framerate", str(fps), "-i", frames,
               "-filter_complex", "[0:v][1:v]overlay=0:0",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"overlay 失败 clip_{i}: {proc.stderr}")
        print(f"clip_{i}.mp4 ({os.path.getsize(out) / 1024 / 1024:.1f}M)")
    print(f"\n烧录完成: {out_dir}")


if __name__ == "__main__":
    main()
