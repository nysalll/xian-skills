# 更新记录

## 0.1.2 (v0.1.2-alpha, 2026-11-08)

- **重构跨表关联查询（`xian query --link`）**：支持对 `dict` 和 `list`（含顶层数组表、嵌套字典、多层列表、奖励数组）进行带深度保护的递归遍历，返回 `source_channel`、`source_version`、`snapshot_id`、`table`、`record_key`、`field_path`、`matched_value`、`match_type` 与 `reference_confidence`。
- **区分明确引用与候选值匹配**：将跨表匹配分为 `semantic_reference`（主键或具有明确 ID/图标/奖励/消耗语义的字段引用）与 `value_match`（仅数值相等、需人工确认的候选关联），支持 `--link-mode all|semantic` 及可读文本报告。
- **完善导表数据完整性标记**：`xian lua tables`、`xian lua index` 与 `xian query --build-catalog` 区分 `nonempty`（非空配置表）、`runtime_generated`（运行时动态或 `*_partN` 分片延迟加载表，静态解析不执行 Lua 代码）、`empty`（空表）与 `logic_skipped`（逻辑代码）。
- **增强 Windows 路径与启动器兼容性**：修复 `installers/windows/xian.cmd` 在 `cmd.exe` 下的变量展开问题，同时生成 `xian.cmd`、`xian.ps1` 与 `xian`（POSIX shell）；新增 `normalize_path` 处理反斜杠、末尾引号、跨 Shell 环境变量、`/c/Users/...` 路径以及 `config.json` 单反斜杠容错。
- **补充第二台电脑实测回归测试**：新增覆盖 12 类跨表关联场景、数据完整性分类与 Windows 路径处理的合成回归测试。

## 0.1.1

- 反编译器改为按用户确认后，从 marsinator358/luajit-decompiler-v2 的 `Mar_24_2024` Release 下载，并核对 SHA256。仓库仍不附带 EXE。
- WorkBuddy 只安装到 `~/.workbuddy/skills/` 和项目 `.workbuddy/skills/`。上传 ZIP 的技能目录在顶层。不再把技能写进 `.codebuddy/`。
- Windows 启动器固定为 `%USERPROFILE%\.xian-skills\bin\xian.cmd`，技能文件里不再写某台电脑的绝对路径。
- 已有 adb 服务时继续用它，不再换另一个 adb.exe。`offline` 会停下来说明，而不是自动重连到另一套服务。
- 检查环境和读取版本不再被当成整包同步、抓包或进程探测的授权。
- 状态输出分开显示当前客户端版本、完整快照份数和 `version.txt` 历史行数。没有反编译器时，导表和查询不会显示成已验证。

## v0.1.0-alpha (2026-11-08)

Python 包版本：`0.1.0`

- 提供统一 CLI `xian`、内容寻址本地数据仓库（默认 `%USERPROFILE%\.xian-skills\`）与 9 个专项 Agent Skills（`xian`、`xian-setup`、`xian-client`、`xian-lua`、`xian-capture`、`xian-assets`、`xian-research`、`xian-events`、`xian-updates`）。
- 支持 Windows + MuMu 12 环境检测、ADB 自动发现、正式服（`com.leiting.xian`）与证道服（`com.leiting.m71`）版本读取、全量/增量快照提取及完整性校验。
- 支持本地 Lua AssetBundle 解密、外部反编译器调用、配置表 JSON 导出、目录索引（`catalog`）与字段/函数检索。
- 支持跨版本与跨渠道（正式服 vs 证道服）配置记录级对比、活动奖励与消耗汇总、客户端贴图/模型/CRI 音频/USM 视频导出。
- 支持经用户确认（`--yes`）的本机会话流量录制、ZM/msgpack 协议解析与上行消息解码、秘境会抗反推与 PVP 客户端系数换算，以及受确认限制的进程/Frida 模块检查。
- 支持向 Claude Code、Codex、Cursor、Kimi Code、Kiro、腾讯 WorkBuddy、豆包工作分发技能目录或生成上传 ZIP 包。
- 仓库不包含游戏客户端、账号会话、抓包产物及第三方专有二进制工具。
