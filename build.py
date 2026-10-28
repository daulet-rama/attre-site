"""Сборка сайта attré: все темы дизайна в одну папку site/.

    python build.py                                                   # для GitHub Pages
    ATTRE_BASE=/ ATTRE_ORIGIN=http://localhost:8000 python build.py   # локальный просмотр

Фото, шрифт и стили общие и лежат в корне (site/assets/). Каждая тема — свой набор страниц:
корень сайта — тема «Галерея», варианты — в подпапках v1/, v2/, v3/. Список — /variants/.
Данные и правила описаны в core.py и README.md.
"""
import shutil
import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # core и themes лежат рядом
import core  # noqa: E402

# (модуль темы, подпапка, название, по мотивам)
THEMES = [
    ('gallery', '', 'Галерея', 'исходный минималистичный вариант'),
    ('v1', 'v1/', 'Вариант 1', 'по мотивам yourantihero.ru'),
    ('v2', 'v2/', 'Вариант 2', 'по мотивам ushatava.ru'),
    ('v3', 'v3/', 'Вариант 3', 'по мотивам massimodutti.com'),
    ('v4', 'v4/', 'Вариант 4 — «Витрина»', 'Ushatava × Massimo: ритм «крупно + два рядом», фото проявляются'),
    ('v5', 'v5/', 'Вариант 5 — «Лента»', 'Antihero × Instagram: сумка на экран, сетка как профиль'),
    ('v6', 'v6/', 'Вариант 6 — «Музей»', 'экспозиция строчными, асимметрия, мягкое «оседание» фото'),
]


def variants_page(themes):
    rows = ''.join(
        f'<li><a href="{core.ROOT_BASE}{sub}ru/"><b>{core.e(title)}</b><span>{core.e(note)}</span></a></li>'
        for _, sub, title, note in themes)
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>attré — варианты дизайна</title>
<style>
body{{margin:0;font:15px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#111;background:#fff}}
main{{max-width:520px;margin:0 auto;padding:40px 20px}}h1{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-weight:500;margin:0 0 24px}}
ul{{list-style:none;margin:0;padding:0;border-top:1px solid #e5e5e5}}li a{{display:grid;gap:2px;padding:16px 0;border-bottom:1px solid #e5e5e5;color:inherit;text-decoration:none}}
b{{font-weight:500}}span{{color:#6f6f6f;font-size:13px}}p{{color:#6f6f6f;font-size:13px}}
</style></head><body><main><h1>attré — варианты дизайна</h1><ul>{rows}</ul>
<p>Фото, тексты и данные общие для всех вариантов; отличаются вёрстка и поведение. Открывайте с телефона.</p>
</main></body></html>
'''


def main():
    if core.OUT_ROOT.exists():
        shutil.rmtree(core.OUT_ROOT)
    shutil.copytree(core.ROOT / 'src', core.OUT_ROOT / 'assets')
    if not core.DATA['products']:
        raise SystemExit('Нет ни одной опубликованной вещи — сайт не собран')
    core.render_images()
    themes = [th for th in THEMES if (core.ROOT / 'themes' / f'{th[0]}.py').exists()]
    core.set_theme('gallery', '')
    core.write('index.html', core.root_redirect())
    core.write('404.html', core.not_found())
    core.write('robots.txt', 'User-agent: *\nDisallow: /\n' if core.PROTOTYPE else 'User-agent: *\nAllow: /\n')
    core.write('.nojekyll', '')
    core.write('variants/index.html', variants_page(themes))
    products = core.DATA['products']
    total = 0
    for name, sub, title, _ in themes:
        theme = import_module(f'themes.{name}')
        core.set_theme(name, sub)
        # Подкатегории (кардхолдеры, брелоки) знает только тема с NESTED_CATS; остальным — «аксессуары» целиком
        nested = getattr(theme, 'NESTED_CATS', False)
        core.DATA['products'] = products if nested else core.flat_cats(products)
        cats = core.cat_pages() if nested else core.present_cats()
        pages = 0
        for l in core.LANGS:
            lang = l['code']
            core.write(f'{lang}/index.html', theme.home(lang))
            core.write(f'{lang}/catalog/index.html', theme.catalog(lang))
            core.write(f'{lang}/info/index.html', theme.info(lang))
            pages += 3
            for path, page in getattr(theme, 'PAGES', {}).items():   # свои страницы темы: о бренде, избранное
                core.write(f'{lang}/{path}index.html', page(lang)); pages += 1
            for c in cats:
                core.write(f'{lang}/c/{c}/index.html', theme.catalog(lang, c)); pages += 1
            for p in core.DATA['products']:
                core.write(f'{lang}/p/{p["slug"]}/index.html', theme.product(p, lang)); pages += 1
        if sub:
            core.write('index.html', f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={core.ROOT_BASE}{sub}ru/">')
        total += pages
        print(f'{title}: {pages} страниц → {core.ROOT_BASE}{sub}')
    core.DATA['products'] = products
    print(f'site/: {total} страниц, {len(core.DATA["products"])} вещей, адрес {core.ORIGIN}{core.ROOT_BASE}')
    if core.WARNINGS:
        print(f'Предупреждений: {len(core.WARNINGS)} (см. выше)')


if __name__ == '__main__':
    main()
