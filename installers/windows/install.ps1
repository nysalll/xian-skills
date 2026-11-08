param(
    [switch]$User,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "没有找到 python。"
    Write-Host "请从 https://www.python.org/downloads/windows/ 安装 Python 3.10 或更新版本，并勾选 Add python.exe to PATH。"
    exit 2
}

if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
    & python -m venv (Join-Path $Root ".venv")
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$venvXian = Join-Path $Root ".venv\Scripts\xian.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e ".[decode,lua]"
& $venvXian init
$launcherHome = Join-Path $env:USERPROFILE ".xian-skills"
New-Item -ItemType Directory -Force -Path (Join-Path $launcherHome "bin") | Out-Null
Set-Content -Path (Join-Path $launcherHome "xian-launcher.txt") -Value $venvXian -Encoding ascii
Copy-Item (Join-Path $PSScriptRoot "xian.cmd") (Join-Path $launcherHome "bin\xian.cmd") -Force
$installArgs = @("install", "--project", $Root)
if ($User) {
    $installArgs += "--user"
}
if ($Force) {
    $installArgs += "--force"
}
& $venvXian @installArgs
& $venvXian doctor --no-device
Write-Host ""
Write-Host "虚拟环境已就绪。下一步："
Write-Host "  .\.venv\Scripts\xian.exe doctor"
Write-Host "  .\.venv\Scripts\xian.exe status"
Write-Host "把技能装进用户目录（会影响本机各 Agent 的技能列表）："
Write-Host "  powershell -ExecutionPolicy Bypass -File .\installers\windows\install.ps1 -User"
