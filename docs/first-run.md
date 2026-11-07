# 首次使用

1. 安装 Python 3.10 或更新版本，并加入 PATH。
2. 安装 MuMu 12，从官方渠道安装《一念逍遥》，登录并完成热更新。
3. 克隆本仓库后运行 `installers\windows\install.ps1`。
4. 运行 `xian doctor`。它会寻找 adb 和 MuMu 配置里的端口，不假定 `7555`。
5. 只有一台在线设备时自动使用它。多台时命令返回退出码 4，并列出序列号。选定后写入配置的 `device`，或每次加 `--device`。
6. 运行 `xian client discover`。正式服默认包名 `com.leiting.xian`，证道服默认 `com.leiting.m71`。没安装的渠道保持“未安装”，不让另一边失败。
7. 运行 `xian verify` 做合成测试，再运行 `xian status` 看人话总结和可复制的问题。
8. 需要整包或增量文件时，先看 `xian client sync --help`，确认后再加 `--yes`。

数据目录和仓库分开。换电脑时复制仓库即可，用户数据仍在各自的 `%USERPROFILE%\.xian-skills\`。

重新检查环境：

```powershell
xian doctor
xian verify --device-check
xian status
```
