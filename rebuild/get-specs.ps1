# Sabrina AI - local specs probe
# Run from PowerShell (no admin needed):
#   cd <this folder>
#   powershell -ExecutionPolicy Bypass -File .\get-specs.ps1
# Writes specs.txt next to this script. Safe; no network calls.

$ErrorActionPreference = "SilentlyContinue"
$out = @()

$out += "=== SABRINA AI SPECS PROBE ==="
$out += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$out += ""

# --- OS ---
$os = Get-CimInstance Win32_OperatingSystem
$out += "--- Operating System ---"
$out += "OS:           $($os.Caption) ($($os.OSArchitecture))"
$out += "Version:      $($os.Version) / Build $($os.BuildNumber)"
$out += "Install date: $($os.InstallDate)"
$out += ""

# --- CPU ---
$cpu = Get-CimInstance Win32_Processor
$out += "--- CPU ---"
foreach ($c in $cpu) {
    $out += "Model:        $($c.Name.Trim())"
    $out += "Cores:        $($c.NumberOfCores) physical / $($c.NumberOfLogicalProcessors) logical"
    $out += "Max clock:    $([math]::Round($c.MaxClockSpeed/1000,2)) GHz"
}
$out += ""

# --- RAM ---
$cs = Get-CimInstance Win32_ComputerSystem
$ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
$out += "--- Memory ---"
$out += "Total RAM:    $ramGB GB"
$mem = Get-CimInstance Win32_PhysicalMemory
$speeds = $mem | Select-Object -ExpandProperty Speed -Unique
$out += "Speed(s):     $($speeds -join ', ') MT/s"
$out += "Sticks:       $($mem.Count)"
$out += ""

# --- GPU (via WMI; note AdapterRAM caps at ~4GB for larger cards) ---
$out += "--- GPU (WMI) ---"
$gpus = Get-CimInstance Win32_VideoController
foreach ($g in $gpus) {
    $vram = if ($g.AdapterRAM) { [math]::Round($g.AdapterRAM/1GB,1) } else { "?" }
    $out += "Name:         $($g.Name)"
    $out += "VRAM (WMI):   $vram GB  (WMI caps around 4GB; see nvidia-smi below)"
    $out += "Driver:       $($g.DriverVersion)"
    $out += "Resolution:   $($g.CurrentHorizontalResolution) x $($g.CurrentVerticalResolution)"
    $out += ""
}

# --- nvidia-smi if present (accurate VRAM on NVIDIA cards) ---
$nvsmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvsmi) {
    $out += "--- GPU (nvidia-smi) ---"
    $nv = & nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv 2>$null
    $out += ($nv | Out-String).Trim()
    $out += ""
} else {
    $out += "(nvidia-smi not found. If you have an NVIDIA GPU, check Task Manager > Performance > GPU for true VRAM.)"
    $out += ""
}

# --- Disk ---
$out += "--- Disks ---"
$disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"
foreach ($d in $disks) {
    $sizeGB = [math]::Round($d.Size/1GB,1)
    $freeGB = [math]::Round($d.FreeSpace/1GB,1)
    $out += "$($d.DeviceID)  $sizeGB GB total / $freeGB GB free"
}
$out += ""

# --- Audio devices ---
$out += "--- Audio devices ---"
$audio = Get-CimInstance Win32_SoundDevice
foreach ($a in $audio) {
    $out += "- $($a.Name)  [$($a.Status)]"
}
$out += ""

# --- Relevant tooling ---
$out += "--- Relevant tooling ---"
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) { $out += "python:       $((& python --version 2>&1) -join '')  @ $($py.Source)" } else { $out += "python:       not on PATH" }
$py3 = Get-Command python3 -ErrorAction SilentlyContinue
if ($py3) { $out += "python3:      $((& python3 --version 2>&1) -join '')" }
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) { $out += "uv:           $((& uv --version 2>&1) -join '')" } else { $out += "uv:           not installed" }
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) { $out += "ollama:       $((& ollama --version 2>&1) -join '')" } else { $out += "ollama:       not installed" }
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { $out += "git:          $((& git --version 2>&1) -join '')" } else { $out += "git:          not installed" }
$out += ""

# --- Write + echo ---
$path = Join-Path $PSScriptRoot "specs.txt"
$out | Out-File -FilePath $path -Encoding ASCII
Write-Host ($out -join "`n")
Write-Host ""
Write-Host "Saved to: $path" -ForegroundColor Green
