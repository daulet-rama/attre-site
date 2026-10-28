"""Вариант 6 — «Музей»: смешение референсов в своё решение, главное — мобильная версия.

От massimodutti.com — белое поле, крупные фото, на компьютере сведения о вещи липнут справа;
от ushatava.ru — тихие текстовые ссылки и фильтр словами через « / »; от yourantihero.ru — фото
во всю ширину одно под другим и чёрная кнопка WhatsApp. Своё — музейная подача: голос строчными,
как логотип (Onest 400, без капса и разрядки), шапка «меню · логотип · whatsapp» словами,
у каждой вещи этикетка «№ 001 — altea» (тот же номер, что уходит в сообщение WhatsApp).

Главная — обложка на весь экран и «экспозиция»: 12 вещей по одной, фото 4:5 то у левого края,
то у правого. Каталог — «развеска» в две колонки, правая ниже на 48px. Товар — фото одно под другим,
сведения сразу после первого фото, строки раскрываются плавно, липкая кнопка внизу.

Движение (src/css/v6.css + src/js/v6.js): обложка открывается шторкой слева направо (1.1 s) и медленно
«дышит» (Ken Burns 10 s); фото «оседают» при появлении (opacity, сдвиг 24px, масштаб 1.04 → 1, ~1 s,
один раз); экспонат, у которого задержались, «поворачивается» — показывает второе фото и возвращается;
в Chrome фото экспозиции чуть плывут при прокрутке (animation-timeline: view(), без JS).
Без JS и при prefers-reduced-motion: reduce всё видно и неподвижно.
"""
import re

from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v6.css'
VER = asset_version('src/css/v6.css', 'src/js/site.js', 'src/js/v6.js')

# Тексты, которых нет в data/i18n.json
TEXTS = {
    'skip': {'ru': 'к содержанию', 'kz': 'негізгі мазмұнға өту', 'en': 'skip to content'},
    'no': {'ru': '№', 'kz': '№', 'en': 'no.'},
    'expo': {'ru': 'экспозиция', 'kz': 'экспозиция', 'en': 'on view'},
    'expo_all': {'ru': 'вся экспозиция', 'kz': 'толық экспозиция', 'en': 'the full collection'},
    'in_store': {'ru': 'в магазине', 'kz': 'дүкенде', 'en': 'in store'},
    'more': {'ru': 'подробнее', 'kz': 'толығырақ', 'en': 'learn more'},
    'about_more': {'ru': 'подробнее о магазине', 'kz': 'дүкен туралы толығырақ', 'en': 'more about us'},
    'sections': {'ru': 'разделы', 'kz': 'бөлімдер', 'en': 'sections'},
    'crumbs': {'ru': 'вы здесь', 'kz': 'сіз осындасыз', 'en': 'you are here'},
}

SEP = '<span class="sep" aria-hidden="true">/</span>'
CUR = ' aria-current="page"'
NO_JS = "document.documentElement.classList.remove('js')"
# html.js — до первой отрисовки; если site.js или v6.js не отработали за 6 s, скрытые состояния снимаются
HEAD_JS = ("(function(d){d.classList.add('js');setTimeout(function(){"
           "if(!window.__site||!window.__v6)d.classList.remove('js')},6000)})(document.documentElement)")

SIZES_CARD = '(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw'
SIZES_EX = '(min-width: 960px) 34vw, (min-width: 600px) 66vw, 84vw'
SIZES_PH = '(min-width: 840px) 54vw, 100vw'
EXPO_N = 12


def tx(key, lang):
    return TEXTS[key][lang]


NB_NUM = re.compile(r'(\d) (?=\d{3}(?!\d))')


def nb(s):
    """Неразрывные пробелы: «2 000 ₸» и «№ 1» не рвутся между строками."""
    return NB_NUM.sub('\\1' + NBSP, str(s)).replace(' ₸', NBSP + '₸').replace('№ ', '№' + NBSP)


def te(key, lang, **kw):
    """Текст из data/i18n.json: экранирован, с неразрывными пробелами."""
    return e(nb(t(key, lang, **kw)))


def phone():
    n = str(DATA['whatsapp'])
    if len(n) == 11:  # 7 706 723 23 49
        return NBSP.join(('+' + n[0], n[1:4], n[4:7], n[7:9], n[9:]))
    return '+' + n


def ig_url():
    return f"https://www.instagram.com/{DATA['instagram']}/"


def pieces(n, lang):
    """«48 вещей / 48 зат / 48 pieces»."""
    if lang == 'ru':
        n10, n100 = n % 10, n % 100
        word = ('вещь' if n10 == 1 and n100 != 11 else
                'вещи' if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else 'вещей')
    elif lang == 'kz':
        word = 'зат'
    else:
        word = 'piece' if n == 1 else 'pieces'
    return f'{n}{NBSP}{word}'


def number(p, lang):
    """Инвентарный номер на этикетке — тот же, что уходит в сообщение WhatsApp."""
    return f"{tx('no', lang)}{NBSP}{p['id']}"


def medium(p, lang):
    """Вторая строка этикетки: тип, цвет — как «техника» под названием работы в музее."""
    return ', '.join(x for x in (p['type'][lang], p['color'][lang]) if x)


def slogan_lang(lang):
    # Слоган английский на всех языках — помечаем, чтобы экранный диктор читал его по-английски
    return ' lang="en"' if lang != 'en' and t('slogan_1', lang) == t('slogan_1', 'en') else ''


def langs(lang, suffix, cls=''):
    items = ''.join(
        f'<li>{SEP if i else ""}<a href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a></li>'
        for i, l in enumerate(LANGS))
    return f'<nav class="langs {cls}" aria-label="{te("nav_lang", lang)}"><ul>{items}</ul></nav>'


def logo(lang):
    return (f'<a class="bar__logo" href="{url(lang + "/")}" aria-label="{te("home", lang)}">'
            f'<img src="{asset("assets/img/brand/logo-black.png")}" alt="attré" width="51" height="20"></a>')


def wa_head(lang):
    return (f'<a class="bar__btn bar__btn--r" href="{e(wa_link(t("wa_general", lang)))}" target="_blank" rel="noopener" '
            f'aria-label="{te("wa_label", lang)}">whatsapp</a>')


# ——— Меню: белая панель на весь экран ———

def menu(lang, suffix, cur):
    info = url(f'{lang}/info/')
    cats = present_cats()
    counts = {c: sum(1 for p in DATA['products'] if p['cat'] == c) for c in cats}

    def big(href, label, key, n):
        return (f'<li><a href="{href}"{CUR if key == cur else ""}><span>{e(label)}</span> '
                f'<span class="menu__n num">{n}</span></a></li>')

    rows = [big(url(lang + '/catalog/'), t('all_items', lang), 'catalog', len(DATA['products']))]
    rows += [big(url(f'{lang}/c/{c}/'), CATS[c][lang], f'c/{c}', counts[c]) for c in cats]
    return f'''<div class="menu" id="menu" data-menu role="dialog" aria-modal="true" aria-label="{te('menu', lang)}">
<div class="menu__bar bar">
<button class="bar__btn" type="button" data-menu-close>{te('close', lang)}</button>
{logo(lang)}
{wa_head(lang)}
</div>
<div class="menu__in">
<nav aria-label="{te('nav_cats', lang)}"><ul class="menu__big">{''.join(rows)}</ul></nav>
<nav aria-label="{te('f_buyers', lang)}"><ul class="menu__small">
<li><a href="{info}#bonus">{te('bonus_short', lang)}</a></li>
<li><a href="{info}#delivery">{te('f_delivery', lang)}</a></li>
<li><a href="{info}#returns">{te('f_returns', lang)}</a></li>
<li><a href="{info}#about">{te('f_about', lang)}</a></li>
</ul></nav>
{langs(lang, suffix)}
<ul class="menu__social">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">whatsapp <span class="num nw">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">instagram @{e(DATA['instagram'])}</a></li>
</ul>
</div>
</div>'''


# ——— Каркас страницы ———

def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', page='', cur=None, after=''):
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
<body class="v6-{page}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
<a class="promo" href="{url(lang + '/info/')}#bonus">{te('promo', lang)}</a>
<header class="hdr bar">
<button class="bar__btn" type="button" aria-controls="menu" aria-expanded="false" data-menu-open>{te('menu', lang)}</button>
{logo(lang)}
{wa_head(lang)}
</header>
{menu(lang, suffix, cur)}
<main id="main" tabindex="-1">
{body}
</main>
{footer(lang, suffix)}
{after}
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="{NO_JS}"></script>
<script src="{asset('assets/js/v6.js')}?v={VER}" defer onerror="{NO_JS}"></script>
</body>
</html>
'''


def footer(lang, suffix):
    info = url(f'{lang}/info/')
    cats = ''.join(f'<li><a href="{url(f"{lang}/c/{c}/")}">{e(CATS[c][lang])}</a></li>' for c in present_cats())
    proto = f'<p>{te("f_proto", lang)}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<div class="ftr__cols">
<div class="ftr__col"><h2>{te('dock_catalog', lang)}</h2><ul>
<li><a href="{url(lang + '/catalog/')}">{te('all_items', lang)}</a></li>
{cats}
</ul></div>
<div class="ftr__col"><h2>{te('f_buyers', lang)}</h2><ul>
<li><a href="{info}#bonus">{te('bonus_short', lang)}</a></li>
<li><a href="{info}#delivery">{te('f_delivery', lang)}</a></li>
<li><a href="{info}#returns">{te('f_returns', lang)}</a></li>
<li><a href="{info}#about">{te('f_about', lang)}</a></li>
<li><a href="{info}#seller">{te('seller_title', lang)}</a></li>
</ul></div>
<div class="ftr__col ftr__col--wide"><h2>{te('f_contacts', lang)}</h2><ul>
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">whatsapp <span class="num nw">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{te('address', lang)}</a></li>
</ul></div>
</div>
{langs(lang, suffix, 'ftr__langs')}
<div class="ftr__brand">
<a class="ftr__logo" href="{url(lang + '/')}" aria-label="{te('home', lang)}"><img src="{asset('assets/img/brand/logo-black-xl.png')}" alt="attré" width="1200" height="459" loading="lazy" decoding="async"></a>
<p class="ftr__slogan"{slogan_lang(lang)}>{te('slogan_1', lang)} {te('slogan_2', lang)}</p>
</div>
<div class="ftr__legal tx">
<p>{te('f_seller', lang)}</p>
<p>{te('f_prices', lang)}</p>
<p>{te('f_consumer', lang)}</p>
{proto}
</div>
</footer>'''


# ——— Этикетка и карточки ———

def tag(p, lang):
    if sold(p):
        return f'<p class="tag tag--sold">{te("sold", lang)}</p>'
    if p['stock'] == 1:
        return f'<p class="tag tag--last">{te("last", lang)}</p>'
    return ''


def label(p, lang, h):
    med = medium(p, lang)
    return (f'<div class="lbl"><{h} class="lbl__t"><span class="lbl__no num">{e(number(p, lang))} —</span> {e(p["name"][lang])}</{h}>'
            + (f'<p class="lbl__m">{e(med)}</p>' if med else '')
            + f'<p class="lbl__p num">{e(price_text(p, lang))}</p>{tag(p, lang)}</div>')


def card(p, lang, *, h='h2', eager=False):
    """Карточка «развески»: фото 3:4, под ним этикетка. Оседает вся карточка (без масштаба фото внутри):
    на первом экране каталога их 4–6, и вместе с фото внутри одновременно двигалось бы вдвое больше."""
    stem = p['images'][0]
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    return f'''<li class="card rv{' card--sold' if sold(p) else ''}"><a class="card__a" href="{item_url(p, lang)}">
<div class="card__frame"><img src="{asset(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" sizes="{SIZES_CARD}" width="600" height="800" alt="" {load} decoding="async"></div>
{label(p, lang, h)}
</a></li>'''


def exhibit(p, lang, i):
    """Экспонат главной: фото 4:5 у левого края (нечётные) или у правого (чётные).
    Второе фото — в data-атрибутах: v6.js подгрузит его, только когда у экспоната задержатся."""
    stem = p['images'][0]
    alt = ''
    if len(p['images']) > 1:
        s2 = p['images'][1]
        alt = f' data-alt-src="{asset(f"assets/img/p/{s2}-600.webp")}" data-alt-srcset="{img_srcset(s2)}"'
    side = 'l' if i % 2 == 0 else 'r'
    return f'''<li class="ex ex--{side} rv"><a class="ex__a" href="{item_url(p, lang)}">
<div class="ex__frame"{alt}><div class="ex__pic"><img class="rv__img" src="{asset(f'assets/img/p/{stem}-600.webp')}" srcset="{img_srcset(stem)}" sizes="{SIZES_EX}" width="600" height="800" alt="" loading="lazy" decoding="async"></div></div>
{label(p, lang, 'h3')}
</a></li>'''


# ——— Каталог ———

def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    opts = [(None, t('all', lang), url(lang + '/catalog/'))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/')) for c in present_cats()]
    # разделитель — после слова: при переносе строка начинается со слова, а не с « / »
    filt = ''.join(f'<li><a href="{href}"{CUR if c == cat else ""}>{e(lab)}</a>{SEP if i < len(opts) - 1 else ""}</li>'
                   for i, (c, lab, href) in enumerate(opts))
    cards = ''.join(card(p, lang, eager=i < 2) for i, p in enumerate(items))
    grid = f'<ul class="hang">\n{cards}\n</ul>' if items else f'<p class="empty tx">{te("empty", lang)}</p>'
    body = f'''<div class="plp">
<div class="plp__head">
<h1 class="plp__t">{e(heading)} <span class="plp__n num">{len(items)}</span></h1>
<nav class="filt" aria-label="{te('nav_cats', lang)}"><ul>{filt}</ul></nav>
</div>
{grid}
</div>'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='catalog',
                  cur=f'c/{cat}' if cat else 'catalog')


# ——— Товар ———

def acc(title, inner):
    return (f'<details class="acc"><summary><span>{e(title)}</span><span class="acc__i" aria-hidden="true"></span></summary>'
            f'<div class="acc__b">{inner}</div></details>')


def product(p, lang):
    name = p['name'][lang]
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    info = url(f'{lang}/info/')
    n = len(p['images'])

    def photo(i, stem):
        alt = e(name) + (' — ' + te('photo_n', lang, i=i + 1, n=n) if n > 1 else '')
        load = 'loading="eager" fetchpriority="high"' if i == 0 else 'loading="lazy"'
        return (f'<figure class="ph rv"><div class="ph__frame"><img class="rv__img" src="{asset(f"assets/img/p/{stem}-1200.webp")}" '
                f'srcset="{img_srcset(stem)}" sizes="{SIZES_PH}" width="1200" height="1600" alt="{alt}" {load} decoding="async"></div></figure>')

    photos = [photo(i, stem) for i, stem in enumerate(p['images'])]

    todo = f'<em class="todo">{te("todo", lang)}</em>'
    size = (f'<span class="num">{te("p_size_fmt", lang, w=p["size"][0], h=p["size"][1], d=p["size"][2])}</span>'
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
        btn_label = t('wa_btn_sold', lang)
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        btn_label = t('wa_btn', lang)
    wa = e(wa_link(msg))
    med = medium(p, lang)
    desc = f'<p class="pi__d tx">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    accs = ''.join((
        acc(t('acc_details', lang), f'<dl class="spec">{spec}</dl>'),
        acc(t('f_delivery', lang), f'<p class="tx">{te("delivery_body", lang)}</p>'
                                   f'<p class="tx">{te("payment_body", lang)}</p>'
                                   f'<a class="lnk" href="{info}#delivery">{e(tx("more", lang))}</a>'),
        acc(t('acc_returns', lang), f'<p class="tx">{te("returns_body", lang)}</p>'),
        acc(tx('in_store', lang), f'<p class="tx">{te("store_body", lang)}</p><p>{te("hours", lang)}</p>'
                                  f'<a class="lnk" href="{e(DATA["map_url"])}" target="_blank" rel="noopener">{te("map", lang)}</a>'),
    ))
    sim = similar(p)
    sim_html = f'''<section class="sim" aria-labelledby="sim-t">
<h2 class="sec-t" id="sim-t">{te('similar', lang)}</h2>
<ul class="hang">{''.join(card(q, lang, h='h3') for q in sim)}</ul>
</section>''' if sim else ''

    body = f'''<article class="pdp" style="--n:{n}">
{photos[0]}
<div class="pi">
<nav class="crumb" aria-label="{e(tx('crumbs', lang))}"><ul>
<li><a href="{url(lang + '/catalog/')}">{te('all_items', lang)}</a>{SEP}</li>
<li><a href="{url(f"{lang}/c/{p['cat']}/")}">{e(CATS[p['cat']][lang])}</a></li>
</ul></nav>
<h1 class="pi__t"><span class="pi__no num">{e(number(p, lang))} —</span> {e(name)}</h1>
{f'<p class="pi__m">{e(med)}</p>' if med else ''}
<p class="pi__p num">{e(price_text(p, lang))}</p>
{tag(p, lang)}
<a class="btn" href="{wa}" target="_blank" rel="noopener" data-cta>{WA_ICON}<span>{e(btn_label)}</span></a>
<a class="pi__bonus" href="{info}#bonus"><span class="u">{te('bonus_short', lang)}</span> — {te('bonus_hint', lang)}</a>
{desc}
<div class="accs">{accs}</div>
</div>
{''.join(photos[1:])}
</article>
{sim_html}'''
    meta = meta_line(p, lang)
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    bar = f'<div class="buybar"><a class="btn" href="{wa}" target="_blank" rel="noopener">{WA_ICON}<span>{e(btn_label)}</span></a></div>'
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product',
                  page='product', after=bar)


# ——— Главная ———

def home(lang):
    cover = HOME['cover']
    cat_url = url(lang + '/catalog/')
    w = 1125 if 1125 in cover['_widths'] else cover['_widths'][-1]
    s_lang = slogan_lang(lang)
    cover_html = f'''<a class="cover" href="{cat_url}" data-cover>
<div class="cover__frame"><img class="cover__img" src="{asset(f"assets/img/home/{cover['_stem']}-{w}.webp")}" srcset="{home_srcset(cover)}" sizes="(min-width: 960px) 40vw, 100vw" width="{w}" height="{round(w / cover['_ratio'])}" alt="{e(tri(cover.get('alt'))[lang])}" fetchpriority="high" decoding="async"></div>
<div class="cover__cap"><p class="cover__slogan"{s_lang}><span>{te('slogan_1', lang)}</span> <span>{te('slogan_2', lang)}</span></p><span class="cover__cta">{te('cta_catalog', lang)}<span aria-hidden="true">{NBSP}→</span></span></div>
</a>'''
    featured = [p for slug in HOME.get('featured', []) for p in DATA['products'] if p['slug'] == slug]
    featured = (featured or [p for p in DATA['products'] if not sold(p)])[:EXPO_N]
    hours = t('hours', lang)
    hours_html = '' if '[' in hours else f'<p>{e(hours)}</p>'
    body = f'''<h1 class="sr-only">{te('site_title', lang)}</h1>
{cover_html}
<section class="expo" aria-labelledby="expo-t">
<div class="expo__head">
<h2 class="sec-t" id="expo-t">{e(tx('expo', lang))}</h2>
<p class="expo__sub">{te('intro_sub', lang)}</p>
</div>
<ul class="expo__list">
{''.join(exhibit(p, lang, i) for i, p in enumerate(featured))}
</ul>
<a class="more" href="{cat_url}"><span class="more__t">{e(tx('expo_all', lang))}</span> <span class="more__n">{pieces(len(DATA['products']), lang)}<span aria-hidden="true">{NBSP}→</span></span></a>
</section>
<section class="about" aria-labelledby="about-t">
<h2 class="sec-t" id="about-t">{te('about_title', lang)}</h2>
<p class="about__body tx">{te('about_body', lang)}</p>
<div class="about__store">
<p class="about__k">{te('store_title', lang)}</p>
<p>{te('address', lang)}</p>
{hours_html}
<p>{te('delivery_world', lang)}</p>
<ul class="about__links">
<li><a class="lnk" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{te('map', lang)}</a></li>
<li><a class="lnk" href="{url(lang + '/info/')}#about">{e(tx('about_more', lang))}</a></li>
</ul>
</div>
</section>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='home')


# ——— Покупателям: путеводитель с номерами залов ———

def info(lang):
    wa = e(wa_link(t('wa_general', lang)))
    secs = [
        ('bonus', t('bonus_title', lang),
         f'<p class="tx">{te("bonus_body", lang)}</p><p class="note tx">{te("bonus_terms", lang)}</p>'),
        ('about', t('about_title', lang), f'<p class="tx">{te("about_body", lang)}</p>'),
        ('delivery', t('delivery_title', lang),
         f'<p class="tx">{te("delivery_body", lang)}</p><p class="tx">{te("payment_body", lang)}</p>'),
        ('returns', t('returns_title', lang), f'<p class="tx">{te("returns_body", lang)}</p>'),
        ('contacts', t('contacts_title', lang), f'''<p>{te('address', lang)}<br>{te('hours', lang)}</p>
<ul class="sec__links">
<li><a href="{wa}" target="_blank" rel="noopener">whatsapp <span class="num nw">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a class="lnk" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{te('map', lang)}</a></li>
</ul>'''),
        ('seller', t('seller_title', lang),
         f'<p class="tx">{te("f_seller", lang)}</p><p class="tx">{te("f_prices", lang)}</p>'
         f'<p class="tx">{te("f_consumer", lang)}</p>'),
    ]
    toc = ''.join(f'<li><a href="#{k}"><span class="no">{i:02d}</span> <span>{e(title)}</span></a></li>'
                  for i, (k, title, _) in enumerate(secs, 1))
    sections = ''.join(
        f'<section class="sec" id="{k}" aria-labelledby="{k}-t"><span class="no" aria-hidden="true">{i:02d}</span>'
        f'<h2 id="{k}-t">{e(title)}</h2>{inner}</section>'
        for i, (k, title, inner) in enumerate(secs, 1))
    body = f'''<div class="info">
<h1 class="info__t">{te('info_title', lang)}</h1>
<nav class="toc" aria-label="{e(tx('sections', lang))}"><ol>{toc}</ol></nav>
<div class="info__body">
{sections}
</div>
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='info', cur='info')
