"""Старый адрес сайта на GitHub Pages → только переадресации на новый (attre.pages.dev).

python3 tools/redirect_site.py site redirect https://attre.pages.dev/ /attre-site/
Для каждой страницы готовой сборки site/ (…/index.html) пишет в redirect/ страницу-переадресацию на тот же путь
нового сайта (с ?query и #hash; без JS — meta refresh). 404.html переводит любой другой старый адрес на тот же путь
нового сайта по адресу из строки браузера (базу /attre-site/ отрезает).
"""
import html
import json
import sys
from pathlib import Path

SRC, OUT, NEW = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].rstrip('/') + '/'
BASE = sys.argv[4] if len(sys.argv) > 4 else '/attre-site/'


def page(url, script):
    u = html.escape(url, quote=True)
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>attré</title>'
            f'<meta name="robots" content="noindex"><link rel="canonical" href="{u}">'
            f'<meta http-equiv="refresh" content="0; url={u}"><script>{script}</script></head>'
            f'<body><a href="{u}">{html.escape(NEW)}</a></body></html>\n')


n = 0
for f in sorted(SRC.rglob('index.html')):
    rel = f.parent.relative_to(SRC).as_posix()
    url = NEW + ('' if rel == '.' else rel + '/')
    dst = OUT / f.relative_to(SRC)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(page(url, f'location.replace({json.dumps(url)} + location.search + location.hash)'), 'utf-8')
    n += 1
OUT.mkdir(parents=True, exist_ok=True)
(OUT / '404.html').write_text(page(NEW, f'var p = location.pathname, b = {json.dumps(BASE)};'
                                      f' if (p.indexOf(b) === 0) p = p.slice(b.length); else p = p.replace(/^\\//, "");'
                                      f' location.replace({json.dumps(NEW)} + p + location.search + location.hash)'), 'utf-8')
print(f'{OUT}/: {n} страниц-переадресаций и 404.html → {NEW}')
