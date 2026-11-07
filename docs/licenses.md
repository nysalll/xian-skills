# 许可证与外部组件说明

本仓库原创代码采用根目录的 [MIT License](../LICENSE) 授权。

| 组件 / 依赖 | 来源 | 本仓库策略 |
| --- | --- | --- |
| `msgpack`、`pycryptodome`、`UnityPy`、`frida` | PyPI（遵循各自开源许可证） | 不捆绑源码；按需在本地虚拟环境中安装 |
| Android SDK Platform-Tools (`adb`) | Google 官方发布包或 MuMu 自带 `adb.exe` | 不捆绑二进制 |
| LuaJIT 反编译器 | 用户自备可执行文件 | 不捆绑；通过配置文件 `decompiler_path` 指定本地路径 |
| `vgmstream` | 用户自备 `vgmstream-cli` | 不捆绑；通过配置文件 `vgmstream_path` 指定本地路径 |
| `ffmpeg`、`tcpdump` | 用户本机或模拟器环境自备 | 不捆绑；`ffmpeg` 可通过 PATH 或 `ffmpeg_path` 调用 |
| 《一念逍遥》客户端与游戏资源 | 用户通过官方渠道自行安装 | 不捆绑；本地提取、解密与分析产物默认保存在仓库外且被 `.gitignore` 排除 |

本地资源读取与协议解析模块仅用于分析用户自己设备上的本地文件与自录流量，并非游戏官方接口。
