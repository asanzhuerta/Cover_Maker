# Stage the files the installer bundles for the first-run bootstrap (ADR-006):
# uv.exe, the engine wheel and one pylock.toml per install profile, all taken
# from engine/uv.lock. Run before `pnpm tauri build`.
#
#   powershell -File desktop/scripts/prepare-runtime.ps1

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$engine = Join-Path $repo "engine"
$out = Join-Path $repo "desktop\src-tauri\resources\runtime"
$deps = Get-Content (Join-Path $out "deps.json") -Raw | ConvertFrom-Json

Get-ChildItem $out -Exclude deps.json, README.md | Remove-Item -Recurse -Force

# uv, pinned by version and hash.
$zip = Join-Path $env:TEMP $deps.uv.file
Invoke-WebRequest $deps.uv.urls[0] -OutFile $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $deps.uv.sha256) { throw "uv download hash mismatch: $hash" }
$unpacked = Join-Path $env:TEMP "cover_maker_uv"
if (Test-Path $unpacked) { Remove-Item -Recurse -Force $unpacked }
Expand-Archive $zip $unpacked
Copy-Item (Join-Path $unpacked "uv.exe") $out

# Engine wheel and lock files.
uv build --wheel --project $engine --out-dir $out
if ($LASTEXITCODE -ne 0) { throw "uv build failed" }
Remove-Item (Join-Path $out ".gitignore") -ErrorAction SilentlyContinue
$profiles = @{
    "core"  = @()
    "cpu"   = @("--extra", "separation", "--extra", "cpu")
    "cu128" = @("--extra", "separation", "--extra", "cu128")
}
foreach ($name in $profiles.Keys) {
    $file = Join-Path $out "pylock.$name.toml"
    uv export --project $engine --frozen --no-dev --no-emit-project --no-header `
        --format pylock.toml @($profiles[$name]) -o $file -q
    if ($LASTEXITCODE -ne 0) { throw "uv export ($name) failed" }
}
Get-ChildItem $out | Format-Table Name, Length -AutoSize
