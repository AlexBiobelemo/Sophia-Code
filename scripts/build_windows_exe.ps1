Param(
  [string]$Name = "Sophia-Code",
  [string]$Entry = "desktop_entry.py"
)

$ErrorActionPreference = "Stop"

Write-Host "Building $Name from $Entry"

python -m pip install --upgrade pip | Out-Host
python -m pip install -r requirements.txt | Out-Host
python -m pip install pyinstaller | Out-Host

# Clean previous outputs
if (Test-Path ".\\build") { Remove-Item -Recurse -Force ".\\build" }
if (Test-Path ".\\dist")  { Remove-Item -Recurse -Force ".\\dist" }

# NOTE: --add-data uses ';' on Windows to separate src and dest.
pyinstaller `
  --noconfirm `
  --clean `
  --name "$Name" `
  --onefile `
  --add-data "app\\templates;app\\templates" `
  --add-data "app\\static;app\\static" `
  --add-data "migrations;migrations" `
  "$Entry" | Out-Host

Write-Host ""
Write-Host "Build complete. Output:"
Get-ChildItem ".\\dist" -Force | Select-Object Name,Length,LastWriteTime

