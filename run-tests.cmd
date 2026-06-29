@echo off
setlocal
set "APP_DIR=%~dp0"
set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%BUNDLED_PY%" (
  "%BUNDLED_PY%" "%APP_DIR%codex_usage_widget.py" --test --include-ui
) else (
  python "%APP_DIR%codex_usage_widget.py" --test --include-ui
)
echo.
pause
