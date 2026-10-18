<#
  Slide Explainer launcher (Windows PowerShell 5+ or PowerShell 7).

    .\start.ps1          demo mode: no API key, no cost (built-in offline model)
    .\start.ps1 -Live    live mode: real OpenAI models, needs backend\.env with OPENAI_API_KEY

  Installs dependencies on first run, starts the backend (127.0.0.1:8000) and the
  frontend (localhost:3000) in two windows, then opens the browser.
#>
param([switch]$Live)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Fail($msg) { Write-Host "`n  $msg`n" -ForegroundColor Red; exit 1 }
function Step($msg) { Write-Host "-> $msg" -ForegroundColor Cyan }

# --- prerequisites ---------------------------------------------------------
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
  foreach ($c in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:APPDATA\Python\Python314\Scripts\uv.exe",
                   "$env:APPDATA\Python\Python313\Scripts\uv.exe", "$env:USERPROFILE\.cargo\bin\uv.exe")) {
    if (Test-Path $c) { $uv = $c; break }
  }
}
if (-not $uv) {
  Fail "uv is not installed. Install it with:`n    powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"`n  then open a new terminal and run this script again."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Fail "Node.js is not installed. Install the LTS version from https://nodejs.org and run this script again."
}
if ($Live -and -not (Test-Path "$root\backend\.env")) {
  Fail "Live mode needs backend\.env. Copy backend\.env.example to backend\.env and set OPENAI_API_KEY."
}

# --- install (first run only does real work) -------------------------------
Step "Installing backend dependencies (uv sync; Python 3.14 is downloaded if needed)"
& $uv --directory "$root\backend" sync --quiet
if ($LASTEXITCODE -ne 0) { Fail "uv sync failed (see above)." }

$chromium = & $uv --directory "$root\backend" run python -c "from slidex.core.hardware import chromium_installed; print(chromium_installed())"
if ($chromium -ne "True") {
  Step "Installing Chromium for PDF export (one time, ~150 MB)"
  & $uv --directory "$root\backend" run playwright install chromium
}

if (-not (Test-Path "$root\frontend\node_modules")) {
  Step "Installing frontend dependencies (npm install, one time)"
  npm --prefix "$root\frontend" install --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { Fail "npm install failed (see above)." }
}

# --- start -----------------------------------------------------------------
if ($Live) {
  $envCmd = "`$env:SLIDEX_FAKE_LLM='0'; `$env:SLIDEX_DEMO_WEB='0'; `$env:SLIDEX_DATA_DIR='../data'"
  $mode = "LIVE (real OpenAI models - costs money)"
} else {
  $envCmd = "`$env:SLIDEX_FAKE_LLM='1'; `$env:SLIDEX_DEMO_WEB='1'; `$env:SLIDEX_DATA_DIR='../data-demo'"
  $mode = "DEMO (offline model - free, deterministic answers)"
}
Step "Starting backend in $mode"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "`$host.UI.RawUI.WindowTitle='Slide Explainer backend'; $envCmd; & '$uv' --directory '$root\backend' run slidex serve"

Step "Starting frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "`$host.UI.RawUI.WindowTitle='Slide Explainer frontend'; npm --prefix '$root\frontend' run dev"

Step "Waiting for http://localhost:3000"
$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
  try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://localhost:3000 | Out-Null; break }
  catch { Start-Sleep -Seconds 2 }
}
Start-Process "http://localhost:3000"
Write-Host "`nSlide Explainer is running in $mode." -ForegroundColor Green
Write-Host "Try samples\vague-lecture.pdf. Close the two server windows to stop.`n"
