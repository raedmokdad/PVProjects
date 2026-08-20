# Tägliche Aufgabe 00:05 Europe/Berlin.
# Als Administrator in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\jobs\setup_windows_task.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}
$taskName = "Wetenergy-Ausschreibungen"
$action = New-ScheduledTaskAction -Execute $python -Argument "jobs\daily.py" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 00:05
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Aufgabe '$taskName' registriert (täglich 00:05). Arbeitsordner: $root"
