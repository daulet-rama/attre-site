"""Ядро сборки attré: данные, картинки, общие помощники. Темы — themes/*.py, запуск — build.py.

Сборка сайта attré: data/ + media/ + src/ → site/.

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
ORIGIN = os.environ.get('ATTRE_ORIGIN', 'https://daulet-rama.github.io').rstrip('/')
ROOT_BASE = os.environ.get('ATTRE_BASE', '/attre-site/')  # корень сайта: общие фото, шрифты, стили
OUT_ROOT = ROOT / 'site'
CTX = {'base': ROOT_BASE, 'out': OUT_ROOT, 'theme': 'v4'}  # текущая тема: адрес и папка её страниц
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


_CAT_ITEMS = load_dir('categories')
CATS = dict_by_key(_CAT_ITEMS)
# Родитель категории: кардхолдеры и брелоки лежат внутри «аксессуаров»
PARENT = {str(d.get('key') or d['_file']).strip(): (d.get('parent') or None) for d in _CAT_ITEMS}
MATS = dict_by_key(load_dir('materials'))
# Палитра — 15 цветов заказчиц (фильтр, кружочки, выбор в админке): ключ, hex или узор принта, названия на трёх языках
COLORS = {c['key']: {'hex': c.get('hex'), 'pattern': c.get('pattern'), **tri(c.get('name'))}
          for c in json.loads((ROOT / 'data' / 'colors.json').read_text('utf-8'))}
SETTINGS = json.loads((ROOT / 'data' / 'settings.json').read_text('utf-8'))
HOME = json.loads((ROOT / 'data' / 'home.json').read_text('utf-8'))


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


PATTERNS = ('leopard', 'zebra', 'cow', 'dalmatian', 'croc')   # узор кружочка цвета: принты и кроко-тиснение


def clean_variants(d, f):
    """Цвета вещи — у каждого свои фото: variants = [{color, name, hex, pattern, material, images}].
    Первый цвет — основной: его фото в каталоге и на странице товара, пока человек не выбрал другой.
    color — ключ палитры (фильтр «цвет»), name — как назвать оттенок покупателю (молочный, карамельный…),
    hex — цвет кружочка (если не задан — из палитры). Два оттенка одного ключа — разные цвета: ?c=brown и ?c=brown-2."""
    out, seen = [], {}
    for n, v in enumerate(d.get('variants') or [], 1):
        if not isinstance(v, dict) or v.get('published') is False:
            continue
        key = v.get('color')
        if key not in COLORS:
            warn(f'products/{f}.json: цвет № {n}: нет цвета «{key}» в data/colors.json — пропущен')
            continue
        srcs = []
        for x in v.get('images') or []:
            x = x.get('image') if isinstance(x, dict) else x
            if not x:
                continue
            path = MEDIA / Path(str(x)).name
            if path.exists():
                srcs.append(path)
            else:
                warn(f'products/{f}.json: цвет «{key}»: нет файла фото {x}')
        if not srcs:
            warn(f'products/{f}.json: цвет «{key}»: нет ни одного фото — пропущен')
            continue
        seen[key] = seen.get(key, 0) + 1
        name = tri(v.get('name'))
        raw = v.get('materials') or ([v['material']] if v.get('material') else [])
        for m in raw:
            if m not in MATS and m != 'other':
                warn(f'products/{f}.json: цвет «{key}»: нет материала «{m}» — не учитывается')
        hexv = str(v.get('hex') or '').strip()
        out.append({
            'id': key if seen[key] == 1 else f'{key}-{seen[key]}',
            'key': key,
            'name': {c: name[c] or COLORS[key][c] for c in CODES},
            'hex': hexv if re.fullmatch(r'#[0-9a-fA-F]{6}', hexv) else COLORS[key]['hex'],
            'pattern': v.get('pattern') if v.get('pattern') in PATTERNS else COLORS[key]['pattern'],
            'materials': [m for m in raw if m in MATS],
            'srcs': srcs,
        })
    return out


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
    mats = [m for m in (d.get('materials') or ([d['material']] if d.get('material') else [])) if m]
    for m in mats:
        if m not in MATS:
            warn(f'products/{f}.json: нет материала «{m}» — не учитывается')
    mats = [m for m in mats if m in MATS]
    colors = [c for c in (d.get('colors') or []) if c in COLORS]
    for c in d.get('colors') or []:
        if c not in COLORS:
            warn(f'products/{f}.json: нет цвета «{c}» в data/colors.json — не учитывается')
    variants = clean_variants(d, f)
    color = tri(d.get('color'))
    srcs = []
    if variants:   # цвета со своими фото: фильтр, материалы и подпись «цвет» берутся из них
        colors = list(dict.fromkeys(v['key'] for v in variants))
        mats = list(dict.fromkeys(m for v in variants for m in v['materials'])) or mats
        color = {c: ', '.join(v['name'][c] for v in variants) for c in CODES}
        srcs = variants[0]['srcs']
    for x in [] if variants else d.get('images') or []:
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
    price = int(price_v) if price_v else None
    # Цена со скидкой (sale_price): только при обычной цене и меньше неё — так же проверяет админка; иначе скидки нет
    sale_v = num(d.get('sale_price'))
    sale = int(sale_v) if sale_v else None
    if sale and not (price and sale < price):
        warn(f'products/{f}.json: цена со скидкой {sale} — {"нет обычной цены" if not price else "не меньше обычной"}, скидки нет')
        sale = None
    stock = num(d.get('stock'))
    return {
        'slug': f, 'id': str(d.get('id') or f), 'order': num(d.get('order')) or 9999,
        'cat': d['cat'], 'material': mats[0] if mats else None, 'materials': mats, 'colors': colors,
        'is_new': bool(d.get('new')), 'popular': bool(d.get('popular')), 'soon': bool(d.get('soon')),
        'name': name, 'type': tri(d.get('type')), 'color': color, 'desc': tri(d.get('desc')),
        'strap': strap if strap['ru'] else None,
        'size': [f'{v:g}' for v in dims] if all(dims) else None,
        'price': price,                                      # нет цены — «цена по запросу»
        'sale': sale,                                        # цена со скидкой или None — см. price_now()
        'stock': int(stock) if stock is not None else None,  # нет остатка — просто «в наличии»
        'srcs': srcs, 'focus': d.get('focus') or {}, 'variants': variants,
    }


PRODUCTS = sorted(filter(None, (clean_product(d) for d in load_dir('products'))), key=lambda p: (p['order'], p['id']))
DATA = {'products': PRODUCTS, **SETTINGS}


def e(s):
    return html.escape(str(s), quote=True)


def t(key, lang, **kw):
    """Текст интерфейса. {address} и {ig} в любом тексте — адрес магазина и ник Instagram из настроек
    (меняются в админке — и все тексты с ними сразу верные)."""
    s = T[key][lang]
    for k, v in kw.items():
        s = s.replace('{' + k + '}', str(v))
    if '{address}' in s:
        s = s.replace('{address}', T['address'][lang])
    if '{ig}' in s:
        s = s.replace('{ig}', '@' + str(SETTINGS.get('instagram') or ''))
    return s


def url(path=''):
    """Адрес страницы текущей темы."""
    return CTX['base'] + path


def abs_url(path=''):
    return ORIGIN + CTX['base'] + path


def asset(path):
    """Общие файлы (фото, шрифт, стили, скрипты) лежат в корне сайта и общие для всех тем."""
    return ROOT_BASE + path


def abs_asset(path):
    return ORIGIN + ROOT_BASE + path


def set_theme(name, sub):
    CTX.update(theme=name, base=ROOT_BASE + sub, out=OUT_ROOT / sub if sub else OUT_ROOT)


def money(n, lang):
    s = f'{n:,}' if lang == 'en' else f'{n:,}'.replace(',', NBSP)
    return s + NBSP + '₸'


def price_now(p):
    """Цена, по которой продаём: со скидкой, если она есть. Она — в корзине и её итоге, в WhatsApp, в фильтре,
    сортировке и бегунке цены, в разметке для поисковиков; обычная цена остаётся зачёркнутой рядом."""
    return p['sale'] or p['price']


def price_text(p, lang):
    return money(price_now(p), lang) if p['price'] else t('price_request', lang)


def wa_link(text):
    return f"https://wa.me/{DATA['whatsapp']}?text={quote(text)}"


def asset_version(*paths):
    h = hashlib.sha1()
    for p in paths:
        h.update((ROOT / p).read_bytes())
    return h.hexdigest()[:8]



# Значок WhatsApp — Simple Icons (CC0), https://simpleicons.org/?q=whatsapp
WA_ICON = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
           '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg>')


def sold(p):
    return p['stock'] == 0


def meta_line(p, lang):
    return ' · '.join(x for x in (p['type'][lang], p['color'][lang]) if x)


def item_url(p, lang):
    return url(f"{lang}/p/{p['slug']}/")


def img_stem(p, vid, i):
    """Имя нарезанного фото: altea-3 (вещь без цветов) или altea-black-2 (фото цвета)."""
    return f"{p['slug']}-{vid}-{i + 1}" if vid else f"{p['slug']}-{i + 1}"


def img_srcset(stem):
    return f"{asset(f'assets/img/p/{stem}-600.webp')} 600w, {asset(f'assets/img/p/{stem}-1200.webp')} 1200w"


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


CACHE = ROOT / '.cache' / 'img'   # нарезанные фото между сборками (в git не идёт)


def cache_key(src, *params):
    """Ключ кэша: содержимое исходника + параметры нарезки (новое фото или другой кадр — новый ключ)."""
    h = hashlib.sha1(Path(src).read_bytes()).hexdigest()
    return hashlib.sha1('|'.join([h, *map(str, params)]).encode()).hexdigest()[:24]


def from_cache(key, outs):
    """outs: {суффикс: путь в site/}. Всё есть в кэше — копирует и возвращает True."""
    hits = {sfx: CACHE / f'{key}{sfx}' for sfx in outs}
    if not all(h.exists() for h in hits.values()):
        return False
    for sfx, dst in outs.items():
        shutil.copyfile(hits[sfx], dst)
    return True


def to_cache(key, outs):
    CACHE.mkdir(parents=True, exist_ok=True)
    for sfx, dst in outs.items():
        shutil.copyfile(dst, CACHE / f'{key}{sfx}')


def render_images():
    from PIL import Image
    out = OUT_ROOT / 'assets' / 'img' / 'p'
    out.mkdir(parents=True, exist_ok=True)
    for p in DATA['products']:
        for vi, v in enumerate(p['variants'] or [{'id': None, 'srcs': p['srcs']}]):
            shots = []
            for i, src in enumerate(v['srcs']):
                focus = p['focus'] if vi == 0 and i == 0 else {}
                stem = img_stem(p, v['id'], i)
                outs = {f'-{w}.webp': out / f'{stem}-{w}.webp' for w in (600, 1200)}
                key = cache_key(src, 'p34', json.dumps(focus, sort_keys=True))
                if not from_cache(key, outs):
                    frame = fit_34(open_rgb(src), focus)
                    for width in (600, 1200):
                        frame.resize((width, round(width * 4 / 3)), Image.LANCZOS).save(
                            outs[f'-{width}.webp'], 'WEBP', quality=86, method=6)
                    to_cache(key, outs)
                shots.append(stem)
                if vi == 0 and i == 0:   # картинка для соцсетей: квадрат, вещь по центру
                    og_out = {'-og.jpg': out / f"{p['slug']}-og.jpg"}
                    if not from_cache(key, og_out):
                        og = Image.open(outs['-1200.webp']).convert('RGB').resize((900, 1200), Image.LANCZOS)
                        sq = Image.new('RGB', (1200, 1200), og.getpixel((2, 2)))
                        sq.paste(og, (150, 0))
                        sq.save(og_out['-og.jpg'], 'JPEG', quality=88, optimize=True, progressive=True)
                        to_cache(key, og_out)
            v['images'] = shots
            if vi == 0:
                p['images'] = shots

    hout = OUT_ROOT / 'assets' / 'img' / 'home'
    hout.mkdir(parents=True, exist_ok=True)
    about = HOME.get('about') or []   # фото «о бренде»: одно или список
    extra = [x for x in (HOME.get('hero_wide'), *(about if isinstance(about, list) else [about]), HOME.get('video')) if x]
    for item in [HOME['cover'], *HOME['banners'], *HOME.get('hero', []), *HOME.get('wear', []), *extra]:
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
        widths = [w_ for w_ in (750, 1125, 1600) if w_ <= frame.width * 1.02]
        if frame.width > (widths[-1] if widths else 0) * 1.05:   # исходник крупнее ступени — отдаём и его размер
            widths.append(frame.width)
        outs = {f'-{width}.webp': hout / f'{stem}-{width}.webp' for width in widths}
        key = cache_key(src, 'home', ratio, fx, fy, *widths)
        if not from_cache(key, outs):
            for width in widths:
                frame.resize((width, round(width / ratio)), Image.LANCZOS).save(
                    outs[f'-{width}.webp'], 'WEBP', quality=86, method=6)
            to_cache(key, outs)
        item['_stem'] = stem
        item['_widths'] = widths
        item['_ratio'] = ratio
    if HOME.get('video'):   # видео уже сжато (H.264, 4:5, ~2,4 МБ) — кладём как есть
        vout = OUT_ROOT / 'assets' / 'video'
        vout.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HOME_MEDIA / HOME['video']['file'], vout / HOME['video']['file'])


def home_srcset(item):
    return ', '.join(f"{asset(f'assets/img/home/{item['_stem']}-{w}.webp')} {w}w" for w in item['_widths'])


def in_cat(p, c):
    """Вещь в категории c — напрямую или через подкатегорию (кардхолдер ∈ аксессуары)."""
    return p['cat'] == c or PARENT.get(p['cat']) == c


def top_cat(key):
    return PARENT.get(key) or key


def present_cats():
    """Верхние категории, где есть вещи (сумки, аксессуары)."""
    return [c for c in CATS if not PARENT.get(c) and any(in_cat(p, c) for p in DATA['products'])]


def subcats(c):
    """Подкатегории c, где есть вещи."""
    return [k for k in CATS if PARENT.get(k) == c and any(p['cat'] == k for p in DATA['products'])]


def leaf_cats():
    """Конечные разделы для меню: сумки, кардхолдеры, брелоки (родитель без своих вещей не показывается)."""
    out = []
    for c in present_cats():
        subs = subcats(c)
        if subs:
            out += subs
        else:
            out.append(c)
    return out


def cat_pages():
    """Все страницы категорий: верхние и подкатегории."""
    return present_cats() + [k for c in present_cats() for k in subcats(c)]


def ordered(items):
    # Проданные в конце, но не удаляются: старые ссылки из Instagram и WhatsApp живут
    return sorted(items, key=lambda p: sold(p))


def similar(p):
    others = [q for q in DATA['products'] if q['slug'] != p['slug'] and not sold(q)]
    others.sort(key=lambda q: (top_cat(q['cat']) != top_cat(p['cat']), q['order']))
    return others[:4]


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
  location.replace('{ROOT_BASE}' + t + '/' + location.search + location.hash);
}})();
</script>
<noscript><meta http-equiv="refresh" content="0; url={target}"></noscript>
</head>
<body><p><a href="{ROOT_BASE}ru/">Русский</a> · <a href="{ROOT_BASE}kz/">Қазақша</a> · <a href="{ROOT_BASE}en/">English</a></p></body>
</html>
'''


def not_found(css):
    """Страница 404 — по любому неверному адресу, поэтому все адреса в ней от корня сайта. css — стили темы
    с ?v=, тот же адрес, что у её страниц (браузер берёт их из кэша); оформление — .nf в стилях темы."""
    rows = ''.join(
        f'<p lang="{l["html"]}">{e(t("nf_title", l["code"]))} <a class="ulink" href="{ROOT_BASE}{l["code"]}/catalog/">{e(t("nf_link", l["code"]))}</a></p>'
        for l in LANGS)
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>404 — attré</title>
<link rel="stylesheet" href="{e(css)}">
</head>
<body>
<main class="nf">
<img src="{ROOT_BASE}assets/img/brand/logo-black.svg" alt="attré" width="62" height="24">
<h1>404</h1>
{rows}
</main>
</body>
</html>
'''


def write(path, text):
    f = CTX['out'] / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, 'utf-8')


