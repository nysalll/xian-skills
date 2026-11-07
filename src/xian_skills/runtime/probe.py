"""Local process inspection. Module names only; no game-function calls."""

from __future__ import annotations

from xian_skills.device.adb import Adb
from xian_skills.errors import EnvError, NeedConfirm

_SCRIPT = r"""
rpc.exports = {
  inspect: function () {
    var mods = Process.enumerateModules();
    var names = mods.map(function (mod) { return mod.name; });
    var interesting = names.filter(function (name) {
      return /lua|il2cpp|unity|tolua/i.test(name);
    });
    var exports = {};
    var wanted = ['luaL_newstate', 'luaL_loadstring', 'lua_pcall'];
    wanted.forEach(function (name) {
      var addr = Module.findExportByName(null, name);
      exports[name] = addr ? true : false;
    });
    return { modules: interesting.slice(0, 80), export_present: exports };
  }
};
"""


def require_yes(yes: bool) -> None:
    if yes:
        return
    raise NeedConfirm(
        "动态探测会查看本机模拟器里的进程，并在你已安装 Frida 时附加到你指定的进程，只读取模块名和少量导出是否存在。"
        "它不会调用这些函数，也不会修改游戏。确认后加 --yes，并自行提供 pid。"
    )


def list_game_processes(adb: Adb) -> dict:
    result = adb.shell("ps -A", timeout=25)
    text = result.stdout or ""
    rows = []
    for line in text.splitlines():
        lowered = line.lower()
        if "leiting" in lowered or "xian" in lowered or "m71" in lowered:
            rows.append(line.strip())
    return {"device": adb.serial, "matches": rows, "frida": "not_run"}


def frida_inspect(host: str, pid: int) -> dict:
    try:
        import frida
    except ImportError as exc:
        raise EnvError("未安装 frida。需要时再执行 pip install frida，并从 Frida 官方发布页安装与设备匹配的 frida-server。") from exc
    device = frida.get_device_manager().add_remote_device(host)
    session = device.attach(int(pid))
    try:
        script = session.create_script(_SCRIPT)
        script.load()
        result = script.exports_sync.inspect()
    finally:
        session.detach()
    return {"host": host, "pid": int(pid), "result": result, "note": "只记录模块名和导出是否存在，没有调用这些函数。"}
