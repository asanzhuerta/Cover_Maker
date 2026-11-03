# M2 spike: measure a clean first-run bootstrap with uv (ADR-006).
#
# Simulates what the installer will do on first run, in an isolated folder with
# its own uv cache and Python install dir, and reports time and disk use.
#
#   powershell -File spikes/bootstrap/measure.ps1 [-Torch cpu|cu128]

param(
    [ValidateSet("cpu", "cu128")] [string] $Torch = "cpu",
    [string] $Root = (Join-Path $env:TEMP "cover_maker_bootstrap_spike")
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")

if (Test-Path $Root) { Remove-Item -Recurse -Force $Root }
New-Item -ItemType Directory -Force $Root | Out-Null
$env:UV_CACHE_DIR = Join-Path $Root "cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root "python"
$venv = Join-Path $Root "venv"

function Measure-Step([string] $Name, [scriptblock] $Block) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    & $Block | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
    $watch.Stop()
    [pscustomobject]@{ Step = $Name; Seconds = [math]::Round($watch.Elapsed.TotalSeconds, 1) }
}

function Size-MB([string] $Path) {
    if (-not (Test-Path $Path)) { return 0 }
    [math]::Round((Get-ChildItem $Path -Recurse -File -Force | Measure-Object Length -Sum).Sum / 1MB)
}

$wheelDir = Join-Path $Root "dist"
$steps = @()
$steps += Measure-Step "build engine wheel" { uv build --wheel --project (Join-Path $repo "engine") --out-dir $wheelDir }
$steps += Measure-Step "install Python 3.12" { uv python install 3.12 }
$steps += Measure-Step "create venv" { uv venv --python 3.12 $venv }
$wheel = (Get-ChildItem $wheelDir -Filter *.whl | Select-Object -First 1).FullName
$steps += Measure-Step "install engine (phase A)" { uv pip install --python $venv $wheel }
$index = if ($Torch -eq "cpu") { "https://download.pytorch.org/whl/cpu" } else { "https://download.pytorch.org/whl/cu128" }
$steps += Measure-Step "install torch $Torch (phase B)" { uv pip install --python $venv torch --index-url $index }
$steps += Measure-Step "engine starts" { & (Join-Path $venv "Scripts\cover-maker.exe") --version }

$steps | Format-Table -AutoSize
[pscustomobject]@{
    PythonMB = Size-MB $env:UV_PYTHON_INSTALL_DIR
    VenvMB   = Size-MB $venv
    CacheMB  = Size-MB $env:UV_CACHE_DIR
} | Format-Table -AutoSize
