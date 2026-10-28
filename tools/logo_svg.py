"""Векторный логотип attré: обводка исходника заказчицы (tools/brand-src/logo-original.png, 2000×2000)
через potrace. Поля — как у logo-black.png, чтобы логотип в шапке не сдвинулся.

    pip install potracer numpy pillow
    python tools/logo_svg.py tools/brand-src/logo-original.png src/img/brand/logo-black.png src/img/brand/logo-black.svg

Проверка: перекрытие с исходником 99 %, расхождения — 1–2 px по краю на слове шириной 1600 px."""
import sys

import numpy as np
import potrace
from PIL import Image, ImageOps

src, png, out = sys.argv[1:4]
im = Image.open(src).convert('L')
x0, y0, x1, y1 = ImageOps.invert(im).getbbox()          # слово в исходнике
# поля как у текущего logo-black.png (доля от высоты/ширины слова)
p = Image.open(png).convert('RGBA')
a = p.split()[-1]
px0, py0, px1, py1 = a.point(lambda v: 255 if v > 127 else 0).getbbox()
pw, ph = px1 - px0, py1 - py0
sx = (x1 - x0) / pw
pad = (px0 * sx, py0 * sx, (p.width - px1) * sx, (p.height - py1) * sx)
print('png', p.size, 'ink', (px0, py0, px1, py1), 'pad in src px', [round(v, 1) for v in pad])

bm = potrace.Bitmap(np.array(im))   # potracer: оттенки 0–255, тёмное — заливка
plist = bm.trace(turdsize=4, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.0,
                 opticurve=True, opttolerance=0.2)
ox, oy = x0 - pad[0], y0 - pad[1]
W, H = (x1 - x0) + pad[0] + pad[2], (y1 - y0) + pad[1] + pad[3]
k = 300 / W                                              # viewBox шириной 300 — короткие числа


def f(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return s if s != '-0' else '0'


def pt(q):
    return f'{f((q.x - ox) * k)} {f((q.y - oy) * k)}'


d = []
for curve in plist:
    d.append('M' + pt(curve.start_point))
    for seg in curve:
        if seg.is_corner:
            d.append('L' + pt(seg.c) + 'L' + pt(seg.end_point))
        else:
            d.append('C' + pt(seg.c1) + ' ' + pt(seg.c2) + ' ' + pt(seg.end_point))
    d.append('Z')
vb = f'0 0 300 {f(H * k)}'
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" fill="#111">'
       f'<path fill-rule="evenodd" d="{"".join(d)}"/></svg>\n')
open(out, 'w').write(svg)
print('curves', len(plist), 'viewBox', vb, 'bytes', len(svg))
