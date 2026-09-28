"""阶段①：素材探测 → work/media_inventory.json

逐文件读取存储尺寸、旋转角、编码、时长，推导真实显示方向；
时间基准优先文件名时间戳（DJI 等惯例），回退 mtime（坑：旋转元数据见 references/pitfalls.md 坑0）。
"""

import argparse
import glob
import os

from common import ffprobe_json, load_config, rotate_display, save_json, video_start_epoch, work_path

VIDEO_EXTS = (".mp4", ".mov", ".m4v")


def probe_one(path, time_source):
    info = ffprobe_json(path, "stream=codec_name,width,height,duration:stream_side_data_list")
    streams = info.get("streams") or []
    if not streams:
        return None
    s = streams[0]
    width, height = int(s["width"]), int(s["height"])
    rotation = 0
    for sd in s.get("side_data_list") or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    disp_w, disp_h = rotate_display(width, height, rotation)
    duration = float(s.get("duration") or 0)
    if duration <= 0:  # 个别流不带 duration，再查 format
        fmt = ffprobe_json(path, "format=duration").get("format", {})
        duration = float(fmt.get("duration") or 0)
    epoch, ts_source = video_start_epoch(path, time_source)
    return {
        "path": path,
        "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
        "codec": s.get("codec_name"),
        "width": width, "height": height,
        "rotation": rotation,
        "display_width": disp_w, "display_height": disp_h,
        "duration": round(duration, 2),
        "start_epoch": epoch,
        "start_iso": __import__("datetime").datetime.fromtimestamp(
            epoch, tz=__import__("common").TZ).isoformat(),
        "time_source": ts_source,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    # 大小写无关匹配（外置盘可能是大小写敏感文件系统，DJI 惯例 .MP4 大写）
    # 全量清点（不按体积过滤）：ffprobe 成本极低，且用户确认的选段可引用任何文件
    all_files = glob.glob(os.path.join(cfg["footage_dir"], "*"))
    files = sorted(f for f in all_files if f.lower().endswith(VIDEO_EXTS))

    inventory = []
    for f in files:
        item = probe_one(f, cfg.get("time_source", "auto"))
        if item:
            inventory.append(item)
            print(f"{os.path.basename(f)}  {item['width']}x{item['height']} rot={item['rotation']} "
                  f"显示 {item['display_width']}x{item['display_height']}  "
                  f"{item['duration']}s  {item['size_mb']}M  [{item['time_source']}]")
        else:
            print(f"⚠️ 无法探测: {f}")

    if not inventory:
        raise SystemExit("没有可用素材")

    # 画布 = 众数显示尺寸
    dims = {}
    for it in inventory:
        key = (it["display_width"], it["display_height"])
        dims[key] = dims.get(key, 0) + 1
    canvas_w, canvas_h = max(dims, key=dims.get)

    out = {"files": inventory, "canvas": {"width": canvas_w, "height": canvas_h}}
    out_path = work_path(cfg, "media_inventory.json")
    save_json(out_path, out)
    mixed = len(dims) > 1
    print(f"\n共 {len(inventory)} 个素材；画布（众数显示尺寸）{canvas_w}x{canvas_h}"
          + ("⚠️ 素材显示方向不一致，取众数" if mixed else ""))
    print(f"已写入 {out_path}")


if __name__ == "__main__":
    main()
