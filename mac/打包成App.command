#!/bin/bash
# 打包者用：把小女巫打包成 Mac App（ClaudeUsageWidget.app），拿到 App 的人不用另外下載任何東西。
# 預設做 Intel 版（x86_64）：Intel Mac 直接執行，M 系列 Mac 會透過 Rosetta 2 執行。
# 想做 M 系列原生版：ARCH=arm64 bash mac/打包成App.command
# 想做 Intel + M 系列都原生的通用版：ARCH=universal2 bash mac/打包成App.command
#   （通用版需要先安裝 python.org 的 Python 3.12「universal2」版，其他兩種會自動下載 Python）
cd "$(dirname "$0")/.." || exit 1
APPDIR="$(pwd)"
ARCH="${ARCH:-x86_64}"
APP="$APPDIR/dist-mac/ClaudeUsageWidget.app"
VERSION="$(cat "$APPDIR/dev/version.txt" 2>/dev/null | tr -d 'v \r\n')"
[ -n "$VERSION" ] || VERSION="4.10"

fail() {
  echo
  echo "[失敗] $1"
  echo "請把這個視窗的畫面截圖給 Claude。"
  read -r -p "按 Enter 關閉視窗…"
  exit 1
}

source "$APPDIR/mac/get-python.sh" || fail "找不到 mac/get-python.sh。"
BUILD_VENV="$APPDIR/.venv-build-$ARCH"
case "$ARCH" in
  x86_64)
    if [ "$(uname -m)" = "arm64" ] && ! arch -x86_64 /usr/bin/true 2>/dev/null; then
      fail "這台 M 系列 Mac 還沒安裝 Rosetta 2，沒辦法做 Intel 版。
請在終端機輸入：softwareupdate --install-rosetta --agree-to-license，裝好後再開一次。"
    fi
    get_python x86_64 "$APPDIR/.python-build-x86_64" || fail "準備 Intel 版 Python 失敗。" ;;
  arm64)
    get_python aarch64 "$APPDIR/.python-build-arm64" || fail "準備 M 系列版 Python 失敗。" ;;
  universal2)
    PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    file "$PYTHON" 2>/dev/null | grep -q arm64 && file "$PYTHON" | grep -q x86_64 || \
      fail "做通用版需要 python.org 的 Python 3.12「macOS 64-bit universal2 installer」，請先安裝：https://www.python.org/downloads/macos/" ;;
  *) fail "ARCH 只能是 x86_64、arm64 或 universal2（目前是 $ARCH）。" ;;
esac

if [ ! -f "$BUILD_VENV/setup_done.txt" ]; then
  echo "正在準備打包用的環境（$ARCH）…"
  "$PYTHON" -m venv "$BUILD_VENV" || fail "建立打包環境失敗。"
  "$BUILD_VENV/bin/python" -m pip install --timeout 60 --upgrade pip || fail "更新 pip 失敗，請確認網路連線。"
  "$BUILD_VENV/bin/python" -m pip install --timeout 60 -r mac/requirements-mac.txt "pyinstaller>=6,<7" || fail "安裝套件失敗，請確認網路連線。"
  echo ok > "$BUILD_VENV/setup_done.txt"
fi

echo "正在打包（$ARCH），約需幾分鐘…"
"$BUILD_VENV/bin/python" -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name ClaudeUsageWidget \
  --icon "$APPDIR/mac/witch.icns" \
  --add-data "$APPDIR/witch.ico:." \
  --target-arch "$ARCH" \
  --osx-bundle-identifier com.ty.claude-usage-widget \
  --distpath "$APPDIR/dist-mac" --workpath "$APPDIR/build-mac" --specpath "$APPDIR/build-mac" \
  "$APPDIR/usage_widget.py" || fail "打包過程出錯。"

# 設定 App 資訊：不顯示 Dock 圖示（像桌面小工具）、版本號、最低支援 macOS 11
PL="$APP/Contents/Info.plist"
setplist() { /usr/libexec/PlistBuddy -c "Set :$1 $3" "$PL" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :$1 $2 $3" "$PL"; }
setplist LSUIElement bool true || fail "寫入 App 設定失敗。"
setplist CFBundleShortVersionString string "$VERSION" || fail "寫入 App 設定失敗。"
setplist CFBundleVersion string "$VERSION" || fail "寫入 App 設定失敗。"
setplist LSMinimumSystemVersion string 11.0 || fail "寫入 App 設定失敗。"

# 改過 Info.plist 後要重新簽章（免費的本機簽章），不然 M 系列 Mac 會拒絕執行
codesign --force --deep --sign - "$APP" || fail "重新簽章失敗。"

mkdir -p "$APPDIR/release"
ZIP="$APPDIR/release/ClaudeUsageWidget-mac-$ARCH-v$VERSION.zip"
ditto -c -k --keepParent "$APP" "$ZIP" || fail "壓縮成 ZIP 失敗。"

echo
echo "完成！"
echo "App：$APP"
echo "要分享給別人的壓縮檔：$ZIP"
echo "可以把 App 拖進「應用程式」資料夾使用。"
read -r -p "按 Enter 關閉視窗…"
exit 0
