"""Тема «Вариант 2» по мотивам ushatava.ru.

Шапка 44px (бургер · логотип · WhatsApp), чёрная полоса бонуса с крестиком, меню на весь экран слева,
шторки справа (категории в каталоге, характеристики/доставка/возврат/магазин на странице товара).
Главная — баннеры 9:16 встык, каталог — «большие» карточки: два фото рядом, листаются свайпом.
Один гротеск 12px с разрядкой .05em, капс в навигации, без скруглений и теней.
Без JS всё видно: меню и шторки становятся обычными блоками внизу страницы.
"""
import datetime

from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v2.css'
VER = asset_version('src/css/v2.css', 'src/js/site.js', 'src/js/v2.js')

TEXTS = {
    'skip': {'ru': 'Перейти к содержимому', 'kz': 'Негізгі мазмұнға өту', 'en': 'Skip to content'},
    'promo_hide': {'ru': 'Скрыть полосу с бонусом', 'kz': 'Бонус жолағын жасыру', 'en': 'Hide the bonus banner'},
    'store': {'ru': 'магазин', 'kz': 'дүкен', 'en': 'store'},
    'sku': {'ru': 'Артикул', 'kz': 'Артикул', 'en': 'Item no.'},
    'prev': {'ru': 'Предыдущее фото', 'kz': 'Алдыңғы фото', 'en': 'Previous photo'},
    'next': {'ru': 'Следующее фото', 'kz': 'Келесі фото', 'en': 'Next photo'},
    'photos': {'ru': 'Фото товара', 'kz': 'Тауар фотолары', 'en': 'Product photos'},
}


def tx(key, lang):
    return TEXTS[key][lang]


# Свои значки (рисованы здесь): крестик 10×10 и «плитка» категорий. Треугольники ▸ — CSS (clip-path).
X_ICON = ('<svg class="ico-x" viewBox="0 0 10 10" aria-hidden="true">'
          '<path d="M1 1l8 8M9 1L1 9" fill="none" stroke="currentColor" stroke-width="1"/></svg>')
GRID_ICON = ('<svg class="ico-grid" viewBox="0 0 10 10" aria-hidden="true">'
             '<path d="M.5.5h3.5v3.5H.5zM6 .5h3.5v3.5H6zM.5 6h3.5v3.5H.5zM6 6h3.5v3.5H6z" '
             'fill="none" stroke="currentColor" stroke-width="1"/></svg>')

# Класс html.js ставится до отрисовки; закрытая полоса бонуса (7 дней) прячется тоже до отрисовки.
HEAD_JS = ("(function(d){d.classList.add('js');"
           "try{var t=+localStorage.getItem('attre-v2-promo');if(t&&Date.now()-t<6048e5)d.classList.add('promo-off')}catch(e){}"
           "setTimeout(function(){if(!window.__v2)d.classList.remove('js')},6000)})(document.documentElement)")


def phone():
    n = DATA['whatsapp']
    return NBSP.join(('+' + n[0], n[1:4], n[4:7], n[7:9], n[9:]))


def ig_url():
    return f"https://www.instagram.com/{DATA['instagram']}/"


def langs(lang, suffix, cls=''):
    links = ''.join(
        f'<a href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a>'
        for l in LANGS)
    return f'<nav class="langs {cls}" aria-label="{e(t("nav_lang", lang))}">{links}</nav>'


def cat_links(lang):
    return [(None, t('all_items', lang), url(lang + '/catalog/'))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/')) for c in present_cats()]


# ——— Каркас страницы ———

def promo(lang):
    return f'''<div class="promo">
<a class="promo__link" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<button class="promo__x js-only" type="button" aria-label="{e(tx('promo_hide', lang))}" data-promo-close>{X_ICON}</button>
</div>'''


def header(lang):
    return f'''<header class="hdr">
<button class="hdr__btn hdr__menu js-only" type="button" aria-controls="menu" aria-expanded="false" data-open="menu"><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
<a class="hdr__logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="{e(t('home', lang))}" width="41" height="16"></a>
<a class="hdr__btn hdr__wa" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</header>'''


def menu(lang, suffix):
    info = url(f'{lang}/info/')
    cats = ''.join(f'<li><a class="go" href="{h}">{e(label)}</a></li>' for _, label, h in cat_links(lang))
    return f'''<div class="menu" id="menu" data-panel data-label="{e(t('menu', lang))}">
<div class="menu__top">
<a class="menu__brand" href="{url(lang + '/')}">{e(DATA['instagram'])}</a>
<button class="pnl-x js-only" type="button" data-close>{e(t('close', lang))}{X_ICON}</button>
</div>
<nav class="menu__nav" aria-label="{e(t('menu', lang))}">
<ul class="mn">{cats}</ul>
<ul class="mn">
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp<span class="mn__aside num">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram<span class="mn__aside">@{e(DATA['instagram'])}</span></a></li>
</ul>
<ul class="mn mn--low">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
</ul>
</nav>
{langs(lang, suffix, 'menu__langs')}
</div>'''


def footer(lang, suffix):
    info = url(f'{lang}/info/')
    proto = f'<p>{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<div class="ftr__acc">
<details class="fa"><summary>{e(t('f_buyers', lang))}</summary><ul class="fa__body fa__body--low">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul></details>
<details class="fa"><summary>{e(t('f_contacts', lang))}</summary><ul class="fa__body">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
</ul></details>
<details class="fa"><summary>{e(tx('store', lang))}</summary><div class="fa__body">
<p>{e(t('address', lang))}</p>
<p>{e(t('hours', lang))}</p>
<p>{e(t('delivery_world', lang))}</p>
<a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a>
</div></details>
</div>
<div class="ftr__row"><p class="ftr__copy">© {datetime.date.today().year} attré</p>{langs(lang, suffix, 'ftr__langs')}</div>
<div class="ftr__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
{proto}
</div>
</footer>'''


def drawer(id_, title, body, lang):
    """Шторка справа. Без JS — обычный блок с заголовком на своём месте в странице."""
    return f'''<section class="dw" id="{id_}" data-panel aria-labelledby="{id_}-t">
<div class="dw__top"><h2 class="dw__t" id="{id_}-t">{e(title)}</h2><button class="pnl-x js-only" type="button" data-close>{e(t('close', lang))}{X_ICON}</button></div>
<div class="dw__body">{body}</div>
</section>'''


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', page=''):
    cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    return f'''<!doctype html>
<html lang="{cfg['html']}">
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
<meta property="og:locale" content="{cfg['og']}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{asset('assets/img/brand/favicon.png')}" type="image/png">
<link rel="apple-touch-icon" href="{asset('assets/img/brand/apple-touch-icon.png')}">
<link rel="preload" href="{asset('assets/fonts/onest-var.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{asset('assets/css/' + CSS)}?v={VER}">
<script>{HEAD_JS}</script>
</head>
<body class="{page}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
{promo(lang)}
{header(lang)}
<main id="main">
{body}
</main>
{footer(lang, suffix)}
{menu(lang, suffix)}
<div class="scrim" data-scrim></div>
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="document.documentElement.classList.remove('js')"></script>
<script src="{asset('assets/js/v2.js')}?v={VER}" defer onerror="document.documentElement.classList.remove('js')"></script>
</body>
</html>
'''


# ——— Каталог: «большие» карточки, два фото рядом, свайп ———

def tag(p, lang):
    if sold(p):
        return f'<p class="tag">{e(t("sold", lang))}</p>'
    if p['stock'] == 1:
        return f'<p class="tag">{e(t("last", lang))}</p>'
    return ''


def card(p, lang, eager=False, h='h2'):
    n = len(p['images'])
    sizes = '(min-width: 960px) 50vw, 100vw' if n == 1 else '(min-width: 960px) 25vw, 50vw'
    imgs = ''.join(
        f'<img src="{asset(f"assets/img/p/{stem}-600.webp")}" srcset="{img_srcset(stem)}" sizes="{sizes}" '
        f'width="600" height="800" alt="" '
        f'loading="{"eager" if eager and i < 2 else "lazy"}"{" fetchpriority=\"high\"" if eager and i == 0 else ""} decoding="async">'
        for i, stem in enumerate(p['images']))
    # Точки — по числу положений ленты (видно два фото сразу), как у листалки с двумя слайдами на экране
    dots = ('<span class="dots" aria-hidden="true"><i class="is-on"></i>' + '<i></i>' * (n - 2) + '</span>') if n > 2 else ''
    cls = 'pc' + (' pc--one' if n == 1 else '') + (' pc--sold' if sold(p) else '')
    return f'''<li class="{cls}"><a class="pc__a" href="{item_url(p, lang)}">
<div class="pc__media" data-slider><div class="pc__track" tabindex="-1">{imgs}</div>{dots}</div>
<div class="pc__body">{tag(p, lang)}<{h} class="pc__name">{e(p['name'][lang])}</{h}><p class="pc__price num">{e(price_text(p, lang))}</p></div>
</a></li>'''


def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    rows = ''.join(
        f'<li><a href="{h}"{" aria-current=\"page\"" if c == cat else ""}>{e(label)}</a></li>'
        for c, label, h in cat_links(lang))
    cats_drawer = drawer('dw-cats', t('nav_cats', lang), f'<ul class="dw__list">{rows}</ul>', lang)
    body = f'''<div class="tb">
<h1 class="tb__t">{e(heading)}</h1>
<button class="tb__btn js-only" type="button" aria-controls="dw-cats" aria-expanded="false" data-open="dw-cats">{e(t('nav_cats', lang))}{GRID_ICON}</button>
</div>
{cats_drawer}
<ul class="pl">
{''.join(card(p, lang, eager=i == 0) for i, p in enumerate(items))}
</ul>
{'' if items else f'<p class="empty">{e(t("empty", lang))}</p>'}'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-catalog')


# ——— Товар ———

def small_card(p, lang):
    stem = p['images'][0]
    return f'''<li class="sc"><a href="{item_url(p, lang)}">
<img src="{asset(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 25vw, 50vw" width="600" height="800" alt="" loading="lazy" decoding="async">
<div class="sc__body">{tag(p, lang)}<h3 class="sc__name">{e(p['name'][lang])}</h3><p class="sc__price num">{e(price_text(p, lang))}</p></div>
</a></li>'''


def product(p, lang):
    name = p['name'][lang]
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    info = url(lang + '/info/')
    n = len(p['images'])
    slides = ''.join(
        f'<img src="{asset(f"assets/img/p/{stem}-1200.webp")}" srcset="{img_srcset(stem)}" '
        f'sizes="(min-width: 960px) 28vw, 100vw" width="1200" height="1600" '
        f'alt="{e(name)}{" — " + e(t("photo_n", lang, i=i + 1, n=n)) if n > 1 else ""}" '
        f'loading="{"eager" if i == 0 else "lazy"}"{" fetchpriority=\"high\"" if i == 0 else ""} decoding="async">'
        for i, stem in enumerate(p['images']))
    nav = '' if n < 2 else f'''<span class="pg__count js-only" aria-hidden="true">1 / {n}</span>
<button class="pg__arr pg__arr--prev js-only" type="button" aria-label="{e(tx('prev', lang))}" data-step="-1"></button>
<button class="pg__arr pg__arr--next js-only" type="button" aria-label="{e(tx('next', lang))}" data-step="1"></button>'''

    todo = f'<span class="todo">{e(t("todo", lang))}</span>'
    size = (f'<span class="num">{e(t("p_size_fmt", lang, w=p["size"][0], h=p["size"][1], d=p["size"][2]))}</span>'
            if p['size'] else todo)
    spec_rows = [
        (t('p_type', lang), e(p['type'][lang]) if p['type'][lang] else todo),
        (t('p_color', lang), e(p['color'][lang]) if p['color'][lang] else todo),
        (t('p_material', lang), e(MATS[p['material']][lang]) if p['material'] else todo),
        (t('p_size', lang), size),
        (t('p_strap', lang), e(p['strap'][lang]) if p['strap'] else todo),
        (t('p_maker', lang), todo),
        (t('p_origin', lang), todo),
    ]
    spec = '<dl class="spec">' + ''.join(f'<div><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in spec_rows) + '</dl>'
    drawers = [
        ('dw-spec', t('acc_details', lang), spec),
        ('dw-delivery', t('f_delivery', lang),
         f'<p>{e(t("delivery_body", lang))}</p><p>{e(t("payment_body", lang))}</p>'),
        ('dw-returns', t('acc_returns', lang), f'<p>{e(t("returns_body", lang))}</p>'),
        ('dw-store', t('acc_store', lang),
         f'<p>{e(t("store_body", lang))}</p><p>{e(t("hours", lang))}</p>'
         f'<p><a class="ul" href="{e(DATA["map_url"])}" target="_blank" rel="noopener">{e(t("map", lang))}</a></p>'),
    ]
    rows = ''.join(
        f'<li><button class="go" type="button" aria-controls="{i}" aria-expanded="false" data-open="{i}">{e(label)}</button></li>'
        for i, label, _ in drawers)
    if sold(p):
        msg = t('wa_sold', lang, name=name, id=p['id'], url=page_url)
        label = t('wa_btn_sold', lang)
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        label = t('wa_btn', lang)
    meta = meta_line(p, lang)
    desc = f'<p>{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    sim = similar(p)
    sim_html = f'''<section class="sim" aria-labelledby="sim-t">
<h2 class="sim__t" id="sim-t">{e(t('similar', lang))}</h2>
<ul class="sg">{''.join(small_card(q, lang) for q in sim)}</ul>
</section>''' if sim else ''
    body = f'''<div class="pp">
<section class="pg" aria-label="{e(tx('photos', lang))}" data-pg>
<div class="pg__track" tabindex="-1">{slides}</div>
{nav}
</section>
<div class="pi">
{tag(p, lang)}
<div class="pi__head">
<div><h1 class="pi__name">{e(name)}</h1>{f'<p class="pi__meta">{e(meta)}</p>' if meta else ''}</div>
<p class="pi__price num">{e(price_text(p, lang))}</p>
</div>
<a class="btn" href="{e(wa_link(msg))}" target="_blank" rel="noopener">{e(label)}</a>
<a class="pi__bonus" href="{info}#bonus"><span class="ul">{e(t('bonus_short', lang))}</span> — {e(t('bonus_hint', lang))}</a>
<div class="pi__desc">{desc}<p>{e(tx('sku', lang))}: <span class="num">{e(p['id'])}</span></p></div>
<ul class="rows js-only">{rows}</ul>
</div>
</div>
<div class="dws">{''.join(drawer(i, title, b, lang) for i, title, b in drawers)}</div>
{sim_html}'''
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product', page='p-product')


# ——— Главная: баннеры 9:16 встык ———

_TONE = {}


def dark_caption(item):
    """Светлый кадр под подписью (нижняя часть баннера) — подпись чёрная, иначе белая с лёгким затемнением.
    Считается по уже нарезанному фото; если его нет — белая подпись."""
    stem = item['_stem']
    if stem not in _TONE:
        dark = False
        try:
            from PIL import Image, ImageStat
            files = sorted((OUT_ROOT / 'assets' / 'img' / 'home').glob(f'{stem}-*.webp'))
            if files:
                im = Image.open(files[0]).convert('L')
                w, h = im.size
                cw = min(w, round(h * 9 / 16))   # кадр 9:16 по центру, как object-fit: cover
                left = (w - cw) // 2
                band = im.crop((left + round(cw * .2), round(h * .84), left + round(cw * .8), round(h * .92)))
                dark = ImageStat.Stat(band).mean[0] > 175
        except Exception:  # noqa: BLE001 — подпись по умолчанию белая
            dark = False
        _TONE[stem] = dark
    return _TONE[stem]


def banner(item, href, caption, lang, first=False, hint=''):
    w = item['_widths'][0] if item['_widths'] else 750
    src = asset(f"assets/img/home/{item['_stem']}-{w}.webp")
    load = 'fetchpriority="high"' if first else 'loading="lazy"'
    cls = 'bn bn--dark' if dark_caption(item) else 'bn'
    return f'''<a class="{cls}" href="{href}">
<span class="bn__cap">{e(caption)}{f'<span class="sr-only"> — {e(hint)}</span>' if hint else ''}</span>
<img src="{src}" srcset="{home_srcset(item)}" sizes="(min-width: 960px) 25vw, (min-width: 600px) 50vw, 100vw" width="{w}" height="{round(w / item['_ratio'])}" alt="{e(tri(item.get('alt'))[lang])}" {load} decoding="async">
</a>'''


def home(lang):
    cover = HOME['cover']
    slogan = f"{t('slogan_1', lang)} {t('slogan_2', lang)}"
    tiles = [banner(cover, url(lang + '/catalog/'), slogan, lang, first=True, hint=t('cta_catalog', lang))]
    tiles += [banner(b, url(lang + '/' + b['link']), tri(b['label'])[lang], lang) for b in HOME['banners']]
    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
<div class="hm">
{''.join(tiles)}
</div>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-home')


# ——— Покупателям ———

def info(lang):
    body = f'''<div class="tb tb--static"><h1 class="tb__t">{e(t('info_title', lang))}</h1></div>
<div class="txt">
<section class="sec" id="bonus">
<h2>{e(t('bonus_title', lang))}</h2>
<p>{e(t('bonus_body', lang))}</p>
<p class="note">{e(t('bonus_terms', lang))}</p>
</section>
<section class="sec" id="about">
<h2>{e(t('about_title', lang))}</h2>
<p>{e(t('about_body', lang))}</p>
</section>
<section class="sec" id="delivery">
<h2>{e(t('delivery_title', lang))}</h2>
<p>{e(t('delivery_body', lang))}</p>
<p>{e(t('payment_body', lang))}</p>
</section>
<section class="sec" id="returns">
<h2>{e(t('returns_title', lang))}</h2>
<p>{e(t('returns_body', lang))}</p>
</section>
<section class="sec" id="contacts">
<h2>{e(t('contacts_title', lang))}</h2>
<p>{e(t('address', lang))}<br>{e(t('hours', lang))}</p>
<ul class="links">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>
</section>
<section class="sec" id="seller">
<h2>{e(t('seller_title', lang))}</h2>
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
</section>
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-info')
