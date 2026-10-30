@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-morph-ui.ps1"
if errorlevel 1 pause
