"""阶段⑧：几何终验 —— 成片帧 vs 原素材旋转解码参考帧的像素差。

⚠️ 用 jianying-editor 的 venv 运行（需要 Pillow 供 HUD 掩码计算，且与 build 同环境）。
  <jianying-editor>/.venv/bin/python verify_geometry.py --resolved .../config.resolved.json
通过标准：排除 HUD 区域后平均绝对差 < 2%（纯编码噪声水平）。
"""

import argparse
import os
import subprocess

import cv2
import numpy as np

from common import jianying_editor_root, load_resolved, work_path

MAD_THRESHOLD = 2.0  # %


def hud_mask(shape, style):
    """按 HUD 布局生成排除掩码（表盘外接区域，宽裕 20%）。"""
    from render_hud import layout
    H, W = shape[:2]
    lay = layout(W, H, style.get("position", "left_top"), float(style.get("scale", 1.0)))
    mask = np.ones((H, W), bool)
    x0 = min(v[0] for v in lay.values())
    x1 = max(v[0] for v in lay.values())
    y0 = min(v[1] for v in lay.values())
    y1 = max(v[1] for v in lay.values())
    r = max(v[2] for v in lay.values())
    # 速度盘在上方、圆环在下方：外接框取 y0-盘径 到 y1+环径，x0-盘径 到 x1+环径
    pad_x = r * 2.5
    mask[max(0, int(y0 - r * 2.5)):int(y1 + r * 2.2), max(0, int(x0 - pad_x)):int(x1 + pad_x)] = False
    return mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolved", required=True)
    args = ap.parse_args()
    cfg = load_resolved(args.resolved)

    selection = load_json_work(cfg, "selection.json")
    inventory = {os.path.basename(f["path"]): f
                 for f in load_json_work(cfg, "media_inventory.json")["files"]}
    first = selection["clips"][0]
    src = inventory[first["file"]]["path"]

    ref_png = work_path(cfg, "ref_rotated.png")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(first["source_start"]), "-i", src, "-frames:v", "1", ref_png],
                   check=True)
    ref = cv2.imread(ref_png)

    cap = cv2.VideoCapture(work_path(cfg, "hud_clips", "clip_0.mp4"))
    ok, ours = cap.read()
    cap.release()
    assert ok and ref is not None, "帧读取失败"
    assert ref.shape == ours.shape, f"尺寸不一致: ref={ref.shape} ours={ours.shape}"

    mask = hud_mask(ours.shape, cfg.get("style", {}))
    diff = np.abs(ref.astype(np.int16) - ours.astype(np.int16)).sum(axis=2)
    mad_pct = float(diff[mask].mean()) / 765 * 100
    print(f"参考帧 {ref.shape[1]}x{ref.shape[0]}；非 HUD 区平均绝对差 {mad_pct:.2f}%（阈值 {MAD_THRESHOLD}%）")

    compare = np.concatenate([ref, ours], axis=1)
    cv2.imwrite(work_path(cfg, "geometry_check.png"), compare)

    if mad_pct < MAD_THRESHOLD:
        print("✅ 几何一致，无拉伸")
    else:
        raise SystemExit("❌ 内容几何与原素材不一致——检查画布方向/切片 scale（坑0）")


def load_json_work(cfg, name):
    import json
    with open(work_path(cfg, name), encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
