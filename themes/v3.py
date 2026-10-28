"""Тема «Вариант 3» — по мотивам massimodutti.com (редизайн 2026), главное — мобильная версия.

Тонкий Onest 300; подписи 12px капсом с разрядкой .16em; чёрное на белом, подложка фото #f6f6f6,
без радиусов и теней. Белая шапка 48px: бургер, логотип слева, WhatsApp справа; меню — белый
«занавес» на весь экран. Главная — стек портретных фото встык. Каталог — липкая панель
«фильтры / вид», нижний лист с категориями, сетка 2 ↔ 1. Товар — фото лентой, три строки
с нижними листами, липкая нижняя панель с названием, ценой и кнопкой WhatsApp.
Поведение: src/js/site.js (меню, проявление фото) + src/js/v3.js (листы, вид, фокус).
Без JS: листы раскрыты прямо на странице, кнопки, которым нужен JS, спрятаны.
"""
from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v3.css'
VER = asset_version('src/css/v3.css', 'src/js/site.js', 'src/js/v3.js')

# Тексты, которых нет в data/i18n.json
TEXTS = {
    'filters': {'ru': 'фильтры', 'kz': 'сүзгілер', 'en': 'filters'},
    'view': {'ru': 'вид', 'kz': 'көрініс', 'en': 'view'},
    'view_hint': {'ru': ' — товаров в ряду', 'kz': ' — бір қатардағы тауар саны', 'en': ' — items per row'},
    'sh_delivery': {'ru': 'доставка, оплата и возврат', 'kz': 'жеткізу, төлем және қайтару',
                    'en': 'delivery, payment & returns'},
    'may_like': {'ru': 'вам может понравиться', 'kz': 'сізге ұнауы мүмкін', 'en': 'you may also like'},
    'ref': {'ru': 'арт.', 'kz': 'арт.', 'en': 'ref.'},
    'store': {'ru': 'магазин', 'kz': 'дүкен', 'en': 'store'},
    'legal': {'ru': 'юридическая информация', 'kz': 'құқықтық ақпарат', 'en': 'legal information'},
    'country': {'ru': 'Казахстан (₸)', 'kz': 'Қазақстан (₸)', 'en': 'Kazakhstan (₸)'},
    'more': {'ru': 'подробнее', 'kz': 'толығырақ', 'en': 'learn more'},
    'sections': {'ru': 'разделы', 'kz': 'бөлімдер', 'en': 'sections'},
    'n_bonus': {'ru': 'бонус', 'kz': 'бонус', 'en': 'bonus'},
    'n_returns': {'ru': 'возврат', 'kz': 'қайтару', 'en': 'returns'},
    'n_seller': {'ru': 'продавец', 'kz': 'сатушы', 'en': 'seller'},
    'skip': {'ru': 'к содержанию', 'kz': 'негізгі мазмұнға өту', 'en': 'skip to content'},
}


def tx(key, lang):
    return TEXTS[key][lang]


CUR = ' aria-current="page"'
# Прозрачный пиксель: фото плиток меню подставляет v3.js, чтобы закрытое меню не тянуло трафик
PIXEL = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
CHEV = ('<svg class="chev" viewBox="0 0 6 10" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
        '<path d="M1 1l4 4-4 4"/></svg>')
CHEV_DOWN = ('<svg class="chev-d" viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
             '<path d="M1 1l4 4 4-4"/></svg>')
SIZES_CARD = '(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw'


# Линейная яркость канала sRGB — для подбора подписи на фото главной
LIN = [(c / 255) / 12.92 if c <= 10 else ((c / 255 + .055) / 1.055) ** 2.4 for c in range(256)]
_TONE = {}


def tone(path):
    """Подпись поверх фото: светлый однородный низ — чёрный текст без затемнения (' is-light', 0);
    иначе белый текст и затемнение снизу, которого хватает на контраст 5:1 по самым светлым
    10 % пикселей под подписью. Фото уже нарезаны в site/assets; нет Pillow или файла — сильное затемнение."""
    if path not in _TONE:
        res = ('', .6)
        try:
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
                b = im.convert('RGB').crop((round(w * .2), round(h * .85), round(w * .8), round(h * .97))).resize((48, 12)).tobytes()
            ls = sorted(.2126 * LIN[b[i]] + .7152 * LIN[b[i + 1]] + .0722 * LIN[b[i + 2]] for i in range(0, len(b), 3))
            p10, p90 = ls[len(ls) // 10], ls[len(ls) * 9 // 10]
            if p10 >= .3:
                res = (' is-light', 0)
            else:
                k = (1.05 / 5 - .05) / max(p90, 1e-4)          # во сколько раз притемнить (цель 5:1 — с запасом)
                a = 1 - min(1, k) ** (1 / 2.2)                 # непрозрачность чёрного под текстом
                res = ('', round(min(max(a / .95, .3), .6), 2))  # под подписью — 95 % градиента
        except Exception:  # noqa: BLE001 — нет Pillow или фото: остаётся сильное затемнение
            pass
        _TONE[path] = res
    return _TONE[path]


def phone():
    n = DATA['whatsapp']
    return f'+{n[0]}{NBSP}{n[1:4]}{NBSP}{n[4:7]}{NBSP}{n[7:9]}{NBSP}{n[9:]}'


def lead_stem(c):
    """Первое фото первой вещи категории (проданные — в конце)."""
    items = ordered([p for p in DATA['products'] if p['cat'] == c])
    return items[0]['images'][0] if items else None


def langs(lang, suffix):
    return ''.join(
        f'<a class="lng" href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a>'
        for l in LANGS)


def social(lang):
    return (f'<li><a href="{e(wa_link(t("wa_general", lang)))}" target="_blank" rel="noopener">'
            f'WhatsApp <span class="num">{phone()}</span></a></li>'
            f'<li><a href="https://www.instagram.com/{e(DATA["instagram"])}/" target="_blank" rel="noopener">'
            f'Instagram @{e(DATA["instagram"])}</a></li>')


def sheet(sid, title, inner, lang, mod=''):
    """Нижний лист. Без JS — обычный раздел на странице; v3.js переносит его в конец body
    и делает диалогом (role="dialog", aria-modal)."""
    return f'''<section class="sheet{mod}" id="{sid}" data-sheet aria-labelledby="{sid}-t">
<div class="sheet__head"><h2 class="sheet__title" id="{sid}-t">{e(title)}</h2><button class="sheet__close" type="button" data-sheet-close aria-label="{e(t('close', lang))}">{CROSS}</button></div>
<div class="sheet__body">{inner}</div>
</section>'''


def opener(sid, label, cls):
    return (f'<button class="{cls}" type="button" data-sheet-open="{sid}" aria-controls="{sid}" '
            f'aria-expanded="false" aria-haspopup="dialog">{label}</button>')


# ——— Меню-«занавес» ———

def menu(lang, suffix, cur):
    """cur — раздел текущей страницы: (ключ, True) на самой странице раздела, (ключ, False) на товаре из него."""
    info = url(f'{lang}/info/')
    key_cur, exact = cur or (None, False)
    mark = CUR if exact else ' aria-current="true"'
    cats = present_cats()
    tabs = [('all', t('all_items', lang), url(lang + '/catalog/'))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/')) for c in cats]
    tabs_html = ''.join(f'<li><a href="{href}"{mark if key == key_cur else ""}>{e(label)}</a></li>'
                        for key, label, href in tabs)
    tiles = []
    for c in cats:
        stem = lead_stem(c)
        img = (f'<img class="mimg" src="{PIXEL}" data-src="{asset(f"assets/img/p/{stem}-600.webp")}" '
               f'data-srcset="{img_srcset(stem)}" sizes="(min-width: 600px) 22vw, 45vw" '
               f'width="600" height="800" alt="" decoding="async">') if stem else ''
        tiles.append(f'<li><a class="mtile" href="{url(f"{lang}/c/{c}/")}"><span class="mtile__media">{img}</span>'
                     f'<span class="mtile__cap">{e(CATS[c][lang])}</span></a></li>')
    return f'''<div class="menu" id="menu" data-menu role="dialog" aria-modal="true" aria-label="{e(t('menu', lang))}">
<div class="menu__bar">
<button class="icon-btn" type="button" data-menu-close aria-label="{e(t('close', lang))}">{CROSS}</button>
<a class="logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="46" height="18"></a>
</div>
<div class="menu__in">
<nav aria-label="{e(t('nav_cats', lang))}">
<ul class="menu__tabs">{tabs_html}</ul>
<ul class="menu__tiles">{''.join(tiles)}</ul>
</nav>
<nav aria-label="{e(t('f_buyers', lang))}">
<ul class="menu__links">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>
</nav>
<nav class="menu__lang" aria-label="{e(t('nav_lang', lang))}">{langs(lang, suffix)}</nav>
<ul class="menu__social">{social(lang)}</ul>
</div>
</div>'''


# ——— Каркас страницы ———

def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', body_class='', cur=None, view=False):
    lang_cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    # Сохранённый вид сетки (1 колонка) — до первой отрисовки, чтобы сетка не прыгала
    view_js = ("<script>try{if(localStorage.getItem('attre-v3-cols')==='1')"
               "document.documentElement.classList.add('v-big')}catch(x){}</script>") if view else ''
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
{view_js}
</head>
<body class="{body_class}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<header class="hdr">
<button class="icon-btn hdr__burger" type="button" aria-controls="menu" aria-expanded="false" data-menu-open><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
<a class="logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="46" height="18"></a>
<a class="icon-btn hdr__wa" href="{wa}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</header>
{menu(lang, suffix, cur)}
<main id="main" tabindex="-1">
{body}
</main>
{footer(lang, suffix)}
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="document.documentElement.classList.remove('js')"></script>
<script src="{asset('assets/js/v3.js')}?v={VER}" defer onerror="document.documentElement.classList.remove('js')"></script>
</body>
</html>
'''


def facc(title, inner):
    return f'<details class="facc"><summary>{e(title)}{CHEV_DOWN}</summary><div class="facc__body">{inner}</div></details>'


def footer(lang, suffix):
    info = url(f'{lang}/info/')
    buyers = f'''<ul class="facc__list">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>'''
    contacts = f'''<ul class="facc__list">{social(lang)}
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
</ul>'''
    store = f'''<ul class="facc__list">
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
<li><span class="facc__note">{e(t('hours', lang))}</span></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>'''
    legal = f'''<div class="facc__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
<p><a href="{info}#seller">{e(t('seller_title', lang))}</a></p>
</div>'''
    proto = f'<p class="ftr__proto">{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<div class="ftr__accs">
{facc(t('f_buyers', lang), buyers)}
{facc(t('f_contacts', lang), contacts)}
{facc(tx('store', lang), store)}
{facc(tx('legal', lang), legal)}
</div>
<div class="ftr__loc"><span>{e(tx('country', lang))}</span><span class="ftr__dot" aria-hidden="true">·</span><nav class="ftr__langs" aria-label="{e(t('nav_lang', lang))}">{langs(lang, suffix)}</nav></div>
<a class="ftr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black-xl.png')}" alt="attré" width="200" height="77" loading="lazy" decoding="async"></a>
{proto}
</footer>'''


# ——— Каталог ———

def card(p, lang, first=False, h='h2'):
    stem = p['images'][0]
    if first:   # первый ряд — без проявления и с высоким приоритетом: это самое заметное фото страницы
        attrs = f'sizes="{SIZES_CARD}" loading="eager" fetchpriority="high"'
    else:
        attrs = f'class="fade" sizes="auto, {SIZES_CARD}" loading="lazy"'
    tag = (f'<p class="tag">{e(t("sold", lang))}</p>' if sold(p)
           else f'<p class="tag tag--last">{e(t("last", lang))}</p>' if p['stock'] == 1 else '')
    return f'''<li class="card{' card--sold' if sold(p) else ''}"><a href="{item_url(p, lang)}">
<div class="card__media"><img {attrs} src="{asset(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" width="600" height="800" alt="" decoding="async"></div>
<div class="card__body">{tag}<{h} class="card__name">{e(p['name'][lang])}</{h}><p class="card__price">{e(price_text(p, lang))}</p></div>
</a></li>'''


def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    opts = [(None, t('all_items', lang), url(lang + '/catalog/'), len(DATA['products']))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/'), sum(1 for p in DATA['products'] if p['cat'] == c))
        for c in present_cats()]
    flist = ''.join(
        f'<li><a href="{href}"{CUR if c == cat else ""}><span>{e(label)}</span><span class="flist__n num">{n}</span></a></li>'
        for c, label, href, n in opts)
    filt = sheet('sh-filter', tx('filters', lang),
                 f'<nav aria-label="{e(t("nav_cats", lang))}"><ul class="flist">{flist}</ul></nav>', lang, ' sheet--filter')
    cards = ''.join(card(p, lang, first=i < 2) for i, p in enumerate(items))
    body = f'''<div class="plp">
<h1 class="plp__title">{e(heading)}</h1>
<div class="plp__bar">
{opener('sh-filter', e(tx('filters', lang)), 'plp__btn')}
<button class="plp__btn" type="button" data-view>{e(tx('view', lang))}{NBSP}<span data-view-n>2</span><span class="sr-only">{e(tx('view_hint', lang))}</span></button>
</div>
{filt}
<ul class="grid grid--cat">
{cards}
</ul>
{'' if items else f'<p class="plp__empty">{e(t("empty", lang))}</p>'}
</div>'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), body_class='is-plp',
                  cur=(cat or 'all', True), view=True)


# ——— Товар ———

def product(p, lang):
    name = p['name'][lang]
    info = url(f'{lang}/info/')
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    n = len(p['images'])
    figs = []
    for i, stem in enumerate(p['images']):
        kind = '1' if i == 0 else '2' if i == 1 else 'n'
        alt = e(name) + (' — ' + e(t('photo_n', lang, i=i + 1, n=n)) if i else '')
        load = 'loading="eager" fetchpriority="high"' if i == 0 else 'class="fade" loading="lazy"'
        figs.append(f'<figure class="pdp__ph pdp__ph--{kind}"><img {load} src="{asset(f"assets/img/p/{stem}-1200.webp")}" '
                    f'srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 33vw, 100vw" width="1200" height="1600" '
                    f'alt="{alt}" decoding="async"></figure>')

    todo = f'<span class="todo">{e(t("todo", lang))}</span>'
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
        status = f'<p class="tag">{e(t("sold", lang))}</p>'
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        label = t('wa_btn', lang)
        status = f'<p class="tag tag--last">{e(t("last", lang))}</p>' if p['stock'] == 1 else ''
    wa_general = e(wa_link(t('wa_general', lang)))

    ref = ' | '.join(x for x in (p['color'][lang], f"{tx('ref', lang)} {p['id']}") if x)
    desc = f'<p class="pdp__desc">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    typ = f'<p class="pdp__type">{e(p["type"][lang])}</p>' if p['type'][lang] else ''

    s_spec = sheet('sh-spec', t('acc_details', lang), f'<dl class="spec">{spec}</dl>', lang)
    s_delivery = sheet('sh-delivery', tx('sh_delivery', lang), f'''<h3 class="sheet__h">{e(t('delivery_title', lang))}</h3>
<p>{e(t('delivery_body', lang))}</p>
<p>{e(t('payment_body', lang))}</p>
<h3 class="sheet__h">{e(t('returns_title', lang))}</h3>
<p>{e(t('returns_body', lang))}</p>
<ul class="sheet__links"><li><a href="{info}#delivery">{e(tx('more', lang))}</a></li></ul>''', lang)
    s_store = sheet('sh-store', t('acc_store', lang), f'''<p>{e(t('store_body', lang))}</p>
<p>{e(t('hours', lang))}</p>
<ul class="sheet__links">
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
<li><a href="{wa_general}" target="_blank" rel="noopener">{e(t('wa_label', lang))}</a></li>
</ul>''', lang)

    body = f'''<article class="pdp">
<div class="pdp__panel">
<div class="pdp__bar">
<div class="pdp__title"><h1 class="pdp__name">{e(name)}</h1><p class="pdp__price num">{e(price_text(p, lang))}</p></div>
<a class="btn" href="{e(wa_link(msg))}" target="_blank" rel="noopener">{e(label)}</a>
</div>
<div class="pdp__head">
{status}
<p class="pdp__ref">{e(ref)}</p>
{typ}
{desc}
<a class="pdp__bonus" href="{info}#bonus"><span class="u">{e(t('bonus_short', lang))}</span> — {e(t('bonus_hint', lang))}</a>
</div>
<div class="pdp__rows">
{opener('sh-spec', e(t('acc_details', lang)) + CHEV, 'row')}
{opener('sh-delivery', e(tx('sh_delivery', lang)) + CHEV, 'row')}
{opener('sh-store', e(t('acc_store', lang)) + CHEV, 'row')}
{s_spec}
{s_delivery}
{s_store}
</div>
</div>
<div class="pdp__gallery">
{''.join(figs)}
</div>
</article>
<section class="more" aria-labelledby="more-t">
<h2 class="sec-title" id="more-t">{e(tx('may_like', lang))}</h2>
<ul class="grid">{''.join(card(q, lang, h='h3') for q in similar(p))}</ul>
</section>'''
    meta = meta_line(p, lang)
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product',
                  body_class='is-pdp', cur=(p['cat'], False))


# ——— Главная: стек портретных фото встык ———

def home(lang):
    cover = HOME['cover']
    w = 1125 if 1125 in cover['_widths'] else cover['_widths'][-1]
    s1, s2 = t('slogan_1', lang), t('slogan_2', lang)
    # Слоган английский на всех языках — помечаем, чтобы экранный диктор читал его по-английски
    s_lang = ' lang="en"' if lang != 'en' and s1 == t('slogan_1', 'en') else ''
    h_cls, h_shade = tone(OUT_ROOT / 'assets' / 'img' / 'home' / f"{cover['_stem']}-{cover['_widths'][0]}.webp")
    hero = f'''<a class="hero{h_cls}" href="{url(lang + '/catalog/')}" style="--shade:{h_shade}">
<img src="{asset(f"assets/img/home/{cover['_stem']}-{w}.webp")}" srcset="{home_srcset(cover)}" sizes="(min-width: 960px) 50vw, 100vw" width="{w}" height="{round(w / cover['_ratio'])}" alt="{e(tri(cover.get('alt'))[lang])}" fetchpriority="high" decoding="async">
<span class="hero__cap"><span{s_lang}>{e(s1)} {e(s2)}</span><span class="sr-only"> — {e(t('all_items', lang))}</span></span>
</a>'''
    # Плитки: баннеры главной, затем категории, на которые не ведёт ни один баннер (фото первой вещи)
    tiles = []
    for b in HOME['banners']:
        bw = b['_widths'][0]
        tiles.append({'href': url(lang + '/' + b['link']), 'cap': tri(b['label'])[lang], 'half': False,
                      'file': OUT_ROOT / 'assets' / 'img' / 'home' / f"{b['_stem']}-{bw}.webp",
                      'src': asset(f"assets/img/home/{b['_stem']}-{bw}.webp"), 'srcset': home_srcset(b),
                      'w': bw, 'h': round(bw / b['_ratio']), 'alt': tri(b.get('alt'))[lang]})
    linked = {b['link'].strip('/').split('/')[-1] for b in HOME['banners'] if b['link'].startswith('c/')}
    for c in present_cats():
        stem = lead_stem(c)
        if c in linked or not stem:
            continue
        tiles.append({'href': url(f'{lang}/c/{c}/'), 'cap': CATS[c][lang], 'half': True,
                      'file': OUT_ROOT / 'assets' / 'img' / 'p' / f'{stem}-600.webp',
                      'src': asset(f'assets/img/p/{stem}-600.webp'), 'srcset': img_srcset(stem),
                      'w': 600, 'h': 800, 'alt': ''})
    # Последняя плитка растягивается на всю ширину, если в ряду ей не хватает пары:
    # телефон — пары только у категорий; планшет — обложка отдельно, плитки по две;
    # компьютер — обложка в паре с первой плиткой.
    if tiles:
        last = tiles[-1]
        last['mod'] = ''.join([
            ' tile--wm' if last['half'] and sum(x['half'] for x in tiles) % 2 else '',
            ' tile--wt' if len(tiles) % 2 else '',
            ' tile--wd' if (len(tiles) + 1) % 2 else ''])

    def tile(x):
        mod = x.get('mod', '')
        phone_w = '100vw' if not x['half'] or 'tile--wm' in mod else '50vw'
        sizes = (f"(min-width: 960px) {'100vw' if 'tile--wd' in mod else '50vw'}, "
                 f"(min-width: 600px) {'100vw' if 'tile--wt' in mod else '50vw'}, {phone_w}")
        cls, shade = tone(x['file'])
        return f'''<a class="tile{' tile--half' if x['half'] else ''}{mod}{cls}" href="{x['href']}" style="--shade:{shade}">
<img class="fade" src="{x['src']}" srcset="{x['srcset']}" sizes="{sizes}" width="{x['w']}" height="{x['h']}" alt="{e(x['alt'])}" loading="lazy" decoding="async">
<span class="tile__cap">{e(x['cap'])}</span>
</a>'''

    full = ''.join(tile(x) for x in tiles if not x['half'])
    halves = [tile(x) for x in tiles if x['half']]
    pair = f'<div class="stack__pair">{"".join(halves)}</div>' if halves else ''
    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
<div class="stack">
{hero}
{full}
{pair}
</div>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), body_class='is-home')


# ——— Покупателям ———

def info(lang):
    nav = [('bonus', tx('n_bonus', lang)), ('about', t('f_about', lang)), ('delivery', t('acc_delivery', lang)),
           ('returns', tx('n_returns', lang)), ('contacts', t('f_contacts', lang)), ('seller', tx('n_seller', lang))]
    nav_html = ''.join(f'<li><a href="#{k}">{e(label)}</a></li>' for k, label in nav)
    wa = e(wa_link(t('wa_general', lang)))

    def sec(key, title, inner):
        return (f'<section class="info__sec" id="{key}" aria-labelledby="{key}-t">'
                f'<h2 id="{key}-t">{e(title)}</h2>{inner}</section>')

    body = f'''<div class="info">
<h1 class="info__title">{e(t('info_title', lang))}</h1>
<nav class="info__nav" aria-label="{e(tx('sections', lang))}"><ul>{nav_html}</ul></nav>
{sec('bonus', t('bonus_title', lang), f"<p>{e(t('bonus_body', lang))}</p><p class='note'>{e(t('bonus_terms', lang))}</p>")}
{sec('about', t('about_title', lang), f"<p>{e(t('about_body', lang))}</p>")}
{sec('delivery', t('delivery_title', lang), f"<p>{e(t('delivery_body', lang))}</p><p>{e(t('payment_body', lang))}</p>")}
{sec('returns', t('returns_title', lang), f"<p>{e(t('returns_body', lang))}</p>")}
{sec('contacts', t('contacts_title', lang), f'''<p>{e(t('address', lang))}<br>{e(t('hours', lang))}</p>
<ul class="info__links">
<li><a href="{wa}" target="_blank" rel="noopener">WhatsApp <span class="num">{phone()}</span></a></li>
<li><a href="https://www.instagram.com/{e(DATA['instagram'])}/" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>''')}
{sec('seller', t('seller_title', lang), f"<p>{e(t('f_seller', lang))}</p><p>{e(t('f_prices', lang))}</p><p>{e(t('f_consumer', lang))}</p>")}
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), body_class='is-info')
