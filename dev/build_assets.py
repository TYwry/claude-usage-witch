"""從參考圖切出 sprite，輸出 assets.json（給 inject.py 嵌入 usage_widget.py）。
用法: python build_assets.py   (需要 pillow numpy scipy)
"""
import base64, io, json, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'reference', 'witch_bottle_reference.png')
S = 0.65   # sprite 內嵌時的縮小比例（畫面上仍以原尺寸繪製）
a = np.array(Image.open(SRC).convert('RGBA'))
al = a[..., 3]
lab, n = ndi.label(al > 30, structure=np.ones((3, 3)))
H, W = al.shape
yy, xx = np.mgrid[0:H, 0:W]
region = np.zeros((H, W), bool); region[:827, :] = True            # 女巫+瓶蓋+金環（y<827）
region |= (((xx - 640) ** 2 + (yy - 800) ** 2) <= 57 ** 2) & (yy <= 862)  # 星星徽章
def piece(ids, extra=None, it=2, pad=4):
    m = ndi.binary_dilation(np.isin(lab, ids), iterations=it) & (al > 0) & np.isin(lab, [0] + list(ids))
    if extra is not None: m &= extra
    ys, xs = np.where(m); x0, x1, y0, y1 = xs.min() - pad, xs.max() + pad + 1, ys.min() - pad, ys.max() + pad + 1
    sub = a.copy(); sub[~m] = 0
    im = Image.fromarray(sub[y0:y1, x0:x1], 'RGBA').convert('RGBa')
    im = im.resize((max(1, round((x1 - x0) * S)), max(1, round((y1 - y0) * S))), Image.LANCZOS).convert('RGBA')
    buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
    return (base64.b64encode(buf.getvalue()).decode(), int(x0), int(y0), int(x1 - x0), int(y1 - y0))
# 連通元件編號依參考圖而定: 1=主體 2=愛心框 3,6=黃驚嘆線 4,5=粉驚嘆線 7=黃星 8=粉星
parts = {'main': ([1], region), 'heart': ([2], None), 'pdash': ([4, 5], None),
         'ydash': ([3, 6], None), 'ystar': ([7], None), 'pstar': ([8], None)}
assets = {k: piece(ids, ex, it=1 if k == 'main' else 2) for k, (ids, ex) in parts.items()}
json.dump(assets, open(os.path.join(HERE, 'assets.json'), 'w'))
print({k: v[1:] for k, v in assets.items()})
