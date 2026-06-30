@echo off
rem ===================================================================
rem  Obsidian AI Chat - double-click installer for locked-down machines.
rem  Runs the PowerShell installer with a per-process execution-policy
rem  bypass (works on the default Restricted/RemoteSigned policies), and
rem  uses the bundled plugins if present (no internet / no git needed).
rem ===================================================================
setlocal
cd /d "%~dp0"
echo ===================================================
echo   Obsidian AI Chat - one-click install
echo ===================================================
echo.

rem prefer PowerShell 7 (pwsh) if installed, else Windows PowerShell 5.1
where pwsh >nul 2>nul && (set "PS=pwsh") || (set "PS=powershell")

if exist "%~dp0plugins\smart-composer\main.js" (
  echo Using bundled plugins ^(offline^).
  "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ObsidianAI.ps1" -Interactive -OfflineDir "%~dp0plugins"
) else (
  echo No bundled plugins found - will fetch from GitHub at install time.
  "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ObsidianAI.ps1" -Interactive
)

echo.
echo If you saw "DONE" above: open Obsidian, press Ctrl+P, run "Reload app without saving".
echo If this window was blocked by company policy, see MANUAL-INSTALL.txt (no scripts needed).
echo.
pause
