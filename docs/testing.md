# 测试

合成测试不包含私人抓包或游戏资源：

```powershell
python -m unittest discover -s tests -v
```

`xian verify` 会运行这套合成测试，并把通过的项目记为 `basic_tested`。这个状态仅代表单元测试通过，不代表已在当前电脑完成真实客户端验证。

`xian verify --device-check` 会在当前连接的 ADB 设备上读取包名和 `version.txt`。读到版本后，`client_version` 才会标成 `verified`。

需要用户单独准备环境或授权的项目（不会在 `verify` 中自动执行）：

- 开启 `adb root` 后的会话抓包录制与真实上行解码
- 各个 AI Agent 客户端内的实际对话触发
- 安装 `ffmpeg` 后的 `.ivf` 转 `.mp4` 视频转码
- 安装 `vgmstream` 后的 `.acb` 音频解码
