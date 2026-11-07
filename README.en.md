# xian-skills

Local research toolkit and AI agent skills for the game 一念逍遥 (`v0.1.0-alpha`, Python package version `0.1.0`).

The toolkit runs on the player's own Windows PC (recommended with MuMu Player 12). It inspects local emulator state, reads game clients (`com.leiting.xian` official and `com.leiting.m71` zhengdao) installed by the player, manages content-addressed snapshots, decodes and indexes Lua config tables, compares versions or channels, analyzes activity rewards/costs, exports client assets, and parses user-authorized local packet captures.

This repository does not contain game client files, account credentials, packet captures, or unredistributable third-party binaries.

## Install

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\windows\install.ps1
.\.venv\Scripts\xian.exe doctor
.\.venv\Scripts\xian.exe init
.\.venv\Scripts\xian.exe verify
.\.venv\Scripts\xian.exe status
```

Add `-User` when the skills should also be copied into the user profile directories for supported AI agents (`-Force` backs up any existing modified skills to `%USERPROFILE%\.xian-skills\backup\` before overwriting). User data and configuration default to `%USERPROFILE%\.xian-skills\`.

`xian status` reports which features are `verified`, `basic_tested`, `ready`, `missing_deps`, or `unverified` on the current machine.

Commands that copy client files, record traffic, inspect processes, or clean cache require `--yes` and exit with code `4` until the user confirms.

## Layout

- `skills/` — agent skill definitions (`xian`, `xian-setup`, `xian-client`, `xian-lua`, `xian-capture`, `xian-assets`, `xian-research`, `xian-events`, `xian-updates`)
- `src/xian_skills/` — unified `xian` CLI and library modules
- `docs/platforms.md` — setup details for Claude Code, Codex, Cursor, Kimi Code, Kiro, WorkBuddy, and 豆包工作

Client config values do not equal server-side combat resolution. Reports separate confirmed facts, supported inferences, hypotheses, and unknowns.

See [README.md](README.md) for the full Chinese documentation.
