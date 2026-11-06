@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 建立公開版 GitHub 儲存庫（打包者用，只需要執行一次）
rem 做法：原本不公開的儲存庫完全保留、不刪任何東西；另外建立一個新的公開儲存庫，
rem 只放目前的檔案（一次存檔），作者改用 GitHub 的匿名信箱，也不放「進度清單.md」。
rem 完成後，這個資料夾之後的 save.bat、publish-release.bat 都會改成上傳到新的公開儲存庫。
set "NEWREPO=claude-usage-witch"
set "PATH=%PATH%;%ProgramFiles%\Git\cmd;%ProgramFiles%\GitHub CLI;%LocalAppData%\Programs\Git\cmd"

if not exist ".git" (
  echo 還沒連結 GitHub，請先雙擊 setup-github.bat。
  goto fail
)
gh auth status >nul 2>nul
if errorlevel 1 (
  echo GitHub 還沒登入，請先雙擊 setup-github.bat。
  goto fail
)
git rev-parse --verify -q private-main >nul
if not errorlevel 1 (
  echo 這個檔案已經執行過了（已有 private-main 分支），不需要再執行。
  goto fail
)
git status --porcelain | findstr . >nul
if not errorlevel 1 (
  echo 還有修改沒存檔，請先雙擊 save.bat，再執行這個檔案。
  goto fail
)

echo 這次會：
echo  1. 在 GitHub 建立新的「公開」儲存庫 %NEWREPO%
echo  2. 只上傳目前的檔案，作者改用 GitHub 匿名信箱，不含「進度清單.md」
echo  3. 原本不公開的儲存庫和所有歷史紀錄都保留，不會刪除
echo.
choice /C YN /M "確定要建立公開儲存庫嗎？ Y=確定  N=取消"
if errorlevel 2 (
  echo 已取消，什麼都沒有改。
  pause
  exit /b 0
)

rem ---- 之後的存檔改用 GitHub 匿名信箱（只設定這個資料夾）----
set "GHLOGIN="
set "GHID="
for /f "delims=" %%u in ('gh api user --jq .login') do set "GHLOGIN=%%u"
for /f "delims=" %%i in ('gh api user --jq .id') do set "GHID=%%i"
if not defined GHID (
  echo 讀不到 GitHub 帳號資料，請確認網路連線。
  goto fail
)
git config user.name "%GHLOGIN%"
git config user.email "%GHID%+%GHLOGIN%@users.noreply.github.com"
echo 之後的存檔作者：%GHLOGIN%（匿名信箱）

rem ---- 舊的分支改名保留，再開一條沒有舊紀錄的新分支 ----
git branch -m main private-main
if errorlevel 1 goto fail
git checkout -q --orphan main
if errorlevel 1 goto fail
git rm -q --cached "進度清單.md" >nul 2>nul

call :check
if errorlevel 1 goto abort
git commit -q -m "Claude 用量小工具（公開版）"
if errorlevel 1 goto fail

echo 正在建立公開儲存庫並上傳...
gh repo create "%NEWREPO%" --public --source . --remote public --push
if errorlevel 1 goto fail

rem ---- 之後 save.bat、publish-release.bat 都上傳到新的公開儲存庫；舊的改叫 old-private ----
git remote rename origin old-private
if errorlevel 1 goto fail
git remote rename public origin
if errorlevel 1 goto fail
git branch -u origin/main main >nul

echo.
echo ============================================
echo  完成！公開儲存庫：https://github.com/%GHLOGIN%/%NEWREPO%
echo  原本不公開的儲存庫保留不動（本機分支 private-main）。
echo  接著請雙擊 publish-release.bat，在新的儲存庫發佈下載檔。
echo ============================================
pause
exit /b 0

:abort
echo.
echo [已中止] 偵測到可能含個人資料或密碼的檔案，已取消上傳，什麼都沒有送出。
echo 請把這個視窗的畫面截圖給 Claude。
pause
exit /b 1

:fail
echo.
echo [失敗] 過程中出錯，請把這個視窗的畫面截圖給 Claude。
pause
exit /b 1

rem ---- 安全檢查：暫存區裡有敏感檔案就中止並取消暫存（和 save.bat 相同）----
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
