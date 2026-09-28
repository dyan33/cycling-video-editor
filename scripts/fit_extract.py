"""阶段②：FIT 解析 + 候选窗口评分 → work/fit_windows.json

- 解析 record 消息（时间戳/速度/功率/心率/海拔）
- 全程摘要（均速/爬升/均功率/均心率/距离/日期）供文案与汇总卡
- 两种选段策略：
  high_intensity: 滑窗评分 = pw*归一化功率 + (1-pw)*归一化心率，去重叠取 top
  uniform:        按素材时间均匀取窗口（覆盖全天行程）
"""

import argparse
import os
from datetime import datetime, timedelta, timezone

import fitdecode

from common import TZ, load_config, load_json, save_json, work_path

FIELDS = ("speed", "power", "heart_rate", "distance", "altitude")


def parse_records(fit_path):
    records = []
    with fitdecode.FitReader(fit_path) as fit:
        for frame in fit:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA or frame.name != "record":
                continue
            row = {}
            for field in frame.fields:
                if field.name == "timestamp" and field.value is not None:
                    row["t"] = field.value
                elif field.name in FIELDS and field.value is not None:
                    row[field.name] = field.value
            if "t" in row:
                records.append(row)
    records.sort(key=lambda r: r["t"])
    return records


def summarize(records):
    n = len(records)
    span = (records[-1]["t"] - records[0]["t"]).total_seconds() if n > 1 else 0
    speeds = [r["speed"] * 3.6 for r in records if "speed" in r]
    powers = [r["power"] for r in records if "power" in r]
    hrs = [r["heart_rate"] for r in records if "heart_rate" in r]
    alts = [r["altitude"] for r in records if "altitude" in r]
    dists = [r["distance"] / 1000 for r in records if "distance" in r]

    climb = sum(b - a for a, b in zip(alts, alts[1:]) if b > a)
    return {
        "duration_h": round(span / 3600, 2),
        "avg_speed_kmh": round(sum(speeds) / len(speeds), 1) if speeds else None,
        "avg_power_w": round(sum(powers) / len(powers)) if powers else None,
        "avg_hr_bpm": round(sum(hrs) / len(hrs)) if hrs else None,
        "climb_m": round(climb) if alts else None,
        "distance_km": round(max(dists), 1) if dists else None,
        "start_date": records[0]["t"].astimezone(TZ).strftime("%Y.%m.%d"),
    }


def window_stats(records, t0, t1, tol_s):
    """窗口均值；记录稀疏时向两侧扩容差补足。"""
    sel = [r for r in records if t0 <= r["t"] < t1]
    if len(sel) < 2:
        mid = t0 + (t1 - t0) / 2
        sel = [r for r in records if abs((r["t"] - mid).total_seconds()) <= tol_s]
    if len(sel) < 2:
        return None
    out = {}
    for key, conv, label in (("power", lambda v: v, "power"),
                             ("heart_rate", lambda v: v, "hr"),
                             ("speed", lambda v: v * 3.6, "speed_kmh")):
        vals = [conv(r[key]) for r in sel if key in r]
        out[label] = round(sum(vals) / len(vals), 1) if vals else None
    return out if (out.get("power") is not None or out.get("hr") is not None) else None


def candidates_high_intensity(records, inventory, sel_cfg, offset):
    clip_s = sel_cfg["clip_seconds"]
    step = sel_cfg.get("window_step_seconds", 2.0)
    skip = sel_cfg.get("edge_skip_seconds", 2.0)
    pw = sel_cfg.get("intensity", {}).get("power_weight", 0.6)

    # 归一化基准：素材时段内 P10~MAX
    t_lo = min(f["start_epoch"] for f in inventory)
    t_hi = max(f["start_epoch"] + f["duration"] for f in inventory)
    in_span = [r for r in records if t_lo <= r["t"].timestamp() <= t_hi]
    powers = sorted(r["power"] for r in in_span if "power" in r)
    hrs = sorted(r["heart_rate"] for r in in_span if "heart_rate" in r)
    p_lo = powers[len(powers) // 10] if powers else 0
    p_hi = powers[-1] if powers else 1
    h_lo = hrs[len(hrs) // 10] if hrs else 0
    h_hi = hrs[-1] if hrs else 1

    def norm(v, lo, hi):
        return (v - lo) / (hi - lo) if v is not None and hi > lo else 0.0

    out = []
    for f in inventory:
        tol = 6.0
        t = skip
        while t + clip_s <= f["duration"] - skip:
            abs0 = f["start_epoch"] + t + offset
            stats = window_stats(records, datetime.fromtimestamp(abs0, tz=timezone.utc),
                                 datetime.fromtimestamp(abs0 + clip_s, tz=timezone.utc), tol)
            if stats:
                score = pw * norm(stats["power"], p_lo, p_hi) + (1 - pw) * norm(stats["hr"], h_lo, h_hi)
                out.append({"file": os.path.basename(f["path"]), "source_start": round(t, 2),
                            "score": round(score, 4), **stats,
                            "abs_iso": datetime.fromtimestamp(abs0, tz=TZ).isoformat(),
                            "has_data": True})
            t += step

    out.sort(key=lambda c: -c["score"])
    picked = []
    for c in out:  # 同视频去重叠
        if all(c["file"] != p["file"] or abs(c["source_start"] - p["source_start"]) >= clip_s
               for p in picked):
            picked.append(c)
    return picked


def candidates_uniform(records, inventory, sel_cfg, offset):
    clip_s = sel_cfg["clip_seconds"]
    skip = sel_cfg.get("edge_skip_seconds", 2.0)
    n = sel_cfg["count"]
    files = sorted(inventory, key=lambda f: f["start_epoch"])
    idx = sorted({round(i * (len(files) - 1) / max(1, n - 1)) for i in range(n)})[:n]

    tol = sel_cfg.get("window_step_seconds", 2.0) + clip_s / 2 + 4
    out = []
    for rank, i in enumerate(idx):
        f = files[i]
        start = max(skip, (f["duration"] - clip_s) / 2.0)
        abs0 = f["start_epoch"] + start + offset
        stats = window_stats(records, datetime.fromtimestamp(abs0, tz=timezone.utc),
                             datetime.fromtimestamp(abs0 + clip_s, tz=timezone.utc), tol) or {}
        out.append({"file": os.path.basename(f["path"]), "source_start": round(start, 2),
                    "score": round(1.0 - rank * 0.01, 3), **stats,
                    "abs_iso": datetime.fromtimestamp(abs0, tz=TZ).isoformat(),
                    "has_data": bool(stats)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    inventory = load_json(work_path(cfg, "media_inventory.json"))["files"]
    max_mb = cfg.get("max_clip_mb", 300)
    # 候选只从限内素材产生（超大文件切片慢且常是长素材）；用户手选 selection 不受限
    inventory_cand = [f for f in inventory if f["size_mb"] <= max_mb]
    records = parse_records(cfg["fit_file"])
    if not records:
        raise SystemExit("FIT 中没有 record 消息")
    summary = summarize(records)
    print(f"FIT records: {len(records)}  范围 {records[0]['t'].astimezone(TZ)} ~ "
          f"{records[-1]['t'].astimezone(TZ)}")
    print("摘要:", summary)

    sel_cfg = cfg["selection"]
    offset = float(cfg.get("time_offset_seconds", 0))
    strategy = sel_cfg.get("strategy", "high_intensity")
    if strategy == "uniform":
        cands = candidates_uniform(records, inventory_cand, sel_cfg, offset)
    else:
        cands = candidates_high_intensity(records, inventory_cand, sel_cfg, offset)
    cands = cands[: max(sel_cfg["count"] * 2, 10)]  # 预览取两倍候选供人工替换

    for c in cands:
        print(f"{c['score']:.3f}  {c['file'][-16:]} @ {c['source_start']:>7.1f}s  "
              f"P{c.get('power') or '-'}  HR{c.get('hr') or '-'}  V{c.get('speed_kmh') or '-'}")

    out = {"summary": summary, "strategy": strategy, "candidates": cands}
    out_path = work_path(cfg, "fit_windows.json")
    save_json(out_path, out)
    print(f"\n已写入 {out_path}")


if __name__ == "__main__":
    main()
