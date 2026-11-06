@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 發佈下載版本到 GitHub（打包者用）
rem 這是打包者用的腳本：用這台電腦的執行環境產生 Windows 與 Mac 兩個下載檔，再發佈到 GitHub。
set "PATH=%PATH%;%ProgramFiles%\Git\cmd;%ProgramFiles%\GitHub CLI;%LocalAppData%\Programs\Git\cmd"
set "VPY=%~dp0.venv\Scripts\python.exe"

if not exist ".git" (
  echo 還沒連結 GitHub，請先雙擊 setup-github.bat。
  pause
  exit /b 1
)
if not exist "%VPY%" (
  echo 找不到執行環境，請先雙擊「一鍵啟動.bat」完成安裝。
  pause
  exit /b 1
)

git status --porcelain | findstr . >nul
if not errorlevel 1 (
  echo 還有修改沒存檔，請先雙擊 save.bat，再執行這個檔案。
  pause
  exit /b 1
)

set "VER="
if exist "dev\version.txt" set /p VER=<"dev\version.txt"
if not defined VER (
  echo 找不到版本號檔案 dev\version.txt。
  goto fail
)
echo 這次要發佈的版本：%VER%

echo 正在產生下載檔...
"%VPY%" dev\make_release.py
if errorlevel 1 goto fail
git push
if errorlevel 1 goto fail
rem 這個資料夾有新舊兩個 GitHub 儲存庫，明確指定發佈到 origin（目前的公開儲存庫），避免 gh 不知道要用哪一個
set "REPO="
for /f "delims=" %%r in ('git remote get-url origin') do set "REPO=%%r"
if not defined REPO goto fail
set "REPO=%REPO:https://github.com/=%"
set "REPO=%REPO:.git=%"
echo 發佈到：%REPO%
echo 正在發佈到 GitHub...
gh release create "%VER%" --repo "%REPO%" "release\ClaudeUsageWidget.zip" "release\ClaudeUsageWidget-mac.zip" --title "%VER%" --notes-file "dev\release-notes.md"
if errorlevel 1 goto fail

echo.
echo 完成！已發佈 %VER%（Windows 與 Mac 兩個下載檔）。
echo 注意：儲存庫目前是「不公開」，別人點下載連結會看到 404，
echo 要給別人下載請先把儲存庫改成公開。
pause
exit /b 0

:fail
echo.
echo [失敗] 發佈過程出錯（這個版本號是否已經發佈過？），請把這個視窗的畫面截圖。
pause
exit /b 1
