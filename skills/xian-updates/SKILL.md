---
name: xian-updates
description: >-
  比较一念逍遥两个客户端快照或两套导表，生成版本更新报告，并附上活动配置变化。
  用户提到游戏更新、版本差异、热更或更新报告时使用。
whenToUse: 用户要对比两个游戏版本，或生成客户端更新报告。
---

# xian-updates

```powershell
xian client diff --channel official --left <旧快照> --right <新快照> --json
xian updates compare --left <旧目录> --right <新目录> --json
xian updates report --left <旧目录> --right <新目录> --output <更新.md>
xian updates history --channel official --json
xian updates records --left <正式服表> --right <证道服表> --relation cross-channel --left-version <版本> --right-version <版本> --output <差异.md>
```

报告写明左右两侧的版本或快照编号。文件哈希变化是客户端资源差异，不是服务器已经采用同一规则的证据。
同一版本内容不同会是另一份快照，不要覆盖旧快照。
正式服和证道服分开对比，缺一侧就只报告存在的一侧。
