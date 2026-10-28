"""Вариант 5 — «Лента»: чистота Antihero × привычки Instagram (Reels, сетка профиля, сторис).

Шапка 52px: логотип слева, WhatsApp и бургер справа; меню — белая панель под шапкой, страница под ней
затемняется (как у Antihero). Чёрная полоса бонуса (Ushatava). Onest 400, мелкий капс с небольшой разрядкой.

Главная — лента: обложка на весь экран, дальше одна вещь на экран. Фото 3:4 во всю ширину без обрезки
(предметную съёмку нельзя резать до 9:16 — теряются края сумки, а подпись ложится на саму вещь),
под фото — продолжение фона кадра: однотонный светлый низ кадра тянется до края экрана, подпись стоит
на нём по центру. Активный экран «оживает»: фото медленно отъезжает (6 с), подпись проявляется,
а фото вещи сменяют друг друга, как сторис (только пока экран на виду; полоски под фото — как точки
карусели Instagram). В конце ленты — сетка 3 × 3 и ссылка на все товары.

Каталог — профиль Instagram: кружки-хайлайты категорий, переключатель «3 / 2» (Massimo Dutti), сетка
квадратов встык с зазором 2px или 2 колонки 3:4 с подписями; плитки проявляются по очереди.
Товар — галерея 4:5 со «сторис»-полоской сверху, тап по левой/правой половине листает; сведения по центру
мелким капсом, чёрная кнопка WhatsApp, вкладки «характеристики / доставка / возврат», похожие сеткой 3 × 1:1.

Движение — только transform и opacity, всё внутри prefers-reduced-motion: no-preference; скрытые
состояния — только при html.js. Без JS всё видно: меню стоит списком под шапкой, вкладки идут разделами.
Цвета продолжения фона и точки обрезки квадратов считаются при сборке по уже нарезанным фото (Pillow);
нет Pillow или фото — белый фон и обрезка по центру.
"""
import json

from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v5.css'
VER = asset_version('src/css/v5.css', 'src/js/site.js', 'src/js/v5.js')

# Тексты, которых нет в data/i18n.json
TEXTS = {
    'skip': {'ru': 'Перейти к содержанию', 'kz': 'Негізгі мазмұнға өту', 'en': 'Skip to content'},
    'feed': {'ru': 'Лента', 'kz': 'Таспа', 'en': 'Feed'},
    'photos': {'ru': '{name} — фото', 'kz': '{name} фотолары', 'en': '{name} — photos'},
    'prev': {'ru': 'Предыдущее фото', 'kz': 'Алдыңғы фото', 'en': 'Previous photo'},
    'next': {'ru': 'Следующее фото', 'kz': 'Келесі фото', 'en': 'Next photo'},
    'about_item': {'ru': 'О товаре', 'kz': 'Тауар туралы', 'en': 'About this item'},
    'tab_returns': {'ru': 'возврат', 'kz': 'қайтару', 'en': 'returns'},
    'view': {'ru': 'Вид сетки', 'kz': 'Тор көрінісі', 'en': 'Grid view'},
    'cols3': {'ru': '3 в ряд', 'kz': 'Бір қатарда 3', 'en': '3 per row'},
    'cols2': {'ru': '2 в ряд', 'kz': 'Бір қатарда 2', 'en': '2 per row'},
    'more': {'ru': 'ещё в каталоге', 'kz': 'каталогта тағы', 'en': 'more in the catalogue'},
    'sections': {'ru': 'Разделы', 'kz': 'Бөлімдер', 'en': 'Sections'},
    'n_bonus': {'ru': 'бонус', 'kz': 'бонус', 'en': 'bonus'},
    'n_returns': {'ru': 'возврат', 'kz': 'қайтару', 'en': 'returns'},
    'n_seller': {'ru': 'продавец', 'kz': 'сатушы', 'en': 'seller'},
}


def tx(key, lang, **kw):
    s = TEXTS[key][lang]
    for k, v in kw.items():
        s = s.replace('{' + k + '}', str(v))
    return s


FEED_N = 10     # вещей в ленте главной
MORE_N = 9      # плиток в сетке под лентой
SIM_N = 6       # похожих на странице товара (две строки по три)
SIZES_TILE = '(min-width: 960px) 470px, 50vw'      # в режиме 3 колонок хватает 600w; 2 колонки — тоже
SIZES_REEL = '(min-width: 960px) 600px, (min-width: 600px) 560px, 100vw'
SIZES_PDP = '(min-width: 960px) 560px, 100vw'

# Свои значки (рисованы здесь): сетки 3 × 3 и 2 × 2 для переключателя вида, тонкая стрелка галереи
ICON_3 = ('<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">'
          '<path d="M0 0h4.5v4.5H0zM5.75 0h4.5v4.5h-4.5zM11.5 0H16v4.5h-4.5zM0 5.75h4.5v4.5H0zM5.75 5.75h4.5v4.5h-4.5z'
          'M11.5 5.75H16v4.5h-4.5zM0 11.5h4.5V16H0zM5.75 11.5h4.5V16h-4.5zM11.5 11.5H16V16h-4.5z"/></svg>')
ICON_2 = ('<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">'
          '<path d="M0 0h7.25v9H0zM8.75 0H16v9H8.75zM0 10.5h7.25V16H0zM8.75 10.5H16V16H8.75z"/></svg>')
CHEV = ('<svg viewBox="0 0 8 14" fill="none" stroke="currentColor" stroke-width="1.2" aria-hidden="true">'
        '<path d="M1 1l6 6-6 6"/></svg>')
# Тонкие значки для кружков-хайлайтов страницы «Покупателям» (как хайлайты «Доставка», «Оплата» в профиле магазина)
_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round" aria-hidden="true"><path d="{}"/></svg>'
INFO_ICONS = {
    'bonus': _ICON.format('M4 10.5h16V20H4zM3 7.5h18v3H3zM12 7.5V20M12 7.5c-1-2.6-4.6-3.4-4.6-1.3 0 1.3 2.6 1.3 4.6 1.3zM12 7.5c1-2.6 4.6-3.4 4.6-1.3 0 1.3-2.6 1.3-4.6 1.3z'),
    'delivery': _ICON.format('M4 7.8L12 4l8 3.8v8.4L12 20l-8-3.8zM4 7.8l8 3.8 8-3.8M12 11.6V20'),
    'returns': _ICON.format('M6.2 8.5A7 7 0 1 1 5 12.2M5.6 4.4v4.3h4.3'),
    'contacts': _ICON.format('M12 20.5s-6-5.4-6-10a6 6 0 0 1 12 0c0 4.6-6 10-6 10zM12 12.6a2.1 2.1 0 1 0 0-4.2 2.1 2.1 0 0 0 0 4.2z'),
    'seller': _ICON.format('M7 3.5h7.2L18 7.3v13.2H7zM14 3.5v4h4M9.6 12h5.8M9.6 15.4h5.8'),
}


# ——— Анализ фото при сборке (по уже нарезанным файлам site/assets/img) ———

def _lum(c):
    """Относительная яркость цвета sRGB (0–255 на канал)."""
    out = 0
    for v, k in zip(c, (.2126, .7152, .0722)):
        v = v / 255
        out += k * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
    return out


_STATS = {}


def photo_stats(stem):
    """bg — продолжение фона под фото в ленте: однотонный светлый низ кадра → градиент по трём участкам
    низа (слева, в центре, справа), иначе '' (белый). pos — object-position для квадрата из кадра 3:4:
    на однотонном фоне — по рамке предмета, чтобы сумка не обрезалась снизу; иначе по центру."""
    if stem in _STATS:
        return _STATS[stem]
    res = {'bg': '', 'pos': '50% 50%'}
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageStat
        with Image.open(OUT_ROOT / 'assets' / 'img' / 'p' / f'{stem}-600.webp') as src:
            im = src.convert('RGB')
        w, h = im.size
        s = max(6, round(h * .03))
        bottom = im.crop((0, h - s, w, h))
        parts = [ImageStat.Stat(bottom.crop((round(w * k / 3), 0, round(w * (k + 1) / 3), s))) for k in range(3)]
        means = [tuple(round(c) for c in x.mean) for x in parts]
        flat = max(ImageStat.Stat(bottom).stddev) < 9 and all(max(x.stddev) < 6 for x in parts)
        if flat and all(_lum(m) > .7 for m in means):
            res['bg'] = 'linear-gradient(90deg,' + ','.join('#%02x%02x%02x' % m for m in means) + ')'
        top = ImageStat.Stat(im.crop((0, 0, w, s)))
        if max(top.stddev) < 9:
            ground = Image.new('RGB', im.size, tuple(round(c) for c in top.mean))
            mask = ImageChops.difference(im, ground).convert('L').point(lambda v: 255 if v > 28 else 0)
            box = mask.filter(ImageFilter.MinFilter(5)).getbbox()
            if box and h > w:
                cy = (box[1] + box[3]) / 2
                off = min(max(cy - w / 2, 0), h - w)
                res['pos'] = f'50% {round(off / (h - w) * 100)}%'
    except Exception:  # noqa: BLE001 — нет Pillow или файла: белый фон, обрезка по центру
        pass
    _STATS[stem] = res
    return res


def shade_for(path, box):
    """Непрозрачность затемнения под белой подписью: контраст ≥ 4.6:1 по светлым 10 % пикселей зоны подписи."""
    try:
        from PIL import Image
        with Image.open(path) as src:
            im = src.convert('RGB')
        w, h = im.size
        zone = im.crop((round(w * box[0]), round(h * box[1]), round(w * box[2]), round(h * box[3]))).resize((64, 24))
        px = sorted(zone.getdata(), key=_lum)
        bright = px[len(px) * 9 // 10]
        for a in range(10, 82, 2):
            k = 1 - a / 100
            if 1.05 / (_lum(tuple(v * k for v in bright)) + .05) >= 4.6:
                return a / 100
        return .8
    except Exception:  # noqa: BLE001
        return .6


# ——— Общие кусочки ———

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


def slogan(lang):
    """Слоган английский на всех языках — помечаем, чтобы экранный диктор читал его по-английски."""
    s1, s2 = t('slogan_1', lang), t('slogan_2', lang)
    mark = ' lang="en"' if lang != 'en' and s1 == t('slogan_1', 'en') else ''
    return f'<span{mark}>{e(s1)} {e(s2)}</span>'


def p_img(stem, w):
    return asset(f'assets/img/p/{stem}-{w}.webp')


def tile(p, lang, *, extra='', h='h2', eager=False):
    """Плитка сетки: квадрат без подписи (название — в alt и aria-label ссылки); в режиме «2» — 3:4 с подписью."""
    name = p['name'][lang]
    stem = p['images'][0]
    pos = photo_stats(stem)['pos']
    price = price_text(p, lang)
    note = t('sold', lang) if sold(p) else t('last', lang) if p['stock'] == 1 else ''
    label = ' — '.join(x for x in (name, note or price) if x)
    load = 'loading="eager"' if eager else 'loading="lazy"'
    flag = f'<span class="tile__flag">{e(note)}</span>' if note else ''
    return f'''<li class="tile rv{' tile--sold' if sold(p) else ''}{extra}"><a class="tile__a" href="{item_url(p, lang)}" aria-label="{e(label)}">
<span class="tile__media"><img class="tile__img" src="{p_img(stem, 600)}" srcset="{img_srcset(stem)}" sizes="{SIZES_TILE}" width="600" height="800" alt="{e(name)}" style="object-position:{pos}" {load} decoding="async">{flag}</span>
<div class="tile__cap"><{h} class="tile__name">{e(name)}</{h}><span class="tile__price num">{e(price)}</span></div>
</a></li>'''


# ——— Каркас страницы ———

def menu(lang, suffix, current):
    info = url(f'{lang}/info/')

    def item(href, label, key=''):
        cur = ' aria-current="page"' if key and key == current else ''
        return f'<li><a href="{href}"{cur}>{e(label)}</a></li>'

    cats = ''.join(item(url(f'{lang}/c/{c}/'), CATS[c][lang], f'c/{c}') for c in present_cats())
    return f'''<nav class="menu" id="v5-menu" aria-label="{e(t('menu', lang))}" data-v5-menu>
<ul class="menu__list">
{item(url(lang + '/catalog/'), t('all_items', lang), 'catalog')}
{cats}
</ul>
<ul class="menu__list menu__list--sub">
{item(info + '#bonus', t('bonus_short', lang))}
{item(info + '#delivery', t('f_delivery', lang))}
{item(info + '#returns', t('f_returns', lang))}
{item(info + '#about', t('f_about', lang))}
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
<a class="ftr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="46" height="18" loading="lazy" decoding="async"></a>
<p class="ftr__slogan">{slogan(lang)}</p>
<h2 class="sr-only">{e(t('f_contacts', lang))}</h2>
<ul class="ftr__links">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="num">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a class="lc" href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
</ul>
<h2 class="sr-only">{e(t('f_buyers', lang))}</h2>
<ul class="ftr__links ftr__links--sub">
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#about">{e(t('f_about', lang))}</a></li>
</ul>
{langs(lang, suffix)}
<div class="ftr__legal">
<p>{e(t('f_seller', lang))}</p>
<p>{e(t('f_prices', lang))}</p>
<p>{e(t('f_consumer', lang))}</p>
{proto}
</div>
</footer>'''


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', current='', page='', html_class='', after=''):
    lang_cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    no_js = "document.documentElement.classList.remove('js')"
    cls = f' class="{html_class}"' if html_class else ''
    # html.js — до отрисовки; выбранный вид сетки (2 колонки) — тоже до отрисовки, чтобы сетка не прыгала.
    # Страховка: если за 6 с не запустились site.js и v5.js — снимаем html.js, всё видно без анимаций.
    head_js = ("(function(d){d.classList.add('js');"
               "try{if(localStorage.getItem('attre-v5-cols')==='2')d.classList.add('v5-two')}catch(x){}"
               "setTimeout(function(){if(!(window.__site&&window.__v5))d.classList.remove('js')},6000)})"
               "(document.documentElement)")
    return f'''<!doctype html>
<html lang="{lang_cfg['html']}"{cls}>
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
<script>{head_js}</script>
</head>
<body class="v5-{page}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<div class="top" data-v5-top>
<header class="hdr">
<a class="hdr__logo" href="{url(lang + '/')}" aria-label="{e(t('home', lang))}"><img src="{asset('assets/img/brand/logo-black.png')}" alt="attré" width="51" height="20"></a>
<div class="hdr__end">
<a class="hdr__icon" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
<button class="hdr__icon hdr__burger" type="button" aria-expanded="false" aria-controls="v5-menu" data-v5-menu-btn><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
</div>
</header>
{menu(lang, suffix, current)}
</div>
<div class="shade" data-v5-shade aria-hidden="true"></div>
<main class="main" id="main" tabindex="-1">
{body}
</main>
{footer(lang, suffix)}
{after}
<script src="{asset('assets/js/site.js')}?v={VER}" defer onerror="{no_js}"></script>
<script src="{asset('assets/js/v5.js')}?v={VER}" defer onerror="{no_js}"></script>
</body>
</html>
'''


# ——— Главная: лента ———

def cover_reel(lang):
    cover = HOME['cover']
    w = 1125 if 1125 in cover['_widths'] else cover['_widths'][-1]
    shade = shade_for(OUT_ROOT / 'assets' / 'img' / 'home' / f"{cover['_stem']}-{cover['_widths'][0]}.webp",
                      (.1, .72, .9, .96))
    sides = ''
    # На широком экране обложка встаёт между двумя баннерами — триптих на высоту экрана
    for b in [x for x in HOME['banners'] if x.get('_widths')][:2]:
        bw = b['_widths'][0]
        sides += (f'<div class="reel__ph cover__side"><img class="reel__img" src="{asset(f"assets/img/home/{b["_stem"]}-{bw}.webp")}" '
                  f'srcset="{home_srcset(b)}" sizes="34vw" width="{bw}" height="{round(bw / b["_ratio"])}" alt="" loading="lazy" decoding="async"></div>')
    cat_url = url(lang + '/catalog/')
    return f'''<section class="reel reel--cover" data-reel aria-labelledby="v5-cover-t" style="--shade:{shade}">
<div class="reel__stage"><div class="reel__slide is-cur">
<div class="reel__ph cover__main"><img class="reel__img" src="{asset(f"assets/img/home/{cover['_stem']}-{w}.webp")}" srcset="{home_srcset(cover)}" sizes="(min-width: 960px) 34vw, 100vw" width="{w}" height="{round(w / cover['_ratio'])}" alt="{e(tri(cover.get('alt'))[lang])}" fetchpriority="high" decoding="async"></div>
{sides}
</div></div>
<a class="reel__hit" href="{cat_url}" tabindex="-1" aria-hidden="true"></a>
<div class="reel__cap cover__cap">
<h2 class="cover__slogan" id="v5-cover-t">{slogan(lang)}</h2>
<a class="cover__go" href="{cat_url}">{e(t('cta_catalog', lang))}</a>
</div>
</section>'''


def reel(p, lang, k):
    name = p['name'][lang]
    href = item_url(p, lang)
    stems = p['images']
    first = photo_stats(stems[0])
    more = [[s, photo_stats(s)['bg']] for s in stems[1:]]
    data = (f' data-base="{asset("assets/img/p/")}" data-sizes="{SIZES_REEL}" '
            f'data-more="{e(json.dumps(more, separators=(",", ":")))}"') if more else ''
    plain = '' if first['bg'] else ' reel__slide--plain'
    style = f' style="--bg:{first["bg"]}"' if first['bg'] else ''
    meta = meta_line(p, lang)
    note = f'<p class="reel__note">{e(t("last", lang))}</p>' if p['stock'] == 1 else ''
    dots = (f'<div class="reel__dots" aria-hidden="true">{"<i><b></b></i>" * len(stems)}</div>'
            if len(stems) > 1 else '')
    return f'''<article class="reel" data-reel{data} aria-labelledby="v5-r{k}">
<div class="reel__stage"><div class="reel__slide is-cur{plain}"{style}>
<div class="reel__ph"><img class="reel__img" src="{p_img(stems[0], 1200)}" srcset="{img_srcset(stems[0])}" sizes="{SIZES_REEL}" width="1200" height="1600" alt="{e(name)}" loading="lazy" decoding="async"></div>
</div></div>
<a class="reel__hit" href="{href}" tabindex="-1" aria-hidden="true"></a>
<div class="reel__space"></div>
<div class="reel__cap">
{dots}
<h2 class="reel__name" id="v5-r{k}"><a class="reel__link" href="{href}">{e(name)}</a></h2>
{f'<p class="reel__meta">{e(meta)}</p>' if meta else ''}
<p class="reel__price num">{e(price_text(p, lang))}</p>
{note}
<span class="reel__go" aria-hidden="true">{e(t('cta_look', lang))}</span>
</div>
</article>'''


def home(lang):
    live = [p for p in DATA['products'] if not sold(p)]
    feed = live[:FEED_N]
    rest = [p for p in ordered(DATA['products']) if p not in feed][:MORE_N]
    cat_url = url(lang + '/catalog/')
    reels = ''.join(reel(p, lang, k) for k, p in enumerate(feed))
    grid = ''.join(tile(p, lang, h='h3') for p in rest)
    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
<div class="feed" aria-label="{e(tx('feed', lang))}" role="region">
{cover_reel(lang)}
{reels}
</div>
<section class="more" aria-labelledby="v5-more-t">
<h2 class="sec-h" id="v5-more-t">{e(tx('more', lang))}</h2>
<ul class="grid grid--3">
{grid}
</ul>
<a class="more__all" href="{cat_url}">{e(t('all_items', lang))}<span class="num">{len(DATA['products'])}</span>{CHEV}</a>
</section>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='home', html_class='v5-snap')


# ——— Каталог: профиль Instagram ———

def highlights(lang, cat):
    """Кружки-хайлайты: «все» и категории; в кружке — фото вещи (без повторов между кружками)."""
    used = set()

    def lead(items):
        for p in ordered(items):
            if p['slug'] not in used:
                used.add(p['slug'])
                return p
        return None

    rows = [(None, t('all', lang), url(lang + '/catalog/'), lead(DATA['products']))]
    rows += [(c, CATS[c][lang], url(f'{lang}/c/{c}/'), lead([p for p in DATA['products'] if p['cat'] == c]))
             for c in present_cats()]
    out = []
    for c, label, href, p in rows:
        img = ''
        if p:
            stem = p['images'][0]
            img = (f'<img src="{p_img(stem, 600)}" srcset="{img_srcset(stem)}" sizes="64px" width="600" height="800" '
                   f'alt="" style="object-position:{photo_stats(stem)["pos"]}" decoding="async">')
        cur = ' aria-current="page"' if c == cat else ''
        out.append(f'<li><a class="hl__a" href="{href}"{cur}><span class="hl__ring">{img}</span>'
                   f'<span class="hl__label">{e(label)}</span></a></li>')
    return f'<nav class="hl" aria-label="{e(t("nav_cats", lang))}"><ul class="hl__list">{"".join(out)}</ul></nav>'


def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or p['cat'] == cat])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    tiles = ''.join(tile(p, lang, eager=i < 9) for i, p in enumerate(items))
    grid = (f'<ul class="grid grid--3 grid--cat" id="v5-grid">\n{tiles}\n</ul>' if items
            else f'<p class="empty">{e(t("empty", lang))}</p>')
    view = f'''<div class="vbar js-only" role="group" aria-label="{e(tx('view', lang))}" data-v5-view>
<button class="vbar__b" type="button" data-cols="3" aria-controls="v5-grid" aria-pressed="true">{ICON_3}<span aria-hidden="true">3</span><span class="sr-only">{e(tx('cols3', lang))}</span></button>
<button class="vbar__b" type="button" data-cols="2" aria-controls="v5-grid" aria-pressed="false">{ICON_2}<span aria-hidden="true">2</span><span class="sr-only">{e(tx('cols2', lang))}</span></button>
</div>''' if items else ''
    body = f'''<div class="prof">
<h1 class="prof__t">{e(heading)}</h1>
<p class="prof__n">{e(t('count', lang, n=len(items)))}</p>
{highlights(lang, cat)}
</div>
{view}
{grid}'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'),
                  current=f'c/{cat}' if cat else 'catalog', page='catalog')


# ——— Товар ———

def similar_n(p, n):
    """Как core.similar, но на две строки сетки: та же категория первой, проданные не показываем."""
    others = [q for q in DATA['products'] if q['slug'] != p['slug'] and not sold(q)]
    others.sort(key=lambda q: (q['cat'] != p['cat'], q['order']))
    return others[:n]


def product(p, lang):
    name = p['name'][lang]
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    info = url(f'{lang}/info/')
    n = len(p['images'])
    slides = []
    for i, stem in enumerate(p['images']):
        alt = e(name) + (' — ' + e(t('photo_n', lang, i=i + 1, n=n)) if i else '')
        load = 'fetchpriority="high"' if i == 0 else 'loading="lazy"'
        slides.append(
            f'<div class="pg__slide"><img src="{p_img(stem, 1200)}" srcset="{img_srcset(stem)}" '
            f'sizes="{SIZES_PDP}" width="1200" height="1600" alt="{alt}" style="object-position:{photo_stats(stem)["pos"]}" '
            f'{load} decoding="async"></div>')
    bar = (f'<div class="pg__bar" aria-hidden="true">{"<i><b></b></i>" * n}</div>' if n > 1 else '')
    nav = (f'''<button class="pg__nav pg__nav--prev js-only" type="button" aria-controls="v5-pg" aria-label="{e(tx('prev', lang))}" data-step="-1">{CHEV}</button>
<button class="pg__nav pg__nav--next js-only" type="button" aria-controls="v5-pg" aria-label="{e(tx('next', lang))}" data-step="1">{CHEV}</button>''' if n > 1 else '')

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
        note = t('sold', lang)
    else:
        msg = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url)
        label = t('wa_btn', lang)
        note = t('last', lang) if p['stock'] == 1 else ''
    meta = meta_line(p, lang)
    wa = e(wa_link(msg))

    tabs = [
        ('spec', t('acc_details', lang), t('acc_details', lang), f'<dl class="spec">{spec}</dl>'),
        ('del', t('acc_delivery', lang), t('f_delivery', lang), f'''<p>{e(t('delivery_body', lang))}</p>
<p>{e(t('payment_body', lang))}</p>
<h3 class="tabs__sub">{e(t('store_title', lang))}</h3>
<p>{e(t('store_body', lang))}</p>
<p>{e(t('hours', lang))}</p>
<p><a class="lnk" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></p>'''),
        ('ret', tx('tab_returns', lang), t('acc_returns', lang), f'<p>{e(t("returns_body", lang))}</p>'),
    ]
    tab_btns = ''.join(
        f'<button class="tabs__tab" type="button" role="tab" id="v5-tab-{k}" aria-controls="v5-panel-{k}" '
        f'aria-selected="{"true" if i == 0 else "false"}"{"" if i == 0 else " tabindex=\"-1\""}>{e(short)}</button>'
        for i, (k, short, _, _) in enumerate(tabs))
    panels = ''.join(
        f'''<section class="tabs__panel" id="v5-panel-{k}" aria-labelledby="v5-h-{k}">
<h2 class="tabs__h" id="v5-h-{k}">{e(full)}</h2>
{content}
</section>
''' for k, _, full, content in tabs)

    sim = similar_n(p, SIM_N)
    sim_html = f'''<section class="sim" aria-labelledby="v5-sim-t">
<h2 class="sec-h" id="v5-sim-t">{e(t('similar', lang))}</h2>
<ul class="grid grid--3">{''.join(tile(q, lang, h='h3') for q in sim)}</ul>
</section>''' if sim else ''

    body = f'''<article class="pdp">
<div class="pg" data-v5-pg>
{bar}
<div class="pg__view">
<div class="pg__track" id="v5-pg" tabindex="0" role="region" aria-label="{e(tx('photos', lang, name=name))}">{''.join(slides)}</div>
{nav}
</div>
</div>
<div class="pi">
<a class="pi__cat" href="{url(f"{lang}/c/{p['cat']}/")}">{e(CATS[p['cat']][lang])}</a>
<h1 class="pi__name">{e(name)}</h1>
{f'<p class="pi__meta">{e(meta)}</p>' if meta else ''}
<p class="pi__price num">{e(price_text(p, lang))}</p>
{f'<p class="pi__note">{e(note)}</p>' if note else ''}
<a class="btn" href="{wa}" target="_blank" rel="noopener" data-cta>{WA_ICON}<span>{e(label)}</span></a>
<a class="pi__bonus" href="{info}#bonus"><span><span class="u">{e(t('bonus_short', lang))}</span> — {e(t('bonus_hint', lang))}</span></a>
{f'<p class="pi__desc">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''}
<div class="tabs" data-v5-tabs>
<div class="tabs__list" role="tablist" aria-label="{e(tx('about_item', lang))}">{tab_btns}</div>
{panels}</div>
</div>
</article>
{sim_html}'''
    desc_meta = ' · '.join(x for x in (meta, price_text(p, lang)) if x)
    buybar = f'<div class="buybar" aria-hidden="true"><a class="btn" href="{wa}" target="_blank" rel="noopener" tabindex="-1">{WA_ICON}<span>{e(label)}</span></a></div>'
    return layout(lang, title=f'{name} — attré', desc=desc_meta, body=body, suffix=f"p/{p['slug']}/",
                  og_image=abs_asset(f"assets/img/p/{p['slug']}-og.jpg"), og_type='product',
                  current=f"p/{p['slug']}", page='product', after=buybar)


# ——— Покупателям ———

def info(lang):
    nav = [('bonus', tx('n_bonus', lang)), ('about', t('f_about', lang)), ('delivery', t('acc_delivery', lang)),
           ('returns', tx('n_returns', lang)), ('contacts', t('f_contacts', lang)), ('seller', tx('n_seller', lang))]
    logo = f'<img src="{asset("assets/img/brand/logo-black.png")}" alt="" width="40" height="16" decoding="async">'
    nav_html = ''.join(
        f'<li><a class="hl__a" href="#{k}"><span class="hl__ring hl__ring--{"logo" if k == "about" else "icon"}">'
        f'{logo if k == "about" else INFO_ICONS[k]}</span><span class="hl__label">{e(label)}</span></a></li>'
        for k, label in nav)
    wa = e(wa_link(t('wa_general', lang)))

    def sec(key, title, inner):
        return (f'<section class="info__sec" id="{key}" aria-labelledby="{key}-t">'
                f'<h2 id="{key}-t">{e(title)}</h2>\n{inner}\n</section>')

    body = f'''<div class="info">
<h1 class="info__t">{e(t('info_title', lang))}</h1>
<nav class="hl hl--info" aria-label="{e(tx('sections', lang))}"><ul class="hl__list">{nav_html}</ul></nav>
{sec('bonus', t('bonus_title', lang), f'<p>{e(t("bonus_body", lang))}</p><p class="note">{e(t("bonus_terms", lang))}</p>')}
{sec('about', t('about_title', lang), f'<p>{e(t("about_body", lang))}</p>')}
{sec('delivery', t('delivery_title', lang), f'<p>{e(t("delivery_body", lang))}</p><p>{e(t("payment_body", lang))}</p>')}
{sec('returns', t('returns_title', lang), f'<p>{e(t("returns_body", lang))}</p>')}
{sec('contacts', t('contacts_title', lang), f"""<p>{e(t('address', lang))}<br>{e(t('hours', lang))}</p>
<ul class="info__links">
<li><a href="{wa}" target="_blank" rel="noopener">WhatsApp <span class="num">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>""")}
{sec('seller', t('seller_title', lang), f'<p>{e(t("f_seller", lang))}</p><p>{e(t("f_prices", lang))}</p><p>{e(t("f_consumer", lang))}</p>')}
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), current='info', page='info')
