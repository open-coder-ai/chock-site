# Build and serve chock-site locally at its pinned catalog and engine, as CI does.
# Run from a chock-site checkout, in Windows PowerShell 5.1 or PowerShell 7:
#   powershell -ExecutionPolicy Bypass -File scripts\local-test.ps1              # build + serve http://127.0.0.1:8000/
#   powershell -ExecutionPolicy Bypass -File scripts\local-test.ps1 -RunTests    # also run unit, then browser (e2e) tests
#   powershell -ExecutionPolicy Bypass -File scripts\local-test.ps1 -Port 8080   # serve on another port
#   powershell -ExecutionPolicy Bypass -File scripts\local-test.ps1 -NoServe     # build dist\ only, then exit (CI uses this)
#   powershell -ExecutionPolicy Bypass -File scripts\local-test.ps1 -NoOpen      # serve without opening a browser
# Needs: Git and Python 3.12 (on Windows, the python.org installer with the "py" launcher).
# Installs nothing outside this checkout.
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$RunTests,
    [switch]$NoServe,
    [switch]$NoOpen
)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

# Windows PowerShell 5.1 has no $IsWindows and runs only on Windows.
$onWindows = ($PSVersionTable.PSEdition -ne "Core") -or $IsWindows

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Stop-Script([string]$msg) { Write-Host "error: $msg" -ForegroundColor Red; exit 1 }
function Invoke-Native([string]$exe, [string[]]$argv) {
    & $exe @argv
    if ($LASTEXITCODE -ne 0) { Stop-Script "failed (exit $LASTEXITCODE): $exe $($argv -join ' ')" }
}
function Test-Python([string]$exe, [string[]]$pre) {
    # Windows PowerShell 5.1 turns redirected native stderr into a terminating error under "Stop".
    $ErrorActionPreference = "Continue"
    $check = @($pre) + @("-c", "import sys; sys.exit(sys.version_info < (3, 12))")
    & $exe @check 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Write-Step "Checking tools"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Stop-Script "git not found. Install Git: https://git-scm.com/downloads"
}
$pyExe = $null
$pyPre = @()
if ($onWindows) {
    if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-Python "py" @("-3.12"))) {
        $pyExe = "py"; $pyPre = @("-3.12")
    }
    elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-Python "python" @())) {
        $pyExe = "python"
    }
    $hint = "Install Python 3.12 from https://www.python.org/downloads/windows/ (keep the 'py launcher' option)."
}
else {
    foreach ($cand in @("python3.12", "python3")) {
        if ((Get-Command $cand -ErrorAction SilentlyContinue) -and (Test-Python $cand @())) { $pyExe = $cand; break }
    }
    $hint = "Install Python 3.12: https://www.python.org/downloads/"
}
if (-not $pyExe) { Stop-Script "Python 3.12 not found. $hint" }
Invoke-Native git @("--version")
Invoke-Native $pyExe (@($pyPre) + @("--version"))

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not ((Test-Path .catalog-ref) -and (Test-Path .framework-ref))) {
    Stop-Script "run this from a chock-site checkout (.catalog-ref and .framework-ref not found in $root)"
}
$catalogRef = (Get-Content .catalog-ref -Raw).Trim()
$engineRef = (Get-Content .framework-ref -Raw).Trim()
Write-Host "site      $(git rev-parse --short HEAD)"
Write-Host "catalog   $catalogRef (.catalog-ref)"
Write-Host "engine    $engineRef (.framework-ref)"

Write-Step "Catalog at the pinned commit -> .catalog"
# Keep LF endings: CRLF would change policy sha256s and break the site's pins.
if (-not (Test-Path .catalog)) {
    Invoke-Native git @("-c", "core.autocrlf=false", "-c", "core.longpaths=true", "clone", "--quiet",
        "https://github.com/open-coder-ai/chock-catalog.git", ".catalog")
}
elseif (-not (Test-Path .catalog/.git)) {
    Stop-Script ".catalog exists but is not a git checkout. Move it away and run again."
}
Invoke-Native git @("-C", ".catalog", "config", "core.autocrlf", "false")
if ($onWindows) { Invoke-Native git @("-C", ".catalog", "config", "core.longpaths", "true") }
if (Test-Path .catalog/.git/shallow) { Invoke-Native git @("-C", ".catalog", "fetch", "--quiet", "--unshallow", "origin") }
$have = & git -C .catalog rev-parse -q --verify "$catalogRef^{commit}"
if ($LASTEXITCODE -ne 0 -or -not $have) { Invoke-Native git @("-C", ".catalog", "fetch", "--quiet", "origin") }
Invoke-Native git @("-C", ".catalog", "checkout", "--quiet", "--force", $catalogRef)
$crlf = & git -C .catalog ls-files --eol | Select-String -Pattern "i/lf\s+w/crlf"
if ($crlf) { Stop-Script ".catalog has files checked out with CRLF endings. Move .catalog away and run again." }
Write-Host "catalog at $(git -C .catalog rev-parse --short HEAD)"

Write-Step "Python environment (.venv) with the pinned chock engine"
if (-not (Test-Path .venv)) { Invoke-Native $pyExe (@($pyPre) + @("-m", "venv", ".venv")) }
if ($onWindows) { $py = Join-Path $root ".venv/Scripts/python.exe" }
else { $py = Join-Path $root ".venv/bin/python" }
if (-not (Test-Path $py)) { Stop-Script ".venv has no $py. Move .venv away and run again." }
if (-not (Test-Python $py @())) { Stop-Script ".venv uses Python older than 3.12. Move .venv away and run again." }
$marker = Join-Path $root ".venv/chock-framework-ref"
$installedRef = ""
if (Test-Path $marker) { $installedRef = (Get-Content $marker -Raw).Trim() }
if ($installedRef -ne $engineRef) {
    # The pin changed (or first run): drop the old engine so pip installs the pinned one.
    & $py -c "import importlib.util, sys; sys.exit(importlib.util.find_spec('chock') is None)"
    if ($LASTEXITCODE -eq 0) { Invoke-Native $py @("-m", "pip", "uninstall", "--quiet", "--yes", "chock") }
}
# PyPI packages are checked by hash; the engine is pinned by commit and pulls nothing else.
Invoke-Native $py @("-m", "pip", "install", "--quiet", "--require-hashes", "-r", "requirements-dev.txt")
Invoke-Native $py @("-m", "pip", "install", "--quiet", "--no-deps", "--no-build-isolation",
    "chock @ git+https://github.com/open-coder-ai/chock@$engineRef")
Invoke-Native $py @("-m", "pip", "check")
[System.IO.File]::WriteAllText($marker, "$engineRef`n")
Invoke-Native $py @("-m", "chock", "--version")

if ($RunTests) {
    Write-Step "Unit tests"
    Invoke-Native $py @("-m", "pytest", "-q", "--ignore=tests/e2e")
    Write-Step "Browser tests (downloads Playwright's Chromium once)"
    Invoke-Native $py @("-m", "playwright", "install", "chromium")
    Invoke-Native $py @("-m", "pytest", "-q", "tests/e2e")
}

$tmpDest = Join-Path ([System.IO.Path]::GetTempPath()) "chock-try"
function Write-EngineCheck {
    Write-Host "To test a builder selection end to end, in a second PowerShell window:" -ForegroundColor Yellow
    Write-Host "  & `"$py`" -m chock install --selection '<code from the builder>' --client codex --dest `"$tmpDest`"" -ForegroundColor Yellow
    Write-Host "  (no --apply: it only builds the plugin into that folder; your agent config is untouched)" -ForegroundColor Yellow
}

if ($NoServe) {
    Write-Step "Building dist/"
    Invoke-Native $py @("-m", "sitegen", "--catalog", ".catalog", "--out", "dist")
    if (-not (Test-Path (Join-Path $root "dist/index.html"))) { Stop-Script "build finished but dist/index.html is missing" }
    Write-Host "Built $(Join-Path $root 'dist/index.html')"
    Write-EngineCheck
    exit 0
}

$url = "http://127.0.0.1:$Port/"
Write-Step "Building and serving $url (Ctrl+C to stop)"
Write-EngineCheck
if (-not $NoOpen) {
    # Open the page once the server answers (the build runs first).
    Start-Job -ArgumentList $Port, $url -ScriptBlock {
        param($p, $u)
        for ($i = 0; $i -lt 120; $i++) {
            $client = New-Object System.Net.Sockets.TcpClient
            try { $client.Connect("127.0.0.1", $p); $client.Close(); Start-Process $u; return }
            catch { Start-Sleep -Seconds 1 }
            finally { $client.Dispose() }
        }
    } | Out-Null
}
& $py -m sitegen serve --catalog .catalog --port $Port
exit $LASTEXITCODE
