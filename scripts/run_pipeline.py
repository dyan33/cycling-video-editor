"""流水线驱动：按序执行阶段，支持 --to 断点与选段人工停点。

用法（自带 venv）：
  .venv/bin/python run_pipeline.py --config ride.yaml --to preview   # 跑到选段停点
  # 人工确认后写 selection.json
  .venv/bin/python run_pipeline.py --config ride.yaml --to verify    # 跑完剩余全部

阶段：probe → fit → preview(停点) → cut → hud → composite → build → verify
build/verify 自动切换到 jianying-editor 的 venv 执行（pyJianYingDraft 所在环境）。
"""

import argparse
import os
import subprocess
import sys

from common import jianying_editor_root, load_config, resolved_path, save_resolved, skill_root, work_path

ORDER = ["probe", "fit", "preview", "cut", "hud", "composite", "build", "verify"]
JY_STAGES = {"build", "verify"}  # 需要 jianying-editor venv 的阶段


def run_stage(stage, cfg):
    if stage == "build" or stage == "verify":
        jy = jianying_editor_root()
        if not jy:
            raise SystemExit(f"阶段 {stage} 需要 jianying-editor skill 未找到")
        python = os.path.join(jy, ".venv", "bin", "python")
        if not os.path.exists(python):
            raise SystemExit(f"jianying-editor venv 不存在: {python}（先在该 skill 里建环境）")
        script = os.path.join(skill_root(), "scripts", f"{'build_draft' if stage == 'build' else 'verify_geometry'}.py")
        cmd = [python, script, "--resolved", resolved_path(cfg)]
    else:
        script = os.path.join(skill_root(), "scripts", f"{stage_to_script(stage)}.py")
        cmd = [sys.executable, script, "--config", cfg["__config_path"]]

    print(f"\n=== 阶段 {stage} ===")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit(f"阶段 {stage} 失败（exit {proc.returncode}）")


def stage_to_script(stage):
    return {"probe": "probe_media", "fit": "fit_extract", "preview": "preview_clips",
            "cut": "cut_clips", "hud": "render_frames", "composite": "composite"}.get(stage, stage)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="ride.yaml 路径")
    ap.add_argument("--to", default="verify", help=f"跑到哪个阶段: {' → '.join(ORDER)}")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cfg["__config_path"] = os.path.abspath(args.config)
    save_resolved(cfg)

    target = args.to
    if target not in ORDER:
        raise SystemExit(f"未知阶段 {target}，可选: {ORDER}")

    for stage in ORDER[: ORDER.index(target) + 1]:
        if stage == "preview":
            sel = work_path(cfg, "selection.json")
            if os.path.exists(sel):
                print(f"\n=== 阶段 preview（selection.json 已存在，跳过人工停点）===")
                continue
            run_stage("preview", cfg)
            print("\n⏸ 选段停点：查看 selection_preview.png，写 selection.json 后执行：")
            print(f"  {sys.executable} {os.path.abspath(__file__)} --config {args.config} --to cut")
            return
        run_stage(stage, cfg)

    print("\n✅ 流水线完成。验收清单见 references/pipeline.md（几何验证 + draft_inspector + 剪映目检）。")


if __name__ == "__main__":
    main()
