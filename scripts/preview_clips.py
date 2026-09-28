"""阶段③：候选窗口抽帧拼图（⏸ 人工选段停点）→ work/selection_preview.png

cv2 忽略旋转元数据，抽出的帧是存储方向——按 rotation 旋转到显示方向再拼图（坑0）。
输出打印候选清单与 selection.json 写法指引，然后退出（由人工确认后继续）。
"""

import argparse
import os

import cv2

from common import TZ, load_config, load_json, work_path
from datetime import datetime

THUMB_W = 440


def grab_display_frame(path, sec, rotation):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None
    if int(rotation) % 180 != 0:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE if rotation == 90 else cv2.ROTATE_90_COUNTERCLOCKWISE)
    h, w = frame.shape[:2]
    if w > THUMB_W:
        frame = cv2.resize(frame, (THUMB_W, int(h * THUMB_W / w)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rows", type=int, default=8, help="预览候选数")
    args = ap.parse_args()
    cfg = load_config(args.config)

    inventory = {os.path.basename(f["path"]): f
                 for f in load_json(work_path(cfg, "media_inventory.json"))["files"]}
    windows = load_json(work_path(cfg, "fit_windows.json"))
    cands = windows["candidates"][: args.rows]
    if not cands:
        raise SystemExit("没有候选窗口，先跑 fit_extract")

    selection_path = work_path(cfg, "selection.json")
    if os.path.exists(selection_path):
        print(f"selection.json 已存在，跳过预览（删除后可重新选段）: {selection_path}")
        return

    from PIL import Image, ImageDraw
    rows = []
    for i, c in enumerate(cands):
        meta = inventory[c["file"]]
        frames = []
        for off in (0.0, c.get("clip_mid", 2.0), 3.9):
            img = grab_display_frame(meta["path"], c["source_start"] + off, meta["rotation"])
            if img is not None:
                frames.append(img)
        if not frames:
            continue
        rows.append((i, c, frames))

    cell_w = max(f.shape[1] for _, _, fs in rows for f in fs)
    cell_h = max(f.shape[0] for _, _, fs in rows for f in fs)
    label_w = 330
    grid = Image.new("RGB", (label_w + cell_w * 3 + 40, (cell_h + 8) * len(rows) + 16), (24, 24, 24))
    draw = ImageDraw.Draw(grid)
    y = 8
    for i, c, frames in rows:
        t = datetime.fromisoformat(c["abs_iso"]).astimezone(TZ).strftime("%H:%M:%S")
        draw.text((10, y + 10), f"#{i} {c['file'][-16:]}", fill=(255, 255, 120))
        draw.text((10, y + 30), f"@{c['source_start']}s  {t}", fill=(160, 220, 255))
        draw.text((10, y + 50), f"P{c.get('power') or '-'} HR{c.get('hr') or '-'} "
                                f"V{c.get('speed_kmh') or '-'} score={c.get('score')}", fill=(180, 255, 180))
        x = label_w
        for f in frames:
            grid.paste(Image.fromarray(f), (x, y))
            x += cell_w + 8
        y += cell_h + 8

    out_png = work_path(cfg, "selection_preview.png")
    grid.save(out_png)
    print(f"候选拼图已保存: {out_png}\n")
    print("=== 人工选段 ===")
    print("查看拼图，淘汰遮挡/歪斜/无画面窗口，确认最终片段列表后写")
    print(f"{selection_path}（schema 如下），然后继续 run_pipeline --to verify：")
    print('''{
  "clips": [
    {"file": "DJI_xxx.MP4", "source_start": 84.0, "duration": 4.0, "note": "可选备注"}
  ]
}''')


if __name__ == "__main__":
    main()
