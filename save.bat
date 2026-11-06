@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 存檔並上傳到 GitHub
set "PATH=%PATH%;%ProgramFiles%\Git\cmd;%ProgramFiles%\GitHub CLI;%LocalAppData%\Programs\Git\cmd"

if not exist ".git" (
  echo 還沒連結 GitHub，請先雙擊 setup-github.bat。
  pause
  exit /b 1
)

call :check
if errorlevel 1 goto abort

git diff --cached --quiet
if not errorlevel 1 (
  rem 上次 commit 成功但上傳失敗（例如斷網）時，補上傳
  git rev-list --count @{u}..HEAD 2>nul | findstr /x "0" >nul
  if errorlevel 1 (
    echo 發現上次還沒上傳成功的存檔，現在補上傳...
    goto push
  )
  echo 沒有新的修改需要存檔。
  pause
  exit /b 0
)

if exist ".commit-message.txt" (
  echo 這次的更新說明：
  echo --------------------------------------------
  type ".commit-message.txt"
  echo.
  echo --------------------------------------------
  git commit -q -F ".commit-message.txt"
  if errorlevel 1 goto fail
  del ".commit-message.txt"
  goto push
)

set "MSG="
set /p "MSG=請輸入這次修改的說明（直接按 Enter 會用「更新」）： "
if not defined MSG set "MSG=更新"
git commit -q -m "%MSG%"
if errorlevel 1 goto fail

:push
git push
if errorlevel 1 goto fail
echo.
echo 完成！已存檔並上傳到 GitHub。
pause
exit /b 0

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
