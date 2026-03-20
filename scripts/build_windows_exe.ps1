Param(
  [string]$Name = "Sophia-Code",
  [string]$Entry = "desktop_entry.py",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

Write-Host "Building $Name from $Entry"

if (-not $SkipInstall) {
  python -m pip install --upgrade pip | Out-Host

  # Install runtime deps for a desktop build. Skip gunicorn (not supported on Windows).
  $reqs = Get-Content ".\\requirements.txt" | Where-Object { $_ -and ($_ -notmatch '^\\s*#') }
  foreach ($r in $reqs) {
    if ($r -match '^gunicorn\\b') { continue }
    python -m pip install "$r" | Out-Host
  }

  python -m pip install pyinstaller | Out-Host
}

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
if (Test-Path ".\\dist") {
  Get-ChildItem ".\\dist" -Force | Select-Object Name,Length,LastWriteTime
} else {
  Write-Host "No dist/ directory was produced."
}
