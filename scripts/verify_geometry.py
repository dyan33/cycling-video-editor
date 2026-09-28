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
    """按真实渲染的 HUD alpha 通道生成排除掩码（内容级事实，适配所有 preset）。

    用最宽数值渲染一帧，文本外扩必然被覆盖；渲染失败回退 mimo 布局外接框。
    （坑10：旧版只按 mimo 表盘布局取外接框，gauges_gradebar 的坡度条/徽章
    延伸到 0.70H，超出掩码底 0.57H，被计入像素差导致几何校验误报 FAIL。）
    """
    H, W = shape[:2]
    try:
        from render_hud import render_frame
        # 最宽数值：位数最多时文本最宽（-15.0% / 999.9 / 9999）
        values = {"speed": 60.0, "power": 400.0, "hr": 190.0,
                  "distance_km": 999.9, "altitude_m": 9999.0, "grade_pct": -15.0}
        ctx = {"altitude_series": [(0, 0.0), (1, 100.0)], "ride_span": (0, 1), "now_epoch": 0.5}
        hud = render_frame(W, H, style, values, ctx)
        alpha = np.array(hud.split()[-1])
        covered = (alpha > 0).astype(np.uint8)
        covered = cv2.dilate(covered, np.ones((61, 61), np.uint8))  # 外扩 ~30px
        return covered == 0
    except Exception as e:  # noqa: BLE001 渲染失败不应阻断几何校验
        print(f"⚠️ HUD alpha 掩码生成失败（{e}），回退 mimo 布局外接框")
    from render_hud import layout
    lay = layout(W, H, style.get("position", "left_top"), float(style.get("scale", 1.0)))
    mask = np.ones((H, W), bool)
    x0 = min(v[0] for v in lay.values())
    x1 = max(v[0] for v in lay.values())
    y0 = min(v[1] for v in lay.values())
    y1 = max(v[1] for v in lay.values())
    r = max(v[2] for v in lay.values())
    # 速度盘在上方、圆环在下方：外接框取 y0-盘径 到 y1+环径，x0-盘径 到 x1+盘径
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
