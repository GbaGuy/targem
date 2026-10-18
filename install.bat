@echo off
rem Double-click to install targem (or pass -Uninstall to remove it).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
