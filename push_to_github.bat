@echo off
title Push Sports Media Guard to GitHub
cd /d "%~dp0"
cls

echo =======================================================
echo   SPORTS MEDIA GUARD - UPLOADING TO GITHUB
echo =======================================================
echo.

echo [1/4] Cleaning previous commit containing exposed secrets...
git reset --soft HEAD~1

echo.
echo [2/4] Staging all files with sanitized Render blueprint...
git add .

echo.
echo [3/4] Creating clean commit without secrets...
git commit -m "Initial commit: Sports Media Guard full stack platform"

echo.
echo [4/4] Pushing to https://github.com/Rahul70321/sports-media-guard ...
git push -u origin main

echo.
echo =======================================================
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS! All files and folders have been uploaded to GitHub!
    echo Visit: https://github.com/Rahul70321/sports-media-guard
) else (
    echo Push encountered an issue. Please check the message above.
)
echo =======================================================
echo.
pause
