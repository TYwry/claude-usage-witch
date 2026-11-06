@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 連結 GitHub（只需要執行一次）
set "REPO=claude-usage-widget"
set "PATH=%PATH%;%ProgramFiles%\Git\cmd;%ProgramFiles%\GitHub CLI;%LocalAppData%\Programs\Git\cmd"

echo ============================================
echo  連結 GitHub：安裝工具、登入、建立不公開的儲存庫
echo ============================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo 正在安裝 Git ...
  winget install -e --id Git.Git --silent --accept-package-agreements --accept-source-agreements
)
where git >nul 2>nul
if errorlevel 1 goto no_git

where gh >nul 2>nul
if errorlevel 1 (
  echo 正在安裝 GitHub CLI ...
  winget install -e --id GitHub.cli --silent --accept-package-agreements --accept-source-agreements
)
where gh >nul 2>nul
if errorlevel 1 goto no_gh

gh auth status >nul 2>nul
if not errorlevel 1 goto logged_in
echo.
echo 接下來會開啟瀏覽器登入 GitHub：
echo 1. 先複製畫面上顯示的 8 碼驗證碼
echo 2. 按 Enter 開啟瀏覽器，貼上驗證碼並按授權
echo.
gh auth login --web --hostname github.com --git-protocol https
gh auth status >nul 2>nul
if errorlevel 1 goto fail
:logged_in
gh auth setup-git

if not exist ".git" git init -b main
git config core.quotepath false

git config user.name >nul 2>nul
if not errorlevel 1 goto has_name
for /f "delims=" %%u in ('gh api user --jq .login') do set "GHLOGIN=%%u"
for /f "delims=" %%i in ('gh api user --jq .id') do set "GHID=%%i"
git config user.name "%GHLOGIN%"
git config user.email "%GHID%+%GHLOGIN%@users.noreply.github.com"
:has_name

call :check
if errorlevel 1 goto abort

git diff --cached --quiet
if errorlevel 1 (
  if exist ".commit-message.txt" (
    git commit -q -F ".commit-message.txt"
  ) else (
    git commit -q -m "首次上傳"
  )
  if errorlevel 1 goto fail
  if exist ".commit-message.txt" del ".commit-message.txt"
)

git remote get-url origin >nul 2>nul
if not errorlevel 1 (
  git push -u origin main
  if errorlevel 1 goto fail
  goto ok
)
gh repo create "%REPO%" --private --source . --remote origin --push
if errorlevel 1 goto fail

:ok
echo.
echo ============================================
echo  完成！已上傳到 GitHub（不公開）。
echo  以後修改完，雙擊 save.bat 就能存檔上傳。
echo ============================================
gh repo view --web >nul 2>nul
pause
exit /b 0

:no_git
echo [失敗] 無法自動安裝 Git，請到 https://git-scm.com/download/win 安裝後再執行一次。
pause
exit /b 1

:no_gh
echo [失敗] 無法自動安裝 GitHub CLI，請到 https://cli.github.com/ 安裝後再執行一次。
pause
exit /b 1

:abort
echo.
echo [已中止] 偵測到可能含個人資料或密碼的檔案，已取消上傳，什麼都沒有送出。
echo 請確認上面列出的檔案，把它移出資料夾或加進 .gitignore 後再試一次。
pause
exit /b 1

:fail
echo.
echo [失敗] 過程中出錯，請把這個視窗的畫面截圖。
pause
exit /b 1

rem ---- 安全檢查：暫存區裡有敏感檔案就中止並取消暫存 ----
:check
git add -A
git diff --cached --name-only > "%TEMP%\cuw_staged.txt"
findstr /i /r /c:"config\.json" /c:"history\.json" /c:"settings\.json" /c:"usage_log" /c:"last_page" /c:"error\.log" /c:"\.env" /c:"\.log$" /c:"\.key$" /c:"\.pem$" /c:"\.pfx$" /c:"\.venv/" /c:"^web/" /c:"secret" /c:"password" /c:"credential" "%TEMP%\cuw_staged.txt"
if errorlevel 1 (
  del "%TEMP%\cuw_staged.txt" >nul 2>nul
  exit /b 0
)
git reset -q
del "%TEMP%\cuw_staged.txt" >nul 2>nul
exit /b 1
