"""從哭哭女巫圖切出「哭臉」貼片，輸出 cry_asset.json（給 inject.py 一起嵌入）。
用法: python build_cry.py   (需要 pillow numpy scipy)
對位參數（縮放 1.635、x 位移 +1）由比對兩張圖的帽子與瓶蓋算出。
"""
import base64, io, json, os
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, 'reference', 'witch_bottle_reference.png')
CRY = os.path.join(HERE, 'reference', 'witch_cry_reference.png')
S, DX = 1.635, 1
BOX = (318, 300, 652, 600)              # 貼片範圍（參考圖座標）
CX, CY, RX, RY, FEATHER = 485, 448, 158, 138, 30
ref = Image.open(REF).convert('RGBA'); R = np.asarray(ref, float)
cry = Image.open(CRY).convert('RGB')
up = cry.resize((round(cry.width * S), round(cry.height * S)), Image.LANCZOS)
up = up.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
U = np.asarray(up, float)
x0, y0, x1, y1 = BOX
P = U[y0:y1, x0 + DX:x1 + DX].copy()
Q = R[y0:y1, x0:x1, :3]
yy, xx = np.mgrid[y0:y1, x0:x1]
dist = np.sqrt(((xx - CX) / RX) ** 2 + ((yy - CY) / RY) ** 2)
# 顏色校正：用貼片外圈（兩張圖沒改的地方）做逐色版線性擬合
ring = (dist > .85) & (dist < 1.25) & (R[y0:y1, x0:x1, 3] > 250)
for c in range(3):
    k, b = np.polyfit(P[..., c][ring], Q[..., c][ring], 1)
    P[..., c] = np.clip(P[..., c] * k + b, 0, 255)
alpha = np.clip((1.0 - dist) * (max(RX, RY) / FEATHER) + 0.5, 0, 1)
alpha = ndi.gaussian_filter(alpha, 2) * (R[y0:y1, x0:x1, 3] / 255.0)
out = np.dstack([P, alpha * 255]).astype(np.uint8)
im = Image.fromarray(out, 'RGBA')
im = im.resize((round(im.width * .65), round(im.height * .65)), Image.LANCZOS)   # 原圖解析度本來就較低，縮小不損畫質
buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
asset = {'cry': [base64.b64encode(buf.getvalue()).decode(), x0, y0, x1 - x0, y1 - y0]}
json.dump(asset, open(os.path.join(HERE, 'cry_asset.json'), 'w'))
print('cry patch', BOX, len(buf.getvalue()) // 1024, 'KB')
