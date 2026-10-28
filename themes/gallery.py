"""Тема «Галерея» (исходный минималистичный вариант): шапка с логотипом по центру,
обложка + подборка + баннеры, сетка 2 колонки 3:4 с подписями по центру."""
from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'site.css'
VER = asset_version('src/css/site.css', 'src/js/site.js')


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
<link rel="icon" href="{asset('assets/img/brand/favicon.png')}" type="image/png">
<link rel="apple-touch-icon" href="{asset('assets/img/brand/apple-touch-icon.png')}">
<link rel="preload" href="{asset('assets/fonts/onest-var.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{asset('assets/css/' + CSS)}?v={VER}">
<script>(function(d){{d.classList.add('js');setTimeout(function(){{if(!window.__site)d.classList.remove('js')}},6000)}})(document.documentElement)</script>
</head>
<body class="{body_class}">
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<header class="hdr">
<button class="hdr__btn" type="button" aria-controls="menu" aria-expanded="false" data-menu-open><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
<a class="hdr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="49" height="19"></a>
<a class="hdr__btn" href="{wa}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</header>
{menu(lang, suffix)}
<main id="main">
{body}
</main>
{footer(lang, suffix)}
{after}
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="document.documentElement.classList.remove('js')"></script>
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
<img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="46" height="18" loading="lazy">
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
<div class="card__media"><img class="fade" src="{asset(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw" width="600" height="800" alt="" loading="{loading}" decoding="async"></div>
<div class="card__body">
<{h} class="card__name">{e(name)}</{h}>
{f'<p class="card__meta">{e(meta)}</p>' if meta else ''}
<p class="card__price num">{e(price_text(p, lang))}</p>
{tag}
</div>
</a></li>'''


def catalog(lang, cat=None):
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
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'))


# ——— Товар ———

def product(p, lang):
    name = p['name'][lang]
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    n = len(p['images'])
    slides = ''.join(
        f'<div class="gallery__slide"><img class="fade" src="{asset(f"assets/img/p/{stem}-1200.webp")}" srcset="{img_srcset(stem)}" '
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
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product',
                  after=f'<div class="buybar">{btn.replace("{cta}", "")}</div>')


# ——— Главная ———

def home(lang):
    cover = HOME['cover']
    cat_url = url(lang + '/catalog/')
    cover_html = f'''<a class="cover" href="{cat_url}">
<img src="{asset(f"assets/img/home/{cover['_stem']}-1125.webp")}" srcset="{home_srcset(cover)}" sizes="100vw" width="1125" height="{round(1125 / cover['_ratio'])}" alt="{e(tri(cover.get('alt'))[lang])}" fetchpriority="high" decoding="async">
<span class="cap-wrap"><span class="cap cap--slogan">{e(t('slogan_1', lang))} {e(t('slogan_2', lang))}</span><span class="cap cap--link">{e(t('cta_catalog', lang))}</span></span>
</a>'''
    banners = ''.join(
        f'''<a class="banner" href="{url(lang + '/' + b['link'])}">
<img class="fade" src="{asset(f"assets/img/home/{b['_stem']}-750.webp")}" srcset="{home_srcset(b)}" sizes="(min-width: 960px) 33vw, (min-width: 600px) 50vw, 100vw" width="750" height="{round(750 / b['_ratio'])}" alt="{e(tri(b.get('alt'))[lang])}" loading="lazy" decoding="async">
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
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), body_class='home')


# ——— Покупателям ———

def info(lang):
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
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'))


