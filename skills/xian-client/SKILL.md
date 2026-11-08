---
name: xian-client
description: >-
  识别一念逍遥正式服和证道服，读取版本，提取或增量同步客户端文件，并保留不可覆盖的历史快照。
  用户提到客户端版本、热更新、提取文件或正式服证道服差异时使用。
whenToUse: 用户要查看游戏版本、从 MuMu 提取客户端，或比较历史快照。
---

# xian-client

包名默认是正式服 `com.leiting.xian` 和证道服 `com.leiting.m71`，可在配置里修改。数据目录要实际读到，不能只假设 `/sdcard/Android/data/<package>/files`。

```powershell
xian client discover --json
xian client version --json
xian client snapshots --channel official --json
xian client sync --channel official --yes
xian client pull --channel official --include version.txt --yes
xian client diff --channel official --left <旧快照> --right <新快照> --json
xian client materialize --channel official --snapshot <快照> --dest <导出目录>
xian client import-dir --channel official --version <版本> --src <本地目录>
```

`discover`、`version`、`snapshots`、`diff` 是只读命令，不要加 `--yes`。

`sync` 和 `pull` 会把模拟器里的游戏文件复制到 `%USERPROFILE%\.xian-skills\data`。用户说检查环境或验证功能时，不要执行它们。先说明要复制哪个渠道、大约哪些目录，以及旧快照不会被覆盖。用户明确同意后再加 `--yes`。

没有证道服时只处理正式服。`current_version` 是 version.txt 的最后一行。`version_txt_line_count` 是这个文件里的历史行数，不是本机快照份数。
