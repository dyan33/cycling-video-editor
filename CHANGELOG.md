# Changelog

## 1.1.1 (2026-09-28)
- fix: verify_geometry 的 HUD 排除掩码改为按当前 preset 真实渲染一帧（最宽数值）取 alpha 外扩 30px 生成，渲染失败回退原 mimo 外接框；修复 gauges_gradebar 等扩展样式的坡度条/徽章超出 mimo 外接框导致的几何误报（蒲虹路 50s 真实任务 2.75% → 1.85% 通过）。已回写坑10。

## 1.1.0 (2026-09-28)
- 新增 4 组数据样式 preset（hud_styles.py）：panel 数据面板 / gauges_gradebar 表盘坡度条 / climb_hero 坡度主角（坡道示意+海拔剖面）/ telemetry_strip 顶部数据带
- 新增数据字段：距离、海拔、坡度（±5s 滑窗海拔差/距离差，带符号颜色分级）
- style.preset 配置项选择样式；render_frame 按 preset 分发；数值+单位按实测宽度组合定位防重叠，超宽自动缩字号
- 经 4 组变体草稿真实出片验证（用户逐样式目检并反馈 3 轮排版问题，已全部修复）

## 1.0.0 (2026-09-28)
- 首个可用版本：8 阶段流水线（probe → fit → preview⏸人工选段 → cut → hud → composite → build → verify）
- 用蒲虹路素材真实测试通过：竖屏 1440x1920、11 段混合时长、动态 HUD 小数表盘、结尾完整长图、几何终验 0.86%
- 测试中发现并修复：外置盘大小写敏感 glob（坑8）、混合时长时间线错位（坑9）、cut 阶段脚本名映射、composite/build 缺导入、300MB 限制误伤 probe 全量清单（改为仅约束候选）
- 坑 8/9 已回写 references/pitfalls.md

## 0.1.0 (2026-09-28)
- 初始骨架：从蒲虹路骑行项目泛化（素材探测/FIT 解析/选段/切片/HUD 表盘/烧录/草稿组装/几何验证 8 阶段流水线）
