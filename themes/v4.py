"""Тема «Вариант 4 — Витрина»: структура Ushatava × лёгкая типографика Massimo Dutti × крупные фото Antihero.

Сайт как тихая витрина, без анимаций при прокрутке: фото просто стоят на местах. Сверху полоса «дарим 2 000 ₸»
(чёрная; красная — по ссылке ?bar=red, для сравнения), шапка 44px: бургер и лупа поиска · логотип по центру · избранное ·
корзина · WhatsApp. Главная: слайдер из пяти фото с кнопкой «каталог» → новинки → популярное → видео «за кадром» с текстом
о бренде → «нас носят» → магазин. Каталог — ритм «одна вещь крупно → две рядом», категории строкой, фильтр в нижнем
листе (сортировка, материал, цвет, цена). Товар — фото листаются вправо-влево, липкая панель: «в корзину», WhatsApp
и сердечко. Избранное и корзина хранятся в браузере (localStorage); список избранного отправляется в WhatsApp,
корзина оформляется готовым сообщением в WhatsApp — без сервера и без полей с личными данными.
Поведение: src/js/v4.js. Без JS всё видно: ленты листаются пальцем, фото товара — свайпом, листы — блоками на странице.
"""
import datetime
import hashlib
import json

from core import *  # noqa: F401,F403 — данные и помощники ядра
from core import asset_version

CSS = 'v4.css'
VER = asset_version('src/css/v4.css', 'src/js/v4.js')
PRICE_RANGE = (12450, 98000)       # бегунок цены по заказчику; раздвигается, если цены выйдут за края
PRICE_STEP = 50

# Тексты, которых нет в data/i18n.json
TEXTS = {
    'skip': {'ru': 'Перейти к содержимому', 'kz': 'Негізгі мазмұнға өту', 'en': 'Skip to content'},
    'photos': {'ru': 'Фото товара', 'kz': 'Тауар фотолары', 'en': 'Product photos'},
    'hero': {'ru': 'Новые фото attré', 'kz': 'attré жаңа фотолары', 'en': 'New attré photos'},
    'prev': {'ru': 'Назад', 'kz': 'Артқа', 'en': 'Previous'},
    'next': {'ru': 'Вперёд', 'kz': 'Алға', 'en': 'Next'},
    'sections': {'ru': 'разделы', 'kz': 'бөлімдер', 'en': 'sections'},
    'store': {'ru': 'магазин', 'kz': 'дүкен', 'en': 'store'},
    'ref': {'ru': 'арт.', 'kz': 'арт.', 'en': 'ref.'},
    'more': {'ru': 'подробнее', 'kz': 'толығырақ', 'en': 'learn more'},
    'wa_item': {'ru': '— «{name}» (№ {id}) {url}', 'kz': '— «{name}» (№ {id}) {url}', 'en': '— “{name}” (No. {id}) {url}'},
}


def tx(key, lang):
    return TEXTS[key][lang]


# Логотип — вектор (src/img/brand/logo-black.svg, обводка исходника заказчицы: tools/logo_svg.py):
# PNG в шапке высотой 17–19px мылился на компьютерах, особенно при масштабе Windows 125–150 %.
# Свои значки (рисованы здесь): крестик, плюс, минус, шеврон, сердце, сумка корзины, WhatsApp, Instagram и Pinterest
X_ICON = ('<svg class="ico" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
          '<path d="M1.5 1.5l11 11M12.5 1.5l-11 11"/></svg>')
PLUS = '<span class="plus" aria-hidden="true"></span>'
MINUS = '<span class="plus plus--minus" aria-hidden="true"></span>'
ARR_ICON = ('<svg class="ico ico--arr" viewBox="0 0 20 14" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
            '<path d="M1 7h17M12.5 1.5 18 7l-5.5 5.5"/></svg>')   # «красивые стрелки» по просьбе заказчицы
HEART = ('<svg class="heart" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round" aria-hidden="true">'
         '<path d="M12 20.3c-.3 0-7.6-4.5-9.3-9-1.2-3.2.8-6.8 4.3-6.8 2.1 0 3.8 1.3 5 3.1 1.2-1.8 2.9-3.1 5-3.1 3.5 0 5.5 3.6 4.3 6.8-1.7 4.5-9 9-9.3 9z"/></svg>')
# Сумка: линии на полупикселях сетки 16px — чёткие и при масштабе 100 %; на странице корзины тело сумки залито
BAG = ('<svg class="bag" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
       '<path d="M2.5 5.5h11v9h-11z"/><path fill="none" d="M5.5 5.5V4a2.5 2.5 0 0 1 5 0v1.5"/></svg>')
# Лупа поиска — той же линией 1px на сетке 16px
LOUPE = ('<svg class="loupe" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
         '<circle cx="6.5" cy="6.5" r="5"/><path d="M10 10l5 5"/></svg>')
# Соцсети у «открыть в 2ГИС» на главной: тонкие линии, как у остальных значков, без цветных логотипов
IG_ICON = ('<svg class="soc__i" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">'
           '<rect x="2.5" y="2.5" width="15" height="15" rx="4.5"/><circle cx="10" cy="10" r="3.5"/>'
           '<circle cx="14.3" cy="5.7" r=".8" fill="currentColor" stroke="none"/></svg>')
PIN_ICON = ('<svg class="soc__i" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<circle cx="10" cy="10" r="7.9"/><path d="M6.5 17 10 9.1"/>'
            '<path d="M8.86 11.76c.38 1.1 1.26 1.75 2.24 1.75 1.82 0 3.29-1.36 3.29-3.51a4.39 4.39 0 1 0-8.51 1.49"/></svg>')
# WhatsApp в той же манере: пузырь 1px, как круг Pinterest; трубка — из фирменного WA_ICON, уменьшена до 0.72
WA_LINE_ICON = ('<svg class="soc__i" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1" '
                'stroke-linejoin="round" aria-hidden="true">'
                '<path d="M6.05 16.84A7.9 7.9 0 1 0 3.16 13.95L2.2 17.8z"/>'
                '<path fill="currentColor" stroke="none" transform="matrix(.72 0 0 .72 1.33 1.36)" d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347"/></svg>')
ARROW = '<span class="arr" aria-hidden="true">→</span>'
CUR = ' aria-current="page"'


def phone():
    n = str(DATA['whatsapp'])
    if len(n) == 11:   # 7 706 723 23 49
        return NBSP.join(('+' + n[0], n[1:4], n[4:7], n[7:9], n[9:]))
    return '+' + n


def ig_url():
    return f"https://www.instagram.com/{DATA['instagram']}/"


def pin_url():
    return f"https://www.pinterest.com/{DATA['pinterest']}/"


def langs(lang, suffix, cls):
    links = ''.join(
        f'<a class="lng" href="{e(url(l["code"] + "/" + suffix))}" hreflang="{l["html"]}" lang="{l["html"]}"'
        f'{" aria-current=\"true\"" if l["code"] == lang else ""}>'
        f'<span aria-hidden="true">{e(l["label"])}</span><span class="sr-only">{e(l["name"])}</span></a>'
        for l in LANGS)
    return f'<nav class="langs {cls}" aria-label="{e(t("nav_lang", lang))}">{links}</nav>'


def cat_rows(lang):
    """(ключ, подпись, адрес, число вещей): «все товары», сумки, кардхолдеры, брелоки — как просила заказчица."""
    ps = DATA['products']
    return [('all', t('all_items', lang), url(lang + '/catalog/'), len(ps))] + [
        (c, CATS[c][lang], url(f'{lang}/c/{c}/'), sum(1 for p in ps if in_cat(p, c))) for c in leaf_cats()]


def slogan(lang):
    """Слоган английский на всех языках — помечаем, чтобы экранный диктор читал его по-английски."""
    s1, s2 = t('slogan_1', lang), t('slogan_2', lang)
    s_lang = ' lang="en"' if lang != 'en' and s1 == t('slogan_1', 'en') else ''
    return f'<span{s_lang}>{e(s1)} {e(s2)}</span>'


def delivery(lang):
    """Доставка из data/settings.json: способы по Казахстану (цена, срок), порог бесплатной, «по миру — уточнить»."""
    dl = DATA.get('delivery') or {}
    if not dl.get('kz'):
        return f'<p>{e(t("delivery_body", lang))}</p>'
    rows = ''.join(
        f'<li class="dlv__i"><span class="dlv__n">{e(tri(o["name"])[lang])}</span>'
        f'<span class="dlv__p tnum">{e(money(o["price"], lang) if o.get("price") else t("dlv_free_word", lang))}</span>'
        f'<span class="dlv__d">{e(tri(o["days"])[lang])}</span></li>'
        for o in dl['kz'])
    free = (f'<p class="dlv__free">{e(t("dlv_free", lang, sum=money(dl["free_from"], lang)))}</p>'
            if dl.get('free_from') else '')
    return (f'<h3 class="dlv__t">{e(t("dlv_kz_title", lang))}</h3><ul class="dlv">{rows}</ul>{free}'
            f'<h3 class="dlv__t">{e(t("dlv_world_title", lang))}</h3><p>{e(t("dlv_world", lang))}</p>')


def seller_lines(lang):
    """Сведения о продавце (закон о защите прав потребителей, правила электронной торговли): ИП/ТОО и ИИН/БИН
    из data/settings.json → seller (заполняют в админке). Пока не заполнено — строки нет, только адрес магазина и тенге."""
    sl = DATA.get('seller') or {}
    name, bin_ = str(sl.get('name') or '').strip(), str(sl.get('bin') or '').strip()
    rows = [t('f_seller_fmt', lang, name=name, bin=bin_)] if name and bin_ else []
    rows += [t('f_store_fmt', lang, address=t('address', lang), hours=t('hours', lang)), t('f_prices', lang)]
    return ''.join(f'<p>{e(x)}</p>' for x in rows)


def paras(text):
    return ''.join(f'<p>{e(x.strip())}</p>' for x in text.split('\n\n') if x.strip())


def mats_text(p, lang):
    return ', '.join(MATS[m][lang] for m in p['materials'])


def home_img(item, sizes, lang, *, load='lazy'):
    w = item['_widths'][0]
    attrs = {'lazy': 'loading="lazy"', 'eager': 'loading="eager"', 'high': 'loading="eager" fetchpriority="high"'}[load]
    return (f'<img src="{asset(f"assets/img/home/{item['_stem']}-{w}.webp")}" '
            f'srcset="{home_srcset(item)}" sizes="{sizes}" width="{w}" height="{round(w / item["_ratio"])}" '
            f'alt="{e(tri(item.get("alt"))[lang])}" {attrs} decoding="async">')


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
<a class="logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black.svg')}" alt="{e(t('home', lang))}" width="52" height="20"></a>
<a class="ibtn menu__wa" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</div>
<nav class="menu__nav" aria-label="{e(t('menu', lang))}">
<ul class="menu__main">{cats}</ul>
<ul class="menu__sub">
<li><a href="{url(lang + '/fav/')}"{CUR if key == 'fav' else ''}>{e(t('fav_title', lang))}<span class="cnt" data-fav-n aria-hidden="true"></span></a></li>
<li><a href="{url(lang + '/cart/')}"{CUR if key == 'cart' else ''}>{e(t('cart_title', lang))}<span class="cnt" data-cart-n aria-hidden="true"></span></a></li>
<li><a href="{url(lang + '/about/')}"{CUR if key == 'about' else ''}>{e(t('about_title', lang))}</a></li>
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
</ul>
</nav>
<div class="menu__foot">
{langs(lang, suffix, 'menu__langs')}
<ul class="menu__contacts">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="tnum">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><span>{e(t('hours', lang))}</span></li>
</ul>
</div>
</div>'''


SEARCH = {}   # язык → адрес индекса поиска с ?v=<хеш содержимого>; заполняет search_index() до сборки страниц


def search_index(lang):
    """Индекс поиска на языке lang — маленький JSON: адрес вещи, названия на всех языках сайта (первое — на этом),
    тип, материал и раздел (на всех языках), цвета — у каждого своё фото и адрес ?c=, цена как на сайте (p — по которой
    продаём, o — зачёркнутая старая), бирка «продано» / «скоро в наличии». v4.js грузит его при первом открытии поиска."""
    order = [lang] + [c for c in CODES if c != lang]

    def uniq(*groups):   # без повторов и пустых: у большинства моделей название одно на всех языках
        seen, out = set(), []
        for s in (x for g in groups for x in g):
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        return out

    items = []
    for p in ordered(DATA['products']):
        url_p = item_url(p, lang)
        it = {'u': url_p, 'n': uniq(p['name'][c] for c in order), 't': uniq(p['type'][c] for c in order),
              'm': uniq(MATS[m][c] for m in p['materials'] for c in order),
              'g': uniq(CATS[k][c] for k in dict.fromkeys((p['cat'], top_cat(p['cat']))) for c in order),
              'i': asset(f"assets/img/p/{p['images'][0]}-600.webp"), 'p': price_now(p)}
        if p['sale']:
            it['o'] = p['price']
        if sold(p) or p['soon']:
            it['s'] = t('sold' if sold(p) else 'soon', lang)
        if p['variants']:   # свой оттенок (карамельный) и цвет палитры (коричневый) — найдётся по обоим
            it['v'] = [{'n': uniq((v['name'][c] for c in order), (COLORS[v['key']][c] for c in order)),
                        'i': asset(f"assets/img/p/{v['images'][0]}-600.webp"), 'u': url_p + (f"?c={v['id']}" if i else '')}
                       for i, v in enumerate(p['variants'])]
        elif p['colors']:
            it['v'] = [{'n': uniq(COLORS[k][c] for c in order)} for k in p['colors']]
        items.append(it)
    text = json.dumps({'items': items}, ensure_ascii=False, separators=(',', ':'))
    SEARCH[lang] = f"{asset(f'assets/search/{lang}.json')}?v={hashlib.sha1(text.encode()).hexdigest()[:8]}"
    return text


def search_panel(lang):
    """Поиск по названию — белая панель, как меню: на телефоне на весь экран, с планшета — слева. Строка поиска сверху,
    результаты сразу под ней — клавиатура телефона их не закрывает. Индекс (search_index) v4.js грузит при первом
    открытии. Без JS панели и лупы в шапке нет."""
    return f'''<div class="srch" id="search" data-panel data-search="{e(SEARCH.get(lang, ''))}" aria-label="{e(t('search', lang))}">
<div class="srch__bar">
<form class="srch__f" role="search" action="#" data-search-form>{LOUPE}<input class="srch__in" type="search" name="q" data-focus autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="search" placeholder="{e(t('search_ph', lang))}" aria-label="{e(t('search_label', lang))}"></form>
<button class="ibtn srch__x" type="button" data-close aria-label="{e(t('close', lang))}">{X_ICON}</button>
</div>
<div class="srch__body" data-search-body>
<p class="srch__n" data-search-n aria-hidden="true"></p>
<p class="sr-only" role="status" data-search-live></p>
<p class="srch__all" data-search-none hidden><a class="ulink" href="{url(lang + '/catalog/')}">{e(t('all_catalog', lang))}{ARROW}</a></p>
<ul class="srch__res" data-search-res aria-label="{e(t('search_res', lang))}"></ul>
</div>
</div>'''


def sheet(sid, title, inner, lang, cls=''):
    """Нижний лист. Без JS — обычный блок на своём месте; v4.js переносит его в конец body и делает диалогом."""
    return f'''<section class="sheet{cls}" id="{sid}" data-panel data-sheet aria-labelledby="{sid}-t">
<div class="sheet__head"><h2 class="sheet__t" id="{sid}-t">{e(title)}</h2><button class="ibtn sheet__x js-only" type="button" data-close aria-label="{e(t('close', lang))}">{X_ICON}</button></div>
<div class="sheet__body">{inner}</div>
</section>'''


def opener(sid, label, cls):
    return (f'<button class="{cls} js-only" type="button" data-open="{sid}" aria-controls="{sid}" '
            f'aria-expanded="false" aria-haspopup="dialog">{label}</button>')


def acc(title, inner, cls=''):
    """Строка, которая раскрывается (details: без JS раскрывается сама, v4.js добавляет плавность высоты)."""
    return (f'<details class="acc{cls}"><summary><span>{e(title)}</span>{PLUS}</summary>'
            f'<div class="acc__body"><div class="acc__clip"><div class="acc__in">{inner}</div></div></div></details>')


def rail_nav(lang, count=None):
    """Стрелки ленты (только мышь) и полоски внизу фото — сколько фото и какое сейчас (вместо счётчика «1 / 5»)."""
    bars = ''
    if count and count > 1:
        bars = ('<span class="rail__bars js-only" aria-hidden="true">'
                + ''.join('<i class="is-on"></i>' if i == 0 else '<i></i>' for i in range(count)) + '</span>')
    return bars + (f'<button class="rail__arr rail__arr--prev js-only" type="button" data-step="-1" aria-label="{e(tx("prev", lang))}">{ARR_ICON}</button>'
                   f'<button class="rail__arr rail__arr--next js-only" type="button" data-step="1" aria-label="{e(tx("next", lang))}">{ARR_ICON}</button>')


# ——— Каркас страницы ———

def footer(lang, suffix):
    info = url(f'{lang}/info/')
    cats = ''.join(f'<li><a href="{h}">{e(label)}</a></li>' for _, label, h, _ in cat_rows(lang))
    proto = f'<p>{e(t("f_proto", lang))}</p>' if PROTOTYPE else ''
    return f'''<footer class="ftr">
<div class="ftr__accs">
{acc(t('dock_catalog', lang), f'<ul class="flist">{cats}</ul>', ' acc--f')}
{acc(t('f_buyers', lang), f"""<ul class="flist">
<li><a href="{url(lang + '/fav/')}">{e(t('fav_title', lang))}</a></li>
<li><a href="{url(lang + '/cart/')}">{e(t('cart_title', lang))}</a></li>
<li><a href="{url(lang + '/about/')}">{e(t('about_title', lang))}</a></li>
<li><a href="{info}#bonus">{e(t('bonus_short', lang))}</a></li>
<li><a href="{info}#delivery">{e(t('f_delivery', lang))}</a></li>
<li><a href="{info}#returns">{e(t('f_returns', lang))}</a></li>
<li><a href="{info}#seller">{e(t('seller_title', lang))}</a></li>
</ul>""", ' acc--f')}
{acc(t('f_contacts', lang), f"""<ul class="flist">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener">WhatsApp <span class="tnum">{phone()}</span></a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a href="{pin_url()}" target="_blank" rel="noopener">Pinterest @{e(DATA['pinterest'])}</a></li>
<li><a href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
</ul>""", ' acc--f')}
{acc(tx('store', lang), f"""<ul class="flist">
<li><a href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('address', lang))}</a></li>
<li><span>{e(t('hours', lang))}</span></li>
<li><span>{e(t('delivery_world', lang))}</span></li>
</ul>""", ' acc--f')}
</div>
<div class="ftr__row">{langs(lang, suffix, 'ftr__langs')}<p class="ftr__copy">© {datetime.date.today().year} attré</p></div>
<div class="ftr__legal">
{seller_lines(lang)}
{proto}
</div>
<div class="ftr__brand">
<a class="ftr__logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black.svg')}" alt="{e(t('home', lang))}" width="300" height="116" loading="lazy" decoding="async"></a>
<p class="ftr__slogan">{slogan(lang)}</p>
</div>
</footer>'''


def js_texts(lang):
    """Тексты для v4.js: подписи кнопок, письма со списком избранного и с заказом из корзины, формат цены."""
    return json.dumps({
        'favAdd': t('fav_add', lang), 'favDel': t('fav_del', lang), 'waFav': t('wa_fav', lang),
        'waItem': tx('wa_item', lang), 'wa': str(DATA['whatsapp']), 'show': t('f_show', lang),
        'play': t('film_play', lang), 'pause': t('film_pause', lang), 'sep': ',' if lang == 'en' else NBSP,
        'cartAdded': t('cart_added', lang), 'cartAsk': t('cart_ask', lang), 'waCart': t('wa_cart', lang),
        'waCartItem': t('wa_cart_item', lang), 'waCartTotal': t('wa_cart_total', lang),
        'waCartAsk': t('wa_cart_ask', lang), 'waCartBonus': t('wa_cart_bonus', lang),
        'waColor': t('wa_color', lang), 'waProductC': t('wa_product_c', lang),
        'priceAsk': t('price_request', lang), 'priceOld': t('price_old', lang), 'priceSale': t('price_sale', lang),
        'searchN': t('search_n', lang), 'searchNone': t('search_none', lang), 'searchErr': t('search_err', lang),
    }, ensure_ascii=False).replace('</', '<\\/')


# Полоса бонуса чёрная; ?bar=red в адресе делает её красной до конца сессии (?bar=black — обратно) — для сравнения.
# Скрипт стоит в <head>, чтобы цвет был сразу, без мигания.
HEAD_JS = ("(function(d){d.classList.add('js');try{var m=/[?&]bar=(red|black)/.exec(location.search),s=sessionStorage;"
           "if(m)s.setItem('attre-bar',m[1]);if(s.getItem('attre-bar')==='red')d.classList.add('bar-red')}catch(e){}"
           "setTimeout(function(){if(!window.__v4)d.classList.remove('js')},6000)})(document.documentElement)")


def layout(lang, *, title, desc, body, suffix, og_image, og_type='website', page='', cur=None, head=''):
    cfg = next(l for l in LANGS if l['code'] == lang)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{l["html"]}" href="{e(abs_url(l["code"] + "/" + suffix))}">' for l in LANGS)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{e(abs_url(I18N["default"] + "/" + suffix))}">'
    robots = '<meta name="robots" content="noindex, nofollow">' if PROTOTYPE else ''
    no_js = "document.documentElement.classList.remove('js')"
    key = (cur or (None,))[0]
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
{head}
<link rel="icon" href="{asset('assets/img/brand/favicon.png')}" type="image/png">
<link rel="icon" href="{asset('assets/img/brand/favicon.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{asset('assets/img/brand/apple-touch-icon.png')}">
<link rel="preload" href="{asset('assets/fonts/onest-var.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{asset('assets/css/' + CSS)}?v={VER}">
<script>{HEAD_JS}</script>
</head>
<body class="{page}">
<a class="skip" href="#main">{e(tx('skip', lang))}</a>
<a class="promo" href="{url(lang + '/info/')}#bonus">{e(t('promo', lang))}</a>
<header class="hdr">
<div class="hdr__l">
<button class="ibtn hdr__menu js-only" type="button" aria-controls="menu" aria-expanded="false" aria-haspopup="dialog" data-open="menu"><span class="burger" aria-hidden="true"></span><span class="sr-only">{e(t('menu', lang))}</span></button>
<button class="ibtn hdr__search js-only" type="button" aria-controls="search" aria-expanded="false" aria-haspopup="dialog" data-open="search">{LOUPE}<span class="sr-only">{e(t('search', lang))}</span></button>
</div>
<a class="logo" href="{url(lang + '/')}"><img src="{asset('assets/img/brand/logo-black.svg')}" alt="{e(t('home', lang))}" width="52" height="20"></a>
<div class="hdr__r">
<a class="ibtn hdr__fav" href="{url(lang + '/fav/')}"{CUR if key == 'fav' else ''}>{HEART}<span class="hdr__n tnum" data-fav-n aria-hidden="true"></span><span class="sr-only">{e(t('fav_title', lang))}</span></a>
<a class="ibtn hdr__cart" href="{url(lang + '/cart/')}"{CUR if key == 'cart' else ''}>{BAG}<span class="hdr__n tnum" data-cart-n aria-hidden="true"></span><span class="sr-only">{e(t('cart_title', lang))}</span></a>
<a class="ibtn hdr__wa" href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_ICON}</a>
</div>
</header>
<main id="main" tabindex="-1">
{body}
</main>
{footer(lang, suffix)}
{menu(lang, suffix, cur)}
{search_panel(lang)}
<script type="application/json" id="v4-t">{js_texts(lang)}</script>
<script src="{asset('assets/js/v4.js')}?v={VER}" defer onerror="{no_js}"></script>
</body>
</html>
'''


# ——— Карточки: витрина «одна вещь крупно → две рядом» и ленты подборок ———

def tag(p, lang):
    """Одна бирка над названием, по важности: продано → скоро в наличии → осталась одна → новинка."""
    if sold(p):
        return f'<p class="tag">{e(t("sold", lang))}</p>'
    if p['soon']:
        return f'<p class="tag tag--on">{e(t("soon", lang))}</p>'
    if p['stock'] == 1:
        return f'<p class="tag tag--on">{e(t("last", lang))}</p>'
    if p['is_new']:
        return f'<p class="tag tag--on tag--new">{e(t("new_tag", lang))}</p>'
    return ''


def price_html(p, lang):
    """Цена в карточке, на товаре и в корзине. Со скидкой — как у примера заказчиц, без процента: старая зачёркнута,
    рядом новая красным. Зачёркивание диктор не читает — ему подписи «старая цена», «цена со скидкой»."""
    if not p['sale']:
        return e(price_text(p, lang))
    return (f'<span class="sr-only">{e(t("price_old", lang))}:</span><s class="price__was">{e(money(p["price"], lang))}</s> '
            f'<span class="sr-only">{e(t("price_sale", lang))}:</span><span class="price__now">{e(money(p["sale"], lang))}</span>')


def fav_btn(p, lang, cls='fav'):
    return (f'<button class="{cls}" type="button" data-fav="{p["slug"]}" aria-pressed="false" '
            f'aria-label="{e(t("fav_add", lang))}">{HEART}</button>')


SIZES = {   # те же значения повторяет v4.js при перестройке ритма после фильтра
    'w1': '(min-width: 600px) 25vw, 100vw', 'w2': '(min-width: 600px) 25vw, 100vw',   # с планшета крупная = обычная
    'h': '(min-width: 600px) 25vw, 50vw', 'row': '(min-width: 960px) 20vw, (min-width: 600px) 30vw, 44vw',
}


def swatch(key, cls=''):
    """Кружочек цвета палитры (фильтр): заливка или узор принта (леопард, коровий, зебра — классы в v4.css)."""
    hexv = COLORS[key]['hex']
    style = f' style="background:{hexv}"' if hexv else ''
    light = ' sw--light' if hexv and is_light(hexv) else ''
    return f'<span class="sw sw--{key}{light}{cls}"{style} aria-hidden="true"></span>'


def is_light(hexv):
    """Светлый кружочек (молочный, бежевый) на белом не виден без тонкой серой обводки."""
    try:
        r, g, b = (int(str(hexv)[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except ValueError:
        return False
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.82


def vswatch(v, cls=''):
    """Кружочек цвета вещи: свой оттенок (hex) или узор принта — леопард, зебра, корова, далматин."""
    pat = v['pattern'] if v['pattern'] in ('leopard', 'zebra', 'cow', 'dalmatian') else None
    if pat:
        return f'<span class="sw sw--{pat}{cls}" aria-hidden="true"></span>'
    light = ' sw--light' if is_light(v['hex']) else ''
    return f'<span class="sw{light}{cls}" style="background:{v["hex"]}" aria-hidden="true"></span>'


def vmats(p, v, lang):
    return ', '.join(MATS[m][lang] for m in (v['materials'] or p['materials']))


def card(p, lang, kind, *, h='h2', load='lazy', hidden=False):
    """kind: 'w' — крупно на всю ширину, 'h' / 'h2' — половина ряда (h2 — правая), 'row' — карточка ленты;
    ' r' в конце — на компьютере крупная карточка стоит справа (ряды идут «ёлочкой»).
    Фото в карточке листаются вправо-влево (полоски внизу, у мыши — стрелки), нажатие на фото открывает товар.
    В лентах главной не листаются: там вбок уже едет сама лента. У проданной вещи — одно фото.
    Кружочки цветов под ценой (просьба заказчицы): нажатие меняет фото карточки на фото этого цвета, ссылка ведёт
    на товар в этом цвете (?c=black). Фото остальных цветов лежат в <template> и не грузятся, пока цвет не выбран."""
    vs = p['variants'] or []
    multi = len(vs) > 1 and not sold(p)
    row = kind == 'row'
    sets = [v['images'] for v in vs] if multi else [p['images']]
    gal = not sold(p) and not row and any(len(x) > 1 for x in sets)   # листается хотя бы у одного цвета
    wide = kind.startswith('w')
    sizes = SIZES['row'] if row else SIZES['w2' if gal else 'w1'] if wide else SIZES['h']
    first = {'lazy': 'loading="lazy"', 'eager': 'loading="eager"',
             'high': 'loading="eager" fetchpriority="high"'}[load]

    def pics(stems, live=True):
        return ''.join(
            f'<img class="vc__img" src="{asset(f"assets/img/p/{x}-600.webp")}" srcset="{img_srcset(x)}" sizes="{sizes}" '
            f'width="600" height="800" alt="" {first if live and i == 0 else 'loading="lazy"'} decoding="async">'
            for i, x in enumerate(stems if gal else stems[:1]))

    shots = p['images'] if gal else p['images'][:1]
    url_p = item_url(p, lang)
    extra = ''
    if gal:   # полоски — сколько фото и какое сейчас; стрелки — только мышь (для клавиатуры есть страница товара)
        bars = ''.join('<i class="is-on"></i>' if i == 0 else '<i></i>' for i in range(len(shots))) if len(shots) > 1 else ''
        extra = (f'<span class="vc__bars js-only" aria-hidden="true">{bars}</span>'
                 f'<button class="vc__arr vc__arr--prev js-only" type="button" data-vstep="-1" tabindex="-1" aria-hidden="true" hidden>{ARR_ICON}</button>'
                 f'<button class="vc__arr vc__arr--next js-only" type="button" data-vstep="1" tabindex="-1" aria-hidden="true"'
                 f'{"" if len(shots) > 1 else " hidden"}>{ARR_ICON}</button>')
    cls = 'vc' + {'row': ' vc--row'}.get(kind, '') + (' vc--w' if wide else '') + (' vc--2' if kind == 'h2' else '')
    cls += (' vc--r' if kind.endswith(' r') else '') + (' vc--gal' if gal else ' vc--one') + (' vc--sold' if sold(p) else '')
    data = (f' data-slug="{p["slug"]}" data-id="{e(p["id"])}" data-name="{e(p["name"][lang])}"'
            f' data-mat="{" ".join(p["materials"])}" data-col="{" ".join(p["colors"])}" data-price="{price_now(p) or ""}"'
            + (f' data-v="{vs[0]["id"]}" data-v0="{vs[0]["id"]}"' if multi else '')
            + (' data-new' if p['is_new'] else '') + (' data-pop' if p['popular'] else '')
            + (' data-sold' if sold(p) else '') + (' hidden' if hidden else ''))
    meta = p['type'][lang] if p['colors'] else meta_line(p, lang)
    names = ', '.join(v['name'][lang] for v in vs) if vs else ', '.join(COLORS[c][lang] for c in p['colors'])
    said = f'<span class="sr-only">{e(t("f_col", lang))}: {e(names)}</span>' if names else ''
    dots, tpls = '', ''
    if multi:   # кнопки — для мыши и пальца; диктору цвета прочитаны в подписи, выбор цвета с клавиатуры — на странице товара
        dots = ('<div class="vc__sw vc__sw--pick js-only" aria-hidden="true">' + ''.join(
            f'<button class="vc__c" type="button" tabindex="-1" data-v="{v["id"]}" data-k="{v["key"]}" '
            f'aria-pressed="{"true" if i == 0 else "false"}" title="{e(v["name"][lang])}">{vswatch(v, " sw--s")}</button>'
            for i, v in enumerate(vs)) + '</div>')
        tpls = ''.join(f'<template data-v="{v["id"]}">{pics(v["images"], live=False)}</template>' for v in vs[1:])
    elif names:
        dots = (f'<p class="vc__sw" title="{e(names)}" aria-hidden="true">'
                + (''.join(vswatch(v, ' sw--s') for v in vs) if vs else ''.join(swatch(c, ' sw--s') for c in p['colors'])) + '</p>')
    return f'''<li class="{cls}"{data}>
<div class="vc__media"><a class="vc__ph" href="{url_p}" tabindex="-1" aria-hidden="true"><span class="vc__track">{pics(p['images'])}</span></a>{extra}</div>
<a class="vc__a" href="{url_p}"><div class="vc__cap">{tag(p, lang)}<{h} class="vc__name">{e(p['name'][lang])}</{h}>{f'<p class="vc__meta">{e(meta)}</p>' if meta and kind != 'row' else ''}<p class="vc__price tnum">{price_html(p, lang)}</p>{said}</div></a>
{dots}{tpls}{fav_btn(p, lang)}</li>'''


def rhythm(n):
    """Ритм витрины: крупно, две рядом, крупно, две рядом… Хвост из двух — просто пара (без дыры в ряду).
    На компьютере каждый второй цикл ставит крупную вещь справа (только у полных циклов). Повтор — в v4.js."""
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


def vitrine(items, lang, *, h='h2', first=False, attrs=''):
    """first — витрина вверху страницы: первые фото грузятся сразу, самое первое — с высоким приоритетом."""
    kinds = rhythm(len(items))

    def load(i):
        if not first or i > 2:
            return 'lazy'
        return 'high' if i == 0 else 'eager'

    cards = ''.join(card(p, lang, kinds[i], h=h, load=load(i)) for i, p in enumerate(items))
    return f'<ul class="vit"{attrs}>\n{cards}\n</ul>'


def shelf(sid, title, link, link_label, items, lang):
    """Подборка на главной: заголовок, ссылка справа и лента карточек со свайпом."""
    cards = ''.join(card(p, lang, 'row', h='h3') for p in items)
    return f'''<section class="shelf shelf--{sid}" aria-labelledby="{sid}-t">
<div class="sec-h"><h2 class="sec-h__t" id="{sid}-t">{e(title)}</h2><a class="sec-h__a" href="{link}">{e(link_label)}{ARROW}</a></div>
<div class="rail rail--row" data-rail="row"><ul class="row" data-track>{cards}</ul>{rail_nav(lang)}</div>
</section>'''


# ——— Каталог: категории строкой, фильтр и сортировка в нижнем листе ———

def filter_sheet(items, lang):
    mats = [m for m in MATS if any(m in p['materials'] for p in items)]
    cols = [c for c in COLORS if any(c in p['colors'] for p in items)]
    prices = [price_now(p) for p in items if p['price']]   # со скидкой — цена со скидкой
    lo = min([PRICE_RANGE[0], *prices]) // PRICE_STEP * PRICE_STEP
    hi = -(-max([PRICE_RANGE[1], *prices]) // PRICE_STEP) * PRICE_STEP
    off = '' if len(prices) > 1 else ' disabled'
    # «рекомендуем» убран (просьба заказчицы): без отметки — обычный порядок, «сбросить» возвращает к нему
    sorts = [('new', 'sort_new'), ('pop', 'sort_pop'), ('asc', 'sort_asc'), ('desc', 'sort_desc')]
    sort_html = ''.join(
        f'<label class="opt"><input type="radio" name="sort" value="{v}"><span>{e(t(k, lang))}</span></label>'
        for v, k in sorts)
    mat_html = ''.join(
        f'<label class="chip"><input type="checkbox" name="mat" value="{m}"><span>{e(MATS[m][lang])}</span></label>' for m in mats)
    col_html = ''.join(
        f'<label class="opt opt--c"><input type="checkbox" name="col" value="{c}">{swatch(c)}<span>{e(COLORS[c][lang])}</span></label>'
        for c in cols)
    sep = ',' if lang == 'en' else NBSP
    fmt = lambda n: f'{n:,}'.replace(',', sep) + NBSP + '₸'   # noqa: E731
    price_html = f'''<div class="range" data-range data-min="{lo}" data-max="{hi}">
<p class="range__out tnum"><output data-out="min">{fmt(lo)}</output><span aria-hidden="true"> — </span><output data-out="max">{fmt(hi)}</output></p>
<div class="range__box"><span class="range__line" aria-hidden="true"><span class="range__fill" data-fill></span></span>
<input type="range" name="min" min="{lo}" max="{hi}" step="{PRICE_STEP}" value="{lo}" aria-label="{e(t('price_min', lang))}"{off}>
<input type="range" name="max" min="{lo}" max="{hi}" step="{PRICE_STEP}" value="{hi}" aria-label="{e(t('price_max', lang))}"{off}></div>
{'' if not off else f'<p class="range__note">{e(t("f_price_off", lang))}</p>'}
</div>'''
    groups = [('sort', t('sort', lang), f'<div class="opts">{sort_html}</div>')]
    if len(mats) > 1:
        groups.append(('mat', t('f_mat', lang), f'<div class="chips">{mat_html}</div>'))
    if len(cols) > 1:
        groups.append(('col', t('f_col', lang), f'<div class="opts opts--c">{col_html}</div>'))
    groups.append(('price', t('f_price', lang), price_html))
    sets = ''.join(f'<fieldset class="fset fset--{k}"><legend class="fset__t">{e(title)}</legend>{inner}</fieldset>'
                   for k, title, inner in groups)
    n = len(items)
    inner = f'''<form class="flt" data-filter action="#" novalidate>{sets}
<div class="flt__foot">
<button class="flt__reset" type="reset" data-f-reset>{e(t('f_reset', lang))}</button>
<button class="btn btn--ink flt__show" type="button" data-close data-f-show>{e(t('f_show', lang).replace('{n}', str(n)))}</button>
</div></form>'''
    return sheet('sh-filter', t('filter', lang), inner, lang, ' sheet--flt js-only')


def catalog(lang, cat=None):
    items = ordered([p for p in DATA['products'] if cat is None or in_cat(p, cat)])
    heading = CATS[cat][lang] if cat else t('all_items', lang)
    key = cat or 'all'
    chips = ''.join(
        f'<li><a href="{h}"{CUR if k == key else ""}>{e(label)}<span class="cnt" aria-hidden="true">{n}</span></a></li>'
        for k, label, h, n in cat_rows(lang))
    can_filter = len(items) >= 4
    btn = opener('sh-filter', f'<span>{e(t("filter", lang))}</span><span class="pb__fc tnum" data-fcount></span>{PLUS}', 'pb__btn') if can_filter else ''
    grid = (vitrine(items, lang, first=True, attrs=' data-grid') + f'''
<div class="empty" data-none hidden><p>{e(t('f_none', lang))}</p><button class="ulink" type="button" data-f-reset>{e(t('f_reset', lang))}</button></div>'''
            if items else f'<p class="empty">{e(t("empty", lang))}</p>')
    body = f'''<div class="pb">
<h1 class="pb__t">{e(heading)}<sup class="pb__n tnum" data-n aria-hidden="true">{len(items)}</sup></h1>
{btn}
</div>
<nav class="tabs" aria-label="{e(t('nav_cats', lang))}"><ul class="tabs__in">{chips}</ul></nav>
{filter_sheet(items, lang) if can_filter else ''}
{grid}'''
    suffix = f'c/{cat}/' if cat else 'catalog/'
    return layout(lang, title=f'{heading} — attré', desc=t('site_desc', lang), body=body, suffix=suffix,
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-cat', cur=(key, True))


# ——— Товар ———

def product_ld(p, lang, page_url):
    """Разметка товара для поисковиков (schema.org Product) — только у вещи с ценой: в offers цена, по которой продаём
    (со скидкой, если она есть). Без цены («цена по запросу») разметки нет: Product без offers Google считает ошибкой."""
    if not p['price']:
        return ''
    state = 'SoldOut' if sold(p) else 'OutOfStock' if p['soon'] else 'InStock'
    ld = {'@context': 'https://schema.org', '@type': 'Product', 'name': p['name'][lang], 'sku': p['id'], 'url': page_url,
          'image': [abs_asset(f'assets/img/p/{x}-1200.webp') for x in p['images']],
          'brand': {'@type': 'Brand', 'name': 'attré'}}
    if p['desc'][lang]:
        ld['description'] = p['desc'][lang]
    ld['offers'] = {'@type': 'Offer', 'price': price_now(p), 'priceCurrency': 'KZT', 'url': page_url,
                    'availability': f'https://schema.org/{state}'}
    data = json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')
    return f'<script type="application/ld+json">{data}</script>'


def product(p, lang):
    name = p['name'][lang]
    info = url(f'{lang}/info/')
    page_url = abs_url(f"{lang}/p/{p['slug']}/")
    vs = p['variants'] or []
    cur = vs[0] if vs else None

    def slides(stems, v=None, live=True):
        out, n = [], len(stems)
        label = f'{name}, {v["name"][lang]}' if v and len(vs) > 1 else name
        for i, stem in enumerate(stems):
            alt = e(label) + (' — ' + e(t('photo_n', lang, i=i + 1, n=n)) if i else '')
            # первые два — сразу (второе увидят первым свайпом), остальные v4.js догрузит после загрузки страницы
            load = ('loading="eager" fetchpriority="high"' if i == 0 else 'loading="eager"' if i == 1 else 'loading="lazy"') if live else 'loading="lazy"'
            out.append(f'<figure class="pg__slide"><img src="{asset(f"assets/img/p/{stem}-1200.webp")}" '
                       f'srcset="{img_srcset(stem)}" sizes="(min-width: 960px) 45vw, 100vw" width="1200" height="1600" '
                       f'alt="{alt}" {load} decoding="async"></figure>')
        return ''.join(out)

    n = max([len(v['images']) for v in vs] or [len(p['images'])])   # полоски и стрелки — если листается хоть один цвет
    # фото остальных цветов — в <template>: не грузятся, пока человек не выбрал цвет
    tpls = ''.join(f'<template data-pv="{v["id"]}">{slides(v["images"], v, live=False)}</template>' for v in vs[1:])

    todo = f'<span class="todo">{e(t("todo", lang))}</span>'
    size = (f'<span class="tnum">{e(t("p_size_fmt", lang, w=p["size"][0], h=p["size"][1], d=p["size"][2]))}</span>'
            if p['size'] else todo)
    spec_rows = [
        (t('p_type', lang), e(p['type'][lang]) if p['type'][lang] else todo),
        (t('p_color', lang), f'<span data-pcol-name>{e(cur["name"][lang])}</span>' if cur
         else e(p['color'][lang]) if p['color'][lang] else todo),
        (t('p_material', lang), f'<span data-pcol-mat>{e(vmats(p, cur, lang))}</span>' if cur and vmats(p, cur, lang)
         else e(mats_text(p, lang)) if p['materials'] else todo),
        (t('p_size', lang), size),
        (t('p_strap', lang), e(p['strap'][lang]) if p['strap'] else todo),
        (t('p_made', lang), e(t('made_in', lang))),   # по просьбе заказчицы — вместо «производитель» и «страна»
    ]
    spec = '<dl class="spec">' + ''.join(f'<div><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in spec_rows) + '</dl>'
    wa_general = e(wa_link(t('wa_general', lang)))
    rows = ''.join([
        acc(t('acc_details', lang), spec),
        acc(t('f_delivery', lang), f'{delivery(lang)}<h3 class="dlv__t">{e(t("pay_title", lang))}</h3><p>{e(t("payment_body", lang))}</p>'
                                   f'<p><a class="ulink" href="{info}#delivery">{e(tx("more", lang))}</a></p>'),
        acc(t('acc_returns', lang), f'<p>{e(t("returns_body", lang))}</p>'),
        acc(t('acc_store', lang), f'<p>{e(t("store_body", lang))}</p><p>{e(t("hours", lang))}</p>'
                                  f'<p class="links"><a class="ulink" href="{e(DATA["map_url"])}" target="_blank" rel="noopener">{e(t("map", lang))}</a>'
                                  f'<a class="ulink" href="{wa_general}" target="_blank" rel="noopener">{e(t("wa_label", lang))}</a></p>'),
    ])

    if sold(p):
        msg, label = t('wa_sold', lang, name=name, id=p['id'], url=page_url), t('wa_btn_sold', lang)
    elif p['soon']:
        msg, label = t('wa_soon', lang, name=name, id=p['id'], url=page_url), t('wa_btn_soon', lang)
    elif cur:
        msg = t('wa_product_c', lang, name=name, id=p['id'], color=cur['name'][lang], url=page_url)
        label = t('wa_btn', lang)
    else:
        msg, label = t('wa_product', lang, name=name, id=p['id'], price=price_text(p, lang), url=page_url), t('wa_btn', lang)
    # «В корзину» — только у вещей в наличии. Вещь уже в корзине — вместо кнопки ссылка «перейти в корзину» (v4.js).
    # Без JS корзины нет: кнопки скрыты, WhatsApp остаётся кнопкой с подписью; с JS он сжимается до значка 44×44.
    buy = not sold(p) and not p['soon']
    vid = f' data-v="{cur["id"]}" data-v0="{cur["id"]}"' if cur else ''
    to_cart = (f'<button class="btn btn--ink js-only" type="button" data-cart-add="{p["slug"]}"{vid}>{e(t("cart_add", lang))}</button>'
               f'<a class="btn js-only" href="{url(lang + "/cart/")}" data-cart-go="{p["slug"]}" hidden>{e(t("cart_go", lang))}</a>'
               f'<span class="sr-only" role="status" data-cart-live></span>') if buy else ''
    typ, color = p['type'][lang], p['color'][lang]
    desc = f'<p class="pp__desc">{e(p["desc"][lang])}</p>' if p['desc'][lang] else ''
    sim = similar(p)
    sim_html = f'''<section class="sim" aria-labelledby="sim-t">
<div class="sec-h"><h2 class="sec-h__t" id="sim-t">{e(t('similar', lang))}</h2><a class="sec-h__a" href="{url(f"{lang}/c/{p['cat']}/")}">{e(CATS[p['cat']][lang])}{ARROW}</a></div>
{vitrine(sim, lang, h='h3')}
</section>''' if sim else ''
    gallery = f'''<div class="pg rail" data-rail="slides"{f' data-v="{cur["id"]}"' if cur else ''}>
<div class="pg__track" data-track role="region" aria-label="{e(tx('photos', lang))}">{slides(p['images'], cur)}</div>
{rail_nav(lang, max(len(p['images']), 2)) if n > 1 else ''}{tpls}
</div>'''
    # Цвет — кружочки сразу под «в корзину» (как показала заказчица): выбранный в кольце, подпись «цвет: молочный».
    # Нажатие меняет фото, строки «цвет» и «материал», цвет для корзины и текст для WhatsApp (v4.js). Без JS — строка цветов.
    picker = ''
    if cur:
        opts = ''.join(
            f'<label class="pcol__o" title="{e(v["name"][lang])}"><input type="radio" name="pcol" value="{v["id"]}"'
            f'{" checked" if i == 0 else ""} data-name="{e(v["name"][lang])}" data-mat="{e(vmats(p, v, lang))}">'
            f'{vswatch(v)}<span class="sr-only">{e(v["name"][lang])}</span></label>'
            for i, v in enumerate(vs))
        picker = (f'<fieldset class="pcol js-only"><legend class="pcol__t">{e(t("p_color", lang))}: '
                  f'<span data-pcol-name>{e(cur["name"][lang])}</span></legend><div class="pcol__opts">{opts}</div></fieldset>')
    wa_data = (f' data-wa-c data-wa-name="{e(name)}" data-wa-id="{e(p["id"])}" data-wa-url="{e(page_url)}"'
               if cur and buy else '')
    body = f'''<article class="pp">
{gallery}
<div class="pp__side">
<div class="pp__bar">
<div class="pp__head"><h1 class="pp__name">{e(name)}</h1><p class="pp__price tnum">{price_html(p, lang)}</p></div>
<div class="pp__acts{' pp__acts--cart' if buy else ''}">{to_cart}<a class="btn btn--wa" href="{e(wa_link(msg))}" target="_blank" rel="noopener"{wa_data}>{WA_ICON}<span class="btn__l">{e(label)}</span></a>{fav_btn(p, lang, 'fav fav--box')}</div>
</div>
<div class="pp__info">
{picker}
{tag(p, lang)}
{f'<p class="pp__type">{e(typ)}</p>' if typ else ''}
{f'<p class="pp__color{" pp__color--all" if cur else ""}">{e(color)}</p>' if color else ''}
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
                  cur=(p['cat'], False), head=product_ld(p, lang, page_url))


# ——— Главная ———

def home(lang):
    cat_url = url(lang + '/catalog/')
    wide = HOME.get('hero_wide')
    wide = wide if wide and wide.get('_widths') else None
    # Горизонтальное фото (просьба заказчицы): на ноутбуке — одно на весь экран (как у muliér), на телефоне —
    # первый слайд, за ним вертикальные. На узком экране оно обрезается по бокам: кадр — по точке фокуса (кружка, сумка)
    slides = ([wide] if wide else []) + (HOME.get('hero') or [HOME['cover']])

    def hero_slide(i, s):
        # горизонтальное в высоком слайде телефона растягивается по высоте: шириной оно ~2,7 экрана
        sizes = '(min-width: 960px) 100vw, 270vw' if s is wide else '100vw'
        fx, fy = s.get('focus', [.5, .4])
        return (f'<figure class="hero__slide" style="--fx:{round(fx * 100)}%;--fy:{round(fy * 100)}%">'
                f'{home_img(s, sizes, lang, load="high" if i == 0 else "lazy")}</figure>')

    hero_slides = ''.join(hero_slide(i, s) for i, s in enumerate(slides))
    hero = f'''<section class="hero{' hero--wide' if wide else ''} rail" data-rail="slides" aria-label="{e(tx('hero', lang))}">
<div class="hero__track" data-track>{hero_slides}</div>
<div class="hero__cap"><a class="ptag hero__cta" href="{cat_url}">{e(t('catalog_btn', lang))}{ARROW}</a></div>
{rail_nav(lang, len(slides))}
</section>'''
    ps = [p for p in DATA['products'] if not sold(p)]
    news = [p for p in ps if p['is_new']] or ps[:6]
    pops = [p for p in ps if p['popular']]
    shelves = shelf('new', t('new_title', lang), f'{cat_url}?sort=new', t('see_all', lang), news, lang)
    if pops:
        shelves += shelf('pop', t('pop_title', lang), f'{cat_url}?sort=pop', t('see_all', lang), pops, lang)

    film = ''
    v = HOME.get('video')
    if v and v.get('_widths'):
        w = 1125 if 1125 in v['_widths'] else v['_widths'][-1]
        lead = t('about_body', lang).split('\n\n')[0]
        film = f'''<section class="film" aria-labelledby="film-t">
<div class="film__media">
<video class="film__v" data-film muted loop playsinline controls preload="none" width="1080" height="1350" poster="{asset(f"assets/img/home/{v['_stem']}-{w}.webp")}" aria-label="{e(tri(v.get('alt'))[lang])}"><source src="{asset('assets/video/' + v['file'])}" type="video/mp4"></video>
<button class="ptag film__btn js-only" type="button" data-film-btn>{e(t('film_play', lang))}</button>
</div>
<div class="film__txt">
<h2 class="sr-only" id="film-t">{e(t('about_title', lang))}</h2>
<p>{e(lead)}</p>
<p><a class="ulink" href="{url(lang + '/about/')}">{e(t('about_title', lang))}{ARROW}</a></p>
</div>
</section>'''

    wear = ''
    if HOME.get('wear'):
        tiles = ''.join(f'<li class="wear__i">{home_img(x, "(min-width: 960px) 20vw, (min-width: 600px) 30vw, 60vw", lang)}</li>'
                        for x in HOME['wear'] if x.get('_widths'))
        wear = f'''<section class="wear" aria-labelledby="wear-t">
<div class="sec-h"><h2 class="sec-h__t" id="wear-t">{e(t('wear_title', lang))}</h2><a class="sec-h__a" href="{ig_url()}" target="_blank" rel="noopener">@{e(DATA['instagram'])}{ARROW}</a></div>
<div class="rail rail--row" data-rail="row"><ul class="row row--wear" data-track>{tiles}</ul>{rail_nav(lang)}</div>
<p class="wear__note">{e(t('wear_note', lang))}</p>
</section>'''

    body = f'''<h1 class="sr-only">{e(t('site_title', lang))}</h1>
<div class="home">
{hero}
{shelves}
{film}
{wear}
<section class="store" aria-labelledby="store-t">
<h2 class="store__t" id="store-t">{e(t('store_title', lang))}</h2>
<p>{e(t('address', lang))}</p>
<p>{e(t('hours', lang))}</p>
<p class="mute">{e(t('delivery_world', lang))}</p>
<p><a class="ulink" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></p>
<ul class="soc">
<li><a href="{e(wa_link(t('wa_general', lang)))}" target="_blank" rel="noopener" aria-label="{e(t('wa_label', lang))}">{WA_LINE_ICON}</a></li>
<li><a href="{ig_url()}" target="_blank" rel="noopener" aria-label="Instagram">{IG_ICON}</a></li>
<li><a href="{pin_url()}" target="_blank" rel="noopener" aria-label="Pinterest">{PIN_ICON}</a></li>
</ul>
</section>
</div>'''
    return layout(lang, title=t('site_title', lang), desc=t('site_desc', lang), body=body, suffix='',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-home')


# ——— О бренде ———

def about(lang):
    pics = HOME.get('about') or []
    pics = [x for x in (pics if isinstance(pics, list) else [pics]) if x.get('_widths')]
    media = ''.join(
        f'<figure class="about__media{" about__media--more" if i else ""}">'
        f'{home_img(x, "(min-width: 960px) 40vw, 100vw", lang, load="high" if i == 0 else "lazy")}</figure>'
        for i, x in enumerate(pics))
    media = f'<div class="about__pics">{media}</div>' if media else ''
    body = f'''<div class="pb"><h1 class="pb__t">{e(t('about_title', lang))}</h1></div>
<div class="about">
{media}
<div class="about__txt">
{paras(t('about_body', lang))}
<p class="about__cta"><a class="btn" href="{url(lang + '/catalog/')}"><span>{e(t('catalog_btn', lang))}</span></a></p>
</div>
</div>'''
    return layout(lang, title=f"{t('about_title', lang)} — attré", desc=t('about_body', lang).split('\n\n')[0], body=body,
                  suffix='about/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-about', cur=('about', True))


# ——— Избранное: все карточки на странице скрыты, v4.js показывает отмеченные ———

def fav(lang):
    cards = ''.join(card(p, lang, 'h', h='h2', hidden=True) for p in ordered(DATA['products']))
    body = f'''<div class="pb"><h1 class="pb__t">{e(t('fav_title', lang))}<sup class="pb__n tnum" data-fav-n aria-hidden="true"></sup></h1></div>
<noscript><p class="empty">{e(t('fav_nojs', lang))}</p></noscript>
<div class="favp js-only">
<div class="empty" data-fav-empty><p>{e(t('fav_empty', lang))}</p><a class="ulink" href="{url(lang + '/catalog/')}">{e(t('all_catalog', lang))}{ARROW}</a></div>
<ul class="vit vit--even" data-fav-grid>{cards}</ul>
<div class="favp__send" data-fav-send hidden>
<a class="btn" href="{e(wa_link(t('wa_fav', lang)))}" target="_blank" rel="noopener" data-fav-wa>{WA_ICON}<span>{e(t('fav_send', lang))}</span></a>
<p class="favp__note">{e(t('fav_note', lang))}</p>
</div>
</div>'''
    return layout(lang, title=f"{t('fav_title', lang)} — attré", desc=t('site_desc', lang), body=body, suffix='fav/',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-fav', cur=('fav', True))


# ——— Корзина: как избранное — строки всех вещей на странице скрыты, v4.js показывает позиции из localStorage ———
# Заказ уходит готовым сообщением в WhatsApp: сервера нет, полей с личными данными нет (по закону РК их нельзя
# хранить вне Казахстана; заявку в Telegram сделаем позже на сервере в РК).

CART_MAX = 5   # одной вещи — не больше пяти; у штучной — не больше остатка


def cart_max(p):
    return min(CART_MAX, p['stock']) if p['stock'] else CART_MAX


def cart_row(p, lang, v=None):
    """Строка корзины — вещь в выбранном цвете (v). Проданная или «скоро в наличии» (статус сменился, пока вещь
    лежала в корзине) остаётся с пометкой «не войдёт в заказ» — её можно только удалить."""
    name = p['name'][lang]
    main = not v or v is p['variants'][0]
    href = item_url(p, lang) + ('' if main else f'?c={v["id"]}')
    off = sold(p) or p['soon']
    meta = p['type'][lang] if v else meta_line(p, lang)
    col = (f'<p class="ci__col">{vswatch(v, " sw--s")}<span>{e(t("p_color", lang))}: {e(v["name"][lang])}</span></p>'
           if v else '')
    remove = (f'<button class="ci__del" type="button" data-cart-del>{e(t("cart_del", lang))}'
              f'<span class="sr-only"> {e(name)}</span></button>')
    if off:
        state = (f'<p class="ci__off">{e(t("sold" if sold(p) else "soon", lang))} · {e(t("cart_off", lang))}</p>'
                 f'<div class="ci__row">{remove}</div>')
    else:
        state = f'''<p class="ci__price tnum" data-cart-sum>{price_html(p, lang)}</p>
<div class="ci__row"><div class="qty" role="group" aria-label="{e(t('cart_qty', lang))}: {e(name)}">
<button class="qty__b" type="button" data-cart-step="-1" aria-label="{e(t('cart_less', lang))}">{MINUS}</button>
<output class="qty__n tnum" data-cart-qty>1</output>
<button class="qty__b" type="button" data-cart-step="1" aria-label="{e(t('cart_more', lang))}">{PLUS}</button>
</div>{remove}</div>'''
    # data-price — цена, по которой продаём (итог и WhatsApp), data-price-old — зачёркнутая обычная, если есть скидка
    data = (f' data-slug="{p["slug"]}" data-id="{e(p["id"])}" data-name="{e(name)}" data-price="{price_now(p) or ""}"'
            + (f' data-price-old="{p["price"]}"' if p['sale'] else '')
            + f' data-max="{cart_max(p)}"' + (f' data-v="{v["id"]}" data-color="{e(v["name"][lang])}"' if v else '')
            + (' data-off' if off else ''))
    img = (v['images'] if v else p['images'])[0]
    return f'''<li class="ci{' ci--off' if off else ''}"{data} hidden>
<a class="ci__img" href="{href}" tabindex="-1" aria-hidden="true"><img src="{asset(f"assets/img/p/{img}-600.webp")}" width="600" height="800" alt="" loading="lazy" decoding="async"></a>
<div class="ci__txt">
<h2 class="ci__name"><a href="{href}">{e(name)}</a></h2>
{f'<p class="ci__meta">{e(meta)}</p>' if meta else ''}
{col}
{state}
</div>
</li>'''


def cart(lang):
    rows = ''.join(cart_row(p, lang, v) for p in ordered(DATA['products']) for v in (p['variants'] or [None]))
    body = f'''<div class="pb"><h1 class="pb__t">{e(t('cart_title', lang))}<sup class="pb__n tnum" data-cart-n aria-hidden="true"></sup></h1></div>
<noscript><p class="empty">{e(t('cart_nojs', lang))}</p></noscript>
<div class="cartp js-only">
<div class="empty" data-cart-empty hidden><p>{e(t('cart_empty', lang))}</p><a class="ulink" href="{url(lang + '/catalog/')}">{e(t('all_catalog', lang))}{ARROW}</a></div>
<ul class="cart" data-cart-list hidden>{rows}</ul>
<div class="cartp__sum" data-cart-send hidden>
<p class="cartp__total"><span class="cartp__lbl">{e(t('cart_total', lang))}</span><span class="tnum" data-cart-total>{e(t('cart_ask', lang))}</span></p>
<p class="cartp__dlv" data-cart-dlv hidden>{e(t('cart_dlv', lang))}</p>
<a class="cartp__bonus" href="{url(lang + '/info/')}#bonus"><span class="u">{e(t('bonus_short', lang))}</span> — {e(t('cart_bonus', lang))}</a>
<a class="btn btn--ink" href="{e(wa_link(t('wa_cart', lang)))}" target="_blank" rel="noopener" data-cart-wa>{WA_ICON}<span>{e(t('cart_send', lang))}</span></a>
<p class="cartp__note">{e(t('cart_note', lang))}</p>
</div>
</div>'''
    return layout(lang, title=f"{t('cart_title', lang)} — attré", desc=t('site_desc', lang), body=body, suffix='cart/',
                  og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-cart', cur=('cart', True))


PAGES = {'about/': about, 'fav/': fav, 'cart/': cart}


# ——— Покупателям ———

def info(lang):
    secs = [('bonus', t('bonus_title', lang)), ('delivery', t('delivery_title', lang)), ('returns', t('returns_title', lang)),
            ('contacts', t('contacts_title', lang)), ('seller', t('seller_title', lang))]
    toc = ''.join(f'<li><a href="#{k}"><span>{e(label)}</span></a></li>' for k, label in secs)
    toc += f'<li><a href="{url(lang + "/about/")}"><span>{e(t("about_title", lang))}</span></a></li>'
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
{sec('bonus', t('bonus_title', lang), f'<p>{e(t("bonus_body", lang))}</p>')}
{sec('delivery', t('delivery_title', lang), f'{delivery(lang)}<h3 class="dlv__t">{e(t("pay_title", lang))}</h3><p>{e(t("payment_body", lang))}</p>')}
{sec('returns', t('returns_title', lang), f'<p>{e(t("returns_body", lang))}</p>')}
{sec('contacts', t('contacts_title', lang), f"""<p>{e(t('address', lang))}<br>{e(t('hours', lang))}</p>
<ul class="ilinks">
<li><a class="ulink" href="{wa}" target="_blank" rel="noopener">WhatsApp <span class="tnum">{phone()}</span></a></li>
<li><a class="ulink" href="{ig_url()}" target="_blank" rel="noopener">Instagram @{e(DATA['instagram'])}</a></li>
<li><a class="ulink" href="{pin_url()}" target="_blank" rel="noopener">Pinterest @{e(DATA['pinterest'])}</a></li>
<li><a class="ulink" href="mailto:{e(DATA['email'])}">{e(DATA['email'])}</a></li>
<li><a class="ulink" href="{e(DATA['map_url'])}" target="_blank" rel="noopener">{e(t('map', lang))}</a></li>
</ul>""")}
{sec('seller', t('seller_title', lang), seller_lines(lang))}
</div>'''
    return layout(lang, title=f"{t('info_title', lang)} — attré", desc=t('site_desc', lang), body=body,
                  suffix='info/', og_image=abs_asset(f'assets/img/brand/og-{lang}.jpg'), page='p-info')
