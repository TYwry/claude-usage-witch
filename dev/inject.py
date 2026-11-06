"""把 assets.json（與 cry_asset.json、shock_asset.json）嵌入 template.py，產生 ../usage_widget.py。先跑 build_assets.py、build_cry.py、build_shock.py。"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
assets = json.load(open(os.path.join(HERE, 'assets.json')))
for extra in ('cry_asset.json', 'shock_asset.json'):    # 哭臉（build_cry.py）、驚嚇臉與裝飾（build_shock.py）
    extra = os.path.join(HERE, extra)
    if os.path.exists(extra):
        assets.update(json.load(open(extra)))
src = open(os.path.join(HERE, 'template.py'), encoding='utf-8').read()
marker = "ASSETS = {}  # __ASSETS__"
assert marker in src
body = "ASSETS = {\n" + "".join('    %r: (%r, %d, %d, %d, %d),\n' % (k, v[0], v[1], v[2], v[3], v[4]) for k, v in assets.items()) + "}\n"
open(os.path.join(HERE, '..', 'usage_widget.py'), 'w', encoding='utf-8').write(src.replace(marker, body))
print('written ../usage_widget.py')
