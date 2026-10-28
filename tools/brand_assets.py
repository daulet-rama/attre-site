"""Брендовые картинки: превью ссылки og-{ru,kz,en}.jpg (логотип + слоган на языке),
favicon.png, apple-touch-icon.png. Нужен Pillow. Фото товаров режет build.py при сборке.

Запуск после смены слогана в data/i18n.json: python tools/brand_assets.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / 'src' / 'img' / 'brand'
RED = (204, 0, 0)


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


if __name__ == '__main__':
    brand_assets()
    print('brand ok')
