# Sabrina AI - nssm binary installer (Windows).
# Downloads nssm 2.24 (the long-stable Windows service-wrapper), extracts
# the 64-bit binary to .\tools\nssm\nssm.exe, and prints the path.
# Required when supervisor.mode = "service" in sabrina.toml. Not needed for
# the default Task Scheduler path.
#
# Run from PowerShell (no admin needed for the download itself; `sabrina
# autostart enable` later does need an elevated shell once for the install):
#   powershell -ExecutionPolicy Bypass -File .\install-nssm.ps1

$ErrorActionPreference = "Stop"

$NssmVersion = "2.24"
$Url = "https://nssm.cc/release/nssm-$NssmVersion.zip"
$ToolsDir = Join-Path $PSScriptRoot "tools"
$NssmDir  = Join-Path $ToolsDir "nssm"
$Zip      = Join-Path $ToolsDir "nssm.zip"
$Extract  = Join-Path $ToolsDir "nssm-extract"

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

if (Test-Path (Join-Path $NssmDir "nssm.exe")) {
    Write-Host "nssm already installed at $NssmDir" -ForegroundColor Green
    exit 0
}

Write-Host "Downloading nssm $NssmVersion ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing

Write-Host "Extracting ..." -ForegroundColor Cyan
if (Test-Path $Extract) { Remove-Item -Recurse -Force $Extract }
Expand-Archive -Path $Zip -DestinationPath $Extract -Force
Remove-Item $Zip

# Zip layout: nssm-2.24/{win32,win64,src}. We want win64\nssm.exe.
# Fall back to win32 on a 32-bit host (Windows on ARM64 also reports x86
# for most processes; nssm-2.24 has no native ARM64 build, but the x86
# binary runs under emulation).
$Candidate64 = Get-ChildItem -Path $Extract -Recurse -Filter "nssm.exe" |
               Where-Object { $_.FullName -match "win64" } |
               Select-Object -First 1
$Candidate32 = Get-ChildItem -Path $Extract -Recurse -Filter "nssm.exe" |
               Where-Object { $_.FullName -match "win32" } |
               Select-Object -First 1

$Source = if ([Environment]::Is64BitOperatingSystem -and $Candidate64) {
    $Candidate64.FullName
} elseif ($Candidate32) {
    $Candidate32.FullName
} else {
    throw "nssm.exe not found after extraction."
}

if (Test-Path $NssmDir) { Remove-Item -Recurse -Force $NssmDir }
New-Item -ItemType Directory -Force -Path $NssmDir | Out-Null
Copy-Item -Path $Source -Destination (Join-Path $NssmDir "nssm.exe") -Force
Remove-Item -Recurse -Force $Extract

$NssmExe = Join-Path $NssmDir "nssm.exe"

Write-Host ""
Write-Host "Installed:   $NssmExe" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. (Optional) Pin the path in sabrina.toml so PATH lookup is skipped:"
Write-Host "       [supervisor]"
Write-Host "       nssm_binary = `"$NssmExe`""
Write-Host ""
Write-Host "  2. Flip supervisor.mode to `"service`" in sabrina.toml."
Write-Host ""
Write-Host "  3. Open an *elevated* PowerShell (admin) and register the service:"
Write-Host "       uv run sabrina autostart enable"
Write-Host ""
Write-Host "  4. Verify:"
Write-Host "       sc.exe query SabrinaAI"
