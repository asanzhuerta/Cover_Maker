# Clean-machine check of the installer in Windows Sandbox (M9 DoD, CPU path).
#
# Maps the NSIS output folder read-only into a fresh sandbox, installs the app
# silently and starts it, so the first-run bootstrap runs on a machine without
# Python, uv, ffmpeg or a GPU. Needs the "Windows Sandbox" optional feature.
#
#   powershell -File desktop/scripts/sandbox-test.ps1

$ErrorActionPreference = "Stop"
$nsis = Resolve-Path (Join-Path $PSScriptRoot "..\src-tauri\target\release\bundle\nsis")
$installer = Get-ChildItem $nsis -Filter "*-setup.exe" | Sort-Object LastWriteTime | Select-Object -Last 1
if (-not $installer) { throw "build the installer first: pnpm tauri build" }

$inside = "C:\Users\WDAGUtilityAccount\Desktop\installer"
$command = "cmd /c `"$inside\$($installer.Name)`" /S && start `"`" `"%LOCALAPPDATA%\Cover_Maker\cover-maker-desktop.exe`""
$wsb = Join-Path $env:TEMP "cover-maker-sandbox.wsb"
@"
<Configuration>
  <vGPU>Disable</vGPU>
  <Networking>Enable</Networking>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$nsis</HostFolder>
      <SandboxFolder>$inside</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>$command</Command>
  </LogonCommand>
</Configuration>
"@ | Set-Content -Encoding utf8 $wsb
Write-Host "Starting Windows Sandbox with $($installer.Name)"
Start-Process $wsb
