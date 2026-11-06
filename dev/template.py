"""Claude 用量小工具 v4.10：小女巫 + 藥水瓶 (Windows 10 / macOS, PySide6)
python usage_widget.py --demo   假資料預覽
python usage_widget.py          讀取 claude.ai 的 Settings > Usage
操作: 左鍵拖曳移動 / 滾輪縮放 / 雙擊切換 5小時與每週 / 右鍵選單
角色與瓶蓋圖片已內嵌在本檔案中，單一檔案即可執行。
"""
import sys, os, re, csv, math, random, time, json, base64
from PySide6.QtCore import Qt, QTimer, QUrl, QPointF, QRectF, QObject, Signal, QLockFile
from PySide6.QtGui import (QPainter, QColor, QPainterPath, QLinearGradient, QRadialGradient, QFont,
                           QFontMetricsF, QPixmap, QPen, QBrush, QDesktopServices, QIcon)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QLineEdit, QVBoxLayout, QLabel, QMessageBox
from PySide6.QtNetwork import QLocalServer, QLocalSocket

IS_MAC = sys.platform == "darwin"
UI_FONT = "PingFang TC" if IS_MAC else "Microsoft JhengHei"   # 中文字型：Mac 用內建的蘋方，Windows 用微軟正黑體
APP_ID = "com.ty.claude-usage-widget"
LAUNCH_AGENT = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", APP_ID + ".plist")   # Mac 登入時自動開啟的設定檔
URL = "https://claude.ai/settings/usage"
POLL_SEC = 60
KEEP_DAYS = 30                 # usage_log.csv 只保留最近幾天
SHOCK_SEC = 8                  # 驚嚇表情維持幾秒
RELIEF_SEC = 3.5               # 驚嚇結束後「安心」鬆一口氣的表情維持幾秒，之後變回原狀
SCARED_AT = 10                 # 5 小時或每週剩餘 % 小於等於這個數字時，露出「有點可怕」的害怕表情
DATA_DIR = os.path.join(os.path.expanduser("~"), ".claude_usage_widget")
LOG = os.path.join(DATA_DIR, "usage_log.csv")
DUMP = os.path.join(DATA_DIR, "last_page.txt")
SETTINGS = os.path.join(DATA_DIR, "settings.json")
os.makedirs(DATA_DIR, exist_ok=True)
INK = QColor(28, 8, 92)
ASSETS = {}  # __ASSETS__


def C(r, g, b, a=255):
    return QColor(r, g, b, a)


def grad(x0, y0, x1, y1, *stops):
    gr = QLinearGradient(x0, y0, x1, y1)
    for pos, col in stops:
        gr.setColorAt(pos, col)
    return QBrush(gr)


def star(cx, cy, r, n=4, inner=0.3):
    p = QPainterPath()
    for i in range(2 * n):
        a = -math.pi / 2 + i * math.pi / n
        rad = r if i % 2 == 0 else r * inner
        pt = (cx + rad * math.cos(a), cy + rad * math.sin(a))
        p.moveTo(*pt) if i == 0 else p.lineTo(*pt)
    p.closeSubpath()
    return p


def outlined_text(g, rect, text, font, fill, ink, w):
    fm = QFontMetricsF(font)
    path = QPainterPath()
    path.addText(rect.center().x() - fm.horizontalAdvance(text) / 2,
                 rect.center().y() + (fm.ascent() - fm.descent()) / 2, font, text)
    g.setPen(QPen(ink, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); g.setBrush(Qt.NoBrush); g.drawPath(path)
    g.setPen(Qt.NoPen); g.setBrush(fill); g.drawPath(path)


def num(v, default, lo=None, hi=None):
    """把設定檔裡的值轉成數字；格式不對就用預設值。"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    if v != v:
        return default
    if lo is not None:
        v = max(lo, min(hi, v))
    return v


def prune_log(days=KEEP_DAYS):
    """刪掉 usage_log.csv 裡超過 days 天的紀錄（無法判讀日期的列保留）。"""
    if not os.path.exists(LOG):
        return
    cut = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - days * 86400))
    try:
        with open(LOG, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if len(rows) < 2:
            return
        head, body = rows[0], rows[1:]
        keep = [r for r in body if not (r and re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$", r[0])) or r[0] >= cut]
        if len(keep) == len(body):
            return
        tmp = LOG + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([head] + keep)
        os.replace(tmp, LOG)
    except (OSError, ValueError, csv.Error):
        # 檔案被鎖住或內容損壞（例如被其他程式改存成別的編碼）：這次先不清，不讓程式當掉，原因記在 error.log
        import traceback
        log_error("清理舊的變化紀錄失敗\n" + traceback.format_exc())


def parse_reset(text, now=None):
    """從用量頁文字找出 5 小時額度（Current session）的重置時間，回傳時間戳（秒），找不到回傳 None。
    支援：「Resets at 5:40 AM」「Resets in 2 hr 15 min」，以及中文介面的「5:40 重置」「2 小時 15 分鐘後重置」。"""
    now = time.time() if now is None else now
    i = -1
    for key in ("Current session", "目前工作階段", "目前的工作階段", "目前時段"):
        i = text.find(key)
        if i >= 0:
            break
    if i < 0:
        return None
    seg = text[i:i + 200]
    j = seg.find("%")                  # 只看到「72% used」之前
    seg = seg[:j] if j > 0 else seg
    # 相對時間：in 2 hr 15 min ／ 2 小時 15 分鐘後
    m = re.search(r"\bin\s+(?:(\d+)\s*(?:hr|hrs|hour|hours|h)\b)?\s*(?:(\d+)\s*(?:min|mins|minute|minutes|m)\b)?", seg, re.I)
    if not (m and (m.group(1) or m.group(2))):
        m = re.search(r"(?:(\d+)\s*小時)?\s*(?:(\d+)\s*分(?:鐘)?)?\s*後", seg)
    if m and (m.group(1) or m.group(2)):
        return now + int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60
    # 絕對時間：5:40 AM ／ 下午 3:00 ／ 17:40
    m = re.search(r"(上午|下午)?\s*(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?", seg)
    if not m:
        return None
    h, mi = int(m.group(2)), int(m.group(3))
    ap = (m.group(4) or m.group(1) or "").upper()
    if ap in ("PM", "下午") and h < 12:
        h += 12
    if ap in ("AM", "上午") and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    lt = time.localtime(now)
    ts = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, mi, 0, 0, 0, -1))
    if ts <= now - 60:                 # 已經過了 → 是明天的這個時間
        ts += 86400
    return ts


def reset_text(ts, now=None):
    """時間戳 → 「05:40 重置 · 還有1小時20分」"""
    if ts is None:
        return ""
    now = time.time() if now is None else now
    left = int(ts - now)
    if left <= 0:
        return "即將重置"
    hh, mm = left // 3600, (left % 3600 + 59) // 60
    if mm == 60:
        hh, mm = hh + 1, 0
    cd = ("%d小時%d分" % (hh, mm)) if hh else ("%d分" % max(1, mm))
    return "%s 重置 · 還有%s" % (time.strftime("%H:%M", time.localtime(ts)), cd)


def load_settings():
    if not os.path.exists(SETTINGS):
        return {}                       # 第一次啟動還沒有設定檔：用預設值
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            return cfg
        raise ValueError("設定檔內容不是物件")
    except (OSError, ValueError):
        # 設定檔損壞：先備份成 settings.bad.json 再用預設值，避免下次又讀到壞檔
        import traceback
        log_error("設定檔損壞，已備份成 settings.bad.json 並改用預設值\n" + traceback.format_exc())
        try:
            os.replace(SETTINGS, os.path.join(DATA_DIR, "settings.bad.json"))
        except OSError:
            log_error("備份損壞的設定檔失敗：" + traceback.format_exc())
        return {}


def install_crash_log():
    """pythonw 沒有黑視窗，錯誤會默默消失；改寫進 error.log 方便除錯（超過 200 KB 自動清空）。"""
    path = os.path.join(DATA_DIR, "error.log")
    def hook(tp, val, tb):
        import traceback
        try:
            if os.path.exists(path) and os.path.getsize(path) > 200_000:
                os.remove(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n=== %s ===\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                traceback.print_exception(tp, val, tb, file=f)
        except Exception:
            pass   # 連錯誤紀錄都寫不進去（例如磁碟滿了）時沒有別的地方可記；下面仍會照常輸出錯誤
        sys.__excepthook__(tp, val, tb)
    sys.excepthook = hook


def log_error(msg):
    """把錯誤寫進 error.log（超過 200 KB 自動清空，和閃退紀錄同一個檔案）。"""
    path = os.path.join(DATA_DIR, "error.log")
    try:
        if os.path.exists(path) and os.path.getsize(path) > 200_000:
            os.remove(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n=== %s ===\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass   # 連記錄檔都寫不進去時已經沒有地方可記；畫面上的提示照常顯示


def update_settings(**kv):
    """只更新 settings.json 裡指定的欄位，其他欄位保留。"""
    cfg = load_settings()
    cfg.update(kv)
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        import traceback
        log_error(traceback.format_exc())


def mac_hide_dock_icon():
    """Mac：用 python 直接執行時，Dock 不要多出一個 Python 圖示，只留小女巫本人。
    （打包成 .app 時由 Info.plist 的 LSUIElement 負責，不需要這一步）"""
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().setActivationPolicy_(1)   # 1 = 配件程式：不顯示 Dock 圖示
    except Exception:
        import traceback
        log_error(traceback.format_exc())   # 沒裝 pyobjc 時只是 Dock 多一個圖示，小女巫照常運作


def mac_activate():
    """Mac：小女巫不在 Dock 上，要跳出視窗時先把程式叫到最前面，視窗才不會躲在別的程式後面。"""
    if not IS_MAC:
        return
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        import traceback
        log_error(traceback.format_exc())   # 叫不到最前面只是視窗可能被擋住，不影響功能


def mac_autostart_on():
    return os.path.exists(LAUNCH_AGENT)


def mac_set_autostart(on):
    """Mac：登入時自動開啟（寫在目前使用者的 ~/Library/LaunchAgents，不需要管理員權限）。
    成功回傳 None，失敗回傳白話原因。"""
    import plistlib
    if getattr(sys, "frozen", False):
        args = [sys.executable]                                  # 打包好的 .app
    else:
        args = [sys.executable, os.path.abspath(__file__)]       # 用 python 直接執行
    try:
        if on:
            os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
            with open(LAUNCH_AGENT, "wb") as f:
                plistlib.dump({"Label": APP_ID, "ProgramArguments": args, "RunAtLoad": True,
                               "LimitLoadToSessionType": "Aqua", "ProcessType": "Interactive"}, f)
        elif os.path.exists(LAUNCH_AGENT):
            os.remove(LAUNCH_AGENT)
        return None
    except OSError as ex:
        import traceback
        log_error(traceback.format_exc())
        return "沒辦法%s「登入時自動開啟」：%s\n可以稍後再從右鍵選單試一次。" % ("開啟" if on else "關閉", ex)


def mac_first_run_ask(parent):
    """Mac 第一次啟動時問一次要不要登入時自動開啟（預設不要），之後可以從右鍵選單改。"""
    if load_settings().get("autostart_asked"):
        return
    box = QMessageBox(QMessageBox.Question, "Claude 用量小工具",
                      "要讓小女巫在每次登入 Mac 時自動開啟嗎？\n之後也可以從小女巫的右鍵選單更改。", parent=parent)
    yes = box.addButton("要", QMessageBox.AcceptRole)
    no = box.addButton("不用", QMessageBox.RejectRole)
    box.setDefaultButton(no)
    box.setEscapeButton(no)
    mac_activate()
    box.exec()
    update_settings(autostart_asked=True)
    if box.clickedButton() is yes:
        err = mac_set_autostart(True)
        if err:
            QMessageBox.warning(parent, "Claude 用量小工具", err)


# 每個使用者帳號只允許一個小工具在跑：兩個同時跑會搶同一份登入資料，後開的那個會一直讀不到數字
INSTANCE_KEY = "claude_usage_widget_" + re.sub(r"\W", "_", os.path.expanduser("~"))


def notify_running():
    """已經有小工具在跑時，請它把小女巫叫到前面，回傳 True。"""
    s = QLocalSocket()
    s.connectToServer(INSTANCE_KEY)
    if not s.waitForConnected(800):
        return False
    s.write(b"show")
    s.waitForBytesWritten(800)
    s.disconnectFromServer()
    return True


class LoginWindow(QWidget):
    closed = Signal()

    def closeEvent(self, e):
        super().closeEvent(e)
        self.closed.emit()


class Reader(QObject):
    """用已登入的內嵌瀏覽器定時載入用量頁，從頁面文字取出百分比。"""
    updated = Signal(int, object, object)   # 5小時已用%、每週已用%、5小時重置時間戳
    status = Signal(str)

    def __init__(self):
        super().__init__()
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView
        web = os.path.join(DATA_DIR, "web")
        self.profile = QWebEngineProfile("claude_usage", self)
        self.profile.setPersistentStoragePath(web)
        self.profile.setCachePath(web)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self.page = QWebEnginePage(self.profile, self)
        self.web = QWebEngineView()
        self.web.setPage(self.page)
        self.view = LoginWindow()
        self.view.closed.connect(lambda: QTimer.singleShot(300, self.refresh))
        self.view.resize(960, 720)
        self.view.setWindowTitle("Claude 登入 / 用量頁面（登入完成後直接關閉此視窗）")
        tip = QLabel("用 Email 登入時，可把信件裡的登入連結貼到下面這一格，按 Enter 開啟")
        tip.setContentsMargins(8, 6, 8, 2)
        self.bar = QLineEdit()
        self.bar.returnPressed.connect(self._go)
        self.web.urlChanged.connect(lambda u: self.bar.setText(u.toString()))
        lay = QVBoxLayout(self.view)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(tip)
        lay.addWidget(self.bar)
        lay.addWidget(self.web, 1)          # 多出來的空間都給網頁
        self.asked_login = False
        self.page.loadFinished.connect(lambda ok: QTimer.singleShot(4000, self._grab) if ok
                                       else self.status.emit("頁面載入失敗，稍後重試"))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(POLL_SEC * 1000)
        self.refresh()

    def _go(self):
        u = QUrl.fromUserInput(self.bar.text().strip())
        if u.scheme() == "http":
            u.setScheme("https")           # 一律改用加密連線
        if u.scheme() == "https":
            self.web.load(u)

    def show_login(self):
        mac_activate()
        self.view.show(); self.view.raise_(); self.view.activateWindow()   # Mac 上要主動叫到最前面，不然可能躲在別的視窗後面

    def shutdown(self):
        """結束前依序釋放瀏覽器元件，避免關閉時的 Release of profile 警告。"""
        self.timer.stop()
        self.web.setPage(None)
        self.page.deleteLater()
        self.web.deleteLater()
        self.view.deleteLater()

    def refresh(self):
        if self.view.isVisible():   # 登入視窗開著時不自動重載
            return
        self.page.load(QUrl(URL))

    def _grab(self):
        self.page.runJavaScript("document.body.innerText", self._parse)

    def _parse(self, text):
        text = text if isinstance(text, str) else ""
        try:
            with open(DUMP, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass   # 例如檔案被其他程式鎖住：只是除錯用的副本，不影響更新數字
        pat = r"(\d{1,3})\s*%\s*(?:used|已使用|已用)|(?:已使用|已用)\s*(\d{1,3})\s*%"
        vals = [int(a or b) for a, b in re.findall(pat, text)]
        if not vals:
            self.status.emit("讀不到用量：請右鍵→顯示登入網頁並登入")
            if not self.asked_login:
                self.asked_login = True
                self.show_login()
            return
        self.updated.emit(vals[0], vals[1] if len(vals) > 1 else None, parse_reset(text))
        self.status.emit("已更新 " + time.strftime("%H:%M:%S"))


class Potion(QWidget):
    IW, IH = 940, 1674            # 內部座標 = 原圖像素
    F = 300 / 940                 # 內部座標 -> 基準視窗 300 x 534
    CX, CY, RX, RY = 467.5, 1235.0, 446.5, 424.0

    def __init__(self, reader=None, demo=False):
        super().__init__()
        self.reader = reader
        self.drag = None
        self.demo = demo
        self.pruned = time.time()
        if not demo:
            prune_log()             # 啟動時先清掉 30 天前的紀錄
        cfg = load_settings()
        self.s = num(cfg.get("scale_v4"), 0.7, 0.35, 2.0)
        self.mode = 1 if cfg.get("mode") == 1 else 0
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        if IS_MAC:
            self.setWindowFlag(Qt.NoDropShadowWindowHint)      # Mac：透明視窗不要多一圈陰影外框
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)   # Mac：切到別的程式時，小女巫也不會自己藏起來
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.apply_scale()
        self.move(*self.safe_pos(num(cfg.get("x"), 80), num(cfg.get("y"), 60)))
        self.session, self.weekly = None, None
        self.disp, self.t0, self.pop = 0.0, time.time(), None
        self.reset_ts = None            # 5 小時額度的重置時間（時間戳）
        self.sad = 0.0                  # 哭哭模式程度 0~1（剩餘 0% 時漸漸變成 1）
        self.shock, self.shock_t = 0.0, None   # 驚嚇程度 0~1、開始嚇到的時間
        self.fear = 0.0                 # 害怕程度 0~1（剩餘額度偏低時漸漸變成 1）
        self.relief = 0.0               # 安心程度 0~1（驚嚇結束後鬆一口氣）
        self.spr = {}
        for name, (b64, x, y, w, h) in ASSETS.items():
            pm = QPixmap(); pm.loadFromData(base64.b64decode(b64), "PNG")
            self.spr[name] = (pm, x, y, w, h)
        self.bubbles = [[random.random(), random.random(), random.uniform(.04, .12), random.random()] for _ in range(10)]
        if reader:
            reader.updated.connect(self.on_update)
            reader.status.connect(self.setToolTip)
        t = QTimer(self)
        t.timeout.connect(self.tick)
        t.start(33)

    # ---- 設定 / 大小 ----
    def apply_scale(self):
        self.setFixedSize(int(self.IW * self.F * self.s), int(self.IH * self.F * self.s))

    def set_scale(self, v):
        self.s = max(0.35, min(2.0, v))
        self.apply_scale(); self.save()

    def safe_pos(self, x, y):
        """存檔的位置若已不在任何螢幕上（例如拔掉外接螢幕），改放回主螢幕左上角。"""
        x, y = int(x), int(y)
        for sc in QApplication.screens():
            g = sc.availableGeometry()
            if g.contains(x + self.width() // 2, y + 20):
                return x, y
        g = QApplication.primaryScreen().availableGeometry()
        return g.x() + 80, g.y() + 60

    def save(self):
        update_settings(scale_v4=self.s, mode=self.mode, x=self.x(), y=self.y())   # 保留其他設定欄位

    # ---- 資料 ----
    def on_update(self, s, wk, reset=None):
        self.reset_ts = reset
        if self.session is not None and s != self.session:
            d = s - self.session
            self.pop = (("-%d%%" % d) if d > 0 else "重置!", time.time())   # 顯示剩餘量的變化
            if not self.demo:
                self.write_log(s, wk, d)
                if time.time() - self.pruned > 6 * 3600:
                    prune_log(); self.pruned = time.time()
        more = lambda new, old: new is not None and old is not None and new > old
        if (more(s, self.session) or more(wk, self.weekly)) and self.left(s) > 0:
            self.shock_t = time.time()          # 用量有增加就嚇一跳（重置不算；用完時改由哭哭模式接手）
        self.session, self.weekly = s, wk

    def write_log(self, s, wk, d):
        try:
            new = not os.path.exists(LOG)
            with open(LOG, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["time", "session", "weekly", "delta"])
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), s, wk, d])
        except OSError:
            pass   # 例如 CSV 正被 Excel 開著而鎖住：跳過這筆，不讓程式當掉

    @staticmethod
    def left(used):
        """已使用 % -> 剩餘 %"""
        return None if used is None else max(0, min(100, 100 - used))

    def value(self):
        """目前主顯示的「剩餘」百分比"""
        return self.left(self.session if self.mode == 0 else self.weekly)

    def tick(self):
        v = self.value()
        if v is not None:
            self.disp += (v - self.disp) * 0.06
        self.sad += ((1.0 if v == 0 else 0.0) - self.sad) * 0.05
        on = self.shock_t is not None and time.time() - self.shock_t < SHOCK_SEC and v != 0
        self.shock += ((1.0 if on else 0.0) - self.shock) * (0.35 if on else 0.15)   # 一下子嚇到
        rel = (self.shock_t is not None and SHOCK_SEC <= time.time() - self.shock_t < SHOCK_SEC + RELIEF_SEC and v != 0)
        self.relief += ((1.0 if rel else 0.0) - self.relief) * (0.15 if rel else 0.08)   # 接著鬆一口氣，再慢慢變回笑臉
        low = any(x is not None and x <= SCARED_AT for x in (self.left(self.session), self.left(self.weekly)))
        self.fear += ((1.0 if low and v != 0 else 0.0) - self.fear) * 0.05
        self.update()

    # ---- 繪製 ----
    def bottle_path(self):
        p = QPainterPath(); p.addEllipse(QPointF(self.CX, self.CY), self.RX, self.RY)
        f = QPainterPath(); f.moveTo(332, 812); f.lineTo(332, 850)
        f.cubicTo(334, 872, 290, 874, 204, 893); f.lineTo(204, 960); f.lineTo(731, 960); f.lineTo(731, 893)
        f.cubicTo(645, 874, 616, 872, 618, 850); f.lineTo(618, 812); f.closeSubpath()
        return p.united(f)

    def blit(self, g, name, dx=0.0, dy=0.0, rot=0.0, sc=1.0, alpha=1.0):
        pm, x, y, w, h = self.spr[name]
        g.save(); g.setOpacity(alpha)
        g.translate(x + w / 2 + dx, y + h / 2 + dy); g.rotate(rot); g.scale(sc, sc)
        g.drawPixmap(QRectF(-w / 2, -h / 2, w, h), pm, QRectF(pm.rect()))
        g.restore()

    def sparkle(self, g, x, y, r, col, t, ph):
        a = .5 + .5 * math.sin(t * 2.4 + ph)
        c = QColor(col); c.setAlpha(int(col.alpha() * (.45 + .55 * a)))
        g.setPen(Qt.NoPen); g.setBrush(c); g.drawPath(star(x, y, r * (.72 + .38 * a)))

    def crack(self, g, sd):
        """愛心上的裂痕（難過時出現）。座標為愛心框所在位置，跟著垂下的愛心一起移動。"""
        pm, x, y, w, h = self.spr["heart"]
        g.save(); g.setOpacity(sd)
        g.translate(x + w / 2, y + h / 2 + 26 * sd); g.rotate(-14 * sd)
        p = QPainterPath(); p.moveTo(-4, -30); p.lineTo(6, -14); p.lineTo(-6, -2); p.lineTo(5, 10); p.lineTo(-2, 22)
        g.setPen(QPen(INK, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); g.setBrush(Qt.NoBrush); g.drawPath(p)
        g.restore()

    def gloom(self, g, t, sd):
        """難過時頭頂兩側的淡藍色「陰影線」，慢慢往下飄。"""
        g.save()
        for i, (bx, by) in enumerate(((258, 250), (282, 236), (306, 252), (660, 236), (684, 250), (708, 238))):
            ph = (t * .35 + i * .21) % 1.0
            a = sd * math.sin(ph * math.pi) * .8
            g.setPen(QPen(C(150, 170, 235, int(255 * a)), 7, Qt.SolidLine, Qt.RoundCap))
            y0 = by + 40 * ph
            g.drawLine(QPointF(bx, y0), QPointF(bx, y0 + 50))
        g.restore()

    def tears(self, g, t, sd):
        """從眼角一顆一顆掉下來的淚滴。"""
        g.save()
        for i, (ex, ey) in enumerate(((396, 492), (590, 482), (402, 488), (584, 486))):
            ph = (t * .55 + i * .5) % 1.0
            x = ex + (-10 if ex < 480 else 10) * ph
            y = ey + 150 * ph * ph
            a = sd * (1 - ph) * min(1.0, ph * 6)
            r = 9 + 3 * (1 - ph)
            p = QPainterPath(); p.moveTo(x, y - r * 1.9)
            p.cubicTo(x + r * .9, y - r * .6, x + r, y + r * .1, x + r, y + r * .3)
            p.arcTo(QRectF(x - r, y - r * .7, 2 * r, 2 * r), 0, -180)
            p.cubicTo(x - r, y + r * .1, x - r * .9, y - r * .6, x, y - r * 1.9)
            g.setPen(QPen(C(60, 90, 170, int(220 * a)), 2.5)); g.setBrush(C(170, 215, 255, int(230 * a))); g.drawPath(p)
            g.setPen(Qt.NoPen); g.setBrush(C(255, 255, 255, int(220 * a))); g.drawEllipse(QPointF(x - r * .35, y - r * .1), r * .28, r * .38)
        g.restore()

    def shock_lines(self, g, t, sk):
        """驚嚇時頭部右側的粉紅色驚嚇線，一閃一閃地伸縮。"""
        g.save()
        for i, ang in enumerate((4, 11)):
            k = abs(math.sin(t * 9 + i * 1.4))
            a = math.radians(ang)
            r0, r1 = 300 + 6 * k, 336 + 14 * k
            p0 = QPointF(480 + r0 * math.cos(a), 470 + r0 * math.sin(a))
            p1 = QPointF(480 + r1 * math.cos(a), 470 + r1 * math.sin(a))
            g.setOpacity(sk * (.6 + .4 * k))
            g.setPen(QPen(INK, 22, Qt.SolidLine, Qt.RoundCap)); g.drawLine(p0, p1)
            g.setPen(QPen(C(255, 150, 190), 13, Qt.SolidLine, Qt.RoundCap)); g.drawLine(p0, p1)
        g.restore()

    def wiggles(self, g, t, ef):
        """害怕時頭旁邊的發抖波浪線：輪流抖動、忽隱忽現。"""
        for i, name in enumerate(("wig1", "wig2", "wig3", "wig4")):
            k = .5 + .5 * math.sin(t * 5 + i * 1.7)
            self.blit(g, name, dx=3 * math.sin(t * 31 + i), dy=-4 * k, rot=8 * math.sin(t * 13 + i * 2),
                      sc=.85 + .2 * k, alpha=ef * (.45 + .55 * k))

    def puff(self, g, ra, er):
        """安心時從嘴巴吐出的一團白煙：冒出來、往左飄、變大後散掉。"""
        p = min(1.0, ra / 2.4)
        if p >= 1.0:
            return
        e = 1 - (1 - p) ** 3
        cx, cy, r = 330 - 140 * e, 478 - 18 * e, 34 * (.35 + .75 * e)
        cloud = QPainterPath()
        for ox, oy, k in ((-.9, .25, .8), (-.25, -.55, .85), (.55, -.2, .75), (.2, .55, .8), (-.5, .55, .7)):
            c = QPainterPath(); c.addEllipse(QPointF(cx + ox * r, cy + oy * r), k * r, k * r)
            cloud = cloud.united(c)
        tail = QPainterPath(); tail.moveTo(cx + .9 * r, cy + .1 * r)
        tail.quadTo(cx + 1.8 * r, cy + .2 * r, cx + 2.6 * r * (1 - .4 * e), cy - .25 * r)
        tail.quadTo(cx + 1.7 * r, cy + .75 * r, cx + .7 * r, cy + .6 * r); tail.closeSubpath()
        cloud = cloud.united(tail)
        g.save(); g.setOpacity(er * min(1.0, p * 8) * (1 - max(0.0, (p - .65) / .35)))
        g.setPen(QPen(INK, 8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); g.setBrush(C(248, 242, 255)); g.drawPath(cloud)
        g.restore()

    def paintEvent(self, _):
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.setRenderHint(QPainter.SmoothPixmapTransform)
        g.scale(self.s * self.F, self.s * self.F)
        t = time.time() - self.t0
        cx, cy = self.CX, self.CY
        body = self.bottle_path()
        # ---- 漂浮裝飾（愛心對話框、星星、驚嘆線）----
        sd, hp = self.sad, 1 - self.sad          # sd: 難過程度, hp: 開心程度
        sk = self.shock * hp                      # sk: 驚嚇程度（哭哭模式優先）
        age = 99.0 if self.shock_t is None else time.time() - self.shock_t   # 嚇到後經過幾秒
        jolt = math.exp(-age * 4.5) * abs(math.sin(age * 13)) * sk          # 剛嚇到時彈跳一下
        shake = sk * (.3 + .7 * math.exp(-age * 1.2)) * math.sin(t * 40)    # 發抖，開頭最明顯
        pop = min(1.0, age / .18) * (1 + .3 * math.exp(-age * 5) * math.cos(age * 18))   # 跳出來的彈性縮放
        er = self.relief * hp * (1 - sk)          # er: 安心程度（驚嚇結束後鬆一口氣）
        ra = age - SHOCK_SEC                      # 開始安心後經過幾秒
        ef = self.fear * hp * (1 - sk) * (1 - er)  # ef: 害怕程度（哭哭、驚嚇、安心時讓位）
        shiver = ef * (.35 + .65 * max(0.0, math.sin(t * 2.1)) ** 6) * math.sin(t * 30)   # 一直微微發抖，一陣一陣抖得更兇
        # 愛心框：開心時輕快漂浮；難過時垂下、歪一邊、變淡，慢慢上下晃
        self.blit(g, "heart", dy=9 * hp * math.sin(t * 2.2) + sd * (26 + 4 * math.sin(t * .9)),
                  rot=-14 * sd, sc=1 + .04 * hp * math.sin(t * 3.1) - .08 * sd, alpha=(1 - .5 * sd) * (1 - sk) * (1 - ef) * (1 - er))
        if er > .01 and "yl1" in self.spr:        # 安心：右側冒出黃色強調線，一閃一閃
            for i, name in enumerate(("yl1", "yl2", "yl3")):
                e = min(1.0, max(0.0, ra - .1 * i) / .25)
                k = abs(math.sin(t * 4 + i * .9))
                self.blit(g, name, sc=e * (1 + .25 * math.exp(-max(0.0, ra) * 4)) * (.92 + .12 * k), alpha=er * e * (.6 + .4 * k))
        if ef > .01 and "bang3" in self.spr:      # 害怕：愛心框換成「!!!」對話框，跟著發抖
            self.blit(g, "bang3", dx=3 * shiver, rot=4 * math.sin(t * 3) + 3 * shiver, sc=1 + .04 * math.sin(t * 4.4), alpha=ef)
            self.wiggles(g, t, ef)
            for i, name in enumerate(("sdrop1", "sdrop2")):   # 冷汗一顆顆往外甩
                ph = (t * .6 + i * .5) % 1.0
                self.blit(g, name, dx=18 * ph, dy=10 * ph * ph, sc=.8 + .25 * math.sin(ph * math.pi),
                          alpha=ef * min(1.0, math.sin(ph * math.pi) * 1.6))
        if sk > .01 and "bang" in self.spr:       # 驚嚇：愛心框換成「!!」對話框，彈出來後左右晃
            self.blit(g, "bang", dy=-10 * jolt, rot=7 * math.sin(t * 9), sc=pop, alpha=sk)
            self.blit(g, "zap", rot=5 * math.sin(t * 7) + 6 * shake, sc=min(1.0, max(0.0, age - .08) / .2) * (1 + .08 * math.sin(t * 11)),
                      alpha=sk * (.75 + .25 * abs(math.sin(t * 8))))
            for i, name in enumerate(("drop1", "drop2")):     # 汗滴依序冒出、往外滑
                e = min(1.0, max(0.0, age - .25 - .15 * i) / .25)
                self.blit(g, name, dx=14 * e + 4 * math.sin(t * 5 + i), dy=-8 * (1 - e) + 5 * math.sin(t * 6 + i * 2),
                          sc=.6 + .4 * e, alpha=sk * e)
            self.shock_lines(g, t, sk)
        if sd > .02:
            self.crack(g, sd)
        # 驚嘆線（興奮的樣子）：難過時淡出
        k = abs(math.sin(t * (3.4 + 5 * sk)))      # 驚嚇時閃得更快、更大
        self.blit(g, "pdash", sc=.9 + (.16 + .2 * sk) * k, alpha=(.55 + .45 * k) * hp * (1 - ef) * (1 - er))
        k = abs(math.sin(t * 3.4 + 1.3))
        self.blit(g, "ydash", sc=.9 + .16 * k, alpha=(.55 + .45 * k) * hp * (1 - sk) * (1 - ef) * (1 - er))   # 驚嚇、害怕、安心時換掉
        # 星星：開心時旋轉彈跳；難過時停下、往下掉、失去光彩
        self.blit(g, "ystar", dy=34 * sd - 30 * jolt, rot=12 * hp * math.sin(t * 1.8) - 24 * sd + 3 * sd * math.sin(t * 1.1) + 10 * shake + 6 * shiver,
                  sc=1 + .1 * hp * math.sin(t * 2.6) - .12 * sd, alpha=1 - .5 * sd)
        self.blit(g, "pstar", dy=40 * sd - 30 * jolt, rot=-12 * hp * math.sin(t * 1.6 + 1) + 28 * sd + 3 * sd * math.sin(t * 1.3) - 10 * shake - 6 * shiver,
                  sc=1 + .1 * hp * math.sin(t * 2.4 + 2) - .12 * sd, alpha=1 - .5 * sd)
        for i, (sx, sy, sr, col) in enumerate(((70, 200, 24, C(255, 255, 255, 200)), (880, 300, 20, C(255, 235, 150, 210)),
                                                (110, 760, 16, C(255, 190, 235, 200)), (870, 800, 18, C(255, 255, 255, 190)))):
            col = QColor(col); col.setAlpha(int(col.alpha() * (1 - .8 * sd)))
            self.sparkle(g, sx, sy, sr, col, t * (1 - .6 * sd), i * 1.7)
        if sd > .02:
            self.gloom(g, t, sd)
        # ---- 光暈 ----
        aura = QRadialGradient(cx, cy, self.RX * 1.2)
        aura.setColorAt(.8, C(170, 110, 255, 60)); aura.setColorAt(1, C(170, 110, 255, 0))
        g.setPen(Qt.NoPen); g.fillRect(QRectF(0, 700, self.IW, self.IH - 700), QBrush(aura))
        # ---- 玻璃瓶身 ----
        g.fillPath(body, grad(0, 830, 0, 1010, (0, C(95, 66, 188)), (1, C(114, 80, 200))))
        lvl = max(0.0, min(100.0, self.disp))
        surf = 1652 - lvl / 100 * 840
        slosh = 1 + 2.2 * sk * math.exp(-age * .5)      # 驚嚇時藥水晃得比較大
        g.save(); g.setClipPath(body)
        for ph, dy, alpha in ((1.7, -14, True), (0.0, 0, False)):
            pts = [(x, surf + dy + slosh * (12 * math.sin(x / 70 + t * 2.2 + ph) + 6 * math.sin(x / 29 - t * 3 + ph)))
                   for x in range(0, 952, 12)]
            liq = QPainterPath(); liq.moveTo(0, 1700)
            for x, y in pts:
                liq.lineTo(x, y)
            liq.lineTo(952, 1700); liq.closeSubpath()
            if alpha:
                g.fillPath(liq, QBrush(C(238, 172, 252, 150)))
            else:
                g.fillPath(liq, grad(0, surf, 0, 1660, (0, C(214, 140, 252)), (.12, C(186, 110, 245)), (.4, C(150, 82, 231)),
                                     (.7, C(112, 54, 204)), (1, C(84, 36, 178))))
        line = QPainterPath(); line.moveTo(*pts[0])
        for x, y in pts[1:]:
            line.lineTo(x, y)
        g.setPen(QPen(C(252, 226, 255, 215), 9, Qt.SolidLine, Qt.RoundCap)); g.setBrush(Qt.NoBrush); g.drawPath(line)
        g.setPen(Qt.NoPen)
        for b in self.bubbles:
            b[1] = (b[1] - b[2] * 0.033) % 1.0
            bx = 250 + b[0] * 440 + 14 * math.sin(t * 2 + b[0] * 9)
            by = 1610 - b[1] * (1610 - surf)
            g.setBrush(C(236, 205, 255, 130))
            if b[3] > .5:
                g.drawPath(star(bx, by, 22 + b[0] * 16))
            else:
                g.drawEllipse(QPointF(bx, by), 10 + b[0] * 14, 10 + b[0] * 14)
        g.restore()
        for i, (sx, sy, sr, col) in enumerate(((692, 975, 38, C(255, 255, 255, 235)), (305, 1050, 28, C(255, 226, 120, 240)),
                                                (818, 1128, 26, C(255, 226, 120, 240)), (711, 1275, 28, C(236, 205, 255, 180)),
                                                (783, 1277, 22, C(236, 205, 255, 170)), (668, 1450, 34, C(226, 190, 255, 180)),
                                                (335, 1548, 38, C(226, 190, 255, 190)))):
            col = QColor(col); col.setAlpha(int(col.alpha() * (1 - .75 * sd)))
            self.sparkle(g, sx, sy, sr, col, t * (1 - .6 * sd), i * 1.3)
        # ---- 玻璃高光與邊框 ----
        g.setPen(QPen(C(255, 255, 255, 205), 26, Qt.SolidLine, Qt.RoundCap))
        g.drawArc(QRectF(cx - 400, cy - 380, 800, 760), 114 * 16, 42 * 16)
        g.setPen(QPen(C(255, 255, 255, 120), 10, Qt.SolidLine, Qt.RoundCap))
        g.drawArc(QRectF(cx - 400, cy - 380, 800, 760), 160 * 16, 20 * 16)
        g.setPen(Qt.NoPen); g.setBrush(C(255, 255, 255, 150)); g.drawEllipse(QPointF(98, 1305), 20, 30)
        g.setBrush(C(172, 150, 236, 200)); g.drawRoundedRect(QRectF(342, 826, 52, 40), 10, 10)
        neckline = QPainterPath(); neckline.moveTo(318, 876); neckline.quadTo(478, 848, 640, 876)
        g.setPen(QPen(C(214, 204, 250, 230), 9, Qt.SolidLine, Qt.RoundCap)); g.setBrush(Qt.NoBrush); g.drawPath(neckline)
        g.save(); g.setClipPath(body)
        g.setPen(QPen(C(240, 196, 253, 235), 28)); g.drawPath(body)
        g.restore()
        g.setPen(QPen(INK, 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); g.drawPath(body)
        # ---- 女巫與瓶蓋（原圖美術，輕微呼吸／搖擺）----
        pm, x, y, w, h = self.spr["main"]
        g.save()
        sob = sd * max(0.0, math.sin(t * 7.0)) ** 8 * (1 if (t % 2.6) < 1.3 else 0)   # 一陣一陣的抽泣
        sigh = er * math.exp(-max(0.0, ra) * 1.2) * math.sin(min(math.pi, max(0.0, ra) * 2.2))   # 呼～地鬆一口氣，肩膀垂下
        g.translate(467, 826 - 46 * jolt + 10 * sigh)
        g.rotate(.8 * hp * math.sin(t * 1.3) + .5 * sd * math.sin(t * .7) + 1.2 * shake + .7 * shiver)
        g.scale(1 + .004 * math.sin(t * 1.9), 1 + (.012 * hp + .006 * sd) * math.sin(t * (2.0 - .9 * sd)) - .02 * sob - .025 * sigh)
        g.translate(-467, -826)
        g.drawPixmap(QRectF(x, y, w, h), pm, QRectF(pm.rect()))
        if sd > .01:
            if "cry" in self.spr:          # 沒有哭臉貼片時（例如沒跑 build_cry.py）只顯示淚滴
                self.blit(g, "cry", alpha=min(1.0, sd * 1.3))
            self.tears(g, t, sd)
        if ef > .01 and "scared" in self.spr:  # 害怕臉貼片
            self.blit(g, "scared", alpha=min(1.0, ef * 1.4))
        if er > .01 and "relief" in self.spr:  # 安心臉貼片
            self.blit(g, "relief", alpha=min(1.0, er * 1.4))
        if sk > .01 and "shock" in self.spr:   # 驚嚇臉貼片（沒跑 build_shock.py 時只有動作，不會當掉）
            self.blit(g, "shock", alpha=min(1.0, sk * 1.4))
        if hp > .01:
            c = C(255, 255, 255, int(235 * hp))
            self.sparkle(g, 764, 106, 30, c, t, .6)
        g.restore()
        if er > .01:
            self.puff(g, ra, er)
        # ---- 文字 ----
        v = self.value()
        txt = "--" if v is None else "%d%%" % round(self.disp)
        f = QFont("Times New Roman"); f.setPixelSize(232); f.setBold(True)
        fill = C(int(255 - 45 * sd), int(252 - 22 * sd), 255)          # 難過時數字偏淡藍
        outlined_text(g, QRectF(cx - 260 + 6 * shake, 1090, 520, 160), txt, f, fill, INK, 30)
        for i, sx in enumerate((212, 752)):
            self.sparkle(g, sx, 1195, 50, C(255, 226, 120, int(255 * (1 - .7 * sd))), t * (1 - .6 * sd), 1 + i * 1.5)
        ls, lw = self.left(self.session), self.left(self.weekly)
        a = "5小時 --" if ls is None else "5小時剩%d%%" % ls
        b = "每週 --" if lw is None else "每週剩%d%%" % lw
        if self.mode == 0:
            sub = a + ("" if lw is None else " · " + b)
        else:
            sub = b + ("" if ls is None else " · " + a)
        f2 = QFont(UI_FONT); f2.setPixelSize(60); f2.setBold(True)
        outlined_text(g, QRectF(cx - 300, 1305, 600, 70), sub, f2, C(248, 238, 255), INK, 17)
        rt = reset_text(self.reset_ts)
        if rt:                                             # 5 小時額度的重置時間
            f4 = QFont(UI_FONT); f4.setPixelSize(46); f4.setBold(True)
            outlined_text(g, QRectF(cx - 300, 1384, 600, 56), rt, f4, C(255, 230, 160), INK, 13)
        if self.pop and time.time() - self.pop[1] < 3.5:
            kk = (time.time() - self.pop[1]) / 3.5
            f3 = QFont("Times New Roman"); f3.setPixelSize(96); f3.setBold(True)
            outlined_text(g, QRectF(560, 900 - 130 * kk, 300, 110), self.pop[0], f3,
                          C(255, 226, 140, int(255 * (1 - kk))), C(28, 8, 92, int(255 * (1 - kk))), 16)

    # ---- 互動 ----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self.drag is not None:
            self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        self.save()

    def mouseDoubleClickEvent(self, e):
        self.toggle()

    def wheelEvent(self, e):
        # 滑鼠滾輪轉一格是 120；Mac 觸控板會連續送出很多小數值，累積滿一格才縮放一次，避免一滑就變超大或超小
        self.wheel_acc = getattr(self, "wheel_acc", 0) + e.angleDelta().y()
        while abs(self.wheel_acc) >= 120:
            step = 1 if self.wheel_acc > 0 else -1
            self.wheel_acc -= 120 * step
            self.set_scale(self.s + 0.08 * step)

    def toggle_autostart(self, on):
        err = mac_set_autostart(on)
        if err:
            mac_activate()
            QMessageBox.warning(self, "Claude 用量小工具", err)

    def toggle(self):
        self.mode = 1 - self.mode; self.save()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        sub = m.addMenu("大小（滾輪也可調整）")
        for name, v in (("小", .5), ("中", .7), ("大", 1.0), ("特大", 1.4)):
            sub.addAction(name, lambda v=v: self.set_scale(v))
        m.addAction("切換 5小時／每週（雙擊）", self.toggle)
        if self.reader:
            m.addAction("立即更新", self.reader.refresh)
            m.addAction("顯示登入網頁", self.reader.show_login)
        m.addAction("開啟變化紀錄", lambda: os.path.exists(LOG) and QDesktopServices.openUrl(QUrl.fromLocalFile(LOG)))
        if IS_MAC and not self.demo:
            a = m.addAction("登入 Mac 時自動開啟")
            a.setCheckable(True)
            a.setChecked(mac_autostart_on())
            a.toggled.connect(self.toggle_autostart)
        m.addAction("離開", QApplication.quit)
        m.exec(e.globalPos())


if __name__ == "__main__":
    install_crash_log()
    app = QApplication(sys.argv)
    if IS_MAC and not getattr(sys, "frozen", False):
        mac_hide_dock_icon()
    ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "witch.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))      # 登入視窗等使用女巫圖示
    demo = "--demo" in sys.argv
    if not demo:
        # 鎖定檔防止「開機自動啟動」和「點捷徑」幾乎同時開出兩個；程式異常結束時鎖會自動失效
        lock = QLockFile(os.path.join(DATA_DIR, "instance.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            notify_running()
            sys.exit(0)                     # 已經在跑了：叫出原本那個就好，不再開第二個
    reader = None if demo else Reader()
    w = Potion(reader, demo)
    if not demo:
        def bring_front():
            while server.hasPendingConnections():
                server.nextPendingConnection().deleteLater()
            w.move(*w.safe_pos(w.x(), w.y()))
            mac_activate()
            w.show(); w.raise_(); w.activateWindow()
        QLocalServer.removeServer(INSTANCE_KEY)
        server = QLocalServer(app)
        server.setSocketOptions(QLocalServer.UserAccessOption)   # 只有自己的使用者帳號能連
        server.listen(INSTANCE_KEY)
        server.newConnection.connect(bring_front)
    if reader:
        app.aboutToQuit.connect(reader.shutdown)
    w.show()
    if IS_MAC and not demo:
        QTimer.singleShot(1500, lambda: mac_first_run_ask(w))
    if demo:
        state = {"s": 70, "w": 35, "hold": 0}
        w.setToolTip("示範模式")
        def step():
            if state["s"] >= 100:
                state["hold"] += 1
                if state["hold"] > 3:
                    state["s"], state["hold"] = 20, 0
            else:
                state["s"] = min(100, state["s"] + random.choice([2, 3, 3, 6]))   # 每次增加都會嚇一跳
            w.on_update(state["s"], state["w"], time.time() + 2 * 3600 + 17 * 60)
        step(); QTimer(w, interval=3500, timeout=step).start()
    sys.exit(app.exec())
