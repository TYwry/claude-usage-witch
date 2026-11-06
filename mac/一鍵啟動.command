#!/bin/bash
# Claude 用量小工具（Mac）：第一次開啟會自動下載需要的東西，之後開啟直接顯示小女巫
cd "$(dirname "$0")/.." || exit 1
APPDIR="$(pwd)"
VENV="$APPDIR/.venv-mac"

fail() {
  echo
  echo "[失敗] $1"
  echo "請把這個視窗的畫面截圖給 Claude。"
  read -r -p "按 Enter 關閉視窗…"
  exit 1
}

[ -f "$APPDIR/usage_widget.py" ] || fail "找不到 usage_widget.py，請確認 mac 資料夾還放在小工具資料夾裡面。"

if [ ! -f "$VENV/setup_done.txt" ]; then
  echo "============================================"
  echo " 第一次使用：正在自動下載並準備執行環境"
  echo " 約需 3 到 5 分鐘，只有第一次需要，請不要關閉視窗"
  echo "============================================"
  echo
  source "$APPDIR/mac/get-python.sh" || fail "找不到 mac/get-python.sh，請重新下載完整的 ZIP 檔。"
  case "$(uname -m)" in
    arm64) ARCH=aarch64 ;;      # M 系列晶片
    *) ARCH=x86_64 ;;           # Intel 晶片
  esac
  get_python "$ARCH" "$APPDIR/.python-mac" || fail "準備 Python 失敗。"
  "$PYTHON" -m venv "$VENV" || fail "建立執行環境失敗。"
  echo "正在下載小工具需要的元件（約 300 MB）…"
  "$VENV/bin/python" -m pip install --timeout 60 --upgrade pip || fail "更新 pip 失敗，請確認網路連線後再開一次。"
  "$VENV/bin/python" -m pip install --timeout 60 -r mac/requirements-mac.txt || fail "下載元件失敗，請確認網路連線後再開一次。"
  echo ok > "$VENV/setup_done.txt"
  echo
  echo "準備完成！以後直接雙擊這個檔案就能開啟小女巫。"
fi

# 用子殼層在背景啟動，關掉終端機視窗時小女巫不會被一起關掉，也不會跳出「要終止程序嗎」
( nohup "$VENV/bin/python" "$APPDIR/usage_widget.py" >/dev/null 2>&1 & )
echo "小女巫已開啟（第一次會先出現 Claude 登入視窗），這個終端機視窗可以關掉。"
exit 0
