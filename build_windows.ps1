# Build ArkTs-X on Windows via WSL2 (Linux x86_64 runtime + JIT).
# The upstream static runtime has no native Win32 execution/JIT port, so this
# clones the kit inside the WSL filesystem and runs build_linux.sh there.
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 [-Distro Debian] [-Bench]
param(
    [string]$Distro = '',
    [string]$WslDir = '~/ArkTs-X',
    [switch]$InstallPackages,
    [switch]$Bench
)
$ErrorActionPreference = 'Stop'
$wslArgs = @()
if ($Distro) { $wslArgs += @('-d', $Distro) }

function Invoke-Wsl([string]$script) {
    & wsl.exe @wslArgs -- bash -lc $script
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed ($LASTEXITCODE): $script" }
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'WSL is not installed. Run "wsl --install -d Debian" (or Ubuntu) and reboot.'
}
if ($InstallPackages) {
    Invoke-Wsl 'sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git cmake ninja-build clang ruby python3-venv wget xz-utils unzip time file rsync'
}
# Sync this checkout into the WSL filesystem and strip CRs, so that a Windows
# checkout made with core.autocrlf=true still matches patch-sha256.json
# (the pinned patches contain no CR bytes). -Bench also needs Dart inside WSL.
$here = (wsl.exe @wslArgs wslpath -a ($PSScriptRoot -replace '\\', '/')).Trim()
Invoke-Wsl "mkdir -p $WslDir && rsync -a --exclude build --exclude vendor --exclude results --exclude .git '$here/' $WslDir/ && cd $WslDir && find . -path ./vendor -prune -o -path ./build -prune -o -type f \( -name '*.py' -o -name '*.sh' -o -name '*.cmake' -o -name '*.json' -o -name '*.txt' -o -name '*.ets' -o -name '*.dart' -o -name '*.patch' \) -print0 | xargs -0 sed -i 's/\r$//'"
Invoke-Wsl "cd $WslDir && sh build_linux.sh"
if ($Bench) {
    Invoke-Wsl "cd $WslDir && dart compile exe bench/suite.dart -o build/dart_aot && python3 run_bench.py --runs 3 && python3 run_game_bench.py --runs 3"
}
Write-Host "Done. Artifacts are in $WslDir/build/ark-source inside WSL."
