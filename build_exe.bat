@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 打包 ClaudeUsageWidget.exe
rem 進階用：把小工具打包成 exe 執行檔。需要先用「一鍵啟動.bat」完成安裝。
if not exist ".venv\setup_done.txt" (
  echo 請先雙擊「一鍵啟動.bat」完成安裝，再執行這個檔案。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6"
if errorlevel 1 goto fail
rem --onedir 啟動比較快（內嵌瀏覽器元件很大）；想要單一 exe 可改成 --onefile（每次啟動會較慢）
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name ClaudeUsageWidget --icon witch.ico --add-data "witch.ico;." usage_widget.py
if errorlevel 1 goto fail
echo.
echo 完成！執行檔在 dist\ClaudeUsageWidget\ClaudeUsageWidget.exe
echo 可以對它按右鍵 → 傳送到 → 桌面（建立捷徑）；要開機自動啟動，把捷徑放進 shell:startup
pause
exit /b 0
:fail
echo.
echo [失敗] 打包過程出錯，請把這個視窗的畫面截圖。
pause
exit /b 1
