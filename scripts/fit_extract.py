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


def grade_series(records, half_window_s=5.0):
    """坡度序列：±half_window_s 滑窗内海拔差/距离差（抗单点噪声）。

    返回 [(epoch_sec, grade_pct)]，供 HUD 逐帧插值。
    """
    pts = [(r["t"].timestamp(), r["distance"], r["altitude"])
           for r in records if "distance" in r and "altitude" in r]
    series = []
    for i, (t, d, a) in enumerate(pts):
        j = i
        while j > 0 and t - pts[j][0] < half_window_s:
            j -= 1
        k = i
        while k < len(pts) - 1 and pts[k][0] - t < half_window_s:
            k += 1
        dd = pts[k][1] - pts[j][1]
        da = pts[k][2] - pts[j][2]
        series.append((t, da / dd * 100 if dd > 2 else 0.0))
    return series


def _interp(points, ts):
    """序列线性插值：ts 为 epoch 秒，points 为 [(epoch_sec, value)]。"""
    if not points:
        return 0.0
    if ts <= points[0][0]:
        return points[0][1]
    if ts >= points[-1][0]:
        return points[-1][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= ts <= t1:
            return v0 if t1 == t0 else v0 + (v1 - v0) * (ts - t0) / (t1 - t0)
    return points[-1][1]


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


def window_stats(records, t0, t1, tol_s, gpts=None):
    """窗口均值；记录稀疏时向两侧扩容差补足。gpts 提供时输出窗口中点坡度。"""
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
    if gpts:
        out["grade_pct"] = round(_interp(gpts, (t0 + (t1 - t0) / 2).timestamp()), 1)
    return out if (out.get("power") is not None or out.get("hr") is not None) else None


def candidates_high_intensity(records, inventory, sel_cfg, offset, gpts=None):
    clip_s = sel_cfg["clip_seconds"]
    step = sel_cfg.get("window_step_seconds", 2.0)
    skip = sel_cfg.get("edge_skip_seconds", 2.0)
    inten = sel_cfg.get("intensity", {})
    pw = inten.get("power_weight", 0.6)
    gw = float(inten.get("grade_weight", 0.0))  # 坡度权重 0~1，默认 0 保持旧行为

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
    # 坡度基准：素材时段内正坡度 P95（抗停车/推车假坡度尖峰，坑12；不用 max）
    g_in_span = [v for t, v in (gpts or []) if t_lo <= t <= t_hi and v > 0]
    if len(g_in_span) >= 5:
        g_hi = sorted(g_in_span)[int(len(g_in_span) * 0.95)]
    else:
        g_hi = max(g_in_span, default=0.0)

    def norm(v, lo, hi):
        return (v - lo) / (hi - lo) if v is not None and hi > lo else 0.0

    out = []
    for f in inventory:
        tol = 6.0
        t = skip
        while t + clip_s <= f["duration"] - skip:
            abs0 = f["start_epoch"] + t + offset
            stats = window_stats(records, datetime.fromtimestamp(abs0, tz=timezone.utc),
                                 datetime.fromtimestamp(abs0 + clip_s, tz=timezone.utc), tol, gpts)
            if stats:
                base = pw * norm(stats["power"], p_lo, p_hi) + (1 - pw) * norm(stats["hr"], h_lo, h_hi)
                grade = stats.get("grade_pct") or 0.0
                score = (1 - gw) * base + gw * min(1.0, max(grade, 0.0) / g_hi if g_hi > 0 else 0.0)
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


def candidates_uniform(records, inventory, sel_cfg, offset, gpts=None):
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
                             datetime.fromtimestamp(abs0 + clip_s, tz=timezone.utc), tol, gpts) or {}
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
    if not inventory_cand:
        biggest = max(f["size_mb"] for f in inventory)
        raise SystemExit(
            f"所有 {len(inventory)} 个素材都超过 max_clip_mb={max_mb}MB，候选为空（坑11）。"
            f"整段长录大文件请在 ride.yaml 调大 max_clip_mb（当前最大素材 {biggest:.0f}MB）")
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
    gpts = grade_series(records)
    if strategy == "uniform":
        cands_all = candidates_uniform(records, inventory_cand, sel_cfg, offset, gpts)
    else:
        cands_all = candidates_high_intensity(records, inventory_cand, sel_cfg, offset, gpts)
    if not cands_all:
        raise SystemExit("素材时段内没有任何含功率/心率的窗口，检查 FIT 是否覆盖素材时段或 time_offset_seconds")
    n_preview = max(sel_cfg["count"] * 2, 10)  # 预览取两倍候选供人工替换
    cands = cands_all[:n_preview]
    if strategy != "uniform":
        # 补充坡度 top 5（去重叠）进预览：强度分与坡度分偏好不同窗口，人工选段需要都看到
        by_grade = sorted(cands_all, key=lambda c: -(c.get("grade_pct") or 0))
        seen = {(c["file"], c["source_start"]) for c in cands}
        for c in by_grade:
            if len(cands) >= n_preview + 5:
                break
            key = (c["file"], c["source_start"])
            if key not in seen:
                cands.append(c)
                seen.add(key)

    for c in cands:
        print(f"{c['score']:.3f}  {c['file'][-16:]} @ {c['source_start']:>7.1f}s  "
              f"P{c.get('power') or '-'}  HR{c.get('hr') or '-'}  V{c.get('speed_kmh') or '-'}  "
              f"G{c.get('grade_pct', 0):+.1f}%")

    out = {"summary": summary, "strategy": strategy, "candidates": cands}
    out_path = work_path(cfg, "fit_windows.json")
    save_json(out_path, out)
    print(f"\n已写入 {out_path}")


if __name__ == "__main__":
    main()
