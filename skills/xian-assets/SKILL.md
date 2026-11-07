---
name: xian-assets
description: >-
  从用户本地的一念逍遥 AssetBundle、USM 和音频 bank 导出图片、模型、音频和视频。
  用户提到贴图、模型、立绘、音频、视频或资源导出时使用。
whenToUse: 用户要导出自己客户端里的图片、模型、音频或视频。
---

# xian-assets

```powershell
xian assets export --input <Bundle或文件> --output <目录> --kind all
xian assets export --input <目录> --output <目录> --kind texture
xian assets export --input <目录> --output <目录> --kind video
```

Unity 资源需要虚拟环境里的 UnityPy。CRI 音频需要用户自己的 vgmstream，路径写入 `vgmstream_path`。
USM 先拆成 IVF；机器上有 ffmpeg 时再转 mp4。不要把导出的游戏资源提交进仓库。
某个依赖缺失时停止这一类导出并说明缺什么，其他已完成的文件保留。
