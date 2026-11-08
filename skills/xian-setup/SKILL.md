---
name: xian-setup
description: >-
  安装 xian-skills，检查 Windows、Python 虚拟环境、ADB 和 MuMu，并解释哪些功能已验证。
  用户要求安装、初始化、修复环境或询问现在能做什么时使用。
whenToUse: 用户要安装 xian-skills、连接 MuMu，或想知道当前电脑能研究什么。
---

# xian-setup

## 安装

在用户克隆下来的 `xian-skills` 目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\install.ps1
.\.venv\Scripts\xian.exe init
.\.venv\Scripts\xian.exe doctor
.\.venv\Scripts\xian.exe verify
.\.venv\Scripts\xian.exe status
```

`install.ps1` 只创建项目虚拟环境。系统 Python、ADB 和模拟器不会静默安装。

## 判断

- `xian doctor --json` 看 Python、包、adb 和在线设备。
- 有多台设备时停下，用用户指定的 `--device`。
- 未安装的渠道保持可用，不要因为没有证道服而中止正式服流程。
- `ready` 只表示依赖在；`basic_tested` 是合成测试；`verified` 才是这台机器上的实际检查。
- 反编译器没装时，反编译和导表不能报成已验证。
- 设备显示 `offline` 时停下来说明，不要换一个 adb.exe 再试。

## 依赖

用户明确同意后，在虚拟环境执行 `xian init --yes` 安装 msgpack、pycryptodome 和 UnityPy。
反编译器要单独同意后用 `xian tools decompiler --install --yes`。vgmstream、ffmpeg、tcpdump 和 frida-server 不随仓库提供。

检查环境、读取版本和运行单元测试都不等于同意整包同步、抓包或进程探测。
