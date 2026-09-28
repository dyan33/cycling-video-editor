# 踩坑记录（按痛程度排序，★=痛感）

用后回写规则：实际使用中发现新坑 → 追加到对应小节或新增小节 → CHANGELOG 记一条 → VERSION minor+1。
写坑时必须包含：现象 / 原因 / 检测或解法 / 教训。凭猜测的结论不要写进来。

## 坑 0：运动相机旋转元数据——存储横屏、显示竖屏 ★★★★★+

**现象**：ffprobe 报告素材 1920x1440（横屏、SAR 方形），切片后画面横屏；但播放器/剪映预览"原视频"是竖屏的，用户看到剪辑版"被拉伸压扁"。
**原因**：竖持拍摄时相机存储横向帧 + `rotation=-90` 显示矩阵，播放器按元数据旋转显示。`ffmpeg -i src -vf scale=<横屏>` 会先自动旋转（autorotate 默认开）得到竖屏帧、再强行缩放到横屏——内容被压扁 33%。`cv2.imread` 同样忽略旋转，抽帧也是"假横屏"。
**检测**：
```bash
ffprobe -v error -select_streams v:0 -show_entries stream_side_data_list -of json src.MP4
```
**解法**：一切几何决策（画布、切片 scale、HUD 布局）按**显示方向**（存储尺寸 + 旋转）来，不按存储尺寸。
**教训**：几何验证必须做**内容级对比**——从原文件抽"带旋转解码"的参考帧（`ffmpeg -ss t -i src -frames:v 1 ref.png`），与成片帧做排除叠加区后的像素差。**叠加物（HUD 表盘/水印）不能当几何量规**：它们画在输出画布上，底层被压扁它们依然是正圆（本项目曾据此误判两次"无变形"）。

## 坑 1：macOS TCC 权限静默挂起 ★★★★★

**现象**：读 `~/Downloads`、`~/Desktop` 的 Python/cp/osascript 进程 0 CPU、S 状态永久挂起，无任何报错。
**原因**：macOS 隐私权限把未授权的受保护目录读取挂起等授权，弹窗可能不显示。
**解法**：让用户把文件移到项目/工作目录（最快）；或系统设置 → 隐私与安全性 → 文件和文件夹 给 App 授权。
**教训**：进程 0 CPU 挂起 + 无输出 = 优先怀疑 TCC（Downloads/Desktop/Documents/外置盘首次访问）。`~/Movies` 实测不受限。

## 坑 2：HEVC/10bit 素材触发 jianying-editor 整段重转码 ★★★★★

**现象**：导入大素材时脚本长时间无响应，发现 ffmpeg 在整段重转码（几十分钟 4K）。
**原因**：jianying-editor 的 `normalize_video_for_jianying` 对非 h264/yuv420p 素材整段重编码，且固定 `scale=1920:1080 + pad`——非 16:9 素材会被 pad 出黑边。
**解法**：本 skill 的切片输出刻意用 `h264 + yuv420p + 宽为16倍数`，使 wrapper 的 `should_normalize` 判 False，导入零转码。
**教训**：任何素材导入前先 `ffprobe codec_name pix_fmt`。HEVC/yuv420p10le 是雷。

## 坑 3：剪映打开后草稿 JSON 被加密 + 多时间线架构 ★★★★

**现象**：`draft_info.json` 生成时是明文，用户在剪映打开过后变加密，程序无法再读写；新版剪映还会生成 `Timelines/<uuid>/`（加密副本）与 `timeline_layout.json`。
**解法**：所有草稿修改走 `overwrite=True` 全量重建（重建会清掉整个旧目录含 Timelines/，剪映重开时从明文根 JSON 重新迁移）。验收用 draft_inspector 在"生成后、打开前"做。
**线索**：`Timelines/<uuid>/draft_cover.jpg` 与 `template.tmp` 是明文，可用于验证剪映实际渲染。

## 坑 4：剪映同轨片段/文本时间重叠直接抛异常 ★★★

**现象**：`SegmentOverlap` 崩溃。
**解法**：时间上会重叠的元素分不同 track_name（本 skill 的数据条/HUD 靠"每镜头一个不重叠时间段"天然安全；文字层多文案用不同轨道）。

## 坑 5：add_text_simple 参数陷阱 ★★

- `font_size`/`color_rgb` 不是有效参数（kwargs 过滤静默忽略）。正确：`style=draft.TextStyle(size=, bold=, color=)`、位置 `clip_settings=draft.ClipSettings(transform_x=, transform_y=)`、入场动画 `anim_in=`。
- transform_y 单位是"半个画布高"，0.62≈顶部、-0.8≈底部字幕。

## 坑 6：BGM 云端直链过期 403 ★★

**解法**：jianying-editor 的 CloudManager 会自动换新链接重试；成功后缓存在 `~/cloud_cache/<id>_*.m4a`，之后直接 `add_audio_safe(缓存路径)` 免下载（bgm.source: cache 即此逻辑）。

## 坑 7：杂项 ★

- `ffprobe -of csv=p=0` 输出带尾逗号，split 后过滤空串
- `uv run` 偶发挂起，直接用 `.venv/bin/python` 更稳
- 视觉模型看图会幻觉细节（位置/比例），几何与数值结论必须代码测量，且量规必须是"底层画面 vs 原始参考帧"，不能是叠加物
- 外置盘素材时：复制进草稿目录（jianying-editor 的 _stage_local_asset 已处理）保证草稿自包含

## 坑 8：外置盘大小写敏感的扩展名匹配 ★★★（1.0.0 测试中发现）

**现象**：glob `*.mp4` 返回 0 个文件，但 `ls` 明明看得到 28 个 `.MP4`；调试时"一会儿读得到一会儿读不到"，极具迷惑性。
**原因**：外置盘可能是**大小写敏感**文件系统，DJI 惯例 `.MP4` 大写扩展名；调试时把大小写两种 glob 求和打印会掩盖单分支为 0 的事实。
**解法**：glob 目录下全部文件后按 `f.lower().endswith(视频扩展名)` 过滤（probe_media 已内置）。

## 坑 9：selection 时间线用 `i × 片段时长` 排布 ★★（1.0.0 测试中发现）

**现象**：混合片段时长（精华 3s + 高强度 4s）时后续片段时间错位、互相重叠。
**解法**：时间线起点按 selection 顺序**累加时长**（build_draft 已内置），selection.json 是时间线唯一事实源。
**教训**：新增可配字段后，所有派生量（时间线/BGM 时长/文案位置）都要改为从数据推导，不留"等长假设"。
