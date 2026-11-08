# 平台适配

技能源文件在 `skills/<name>/SKILL.md`。`xian install` 复制这些目录。目标里已有同名技能且内容不同时跳过，`--force` 会先备份到 `%USERPROFILE%\.xian-skills\backup\` 再覆盖。

下面的路径和能力按 2026-11-08 能查到的官方文档整理。本机只确认了部分产品的配置目录存在，没有在七个产品里逐个发起对话。因此“技能已被产品加载”全部是未验证。

| 平台 | 文档 | 安装位置 | 本地命令 | 本机目录 | 验证 |
| --- | --- | --- | --- | --- | --- |
| Claude Code | https://code.claude.com/docs/en/skills | 用户 `~/.claude/skills/`，项目 `.claude/skills/` | 可以，受权限确认限制 | `~/.claude` 存在 | 未在 Claude Code 里调用 |
| OpenAI Codex | https://learn.chatgpt.com/docs/build-skills | 用户 `~/.agents/skills/`，旧安装器仍写 `~/.codex/skills/`，项目 `.agents/skills/` | 可以，受沙箱和审批限制 | `~/.codex` 存在，`~/.agents` 不存在 | 未在 Codex 里调用 |
| Cursor | https://cursor.com/docs/skills | 用户 `~/.cursor/skills/` 和 `~/.agents/skills/`，项目 `.cursor/skills/`、`.agents/skills/` | 可以，执行命令前需要批准 | `~/.cursor` 存在 | 未做一次新的技能触发实验 |
| Kimi Code | https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html | 用户 `~/.kimi-code/skills/` 和 `~/.agents/skills/`，项目 `.kimi-code/skills/`、`.agents/skills/` | Kimi Code CLI 可以执行本地命令 | `~/.kimi-code` 存在 | 未调用。Kimi 网页聊天不是这个产品 |
| Kiro | https://kiro.dev/docs/skills/ | 用户 `~/.kiro/skills/`，项目 `.kiro/skills/` | IDE 和 CLI 可以，受沙箱限制。Web 和手机不能操作这台 Windows 上的 MuMu | `~/.kiro` 存在 | 未调用 |
| 腾讯 WorkBuddy | https://www.tencentcloud.com/zh/document/product/1316/84503 | 用户 `~/.workbuddy/skills/<名称>/SKILL.md`，项目 `.workbuddy/skills/`。ZIP 里技能文件夹在顶层。不使用 `.codebuddy/` | 桌面 Agent 可以执行本地任务。调用 `%USERPROFILE%\.xian-skills\bin\xian.cmd`，不要改 SKILL.md | 第二台电脑实际把九个技能放到 `~/.workbuddy/skills/` 后才能调用 | 目录已按这次反馈改。产品内自动发现仍取决于新开的 WorkBuddy 对话 |
| 豆包工作 | https://www.doubao.com/work/docs/zh-cn/articles/081010973544-skills | 客户端“技能 → 上传技能”，包内要有带 YAML `name` 和 `description` 的 `SKILL.md` | 只有工作任务选择“本地电脑”时才能跑本机命令。云电脑看不到本机 MuMu。豆包普通对话没有这套能力 | 无稳定的官方本地技能目录可写 | 未打开豆包工作。安装器生成 zip，不假装已经导入 |

`xian install` 的 JSON 里 `invocation_verified` 固定为 false。复制文件成功只说明文件到了磁盘。

WorkBuddy 和豆包工作的 zip 包默认生成在 `%USERPROFILE%\.xian-skills\dist\`（`xian-skills-workbuddy.zip` 与 `xian-skills-doubao-work.zip`），供客户端上传界面导入使用。不要把生成 zip 包和“已经在产品里测过”写成同一件事。
