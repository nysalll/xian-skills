# 更新记录

## v0.1.0-alpha (2026-11-08)

Python 包版本：`0.1.0`

- 提供统一 CLI `xian`、内容寻址本地数据仓库（默认 `%USERPROFILE%\.xian-skills\`）与 9 个专项 Agent Skills（`xian`、`xian-setup`、`xian-client`、`xian-lua`、`xian-capture`、`xian-assets`、`xian-research`、`xian-events`、`xian-updates`）。
- 支持 Windows + MuMu 12 环境检测、ADB 自动发现、正式服（`com.leiting.xian`）与证道服（`com.leiting.m71`）版本读取、全量/增量快照提取及完整性校验。
- 支持本地 Lua AssetBundle 解密、外部反编译器调用、配置表 JSON 导出、目录索引（`catalog`）与字段/函数检索。
- 支持跨版本与跨渠道（正式服 vs 证道服）配置记录级对比、活动奖励与消耗汇总、客户端贴图/模型/CRI 音频/USM 视频导出。
- 支持经用户确认（`--yes`）的本机会话流量录制、ZM/msgpack 协议解析与上行消息解码、秘境会抗反推与 PVP 客户端系数换算，以及受确认限制的进程/Frida 模块检查。
- 支持向 Claude Code、Codex、Cursor、Kimi Code、Kiro、腾讯 WorkBuddy、豆包工作分发技能目录或生成上传 ZIP 包。
- 仓库不包含游戏客户端、账号会话、抓包产物及第三方专有二进制工具。
