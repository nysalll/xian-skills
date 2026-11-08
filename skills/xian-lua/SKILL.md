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
xian query --catalog <索引目录> --q "青铜丹房" --json
xian query --link <记录id> --tables-dir <导表目录> --channel official --version <版本> --snapshot <快照> --json
xian query --index <索引> --kind table --q <关键词> --json
xian query --table <某表.json> --field <字段> --op eq --value <值> --json
xian search --root <目录> --q <文本> --json
```

Lua64 和 Lua32 都要保留。仓库不附带反编译器。

没有反编译器时，先运行 `xian tools decompiler` 给用户看来源、许可证和 SHA256。用户明确同意后再执行 `xian tools decompiler --install --yes`。不要自己下载别的 EXE，也不要改这个文件里的路径。

解密可以在反编译器安装前进行。导表和查询要等反编译完成。查询结果要带上渠道、版本和快照，不要把正式服和证道服混在一次回答里。
