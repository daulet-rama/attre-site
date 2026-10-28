"""Тема «Вариант 4 — Витрина»: структура Ushatava × лёгкая типографика Massimo Dutti × крупные фото Antihero.

Сайт как тихая витрина. Шапка 44px (бургер · логотип ровно по центру · WhatsApp), чёрная полоса бонуса.
Главная — обложка почти на весь экран, которая медленно «дышит» (Ken Burns), подписи — белые «бирки»
поверх фото, как ярлыки в витрине. Ниже витрина ритмом «одна вещь крупно (4:5) → две рядом (3:4)»;
фото «проявляются» снизу вверх, как поднятая штора, а у вещей с двумя фото второе мягко сменяет первое,
пока карточка на экране. Каталог — липкая панель «раздел · категории» и нижний лист. Товар — свайп-галерея
со счётчиком «1 / 5», сведения лёгкой типографикой, раскрывающиеся строки и липкая панель с кнопкой WhatsApp.
Поведение: src/js/v4.js (site.js подключён ради общего флага, на его разметку тема не опирается).
Без JS всё видно: фото сразу, листы раскрыты на странице, фото товара идут столбиком.
"""
import datetime

from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v4.css'
VER = asset_version('src/css/v4.css', 'src/js/site.js', 'src/js/v4.js')

# Тексты, которых нет в data/i18n.json
TEXTS = {
    'skip': {'ru': 'Перейти к содержимому', 'kz': 'Негізгі мазмұнға өту', 'en': 'Skip to content'},
    'photos': {'ru': 'Фото товара', 'kz': 'Тауар фотолары', 'en': 'Product photos'},
    'prev': {'ru': 'Предыдущее фото', 'kz': 'Алдыңғы фото', 'en': 'Previous photo'},
    'next': {'ru': 'Следующее фото', 'kz': 'Келесі фото', 'en': 'Next photo'},
    'sections': {'ru': 'разделы', 'kz': 'бөлімдер', 'en': 'sections'},
    'store': {'ru': 'магазин', 'kz': 'дүкен', 'en': 'store'},
    'ref': {'ru': 'арт.', 'kz': 'арт.', 'en': 'ref.'},
    'more': {'ru': 'подробнее', 'kz': 'толығырақ', 'en': 'learn more'},
}


def tx(key, lang):
    return TEXTS[key][lang]


# Прозрачный пиксель: второе фото карточки подставляет v4.js, когда карточка рядом с экраном
PIXEL = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
# Свои значки (рисованы здесь): крестик, плюс, шеврон
X_ICON = ('<svg class="ico" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
          '<path d="M1.5 1.5l11 11M12.5 1.5l-11 11"/></svg>')
PLUS = '<span class="plus" aria-hidden="true"></span>'
CHEV = ('<svg class="ico" viewBox="0 0 8 14" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
        '<path d="M1 1l6 6-6 6"/></svg>')
ARROW = '<span class="arr" aria-hidden="true">→</span>'
CUR = ' aria-current="page"'


def phone():
    n = str(DATA['whatsapp'])
    if len(n) == 11:   # 7 706 723 23 49
        return NBSP.join(('+' + n[0], n[1:4], n[4:7], n[7:9], n[9:]))
    return '+' + n


def ig_url():
    return f"https://www.instagram.com/{DATA['instagram']}/"


def langs(lang, suffix, cls):
    links = ''.join(
        f'<a class="lng" href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a>'
        for l in LANGS)
    return f'<nav class="langs {cls}" aria-label="{e(t("nav_lang", lang))}">{links}</nav>'


def cat_rows(lang):
    """(ключ, подпись, адрес, число вещей): «все товары» и категории, где есть вещи."""
    ps = DATA['products']
    return [('all', t('all_items', lang), url(lang + '/catalog/'), len(ps))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/'), sum(1 for p in ps if p['cat'] == c)) for c in present_cats()]


def slogan(lang):
    """Слоган английский на всех языках — помечаем, чтобы экранный диктор читал его по-английски."""
    s1, s2 = t('slogan_1', lang), t('slogan_2', lang)
    s_lang = ' lang="en"' if lang != 'en' and s1 == t('slogan_1', 'en') else ''
    return f'<span{s_lang}>{e(s1)} {e(s2)}</span>'


# ——— Панели: меню и нижние листы ———

def menu(lang, suffix, cur):
    """cur — (ключ раздела, точное совпадение): на странице раздела — aria-current="page", на товаре — "true"."""
    info = url(f'{lang}/info/')
    key, exact = cur or (None, False)
    mark = CUR if exact else ' aria-current="true"'
    cats = ''.join(
        f'<li><a href="{h}"{mark if k == key else ""}><span>{e(label)}</span>'
        f'<span class="cnt" aria-hidden="true">{n}</span></a></li>'
        for k, label, h, n in cat_rows(lang))
    return f'''<div class="menu" id="menu" data-panel aria-label="{e(t('menu', lang))}">
<div class="menu__bar">
<button class="ibtn menu__x" type="button" data-close aria-label="{e(t('close', lang))}">{X_ICON}</button>
<a class="logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="{e(t('home', lang))}" width="46" height="18"></a>
<a class="ibtn menu__wa" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</div>
<nav class="menu__nav" aria-label="{e(t('menu', lang))}">
<ul class="menu__main">{cats}</ul>
<ul class="menu__sub">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>
</nav>
<div class="menu__foot">
{langs(lang, suffix, 'menu__langs')}
<ul class="menu__contacts">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="tnum">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
</ul>
</div>
</div>'''


def sheet(sid, title, inner, lang):
    """Нижний лист. Без JS — обычный блок на своём месте; v4.js переносит его в конец body и делает диалогом."""
    return f'''<section class="sheet" id="{sid}" data-panel data-sheet aria-labelledby="{sid}-t">
<div class="sheet__head"><h2 class="sheet__t" id="{sid}-t">{e(title)}</h2><button class="ibtn sheet__x js-only" type="button" data-close aria-label="{e(t('close', lang))}">{X_ICON}</button></div>
<div class="sheet__body">{inner}</div>
</section>'''


def opener(sid, label, cls):
    return (f'<button class="{cls} js-only" type="button" data-open="{sid}" aria-controls="{sid}" '
            f'aria-expanded="false" aria-haspopup="dialog">{label}</button>')


def acc(title, inner, cls=''):
    """Строка, которая плавно раскрывается (details: без JS раскрывается сама, v4.js добавляет плавность)."""
    return (f'<details class="acc{cls}"><summary><span>{e(title)}</span>{PLUS}</summary>'
            f'<div class="acc__body"><div class="acc__clip"><div class="acc__in">{inner}</div></div></div></details>')


# ——— Каркас страницы ———

def footer(lang, suffix):
    info = url(f'{lang}/info/')
    cats = ''.join(f'<li><a href="{h}">{e(label)}</a></li>' for _, label, h, _ in cat_rows(lang))
    hours = t('hours', lang)
    proto = f'<p>{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<div class="ftr__accs">
{acc(t('dock_catalog', lang), f'<ul class="flist">{cats}</ul>', ' acc--f')}
{acc(t('f_buyers', lang), f"""<ul class="flist">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
<li><a href="{info}#seller">{e(t('seller_title', lang))}</a></li>
</ul>""", ' acc--f')}
{acc(t('f_contacts', lang), f"""<ul class="flist">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="tnum">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
</ul>""", ' acc--f')}
{acc(tx('store', lang), f"""<ul class="flist">
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
<li><span>{e(hours)}</span></li>
<li><span>{e(t('delivery_world', lang))}</span></li>
</ul>""", ' acc--f')}
</div>
<div class="ftr__row">{langs(lang, suffix, 'ftr__langs')}<p class="ftr__copy">© {datetime.date.today().year} attré</p></div>
<div class="ftr__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
{proto}
</div>
<a class="ftr__logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black-xl.png')}" alt="{e(t('home', lang))}" width="1200" height="459" loading="lazy" decoding="async"></a>
</footer>'''


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', page='', cur=None):
    cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    no_js = "document.documentElement.classList.remove('js')"
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
<script>(function(d){{d.classList.add('js');setTimeout(function(){{if(!window.__v4)d.classList.remove('js')}},6000)}})(document.documentElement)</script>
</head>
<body class="{page}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<header class="hdr">
<button class="ibtn hdr__menu js-only" type="button" aria-controls="menu" aria-expanded="false" aria-haspopup="dialog" data-open="menu"><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
<a class="logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="{e(t('home', lang))}" width="46" height="18"></a>
<a class="ibtn hdr__wa" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</header>
<main id="main" tabindex="-1">
{body}
</main>
{footer(lang, suffix)}
{menu(lang, suffix, cur)}
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="{no_js}"></script>
<script src="{asset('assets/js/v4.js')}?v={VER}" defer onerror="{no_js}"></script>
</body>
</html>
'''


# ——— Витрина: «одна вещь крупно → две рядом» ———

def tag(p, lang):
    if sold(p):
        return f'<p class="tag">{e(t("sold", lang))}</p>'
    if p['stock'] == 1:
        return f'<p class="tag tag--last">{e(t("last", lang))}</p>'
    return ''


def card(p, lang, kind, *, h='h2', load='lazy'):
    """kind: 'w' — крупно на всю ширину, 'h' — половина ряда, 'h2' — правая половина (проявляется чуть позже);
    ' r' в конце — на компьютере крупная карточка стоит справа (ряды идут «ёлочкой»)."""
    imgs = p['images']
    one = len(imgs) < 2 or sold(p)   # у проданной вещи второе фото не показываем: она в конце, без «жизни»
    wide = kind.startswith('w')
    if wide:
        sizes = '(min-width: 600px) 50vw, 100vw' if one else '(min-width: 600px) 25vw, 100vw'
    else:
        sizes = '(min-width: 600px) 25vw, 50vw'
    attrs = {'lazy': 'loading="lazy"', 'eager': 'loading="eager"',
             'high': 'loading="eager" fetchpriority="high"'}[load]
    a = imgs[0]
    img_a = (f'<img class="vc__img" src="{asset(f"assets/img/p/{a}-600.webp")}" srcset="{img_srcset(a)}" '
             f'sizes="{sizes}" width="600" height="800" alt="" {attrs} decoding="async">')
    img_b = '' if one else (
        f'<img class="vc__img vc__img--b" src="{PIXEL}" data-src="{asset(f"assets/img/p/{imgs[1]}-600.webp")}" '
        f'data-srcset="{img_srcset(imgs[1])}" sizes="{sizes}" width="600" height="800" alt="" decoding="async">')
    cls = 'vc' + (' vc--w' if wide else '') + (' vc--2' if kind == 'h2' else '') + (' vc--r' if kind.endswith(' r') else '')
    cls += (' vc--one' if one else '') + (' vc--sold' if sold(p) else '')
    live = '' if one else ' data-vc'
    meta = meta_line(p, lang)
    return f'''<li class="{cls}" data-rv{live}><a class="vc__a" href="{item_url(p, lang)}">
<div class="vc__media">{img_a}{img_b}</div>
<div class="vc__cap">{tag(p, lang)}<{h} class="vc__name">{e(p['name'][lang])}</{h}>{f'<p class="vc__meta">{e(meta)}</p>' if meta else ''}<p class="vc__price tnum">{e(price_text(p, lang))}</p></div>
</a></li>'''


def rhythm(n):
    """Ритм витрины: крупно, две рядом, крупно, две рядом… Хвост из двух — просто пара (без дыры в ряду).
    На компьютере каждый второй цикл ставит крупную вещь справа (только у полных циклов)."""
    kinds = []
    for i in range(n):
        c = i % 3
        k = 'w' if c == 0 else 'h' if c == 1 else 'h2'
        if c == 0 and (i // 3) % 2 == 1 and i + 2 < n:
            k += ' r'
        kinds.append(k)
    if n % 3 == 2:
        kinds[-2], kinds[-1] = 'h', 'h2'
    return kinds


def vitrine(items, lang, *, h='h2', first=False):
    """first — витрина вверху страницы: первые фото грузятся сразу, самое первое — с высоким приоритетом."""
    kinds = rhythm(len(items))

    def load(i):
        if not first or i > 2:
            return 'lazy'
        return 'high' if i == 0 else 'eager'

    cards = ''.join(card(p, lang, kinds[i], h=h, load=load(i)) for i, p in enumerate(items))
    return f'<ul class="vit">\n{cards}\n</ul>'


# ——— Каталог ———

def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    key = cat or 'all'
    rows = ''.join(
        f'<li><a href="{h}"{CUR if k == key else ""}><span>{e(label)}</span><span class="cnt" aria-hidden="true">{n}</span></a></li>'
        for k, label, h, n in cat_rows(lang))
    cats_sheet = sheet('sh-cats', t('nav_cats', lang),
                       f'<nav aria-label="{e(t("nav_cats", lang))}"><ul class="slist">{rows}</ul></nav>', lang)
    grid = vitrine(items, lang, first=True) if items else f'<p class="empty">{e(t("empty", lang))}</p>'
    body = f'''<div class="pb">
<h1 class="pb__t">{e(heading)}<sup class="pb__n tnum" aria-hidden="true">{len(items)}</sup></h1>
{opener('sh-cats', f'<span>{e(t("nav_cats", lang))}</span>{PLUS}', 'pb__btn')}
</div>
{cats_sheet}
{grid}'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-cat', cur=(key, True))


# ——— Товар ———

def product(p, lang):
    name = p['name'][lang]
    info = url(f'{lang}/info/')
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    n = len(p['images'])
    slides = []
    for i, stem in enumerate(p['images']):
        alt = e(name) + (' — ' + e(t('photo_n', lang, i=i + 1, n=n)) if i else '')
        # первое — сразу и с высоким приоритетом, второе — сразу (его увидят первым свайпом), остальные — лениво
        load = 'loading="eager" fetchpriority="high"' if i == 0 else 'loading="eager"' if i == 1 else 'loading="lazy"'
        slides.append(f'<figure class="pg__slide"{" data-rv" if i else ""}><img src="{asset(f"assets/img/p/{stem}-1200.webp")}" '
                      f'srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 30vw, 100vw" width="1200" height="1600" '
                      f'alt="{alt}" {load} decoding="async"></figure>')
    nav = '' if n < 2 else f'''<span class="ptag pg__count tnum js-only" aria-hidden="true">1 / {n}</span>
<button class="pg__arr pg__arr--prev js-only" type="button" data-step="-1" aria-label="{e(tx('prev', lang))}">{CHEV}</button>
<button class="pg__arr pg__arr--next js-only" type="button" data-step="1" aria-label="{e(tx('next', lang))}">{CHEV}</button>'''

    todo = f'<span class="todo">{e(t("todo", lang))}</span>'
    size = (f'<span class="tnum">{e(t("p_size_fmt", lang, w=p["size"][0], h=p["size"][1], d=p["size"][2]))}</span>'
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
    wa_general = e(wa_link(t('wa_general', lang)))
    rows = ''.join([
        acc(t('acc_details', lang), spec),
        acc(t('f_delivery', lang), f'<p>{e(t("delivery_body", lang))}</p><p>{e(t("payment_body", lang))}</p>'
                                   f'<p><a class="ulink" href="{info}#delivery">{e(tx("more", lang))}</a></p>'),
        acc(t('acc_returns', lang), f'<p>{e(t("returns_body", lang))}</p>'),
        acc(t('acc_store', lang), f'<p>{e(t("store_body", lang))}</p><p>{e(t("hours", lang))}</p>'
                                  f'<p class="links"><a class="ulink" href="{e(DATA["map_url"])}" target="_blank" rel="noopener">{e(t("map", lang))}</a>'
                                  f'<a class="ulink" href="{wa_general}" target="_blank" rel="noopener">{e(t("wa_label", lang))}</a></p>'),
    ])

    if sold(p):
        msg = t('wa_sold', lang, name=name, id=p['id'], url=page_url)
        label = t('wa_btn_sold', lang)
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        label = t('wa_btn', lang)
    typ, color = p['type'][lang], p['color'][lang]
    desc = f'<p class="pp__desc">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    sim = similar(p)
    sim_html = f'''<section class="sim" aria-labelledby="sim-t">
<div class="sec-h"><h2 class="sec-h__t" id="sim-t">{e(t('similar', lang))}</h2><a class="sec-h__a" href="{url(f"{lang}/c/{p['cat']}/")}">{e(CATS[p['cat']][lang])}{ARROW}</a></div>
{vitrine(sim, lang, h='h3')}
</section>''' if sim else ''
    body = f'''<article class="pp">
<div class="pg" data-pg data-settle>
<div class="pg__track" role="region" aria-label="{e(tx('photos', lang))}">{''.join(slides)}</div>
{nav}
</div>
<div class="pp__side">
<div class="pp__bar">
<div class="pp__head"><h1 class="pp__name">{e(name)}</h1><p class="pp__price tnum">{e(price_text(p, lang))}</p></div>
<a class="btn" href="{e(wa_link(msg))}" target="_blank" rel="noopener">{WA_ICON}<span>{e(label)}</span></a>
</div>
<div class="pp__info">
{tag(p, lang)}
{f'<p class="pp__type">{e(typ)}</p>' if typ else ''}
{f'<p class="pp__color">{e(color)}</p>' if color else ''}
<p class="pp__ref">{e(tx('ref', lang))} <span class="tnum">{e(p['id'])}</span></p>
<a class="pp__bonus" href="{info}#bonus"><span class="u">{e(t('bonus_short', lang))}</span> — {e(t('bonus_hint', lang))}</a>
{desc}
<div class="pp__accs">{rows}</div>
</div>
</div>
</article>
{sim_html}'''
    meta = meta_line(p, lang)
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product', page='p-prod',
                  cur=(p['cat'], False))


# ——— Главная ———

def home(lang):
    cover = HOME['cover']
    w = 1125 if 1125 in cover['_widths'] else cover['_widths'][-1]
    cat_url = url(lang + '/catalog/')
    cover_html = f'''<a class="cover" href="{cat_url}" data-settle>
<span class="cover__media"><img class="cover__img" src="{asset(f"assets/img/home/{cover['_stem']}-{w}.webp")}" srcset="{home_srcset(cover)}" sizes="(min-width: 960px) 25vw, 100vw" width="{w}" height="{round(w / cover['_ratio'])}" alt="{e(tri(cover.get('alt'))[lang])}" fetchpriority="high" decoding="async"></span>
<span class="cover__cap">
<span class="ptag cover__tag">{slogan(lang)}</span>
<span class="ptag cover__tag cover__cta">{e(t('cta_catalog', lang))}{ARROW}</span>
</span>
</a>'''
    banners = ''.join(
        f'''<a class="bn" href="{url(lang + '/' + b['link'])}" data-rv>
<span class="bn__media"><img src="{asset(f"assets/img/home/{b['_stem']}-{b['_widths'][0]}.webp")}" srcset="{home_srcset(b)}" sizes="(min-width: 960px) 25vw, (min-width: 600px) 33vw, 74vw" width="{b['_widths'][0]}" height="{round(b['_widths'][0] / b['_ratio'])}" alt="{e(tri(b.get('alt'))[lang])}" loading="lazy" decoding="async"><span class="ptag bn__tag">{e(tri(b['label'])[lang])}{ARROW}</span></span>
</a>''' for b in HOME['banners'] if b.get('_widths'))
    featured = [p for slug in HOME.get('featured', []) for p in DATA['products'] if p['slug'] == slug]
    featured = (featured or [p for p in DATA['products'] if not sold(p)])[:6]
    hours = t('hours', lang)
    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
<div class="home">
{cover_html}
<section class="shelf" aria-labelledby="shelf-t">
<div class="sec-h"><h2 class="sec-h__t" id="shelf-t">{e(t('instock_title', lang))}</h2><a class="sec-h__a" href="{cat_url}">{e(t('all_catalog', lang))}{ARROW}</a></div>
{vitrine(featured, lang, h='h3')}
</section>
<section class="cats" aria-labelledby="cats-t">
<div class="sec-h"><h2 class="sec-h__t" id="cats-t">{e(t('nav_cats', lang))}</h2></div>
<div class="cats__strip" data-near>{banners}</div>
</section>
<section class="store" aria-labelledby="store-t">
<h2 class="store__t" id="store-t">{e(t('store_title', lang))}</h2>
<p>{e(t('address', lang))}</p>
{'' if '[' in hours else f'<p>{e(hours)}</p>'}
<p class="mute">{e(t('delivery_world', lang))}</p>
<p><a class="ulink" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></p>
</section>
</div>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-home')


# ——— Покупателям ———

def info(lang):
    secs = [('bonus', t('bonus_title', lang)), ('about', t('about_title', lang)), ('delivery', t('delivery_title', lang)),
            ('returns', t('returns_title', lang)), ('contacts', t('contacts_title', lang)), ('seller', t('seller_title', lang))]
    toc = ''.join(f'<li><a href="#{k}"><span>{e(label)}</span></a></li>' for k, label in secs)
    toc_sheet = sheet('sh-toc', tx('sections', lang),
                      f'<nav aria-label="{e(tx("sections", lang))}"><ul class="slist">{toc}</ul></nav>', lang)
    wa = e(wa_link(t('wa_general', lang)))

    def sec(key, title, inner):
        return f'<section class="isec" id="{key}" aria-labelledby="{key}-t"><h2 id="{key}-t">{e(title)}</h2>{inner}</section>'

    body = f'''<div class="pb">
<h1 class="pb__t">{e(t('info_title', lang))}</h1>
{opener('sh-toc', f'<span>{e(tx("sections", lang))}</span>{PLUS}', 'pb__btn')}
</div>
{toc_sheet}
<div class="info">
{sec('bonus', t('bonus_title', lang), f'<p>{e(t("bonus_body", lang))}</p><p class="note">{e(t("bonus_terms", lang))}</p>')}
{sec('about', t('about_title', lang), f'<p>{e(t("about_body", lang))}</p>')}
{sec('delivery', t('delivery_title', lang), f'<p>{e(t("delivery_body", lang))}</p><p>{e(t("payment_body", lang))}</p>')}
{sec('returns', t('returns_title', lang), f'<p>{e(t("returns_body", lang))}</p>')}
{sec('contacts', t('contacts_title', lang), f"""<p>{e(t('address', lang))}<br>{e(t('hours', lang))}</p>
<ul class="ilinks">
<li><a class="ulink" href="{wa}" target="_blank" rel="noopener">WhatsApp <span class="tnum">{phone()}</span></a></li>
<li><a class="ulink" href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a class="ulink" href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a class="ulink" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>""")}
{sec('seller', t('seller_title', lang), f'<p>{e(t("f_seller", lang))}</p><p>{e(t("f_prices", lang))}</p><p>{e(t("f_consumer", lang))}</p>')}
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-info')
