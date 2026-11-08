# 研究怎么往下做

1. 用 `xian status --json` 看功能和数据，不把未验证项说成可用。
2. 用 `xian research analyze --question` 得到第一步命令。
3. 能在现有快照、索引和 jsonl 里回答的，先查本地：
   - 中文名称用 `xian query --catalog <目录> --q "<名称>"`
   - 查哪些表含某英文字段用 `xian query --index <索引> --kind field --q <字段>`
   - 查英文记录 key 或函数/常量定义用 `xian search --root <目录> --q <标识符>`
   - 追踪某个数字或字符串 ID 的跨表引用用 `xian query --link <ID> --tables-dir <导表目录>`，区分 `semantic_reference`（明确引用）与 `value_match`（候选值匹配）
4. 注意静态导表边界：若某张表标记为 `data_status: "runtime_generated"`（如 `*_partN` 分片加载或运行时生成），静态解析不会执行游戏 Lua 代码，需继续检索对应的 `*_partN` 表或阅读反编译源码。
5. 需要新的客户端文件或流量时，先说明影响，等用户确认后再加 `--yes`。
6. 计算写在 `xian research init-script` 创建的目录。
7. 结论使用四个小节：已确认事实、有证据支持的推断、待验证假设、当前无法判断。
8. 报告里记录输入快照编号、工具版本和命令。原始抓包与账号标识留在数据目录。
