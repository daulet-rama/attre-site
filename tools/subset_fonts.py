"""Собирает облегчённый woff2 из Onest[wght].ttf: латиница, кириллица (вкл. казахские
буквы), ₸, типографские знаки. Переменная ось wght сохраняется — один файл на все веса.

Запуск (нужны fonttools и brotli):
    python tools/subset_fonts.py
"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'tools' / 'fonts-src' / 'Onest[wght].ttf'
OUT = ROOT / 'src' / 'fonts' / 'onest-var.woff2'

UNICODES = [
    *range(0x0020, 0x007F),   # Basic Latin
    *range(0x00A0, 0x0100),   # Latin-1 (é в «attré», ×, «», nbsp)
    *range(0x0400, 0x0500),   # Кириллица, в т.ч. Ә Ғ Қ Ң Ө Ұ Ү Һ І
    *range(0x2010, 0x2028),   # тире, кавычки, многоточие
    *range(0x2030, 0x203B),
    0x20AC, 0x20B8, 0x2116,   # € ₸ №
    *range(0x2190, 0x2194), 0x2197, 0x2212,  # стрелки, минус
]

# Казахские буквы и ₸ обязаны остаться — проверяем после сборки.
MUST_HAVE = 'ӘәҒғҚқҢңӨөҰұҮүҺһІі₸№«»—'


def main():
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = ['kern', 'liga', 'calt', 'ccmp', 'locl', 'case', 'tnum', 'pnum']
    opts.name_IDs = ['*']
    opts.notdef_outline = True
    font = TTFont(SRC)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=UNICODES)
    sub.subset(font)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    font.flavor = 'woff2'
    font.save(OUT)

    check = TTFont(OUT).getBestCmap()
    missing = [c for c in MUST_HAVE if ord(c) not in check]
    if missing:
        raise SystemExit(f'В шрифте нет символов: {missing}')
    print(f'{OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024} КБ, {len(check)} символов, проверка пройдена')


if __name__ == '__main__':
    main()
