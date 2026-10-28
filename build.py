"""Сборка статического прототипа attré: data/*.json + src/ → site/.

Только стандартная библиотека Python. Запуск:
    python build.py                                   # для GitHub Pages (адрес по умолчанию)
    ATTRE_BASE=/ ATTRE_ORIGIN=http://localhost:8000 python build.py   # локальный просмотр
"""
import hashlib
import html
import json
import os
import shutil
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'site'
ORIGIN = os.environ.get('ATTRE_ORIGIN', 'https://daulet-rama.github.io').rstrip('/')
BASE = os.environ.get('ATTRE_BASE', '/attre-site/')
PROTOTYPE = True  # noindex + пометка в подвале; снять перед боевым запуском

I18N = json.loads((ROOT / 'data' / 'i18n.json').read_text('utf-8'))
DATA = json.loads((ROOT / 'data' / 'products.json').read_text('utf-8'))
for _p in DATA['products']:
    # Кадры готовит tools/prepare_images.py: основной и крупный план фактуры.
    _p.setdefault('images', [f"{_p['slug']}-1", f"{_p['slug']}-2"])
LANGS = I18N['langs']
T = I18N['t']
CATS = I18N['categories']
MATS = I18N['materials']
NBSP = ' '


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


def price(n, lang='ru'):
    s = f'{n:,}' if lang == 'en' else f'{n:,}'.replace(',', NBSP)
    return s + NBSP + '₸'


def wa_link(text):
    return f"https://wa.me/{DATA['whatsapp']}?text={quote(text)}"


def asset_version(*paths):
    h = hashlib.sha1()
    for p in paths:
        h.update((ROOT / p).read_bytes())
    return h.hexdigest()[:8]


VER = asset_version('src/css/site.css', 'src/js/site.js')
HVER = asset_version('src/css/home.css', 'src/js/home.js')

# Значок WhatsApp — Simple Icons (CC0), https://simpleicons.org/?q=whatsapp
WA_ICON = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
           '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg>')
ARROW_LEFT = ('<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" '
              'stroke-width="1.5" aria-hidden="true"><path d="M10 3L5 8l5 5"/></svg>')


def item_name(p, lang):
    return p['name'][lang]


def item_url(p, lang):
    return url(f"{lang}/p/{p['slug']}/")


def img_srcset(name):
    return (f"{url('assets/img/p/' + name + '-450.webp')} 450w, "
            f"{url('assets/img/p/' + name + '-900.webp')} 900w")


def sold(p):
    return p['stock'] <= 0


# ——— Общий каркас страницы ———

def lang_nav(lang, suffix):
    links = ''.join(
        f'<a href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a>'
        for l in LANGS)
    return f'<nav class="lang" aria-label="{e(t("nav_lang", lang))}">{links}</nav>'


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', body_class='', extra_head='',
           header=True, extra_js=''):
    lang_cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">'
        for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    header_html = f'''<header class="hdr">
<a class="hdr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{url('assets/img/brand/logo-black.png')}" alt="attré" width="52" height="20"></a>
{lang_nav(lang, suffix)}
<a class="icon-btn" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</header>''' if header else ''
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
{extra_head}
</head>
<body class="{body_class}">
<div class="wrap">
{header_html}
{body}
{footer(lang)}
</div>
<script src="{url('assets/js/site.js')}?v={VER}" defer></script>
{extra_js}
</body>
</html>
'''


def footer(lang):
    info = url(f'{lang}/info/')
    return f'''<footer class="ftr">
<div class="ftr__brand">
<a class="ftr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{url('assets/img/brand/logo-red.png')}" alt="attré" width="93" height="36" loading="lazy"></a>
<p class="ftr__slogan" lang="en">not mass. <span>not repeated.</span></p>
</div>
<div>
<h2>{e(t('f_contacts', lang))}</h2>
<ul>
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">+7{NBSP}706{NBSP}723{NBSP}23{NBSP}49</span></a></li>
<li><a href="https://www.instagram.com/{DATA['instagram']}/" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
</ul>
</div>
<div>
<h2>{e(t('f_buyers', lang))}</h2>
<ul>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
<li><a href="{info}#credits">{e(t('f_credits', lang))}</a></li>
</ul>
</div>
<div class="ftr__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
</div>
{f'<p class="ftr__proto">{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''}
</footer>'''


# ——— Каталог ———

def card(p, lang, eager=False, h='h3'):
    name = item_name(p, lang)
    img = p['images'][0]
    loading = 'eager" fetchpriority="high' if eager else 'lazy'
    badge = f'<span class="badge">{e(t("sold", lang))}</span>' if sold(p) else ''
    last = f'<span class="last">{e(t("last", lang))}</span>' if p['stock'] == 1 else ''
    return f'''<li class="card" data-card{' data-sold' if sold(p) else ''}>
<a class="card__link" href="{item_url(p, lang)}">
<div class="card__media"><img src="{url('assets/img/p/' + img + '-450.webp')}" srcset="{img_srcset(img)}" sizes="(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw" width="450" height="563" alt="" loading="{loading}" decoding="async">{badge}</div>
<div class="card__body">
<{h} class="card__name">{e(name)}</{h}>
<p class="card__mat">{e(MATS[p['material']][lang])} · {e(p['color'][lang])}</p>
<p class="card__price"><span class="num">{price(p['price'], lang)}</span>{last}</p>
</div>
</a>
</li>'''


def ordered(items):
    # В наличии сначала, проданные в конце — проданные не удаляем, чтобы старые ссылки жили.
    return sorted(items, key=lambda p: sold(p))


def catalog_page(lang, cat=None):
    present = [c for c in CATS if any(p['cat'] == c for p in DATA['products'])]
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    tabs = [(None, t('all', lang), url(lang + '/catalog/'))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/')) for c in present]
    tabs_html = ''.join(
        f'<a class="tab" href="{href}" data-keep-instock{" aria-current=\"page\"" if c == cat else ""}>{e(label)}</a>'
        for c, label, href in tabs)
    cards = '\n'.join(card(p, lang, eager=i < 4, h='h2') for i, p in enumerate(items))
    heading = CATS[cat][lang] if cat else t('site_title', lang)
    suffix = f'c/{cat}/' if cat else 'catalog/'
    body = f'''<main id="main">
<h1 class="sr-only">{e(heading)}</h1>
<section class="intro">
<p class="intro__slogan" lang="en">not mass. <span>not repeated.</span></p>
<p class="intro__sub">{e(t('intro_sub', lang))}</p>
</section>
<div class="tabs">
<nav class="tabs__scroll" aria-label="{e(t('nav_cats', lang))}">{tabs_html}</nav>
<button class="stock-toggle" type="button" aria-pressed="false" data-stock-toggle><span class="stock-toggle__box" aria-hidden="true"></span>{e(t('in_stock', lang))}</button>
</div>
<p class="sr-only" role="status" data-count data-template="{e(t('count', lang))}"></p>
<ul class="grid grid--catalog">
{cards}
</ul>
{'' if items else f'<p class="empty">{e(t("empty", lang))}</p>'}
<section class="store">
<h2>{e(t('store_title', lang))}</h2>
<p>{e(t('address', lang))}</p>
<p>{e(t('hours', lang))}</p>
<a class="link" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a>
</section>
</main>'''
    title = f"{CATS[cat][lang]} — attré" if cat else f"{t('dock_catalog', lang)} — attré"
    return layout(lang, title=title, desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_url('assets/img/brand/og.jpg'))


# ——— Товар ———

def similar(p):
    others = [q for q in DATA['products'] if q['slug'] != p['slug']]
    others.sort(key=lambda q: (q['cat'] != p['cat'], sold(q), q['material'] != p['material']))
    return others[:4]


def product_page(p, lang):
    name = item_name(p, lang)
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    n = len(p['images'])
    slides = ''.join(
        f'<div class="gallery__slide"><img src="{url("assets/img/p/" + im + "-900.webp")}" srcset="{img_srcset(im)}" '
        f'sizes="(min-width: 960px) 30vw, 100vw" width="900" height="1125" '
        f'alt="{e(name)}{" — " + e(t("detail", lang)) if i else ""}" '
        f'loading="{"eager" if i == 0 else "lazy"}"{" fetchpriority=\"high\"" if i == 0 else ""} decoding="async"></div>'
        for i, im in enumerate(p['images']))
    if sold(p):
        status = f'<span class="dot dot--off" aria-hidden="true"></span><span>{e(t("sold", lang))}</span>'
    elif p['stock'] == 1:
        status = f'<span class="dot dot--red" aria-hidden="true"></span><span>{e(t("status_last", lang))}</span>'
    else:
        status = f'<span class="dot" aria-hidden="true"></span><span>{e(t("status_stock", lang))}</span>'
    todo = f'<em class="todo">{e(t("todo", lang))}</em>'
    size = (f'<span class="num">{e(t("p_size_fmt", lang, w=p["size"][0], h=p["size"][1], d=p["size"][2]))}</span>'
            if p.get('size') else todo)
    strap = e(p['strap'][lang]) if p.get('strap') else todo
    rows = [
        (t('p_material', lang), e(MATS[p['material']][lang])),
        (t('p_color', lang), e(p['color'][lang])),
        (t('p_size', lang), size),
        (t('p_strap', lang), strap),
        (t('p_maker', lang), todo),
        (t('p_origin', lang), todo),
    ]
    passport = ''.join(f'<div><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in rows)
    if sold(p):
        msg = t('wa_sold', lang, name=name, id=p['id'], url=page_url)
        bar = (f'<div class="buybar__info"><p class="buybar__sold">{e(t("sold_word", lang))} <span lang="en">not repeated.</span></p></div>'
               f'<a class="btn btn--ghost" href="{e(wa_link(msg))}" target="_blank" rel="noopener">{WA_ICON}{e(t("wa_btn_sold", lang))}</a>')
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price(p['price'], lang), url=page_url)
        bar = (f'<div class="buybar__info"><p class="buybar__name">{e(name)}</p><p class="buybar__price num">{price(p["price"], lang)}</p></div>'
               f'<a class="btn" href="{e(wa_link(msg))}" target="_blank" rel="noopener">{WA_ICON}{e(t("wa_btn", lang))}</a>')
    sold_line = (f'<p class="pdp__status pdp__sold">{e(t("sold_word", lang))} <span lang="en">not repeated.</span></p>'
                 if sold(p) else '')
    cat_name = CATS[p['cat']][lang]
    sim = '\n'.join(card(q, lang) for q in similar(p))
    body = f'''<main id="main">
<nav class="crumb"><a href="{url(f"{lang}/c/{p['cat']}/")}">{ARROW_LEFT}{e(t('back', lang, cat=cat_name))}</a></nav>
<div class="pdp-wrap">
<div class="gallery" data-gallery>
<div class="gallery__track">{slides}</div>
<span class="gallery__count" aria-hidden="true">1 / {n}</span>
</div>
<div class="pdp">
<h1 class="pdp__name">{e(name)}</h1>
<p class="pdp__price num">{price(p['price'], lang)}</p>
{sold_line or f'<p class="pdp__status">{status}</p>'}
<p class="pdp__desc">{e(p['desc'][lang])}</p>
<dl class="passport">{passport}</dl>
<details class="acc"><summary>{e(t('acc_delivery', lang))}</summary><div class="acc__body"><p>{e(t('delivery_body', lang))}</p></div></details>
<details class="acc"><summary>{e(t('acc_returns', lang))}</summary><div class="acc__body"><p>{e(t('returns_body', lang))}</p></div></details>
<details class="acc"><summary>{e(t('acc_store', lang))}</summary><div class="acc__body"><p>{e(t('store_body', lang))}</p><p>{e(t('hours', lang))}</p></div></details>
<div class="buybar">{bar}</div>
</div>
</div>
<section class="similar">
<h2 class="section-title">{e(t('similar', lang))}</h2>
<ul class="grid">
{sim}
</ul>
</section>
</main>'''
    desc = f"{MATS[p['material']][lang]} · {p['color'][lang]} · {price(p['price'], lang)}"
    return layout(lang, title=f'{name} — attré', desc=desc, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_url(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product', body_class='has-buybar')


# ——— Главная ———

BAG_SYMBOL = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
              '<symbol id="bag" viewBox="0 0 40 48">'
              '<path d="M13.5 17v-4a6.5 6.5 0 0 1 13 0v4" fill="none" stroke="currentColor" stroke-width="2.4"/>'
              '<path d="M6 17h28l3 29H3z" fill="currentColor"/></symbol></svg>')
HOME_MATS = [('leather', 'mat-leather', 'mat_leather_line'),
             ('suede', 'mat-suede', 'mat_suede_line'),
             ('textile', 'mat-textile', 'mat_textile_line')]
STORY_ITEM = 'suede-shoulder-red'


def home_img(name, widths, sizes, alt, extra=''):
    srcset = ', '.join(f"{url(f'assets/img/home/{name}-{w}.webp')} {w}w" for w in widths)
    return (f'<img src="{url(f"assets/img/home/{name}-828.webp")}" srcset="{srcset}" sizes="{sizes}" '
            f'width="828" height="1656" alt="{e(alt)}" decoding="async"{extra}>')


def home_page(lang):
    wa = e(wa_link(t('wa_general', lang)))
    cat = url(f'{lang}/catalog/')
    logo = url('assets/img/brand/logo-red-xl.png')  # один файл: в герое красный, на шторке — белый фильтром
    story_p = next(p for p in DATA['products'] if p['slug'] == STORY_ITEM)
    # Волна от центра: задержка растёт с расстоянием до центральной клетки 5×5
    sils = ''.join(
        f'<svg class="sil" viewBox="0 0 40 48" style="--d:{round(((i // 5 - 2) ** 2 + (i % 5 - 2) ** 2) ** .5 * 2)}" '
        f'aria-hidden="true"><use href="#bag"/></svg>' for i in range(25))
    mats = ''.join(
        f'<article class="mat">{home_img(img, (480, 828), "(min-width: 960px) 33vw, 100vw", "", " loading=\"lazy\"")}'
        f'<div class="mat__body"><p class="mat__n">0{i + 1} / 0{len(HOME_MATS)}</p>'
        f'<h2 class="mat__name">{e(MATS[m][lang])}</h2><p class="mat__line">{e(t(line, lang))}</p></div></article>'
        for i, (m, img, line) in enumerate(HOME_MATS))
    items = [p for p in DATA['products'] if not sold(p)][:6]
    edit = ''.join(
        f'<li class="edit__item"><a href="{item_url(p, lang)}"><div class="edit__media">'
        f'<img src="{url("assets/img/p/" + p["images"][0] + "-450.webp")}" srcset="{img_srcset(p["images"][0])}" '
        f'sizes="(min-width: 960px) 23vw, 68vw" width="450" height="563" alt="" loading="lazy" decoding="async"></div>'
        f'<p class="edit__no">№ {e(p["id"])}</p><h3 class="edit__name">{e(item_name(p, lang))}</h3>'
        f'<p class="edit__price num">{price(p["price"], lang)}</p></a></li>'
        for p in items)
    run = 'not mass. not repeated. — ' * 6
    body = f'''<div class="curtain" aria-hidden="true"><img src="{logo}" alt="" width="1200" height="459"></div>
{BAG_SYMBOL}
<main id="main">
<section class="hero">
{home_img('hero', (480, 828, 1170), '(min-width: 960px) 50vw, 100vw', t('hero_alt', lang), ' fetchpriority="high"').replace('<img ', '<img class="hero__img" ', 1)}
<div class="hero__top">{lang_nav(lang, '')}<a class="icon-btn" href="{wa}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a></div>
<h1 class="hero__mark"><img src="{logo}" alt="attré" width="1200" height="459"></h1>
<div class="hero__card">
<p class="hero__slogan" lang="en">not mass. <span>not repeated.</span></p>
<p class="hero__sub">{e(t('intro_sub', lang))}</p>
<div class="hero__cta"><a class="btn" href="{cat}">{e(t('cta_catalog', lang))}</a><a class="btn btn--ghost btn--sq" href="{wa}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a></div>
</div>
</section>
<section class="story" data-story aria-labelledby="story-t">
<h2 class="story__title" id="story-t" lang="en"><span class="story__mass">not mass.</span> <span class="story__rep">not repeated.</span></h2>
<div class="story__stage">
<div class="story__grid" aria-hidden="true">{sils}</div>
<a class="story__card" href="{item_url(story_p, lang)}" tabindex="-1" aria-hidden="true"><img src="{url('assets/img/p/' + story_p['images'][0] + '-450.webp')}" srcset="{img_srcset(story_p['images'][0])}" sizes="230px" width="450" height="563" alt="" loading="lazy" decoding="async"></a>
</div>
<p class="story__text">{e(t('story_text', lang))}</p>
<a class="link story__link" href="{item_url(story_p, lang)}">{e(t('story_link', lang))} →</a>
</section>
<section class="mats" aria-label="{e(t('mats_title', lang))}">{mats}</section>
<section class="edit" aria-labelledby="edit-t">
<div class="edit__head"><h2 id="edit-t">{e(t('instock_title', lang))}</h2><a class="link" href="{cat}">{e(t('all_catalog', lang))} →</a></div>
<ul class="edit__track">{edit}<li class="edit__item edit__all"><a href="{cat}">{e(t('all_catalog', lang))}<span aria-hidden="true">→</span></a></li></ul>
</section>
<div class="marquee" aria-hidden="true"><div class="marquee__track"><span>{run}</span><span>{run}</span></div></div>
<section class="now" aria-label="{e(t('now_label', lang))}">
<p class="now__label">{e(t('now_label', lang))}</p>
<p class="now__time num" data-clock></p>
<p>{e(t('address', lang))}</p>
{'' if '[' in t('hours', lang) else f'<p>{e(t("hours", lang))}</p>'}
<p>{e(t('delivery_world', lang))}</p>
<a class="link" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a>
</section>
<section class="fin">
<h2 class="fin__title">{e(t('fin_title', lang))}</h2>
<a class="btn btn--wide" href="{cat}">{e(t('cta_catalog', lang))} →</a>
<a class="btn btn--ghost btn--wide" href="{wa}" target="_blank" rel="noopener">{WA_ICON}{e(t('wa_btn', lang))}</a>
<a class="link" href="https://www.instagram.com/{DATA['instagram']}/" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a>
</section>
</main>
<nav class="dock" aria-label="{e(t('dock_label', lang))}"><a href="{cat}">{e(t('dock_catalog', lang))}</a><a href="{wa}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a></nav>'''
    # html.js включает «скрыто до анимации»; если home.js не загрузился за 6 с или упал — снимаем,
    # чтобы финальные состояния остались видны.
    head = (f'<link rel="stylesheet" href="{url("assets/css/home.css")}?v={HVER}">'
            '<script>(function(d){d.classList.add("js");try{if(sessionStorage.getItem("attre-curtain"))'
            'd.classList.add("no-curtain");sessionStorage.setItem("attre-curtain","1")}catch(e){}'
            'setTimeout(function(){if(!window.__home)d.classList.remove("js")},6000)})(document.documentElement)</script>')
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_url('assets/img/brand/og.jpg'), body_class='home', extra_head=head, header=False,
                  extra_js=f'<script src="{url("assets/js/home.js")}?v={HVER}" defer onerror="document.documentElement.classList.remove(\'js\')"></script>')


# ——— Покупателям ———

def info_page(lang):
    credits = ''.join(
        f'<li><a href="{e(p["photo"]["url"])}" target="_blank" rel="noopener">{e(p["photo"]["author"])}</a> — {e(item_name(p, lang))}</li>'
        for p in DATA['products'] if p.get('photo'))
    body = f'''<main id="main" class="page">
<h1>{e(t('info_title', lang))}</h1>
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
<h2 id="credits">{e(t('credits_title', lang))}</h2>
<p>{e(t('credits_body', lang))}</p>
<ul>{credits}</ul>
</main>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_url('assets/img/brand/og.jpg'))


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
<img src="{BASE}assets/img/brand/logo-black.png" alt="attré" width="62" height="24">
<h1 style="margin-top:32px">404. <span lang="en">not repeated.</span></h1>
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
    write('index.html', root_redirect())
    write('404.html', not_found())
    write('robots.txt', 'User-agent: *\nDisallow: /\n' if PROTOTYPE else 'User-agent: *\nAllow: /\n')
    write('.nojekyll', '')
    pages = 3
    for l in LANGS:
        lang = l['code']
        write(f'{lang}/index.html', home_page(lang))
        write(f'{lang}/catalog/index.html', catalog_page(lang)); pages += 1
        for c in CATS:
            if any(p['cat'] == c for p in DATA['products']):
                write(f'{lang}/c/{c}/index.html', catalog_page(lang, c)); pages += 1
        for p in DATA['products']:
            write(f'{lang}/p/{p["slug"]}/index.html', product_page(p, lang)); pages += 1
        write(f'{lang}/info/index.html', info_page(lang))
        pages += 2
    print(f'site/: {pages} страниц, база {BASE}, адрес {ORIGIN}')


if __name__ == '__main__':
    main()
