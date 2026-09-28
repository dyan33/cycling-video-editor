"""公共工具：配置加载、工作目录、ffprobe、时间基准。"""

import glob
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))  # 默认本地时区（Asia/Shanghai）；文件名时间戳按此时区解析

FILENAME_TS_RE = re.compile(r"(20[2-9]\d[01]\d[0-3]\d[0-2]\d[0-5]\d[0-5]\d)")


def skill_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path):
    """仅在自带 venv 中调用（依赖 PyYAML）。跨 venv 阶段用 save_resolved/load_resolved。"""
    import yaml
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg.get("footage_dir") or not cfg.get("fit_file"):
        raise SystemExit("ride.yaml 缺少 footage_dir / fit_file")
    if cfg.get("work_dir"):
        cfg["work_dir"] = os.path.abspath(os.path.expanduser(cfg["work_dir"]))
    else:
        cfg["work_dir"] = os.path.abspath(os.path.expanduser(
            f"~/Movies/ride-projects/{cfg['ride_name']}"))
    os.makedirs(cfg["work_dir"], exist_ok=True)
    return cfg


def save_resolved(cfg):
    """把配置快照写入工作目录，供 jianying-editor venv 下的阶段读取（无 yaml 依赖）。"""
    save_json(work_path(cfg, "config.resolved.json"), {"work_dir": cfg["work_dir"], "config": cfg})


def load_resolved(path):
    """读取 save_resolved 的产物，返回含 work_dir 的配置 dict。"""
    data = load_json(path)
    cfg = data["config"]
    cfg["work_dir"] = data["work_dir"]
    return cfg


def resolved_path(cfg):
    return work_path(cfg, "config.resolved.json")


def work_path(cfg, *parts):
    return os.path.join(cfg["work_dir"], *parts)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ffprobe_json(path, entries):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", entries, "-of", "json", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {}
    return json.loads(proc.stdout or "{}")


def video_start_epoch(path, time_source="auto"):
    """视频开始时刻（epoch 秒）。filename 模式解析文件名 14 位时间戳，否则 mtime。"""
    name = os.path.basename(path)
    use_filename = time_source == "filename" or (
        time_source == "auto" and FILENAME_TS_RE.search(name))
    m = FILENAME_TS_RE.search(name) if use_filename else None
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=TZ)
            return dt.timestamp(), "filename"
        except ValueError:
            pass
    return os.path.getmtime(path), "mtime"


def rotate_display(width, height, rotation):
    """存储尺寸 + 旋转角 → 显示尺寸（±90 交换宽高）。"""
    if int(rotation or 0) % 180 != 0:
        return height, width
    return width, height


def jianying_editor_root():
    """探测 jianying-editor skill 根目录。"""
    candidates = [
        os.environ.get("JY_SKILL_ROOT", "").strip(),
        os.path.expanduser("~/.agents/skills/jianying-editor"),
        os.path.expanduser("~/.zcode/skills/jianying-editor"),
        os.path.join(os.getcwd(), ".agents", "skills", "jianying-editor"),
        os.path.join(os.getcwd(), ".zcode", "skills", "jianying-editor"),
    ]
    for p in candidates:
        if p and os.path.exists(os.path.join(p, "scripts", "jy_wrapper.py")):
            return p
    return None


def find_bgm_local(cloud_id):
    hits = glob.glob(os.path.expanduser(f"~/cloud_cache/{cloud_id}_*"))
    return hits[0] if hits else None
