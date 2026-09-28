"""阶段⑦：草稿组装 → 剪映草稿

⚠️ 必须用 jianying-editor 的 venv 运行（pyJianYingDraft 由其 vendor 提供）：
  <jianying-editor>/.venv/bin/python build_draft.py --config ride.yaml --work-dir <dir>
"""

import argparse
import glob
import json
import os
import sys

from common import jianying_editor_root, load_json, load_resolved, work_path

# --- jianying-editor bootstrap（先于 pyJianYingDraft 导入，由其初始化 vendor 路径）---
jy_root = jianying_editor_root()
if not jy_root:
    raise SystemExit("未找到 jianying-editor skill（设 JY_SKILL_ROOT 或安装到 ~/.agents/skills/）")
sys.path.insert(0, os.path.join(jy_root, "scripts"))

from jy_wrapper import JyProject  # noqa: E402
import pyJianYingDraft as draft  # noqa: E402


def auto_texts(fit_summary, texts):
    title = texts.get("title") or f"骑行 · {fit_summary.get('start_date', '')}"
    ending = texts.get("ending")
    if ending in (None, "auto"):
        parts = []
        if fit_summary.get("distance_km"):
            parts.append(f"完骑 {fit_summary['distance_km']}km")
        if fit_summary.get("climb_m"):
            parts.append(f"爬升 {fit_summary['climb_m']}m")
        ending = " · ".join(parts) if parts else "骑行完成"
    if texts.get("summary") in (None, "auto"):
        s_parts = []
        if fit_summary.get("avg_speed_kmh"):
            s_parts.append(f"均速{fit_summary['avg_speed_kmh']}km/h")
        if fit_summary.get("climb_m"):
            s_parts.append(f"爬升{fit_summary['climb_m']}m")
        if fit_summary.get("avg_power_w"):
            s_parts.append(f"均功率{fit_summary['avg_power_w']}W")
        summary = " · ".join(s_parts)
    else:
        summary = texts["summary"]
    return title, summary, ending


def resolve_bgm(bgm_cfg):
    source = (bgm_cfg or {}).get("source", "none")
    if source == "cache":
        path = glob.glob(os.path.expanduser(f"~/cloud_cache/{bgm_cfg.get('cloud_id')}_*.m4a"))
        return path[0] if path else None
    if source == "local":
        p = bgm_cfg.get("local_path")
        return p if p and os.path.exists(p) else None
    return "CLOUD" if source == "cloud_id" else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolved", required=True, help="work_dir/config.resolved.json")
    args = ap.parse_args()
    cfg = load_resolved(args.resolved)

    selection = load_json(work_path(cfg, "selection.json"))
    fit_windows = load_json(work_path(cfg, "fit_windows.json"))
    fit_summary = fit_windows["summary"]
    canvas = selection.get("canvas")
    if not canvas:
        # 回退：从 media_inventory 取第一段显示尺寸
        inv = load_json(work_path(cfg, "media_inventory.json"))
        first = next(f for f in inv["files"]
                     if os.path.basename(f["path"]) == selection["clips"][0]["file"])
        canvas = {"width": first["display_width"], "height": first["display_height"]}

    clip_s = cfg["selection"]["clip_seconds"]
    # 时间线起点按 selection 累计时长（支持混合片段时长），selection 是唯一事实源
    starts, t_acc = [], 0.0
    for c in selection["clips"]:
        starts.append(t_acc)
        t_acc += c.get("duration", clip_s)
    video_total_s = t_acc
    n_clips = len(selection["clips"])
    draft_cfg = cfg.get("draft", {})
    end_s = float(draft_cfg.get("ending_seconds", 6))
    ending_image = cfg.get("ending_image")
    if ending_image:
        ending_image = os.path.abspath(os.path.expanduser(ending_image))
        total_s = video_total_s + end_s
    else:
        total_s = video_total_s

    draft_name = draft_cfg.get("name") or cfg["ride_name"]
    project = JyProject(draft_name, width=canvas["width"], height=canvas["height"], overwrite=True)

    # 1. 主轨：HUD 烧录片段（无 HUD 时为干净切片）
    src_dir = work_path(cfg, "hud_clips") if cfg.get("style", {}).get("enabled", True) \
        else work_path(cfg, "clips")
    segments = []
    for i in range(n_clips):
        dur = selection["clips"][i].get("duration", clip_s)
        seg = project.add_media_safe(os.path.join(src_dir, f"clip_{i}.mp4"),
                                     start_time=f"{starts[i]:.3f}s", duration=f"{dur}s",
                                     track_name="MainVideo")
        if seg is None:
            raise RuntimeError(f"素材导入失败 clip_{i}")
        segments.append(seg)

    # 2. 结尾图：完整原图等比全高居中（零裁切）
    card_start = video_total_s
    if ending_image:
        seg = project.add_media_safe(ending_image, start_time=f"{card_start}s",
                                     duration=f"{end_s}s", track_name="MainVideo")
        if seg is None:
            raise RuntimeError("结尾图导入失败")
        from PIL import Image
        img_h = Image.open(ending_image).size[1]
        scale = canvas["height"] / img_h
        seg.clip_settings = draft.ClipSettings(scale_x=scale, scale_y=scale)
        segments.append(seg)

    # 3. 转场
    trans = draft_cfg.get("transition", "叠化")
    for seg in segments[:-1]:
        project.add_transition_simple(trans, video_segment=seg,
                                      duration=f"{draft_cfg.get('transition_duration', 0.5)}s")

    # 4. 文案
    title, summary, ending = auto_texts(fit_summary, cfg.get("texts", {}))
    title_s = float(draft_cfg.get("title_seconds", 3))
    project.add_text_simple(title, start_time="0.2s", duration=f"{title_s}s", track_name="Titles",
                            anim_in="向上滑动", style=draft.TextStyle(size=8.0),
                            clip_settings=draft.ClipSettings(transform_y=0.62))
    if summary:
        project.add_text_simple(summary, start_time="0.2s", duration="4.5s", track_name="Summary",
                                style=draft.TextStyle(size=4.5),
                                clip_settings=draft.ClipSettings(transform_y=0.38))
    if ending_image:
        project.add_text_simple(ending, start_time=f"{card_start + 0.5}s", duration=f"{end_s - 1}s",
                                track_name="Titles", anim_in="向上滑动",
                                style=draft.TextStyle(size=5.0),
                                clip_settings=draft.ClipSettings(transform_y=-0.72))

    # 5. BGM
    bgm_seg = None
    resolved = resolve_bgm(cfg.get("bgm", {}))
    if resolved == "CLOUD":
        bgm_seg = project.add_cloud_music(cfg["bgm"]["cloud_id"], start_time="0s",
                                          duration=f"{total_s}s", track_name="BGM")
        if bgm_seg is None:
            print("⚠️ 云端 BGM 下载失败，跳过背景音乐")
    elif resolved:
        bgm_seg = project.add_audio_safe(resolved, start_time="0s",
                                         duration=f"{total_s}s", track_name="BGM")
    if bgm_seg is not None:
        bgm_seg.volume = float(cfg.get("bgm", {}).get("volume", 0.7))
        print("[BGM] 已添加")

    project.save()

    # 6. canvas patch（防 wrapper 写入的画布与显示方向不符）
    draft_info = os.path.join(project.draft_dir, "draft_info.json")
    with open(draft_info, encoding="utf-8") as f:
        info = json.load(f)
    old = dict(info.get("canvas_config", {}))
    info["canvas_config"]["width"] = canvas["width"]
    info["canvas_config"]["height"] = canvas["height"]
    with open(draft_info, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)
    print(f"[canvas] {old.get('width')}x{old.get('height')} -> {canvas['width']}x{canvas['height']}")
    print(f"✅ 草稿已保存: {draft_name}（{total_s:.0f}s）  {project.draft_dir}")


if __name__ == "__main__":
    main()
