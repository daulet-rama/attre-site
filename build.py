"""Сборка сайта attré: data/ + media/ + src/ → site/.

Данные:
  data/products/*.json    одна вещь = один файл (имя файла = адрес страницы /p/<имя>/)
  data/categories/*.json  категории; data/materials/*.json — материалы
  data/settings.json      контакты; data/home.json — фото и подписи главной
  data/i18n.json          тексты интерфейса на рус/қаз/eng
  media/products/, media/home/  мастер-копии фото (до 2400px); размеры для сайта режутся здесь
Нужны Python 3.12+ и Pillow. Запуск:
    python build.py                                                   # для GitHub Pages
    ATTRE_BASE=/ ATTRE_ORIGIN=http://localhost:8000 python build.py   # локальный просмотр
Ошибки в данных не роняют сборку: вещь пропускается, причина печатается как «ВНИМАНИЕ».
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'site'
ORIGIN = os.environ.get('ATTRE_ORIGIN', 'https://daulet-rama.github.io').rstrip('/')
BASE = os.environ.get('ATTRE_BASE', '/attre-site/')
PROTOTYPE = True  # noindex + пометка в подвале; снять перед боевым запуском
MEDIA = ROOT / 'media' / 'products'
HOME_MEDIA = ROOT / 'media' / 'home'
NBSP = ' '
WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print('ВНИМАНИЕ:', msg, file=sys.stderr)


def load_dir(name):
    items = []
    for f in sorted((ROOT / 'data' / name).glob('*.json')):
        try:
            d = json.loads(f.read_text('utf-8'))
        except json.JSONDecodeError as ex:
            warn(f'{name}/{f.name}: файл не читается ({ex}) — пропущен')
            continue
        d['_file'] = f.stem
        items.append(d)
    return items


I18N = json.loads((ROOT / 'data' / 'i18n.json').read_text('utf-8'))
LANGS = I18N['langs']
T = I18N['t']
CODES = [l['code'] for l in LANGS]


def tri(v):
    """Поле на трёх языках; пустой казахский или английский берёт русский."""
    v = v if isinstance(v, dict) else {}
    ru = str(v.get('ru') or '').strip()
    return {c: (str(v.get(c) or '').strip() or ru) for c in CODES}


def dict_by_key(items):
    out = {}
    for d in sorted(items, key=lambda d: (d.get('order') or 999, str(d.get('key') or d['_file']))):
        key = str(d.get('key') or d['_file']).strip()
        names = tri(d.get('name'))
        out[key] = {c: names[c] or key for c in CODES}
    return out


CATS = dict_by_key(load_dir('categories'))
MATS = dict_by_key(load_dir('materials'))
SETTINGS = json.loads((ROOT / 'data' / 'settings.json').read_text('utf-8'))
HOME = json.loads((ROOT / 'data' / 'home.json').read_text('utf-8'))


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


def clean_product(d):
    f = d['_file']
    if d.get('published') is False:
        return None
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', f):
        warn(f'products/{f}.json: имя файла должно быть латиницей, цифрами и дефисами — пропущен')
        return None
    name = tri(d.get('name'))
    if not name['ru']:
        warn(f'products/{f}.json: нет названия — пропущен')
        return None
    if d.get('cat') not in CATS:
        warn(f'products/{f}.json: нет категории «{d.get("cat")}» — пропущен')
        return None
    mat = d.get('material') or None
    if mat and mat not in MATS:
        warn(f'products/{f}.json: нет материала «{mat}» — поле скрыто')
        mat = None
    srcs = []
    for x in d.get('images') or []:
        x = x.get('image') if isinstance(x, dict) else x
        if not x:
            continue
        path = MEDIA / Path(str(x)).name
        if path.exists():
            srcs.append(path)
        else:
            warn(f'products/{f}.json: нет файла фото {x}')
    if not srcs:
        warn(f'products/{f}.json: нет ни одного фото — пропущен')
        return None
    size = d.get('size') if isinstance(d.get('size'), dict) else {}
    dims = [num(size.get(k)) for k in ('w', 'h', 'd')]
    strap = tri(d.get('strap'))
    price_v = num(d.get('price'))
    stock = num(d.get('stock'))
    return {
        'slug': f, 'id': str(d.get('id') or f), 'order': num(d.get('order')) or 9999,
        'cat': d['cat'], 'material': mat,
        'name': name, 'type': tri(d.get('type')), 'color': tri(d.get('color')), 'desc': tri(d.get('desc')),
        'strap': strap if strap['ru'] else None,
        'size': [f'{v:g}' for v in dims] if all(dims) else None,
        'price': int(price_v) if price_v else None,          # нет цены — «цена по запросу»
        'stock': int(stock) if stock is not None else None,  # нет остатка — просто «в наличии»
        'srcs': srcs, 'focus': d.get('focus') or {},
    }


PRODUCTS = sorted(filter(None, (clean_product(d) for d in load_dir('products'))), key=lambda p: (p['order'], p['id']))
DATA = {'products': PRODUCTS, **SETTINGS}


def e(s):
    return html.escape(str(s), quote=True)


def t(key, lang, **kw):
    s = T[key][lang]
    for k, v in kw.items():
        s = s.replace('{' + k + '}', str(v))
    return s


def url(path=''):
    return BASE + path


def abs_url(path=''):
    return ORIGIN + BASE + path


def money(n, lang):
    s = f'{n:,}' if lang == 'en' else f'{n:,}'.replace(',', NBSP)
    return s + NBSP + '₸'


def price_text(p, lang):
    return money(p['price'], lang) if p['price'] else t('price_request', lang)


def wa_link(text):
    return f"https://wa.me/{DATA['whatsapp']}?text={quote(text)}"


def asset_version(*paths):
    h = hashlib.sha1()
    for p in paths:
        h.update((ROOT / p).read_bytes())
    return h.hexdigest()[:8]


VER = asset_version('src/css/site.css', 'src/js/site.js')

# Значок WhatsApp — Simple Icons (CC0), https://simpleicons.org/?q=whatsapp
WA_ICON = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
           '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg>')
ARROW_LEFT = ('<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" aria-hidden="true">'
              '<path d="M7.5 2L3.5 6l4 4"/></svg>')
CROSS = ('<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" aria-hidden="true">'
         '<path d="M1 1l12 12M13 1L1 13"/></svg>')


def sold(p):
    return p['stock'] == 0


def meta_line(p, lang):
    return ' · '.join(x for x in (p['type'][lang], p['color'][lang]) if x)


def item_url(p, lang):
    return url(f"{lang}/p/{p['slug']}/")


def img_srcset(stem):
    return f"{url(f'assets/img/p/{stem}-600.webp')} 600w, {url(f'assets/img/p/{stem}-1200.webp')} 1200w"


# ——— Картинки: режутся из мастер-копий при каждой сборке, сжатие один раз ———

def fit_34(im, focus):
    """Кадр 3:4. Фото на однотонном студийном фоне не обрезаем, а продлеваем фон краёв,
    чтобы вещь осталась целиком; остальные кадры обрезаем по точке фокуса."""
    from PIL import Image, ImageFilter, ImageStat
    w, h = im.size
    target = 3 / 4
    strip = max(4, round(min(w, h) * 0.02))
    edges = [im.crop((0, 0, w, strip)), im.crop((0, h - strip, w, h)), im.crop((0, 0, strip, h)), im.crop((w - strip, 0, w, h))]
    uniform = all(max(ImageStat.Stat(x).stddev) < 9 for x in edges)
    if uniform and abs(w / h - target) > 0.01:
        if w / h > target:   # шире — добавляем фон сверху и снизу
            nh = round(w / target)
            top = (nh - h) // 2
            out = Image.new('RGB', (w, nh))
            if top > 0:
                out.paste(im.crop((0, 0, w, 2)).resize((w, top)).filter(ImageFilter.GaussianBlur(6)), (0, 0))
            if nh - h - top > 0:
                out.paste(im.crop((0, h - 2, w, h)).resize((w, nh - h - top)).filter(ImageFilter.GaussianBlur(6)), (0, top + h))
            out.paste(im, (0, top))
            return out
        nw = round(h * target)   # уже — добавляем фон слева и справа
        left = (nw - w) // 2
        out = Image.new('RGB', (nw, h))
        if left > 0:
            out.paste(im.crop((0, 0, 2, h)).resize((left, h)).filter(ImageFilter.GaussianBlur(6)), (0, 0))
        if nw - w - left > 0:
            out.paste(im.crop((w - 2, 0, w, h)).resize((nw - w - left, h)).filter(ImageFilter.GaussianBlur(6)), (left + w, 0))
        out.paste(im, (left, 0))
        return out
    fx, fy = float(focus.get('x', .5)), float(focus.get('y', .45))
    cw = min(w, h * target)
    ch = cw / target
    left = min(max(fx * w - cw / 2, 0), w - cw)
    top = min(max(fy * h - ch / 2, 0), h - ch)
    return im.crop((round(left), round(top), round(left + cw), round(top + ch)))


def open_rgb(path):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert('RGB')


def render_images():
    from PIL import Image
    out = OUT / 'assets' / 'img' / 'p'
    out.mkdir(parents=True, exist_ok=True)
    for p in DATA['products']:
        shots = []
        for i, src in enumerate(p['srcs']):
            frame = fit_34(open_rgb(src), p['focus'] if i == 0 else {})
            stem = f"{p['slug']}-{i + 1}"
            for width in (600, 1200):
                frame.resize((width, round(width * 4 / 3)), Image.LANCZOS).save(
                    out / f'{stem}-{width}.webp', 'WEBP', quality=86, method=6)
            shots.append(stem)
            if i == 0:
                og = frame.resize((900, 1200), Image.LANCZOS)
                sq = Image.new('RGB', (1200, 1200), og.getpixel((2, 2)))
                sq.paste(og, (150, 0))
                sq.save(out / f"{p['slug']}-og.jpg", 'JPEG', quality=88, optimize=True, progressive=True)
        p['images'] = shots

    hout = OUT / 'assets' / 'img' / 'home'
    hout.mkdir(parents=True, exist_ok=True)
    for item in [HOME['cover'], *HOME['banners']]:
        src = HOME_MEDIA / item['image']
        im = open_rgb(src)
        w, h = im.size
        ratio = item.get('ratio', 2 / 3)
        fx, fy = item.get('focus', [0.5, 0.4])
        cw = min(w, h * ratio)
        ch = cw / ratio
        left = min(max(fx * w - cw / 2, 0), w - cw)
        top = min(max(fy * h - ch / 2, 0), h - ch)
        frame = im.crop((round(left), round(top), round(left + cw), round(top + ch)))
        stem = Path(item['image']).stem
        for width in (750, 1125, 1600):
            if width <= frame.width * 1.02:
                frame.resize((width, round(width / ratio)), Image.LANCZOS).save(
                    hout / f'{stem}-{width}.webp', 'WEBP', quality=86, method=6)
        item['_stem'] = stem
        item['_widths'] = [w_ for w_ in (750, 1125, 1600) if (hout / f'{stem}-{w_}.webp').exists()]
        item['_ratio'] = ratio


def home_srcset(item):
    return ', '.join(f"{url(f'assets/img/home/{item['_stem']}-{w}.webp')} {w}w" for w in item['_widths'])


# ——— Каркас страницы ———

def lang_row(lang, suffix):
    return '<div class="lang-row">' + ''.join(
        f'<a href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a>'
        for l in LANGS) + '</div>'


def present_cats():
    return [c for c in CATS if any(p['cat'] == c for p in DATA['products'])]


def menu(lang, suffix):
    info = url(f'{lang}/info/')
    cats = ''.join(f'<li><a href="{url(f"{lang}/c/{c}/")}">{e(CATS[c][lang])}</a></li>' for c in present_cats())
    return f'''<div class="menu" id="menu" data-menu role="dialog" aria-modal="true" aria-label="{e(t('menu', lang))}">
<div class="menu__top"><button class="menu__close" type="button" data-menu-close>{CROSS}<span>{e(t('close', lang))}</span></button></div>
<nav aria-label="{e(t('nav_cats', lang))}">
<ul class="menu__list">
<li><a href="{url(lang + '/catalog/')}">{e(t('all_items', lang))}</a></li>
{cats}
</ul>
<ul class="menu__list menu__list--small">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>
</nav>
{lang_row(lang, suffix)}
<div class="menu__foot">
<a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">+7{NBSP}706{NBSP}723{NBSP}23{NBSP}49</span></a>
<a href="https://www.instagram.com/{DATA['instagram']}/" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a>
</div>
</div>'''


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', body_class='', after=''):
    lang_cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    wa = e(wa_link(t('wa_general', lang)))
    return f'''<!doctype html>
<html lang="{lang_cfg['html']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#ffffff">
{robots}
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(abs_url(lang + '/' + suffix))}">
{alternates}
<meta property="og:site_name" content="attré">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(abs_url(lang + '/' + suffix))}">
<meta property="og:image" content="{e(og_image)}">
<meta property="og:locale" content="{lang_cfg['og']}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{url('assets/img/brand/favicon.png')}" type="image/png">
<link rel="apple-touch-icon" href="{url('assets/img/brand/apple-touch-icon.png')}">
<link rel="preload" href="{url('assets/fonts/onest-var.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{url('assets/css/site.css')}?v={VER}">
<script>(function(d){{d.classList.add('js');setTimeout(function(){{if(!window.__site)d.classList.remove('js')}},6000)}})(document.documentElement)</script>
</head>
<body class="{body_class}">
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<header class="hdr">
<button class="hdr__btn" type="button" aria-controls="menu" aria-expanded="false" data-menu-open><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
<a class="hdr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{url('assets/img/brand/logo-black.png')}" alt="attré" width="49" height="19"></a>
<a class="hdr__btn" href="{wa}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</header>
{menu(lang, suffix)}
<main id="main">
{body}
</main>
{footer(lang, suffix)}
{after}
<script src="{url('assets/js/site.js')}?v={VER}" defer onerror="document.documentElement.classList.remove('js')"></script>
</body>
</html>
'''


def footer(lang, suffix):
    info = url(f'{lang}/info/')
    cats = ''.join(f'<li><a href="{url(f"{lang}/c/{c}/")}">{e(CATS[c][lang])}</a></li>' for c in present_cats())
    proto = f'<p>{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<div class="ftr__cols">
<div><h2>{e(t('dock_catalog', lang))}</h2><ul><li><a href="{url(lang + '/catalog/')}">{e(t('all_items', lang))}</a></li>{cats}</ul></div>
<div><h2>{e(t('f_buyers', lang))}</h2><ul>
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul></div>
<div><h2>{e(t('f_contacts', lang))}</h2><ul>
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">+7{NBSP}706{NBSP}723{NBSP}23{NBSP}49</span></a></li>
<li><a href="https://www.instagram.com/{DATA['instagram']}/" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
</ul></div>
</div>
{lang_row(lang, suffix)}
<div class="ftr__brand">
<img src="{url('assets/img/brand/logo-black.png')}" alt="attré" width="46" height="18" loading="lazy">
<p class="ftr__slogan">{e(t('slogan_1', lang))} <span>{e(t('slogan_2', lang))}</span></p>
</div>
<div class="ftr__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
{proto}
</div>
</footer>'''


# ——— Каталог ———

def card(p, lang, eager=False, h='h2'):
    name = p['name'][lang]
    stem = p['images'][0]
    loading = 'eager" fetchpriority="high' if eager else 'lazy'
    tag = (f'<span class="tag">{e(t("sold", lang))}</span>' if sold(p)
           else f'<span class="tag tag--last">{e(t("last", lang))}</span>' if p['stock'] == 1 else '')
    meta = meta_line(p, lang)
    return f'''<li class="card{' card--sold' if sold(p) else ''}"><a href="{item_url(p, lang)}">
<div class="card__media"><img class="fade" src="{url(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw" width="600" height="800" alt="" loading="{loading}" decoding="async"></div>
<div class="card__body">
<{h} class="card__name">{e(name)}</{h}>
{f'<p class="card__meta">{e(meta)}</p>' if meta else ''}
<p class="card__price num">{e(price_text(p, lang))}</p>
{tag}
</div>
</a></li>'''


def ordered(items):
    # Проданные в конце, но не удаляются: старые ссылки из Instagram и WhatsApp живут
    return sorted(items, key=lambda p: sold(p))


def catalog_page(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    tabs = [(None, t('all', lang), url(lang + '/catalog/'))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/')) for c in present_cats()]
    tabs_html = ''.join(
        f'<a class="tab" href="{href}"{" aria-current=\"page\"" if c == cat else ""}>{e(label)}</a>'
        for c, label, href in tabs)
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    body = f'''<div class="cat-head"><h1 class="cat-title">{e(heading)}</h1></div>
<nav class="tabs" aria-label="{e(t('nav_cats', lang))}"><div class="tabs__scroll">{tabs_html}</div></nav>
<ul class="grid">
{''.join(card(p, lang, eager=i < 4) for i, p in enumerate(items))}
</ul>
{'' if items else f'<p class="page">{e(t("empty", lang))}</p>'}'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_url(f'assets/img/brand/og-{lang}.jpg'))


# ——— Товар ———

def similar(p):
    others = [q for q in DATA['products'] if q['slug'] != p['slug'] and not sold(q)]
    others.sort(key=lambda q: (q['cat'] != p['cat'], q['order']))
    return others[:4]


def product_page(p, lang):
    name = p['name'][lang]
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    n = len(p['images'])
    slides = ''.join(
        f'<div class="gallery__slide"><img class="fade" src="{url(f"assets/img/p/{stem}-1200.webp")}" srcset="{img_srcset(stem)}" '
        f'sizes="(min-width: 960px) 30vw, 100vw" width="1200" height="1600" '
        f'alt="{e(name)}{" — " + e(t("photo_n", lang, i=i + 1, n=n)) if i else ""}" '
        f'loading="{"eager" if i == 0 else "lazy"}"{" fetchpriority=\"high\"" if i == 0 else ""} decoding="async"></div>'
        for i, stem in enumerate(p['images']))
    todo = f'<em class="todo">{e(t("todo", lang))}</em>'
    size = (f'<span class="num">{e(t("p_size_fmt", lang, w=p["size"][0], h=p["size"][1], d=p["size"][2]))}</span>'
            if p['size'] else todo)
    rows = [
        (t('p_type', lang), e(p['type'][lang]) if p['type'][lang] else todo),
        (t('p_color', lang), e(p['color'][lang]) if p['color'][lang] else todo),
        (t('p_material', lang), e(MATS[p['material']][lang]) if p['material'] else todo),
        (t('p_size', lang), size),
        (t('p_strap', lang), e(p['strap'][lang]) if p['strap'] else todo),
        (t('p_maker', lang), todo),
        (t('p_origin', lang), todo),
    ]
    spec = ''.join(f'<div><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in rows)
    if sold(p):
        msg = t('wa_sold', lang, name=name, id=p['id'], url=page_url)
        label = t('wa_btn_sold', lang)
        status = f'<p class="pdp__status"><span class="tag">{e(t("sold", lang))}</span></p>'
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        label = t('wa_btn', lang)
        status = f'<p class="pdp__status"><span class="tag tag--last">{e(t("last", lang))}</span></p>' if p['stock'] == 1 else ''
    btn = f'<a class="btn btn--wide" href="{e(wa_link(msg))}" target="_blank" rel="noopener"{{cta}}>{WA_ICON}{e(label)}</a>'
    meta = meta_line(p, lang)
    cat_name = CATS[p['cat']][lang]
    desc = f'<p class="pdp__desc">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    body = f'''<nav class="crumb"><a href="{url(f"{lang}/c/{p['cat']}/")}">{ARROW_LEFT}{e(cat_name)}</a></nav>
<div class="pdp-wrap">
<div class="gallery" data-gallery>
<div class="gallery__track">{slides}</div>
<span class="gallery__count" aria-hidden="true">1 / {n}</span>
</div>
<div class="pdp">
<h1 class="pdp__name">{e(name)}</h1>
{f'<p class="pdp__meta">{e(meta)}</p>' if meta else ''}
<p class="pdp__price num">{e(price_text(p, lang))}</p>
{status}
{btn.replace('{cta}', ' data-cta')}
<p class="pdp__bonus"><a class="link" href="{url(lang + '/info/')}#bonus">{e(t('bonus_short', lang))}</a> — {e(t('bonus_hint', lang))}</p>
{desc}
<div class="accs">
<details class="acc"><summary>{e(t('acc_details', lang))}</summary><div class="acc__body"><dl class="spec">{spec}</dl></div></details>
<details class="acc"><summary>{e(t('f_delivery', lang))}</summary><div class="acc__body"><p>{e(t('delivery_body', lang))}</p><p>{e(t('payment_body', lang))}</p></div></details>
<details class="acc"><summary>{e(t('acc_returns', lang))}</summary><div class="acc__body"><p>{e(t('returns_body', lang))}</p></div></details>
<details class="acc"><summary>{e(t('acc_store', lang))}</summary><div class="acc__body"><p>{e(t('store_body', lang))}</p><p>{e(t('hours', lang))}</p></div></details>
</div>
</div>
</div>
<section aria-labelledby="sim-t">
<h2 class="sec-title" id="sim-t">{e(t('similar', lang))}</h2>
<ul class="grid">{''.join(card(q, lang, h='h3') for q in similar(p))}</ul>
</section>'''
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_url(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product',
                  after=f'<div class="buybar">{btn.replace("{cta}", "")}</div>')


# ——— Главная ———

def home_page(lang):
    cover = HOME['cover']
    cat_url = url(lang + '/catalog/')
    cover_html = f'''<a class="cover" href="{cat_url}">
<img src="{url(f"assets/img/home/{cover['_stem']}-1125.webp")}" srcset="{home_srcset(cover)}" sizes="100vw" width="1125" height="{round(1125 / cover['_ratio'])}" alt="{e(tri(cover.get('alt'))[lang])}" fetchpriority="high" decoding="async">
<span class="cap-wrap"><span class="cap cap--slogan">{e(t('slogan_1', lang))} {e(t('slogan_2', lang))}</span><span class="cap cap--link">{e(t('cta_catalog', lang))}</span></span>
</a>'''
    banners = ''.join(
        f'''<a class="banner" href="{url(lang + '/' + b['link'])}">
<img class="fade" src="{url(f"assets/img/home/{b['_stem']}-750.webp")}" srcset="{home_srcset(b)}" sizes="(min-width: 960px) 33vw, (min-width: 600px) 50vw, 100vw" width="750" height="{round(750 / b['_ratio'])}" alt="{e(tri(b.get('alt'))[lang])}" loading="lazy" decoding="async">
<span class="cap-wrap"><span class="cap">{e(tri(b['label'])[lang])}</span><span class="cap cap--link">{e(t('cta_look', lang))}</span></span>
</a>''' for b in HOME['banners'])
    featured = [p for slug in HOME.get('featured', []) for p in DATA['products'] if p['slug'] == slug]
    featured = (featured or [p for p in DATA['products'] if not sold(p)])[:6]
    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
{cover_html}
<section aria-labelledby="new-t">
<h2 class="sec-title" id="new-t">{e(t('instock_title', lang))}</h2>
<ul class="grid">{''.join(card(p, lang, h='h3') for p in featured)}</ul>
<a class="more-link" href="{cat_url}">{e(t('all_catalog', lang))}</a>
</section>
<div class="banners">{banners}</div>
<section class="store" aria-labelledby="store-t">
<h2 id="store-t">{e(t('store_title', lang))}</h2>
<p>{e(t('address', lang))}</p>
{'' if '[' in t('hours', lang) else f'<p>{e(t("hours", lang))}</p>'}
<p>{e(t('delivery_world', lang))}</p>
<a class="link" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a>
</section>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_url(f'assets/img/brand/og-{lang}.jpg'), body_class='home')


# ——— Покупателям ———

def info_page(lang):
    body = f'''<div class="page">
<h1>{e(t('info_title', lang))}</h1>
<h2 id="bonus">{e(t('bonus_title', lang))}</h2>
<p>{e(t('bonus_body', lang))}</p>
<p class="note">{e(t('bonus_terms', lang))}</p>
<h2 id="about">{e(t('about_title', lang))}</h2>
<p>{e(t('about_body', lang))}</p>
<h2 id="delivery">{e(t('delivery_title', lang))}</h2>
<p>{e(t('delivery_body', lang))}</p>
<p>{e(t('payment_body', lang))}</p>
<h2 id="returns">{e(t('returns_title', lang))}</h2>
<p>{e(t('returns_body', lang))}</p>
<h2 id="contacts">{e(t('contacts_title', lang))}</h2>
<p>{e(t('address', lang))}<br>{e(t('hours', lang))}</p>
<p><a class="link" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">{e(t('wa_label', lang))}</a></p>
<h2 id="seller">{e(t('seller_title', lang))}</h2>
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_url(f'assets/img/brand/og-{lang}.jpg'))


def root_redirect():
    target = url(I18N['default'] + '/')
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>attré</title>
<script>
(function () {{
  var ls = navigator.languages || [navigator.language || ''];
  var map = {{ru: 'ru', kk: 'kz', en: 'en'}};
  var t = 'ru';
  for (var i = 0; i < ls.length; i++) {{
    var c = map[String(ls[i]).toLowerCase().slice(0, 2)];
    if (c) {{ t = c; break; }}
  }}
  location.replace('{BASE}' + t + '/' + location.search + location.hash);
}})();
</script>
<noscript><meta http-equiv="refresh" content="0; url={target}"></noscript>
</head>
<body><p><a href="{BASE}ru/">Русский</a> · <a href="{BASE}kz/">Қазақша</a> · <a href="{BASE}en/">English</a></p></body>
</html>
'''


def not_found():
    rows = ''.join(
        f'<p lang="{l["html"]}">{e(t("nf_title", l["code"]))} <a class="link" href="{BASE}{l["code"]}/">{e(t("nf_link", l["code"]))}</a></p>'
        for l in LANGS)
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>404 — attré</title>
<link rel="stylesheet" href="{BASE}assets/css/site.css?v={VER}">
</head>
<body>
<main class="nf">
<img src="{BASE}assets/img/brand/logo-black.png" alt="attré" width="62" height="24" style="margin:0 auto 32px">
<h1>404</h1>
{rows}
</main>
</body>
</html>
'''


def write(path, text):
    f = OUT / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, 'utf-8')


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / 'src', OUT / 'assets')
    if not DATA['products']:
        raise SystemExit('Нет ни одной опубликованной вещи — сайт не собран')
    render_images()
    write('index.html', root_redirect())
    write('404.html', not_found())
    write('robots.txt', 'User-agent: *\nDisallow: /\n' if PROTOTYPE else 'User-agent: *\nAllow: /\n')
    write('.nojekyll', '')
    pages = 3
    for l in LANGS:
        lang = l['code']
        write(f'{lang}/index.html', home_page(lang))
        write(f'{lang}/catalog/index.html', catalog_page(lang))
        write(f'{lang}/info/index.html', info_page(lang))
        pages += 3
        for c in present_cats():
            write(f'{lang}/c/{c}/index.html', catalog_page(lang, c)); pages += 1
        for p in DATA['products']:
            write(f'{lang}/p/{p["slug"]}/index.html', product_page(p, lang)); pages += 1
    print(f'site/: {pages} страниц, {len(DATA["products"])} вещей, база {BASE}, адрес {ORIGIN}')
    if WARNINGS:
        print(f'Предупреждений: {len(WARNINGS)} (см. выше)')


if __name__ == '__main__':
    main()
