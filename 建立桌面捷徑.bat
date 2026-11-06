@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "VPYW=%~dp0.venv\Scripts\pythonw.exe"
set "APPDIR=%~dp0"
if not exist "%VPYW%" (
  echo 還沒安裝，請先雙擊「一鍵啟動.bat」。
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Claude 用量小工具.lnk'); $s.TargetPath=$env:VPYW; $s.Arguments='usage_widget.py'; $s.WorkingDirectory=$env:APPDIR; $s.IconLocation=$env:APPDIR+'witch.ico'; $s.Description='Claude 用量小工具'; $s.Save()"
echo 已在桌面建立「Claude 用量小工具」捷徑（女巫圖示）。
echo 如果桌面圖示沒有馬上變成女巫，按 F5 重新整理桌面即可。
pause
