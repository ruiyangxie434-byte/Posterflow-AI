$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "未找到 .venv，请先按照 README 安装依赖。" -ForegroundColor Yellow
    exit 1
}

Set-Location -LiteralPath $projectRoot
& $python -m streamlit run app.py

