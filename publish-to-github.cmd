@echo off
setlocal
cd /d "%~dp0"

echo This will publish Codex Usage Widget to GitHub.
echo.

git --version >nul 2>nul
if errorlevel 1 (
  echo Git is not installed or not available in PATH.
  pause
  exit /b 1
)

if not exist ".git" (
  git init
)

set /p GIT_NAME=Commit display name:
if "%GIT_NAME%"=="" (
  echo Commit display name is required.
  pause
  exit /b 1
)

set /p GIT_EMAIL=Commit email:
if "%GIT_EMAIL%"=="" (
  echo Commit email is required.
  pause
  exit /b 1
)

git config user.name "%GIT_NAME%"
git config user.email "%GIT_EMAIL%"

git add .
git update-index --chmod=+x start-mac.command

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Initial release"
) else (
  echo Nothing new to commit.
)

git branch -M main

set /p REPO_URL=Paste GitHub repository HTTPS URL:
if "%REPO_URL%"=="" (
  echo Repository URL is required.
  pause
  exit /b 1
)

git remote remove origin >nul 2>nul
git remote add origin "%REPO_URL%"
git push -u origin main

echo.
echo Done. Your project is now on GitHub.
pause
