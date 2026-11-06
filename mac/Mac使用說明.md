# Claude 用量小工具 Mac 版（v4.10）

小女巫的 Mac 版和 Windows 版用的是同一個 `usage_widget.py`，表情、動畫、功能都一樣。這個 `mac` 資料夾放的是 Mac 專用的啟動腳本、打包腳本和圖示。

## 支援哪些 Mac

- macOS 11（Big Sur）以上。
- Intel 晶片和 M 系列晶片都可以用。打包成 App 時預設做 Intel 版，M 系列 Mac 會自動透過 Rosetta 2 執行（第一次開啟時 Mac 可能會問要不要安裝 Rosetta，按「安裝」即可）。

## 方法一：直接執行（打包者、自己用）

1. 把整個小工具資料夾（含 `usage_widget.py`、`witch.ico` 和 `mac` 資料夾）複製到 Mac。
2. 第一次先讓腳本可以雙擊（從 GitHub 下載的 ClaudeUsageWidget-mac.zip 已經設定好，可以跳過這一步）：打開「終端機」，輸入 `chmod +x `（最後有一個空格），把 `mac` 資料夾裡的兩個 `.command` 檔拖進終端機視窗，按 Enter。
3. 雙擊 `mac/一鍵啟動.command`。
   - 如果跳出「無法打開，因為它來自未識別的開發者」，改成對檔案按右鍵（或 Control + 點一下）→「打開」→ 再按「打開」。
   - 第一次會自動下載免安裝的 Python 和需要的元件（約 3 到 5 分鐘，不用自己安裝任何東西），之後雙擊就直接開啟。
4. 小女巫出現後會先跳出 Claude 登入視窗，登入後關掉視窗即可；也會問一次要不要「登入 Mac 時自動開啟」。

## 方法二：打包成 App

1. 雙擊 `mac/打包成App.command`（會自動下載打包用的 Python），完成後會產生：
   - `dist-mac/ClaudeUsageWidget.app`：可以拖進「應用程式」資料夾使用。
   - `release/ClaudeUsageWidget-mac-x86_64-v4.10.zip`：要分享給別人時傳這個。
2. 想做 Intel 和 M 系列都原生執行的通用版，在終端機輸入：`ARCH=universal2 bash mac/打包成App.command`（需要 python.org 的 universal2 版 Python）。

## 拿到 App 的人怎麼開

1. 解壓縮 ZIP，把 `ClaudeUsageWidget.app` 拖進「應用程式」資料夾。
2. 第一次開啟時，Mac 會擋下沒有付費簽章的 App：
   - 對 App 按右鍵 →「打開」→ 再按「打開」。
   - 如果沒有「打開」可以按（macOS 15 以後），請到「系統設定 → 隱私權與安全性」，往下找到被擋下的 ClaudeUsageWidget，按「強制打開」。
3. 只有第一次需要這樣，之後雙擊就能開。

## 使用方式

- 左鍵拖曳移動；滑鼠滾輪或觸控板上下滑動可以縮放；雙擊切換 5 小時／每週。
- 右鍵（觸控板兩指點一下）打開選單：大小、立即更新、顯示登入網頁、開啟變化紀錄、登入 Mac 時自動開啟、離開。
- 小女巫不會出現在 Dock 上，要結束請用右鍵選單的「離開」。

## 資料放在哪裡

登入狀態、設定、變化紀錄、錯誤紀錄都放在 `~/.claude_usage_widget/`（家目錄裡的隱藏資料夾），和 Windows 版的位置規則一樣。
開啟「登入 Mac 時自動開啟」時會在 `~/Library/LaunchAgents/com.ty.claude-usage-widget.plist` 建立一個設定檔；關掉時會移除它。如果之後把 App 搬到別的位置，請在右鍵選單關掉再打開一次。
