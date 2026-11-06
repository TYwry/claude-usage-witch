"""從驚嚇、害怕、安心三張女巫圖切出臉部貼片與裝飾，輸出 shock_asset.json（給 inject.py 一起嵌入）。
用法: python build_shock.py   (需要 pillow numpy scipy)
這幾張圖的角色比一般圖大一點、位置也有偏移：對位參數（縮放 S、位移 DX, DY，以 (470, 450) 為中心）
由比對瀏海與帽子算出。背景是畫出來的灰白格子（不是透明），裝飾用「從圖邊連通的淡色區域」去背。
"""
import base64, io, json, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, 'reference', 'witch_bottle_reference.png')
OX, OY = 470, 450
BOX = (322, 340, 652, 616)                          # 臉部貼片範圍（參考圖座標）
CX, CY, RX, RY, FEATHER = 487, 478, 158, 132, 22
SMALL = 0.65                                        # 內嵌時縮小比例（畫面上仍以原尺寸繪製）
# 每張圖: 檔名, 臉部貼片名稱, (S, DX, DY), 裝飾 {名稱: (元件內一點, 只取這個範圍 x0,y0,x1,y1 或 None)}（座標為該圖像素）
SOURCES = [
    ('witch_shock_reference.png', 'shock', (1.02, -11.5, 7.5),
     {'zap': ((250, 230), None), 'bang': ((150, 410), None),
      'drop1': ((815, 395), None), 'drop2': ((825, 450), None)}),
    ('witch_scared_reference.png', 'scared', (1.02, -2.5, 7.5),
     {'bang3': ((165, 370), (60, 280, 242, 442)),     # !!! 對話框黏著帽緣，用範圍切開
      'wig1': ((736, 300), None), 'wig2': ((779, 340), None), 'wig3': ((204, 488), None), 'wig4': ((778, 510), None),
      'sdrop1': ((830, 405), None), 'sdrop2': ((840, 463), None)}),
    ('witch_relieved_reference.png', 'relief', (0.9725, -15, -4),      # 吐氣的白煙跟頭髮重疊切不乾淨，改在程式裡畫
     {'yl1': ((772, 340), None), 'yl2': ((805, 390), None), 'yl3': ((802, 457), None)}),
]
ref = np.asarray(Image.open(REF).convert('RGBA'), float)


def png(arr):
    im = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    im = im.resize((max(1, round(im.width * SMALL)), max(1, round(im.height * SMALL))), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


assets = {}
for fname, face, (S, DX, DY), picks in SOURCES:
    sh = np.asarray(Image.open(os.path.join(HERE, 'reference', fname)).convert('RGB'), float)
    # ---- 臉部貼片：對位到參考圖座標，用羽化橢圓蓋上去 ----
    x0, y0, x1, y1 = BOX
    yy, xx = np.mgrid[y0:y1, x0:x1]
    P = np.dstack([ndi.map_coordinates(sh[..., c], [OY + (yy - OY) * S + DY, OX + (xx - OX) * S + DX], order=3)
                   for c in range(3)])
    Q = ref[y0:y1, x0:x1]
    dist = np.sqrt(((xx - CX) / RX) ** 2 + ((yy - CY) / RY) ** 2)
    ring = (dist > .85) & (dist < 1.25) & (Q[..., 3] > 250)     # 兩張圖都沒改的外圈，用來校正顏色
    for c in range(3):
        k, b = np.polyfit(P[..., c][ring], Q[..., c][ring], 1)
        P[..., c] = np.clip(P[..., c] * k + b, 0, 255)
    alpha = np.clip((1.0 - dist) * (max(RX, RY) / FEATHER) + 0.5, 0, 1)
    alpha = ndi.gaussian_filter(alpha, 2) * (Q[..., 3] / 255.0)
    assets[face] = [png(np.dstack([P, alpha * 255])), x0, y0, x1 - x0, y1 - y0]
    # ---- 裝飾：去掉格子背景後，依位置挑出各個元件 ----
    mx, mn = sh.max(2), sh.min(2)
    lab, _ = ndi.label((mn > 200) & (mx - mn < 30))
    edge = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    fg = ndi.binary_opening(~np.isin(lab, list(edge)), iterations=1)
    fl, _ = ndi.label(fg, structure=np.ones((3, 3)))
    for name, ((px, py), box) in picks.items():
        win = fl[py - 12:py + 13, px - 12:px + 13]       # 細線不一定剛好點中：取附近最近的元件
        ys, xs = np.nonzero(win)
        assert len(ys), name
        k = np.argmin((ys - 12) ** 2 + (xs - 12) ** 2)
        i = win[ys[k], xs[k]]
        m = fl == i
        if box:
            lim = np.zeros_like(m); lim[box[1]:box[3], box[0]:box[2]] = True; m &= lim
        ys, xs = np.where(m)
        X0, X1, Y0, Y1 = xs.min() - 3, xs.max() + 4, ys.min() - 3, ys.max() + 4
        a = ndi.gaussian_filter(ndi.binary_dilation(m, iterations=1).astype(float), .8)[Y0:Y1, X0:X1]
        arr = np.dstack([sh[Y0:Y1, X0:X1], a * 255])
        w, h = (X1 - X0) / S, (Y1 - Y0) / S                    # 換回參考圖座標
        rx, ry = OX + (X0 - DX - OX) / S, OY + (Y0 - DY - OY) / S
        assets[name] = [png(arr), round(rx), round(ry), round(w), round(h)]
json.dump(assets, open(os.path.join(HERE, 'shock_asset.json'), 'w'))
print({k: v[1:] for k, v in assets.items()})
