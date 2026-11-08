# 命令

全局选项 `--json` 和 `--config` 可以写在子命令前面或后面。

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 参数或输入不成立 |
| 2 | 缺环境或依赖 |
| 3 | 执行失败，已有快照保持不变 |
| 4 | 需要 `--yes` |

## 环境与安装

```text
xian doctor [--no-device]
xian init [--data-dir DIR] [--adb PATH] [--device SERIAL] [--yes]
xian status [--no-device] [--device SERIAL]
xian verify [--device-check] [--device SERIAL]
xian tools decompiler [--install --yes]
xian cache clean --yes
xian install [--platform a,b] [--project DIR] [--user] [--source DIR] [--force]
xian platforms
```

`init --yes` 只在已经激活的虚拟环境里安装 `msgpack`、`pycryptodome` 和 `UnityPy`。

## 客户端

```text
xian client discover [--device SERIAL]
xian client version [--device SERIAL]
xian client import-dir --channel official|zhengdao --version VER --src DIR
xian client pull --channel official|zhengdao [--device SERIAL] [--include a,b] --yes
xian client sync --channel official|zhengdao [--device SERIAL] [--include a,b] --yes
xian client snapshots --channel official|zhengdao
xian client diff --channel official|zhengdao --left ID --right ID
xian client materialize --channel official|zhengdao --snapshot ID --dest DIR
```

`--include` 只提取点名的相对路径，快照标记为 `incomplete`，不会当成整包基线。完整同步（`complete: true`）才会与上一份完整快照做增删改对比。

## Lua 与查询

```text
xian lua decode --input PATH --output DIR [--tag Lua64|Lua32] [--limit N]
xian lua decode --input FILE --output FILE --raw
xian lua decompile --input PATH --output DIR [--limit N]
xian lua tables --input PATH --output DIR
xian lua constants --input FILE [--output FILE]
xian lua index [--lua DIR] [--tables DIR] --output DIR
xian query --build-catalog TABLES_DIR --output DIR [--channel CH] [--version VER] [--snapshot ID]
xian query --catalog DIR --q TEXT [--limit N]
xian query --link ID [--tables-dir DIR | --catalog DIR] [--link-mode all|semantic] [--max-depth N] [--channel CH] [--version VER] [--snapshot ID] [--limit N]
xian query --index DIR [--kind file|table|field|func] --q TEXT [--limit N]
xian query --table FILE [--field NAME --op eq|ne|gt|ge|lt|le|contains --value TEXT] [--limit N]
xian search --root DIR --q TEXT [--limit N]
```

反编译器可通过 `xian tools decompiler --install --yes` 下载固定版本并校验 SHA256，或来自配置 `decompiler_path`。

`xian query --link` 会递归遍历 JSON `dict` 与 `list`（含顶层数组表、嵌套字典、多层列表和奖励数组），并将匹配结果分为：

- `semantic_reference`：顶层主键或具有明确 ID/图标/奖励/消耗语义的跨表引用（`reference_confidence` 为 `high` 或 `medium`）。
- `value_match`：仅数值或字符串相等、尚未确认引用语义的候选关联（`reference_confidence` 为 `low`）。
- `--link-mode semantic` 仅在 `hits` 中返回 `semantic_reference`；`--link-mode all`（默认）返回全部递归匹配并区分标记。

## 抓包

```text
xian capture start --session NAME [--device SERIAL] [--out DIR] [--minutes N] [--rotate-mb N] [--profile full|mijing|pvp|combat] --yes
xian capture stop [--session NAME | --out DIR] [--device SERIAL]
xian capture status
xian capture parse --pcap FILE --output FILE [--profile full|mijing|pvp|combat]
xian capture stats --jsonl FILE
```

产物默认在数据目录的 `captures/`，并自动写入 `PRIVATE.txt`。

## 资源、研究与报告

```text
xian assets export --input PATH --output DIR [--kind all|texture|mesh|audio|video] [--limit N]
xian research run --question TEXT --catalog DIR [--channel CH] [--output DIR]
xian research analyze --question TEXT
xian research init-script --name TEXT [--dir DIR]
xian research mijing --jsonl FILE [--me RID]
xian research pvp [--hitrate N] [--dodge N] [--crit N] [--crit-resist N] [--my-dim N] [--op-dim N] [--my-ex N] [--op-ex N] [--crit-damage N] [--op-crit-defense N] [--user-rank N] [--skill-rank N] [--as-base N] [--as-grow N] [--skill-level N] [--endurance N] [--layers N] [--coefs FILE]
xian runtime probe [--device SERIAL] [--pid PID] [--frida-port PORT] --yes
xian events analyze --tables DIR [--other DIR] [--output FILE]
xian updates compare --left DIR --right DIR
xian updates report --left DIR --right DIR --output FILE
xian updates records --left DIR --right DIR [--relation cross-channel|same-channel] [--left-label TEXT] [--right-label TEXT] [--left-version VER] [--right-version VER] [--output FILE]
xian updates history --channel official|zhengdao
```

PVP 和秘境公式来自此前对客户端 `calc` 配置的阅读。输出里的 `limitation` 必须保留：这不是服务器最终结算。
