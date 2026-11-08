# 平台适配

技能源文件在 `skills/<name>/SKILL.md`。`xian install` 复制这些目录。目标里已有同名技能且内容不同时跳过，`--force` 会先备份到 `%USERPROFILE%\.xian-skills\backup\` 再覆盖。

| 平台 | 文档 | 安装位置 | 本地命令与调用说明 |
| --- | --- | --- | --- |
| Claude Code | https://code.claude.com/docs/en/skills | 用户 `~/.claude/skills/`，项目 `.claude/skills/` | 支持执行本地命令，受客户端权限确认限制 |
| OpenAI Codex | https://learn.chatgpt.com/docs/build-skills | 用户 `~/.agents/skills/`、`~/.codex/skills/`，项目 `.agents/skills/` | 支持执行本地命令，受沙箱和审批限制 |
| Cursor | https://cursor.com/docs/skills | 用户 `~/.cursor/skills/` 和 `~/.agents/skills/`，项目 `.cursor/skills/`、`.agents/skills/` | 支持执行本地命令，运行前需用户批准 |
| Kimi Code | https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html | 用户 `~/.kimi-code/skills/` 和 `~/.agents/skills/`，项目 `.kimi-code/skills/`、`.agents/skills/` | Kimi Code CLI 支持执行本地命令（不含网页版聊天） |
| Kiro | https://kiro.dev/docs/skills/ | 用户 `~/.kiro/skills/`，项目 `.kiro/skills/` | 桌面 IDE 和 CLI 支持执行本地命令，受沙箱限制 |
| 腾讯 WorkBuddy | https://www.tencentcloud.com/zh/document/product/1316/84503 | 用户 `~/.workbuddy/skills/<名称>/SKILL.md`，项目 `.workbuddy/skills/`，或上传顶层为技能文件夹的 ZIP（不使用 `.codebuddy/`） | 桌面 Agent 支持执行本地任务；统一调用 `%USERPROFILE%\.xian-skills\bin\xian.cmd`，无需修改 `SKILL.md` |
| 豆包工作 | https://www.doubao.com/work/docs/zh-cn/articles/081010973544-skills | 客户端“技能 → 上传技能”导入 ZIP（包内含带 YAML `name` 和 `description` 的 `SKILL.md`） | 仅在工作任务选择“本地电脑”模式时可执行本机命令；云电脑无法访问本机 MuMu |

`xian install` 的 JSON 里 `invocation_verified` 固定为 `false`。复制文件成功只说明技能文件已写入磁盘。

WorkBuddy 和豆包工作的 zip 包默认生成在 `%USERPROFILE%\.xian-skills\dist\`（`xian-skills-workbuddy.zip` 与 `xian-skills-doubao-work.zip`），供客户端上传界面导入使用。
