---
name: xian-research
description: >-
  研究一念逍遥的秘境、PVP、神通、功法和伤害计算。先查配置和已有样本，再写临时脚本，
  区分客户端系数、样本拟合和服务器未知部分。
whenToUse: 用户要研究战斗机制、秘境怪物、神通伤害、功法或切磋数值。
---

# xian-research

不要只返回同名配置就结束。按这个顺序：

1. `xian status --json`
2. `xian research run --question "<原问题>" --catalog <索引> --channel official`
3. `xian query` 和 `xian search` 定位配置与客户端函数。
4. 有授权 jsonl 时运行 `xian research mijing --jsonl <文件> --me <角色标识>`。
5. 用 `xian research pvp` 做可复核换算。系数来自客户端默认值时，在结论里写明。
6. 需要新计算时 `xian research init-script --name <题目>`，脚本放在研究目录。

```powershell
xian research pvp --hitrate 500000 --dodge 400000 --crit 900000 --crit-resist 700000 --json
xian research mijing --jsonl <cap.jsonl> --json
```

临时脚本只读输入，输出写到该研究目录的 `outputs/`。验证过的通用算法再考虑收进工具，不要把某一次角色面板写进仓库。
动态探测用 `xian runtime probe --yes`，可选 `--pid`。它只列出进程和模块，不调用游戏函数。
