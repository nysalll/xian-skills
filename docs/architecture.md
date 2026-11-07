# 架构

`xian` 是唯一的执行入口。技能只告诉 Agent 何时调用哪条命令。七个平台不各写一套解析器。

```text
skills/                 Agent 说明
src/xian_skills/cli     参数、确认、退出码
config/                 %USERPROFILE%\.xian-skills\config.json
device/                 寻找 adb 和模拟器端口
client/                 版本、清单、增量快照
storage/                内容寻址仓库
lua/                    XOR、反编译、配置表、索引
query/                  表、字段、函数、文本
protocol/               pcap 与 ZM 帧
capture/                tcpdump 会话和脱敏
assets/                 Unity、USM、外部音频解码器
research/               秘境、PVP、研究计划和临时脚本
events/                 活动表识别和数量加总
updates/                目录或快照差异、更新报告
runtime/                进程列表和可选的 Frida 模块检查
diagnostics/            doctor、verify、status
install/                技能复制和 zip
```

快照一旦提交就不再改写。文件正文在 `data/blobs/`，快照只保存路径、sha256、md5 和来源。研究脚本放在 `data/research/<题目>/`，不修改 blob。

新增一种配置查询时，优先加 `query` 或 `events` 里的字段规则，并补一个合成样本测试。不要把某一期活动的结论写死进代码。

游戏版本变化时，重新 `client sync` 会得到新快照。旧快照保留，报告通过快照编号引用输入。
