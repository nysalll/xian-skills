# xian-skills

面向《一念逍遥》玩家的本机游戏数据研究工具与 AI Agent 技能集（当前版本：`0.1.2` / `v0.1.2-alpha`）。

`xian-skills` 在玩家自己的 Windows 电脑上运行：连接本机 MuMu 模拟器、识别自己安装的正式服或证道服客户端、提取与增量管理快照、解密并导出配置表、检索道具与神通数值、对比版本差异、拆解活动奖励与消耗、导出贴图/模型/音频/视频，并在用户授权后录制本机会话流量辅助秘境与切磋机制研究。

本项目已在第二台独立的 Windows + MuMu 12 + WorkBuddy 电脑上完成从 GitHub 安装、客户端同步、Lua 解密、反编译、全量导表、目录索引与“灵域”系统跨表机制研究的完整实测（见 [第二台电脑实测记录](docs/verification/2026-11-08-second-pc.md)）。

本仓库不包含游戏客户端、账号凭据、会话抓包或未授权的第三方二进制工具，也不会向外部服务上传玩家数据。

---

## 1. 可以完成哪些研究任务

- **客户端识别与快照管理**：自动发现 MuMu 12 的 ADB 端口，识别正式服（`com.leiting.xian`）与证道服（`com.leiting.m71`）当前版本，提取客户端文件并按内容寻址保存不可覆盖的历史快照，支持增量同步与快照间文件差异对比。
- **Lua 解密、导表与配置检索**：解密本地 `Lua64` / `Lua32` AssetBundle，调用用户配置的 LuaJIT 反编译器，将配置表导出为 JSON，建立目录索引（`catalog`）与函数索引，按名称、字段条件或跨表关联 ID 查询客户端配置。
- **版本更新与跨渠道差异报告**：对比同一渠道的两个历史快照，或横向对比正式服与证道服的配置表记录差异，生成结构化 Markdown 报告。
- **活动配置拆解**：识别活动、礼包、商店、兑换与任务相关配置表，自动加总配置中明确写出的奖励与消耗数量，并明确区分概率、保底与服务器限购。
- **客户端资源导出**：从本地客户端导出贴图（`.png`）、模型网格（`.obj`）、CRI 音频（`.acb` → `.wav`）及 USM 视频（`.usm` → `.ivf` / `.mp4`）。
- **本机抓包与机制研究**：在用户确认（`--yes`）后录制本机模拟器流量，解析 `ZM`/msgpack 协议与对时后的上行消息；结合客户端 `calc` 系数估算 PVP 命中/会心/破防，或根据实战 `cap.jsonl` 反推秘境怪物会抗与受击样本。

---

## 2. 支持的 AI Agent 平台

统一执行入口为 `xian` CLI，源码位于 `skills/` 的 9 个技能负责引导不同平台的 AI Agent 调用对应命令：

| 平台 | 安装方式 | 状态说明 |
| --- | --- | --- |
| Claude Code | 复制到 `.claude/skills/`（项目或用户目录） | 已验证文件安装，尚未在客户端内实测触发 |
| OpenAI Codex | 复制到 `.agents/skills/` 与 `~/.codex/skills/` | 已验证文件安装，尚未在客户端内实测触发 |
| Cursor | 复制到 `.cursor/skills/` 与 `.agents/skills/` | 已验证文件安装与 CLI 工作流，待新会话验证自动触发 |
| Kimi Code | 复制到 `.kimi-code/skills/` 与 `.agents/skills/` | 已验证文件安装（限 Kimi Code CLI，非网页版） |
| Kiro | 复制到 `.kiro/skills/` | 已验证文件安装（限桌面 IDE/CLI） |
| 腾讯 WorkBuddy | 复制到 `~/.workbuddy/skills/`，或上传顶层就是技能文件夹的 ZIP | 已在第二台电脑实测完整 CLI 研究流程；调用 `%USERPROFILE%\.xian-skills\bin\xian.cmd`，不要改 `SKILL.md`。不使用 `.codebuddy/` |
| 豆包工作 | 生成 `%USERPROFILE%\.xian-skills\dist\xian-skills-doubao-work.zip` | 需在客户端“技能 → 上传技能”导入并选“本地电脑”模式 |

各平台目录规范详见 [docs/platforms.md](docs/platforms.md)。`xian install` 输出中的 `invocation_verified` 默认为 `false`，表示复制文件或生成上传包不等于已在全部 7 个客户端界面中逐一完成对话触发验证。

---

## 3. 让 AI 从 GitHub 自动安装（推荐）

你可以直接把下面这段话复制给你的 AI Agent（如 Cursor、Claude Code、Codex、Kimi Code 等）：

```text
请帮我在当前 Windows 电脑上从 https://github.com/nysalll/xian-skills.git 克隆 xian-skills 仓库，严格按照仓库 README.md 的步骤运行 installers\windows\install.ps1 完成虚拟环境和技能初始化，然后依次执行 xian doctor、xian verify 和 xian status，最后用通俗的话告诉我当前电脑、MuMu 模拟器、正式服/证道服客户端以及各项研究功能的状态。检查环境、读取版本和运行测试不算同意。未经我明确同意，不要执行带 --yes 的整包同步、下载反编译器、抓包或进程探测。
```

### 给 Agent 的标准安装顺序

当你在用户的 Windows 电脑上执行安装时，请按顺序执行，不要跳过检查：

1. 阅读本文件、`docs/platforms.md` 和 `docs/privacy.md`。
2. 运行 Windows 安装脚本（默认只创建项目 `.venv` 并安装项目级技能）：

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\install.ps1
```

仅当用户明确要求把技能安装到本机用户目录（供所有项目使用）时，再加 `-User`（如已有同名技能且内容不同会默认跳过；仅在用户要求覆盖时加 `-Force`并自动备份到 `%USERPROFILE%\.xian-skills\backup\`）：

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\install.ps1 -User
```

3. 检查环境、初始化配置并查看功能状态：

```powershell
.\.venv\Scripts\xian.exe doctor
.\.venv\Scripts\xian.exe init
.\.venv\Scripts\xian.exe verify
.\.venv\Scripts\xian.exe status
```

4. 根据 `xian status` 的输出如实告知用户：哪些功能是 `verified`（真机已验证）或 `basic_tested`（合成测试通过），哪些是 `ready`、`missing_deps` 或 `unverified`。
5. 涉及客户端提取/同步（`client pull/sync`）、抓包（`capture start`）、动态探测（`runtime probe`）和清理缓存（`cache clean`）的操作，必须先向用户说明影响，获得确认后再加 `--yes`（未加 `--yes` 时退出码为 `4`）。

---

## 4. 推荐环境与手动使用指南

### 推荐环境

- **操作系统**：Windows 10 / Windows 11（64 位）
- **模拟器**：MuMu 模拟器 12（建议从官方渠道安装《一念逍遥》正式服或证道服，登录并完成热更新；只装正式服完全不影响使用）
- **Python**：Python 3.10 或更高版本（官方安装包：`https://www.python.org/downloads/windows/`，安装时勾选 `Add python.exe to PATH`）

### 检查 ADB 与客户端、初始化工具链

```powershell
# 1. 创建虚拟环境并安装 Python 依赖（msgpack、pycryptodome、UnityPy）
powershell -ExecutionPolicy Bypass -File .\installers\windows\install.ps1

# 2. 检查 Python、依赖包、ADB 与在线模拟器端口（自动扫描 MuMu 配置，不死绑 7555）
.\.venv\Scripts\xian.exe doctor

# 3. 识别已安装的正式服 (com.leiting.xian) 与证道服 (com.leiting.m71) 及当前版本号
.\.venv\Scripts\xian.exe client discover
.\.venv\Scripts\xian.exe client version

# 4. 运行合成自检与设备版本校验，并查看当前可用功能列表
.\.venv\Scripts\xian.exe verify --device-check
.\.venv\Scripts\xian.exe status
```

### 常用命令示例

```powershell
# 先只拉取 version.txt（小范围提取，需 --yes）
.\.venv\Scripts\xian.exe client pull --channel official --include version.txt --yes

# 增量同步完整客户端快照（需 --yes，旧快照不会覆盖）
.\.venv\Scripts\xian.exe client sync --channel official --yes

# 解密 Lua64、安装/调用反编译器、导出配置表 JSON 并建立目录索引
.\.venv\Scripts\xian.exe lua decode --input <Lua64目录> --output <字节码目录> --tag Lua64
.\.venv\Scripts\xian.exe tools decompiler --install --yes
.\.venv\Scripts\xian.exe lua decompile --input <字节码目录> --output <源码目录>
.\.venv\Scripts\xian.exe lua tables --input <源码目录> --output <导表目录>
.\.venv\Scripts\xian.exe lua index --lua <源码目录> --tables <导表目录> --output <索引目录>
.\.venv\Scripts\xian.exe query --build-catalog <导表目录> --output <索引目录> --channel official --version <版本号> --snapshot <快照ID>

# 五类常用配置查询与跨表关联
.\.venv\Scripts\xian.exe query --catalog <索引目录> --q "青铜丹房"
.\.venv\Scripts\xian.exe query --index <索引目录> --kind field --q attack
.\.venv\Scripts\xian.exe search --root <导表或源码目录> --q attack_grow_rate
.\.venv\Scripts\xian.exe query --table <某表.json> --field quality --op eq --value purple
.\.venv\Scripts\xian.exe query --link 97104 --tables-dir <导表目录> --link-mode all

# 分析活动、生成跨版本或跨渠道差异报告
.\.venv\Scripts\xian.exe events analyze --tables <导表目录> --output 活动分析.md
.\.venv\Scripts\xian.exe updates records --left <正式服导表> --right <证道服导表> --relation cross-channel --output 渠道差异.md
.\.venv\Scripts\xian.exe updates report --left <旧版本目录> --right <新版本目录> --output 更新报告.md
```

### 查询入口与跨表关联说明

| 查询场景 | 推荐命令 | 说明 |
| --- | --- | --- |
| 中文名称检索 | `xian query --catalog <索引> --q "<中文名>"` | 在单渠道目录索引中匹配 `name`/`title`/`skill_name`/`show_name` 及相关表 |
| 英文字段名分布 | `xian query --index <索引> --kind field --q <字段名>` | 查找哪些配置表包含指定字段（如 `attack`） |
| 英文记录 key / 定义搜索 | `xian search --root <目录> --q <英文key>` | 在导表 JSON 或反编译 Lua 源码中全文检索常量或 key（如 `attack_grow_rate`） |
| 单表条件筛选 | `xian query --table <表.json> --field <字段> --op <操作符> --value <值>` | 支持字典表与顶层数组表的字段筛选 |
| 跨表 ID 引用追踪 | `xian query --link <ID> --tables-dir <导表目录> [--link-mode all\|semantic]` | 递归扫描 `dict` 与 `list`，区分 `semantic_reference`（主键或明确 ID/图标/奖励/消耗语义引用）与 `value_match`（仅数值相等的候选关联） |

完整命令与参数说明见 [docs/cli.md](docs/cli.md)。退出码约定：`0` 成功，`1` 参数或输入错误，`2` 环境或依赖缺失，`3` 执行失败，`4` 需要用户确认（`--yes`）。

---

## 5. 如何使用自然语言开展研究

安装完成后，你可以直接用自然语言对 AI Agent 提问（更多示例见 [examples/questions.md](examples/questions.md)）：

- “帮我检查 MuMu 和已经安装的一念逍遥，告诉我现在哪些研究功能可以直接用。”
- “读取正式服和证道服的当前版本号；如果没装证道服就只看正式服。”
- “在正式服配置索引里查一下‘青铜丹房’和关联表记录，并标明数据版本与客户端配置边界。”
- “对比正式服和证道服的配置表，生成一份横向差异报告，重点看神通和活动表。”
- “拆解当前配置里的活动奖励和兑换消耗，把确定数量和概率/限购分开列出来。”
- “用客户端系数估算命中 50 万、闪避 40 万、会心 90 万、会抗 70 万时的命中率和会心率，并说明哪些部分还需要实战样本。”

### 技能分工

| 技能 | 作用 |
| --- | --- |
| `xian` | 总入口：路由专项技能，把结论分为“已确认事实、有证据支持的推断、待验证假设、当前无法判断” |
| `xian-setup` | 安装、虚拟环境初始化与环境检查 |
| `xian-client` | 客户端版本识别、文件提取与增量快照管理 |
| `xian-lua` | Lua AssetBundle 解密、反编译、配置导表与索引查询 |
| `xian-capture` | 本机会话流量录制、ZM 协议解析与上行解码 |
| `xian-assets` | 贴图、模型网格、音频、视频资源导出 |
| `xian-research` | 秘境反推、PVP 换算、神通/功法研究与独立脚本工作区 |
| `xian-events` | 活动配置表识别、奖励与消耗汇总 |
| `xian-updates` | 快照或配置表对比、版本更新与跨渠道差异报告 |

---

## 6. 数据目录与外部依赖

### 用户数据默认位置

正式用户配置与数据默认存放在仓库外部的 `%USERPROFILE%\.xian-skills\`，更新或重新克隆代码仓库不会影响已有数据：

- `%USERPROFILE%\.xian-skills\config.json`：保存 `adb_path`、`device`、`decompiler_path`、`vgmstream_path`、`ffmpeg_path` 等本机配置。
- `%USERPROFILE%\.xian-skills\data\`：保存正式服/证道服快照、内容寻址 `blobs/`、配置索引、本地抓包与研究笔记。

正式服与证道服快照分开存放，相同文件内容只存一份，新同步生成新快照且不覆盖旧快照。`xian cache clean --yes` 仅清理可再生的 `cache/` 目录。

### 额外权限与外部工具说明

| 组件 / 权限 | 用途 | 获取与配置方式 |
| --- | --- | --- |
| Python 3.10+ | 运行 `xian` CLI | 用户从 Python 官网安装，仓库不内置 |
| `msgpack`、`pycryptodome`、`UnityPy` | 协议解析、上行解密、AssetBundle 读取 | `install.ps1` 或 `xian init --yes` 自动装入 `.venv` |
| Android `adb` | 连接模拟器、读取版本与拉取客户端 | 已有 adb 服务时继续用它。没有服务时优先 MuMu 自带的 adb。设备 offline 时不要换另一个 adb.exe |
| LuaJIT 反编译器 | 将解密后的 LuaJIT 字节码反编译为 `.lua` 源码 | 不随仓库分发。用户同意后执行 `xian tools decompiler --install --yes`，只下载 marsinator358 的 `Mar_24_2024` Windows 文件并核对 SHA256 |
| `vgmstream-cli` | 解码 `.acb` 音频 bank 为 `.wav` | 仓库不内置；用户自备后将路径写入 `vgmstream_path` |
| `ffmpeg` | 将 USM 拆出的 `.ivf` 视频转码为 `.mp4` | 仓库不内置；放入系统 PATH 或写入 `ffmpeg_path`（无 `ffmpeg` 时保留 `.ivf`） |
| 模拟器 `root` + `tcpdump` | `xian capture start --yes` 本机抓包 | 需模拟器开启 root 且系统内含 `/system/bin/tcpdump`；无 root 时抓包不可用，不影响本地配置与资源分析 |
| `frida` + `frida-server` | `xian runtime probe --pid <PID> --yes` | 可选；仅用于查看已加载模块名与少量导出符号是否存在 |

---

## 7. 当前 Alpha 版本（`v0.1.2-alpha`）的真实限制

- **客户端配置不等于服务器最终结算**：配置表中的系数、奖励和活动规则仅代表客户端本地数据；未下发的服务器随机过程、实时个人限购与最终伤害结算无法单凭配置表确认。
- **静态配置导表的数据完整性边界**：反编译成功不等于所有表都能靠静态字面量完整提取。例如在第二台电脑的 3001 个 Lua 文件中，2967 张表导出为 JSON，34 个文件属于逻辑代码跳过；导出表中包含 21 张通过运行时逻辑或 `rerequire("..._partN")` 动态生成的表（标记为 `data_status: "runtime_generated"`，顶层 `entries` 为 `0`）以及 19 张空表（`data_status: "empty"`）。为保证安全，工具不会执行不受信任的游戏 Lua 代码来生成动态表，研究时应继续查询对应的 `*_partN` 分片表或结合反编译源码核对。
- **跨表关联中的数值相等不等同于确认引用**：`xian query --link` 会将明确具有 ID/图标/奖励/消耗语义的匹配标记为 `semantic_reference`，将仅数值相等但语义未明的匹配标记为 `value_match`（候选关联），避免把巧合相同的数值直接当成真实关联。
- **平台对话触发验证状态**：7 个目标 AI Agent 平台的技能目录安装与上传包生成均已实现，其中开发机（Cursor）与第二台电脑（腾讯 WorkBuddy）已完成真实客户端配置研究全流程验证，其余平台尚未逐一在客户端界面中发起真实对话验证（`invocation_verified: false`）。
- **真机已验证与待验证边界**：正式服/证道服完整快照同步、Lua 批量解密、配置表反编译与全量导表、目录索引检索、跨表关联研究、跨渠道记录差异、贴图/模型/CRI 音频导出、USM 视频拆流均已在 Windows + MuMu 12 真机环境验证；开启 `adb root` 后的实机在线抓包录制、真实会话上行解码、MP4 转码（需安装 `ffmpeg`）及 `frida` 运行时探测仍需按需授权验证（详见本机验证记录）。

---

## 8. 常见故障及修复方法

| 常见问题 | 原因与修复方法 |
| --- | --- |
| 提示找不到 `python` | 安装 Python 3.10+ 时勾选 `Add python.exe to PATH`，安装后重新打开 PowerShell |
| 直接运行 `xian` 报错找不到命令 | 使用 `.\.venv\Scripts\xian.exe <子命令>`，或先运行 `.\.venv\Scripts\Activate.ps1` |
| `xian init --yes` 拒绝安装依赖 | 当前未处于虚拟环境；请先运行 `installers\windows\install.ps1` |
| 找不到 `adb` 或没有在线设备 | 先启动 MuMu 12，运行 `.\.venv\Scripts\xian.exe doctor`；也可将 MuMu 的 `shell\adb.exe` 写入 `config.json` 的 `adb_path` |
| 退出码 `4` 提示有多台在线设备 | 按提示的序列号加上 `--device 127.0.0.1:<端口>`，或运行 `xian init --device 127.0.0.1:<端口>` 保存默认设备 |
| 游戏已安装但数据目录不可读 | 先在模拟器内打开游戏、登录并完成热更新，使外部数据目录生成 |
| 只装了正式服、没装证道服 | 属于正常情况，未安装的渠道会标记为未安装，不会导致正式服命令失败 |
| `lua decompile` 报未配置反编译器 | 在 `%USERPROFILE%\.xian-skills\config.json` 中设置 `"decompiler_path": "C:\\path\\to\\decompiler.exe"` |
| `lua tables` 跳过部分 `.lua` 文件 | 逻辑脚本并非数据配置表，跳过属于正常行为，不会中断其余配置表导出 |
| 抓包启动失败 | 确认已在模拟器设置中开启 root 权限、设备内存在 `/system/bin/tcpdump`，且命令带有 `--yes` |
| 技能未在 Agent 中生效 | 参考 [docs/platforms.md](docs/platforms.md)；WorkBuddy 与豆包工作需手动上传 `%USERPROFILE%\.xian-skills\dist\` 下的 `.zip` 包并新开会话 |

更多排查说明见 [docs/troubleshooting.md](docs/troubleshooting.md)。

---

## 9. 项目文档索引

- [首次使用指南](docs/first-run.md)
- [AI Agent 平台适配说明](docs/platforms.md)
- [CLI 命令参考](docs/cli.md)
- [自然语言提问示例](examples/questions.md)
- [隐私与安全边界](docs/privacy.md)
- [故障排查](docs/troubleshooting.md)
- [测试说明](docs/testing.md)
- [项目架构](docs/architecture.md)
- [许可证与外部组件说明](docs/licenses.md)
- 本机与第二台电脑验证记录：
  - [基础环境与初步检查 (2026-11-08)](docs/verification/local-2026-11-08.md)
  - [真实客户端快照与资源验收 (2026-11-08)](docs/verification/2026-11-08-real-client.md)
  - [全量配置查询、差异与工作流验证 (2026-11-08)](docs/verification/2026-11-08-agent.md)
  - [第二台电脑 WorkBuddy 实测与反馈修复 (2026-11-08)](docs/verification/2026-11-08-second-pc.md)

English overview: [README.en.md](README.en.md).
