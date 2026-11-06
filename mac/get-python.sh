#!/bin/bash
# 給「一鍵啟動.command」和「打包成App.command」共用：自動下載免安裝的 Python 3.12，使用者不用自己去官網找。
# 來源：python-build-standalone（https://github.com/astral-sh/python-build-standalone），下載後會核對 SHA-256，內容不符就不使用。
PY_TAG="20241016"
PY_VER="3.12.7"
PY_SHA_x86_64="60c5271e7edc3c2ab47440b7abf4ed50fbc693880b474f74f05768f5b657045a"
PY_SHA_aarch64="4c18852bf9c1a11b56f21bcf0df1946f7e98ee43e9e4c0c5374b2b3765cf9508"

# 用法：get_python <x86_64|aarch64> <放置資料夾>；成功時把 python 路徑放在變數 PYTHON
get_python() {
  local arch="$1" dest="$2" sha file url tmp
  PYTHON="$dest/bin/python3"
  if [ -x "$PYTHON" ] && "$PYTHON" -c 'import venv' >/dev/null 2>&1; then
    return 0
  fi
  case "$arch" in
    x86_64) sha="$PY_SHA_x86_64" ;;
    aarch64) sha="$PY_SHA_aarch64" ;;
    *) echo "不支援的晶片類型：$arch"; return 1 ;;
  esac
  file="cpython-$PY_VER+$PY_TAG-$arch-apple-darwin-install_only.tar.gz"
  url="https://github.com/astral-sh/python-build-standalone/releases/download/$PY_TAG/$file"
  tmp="${TMPDIR:-/tmp}/claude-usage-widget-$file"
  echo "正在下載 Python $PY_VER（約 16 MB，只有第一次需要）…"
  if ! curl -fL --retry 3 --connect-timeout 15 --max-time 900 -# -o "$tmp" "$url"; then
    echo "下載 Python 失敗：請確認網路連線（需要能連到 github.com），然後再開一次。"
    return 1
  fi
  if [ "$(shasum -a 256 "$tmp" | cut -d' ' -f1)" != "$sha" ]; then
    echo "下載的 Python 檔案不完整或內容不符，為了安全不使用它。請確認網路連線後再開一次。"
    rm -f "$tmp"
    return 1
  fi
  echo "正在解壓縮 Python…"
  mkdir -p "$dest" || return 1
  # 壓縮檔裡最上層是 python/ 資料夾，去掉這一層直接放進 dest
  if ! tar -xzf "$tmp" -C "$dest" --strip-components 1; then
    echo "解壓縮 Python 失敗，請確認磁碟空間足夠後再開一次。"
    return 1
  fi
  rm -f "$tmp"
  "$PYTHON" -c 'import venv' >/dev/null 2>&1 || { echo "Python 解壓縮後無法執行。"; return 1; }
  return 0
}
