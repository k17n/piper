# Starts Piper: checks uv and Ollama, rebuilds the UI if needed, then opens the app.
# Usage:  .\start.ps1            (native window)
#         .\start.ps1 --browser  (browser tab instead)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Step($text) { Write-Host "-> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "x  $text" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

# 1. uv (also found when PATH hasn't refreshed since it was installed)
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    $uv = Get-ChildItem "$env:APPDATA\Python\Python3*\Scripts\uv.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $uv) { Fail "uv not found. Install it with:  python -m pip install --user uv" }

# 2. Ollama: start it if it isn't answering yet
function Test-Ollama {
    # A plain TCP connect: Invoke-WebRequest's first call can stall on proxy detection / IPv6 localhost.
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.ConnectAsync("127.0.0.1", 11434).Wait(1000) -and $client.Connected }
    catch { $false }
    finally { $client.Dispose() }
}
if (-not (Test-Ollama)) {
    Step "Starting Ollama"
    $ollamaApp = "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
    $ollamaCli = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (Test-Path $ollamaApp) { Start-Process $ollamaApp }
    elseif ($ollamaCli) { Start-Process $ollamaCli -ArgumentList "serve" -WindowStyle Hidden }
    else { Fail "Ollama is not installed. Get it from https://ollama.com/download" }
    # a cold start (GPU detection) can take most of a minute
    $deadline = (Get-Date).AddSeconds(90)
    while (-not (Test-Ollama)) {
        if ((Get-Date) -gt $deadline) { Fail "Ollama didn't start within 90 seconds. Open it from the Start menu and try again." }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 1
    }
    Write-Host ""
}

# 3. Python dependencies (fast no-op once installed)
Step "Checking Python dependencies"
& $uv sync --quiet
if ($LASTEXITCODE -ne 0) { Fail "uv sync failed." }

# 4. UI: build when missing or when any UI source file is newer than the last build
$built = "src\piper_jobs\static\index.html"
$needsBuild = -not (Test-Path $built)
if (-not $needsBuild) {
    $builtAt = (Get-Item $built).LastWriteTime
    $newest = Get-ChildItem web\src, web\index.html, web\package.json -Recurse -File |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $needsBuild = $newest.LastWriteTime -gt $builtAt
}
if ($needsBuild) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "npm not found. Install Node.js to build the UI." }
    Push-Location web
    try {
        if (-not (Test-Path node_modules)) { Step "Installing UI packages"; npm install --no-fund --no-audit }
        Step "Building the UI"
        npm run build
        if ($LASTEXITCODE -ne 0) { Fail "UI build failed." }
    } finally { Pop-Location }
}

# 5. Run
Step "Opening Piper (close the window to quit)"
$env:PYTHONIOENCODING = "utf-8"
& $uv run piper ui @args
