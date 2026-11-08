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
2. 查询用 `xian query --catalog <目录> --q "<原话>" --json`。差异用 `xian updates records`，并读它的 `warning`。活动用 `xian events analyze`。一条龙研究用 `xian research run`。
3. 客户端配置不是服务器结算。没有样本就不要把换算写成最终伤害。

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
