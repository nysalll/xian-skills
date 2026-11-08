---
name: xian-capture
description: >-
  在用户确认后录制其自己的模拟器流量，解析 ZM 帧，统计消息，并解码对时之后的上行。
  用户提到抓包、协议、上行、cap.jsonl 或战斗记录时使用。
whenToUse: 用户明确要求录自己的游戏流量，或解析已经存在的 pcap。
---

# xian-capture

检查环境或验证功能不是抓包授权。开始前要说明：可能执行 `adb root`，在设备上启动 tcpdump，结果只写 `%USERPROFILE%\.xian-skills\data\captures`，不上传。用户明确同意后再加 `--yes`。登录由用户自己完成。

```powershell
xian capture start --session <名字> --minutes 10 --profile full --yes
xian capture stop --json
xian capture status --json
xian capture parse --pcap <文件.pcap> --output <out.jsonl> --profile full
xian capture stats --jsonl <out.jsonl> --json
```

没有 `--yes` 时命令返回退出码 4，不要改用别的方式绕过。
同一时间只录一场。不要按端口过滤。口令、token、cookie 会写成 `[redacted]`。
上行解不出时保留加密计数，不要编造消息内容。原始 jsonl 不要提交或外发。
