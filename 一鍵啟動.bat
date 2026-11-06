@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Claude 用量小工具
set "VPY=%~dp0.venv\Scripts\python.exe"
set "VPYW=%~dp0.venv\Scripts\pythonw.exe"
set "APPDIR=%~dp0"

if exist ".venv\setup_done.txt" goto launch

echo ============================================
echo  第一次使用：正在準備執行環境
echo  約需 3 到 5 分鐘，只有第一次需要，請不要關閉視窗
echo ============================================
echo.
set "PY="
for %%v in (3.12 3.13 3.11 3.10) do call :trypy %%v
if not defined PY call :trypy 3
if not defined PY call :trypython

if not defined PY (
  echo 找不到 Python，正在自動安裝 Python 3.12 ...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo.
  echo [失敗] 無法自動安裝 Python。
  echo 請到 https://www.python.org/downloads/ 安裝 Python 3.12，
  echo 安裝時勾選 "Add python.exe to PATH"，然後再雙擊這個檔案一次。
  pause
  exit /b 1
)
echo 使用 Python: %PY%

"%PY%" -m venv .venv
if errorlevel 1 goto fail
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install "PySide6>=6.6,<7"
if errorlevel 1 goto fail
echo ok> ".venv\setup_done.txt"

echo.
echo 正在桌面建立捷徑「Claude 用量小工具」...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Claude 用量小工具.lnk'); $s.TargetPath=$env:VPYW; $s.Arguments='usage_widget.py'; $s.WorkingDirectory=$env:APPDIR; if (Test-Path ($env:APPDIR+'witch.ico')) { $s.IconLocation=$env:APPDIR+'witch.ico' }; $s.Save()"

echo.
choice /C YN /M "要讓小工具開機時自動啟動嗎？ Y=要  N=不要"
if errorlevel 2 goto done_setup
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Claude 用量小工具.lnk'); $s.TargetPath=$env:VPYW; $s.Arguments='usage_widget.py'; $s.WorkingDirectory=$env:APPDIR; if (Test-Path ($env:APPDIR+'witch.ico')) { $s.IconLocation=$env:APPDIR+'witch.ico' }; $s.Save()"
echo 已設定開機自動啟動。

:done_setup
echo.
echo 準備完成！以後直接點桌面捷徑就能開啟。

:launch
start "" "%VPYW%" usage_widget.py
exit /b 0

:fail
echo.
echo [失敗] 安裝過程出錯，請把這個視窗的畫面截圖給 Claude。
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1

:trypy
if defined PY exit /b 0
for /f "delims=" %%i in ('py -%1 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
exit /b 0

:trypython
for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
exit /b 0
