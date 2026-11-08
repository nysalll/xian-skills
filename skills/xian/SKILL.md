---
name: xian
description: >-
  研究《一念逍遥》的本地工具入口。用户提到一念逍遥、xian-skills、正式服、证道服、MuMu、
  配置表、Lua、抓包、秘境、神通、功法、活动或版本更新时使用。负责选择专项流程、调用 xian CLI，
  并把结论分成已确认事实、有证据支持的推断、待验证假设和当前无法判断。
whenToUse: 用户要安装或使用 xian-skills，或要研究一念逍遥的客户端、配置、战斗、活动、更新。
---

# xian

先读 [references/workflow.md](references/workflow.md)。命令细节见仓库 `docs/cli.md`。

## 调用命令

不要修改本文件，也不要把本机绝对路径写进技能。在 Windows 上运行：

`%USERPROFILE%\.xian-skills\bin\xian.cmd`

这个启动器会转到安装器记下的虚拟环境。若它不存在，再试仓库里的 `.venv\Scripts\xian.exe`，然后是 `python -m xian_skills`。

## 授权

“检查环境”“看看能不能用”“验证功能”“识别客户端”“读取版本”都不是授权。这些用 `doctor`、`status`、`client discover`、`client version`，不要加 `--yes`。

只有用户明确同意复制文件、下载反编译器、抓包、改 root 或探测进程之后，才能加 `--yes`。同意前要说明范围、影响和保存位置。保存位置默认是 `%USERPROFILE%\.xian-skills\data`。

## 开始

1. 运行 `xian status --json`。
2. 按问题类型选择对应的查询入口（见下表）。差异用 `xian updates records`，并读它的 `warning`。活动用 `xian events analyze`。一条龙研究用 `xian research run`。
3. 注意导表完整性边界：`lua tables` 导出的 JSON 分为 `nonempty`（非空配置表）、`runtime_generated`（运行时动态或 `*_partN` 分片延迟加载表，静态字面量导表不执行游戏 Lua 代码，顶层 `entries=0`）和 `empty`（空表），另有逻辑代码记入 `logic_skipped`。遇到 `runtime_generated` 表时，继续查对应的 `*_partN` 分片表或结合 Lua 源码核对，不要把 `entries=0` 误判为客户端无此数据。
4. 客户端配置不是服务器结算。没有样本就不要把换算写成最终伤害。

## 查询入口怎么选

| 用户提问类型 | 示例 | 使用命令 |
| --- | --- | --- |
| 查中文名称或概念 | “查一下青铜丹房。” | `xian query --catalog <索引目录> --q "<中文词>" --json` |
| 查某英文字段出现在哪些表 | “有哪些配置表包含 attack 字段？” | `xian query --index <索引目录> --kind field --q <字段名> --json` |
| 查英文记录 key 或配置常量定义 | “找出 attack_grow_rate 的定义。” | `xian search --root <导表或源码目录> --q <英文标识符> --json` |
| 在单张表内按字段条件筛选 | “筛出某表里 quality 等于 purple 的记录。” | `xian query --table <表.json> --field <字段> --op eq --value <值> --json` |
| 跨表追踪某个道具 / 奖励 / 技能 ID 引用 | “某个道具 ID 出现在哪些系统里？”“追踪某奖励 ID 的所有配置引用。” | `xian query --link <ID> --tables-dir <导表目录> [--link-mode all\|semantic] --json` |

`--link` 会递归遍历 dict 和 list，并将结果分为 `semantic_reference`（主键或具有明确 ID/图标/奖励/消耗语义的字段引用）和 `value_match`（仅数值相等、尚未确认引用语义的候选关联）。对于 `value_match`，不得直接宣称是已确认关联。

## 路由

| 用户想做 | 读取 |
| --- | --- |
| 安装、检查环境 | `xian-setup` |
| 版本、提取、增量同步 | `xian-client` |
| 解密、导表、查询 | `xian-lua` |
| 抓包和协议 | `xian-capture` |
| 图片、模型、音频、视频 | `xian-assets` |
| 秘境、PVP、神通、功法 | `xian-research` |
| 活动奖励和消耗 | `xian-events` |
| 版本差异和更新报告 | `xian-updates` |

## 回答格式

- 已确认事实：命令输出里直接读到的内容，附上命令和数据版本。
- 有证据支持的推断：写明证据和反例是否找过。
- 待验证假设：写明还缺哪场记录或哪张表。
- 当前无法判断：服务器未下发、样本不足或工具未验证。
