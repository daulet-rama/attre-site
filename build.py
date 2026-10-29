"""Сборка сайта attré: data/ + media/ + src/ → site/. Тема одна — «Витрина» (themes/v4.py), страницы в корне сайта.

    python build.py                                                      # для GitHub Pages (так собирает CI)
    ATTRE_BASE=/ ATTRE_ORIGIN=https://attre.pages.dev python build.py    # для Cloudflare Pages
    ATTRE_BASE=/ ATTRE_ORIGIN=http://localhost:8000 python build.py      # локальный просмотр

Страницы — /ru/, /kz/, /en/, корень сайта выбирает язык; фото, шрифт, стили и скрипты — site/assets/,
индекс поиска — site/assets/search/<язык>.json.
Старые адреса не ломаются: «Витрина» жила в /v4/, другие варианты дизайна — в /v1/…/v6/ (их список — /variants/).
По каждому такому адресу лежит страница-переадресация на тот же путь в корне (?параметры и #якорь сохраняются).
Сборка в корень домена (ATTRE_BASE=/, Cloudflare Pages) пишет ещё _redirects — те же переадресации ответом
сервера 301 — и _headers (сроки кэша). Данные и правила описаны в core.py и README.md.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # core и themes лежат рядом
import core  # noqa: E402
from themes import v4 as theme  # noqa: E402

# Подпапки прежних тем: их адреса ведут на тот же путь в корне (заказчицы пользуются ссылками …/v4/ru/…)
OLD = ['v4/', 'v1/', 'v2/', 'v3/', 'v5/', 'v6/']

# Сроки кэша на Cloudflare Pages: https://developers.cloudflare.com/pages/configuration/headers/
# HTML здесь нет: Pages отдаёт его с «public, max-age=0, must-revalidate» — правки из админки видны сразу.
# Правило «/*» с Cache-Control не добавлять: значения всех совпавших правил склеиваются через запятую.
HEADERS = '''# Сроки кэша на Cloudflare Pages. Файл пишет build.py — правьте там.

# Стили и скрипты — всегда с ?v=<хеш> в адресе (asset_version в themes/v4.py); шрифт менять под новым именем.
# Индекс поиска — тоже с ?v=<хеш содержимого> (search_index в themes/v4.py): на другой странице не перезапрашивается
/assets/css/*
  Cache-Control: public, max-age=31536000, immutable
/assets/js/*
  Cache-Control: public, max-age=31536000, immutable
/assets/fonts/*
  Cache-Control: public, max-age=31536000, immutable
/assets/search/*
  Cache-Control: public, max-age=31536000, immutable

# Фото и видео — имена без хеша (фото можно заменить под тем же именем): 10 минут без запросов к серверу,
# потом сутки браузер сразу показывает сохранённое и в фоне сверяет с сервером (ETag → 304).
# Видео отдаёт функция functions/assets/video/[[path]].js: к её ответам _headers не применяется, срок она ставит
# сама (CACHE в функции, менять вместе); эта строка — для файла, который функция берёт через env.ASSETS
/assets/img/*
  Cache-Control: public, max-age=600, stale-while-revalidate=86400
/assets/video/*
  Cache-Control: public, max-age=600, stale-while-revalidate=86400

# Превью-адреса выкладок (https://<хеш>.attre.pages.dev) — не для поисковиков
https://:version.:project.pages.dev/*
  X-Robots-Tag: noindex
'''


def redirects():
    """Cloudflare Pages: старые адреса → тот же путь в корне ответом 301. Правила _redirects срабатывают раньше
    файлов, страницы-переадресации там не нужны (они — для GitHub Pages).
    Первая часть пути — :lang (непустая, без «/»), а не весь путь через «*»: из /v4//evil.com правило «/:splat»
    сделало бы //evil.com, и сайт уводил бы на чужой адрес. Остальное под /vN/ (сама /v4/, //…) — в корень.
    Синтаксис: https://developers.cloudflare.com/pages/configuration/redirects/"""
    rows = ['/variants/* / 301']
    for sub in OLD:
        rows += [f'/{sub}:lang/* /:lang/:splat 301', f'/{sub}:lang /:lang/ 301', f'/{sub}* / 301']
    return '# Старые адреса → тот же путь в корне сайта. Файл пишет build.py — правьте там.\n' + '\n'.join(rows) + '\n'


def moved(path):
    """Страница-переадресация по старому адресу на path (путь от корня сайта: 'ru/p/altea/' или '' — выбор языка).
    Скрипт сохраняет ?параметры (цвет товара ?c=, фильтр каталога) и #якорь; без JS — meta refresh."""
    to = core.ROOT_BASE + path
    lang = next((l['html'] for l in core.LANGS if path.startswith(l['code'] + '/')), 'ru')
    js = json.dumps(to).replace('</', '<\\/')
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>attré</title>
<link rel="canonical" href="{core.e(core.ORIGIN + to)}">
<script>location.replace({js} + location.search + location.hash)</script>
<noscript><meta http-equiv="refresh" content="0; url={core.e(to)}"></noscript>
</head>
<body><p><a href="{core.e(to)}">attré</a></p></body>
</html>
'''


def pages():
    """Страницы темы на одном языке: (путь от корня языка, функция lang → html)."""
    out = [('', theme.home), ('catalog/', theme.catalog), ('info/', theme.info), *theme.PAGES.items()]
    out += [(f'c/{c}/', lambda lang, c=c: theme.catalog(lang, c)) for c in core.cat_pages()]
    out += [(f'p/{p["slug"]}/', lambda lang, p=p: theme.product(p, lang)) for p in core.DATA['products']]
    return out


def main():
    if core.OUT_ROOT.exists():
        shutil.rmtree(core.OUT_ROOT)
    shutil.copytree(core.ROOT / 'src', core.OUT_ROOT / 'assets')
    if not core.DATA['products']:
        raise SystemExit('Нет ни одной опубликованной вещи — сайт не собран')
    core.render_images()
    core.set_theme('v4', '')
    core.write('index.html', core.root_redirect())
    core.write('404.html', core.not_found(f"{core.asset('assets/css/' + theme.CSS)}?v={theme.VER}"))
    core.write('robots.txt', 'User-agent: *\nDisallow: /\n' if core.PROTOTYPE else 'User-agent: *\nAllow: /\n')
    core.write('.nojekyll', '')
    # Индекс поиска — маленький JSON на язык (v4.js грузит его при первом открытии поиска). До страниц:
    # в их разметке — адрес индекса с хешем содержимого
    for l in core.LANGS:
        core.write(f'assets/search/{l["code"]}.json', theme.search_index(l['code']))
    paths = []
    for l in core.LANGS:
        for path, page in pages():
            core.write(f'{l["code"]}/{path}index.html', page(l['code']))
            paths.append(f'{l["code"]}/{path}')
    # Старые адреса: подпапка темы и /variants/ → корень (выбор языка), страницы → тот же путь в корне
    core.write('variants/index.html', moved(''))
    for sub in OLD:
        core.write(f'{sub}index.html', moved(''))
        for path in paths:
            core.write(f'{sub}{path}index.html', moved(path))
    if core.ROOT_BASE == '/':   # файлы Cloudflare Pages: правила в них — от корня домена
        core.write('_headers', HEADERS)
        core.write('_redirects', redirects())
    print(f'«Витрина»: {len(paths)} страниц → {core.ROOT_BASE}; '
          f'переадресаций со старых адресов: {len(OLD) * (len(paths) + 1) + 1}')
    print(f'site/: {len(core.DATA["products"])} вещей, адрес {core.ORIGIN}{core.ROOT_BASE}')
    if core.WARNINGS:
        print(f'Предупреждений: {len(core.WARNINGS)} (см. выше)')


if __name__ == '__main__':
    main()
