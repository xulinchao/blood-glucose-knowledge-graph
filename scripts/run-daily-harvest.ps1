# 每日选题采集 — TraeWork / 计划任务一键入口
# 用法: powershell -ExecutionPolicy Bypass -File scripts/run-daily-harvest.ps1

$ErrorActionPreference = "Stop"
function Invoke-External {
    param([scriptblock]$Block)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $prev }
}
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# Agent Reach / OpenCLI 工具链
$venvScripts = Join-Path $env:USERPROFILE ".agent-reach-venv\Scripts"
$ghCli = "C:\Program Files\GitHub CLI"
if (Test-Path $venvScripts) {
    $env:Path = "$venvScripts;$ghCli;" + $env:Path
}

# 修复 mcporter 配置 BOM（若存在）
$mcporterCfg = Join-Path $env:USERPROFILE ".mcporter\mcporter.json"
if (Test-Path $mcporterCfg) {
    $raw = [System.IO.File]::ReadAllBytes($mcporterCfg)
    if ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF) {
        $text = [System.Text.Encoding]::UTF8.GetString($raw, 3, $raw.Length - 3)
        [System.IO.File]::WriteAllText($mcporterCfg, $text, (New-Object System.Text.UTF8Encoding $false))
    }
}

# OpenCLI 多 profile 时设默认（忽略失败）
$profiles = Invoke-External { opencli.cmd profile list 2>&1 }
$connected = $profiles | Select-String "connected" | Select-Object -First 1
if ($connected) {
    $name = ($connected.Line -split '\s+')[0]
    if ($name) { Invoke-External { opencli.cmd profile use $name 2>&1 | Out-Null } }
}

$python = Join-Path $venvScripts "python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
    $pyArgs = @("-3", "src/daily_topic_harvest.py")
} else {
    $pyArgs = @("src/daily_topic_harvest.py")
}

Write-Host ">>> 开始每日选题采集 ($ProjectRoot)" -ForegroundColor Cyan
if ($python -eq "py") {
    & py -3 @pyArgs
} else {
    & $python @pyArgs
}
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
Write-Host ">>> 完成" -ForegroundColor Green
