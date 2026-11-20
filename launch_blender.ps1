$ErrorActionPreference = 'Stop'
$blenderPath = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
if (-not (Test-Path -LiteralPath $blenderPath)) {
    throw "Blender not found: $blenderPath"
}
$prototypePath = Join-Path $PSScriptRoot 'pie_prototype.py'
Start-Process -FilePath $blenderPath -ArgumentList @('--python', ('"' + $prototypePath + '"')) -WindowStyle Normal
