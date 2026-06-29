@echo off
setlocal
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Codex Usage Widget.lnk"
if exist "%LINK%" del "%LINK%"
echo Removed startup shortcut if it existed.
pause
