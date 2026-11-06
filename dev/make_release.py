"""打包者用：產生下載用的 ClaudeUsageWidget.zip（Windows）與 ClaudeUsageWidget-mac.zip（Mac），給 publish-release.bat 使用。"""
import os, time, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN_FILES = ["usage_widget.py", "一鍵啟動.bat", "build_exe.bat", "requirements.txt", "witch.ico", "建立桌面捷徑.bat"]
MAC_FILES = ["usage_widget.py", "witch.ico", "mac/一鍵啟動.command", "mac/打包成App.command", "mac/get-python.sh",
             "mac/requirements-mac.txt", "mac/witch.icns", "mac/Mac使用說明.md"]
out_dir = os.path.join(ROOT, "release")
os.makedirs(out_dir, exist_ok=True)


def add(z, name, top):
    src = os.path.join(ROOT, *name.split("/"))
    if not os.path.exists(src):
        raise SystemExit("[失敗] 找不到要打包的檔案：" + name)
    info = zipfile.ZipInfo(top + "/" + name, time.localtime(os.path.getmtime(src))[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3                      # 標成 Unix 格式，Mac 解壓縮時才會套用下面的權限
    mode = 0o755 if name.endswith(".command") else 0o644   # .command 要能直接雙擊執行
    info.external_attr = (0o100000 | mode) << 16
    with open(src, "rb") as f:
        data = f.read()
    if name.endswith((".command", ".sh")):
        data = data.replace(b"\r\n", b"\n")      # Mac 的腳本必須是 LF 換行
    z.writestr(info, data)


for zip_name, files, top in (("ClaudeUsageWidget.zip", WIN_FILES, "ClaudeUsageWidget"),
                             ("ClaudeUsageWidget-mac.zip", MAC_FILES, "ClaudeUsageWidget-mac")):
    out = os.path.join(out_dir, zip_name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        if top == "ClaudeUsageWidget":
            for name in files:
                z.write(os.path.join(ROOT, name), top + "/" + name)
        else:
            for name in files:
                add(z, name, top)
    print(out)
