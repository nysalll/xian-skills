---
name: xian-lua
description: >-
  解密一念逍遥 Lua AssetBundle，反编译 LuaJIT，导出配置 JSON，并按表名、字段、函数和数值查询。
  用户要查游戏配置、道具、技能表或 Lua 逻辑时使用。
whenToUse: 用户要解密 Lua、导表、建索引，或从配置里查一个名字、字段或数值。
---

# xian-lua

```powershell
xian lua decode --input <Lua64目录> --output <输出> --tag Lua64
xian lua decode --input <文本资源> --output <字节码> --raw
xian lua decompile --input <字节码目录> --output <源码目录>
xian lua tables --input <源码目录> --output <JSON目录>
xian lua constants --input <file.lua> --output <file.json>
xian lua index --lua <源码> --tables <JSON> --output <索引>
xian query --build-catalog <导表目录> --output <索引目录> --channel official --version <版本> --snapshot <快照>
xian query --catalog <索引目录> --q "<中文名称>" --json
xian query --link <记录id> --tables-dir <导表目录> --link-mode all --channel official --version <版本> --snapshot <快照> --json
xian query --index <索引> --kind field --q <英文字段名> --json
xian query --index <索引> --kind table --q <表名关键词> --json
xian query --table <某表.json> --field <字段> --op eq --value <值> --json
xian search --root <目录> --q <英文记录key或文本> --json
```

## 查询入口选择

- **查中文名称**（如道具、神通、领域名称）：`xian query --catalog <索引目录> --q "<中文名>"`
- **查英文字段名分布在哪些表**（如查找含 `attack` 字段的表）：`xian query --index <索引> --kind field --q <字段名>`
- **查英文记录 key 或常量定义**（如查找 `attack_grow_rate` 的定义）：`xian search --root <导表或源码目录> --q <英文key>`
- **单表条件筛选**：`xian query --table <某表.json> --field <字段> --op eq|ne|gt|ge|lt|le|contains --value <值>`
- **跨表关联追踪**（追踪道具 ID、奖励 ID、技能 ID 出现在哪些系统）：`xian query --link <ID> --tables-dir <导表目录> [--link-mode all|semantic]`
  - `semantic_reference`：主键或具有明确 ID/图标/奖励/消耗语义的字段引用。
  - `value_match`：仅发现相同数字或字符串，尚不能确定引用语义，回答时必须标为候选关联。

## 反编译器与数据完整性边界

Lua64 和 Lua32 都要保留。仓库不附带反编译器。

没有反编译器时，先运行 `xian tools decompiler` 给用户看来源、许可证和 SHA256。用户明确同意后再执行 `xian tools decompiler --install --yes`。不要自己下载别的 EXE，也不要改这个文件里的路径。

不要把“没有抛出异常”等同于“所有配置内容已完整提取”。`xian lua tables` 与 `build-catalog` 会区分四类状态：

1. `nonempty`：静态字面量解析成功且包含非空记录。
2. `runtime_generated`：Lua 文件在客户端中通过运行时逻辑、`setmetatable` 或 `rerequire("..._partN")` 动态生成数据；静态导表不执行不受信任的游戏 Lua 代码，因此该主表顶层 `entries` 为 `0`（分片数据位于对应的 `*_partN.lua.json`）。
3. `empty`：源码本身为空表字面量 `{}`。
4. `logic_skipped`：属于逻辑代码而非配置表，导表阶段按预期跳过。

查询结果要带上渠道、版本和快照，不要把正式服和证道服混在一次回答里。
