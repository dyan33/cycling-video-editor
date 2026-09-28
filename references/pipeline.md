# 流水线详解

## 阶段与数据流

```
ride.yaml
  │
  ├─① probe_media.py      → work/media_inventory.json   素材清单+真实显示方向+时间基准
  ├─② fit_extract.py      → work/fit_windows.json       FIT记录摘要+候选窗口评分
  ├─③ preview_clips.py    → work/selection_preview.png  候选抽帧拼图（⏸ 人工选段停点）
  │     人工确认后写 work/selection.json（schema 见下）
  ├─④ cut_clips.py        → work/clips/clip_N.mp4       旋转感知切片
  ├─⑤ render_frames.py    → work/hud_frames/clip_N/     逐帧 HUD（FIT 线性插值）
  ├─⑥ composite.py        → work/hud_clips/clip_N.mp4   overlay 烧录
  ├─⑦ build_draft.py      → 剪映草稿（须用 jianying-editor venv 运行）
  └─⑧ verify_geometry.py  → work/geometry_check.png     成片帧 vs 旋转解码参考帧像素差
```

`run_pipeline.py --config ride.yaml --to <stage>` 按序跑到指定阶段；`preview` 阶段若 `selection.json` 不存在则打印候选清单并停止（人工确认），存在则跳过继续。

## 工作目录

缺省 `~/Movies/ride-projects/<ride_name>/`（可在 ride.yaml `work_dir` 覆盖）。所有中间产物都在这里，删除工作目录不影响剪映草稿（草稿自包含素材副本）。

## 只改 build 层配置的捷径

BGM/文案/转场/结尾图时长等**只影响草稿组装**的配置变更，无需重跑视频处理链（cut/hud/composite 对同一 selection 产物是幂等重算，重跑纯耗时）。三步：

```bash
# ① 改 ride.yaml（如 bgm.cloud_id）→ ② 重生成 resolved
<skill>/.venv/bin/python -c "import sys; sys.path.insert(0,'<skill>/scripts'); from common import load_config, save_resolved; save_resolved(load_config('<work>/ride.yaml'))"
# ③ 直接单跑 build（jianying venv；verify 可选）
<JY_ROOT>/.venv/bin/python <skill>/scripts/build_draft.py --resolved <work>/config.resolved.json
```

注意：换 BGM 走 `bgm.source: cache` 时需先把歌曲下载到 `~/cloud_cache/<id>_*.m4a`（用 jianying-editor 的 `cloud_manager.py <id>`）。

## media_inventory.json schema

```json
{
  "files": [{
    "path": "...", "size_mb": 62.1, "codec": "hevc",
    "width": 1920, "height": 1440,          // 存储尺寸
    "rotation": -90,                          // 0/±90/180，无则 0
    "display_width": 1440, "display_height": 1920,  // 显示尺寸（旋转后）
    "duration": 11.3,
    "start_epoch": 178..., "start_iso": "...", "time_source": "filename|mtime"
  }],
  "canvas": {"width": 1440, "height": 1920}   // 众数显示尺寸
}
```

**时间基准**：优先文件名 `(\d{14})` 时间戳（DJI/Insta360 惯例，按本地时区），否则文件 mtime（不可靠，建议校准）。`time_offset_seconds` 加到视频时间上对齐码表（相机钟快 30 秒则填 -30）。校准方法：选一段已知爬坡画面，对比 FIT 功率爬升时刻，微调至吻合。

## selection.json schema（人工确认的产物）

```json
{
  "clips": [
    {"file": "DJI_xxx.MP4", "source_start": 84.0, "duration": 4.0, "note": "发卡弯 P360"}
  ],
  "note": "可选备注"
}
```

- `source_start` 是**视频内起点秒**。写好后重跑 `--to verify`。
- 画布自动取第一段的显示尺寸。

## fit_windows.json schema

```json
{
  "summary": {"duration_h": 11.85, "avg_speed_kmh": 26.4, "avg_power_w": 119, "avg_hr_bpm": 145, "climb_m": 1347, "distance_km": null, "start_date": "2026-09-26"},
  "candidates": [{"file": "...", "source_start": 84.0, "score": 0.863, "power": 368.0, "hr": 178.0, "speed_kmh": 17.3, "grade_pct": 7.6, "abs_iso": "...", "has_data": true}]
}
```

评分：`score = (1-grade_weight) × (power_weight×归一化功率 + (1-power_weight)×归一化心率) + grade_weight × 归一化正坡度`；`grade_weight` 默认 0（纯强度分），要突出爬坡时设 0.3~0.5。坡度 top 窗口可能是停车/推车假坡度（V≈0/P≈0），选段时须目检剔除（坑12）。

## HUD 布局

**preset 一览**（ride.yaml `style.preset`）：

| preset | 内容 | 数据字段 |
|---|---|---|
| `mimo`（默认） | 速度半圆盘 + 功率/心率圆环，支持 fields/decimals/theme/position/scale | speed/power/hr |
| `panel` | 数据面板 6 行（色点+标签+数值） | 全部 6 字段 |
| `gauges_gradebar` | Mimo 表盘（环加大）+ 坡度摆针条（±15%）+ 海拔/距离徽章 | 全部 6 字段 |
| `climb_hero` | 大号坡度（颜色分级）+ 坡道斜面示意 + 海拔剖面迷你图 + 数据竖列 | 全部 6 字段 |
| `telemetry_strip` | 顶部横排 6 格数据带（超宽自动缩字号） | 全部 6 字段 |

坡度：`grade_series` 由 ±5s 滑窗海拔差/距离差计算（fit_extract），带符号（+上坡/−下坡），颜色分级 <3 白、3-6 黄、6-9 橙、≥9 红、下坡蓝。

- 速度半圆盘：圆心 `(0.167W, 0.24H)`，半径 `0.090W × scale`；功率/心率圆环：`(0.115W, 0.417H)`、`(0.208W, 0.417H)`，半径 `0.044W × scale`
- position 四角预设：left_top 为基准，right 镜像 x，bottom 镜像 y（mimo 有效）
- 数值格式：decimals 配置；字号随文本长度自动收缩防溢出；数值+单位按实测宽度组合定位防重叠
- 逐帧插值：帧时刻 t 在 FIT 相邻记录间线性插值（速度 m/s→km/h）；记录间隔大时镜头内数值缓变是数据粒度所致，非 bug

## 草稿组装（阶段⑦）

- **必须用 jianying-editor 的 venv 运行**：`<JY_ROOT>/.venv/bin/python <skill>/scripts/build_draft.py --config ... --work-dir ...`（JY_ROOT 探测顺序：`$JY_SKILL_ROOT` → `~/.agents/skills/jianying-editor` → `~/.zcode/skills/jianying-editor`）
- 画布 = selection 首段显示尺寸；save() 后 patch canvas_config（防 wrapper 默认值不符）
- 结尾图：完整原图，`scale = 画布高/图高` 等比全高居中，零裁切
- 文案：title/summary/ending；summary 自动格式 `均速Xkm/h · 爬升Xm · 均功率XW`
- BGM 四来源：cache（`~/cloud_cache/<id>_*.m4a`）/ cloud_id（add_cloud_music 自动下载）/ local / none

## 验收清单（每次必做）

1. `verify_geometry.py` 通过（像素差 <2%）
2. `draft_inspector.py summary --name <草稿>` 段数/轨道数符合预期
3. 用户在剪映打开目检（首次务必确认竖屏/横屏方向正确）
4. 导出：用户在剪映手动导出，比例选"原始"
