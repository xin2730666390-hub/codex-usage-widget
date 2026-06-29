@echo off
setlocal
set "APP_DIR=%~dp0"
set "BUNDLED_PY_DIR=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python"
set "PY=%BUNDLED_PY_DIR%\pythonw.exe"

if not exist "%PY%" set "PY=%BUNDLED_PY_DIR%\python.exe"
if exist "%PY%" goto run

for %%P in (pythonw.exe python.exe py.exe) do (
  where %%P >nul 2>nul
  if not errorlevel 1 (
    set "PY=%%P"
    goto run
  )
)

echo Could not find Python. Please open Codex once, then run this again.
pause
exit /b 1

:run
start "Codex Usage Widget" "%PY%" "%APP_DIR%codex_usage_widget.py"
exit /b 0
