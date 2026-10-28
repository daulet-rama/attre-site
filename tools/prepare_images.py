"""Готовит картинки для прототипа из data/products.json (нужен Pillow).

Для каждого товара:
  <slug>-1-{450,900}.webp — основной кадр 4:5 (обрезка по точке focus)
  <slug>-2-{450,900}.webp — крупный план фактуры (обрезка по точке detail)
  <slug>-og.jpg          — 1200×1200 для превью ссылки в WhatsApp/Telegram
Плюс бренд: og-{ru,kz,en}.jpg, favicon.png, apple-touch-icon.png.

Исходники качаются с images.unsplash.com в tools/photos-src/ (в git не попадают).
Запуск: python tools/prepare_images.py
"""
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'tools' / 'photos-src'
OUT = ROOT / 'src' / 'img' / 'p'
BRAND = ROOT / 'src' / 'img' / 'brand'
PAD = (243, 242, 239)
RED = (204, 0, 0)


def fetch(p):
    SRC.mkdir(parents=True, exist_ok=True)
    dst = SRC / f"{p['slug']}.jpg"
    if dst.exists():
        return dst
    base = p['photo']['src'].split('?')[0]
    req = urllib.request.Request(f'{base}?fm=jpg&q=85&w=1800', headers={'User-Agent': 'attre-prototype/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        dst.write_bytes(r.read())
    return dst


def crop_45(im, fx, fy, zoom=1.0):
    """Кадр 4:5 вокруг точки (fx, fy) в долях; zoom > 1 — крупнее."""
    w, h = im.size
    cw = min(w, h * 4 / 5) / zoom
    ch = cw * 5 / 4
    left = min(max(fx * w - cw / 2, 0), w - cw)
    top = min(max(fy * h - ch / 2, 0), h - ch)
    return im.crop((round(left), round(top), round(left + cw), round(top + ch)))


def save_pair(im, stem):
    for width in (450, 900):
        im.resize((width, round(width * 5 / 4)), Image.LANCZOS).save(
            OUT / f'{stem}-{width}.webp', 'WEBP', quality=80, method=6)


def og_square(frame, stem):
    canvas = Image.new('RGB', (1200, 1200), PAD)
    fit = frame.resize((960, 1200), Image.LANCZOS)
    canvas.paste(fit, (120, 0))
    canvas.save(OUT / f'{stem}-og.jpg', 'JPEG', quality=84, optimize=True, progressive=True)


def brand_assets():
    font_path = ROOT / 'tools' / 'fonts-src' / 'Onest[wght].ttf'
    logo = Image.open(BRAND / 'logo-black.png').convert('RGBA')

    # Превью ссылки на главную/каталог: логотип и слоган на языке страницы.
    i18n = json.loads((ROOT / 'data' / 'i18n.json').read_text('utf-8'))
    font = ImageFont.truetype(str(font_path), 44)
    font.set_variation_by_axes([500])
    lw = 420
    lg = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    for lang in (l['code'] for l in i18n['langs']):
        og = Image.new('RGB', (1200, 630), (255, 255, 255))
        og.paste(lg, ((1200 - lw) // 2, 170), lg)
        d = ImageDraw.Draw(og)
        a, b = i18n['t']['slogan_1'][lang] + ' ', i18n['t']['slogan_2'][lang]
        wa, wb = d.textlength(a, font=font), d.textlength(b, font=font)
        x = (1200 - wa - wb) / 2
        d.text((x, 400), a, font=font, fill=(17, 17, 17))
        d.text((x + wa, 400), b, font=font, fill=RED)
        og.save(BRAND / f'og-{lang}.jpg', 'JPEG', quality=88, optimize=True)

    # Иконка: белая «a» из логотипа на красном квадрате.
    white = Image.open(BRAND / 'logo-white.png').convert('RGBA')
    a_glyph = white.crop((0, 0, round(white.width * 0.235), white.height))
    a_glyph = a_glyph.crop(a_glyph.getbbox())
    for size, name in ((64, 'favicon.png'), (180, 'apple-touch-icon.png')):
        sq = Image.new('RGBA', (size, size), RED + (255,))
        gh = round(size * 0.56)
        g = a_glyph.resize((round(a_glyph.width * gh / a_glyph.height), gh), Image.LANCZOS)
        sq.paste(g, ((size - g.width) // 2, round(size * 0.24)), g)
        sq.save(BRAND / name, optimize=True)


def main(only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / 'data' / 'products.json').read_text('utf-8'))
    for p in data['products']:
        if only and p['slug'] not in only:
            continue
        im = Image.open(fetch(p)).convert('RGB')
        ph = p['photo']
        fx, fy = ph.get('focus', [0.5, 0.5])
        main_frame = crop_45(im, fx, fy, ph.get('zoom', 1.0))
        save_pair(main_frame, f"{p['slug']}-1")
        dx, dy, dz = ph.get('detail', [fx, fy, 2.4])
        save_pair(crop_45(im, dx, dy, dz), f"{p['slug']}-2")
        og_square(main_frame, p['slug'])
        print('ok', p['slug'])
    brand_assets()
    print('brand ok')


if __name__ == '__main__':
    if sys.argv[1:] == ['--brand']:
        brand_assets()
    else:
        main(set(sys.argv[1:]) or None)
