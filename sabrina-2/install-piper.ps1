# Sabrina AI - Piper binary installer (Windows).
# Downloads the official Piper release, extracts to .\tools\piper\, and prints
# the path. You can either:
#   (a) add that folder to your PATH (permanent), or
#   (b) set SABRINA_TTS__PIPER__BINARY in .env to the full piper.exe path.
#
# Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\install-piper.ps1

$ErrorActionPreference = "Stop"

$PiperVersion = "2023.11.14-2"   # latest tagged Windows release
$Url = "https://github.com/rhasspy/piper/releases/download/$PiperVersion/piper_windows_amd64.zip"
$ToolsDir = Join-Path $PSScriptRoot "tools"
$PiperDir = Join-Path $ToolsDir "piper"
$Zip = Join-Path $ToolsDir "piper.zip"

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

if (Test-Path (Join-Path $PiperDir "piper.exe")) {
    Write-Host "Piper already installed at $PiperDir" -ForegroundColor Green
    exit 0
}

Write-Host "Downloading Piper $PiperVersion ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing

Write-Host "Extracting ..." -ForegroundColor Cyan
if (Test-Path $PiperDir) { Remove-Item -Recurse -Force $PiperDir }
Expand-Archive -Path $Zip -DestinationPath $ToolsDir -Force
Remove-Item $Zip

# The zip extracts to a folder called "piper" by default - perfect.
$PiperExe = Join-Path $PiperDir "piper.exe"
if (-not (Test-Path $PiperExe)) {
    # Some releases extract differently; locate piper.exe.
    $found = Get-ChildItem -Path $ToolsDir -Recurse -Filter "piper.exe" | Select-Object -First 1
    if ($found) { $PiperExe = $found.FullName } else { throw "piper.exe not found after extraction." }
}

Write-Host ""
Write-Host "Installed:   $PiperExe" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Tell Sabrina where it lives. Easiest: add this line to .env -"
Write-Host "     SABRINA_TTS__PIPER__BINARY=$PiperExe"
Write-Host ""
Write-Host "  2. Download a voice (inside the sabrina-2 folder):"
Write-Host "     uv run sabrina tts download-voice amy-medium"
Write-Host ""
Write-Host "  3. Test it:"
Write-Host "     uv run sabrina tts 'Hello, I am Sabrina.'"
