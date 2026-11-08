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
3. 组合使用五种查询定位完整配置链路与客户端函数：
   - 中文名称：`xian query --catalog <索引> --q "<名称>" --json`
   - 字段分布：`xian query --index <索引> --kind field --q <英文字段名> --json`
   - 英文 key / 源码定义：`xian search --root <导表或源码目录> --q <英文key> --json`
   - 跨表 ID 引用追踪：`xian query --link <ID> --tables-dir <导表目录> --link-mode all --json`（区分 `semantic_reference` 明确引用与 `value_match` 候选数值匹配）
   - 单表条件筛选：`xian query --table <表.json> --field <字段> --op <操作符> --value <值> --json`
   - 若目标表标记为 `data_status: "runtime_generated"`（顶层 `entries=0`），继续检索对应的 `*_partN.lua.json` 分片表或反编译后的 `.lua` 源码，不要执行未受信任的 Lua 代码。
4. 有授权 jsonl 时运行 `xian research mijing --jsonl <文件> --me <角色标识>`。
5. 用 `xian research pvp` 做可复核换算。系数来自客户端默认值时，在结论里写明。
6. 需要新计算时 `xian research init-script --name <题目>`，脚本放在研究目录。

```powershell
xian research pvp --hitrate 500000 --dodge 400000 --crit 900000 --crit-resist 700000 --json
xian research mijing --jsonl <cap.jsonl> --json
```

临时脚本只读输入，输出写到该研究目录的 `outputs/`。验证过的通用算法再考虑收进工具，不要把某一次角色面板写进仓库。
动态探测用 `xian runtime probe --yes`，可选 `--pid`。它只列出进程和模块，不调用游戏函数。
