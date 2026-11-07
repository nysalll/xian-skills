# 故障排查

| 现象 | 处理 |
| --- | --- |
| 找不到 python | 安装 Python 3.10+ 并勾选 Add to PATH，重新打开终端 |
| `xian` 不是命令 | 使用 `.\.venv\Scripts\xian.exe`，或先激活 `.venv` |
| `init --yes` 拒绝安装依赖 | 当前不是虚拟环境。先运行 `installers\windows\install.ps1` |
| 没有 adb | 安装 Android SDK Platform-Tools，或把 `adb.exe` 路径写入配置 `adb_path`。也可用 MuMu 自带的 `shell\adb.exe` |
| 多台设备 | 看退出码 4 的设备列表，用 `--device 127.0.0.1:端口` |
| 游戏已安装但目录不可读 | 先在模拟器里打开游戏并完成热更新。不要为了读目录去改系统策略，除非用户明确同意 |
| 只有正式服 | 正常。证道服未安装不会让正式服命令失败 |
| 反编译失败 | 配置 `decompiler_path`。仓库不附带反编译器 |
| 导表被跳过 | 该文件是逻辑代码，或反编译结果不是干净的配置表。跳过不是整条管线损坏 |
| 抓包起不来 | 设备上要有 tcpdump，并且用户同意 `adb root`。当前 shell 不是 root 时，抓包会停在这一步 |
| Unity 导出报缺 UnityPy | 在虚拟环境执行 `xian init --yes` |
| 音频 bank 失败 | 配置 `vgmstream_path`。USM 视频不依赖它 |
| 技能没有出现在 Agent 里 | 看 `docs/platforms.md`。文件复制成功不等于产品已经加载。WorkBuddy 和豆包工作需要在客户端上传 zip，并新开任务 |
| 升级后不想用新技能 | `xian install --force` 的上一份在 `%USERPROFILE%\.xian-skills\backup\`。把对应目录拷回去 |

磁盘很忙时，抓包解析会等待占用下降。不要同时对整个客户端目录做全盘搜索。
