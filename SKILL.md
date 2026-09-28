---
name: cycling-video-editor
description: 骑行/运动视频自动剪辑流水线：FIT 码表数据 + 运动相机素材 → 剪映草稿。自动精选片段（FIT 功率心率评分）、渲染 DJI Mimo 风格实时数据表盘 HUD（速度/功率/心率逐帧滚动）、叠化转场、BGM、结尾数据图。Use whenever 用户想剪辑骑行/运动视频、把码表数据叠加到视频、做骑行 vlog/运动数据可视化，或提到骑行视频、FIT 文件、功率/心率/速度表盘、运动相机素材剪辑 —— 即使他们没说"自动剪辑"。依赖 jianying-editor skill（草稿生成阶段）。
---

# Cycling Video Editor

把"运动相机素材 + FIT 码表数据"自动剪成带实时数据表盘的剪映草稿。完整流水线与数据 schema 见 [references/pipeline.md](references/pipeline.md)；**踩坑必读** [references/pitfalls.md](references/pitfalls.md)（旋转元数据/TCC 挂起/HEVC/草稿加密，每次几何或卡壳问题先对照它）。

## 工作流（新剪辑任务）

1. **建工作目录与配置**：向用户要三样——素材目录、FIT 文件、目标风格（时长/片段数/文案，有默认值可跳过）。复制 `config/ride.example.yaml` 到工作目录（缺省 `~/Movies/ride-projects/<ride_name>/`）为 `ride.yaml`，填入绝对路径。**FIT 与素材在 Downloads/Desktop 时先请用户移到工作目录**（macOS TCC 会静默挂起读取，pitfalls 坑1）。
2. **环境**：首次运行 `bash <skill>/scripts/bootstrap.sh`（uv 创建 skill 自带 venv）。
3. **跑到选段停点**：
   ```bash
   <skill>/.venv/bin/python <skill>/scripts/run_pipeline.py --config <work>/ride.yaml --to preview
   ```
   产出 `selection_preview.png`（候选窗口抽帧拼图 + FIT 评分）。**人工选段**：查看拼图，淘汰遮挡/歪斜/空旷窗口，写 `work/selection.json`（schema 在拼图输出里打印）。
4. **跑完剩余**：
   ```bash
   <skill>/.venv/bin/python <skill>/scripts/run_pipeline.py --config <work>/ride.yaml --to verify
   ```
   build/verify 阶段自动切换到 jianying-editor 的 venv 执行。
5. **验收**：`verify_geometry` 必须通过（像素差 <2%）；用 jianying-editor 的 `scripts/draft_inspector.py summary --name <草稿名>` 核对结构；请用户在剪映目检方向与表盘。macOS 导出需用户手动，比例选"原始"。

## 阶段速查

| 阶段 | 脚本 | 产物 |
|---|---|---|
| probe | probe_media.py | media_inventory.json（含旋转→显示方向、时间基准） |
| fit | fit_extract.py | fit_windows.json（摘要+候选评分） |
| preview ⏸ | preview_clips.py | selection_preview.png → 人工写 selection.json |
| cut | cut_clips.py | clips/（旋转感知切片） |
| hud | render_frames.py | hud_frames/（FIT 插值逐帧表盘） |
| composite | composite.py | hud_clips/（overlay 烧录） |
| build | build_draft.py | 剪映草稿（含 canvas patch） |
| verify | verify_geometry.py | geometry_check.png + 像素差判定 |

单阶段重跑：`--to <阶段>` 会按序执行其前置；改了配置重跑 probe 起的全部阶段。

## 硬性规则

- **几何只信内容级对比**（verify_geometry），叠加物与容器比例不作数；素材必须查旋转元数据（probe 已内置，画布自动按显示方向）。
- **禁止在 skill 目录写业务脚本/中间产物**——一切进工作目录；skill 目录只改代码与文档。
- 草稿被用户在剪映打开过后不可增量修改，一律 `overwrite=True` 全量重建（pitfalls 坑3）。
- build/verify 阶段必须用 jianying-editor 的 venv（脚本会自动切换，勿手动换环境后报 ImportError）。

## 迭代更新（每次使用后）

1. 实际使用中发现新坑/新需求 → 回写 `references/pitfalls.md`（含现象/原因/解法/教训）或改脚本；
2. `CHANGELOG.md` 记一条，`VERSION` minor+1，git commit；
3. 行为变化影响触发或输出格式时，更新 `tests/test_prompts.md` 并重跑一条真实提示词验证；
4. 用户反馈风格偏好（颜色/位置/字段）→ 若是通用偏好，调 `config/ride.example.yaml` 默认值。
