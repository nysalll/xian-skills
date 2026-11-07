# 测试

合成测试不包含私人抓包或游戏资源：

```powershell
python -m unittest discover -s tests -v
```

`xian verify` 会再跑这套测试，并把通过的项目记为 `basic_tested`。这个状态不是真实客户端验证。

`xian verify --device-check` 会在当前 adb 设备上读取包名和 `version.txt`。读到版本后，`client_version` 才标成 `verified`。

已经在开发机上做过的真实检查写在 `docs/verification/local-2026-11-08.md`。那次检查没有把客户端文件提交进仓库。

第二轮真实数据记录在 `docs/verification/2026-11-08-real-client.md`。

仍然不能写成通过的项目：

- 开启 root 后的一场新抓包，以及真实会话的上行解码
- 七个 Agent 产品里的实际对话
- 没有 ffmpeg 时的 mp4 转码
- `reward.lua` 里尚未识别的奖励结构
