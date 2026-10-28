"""Картинки для главной: вертикальный герой 1:2, крупные планы материалов 1:2,
крупный логотип для героя и шторки. Нужен Pillow; исходники фото — tools/photos-src/
(их скачивает prepare_images.py), исходник логотипа — путь в аргументе.

Запуск: python tools/prepare_home.py /path/to/logo-2000.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'tools' / 'photos-src'
OUT = ROOT / 'src' / 'img' / 'home'
BRAND = ROOT / 'src' / 'img' / 'brand'

# имя → (исходник, центр x, центр y, увеличение)
FRAMES = {
    'hero':       ('bucket-black', 0.50, 0.50, 1.00),
    'mat-leather': ('woven-tote-cognac', 0.45, 0.60, 1.90),
    'mat-suede':   ('suede-shoulder-red', 0.47, 0.50, 1.25),
    'mat-textile': ('drawstring-bag-olive', 0.52, 0.60, 2.10),
}
WIDTHS = {'hero': (480, 828, 1170), 'default': (480, 828)}


def crop_tall(im, fx, fy, zoom):
    w, h = im.size
    cw = min(w, h / 2) / zoom
    ch = cw * 2
    left = min(max(fx * w - cw / 2, 0), w - cw)
    top = min(max(fy * h - ch / 2, 0), h - ch)
    return im.crop((round(left), round(top), round(left + cw), round(top + ch)))


def frames():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (slug, fx, fy, zoom) in FRAMES.items():
        im = Image.open(SRC / f'{slug}.jpg').convert('RGB')
        frame = crop_tall(im, fx, fy, zoom)
        for width in WIDTHS.get(name, WIDTHS['default']):
            out = frame.resize((width, width * 2), Image.LANCZOS)
            out.save(OUT / f'{name}-{width}.webp', 'WEBP', quality=72 if name == 'hero' else 70, method=6)
        print(name, frame.size)


def logos(src):
    """Большой логотип (ширина 1200) в трёх цветах на прозрачном фоне."""
    alpha = ImageOps.invert(Image.open(src).convert('L'))
    alpha = alpha.crop(alpha.point(lambda v: 255 if v > 8 else 0).getbbox())
    width = 1200
    alpha = alpha.resize((width, round(alpha.height * width / alpha.width)), Image.LANCZOS)
    for name, rgb in (('black', (17, 17, 17)), ('white', (255, 255, 255)), ('red', (204, 0, 0))):
        im = Image.new('RGBA', alpha.size, rgb + (0,))
        solid = Image.new('RGBA', alpha.size, rgb + (255,))
        solid.putalpha(alpha)
        im.paste(solid, (0, 0))
        im.save(BRAND / f'logo-{name}-xl.png', optimize=True)
    print('logo xl', alpha.size)


if __name__ == '__main__':
    frames()
    if len(sys.argv) > 1:
        logos(sys.argv[1])
