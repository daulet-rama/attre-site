"""Вариант 1 — по мотивам yourantihero.ru (сайт на Tilda), прежде всего мобильная версия.

Шапка 60px без линии: логотип слева, WhatsApp и бургер из двух линий справа. Меню — белая панель
под шапкой, остальная страница затемняется; бургер превращается в крестик. Главная — фото 2:3
во всю ширину подряд, без зазоров, подпись капсом по центру. Каталог — сразу сетка 2 × 50% без полей,
название и цена капсом по центру. Товар — свайп-галерея 3:4 с тонкой стрелкой, чёрная кнопка
WhatsApp, вкладки «характеристики / доставка / возврат», карусель «похожие» по одной карточке.
Шрифт — системный Arial, как у референса (на Android — Roboto); казахские буквы и ₸ в них есть.
Без JS всё видно: меню стоит списком под шапкой, вкладки идут разделами подряд."""
from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v1.css'
VER = asset_version('src/css/v1.css', 'src/js/site.js', 'src/js/v1.js')

# Тексты, которых нет в data/i18n.json
TEXTS = {
    'skip': {'ru': 'Перейти к содержанию', 'kz': 'Негізгі мазмұнға өту', 'en': 'Skip to content'},
    'photos': {'ru': '{name} — фото', 'kz': '{name} фотолары', 'en': '{name} — photos'},
    'next_photo': {'ru': 'Следующее фото', 'kz': 'Келесі фото', 'en': 'Next photo'},
    'about_item': {'ru': 'О товаре', 'kz': 'Тауар туралы', 'en': 'About this item'},
    'tab_returns': {'ru': 'возврат', 'kz': 'қайтару', 'en': 'returns'},
}

CHEVRON = ('<svg viewBox="0 0 12 24" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
           '<path d="M1.5 1.5L10.5 12 1.5 22.5" vector-effect="non-scaling-stroke"/></svg>')


def tx(key, lang):
    return TEXTS[key][lang]


def phone():
    n = str(DATA['whatsapp'])
    if len(n) == 11:  # 7 706 723 23 49
        return f'+{n[0]}{NBSP}{n[1:4]}{NBSP}{n[4:7]}{NBSP}{n[7:9]}{NBSP}{n[9:]}'
    return '+' + n


def ig_url():
    return f"https://www.instagram.com/{DATA['instagram']}/"


def langs(lang, suffix):
    links = ''.join(
        f'<li><a href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a></li>'
        for l in LANGS)
    return f'<ul class="langs" aria-label="{e(t("nav_lang", lang))}">{links}</ul>'


# ——— Каркас страницы ———

def menu(lang, suffix, current):
    info = url(f'{lang}/info/')

    def item(href, label, key):
        cur = ' aria-current="page"' if key == current else ''
        return f'<li><a href="{href}"{cur}>{e(label)}</a></li>'

    cats = ''.join(item(url(f'{lang}/c/{c}/'), CATS[c][lang], f'c/{c}') for c in present_cats())
    return f'''<nav class="menu" id="v1-menu" aria-label="{e(t('menu', lang))}" data-v1-menu>
<ul class="menu__list">
{item(url(lang + '/catalog/'), t('all_items', lang), 'catalog')}
{cats}
</ul>
<ul class="menu__list menu__list--sub">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>
{langs(lang, suffix)}
<ul class="menu__social">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp</a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram</a></li>
</ul>
</nav>'''


def footer(lang, suffix):
    info = url(f'{lang}/info/')
    proto = f'<p>{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<h2 class="ftr__h">{e(t('f_buyers', lang))}</h2>
<ul class="ftr__list">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>
<h2 class="ftr__h">{e(t('f_contacts', lang))}</h2>
<ul class="ftr__list">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a class="lc" href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
</ul>
{langs(lang, suffix)}
<p class="ftr__slogan">{e(t('slogan_1', lang))} {e(t('slogan_2', lang))}</p>
<div class="ftr__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
{proto}
</div>
</footer>'''


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', current='', page=''):
    lang_cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    no_js = "document.documentElement.classList.remove('js')"
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
<link rel="icon" href="{asset('assets/img/brand/favicon.png')}" type="image/png">
<link rel="apple-touch-icon" href="{asset('assets/img/brand/apple-touch-icon.png')}">
<link rel="stylesheet" href="{asset('assets/css/' + CSS)}?v={VER}">
<script>(function(d){{d.classList.add('js');setTimeout(function(){{if(!window.__site)d.classList.remove('js')}},6000)}})(document.documentElement)</script>
</head>
<body class="v1-{page}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<div class="top" data-v1-top>
<header class="hdr">
<a class="hdr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="57" height="22"></a>
<div class="hdr__icons">
<a class="hdr__icon" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
<button class="hdr__icon hdr__burger" type="button" aria-expanded="false" aria-controls="v1-menu" data-v1-menu-btn><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
</div>
</header>
{menu(lang, suffix, current)}
</div>
<div class="shade" data-v1-shade aria-hidden="true"></div>
<main class="main" id="main" tabindex="-1">
{body}
</main>
{footer(lang, suffix)}
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="{no_js}"></script>
<script src="{asset('assets/js/v1.js')}?v={VER}" defer onerror="{no_js}"></script>
</body>
</html>
'''


# ——— Каталог ———

CARD_SIZES = '(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw'
SIM_SIZES = '(min-width: 960px) 25vw, (min-width: 600px) 40vw, 70vw'


def card(p, lang, *, h='h2', eager=False, high=False, sizes=CARD_SIZES):
    stem = p['images'][0]
    load = ' fetchpriority="high"' if high else '' if eager else ' loading="lazy"'
    note = t('sold', lang) if sold(p) else t('last', lang) if p['stock'] == 1 else ''
    note_html = f'<p class="card__note">{e(note)}</p>' if note else ''
    return f'''<li class="card"><a href="{item_url(p, lang)}">
<div class="card__media"><img class="fade" src="{asset(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" sizes="{sizes}" width="600" height="800" alt=""{load} decoding="async"></div>
<{h} class="card__name">{e(p['name'][lang])}</{h}>
<p class="card__price num">{e(price_text(p, lang))}</p>
{note_html}
</a></li>'''


def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    cards = ''.join(card(p, lang, eager=i < 4, high=i < 2) for i, p in enumerate(items))
    grid = f'<ul class="grid">\n{cards}\n</ul>' if items else f'<p class="empty">{e(t("empty", lang))}</p>'
    body = f'''<div class="cat">
<h1 class="sr-only">{e(heading)}</h1>
{grid}
</div>'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'),
                  current=f'c/{cat}' if cat else 'catalog', page='catalog')


# ——— Товар ———

def product(p, lang):
    name = p['name'][lang]
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    info = url(f'{lang}/info/')
    n = len(p['images'])
    slides = []
    for i, stem in enumerate(p['images']):
        alt = e(name) + (' — ' + e(t('photo_n', lang, i=i + 1, n=n)) if i else '')
        load = ' fetchpriority="high"' if i == 0 else '' if i == 1 else ' loading="lazy"'
        cls = ' class="fade"' if i else ''
        slides.append(
            f'<div class="gal__slide"><img{cls} src="{asset(f"assets/img/p/{stem}-1200.webp")}" '
            f'srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 50vw, 100vw" width="1200" height="1600" '
            f'alt="{alt}"{load} decoding="async"></div>')
    arrow = (f'<button class="gal__next" type="button" aria-controls="v1-gal" '
             f'aria-label="{e(tx("next_photo", lang))}">{CHEVRON}</button>') if n > 1 else ''

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
        note = t('sold', lang)
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        label = t('wa_btn', lang)
        note = t('last', lang) if p['stock'] == 1 else ''
    meta = meta_line(p, lang)
    meta_html = f'<p class="pdp__meta">{e(meta)}</p>' if meta else ''
    note_html = f'<p class="pdp__note">{e(note)}</p>' if note else ''
    desc_html = f'<p class="pdp__desc">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    hours = t('hours', lang)

    tabs = [('spec', t('acc_details', lang), t('acc_details', lang), f'<dl class="spec">{spec}</dl>'),
            ('del', t('acc_delivery', lang), t('f_delivery', lang),
             f'''<p>{e(t('delivery_body', lang))}</p>
<p>{e(t('payment_body', lang))}</p>
<h3 class="tabs__sub">{e(t('store_title', lang))}</h3>
<p>{e(t('store_body', lang))}</p>
<p>{e(hours)}</p>
<a class="lnk" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a>'''),
            ('ret', tx('tab_returns', lang), t('acc_returns', lang), f'<p>{e(t("returns_body", lang))}</p>')]
    tab_btns = ''.join(
        f'<button class="tabs__tab" type="button" role="tab" id="v1-tab-{k}" aria-controls="v1-panel-{k}" '
        f'aria-selected="{"true" if i == 0 else "false"}"{"" if i == 0 else " tabindex=\"-1\""}>{e(short)}</button>'
        for i, (k, short, _, _) in enumerate(tabs))
    panels = ''.join(
        f'''<section class="tabs__panel" id="v1-panel-{k}" aria-labelledby="v1-h-{k}">
<h2 class="tabs__h" id="v1-h-{k}">{e(full)}</h2>
{content}
</section>
''' for k, _, full, content in tabs)

    body = f'''<div class="pdp-wrap">
<div class="gal" data-v1-gal>
<div class="gal__track" id="v1-gal" role="region" tabindex="0" aria-label="{e(tx('photos', lang).replace('{name}', name))}">{''.join(slides)}</div>
{arrow}
</div>
<div class="pdp">
<h1 class="pdp__name">{e(name)}</h1>
<p class="pdp__price num">{e(price_text(p, lang))}</p>
{meta_html}
{note_html}
<a class="btn" href="{e(wa_link(msg))}" target="_blank" rel="noopener">{e(label)}</a>
<a class="pdp__bonus" href="{info}#bonus"><span><span class="u">{e(t('bonus_short', lang))}</span> — {e(t('bonus_hint', lang))}</span></a>
{desc_html}
<div class="tabs" data-v1-tabs>
<div class="tabs__list" role="tablist" aria-label="{e(tx('about_item', lang))}">{tab_btns}</div>
{panels}</div>
</div>
</div>
<section class="sim" aria-labelledby="v1-sim">
<h2 class="sim__title" id="v1-sim">{e(t('similar', lang))}</h2>
<ul class="sim__track">
{''.join(card(q, lang, h='h3', sizes=SIM_SIZES) for q in similar(p))}
</ul>
</section>'''
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product',
                  current=f"p/{p['slug']}", page='product')


# ——— Главная ———

def obj_pos(item, target=2 / 3):
    """Точка кадра для object-position: тот же фокус, что при нарезке, но для кадра 2:3."""
    r = item.get('_ratio') or target
    focus = item.get('focus') or [.5, .5]
    fx, fy = float(focus[0]), float(focus[1])
    if abs(r - target) < .01:
        return '50% 50%'
    if r < target:  # фото выше кадра — режем сверху и снизу
        h, ch = 1 / r, 1 / target
        top = min(max(fy * h - ch / 2, 0), h - ch)
        return f'50% {round(top / (h - ch) * 100)}%'
    w, cw = r, target  # фото шире кадра — режем по бокам
    left = min(max(fx * w - cw / 2, 0), w - cw)
    return f'{round(left / (w - cw) * 100)}% 50%'


def home(lang):
    items = [(HOME['cover'], url(lang + '/catalog/'), t('all_items', lang))]
    items += [(b, url(lang + '/' + b['link']), tri(b['label'])[lang]) for b in HOME['banners']]
    looks = []
    for it, href, label in items:
        widths = it.get('_widths') or []
        if not widths:
            continue
        first = not looks
        w = 1125 if 1125 in widths else widths[0]
        load = ' fetchpriority="high"' if first else ' loading="lazy"'
        cls = '' if first else ' class="fade"'
        looks.append(f'''<a class="look" href="{href}">
<img{cls} src="{asset(f"assets/img/home/{it['_stem']}-{w}.webp")}" srcset="{home_srcset(it)}" sizes="(min-width: 960px) 25vw, (min-width: 600px) 50vw, 100vw" width="{w}" height="{round(w / it['_ratio'])}" alt="{e(tri(it.get('alt'))[lang])}" style="object-position: {obj_pos(it)}"{load} decoding="async">
<span class="look__cap">{e(label)}</span>
</a>''')
    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
<div class="looks">
{''.join(looks)}
</div>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='home')


# ——— Покупателям ———

def info(lang):
    hours = t('hours', lang)
    body = f'''<div class="page">
<h1 class="page__title">{e(t('info_title', lang))}</h1>
<section id="bonus">
<h2>{e(t('bonus_title', lang))}</h2>
<p>{e(t('bonus_body', lang))}</p>
<p class="note">{e(t('bonus_terms', lang))}</p>
</section>
<section id="about">
<h2>{e(t('about_title', lang))}</h2>
<p>{e(t('about_body', lang))}</p>
</section>
<section id="delivery">
<h2>{e(t('delivery_title', lang))}</h2>
<p>{e(t('delivery_body', lang))}</p>
<p>{e(t('payment_body', lang))}</p>
</section>
<section id="returns">
<h2>{e(t('returns_title', lang))}</h2>
<p>{e(t('returns_body', lang))}</p>
</section>
<section id="contacts">
<h2>{e(t('contacts_title', lang))}</h2>
<p>{e(t('address', lang))}<br>{e(hours)}</p>
<ul class="page__links">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">{e(t('wa_label', lang))}</a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>
</section>
<section id="seller">
<h2>{e(t('seller_title', lang))}</h2>
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
</section>
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), current='info', page='info')
