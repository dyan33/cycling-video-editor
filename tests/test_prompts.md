# 测试提示词（skill-creator 迭代循环用）

每个提示词在新的 ZCode 会话中测试：观察触发是否命中、配置询问是否到位、停点行为、成品验收。
跑完后把结果与问题记到 CHANGELOG，修完 bump VERSION。

## T1 标准新任务（触发 + 全流程）

> 帮我把 /Volumes/1TB/骑行素材/蒲虹路_20260926 的素材和 ~/ride-0-2026-09-26-07-31-02.fit 剪个 30 秒左右的竖屏骑行视频，要有功率心率速度表盘

预期：询问/默认配置 → 建工作目录与 ride.yaml → bootstrap → --to preview 停点 → 请求人工选段。

## T2 数据叠加为主（已有视频只要表盘）

> 我有一段骑行视频想加上码表数据，功率心率速度那种 Mimo 风格的表盘，素材在 ./footage，FIT 是 ./ride.fit

预期：触发本 skill；确认片段数与时长后走完整流水线；注意 fit_file/footage_dir 路径展开。

## T3 续跑/迭代（断点 + 参数修改）

> 上次的骑行视频项目（~/Movies/ride-projects/puhonglu_20260926），把选段换成第 2、4、7 个候选，BGM 换成舒缓一点的，重新生成草稿

预期：不重跑 probe/fit；直接改 selection.json 与 ride.yaml 的 bgm/texts；从 cut 阶段继续到 verify。

## T4 边界（无 FIT / 横屏素材）

> 只有素材没有 FIT 文件，能剪个不带数据表盘的精华集锦吗

预期：如实告知本 skill 依赖 FIT（表盘与时间对齐均需要）；可降级为 style.enabled=false 的纯剪辑（uniform 选段），或引导走 jianying-editor 常规剪辑。
