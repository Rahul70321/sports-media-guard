@echo off
title Push Sports Media Guard to GitHub
cd /d "%~dp0"
cls

echo =======================================================
echo   SPORTS MEDIA GUARD - UPLOADING TO GITHUB
echo =======================================================
echo.

git add .
git commit -m "Configure GitHub Pages automatic enablement"
git push origin main

echo.
echo =======================================================
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS! Pushed to GitHub.
) else (
    echo An issue occurred during push.
)
echo =======================================================
pause
