"""Данные сайта: чтение, проверка и запись (DESIGN.md → «Данные», «API»).

Формат файлов — ровно как у сайта: json.dumps(obj, ensure_ascii=False, indent=2) + "\\n". Неизвестные поля
сохраняются как были (и порядок ключей тоже). Каждая запись — под store.write_lock: свежий снимок ветки →
проверка → один коммит (данные и фото вместе). Если файл изменился после того, как его открыли, — 409.

Ошибки — CatalogError с понятным текстом по-русски и полем формы (`field`, путь как в JSON: `name.ru`,
`variants.0.images`, `contacts.whatsapp`…).
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import re
import secrets
import unicodedata
from contextlib import contextmanager
from pathlib import PurePosixPath
from typing import Any

from .images import PREVIEW_VERSION, UPLOAD_RE, Uploads
from .store import ConflictError, Snapshot, Store, _LRU

log = logging.getLogger('attre.catalog')

LOCK_WAIT = 90          # секунд ждать, пока закончится чужое сохранение (GitHub медленный), потом — понятная ошибка
MSG_LOCKED = 'Сейчас сохраняется другое изменение — попробуйте через минуту.'

PRODUCTS = 'data/products/'
CATEGORIES = 'data/categories/'
MATERIALS = 'data/materials/'
COLORS = 'data/colors.json'
SETTINGS = 'data/settings.json'
I18N = 'data/i18n.json'
MEDIA = 'media/products/'
LANGS = ('ru', 'kz', 'en')
LEGACY = ('images', 'colors', 'color', 'materials', 'material')      # старые поля товара без variants
VARIANT_SITE_KEYS = ('hex', 'pattern', 'published')                  # поля цвета, которые понимает core.py
PATTERNS = ('leopard', 'zebra', 'cow', 'dalmatian', 'croc')          # узоры кружочка — как core.PATTERNS
HEX_RE = re.compile(r'#[0-9a-fA-F]{6}')
EXTRA_MAX_BYTES, EXTRA_MAX_DEPTH = 2000, 4      # «чужие» поля, которые сохраняем как были: только небольшие
# Управляющие символы направления текста (LRE…RLO, LRI…PDI): ими можно «перевернуть» название в каталоге и в git
BIDI = dict.fromkeys([*range(0x202A, 0x202F), *range(0x2066, 0x206A)])
# Старые ключи цветов → ключи палитры из 15 цветов: в коммите палитры «white» стал «молочным», «mustard» —
# «жёлтым», «turquoise» убран (ближе всего «голубой»). «animal» (леопард, корова или зебра) не угадываем.
LEGACY_COLOR_ALIASES = {'white': 'milky', 'mustard': 'yellow', 'turquoise': 'light-blue'}
RESERVED_SLUGS = {'order', 'new'}

SLUG_RE = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}')
MEDIA_NAME_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?:jpe?g|png|webp)', re.I)

LIMITS = {
    'name_max': 60, 'type_max': 60, 'shade_max': 60, 'text_max': 2000,
    'photos_min': 1, 'photos_max': 8, 'colors_max': 20,
    'price_max': 10_000_000, 'stock_max': 100_000, 'size_min': 1, 'size_max': 200,
}
LANG_NOTE = {'ru': '', 'kz': ' (на казахском)', 'en': ' (на английском)'}

MSG_CONFLICT_PRODUCT = ('Этот товар только что изменили — на другом устройстве или в другой вкладке. '
                        'Обновите страницу, чтобы увидеть последние изменения, и внесите свои ещё раз.')
MSG_CONFLICT_SETTINGS = ('Настройки магазина только что изменили на другом устройстве. '
                         'Обновите страницу и внесите изменения ещё раз.')
MSG_CONFLICT_DATA = 'Данные только что изменились. Обновите страницу и попробуйте ещё раз.'
MSG_RELOAD = 'Обновите страницу и попробуйте ещё раз.'
MSG_SALE = 'Цена со скидкой — целое число тенге больше нуля, без копеек и букв, например 36 000.'
MSG_SALE_NO_PRICE = 'Сначала укажите обычную цену — скидка считается от неё.'


class CatalogError(Exception):
    status = 400

    def __init__(self, message: str, field: str | None = None, status: int | None = None):
        super().__init__(message)
        self.message, self.field = message, field
        if status:
            self.status = status

    def to_json(self) -> dict:
        return {'error': self.message, **({'field': self.field} if self.field else {})}


class NotFound(CatalogError):
    status = 404


class Conflict(CatalogError):
    status = 409


# ——————————————————————————— помощники ———————————————————————————

def dumps(obj: Any) -> bytes:
    """Формат файлов сайта."""
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
    'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ә': 'a', 'ғ': 'g', 'қ': 'k', 'ң': 'n', 'ө': 'o', 'ұ': 'u', 'ү': 'u', 'һ': 'h', 'і': 'i',
    'ß': 'ss', 'æ': 'ae', 'œ': 'oe', 'ø': 'o', 'ł': 'l', 'đ': 'd', 'ð': 'd', 'þ': 'th', 'ı': 'i',
}


def translit(text: str, max_len: int = 50) -> str:
    """Название (русское, казахское, латиница с диакритикой) → адрес страницы: только a-z, 0-9 и дефис."""
    out = []
    for ch in str(text or '').lower():
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
            continue
        base = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c))
        out.append(base if base.isascii() else '-')
    slug = re.sub(r'[^a-z0-9]+', '-', ''.join(out).lower()).strip('-')
    if len(slug) > max_len:
        cut = slug[:max_len]
        slug = cut.rsplit('-', 1)[0] if '-' in cut else cut
    return slug.strip('-')


def tri(v: Any) -> dict:
    """Текст на трёх языках как есть (без подстановки русского): {'ru','kz','en'} — строки."""
    if isinstance(v, str):
        v = {'ru': v}
    v = v if isinstance(v, dict) else {}
    return {l: str(v.get(l) or '') for l in LANGS}


def site_order(v: Any) -> float:
    """Порядок так, как его понимает сайт (core.py: `num(order) or 9999`): 0, минус и не число — в конец."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 9999.0
    return f if f > 0 else 9999.0


def num_out(v: Any) -> int | float | None:
    """Число из файла для формы: 45000.0 → 45000; не число → None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, str):
        try:
            v = float(v.replace(',', '.').replace(' ', ''))
        except ValueError:
            return None
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return int(v) if float(v).is_integer() else v


def money(n: int) -> str:
    """45000 → «45 000 ₸» (как в форме и на сайте)."""
    return f'{n:,}'.replace(',', ' ') + ' ₸'


def site_money(v: Any) -> int | None:
    """Цена так, как её читает сайт (core.clean_product: num() и int()): float(v) без копеек; 0, минус,
    не число — None. «45000», 45000.7 — 45000; «45 000» с пробелом сайт не понимает — None."""
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return int(f) if math.isfinite(f) and f >= 1 else None


def sale_of(price: Any, sale: Any) -> int | None:
    """Скидка так, как её понимает сайт: цена со скидкой — только если цена задана и 0 < sale_price < price,
    иначе скидки нет (то же правило у сайта и в превью админки). Числа — как их читает сайт: файл, исправленный
    руками («36000», 36000.5), в списке товаров выглядит так же, как на сайте."""
    p, s = site_money(price), site_money(sale)
    return s if p and s and s < p else None


def media_path(x: Any) -> str | None:
    """Ссылка на фото из файла товара (строка или {image}) → media/products/<имя> (сайт тоже берёт только имя)."""
    x = x.get('image') if isinstance(x, dict) else x
    if not isinstance(x, str) or not x.strip():
        return None
    name = PurePosixPath(x.strip().replace('\\', '/')).name
    return MEDIA + name if MEDIA_NAME_RE.fullmatch(name) else None


def refs(doc: dict | None) -> set[str]:
    """Все фото, на которые ссылается файл товара (старые images и фото цветов)."""
    if not isinstance(doc, dict):
        return set()
    items = list(doc['images']) if isinstance(doc.get('images'), list) else []
    variants = doc['variants'] if isinstance(doc.get('variants'), list) else []
    for v in variants:
        if isinstance(v, dict) and isinstance(v.get('images'), list):
            items += v['images']
    return {p for p in map(media_path, items) if p}


def media_url(path: str, sha: str | None = None, width: int = 480) -> str:
    url = f'/api/media/{PurePosixPath(path).name}?w={width}'
    return url + (f'&v={sha[:12]}-{PREVIEW_VERSION}' if sha else '')


def _dedupe(items):
    return list(dict.fromkeys(x for x in items if x))


def _text(v: Any, multiline: bool) -> str:
    if v is None:
        return ''
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        raise ValueError
    s = str(v).replace('\r\n', '\n').replace('\r', '\n').translate(BIDI)
    s = ''.join(ch for ch in s if ch in '\n\t' or unicodedata.category(ch) not in ('Cc', 'Cs'))   # управляющие символы
    if multiline:
        s = '\n'.join(line.rstrip() for line in s.split('\n'))
        s = re.sub(r'\n{3,}', '\n\n', s)
    else:
        s = re.sub(r'\s+', ' ', s)
    return s.strip()


def tri_in(v: Any, field: str, label: str, max_len: int, *, required: bool = False, multiline: bool = False,
           required_msg: str | None = None) -> dict:
    """Текст на трёх языках из формы. Можно прислать строку — это русский."""
    if isinstance(v, str) or v is None:
        v = {'ru': v or ''}
    if not isinstance(v, dict):
        raise CatalogError(f'{label}: {MSG_RELOAD.lower()}', field)
    out = {}
    for lang in LANGS:
        try:
            s = _text(v.get(lang), multiline)
        except ValueError:
            raise CatalogError(f'{label}{LANG_NOTE[lang]}: {MSG_RELOAD.lower()}', f'{field}.{lang}') from None
        if len(s) > max_len:
            raise CatalogError(f'{label}{LANG_NOTE[lang]} — не длиннее {max_len} символов (сейчас {len(s)}).',
                               f'{field}.{lang}')
        out[lang] = s
    if required and not out['ru']:
        raise CatalogError(required_msg or f'{label}: напишите текст.', f'{field}.ru')
    return out


def int_in(v: Any, field: str, lo: int, hi: int, msg: str) -> int | None:
    """Целое число или None (пустое поле). «45 000» и 45000.0 — можно, 1.5 и «abc» — нет."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise CatalogError(msg, field)
    if isinstance(v, str):
        s = re.sub(r'[\s\u00a0\u202f₸]', '', v)
        if not re.fullmatch(r'\d{1,12}', s):
            raise CatalogError(msg, field)
        v = int(s)
    if isinstance(v, float):
        if not math.isfinite(v) or not v.is_integer():
            raise CatalogError(msg, field)
        v = int(v)
    if not isinstance(v, int) or not lo <= v <= hi:
        raise CatalogError(msg, field)
    return v


def sale_in(v: Any, price: int | None) -> int | None:
    """Цена со скидкой из формы: пусто — скидки нет; иначе целое, меньше обычной цены (а она должна быть)."""
    sale = int_in(v, 'sale_price', 1, LIMITS['price_max'], MSG_SALE)
    if sale is None:
        return None
    if not price:                       # цены нет (или 0 — на сайте это тоже «цена по запросу»)
        raise CatalogError(MSG_SALE_NO_PRICE, 'sale_price')
    if sale >= price:
        raise CatalogError(f'Цена со скидкой должна быть меньше обычной ({money(price)}).', 'sale_price')
    return sale


def size_in(v: Any, field: str, label: str) -> int | float | None:
    lo, hi = LIMITS['size_min'], LIMITS['size_max']
    msg = f'{label} — число сантиметров от {lo} до {hi}. Не знаете — оставьте пустым.'
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise CatalogError(msg, field)
    if isinstance(v, str):
        try:
            v = float(v.strip().replace(',', '.'))
        except ValueError:
            raise CatalogError(msg, field) from None
    if not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise CatalogError(msg, field)
    v = round(float(v), 1)
    return int(v) if v.is_integer() else v


def bool_in(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v or '').strip().lower() in ('1', 'true', 'yes', 'on', 'да')


def _put_at(d: dict, old_key: str, new_key: str, value: Any) -> dict:
    """Заменить ключ old_key на new_key на том же месте (чтобы в истории git был понятный дифф)."""
    return {(new_key if k == old_key else k): (value if k == old_key else v) for k, v in d.items()}


def _put_after(d: dict, after: str, key: str, value: Any) -> dict:
    """Поле key — на своём месте, а новое — сразу после after (в истории git — одна новая строка).
    value None — поля в файле нет совсем."""
    if value is None:
        return {k: v for k, v in d.items() if k != key}
    if key in d or after not in d:
        return {**d, key: value}
    out = {}
    for k, v in d.items():
        out[k] = v
        if k == after:
            out[key] = value
    return out


def _hash(v: Any) -> str:
    return hashlib.sha1(json.dumps(v, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:12]


def small_json(v: Any, max_bytes: int = EXTRA_MAX_BYTES, max_depth: int = EXTRA_MAX_DEPTH) -> bool:
    """Значение — обычные данные JSON, неглубокое (≤ max_depth) и небольшое (≤ max_bytes в файле).
    Проверка без рекурсии: вложенность в сотни уровней не роняет сервер."""
    stack = [(v, 1)]
    while stack:
        x, depth = stack.pop()
        if isinstance(x, (dict, list)):
            if depth > max_depth:
                return False
            items = x.items() if isinstance(x, dict) else enumerate(x)
            for k, y in items:
                if isinstance(x, dict) and not isinstance(k, str):
                    return False
                stack.append((y, depth + 1))
        elif x is not None and not isinstance(x, (str, int, float, bool)):
            return False
        elif isinstance(x, float) and not math.isfinite(x):
            return False
    return len(json.dumps(v, ensure_ascii=False)) <= max_bytes


class _Ctx:
    """Справочники одного снимка: палитра, категории, материалы, какие фото есть в репозитории."""

    def __init__(self, cat: 'Catalog', snap: Snapshot):
        self.snap = snap
        self.palette = cat.palette(snap)
        self.colors = [c['key'] for c in self.palette]
        self.categories = cat.categories(snap)
        self.cats = {c['key']: c for c in self.categories}
        parents = {c.get('parent') for c in self.categories if c.get('parent')}
        self.leaves = {k for k in self.cats if k not in parents}
        self.materials = cat.materials(snap)
        self.mats = [m['key'] for m in self.materials]
        self.media = set(snap.list(MEDIA))


# ——————————————————————————— каталог ———————————————————————————

class Catalog:
    def __init__(self, store: Store, uploads: Uploads, site_url: str = ''):
        self.store, self.uploads, self.site_url = store, uploads, site_url
        self._json = _LRU(max_items=2000)          # blob sha → разобранный JSON (не менять! отдаём копии)

    # ——— чтение файлов ———
    def _parse(self, snap: Snapshot, path: str, sha: str, data: bytes | None = None):
        obj = self._json.get(sha)
        if obj is None:
            raw = data if data is not None else snap.read(path)
            try:
                obj = json.loads((raw or b'').decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise CatalogError(f'Файл {path} повреждён. Сообщите Даулету.', status=500) from None
            self._json.put(sha, obj)
        return obj

    def _load(self, snap: Snapshot, path: str, default: Any = ...) -> Any:
        sha = snap.blob_sha(path)
        if sha is None:
            if default is ...:
                raise CatalogError(f'В репозитории нет файла {path}. Сообщите Даулету.', status=500)
            return copy.deepcopy(default)
        return copy.deepcopy(self._parse(snap, path, sha))

    def _load_dir(self, snap: Snapshot, prefix: str) -> dict[str, Any]:
        files = {p: s for p, s in snap.list(prefix).items()
                 if p.endswith('.json') and '/' not in p[len(prefix):]}
        need = [p for p, s in files.items() if self._json.get(s) is None]
        blobs = snap.read_many(need) if need else {}
        out = {}
        for p, s in sorted(files.items()):
            try:
                obj = self._parse(snap, p, s, blobs.get(p))
            except CatalogError:
                log.warning('файл %s не читается — пропущен', p)
                continue
            if isinstance(obj, dict):
                out[p[len(prefix):-len('.json')]] = copy.deepcopy(obj)
        return out

    def raw_products(self, snap: Snapshot) -> dict[str, dict]:
        """slug → содержимое файла (только файлы с правильным именем, как у сайта)."""
        return {s: d for s, d in self._load_dir(snap, PRODUCTS).items() if SLUG_RE.fullmatch(s)}

    def palette(self, snap: Snapshot) -> list[dict]:
        items = self._load(snap, COLORS)
        if not isinstance(items, list):
            raise CatalogError(f'Файл {COLORS} повреждён. Сообщите Даулету.', status=500)
        out = []
        for c in items:
            if isinstance(c, dict) and isinstance(c.get('key'), str):
                out.append({**c, 'name': tri(c.get('name'))})
        return out

    def _keyed(self, snap: Snapshot, prefix: str) -> list[dict]:
        items = []
        for stem, d in self._load_dir(snap, prefix).items():
            key = str(d.get('key') or stem).strip()
            items.append({**d, 'key': key, 'name': tri(d.get('name'))})
        items.sort(key=lambda d: (num_out(d.get('order')) or 999, d['key']))
        return items

    def categories(self, snap: Snapshot) -> list[dict]:
        return self._keyed(snap, CATEGORIES)

    def materials(self, snap: Snapshot) -> list[dict]:
        return self._keyed(snap, MATERIALS)

    def ctx(self, snap: Snapshot) -> _Ctx:
        return _Ctx(self, snap)

    # ——— товар для формы ———
    def _form_variants(self, raw: dict, ctx: _Ctx) -> list[dict]:
        def images(items):
            return [p for p in _dedupe(map(media_path, items if isinstance(items, list) else [])) if p in ctx.media]

        def materials(d):
            items = d['materials'] if isinstance(d.get('materials'), list) and d['materials'] else [d.get('material')]
            items = _dedupe(m for m in items if isinstance(m, str) and m in ctx.mats)    # как core.py
            # material — основной (для формы), materials — все, если их несколько (так бывает у старых товаров)
            return {'material': items[0] if items else None, **({'materials': items} if len(items) > 1 else {})}

        vs = raw.get('variants')
        if isinstance(vs, list) and any(isinstance(v, dict) for v in vs):
            out = []
            for v in vs:
                if not isinstance(v, dict):
                    continue
                fixed = {'color': v.get('color') if v.get('color') in ctx.colors else '', 'name': tri(v.get('name')),
                         **materials(v), 'images': images(v.get('images'))}
                x = {}
                for k, val in v.items():      # ключи — в порядке файла: так он и вернётся при сохранении
                    if k in ('material', 'materials'):
                        x.update({m: fixed[m] for m in ('material', 'materials') if m in fixed and m not in x})
                    elif k in fixed:
                        x[k] = fixed[k]
                    elif isinstance(k, str):
                        x[k] = copy.deepcopy(val)
                x.update({k: val for k, val in fixed.items() if k not in x})
                out.append(x)
            return out
        # Наследие: товар без variants — старые фото становятся одним цветом. Ключ — первый цвет из старого
        # списка colors, который есть в палитре (с учётом переименований палитры); нет — пусто, форма попросит выбрать.
        colors = raw.get('colors') if isinstance(raw.get('colors'), list) else []
        keys = [c if c in ctx.colors else LEGACY_COLOR_ALIASES.get(c) for c in colors if isinstance(c, str)]
        return [{'color': next((k for k in keys if k in ctx.colors), ''), 'name': tri({}), **materials(raw),
                 'images': images(raw.get('images'))}]

    def form(self, slug: str, raw: dict, ctx: _Ctx) -> dict:
        """Товар «как в файле + slug», но уже в новом виде: variants вместо старых полей, все поля на месте."""
        p = {k: copy.deepcopy(v) for k, v in raw.items() if k not in LEGACY}
        size = raw.get('size') if isinstance(raw.get('size'), dict) else {}
        p.update({
            'id': str(raw.get('id') or ''),
            'published': raw.get('published') is not False,
            'order': num_out(raw.get('order')),
            'cat': str(raw.get('cat') or ''),
            'name': tri(raw.get('name')), 'type': tri(raw.get('type')),
            'new': bool(raw.get('new')), 'popular': bool(raw.get('popular')), 'soon': bool(raw.get('soon')),
            # sale_price — как в файле (даже неправильная: форма покажет её, а проверка объяснит, что не так)
            'price': num_out(raw.get('price')), 'sale_price': num_out(raw.get('sale_price')),
            'stock': num_out(raw.get('stock')),
            'desc': tri(raw.get('desc')), 'strap': tri(raw.get('strap')),
            'size': {**size, **{k: num_out(size.get(k)) for k in 'whd'}},
            'variants': self._form_variants(raw, ctx),
            'slug': slug,
        })
        return p

    # ——— списки ———
    def products(self) -> list[dict]:
        """Для сетки товаров: коротко, по порядку как на сайте. name и type — по-русски (строкой)."""
        snap = self.store.snapshot()
        ctx = self.ctx(snap)
        out = []
        for slug, raw in self.raw_products(snap).items():
            p = self.form(slug, raw, ctx)
            vs = p['variants']
            main = next((v['images'][0] for v in vs if v['images']), None)
            out.append({
                'slug': slug, 'id': p['id'], 'name': p['name']['ru'], 'cat': p['cat'], 'type': p['type']['ru'],
                # скидка — как на сайте: из файла как есть (p — уже для формы, там «36 000» стало числом)
                'price': p['price'], 'sale_price': sale_of(raw.get('price'), raw.get('sale_price')),
                'stock': p['stock'], 'soon': p['soon'], 'new': p['new'],
                'popular': p['popular'], 'published': p['published'], 'order': p['order'],
                'colors': [v['color'] for v in vs if v['color']],
                'thumb': media_url(main, snap.blob_sha(main)) if main else None,
                'photos': sum(len(v['images']) for v in vs),
            })
        out.sort(key=lambda x: (site_order(x['order']), x['id']))
        return out

    def meta(self, users: list[str]) -> dict:
        snap = self.store.snapshot()
        ctx = self.ctx(snap)
        raws = self.raw_products(snap)
        parent = {c['key']: c.get('parent') or None for c in ctx.categories}
        cats = []
        for c in ctx.categories:
            k = c['key']
            count = sum(1 for d in raws.values() if d.get('cat') == k or parent.get(d.get('cat')) == k)
            cats.append({'key': k, 'name': c['name'], 'parent': parent[k], 'order': num_out(c.get('order')),
                         'count': count, 'leaf': k in ctx.leaves})
        types: dict[str, dict] = {}
        for d in raws.values():
            t = tri(d.get('type'))
            if t['ru'].strip():
                types.setdefault(t['ru'].strip().casefold(), t)
        return {
            'palette': ctx.palette,
            'categories': cats,
            'materials': [{'key': m['key'], 'name': m['name'], 'order': num_out(m.get('order'))}
                          for m in ctx.materials],
            'types': sorted(types.values(), key=lambda t: t['ru'].casefold()),
            'site_url': self.site_url,
            'users': list(users),
            'limits': dict(LIMITS),
        }

    def product(self, slug: str) -> dict:
        if not SLUG_RE.fullmatch(slug or ''):
            raise NotFound('Товар не найден.')
        snap = self.store.snapshot()
        path = f'{PRODUCTS}{slug}.json'
        sha = snap.blob_sha(path)
        if sha is None:
            raise NotFound('Товар не найден — возможно, его уже удалили.')
        raw = self._load(snap, path)
        if not isinstance(raw, dict):
            raise CatalogError(f'Файл {path} повреждён. Сообщите Даулету.', status=500)
        return {'product': self.form(slug, raw, self.ctx(snap)), 'sha': sha}

    def product_url(self, slug: str) -> str | None:
        return f'{self.site_url}ru/p/{slug}/' if self.site_url else None

    # ——— проверка формы ———
    def _image_ref(self, x: Any, ctx: _Ctx) -> tuple[str, str] | str:
        """→ ('path', media/products/…) | ('upload', up_…) | текст ошибки."""
        if isinstance(x, dict):
            x = x.get('image') or x.get('path') or x.get('upload')
        if not isinstance(x, str) or not x.strip():
            return 'фото не найдено — удалите его и добавьте заново'
        x = x.strip()
        uid = x[len('upload:'):] if x.startswith('upload:') else (x if UPLOAD_RE.fullmatch(x) else None)
        if uid is not None:
            if UPLOAD_RE.fullmatch(uid) and self.uploads.exists(uid):
                return ('upload', uid)
            return 'загрузка устарела — добавьте это фото заново'
        p = media_path(x)
        if p and p in ctx.media:
            return ('path', p)
        return 'фото не найдено — удалите его и добавьте заново'

    def _clean_variants(self, vs: Any, ctx: _Ctx, allowed_extra: set[str]) -> list[dict]:
        if not isinstance(vs, list) or not vs:
            raise CatalogError('Добавьте хотя бы один цвет с фото.', 'variants')
        if len(vs) > LIMITS['colors_max']:
            raise CatalogError(f'Не больше {LIMITS["colors_max"]} цветов у одного товара.', 'variants')
        out, seen = [], set()
        for i, v in enumerate(vs):
            f, n = f'variants.{i}', i + 1
            if not isinstance(v, dict):
                raise CatalogError(f'Цвет № {n}: {MSG_RELOAD.lower()}', f)
            color = v.get('color')
            if not isinstance(color, str) or color not in ctx.colors:
                raise CatalogError(f'Цвет № {n}: выберите цвет из палитры.', f'{f}.color')
            name = tri_in(v.get('name'), f'{f}.name', f'Цвет № {n}: свой оттенок', LIMITS['shade_max'])
            if color in seen and not name['ru']:
                raise CatalogError(f'Цвет № {n}: такой цвет у товара уже есть — напишите название оттенка, '
                                   'например «карамельный».', f'{f}.name.ru')
            seen.add(color)
            mats = v.get('materials') if isinstance(v.get('materials'), list) and v.get('materials') else (
                [] if v.get('material') in (None, '') else [v.get('material')])
            for m in mats:
                if not isinstance(m, str) or m not in ctx.mats:
                    raise CatalogError(f'Цвет № {n}: выберите материал из списка.', f'{f}.material')
            mats = _dedupe(mats)
            imgs = v.get('images')
            if not isinstance(imgs, list) or not imgs:
                raise CatalogError(f'Цвет № {n}: добавьте хотя бы одно фото.', f'{f}.images')
            images = []
            for j, x in enumerate(imgs):
                ref = self._image_ref(x, ctx)
                if isinstance(ref, str):
                    raise CatalogError(f'Цвет № {n}, фото № {j + 1}: {ref}.', f'{f}.images')
                if ref not in images:
                    images.append(ref)
            if len(images) > LIMITS['photos_max']:
                raise CatalogError(f'Цвет № {n}: не больше {LIMITS["photos_max"]} фото у одного цвета '
                                   f'(сейчас {len(images)}).', f'{f}.images')
            extra = {k: val for k, val in v.items()
                     if k in allowed_extra and k not in ('color', 'name', 'material', 'materials', 'images')}
            # Поля, которых нет в форме, сохраняются как были — но только правильные: свой оттенок кружочка (hex),
            # узор (pattern), «не показывать цвет» (published — переключателя в форме нет), остальное — небольшое.
            hex_ok = extra.get('hex') in (None, '') or (isinstance(extra['hex'], str) and HEX_RE.fullmatch(extra['hex']))
            pattern_ok = extra.get('pattern') in (None, '') or extra['pattern'] in PATTERNS
            published_ok = 'published' not in extra or isinstance(extra['published'], bool)
            if not (hex_ok and pattern_ok and published_ok
                    and all(small_json(x) for k, x in extra.items() if k not in VARIANT_SITE_KEYS)):
                raise CatalogError(f'Цвет № {n}: {MSG_RELOAD.lower()}', f)
            extra = copy.deepcopy(extra)
            out.append({'color': color, 'name': name, 'materials': mats, 'images': images, 'extra': extra,
                        'keys': [k for k in v if isinstance(k, str)]})
        return out

    def clean(self, data: Any, ctx: _Ctx, allowed_extra: set[str]) -> dict:
        """Проверка товара из формы (DESIGN.md → «Проверки на сервере»). → только известные поля."""
        if not isinstance(data, dict):
            raise CatalogError(f'Нет данных товара. {MSG_RELOAD}')
        name = tri_in(data.get('name'), 'name', 'Название', LIMITS['name_max'], required=True,
                      required_msg='Напишите название товара.')
        cat = data.get('cat')
        if not isinstance(cat, str) or cat not in ctx.cats:
            raise CatalogError('Выберите категорию.', 'cat')
        if cat not in ctx.leaves:
            subs = [c['name']['ru'] for c in ctx.categories if c.get('parent') == cat]
            raise CatalogError('Выберите раздел внутри: ' + ', '.join(subs) + '.', 'cat')
        size = data.get('size')
        if size is not None and not isinstance(size, dict):
            raise CatalogError(f'Размер: {MSG_RELOAD.lower()}', 'size')
        size = size or {}
        type_ = tri_in(data.get('type'), 'type', 'Тип', LIMITS['type_max'])
        price = int_in(data.get('price'), 'price', 0, LIMITS['price_max'],
                       'Цена — целое число тенге от 0 до 10 000 000, без копеек и букв. '
                       'Пусто — на сайте будет «цена по запросу».')
        return {
            'published': bool_in(data.get('published', True)),
            'cat': cat,
            'name': name,
            'type': type_,
            'new': bool_in(data.get('new')), 'popular': bool_in(data.get('popular')), 'soon': bool_in(data.get('soon')),
            'price': price,
            'sale_price': sale_in(data.get('sale_price'), price),
            'stock': int_in(data.get('stock'), 'stock', 0, LIMITS['stock_max'],
                            'Остаток — целое число штук: 0 или больше. Пусто — просто «в наличии».'),
            'desc': tri_in(data.get('desc'), 'desc', 'Описание', LIMITS['text_max'], multiline=True),
            'strap': tri_in(data.get('strap'), 'strap', 'Ручки и ремни', LIMITS['text_max'], multiline=True),
            'size': {k: size_in(size.get(k), f'size.{k}', label)
                     for k, label in (('w', 'Ширина'), ('h', 'Высота'), ('d', 'Глубина'))},
            'variants': self._clean_variants(data.get('variants'), ctx, allowed_extra),
        }

    # ——— запись ———
    def _place_uploads(self, slug: str, variants: list[dict], ctx: _Ctx) -> tuple[list[dict], dict[str, bytes]]:
        """upload:up_… → новое имя media/products/<slug>-<цвет>-<6 hex>.jpg; → (цвета для файла, новые фото)."""
        taken = set(ctx.media)
        placed: dict[str, str] = {}
        files: dict[str, bytes] = {}
        out = []
        for v in variants:
            paths = []
            for kind, ref in v['images']:
                if kind == 'upload':
                    if ref not in placed:
                        data = self.uploads.read(ref)
                        if data is None:
                            raise CatalogError('Одно из фото загружено слишком давно — добавьте его заново.',
                                               'variants')
                        while True:
                            path = f'{MEDIA}{slug}-{v["color"]}-{secrets.token_hex(3)}.jpg'
                            if path not in taken:
                                break
                        taken.add(path)
                        placed[ref], files[path] = path, data
                    ref = placed[ref]
                if ref not in paths:
                    paths.append(ref)
            fields = {'color': v['color']}
            if any(v['name'].values()):
                fields['name'] = v['name']
            if len(v['materials']) > 1:
                fields['materials'] = v['materials']      # несколько материалов — списком (core.py так понимает)
            elif v['materials']:
                fields['material'] = v['materials'][0]
            fields['images'] = paths
            fields.update(v['extra'])
            out.append(self._in_order(fields, v.get('keys') or []))
        return out, files

    @staticmethod
    def _in_order(fields: dict, keys: list[str]) -> dict:
        """Ключи цвета — в том порядке, в каком они были в файле (форма присылает цвет как был): иначе, например,
        hex переезжал бы в конец и в истории git появлялись лишние строки. material и materials взаимозаменяемы."""
        out = {}
        for k in keys:
            for name in (('material', 'materials') if k in ('material', 'materials') else (k,)):
                if name in fields and name not in out:
                    out[name] = fields[name]
        for k, val in fields.items():
            if k not in out:
                out[k] = val
        return out

    @staticmethod
    def _apply(base: dict, clean: dict, variants: list[dict]) -> dict:
        """Поля формы → поверх файла: порядок ключей и неизвестные поля — как были, старые поля — убираем."""
        d = copy.deepcopy(base)
        if 'variants' not in d and 'images' in d:
            d = _put_at(d, 'images', 'variants', variants)
        for k in LEGACY:
            d.pop(k, None)
        for k in ('published', 'cat'):
            d[k] = clean[k]
        for k in ('name', 'type'):
            d[k] = {**(d[k] if isinstance(d.get(k), dict) else {}), **clean[k]}
        for k in ('new', 'popular', 'soon', 'price', 'stock'):
            d[k] = clean[k]
        d = _put_after(d, 'price', 'sale_price', clean['sale_price'])      # без скидки поля нет
        for k in ('desc', 'strap'):
            d[k] = {**(d[k] if isinstance(d.get(k), dict) else {}), **clean[k]}
        d['size'] = {**(d['size'] if isinstance(d.get('size'), dict) else {}), **clean['size']}
        d['variants'] = variants
        return d

    @contextmanager
    def _writing(self):
        """Одна запись за раз (store.write_lock), но ждать чужую — не дольше LOCK_WAIT, потом понятная ошибка."""
        if not self.store.write_lock.acquire(timeout=LOCK_WAIT):
            raise CatalogError(MSG_LOCKED, status=503)
        try:
            yield
        finally:
            self.store.write_lock.release()

    def _commit(self, snap: Snapshot, changes: dict[str, bytes | None], message: str, user: str,
                conflict_msg: str = MSG_CONFLICT_DATA, own: str | None = None) -> str:
        """Коммит с защитой от одновременной правки: изменяемые файлы должны быть такими же, как в снимке.
        Если удаляются фото — то же для всех товаров: «ничейные» фото посчитаны по снимку, а чужой коммит
        (Даулет руками, вторая копия админки при деплое) мог как раз начать ссылаться на них.
        own — файл, который правит человек: конфликт по нему — conflict_msg, по другому файлу — общий текст."""
        expect = {p: snap.blob_sha(p) for p in changes}
        if any(v is None and p.startswith(MEDIA) for p, v in changes.items()):
            for p, s in snap.list(PRODUCTS).items():
                if SLUG_RE.fullmatch(p[len(PRODUCTS):-len('.json')] if p.endswith('.json') else ''):
                    expect.setdefault(p, s)
        try:
            return self.store.commit(changes, message, user, expect=expect)
        except ConflictError as ex:
            raise Conflict(conflict_msg if own is None or ex.path == own else MSG_CONFLICT_DATA) from None

    @staticmethod
    def _orphans(old: dict | None, new: dict | None, others: dict[str, dict], ctx: _Ctx) -> list[str]:
        """Фото этого товара, на которые после правки не ссылается ни один товар (чужие лишние фото не трогаем)."""
        used = set().union(*(refs(d) for d in others.values())) if others else set()
        return sorted(p for p in refs(old) - refs(new) - used if p in ctx.media)

    @staticmethod
    def _keep_one_on_site(slug: str, raws: dict[str, dict]):
        """Сборка сайта падает, если не осталось ни одного показанного товара — не даём до этого дойти."""
        if not any(s != slug and d.get('published') is not False for s, d in raws.items()):
            raise CatalogError('Это последний товар, который виден на сайте, — сайт не может быть пустым. '
                               'Сначала добавьте или покажите другой товар.', 'published')

    @staticmethod
    def _next_order(raws: dict[str, dict]) -> tuple[int, dict[str, int]]:
        """Новый товар — первым: order = минимальный − 10. Сайт считает 0 и минус «в конец» (core.py),
        поэтому, если места сверху нет, все товары одним коммитом получают 1010, 1020, …, а новый — 1000
        (запас на сотню новых товаров; «Изменить порядок» снова расставит 10, 20, …)."""
        orders = [site_order(d.get('order')) for d in raws.values()]
        valid = [o for o in orders if o < 9999]
        if not valid:
            return 10, {}
        m = math.floor(min(valid))
        if m - 10 >= 1:
            return int(m - 10), {}
        ranked = sorted(raws, key=lambda s: (site_order(raws[s].get('order')), str(raws[s].get('id') or '')))
        return 1000, {s: 1010 + 10 * i for i, s in enumerate(ranked)}

    def _only_order_changed(self, old_sha: str, current: Any) -> bool:
        """Файл изменился после того, как его открыли, но только порядком (кто-то в это время нажал «Изменить
        порядок» или добавил товар) — правку не отклоняем: порядок ставит сервер, форма его не трогает."""
        if not re.fullmatch(r'[0-9a-f]{40}', old_sha) or not isinstance(current, dict):
            return False
        try:
            old = json.loads(self.store.read_blob(old_sha).decode('utf-8'))
        except Exception:   # noqa: BLE001 — нет такой версии или она не JSON: значит, конфликт
            return False
        return isinstance(old, dict) and {**old, 'order': None} == {**current, 'order': None}

    @staticmethod
    def _next_id(raws: dict[str, dict]) -> str:
        ids = [int(str(d.get('id'))) for d in raws.values() if re.fullmatch(r'\d{1,6}', str(d.get('id') or ''))]
        return str(max(ids, default=0) + 1).zfill(3)

    @staticmethod
    def _unique_slug(name: str, snap: Snapshot) -> str:
        base = translit(name) or 'tovar'
        if not base[0].isalnum():
            base = 'tovar-' + base
        n = 1
        while True:
            slug = base if n == 1 else f'{base}-{n}'
            if slug not in RESERVED_SLUGS and snap.blob_sha(f'{PRODUCTS}{slug}.json') is None:
                return slug
            n += 1

    def create(self, data: Any, user: str) -> dict:
        with self._writing():
            snap = self.store.snapshot(fresh=True)
            ctx = self.ctx(snap)
            clean = self.clean(data, ctx, set(VARIANT_SITE_KEYS))
            raws = self.raw_products(snap)
            slug = self._unique_slug(clean['name']['ru'], snap)
            order, renumber = self._next_order(raws)
            variants, files = self._place_uploads(slug, clean['variants'], ctx)
            doc = {
                'id': self._next_id(raws), 'published': clean['published'], 'order': order, 'cat': clean['cat'],
                'name': clean['name'], 'type': clean['type'],
                'new': clean['new'], 'popular': clean['popular'], 'soon': clean['soon'],
                'price': clean['price'], 'stock': clean['stock'],
                'desc': clean['desc'], 'strap': clean['strap'], 'size': clean['size'], 'variants': variants,
            }
            doc = _put_after(doc, 'price', 'sale_price', clean['sale_price'])    # без скидки поля нет
            changes: dict[str, bytes | None] = {f'{PRODUCTS}{slug}.json': dumps(doc), **files}
            for other, new_order in renumber.items():
                changes[f'{PRODUCTS}{other}.json'] = dumps({**raws[other], 'order': new_order})
            commit = self._commit(snap, changes, f'Админка: новый товар «{clean["name"]["ru"]}» ({user})', user)
            return {'slug': slug, 'commit': commit, 'url': self.product_url(slug)}

    def update(self, slug: str, data: Any, sha: Any, user: str) -> dict:
        if not SLUG_RE.fullmatch(slug or ''):
            raise NotFound('Товар не найден.')
        path = f'{PRODUCTS}{slug}.json'
        with self._writing():
            snap = self.store.snapshot(fresh=True)
            cur_sha = snap.blob_sha(path)
            if cur_sha is None:
                raise NotFound('Этот товар уже удалили — например, на другом устройстве.')
            base = self._load(snap, path)
            if not isinstance(base, dict):
                raise CatalogError(f'Файл {path} повреждён. Сообщите Даулету.', status=500)
            ctx = self.ctx(snap)
            stored_extra = {k for v in base.get('variants') or [] if isinstance(v, dict) for k in v
                            if not str(k).startswith('_')} if isinstance(base.get('variants'), list) else set()
            clean = self.clean(data, ctx, set(VARIANT_SITE_KEYS) | stored_extra)
            variants, files = self._place_uploads(slug, clean['variants'], ctx)
            doc = self._apply(base, clean, variants)
            new_bytes = dumps(doc)
            if not files and new_bytes == snap.read(path):
                return {'commit': snap.head, 'unchanged': True, 'url': self.product_url(slug)}
            if not isinstance(sha, str) or not sha:
                raise CatalogError(MSG_RELOAD, 'sha')
            if sha != cur_sha and not self._only_order_changed(sha, base):
                raise Conflict(MSG_CONFLICT_PRODUCT)
            raws = self.raw_products(snap)
            if base.get('published') is not False and doc['published'] is False:
                self._keep_one_on_site(slug, raws)
            others = {s: d for s, d in raws.items() if s != slug}
            changes: dict[str, bytes | None] = {path: new_bytes, **files}
            for p in self._orphans(base, doc, others, ctx):
                changes[p] = None
            commit = self._commit(snap, changes, f'Админка: «{clean["name"]["ru"]}» — сохранено ({user})', user,
                                  MSG_CONFLICT_PRODUCT, own=path)
            return {'commit': commit, 'url': self.product_url(slug)}

    def delete(self, slug: str, sha: Any, user: str) -> dict:
        if not SLUG_RE.fullmatch(slug or ''):
            raise NotFound('Товар не найден.')
        path = f'{PRODUCTS}{slug}.json'
        with self._writing():
            snap = self.store.snapshot(fresh=True)
            cur_sha = snap.blob_sha(path)
            if cur_sha is None:
                raise NotFound('Этот товар уже удалили.')
            if not isinstance(sha, str) or not sha:
                raise CatalogError(MSG_RELOAD, 'sha')
            base = self._load(snap, path)
            if sha != cur_sha and not self._only_order_changed(sha, base):
                raise Conflict(MSG_CONFLICT_PRODUCT)
            base = base if isinstance(base, dict) else {}
            raws = self.raw_products(snap)
            if base.get('published') is not False:
                self._keep_one_on_site(slug, raws)
            ctx = self.ctx(snap)
            others = {s: d for s, d in raws.items() if s != slug}
            changes: dict[str, bytes | None] = {path: None}
            for p in self._orphans(base, None, others, ctx):
                changes[p] = None
            name = tri(base.get('name'))['ru'] or slug
            commit = self._commit(snap, changes, f'Админка: удалён «{name}» ({user})', user, MSG_CONFLICT_PRODUCT,
                                  own=path)
            return {'commit': commit}

    def reorder(self, slugs: Any, user: str) -> dict:
        if not isinstance(slugs, list) or not slugs or not all(isinstance(s, str) for s in slugs):
            raise CatalogError(f'Нет списка товаров. {MSG_RELOAD}', 'slugs')
        if len(set(slugs)) != len(slugs):
            raise CatalogError(f'Товар в списке повторяется. {MSG_RELOAD}', 'slugs')
        with self._writing():
            snap = self.store.snapshot(fresh=True)
            raws = self.raw_products(snap)
            unknown = [s for s in slugs if s not in raws]
            if unknown:
                raise Conflict('Список товаров изменился (кто-то добавил или удалил товар). '
                               'Обновите страницу и расставьте порядок ещё раз.')
            rest = sorted((s for s in raws if s not in set(slugs)),
                          key=lambda s: (site_order(raws[s].get('order')), str(raws[s].get('id') or '')))
            changes: dict[str, bytes | None] = {}
            for i, s in enumerate(list(slugs) + rest):
                order = 10 * (i + 1)
                if raws[s].get('order') != order or isinstance(raws[s].get('order'), bool):
                    changes[f'{PRODUCTS}{s}.json'] = dumps({**raws[s], 'order': order})
            if not changes:
                return {'commit': snap.head, 'unchanged': True}
            commit = self._commit(snap, changes, f'Админка: порядок товаров ({user})', user)
            return {'commit': commit}

    # ——— настройки магазина ———
    BLOCKS = ('contacts', 'delivery', 'promo', 'seller')
    I18N_KEYS = ('address', 'hours', 'promo', 'dlv_world')

    @staticmethod
    def _i18n_view(v: Any) -> dict:
        """Текст из i18n.json для формы. Сайт берёт эти тексты как есть, без подстановки русского, поэтому
        при сохранении пустой қаз/eng заполняется русским; в форме такой перевод снова показываем пустым."""
        t = tri(v)
        return {'ru': t['ru'], 'kz': '' if t['kz'] == t['ru'] else t['kz'], 'en': '' if t['en'] == t['ru'] else t['en']}

    def _settings_view(self, s: dict, i18n: dict) -> dict:
        t = i18n.get('t') if isinstance(i18n.get('t'), dict) else {}
        dl = s.get('delivery') if isinstance(s.get('delivery'), dict) else {}
        kz = dl.get('kz') if isinstance(dl.get('kz'), list) else []
        seller = s.get('seller') if isinstance(s.get('seller'), dict) else {}

        def st(v):
            return '' if v is None else str(v)

        return {
            'contacts': {
                'whatsapp': st(s.get('whatsapp')), 'instagram': st(s.get('instagram')),
                'pinterest': st(s.get('pinterest')), 'email': st(s.get('email')), 'map_url': st(s.get('map_url')),
                'address': self._i18n_view(t.get('address')), 'hours': self._i18n_view(t.get('hours')),
            },
            'delivery': {
                'free_from': num_out(dl.get('free_from')),
                'kz': [{**{k: copy.deepcopy(v) for k, v in o.items()}, 'price': num_out(o.get('price')),
                        'name': tri(o.get('name')), 'days': tri(o.get('days'))} for o in kz if isinstance(o, dict)],
                'world': self._i18n_view(t.get('dlv_world')),
            },
            'promo': self._i18n_view(t.get('promo')),
            'seller': {'name': st(seller.get('name')), 'bin': st(seller.get('bin'))},
        }

    @classmethod
    def _settings_sha(cls, view: dict) -> str:
        return '-'.join(f'{b[0]}{_hash(view[b])}' for b in cls.BLOCKS)

    def settings(self) -> dict:
        snap = self.store.snapshot()
        view = self._settings_view(self._load(snap, SETTINGS), self._load(snap, I18N))
        return {**view, 'sha': self._settings_sha(view)}

    @staticmethod
    def _nick(v: Any, domain: str, field: str, msg: str, pattern: str) -> str:
        s = _text(v, False) if isinstance(v, (str, type(None))) else None
        if s is None:
            raise CatalogError(msg, field)
        m = re.search(domain + r'[^/]*/@?([^/?#\s]+)', s, re.I)
        if m:
            s = m.group(1)
        s = s.lstrip('@').strip('/')
        if not re.fullmatch(pattern, s):
            raise CatalogError(msg, field)
        return s

    def _clean_contacts(self, v: Any, cur: dict) -> dict:
        if not isinstance(v, dict):
            raise CatalogError(f'Контакты: {MSG_RELOAD.lower()}', 'contacts')
        out = copy.deepcopy(cur)
        if 'whatsapp' in v:
            digits = re.sub(r'\D', '', str(v.get('whatsapp') or ''))
            if len(digits) == 11 and digits.startswith('8'):
                digits = '7' + digits[1:]                  # 8 706 … → 7 706 …
            if not re.fullmatch(r'7\d{10}', digits):
                raise CatalogError('WhatsApp — номер из 11 цифр, начинается с 7, например 7 706 723 23 49.',
                                   'contacts.whatsapp')
            out['whatsapp'] = digits
        if 'instagram' in v:
            out['instagram'] = self._nick(v.get('instagram'), r'instagram\.com', 'contacts.instagram',
                                          'Instagram — ник без @, например attre.studio.', r'[A-Za-z0-9._]{1,30}')
        if 'pinterest' in v:
            out['pinterest'] = self._nick(v.get('pinterest'), r'pinterest\.[a-z.]+', 'contacts.pinterest',
                                          'Pinterest — ник без @, например attrestudio.', r'[A-Za-z0-9._-]{1,30}')
        if 'email' in v:
            e = _text(v.get('email'), False) if isinstance(v.get('email'), (str, type(None))) else ''
            if not re.fullmatch(r'[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}', e) or len(e) > 100:
                raise CatalogError('E-mail — например attre.studio@gmail.com.', 'contacts.email')
            out['email'] = e
        if 'map_url' in v:
            u = _text(v.get('map_url'), False) if isinstance(v.get('map_url'), (str, type(None))) else ''
            if not re.fullmatch(r'https://\S+', u) or len(u) > 500:
                raise CatalogError('Ссылка 2ГИС — адрес страницы целиком, начинается с https://', 'contacts.map_url')
            out['map_url'] = u
        if 'address' in v:
            out['address'] = tri_in(v.get('address'), 'contacts.address', 'Адрес', 200, required=True,
                                    required_msg='Напишите адрес магазина.')
        if 'hours' in v:
            out['hours'] = tri_in(v.get('hours'), 'contacts.hours', 'Часы работы', 100, required=True,
                                  required_msg='Напишите часы работы, например «Часы работы: 11:00–20:00».')
        return out

    def _clean_delivery(self, v: Any, cur: dict, allowed_extra: set[str]) -> dict:
        if not isinstance(v, dict):
            raise CatalogError(f'Доставка: {MSG_RELOAD.lower()}', 'delivery')
        out = copy.deepcopy(cur)
        if 'free_from' in v:
            out['free_from'] = int_in(v.get('free_from'), 'delivery.free_from', 0, LIMITS['price_max'],
                                      'Бесплатно от — сумма в тенге, целое число. Пусто — без бесплатной доставки.')
        if 'kz' in v:
            items = v.get('kz')
            if not isinstance(items, list):
                raise CatalogError(f'Способы доставки: {MSG_RELOAD.lower()}', 'delivery.kz')
            if len(items) > 10:
                raise CatalogError('Не больше 10 способов доставки.', 'delivery.kz')
            out['kz'] = []
            for i, o in enumerate(items):
                f, n = f'delivery.kz.{i}', i + 1
                if not isinstance(o, dict):
                    raise CatalogError(f'Способ доставки № {n}: {MSG_RELOAD.lower()}', f)
                name = tri_in(o.get('name'), f'{f}.name', f'Способ доставки № {n}: название', 100, required=True,
                              required_msg=f'Способ доставки № {n}: напишите название.')
                price = int_in(o.get('price'), f'{f}.price', 0, 1_000_000,
                               f'Способ доставки № {n}: цена — целое число тенге (0 — бесплатно).')
                if price is None:
                    raise CatalogError(f'Способ доставки № {n}: укажите цену (0 — бесплатно).', f'{f}.price')
                days = tri_in(o.get('days'), f'{f}.days', f'Способ доставки № {n}: срок', 100)
                extra = {k: x for k, x in o.items() if k in allowed_extra and k not in ('name', 'price', 'days')}
                if not all(small_json(x) for x in extra.values()):
                    raise CatalogError(f'Способ доставки № {n}: {MSG_RELOAD.lower()}', f)
                extra = copy.deepcopy(extra)
                out['kz'].append({**extra, 'price': price, 'name': name, 'days': days})
        if 'world' in v:
            out['world'] = tri_in(v.get('world'), 'delivery.world', 'Доставка по миру', 500, required=True,
                                  required_msg='Доставка по миру: напишите текст.')
        return out

    @staticmethod
    def _clean_promo(v: Any, cur: dict) -> dict:
        return tri_in(v, 'promo', 'Полоса сверху', 200, required=True,
                      required_msg='Напишите текст полосы сверху сайта.')

    @staticmethod
    def _clean_seller(v: Any, cur: dict) -> dict:
        if not isinstance(v, dict):
            raise CatalogError(f'Продавец: {MSG_RELOAD.lower()}', 'seller')
        out = copy.deepcopy(cur)
        if 'name' in v:
            try:
                out['name'] = _text(v.get('name'), False)
            except ValueError:
                raise CatalogError(f'Продавец: {MSG_RELOAD.lower()}', 'seller.name') from None
            if len(out['name']) > 120:
                raise CatalogError('Название продавца — не длиннее 120 символов.', 'seller.name')
        if 'bin' in v:
            raw = str(v.get('bin') or '')
            digits = re.sub(r'[\s\u00a0-]', '', raw)
            if digits and not re.fullmatch(r'\d{12}', digits):
                raise CatalogError('ИИН/БИН — 12 цифр.', 'seller.bin')
            out['bin'] = digits
        if bool(out['name']) != bool(out['bin']):
            field = 'seller.bin' if out['name'] else 'seller.name'
            raise CatalogError('Заполните и название (ИП или ТОО), и ИИН/БИН — иначе строка в подвале сайта '
                               'не появится. '
                               'Или очистите оба поля.', field)
        return out

    @staticmethod
    def _parse_sha(sha: Any) -> dict[str, str] | None:
        if not isinstance(sha, str) or not re.fullmatch(r'(?:[cdps][0-9a-f]{12}-){3}[cdps][0-9a-f]{12}', sha):
            return None
        return {part[0]: part[1:] for part in sha.split('-')}

    def save_settings(self, data: Any, user: str) -> dict:
        if not isinstance(data, dict):
            raise CatalogError(f'Нет данных. {MSG_RELOAD}')
        with self._writing():
            snap = self.store.snapshot(fresh=True)
            s_raw, i_raw = self._load(snap, SETTINGS), self._load(snap, I18N)
            if not isinstance(s_raw, dict) or not isinstance(i_raw, dict):
                raise CatalogError('Файл настроек повреждён. Сообщите Даулету.', status=500)
            cur = self._settings_view(s_raw, i_raw)
            parts = self._parse_sha(data.get('sha'))
            if parts is None:
                raise CatalogError(MSG_RELOAD, 'sha')
            kz_extra = {k for o in (s_raw.get('delivery') or {}).get('kz') or [] if isinstance(o, dict)
                        for k in o if not str(k).startswith('_')} if isinstance(s_raw.get('delivery'), dict) else set()
            cleaners = {'contacts': self._clean_contacts, 'promo': self._clean_promo, 'seller': self._clean_seller,
                        'delivery': lambda v, c: self._clean_delivery(v, c, kz_extra)}
            new, changed = copy.deepcopy(cur), []
            for block in self.BLOCKS:
                if block not in data:
                    continue
                value = cleaners[block](data[block], cur[block])
                if value == cur[block]:
                    continue
                if parts.get(block[0]) != _hash(cur[block]):
                    raise Conflict(MSG_CONFLICT_SETTINGS)
                new[block], changed = value, changed + [block]
            if not changed:
                return {'commit': snap.head, 'sha': self._settings_sha(cur), 'unchanged': True}

            s_new, i_new = copy.deepcopy(s_raw), copy.deepcopy(i_raw)
            t = i_new.setdefault('t', {})

            def put_text(key, value):
                filled = {l: value[l] or value['ru'] for l in LANGS}
                t[key] = {**(t[key] if isinstance(t.get(key), dict) else {}), **filled}

            if 'contacts' in changed:
                c = new['contacts']
                for k in ('whatsapp', 'instagram', 'pinterest', 'email', 'map_url'):
                    s_new[k] = c[k]
                put_text('address', c['address'])
                put_text('hours', c['hours'])
            if 'delivery' in changed:
                dl = s_new['delivery'] if isinstance(s_new.get('delivery'), dict) else {}
                dl['free_from'] = new['delivery']['free_from']
                dl['kz'] = new['delivery']['kz']
                s_new['delivery'] = dl
                put_text('dlv_world', new['delivery']['world'])
            if 'promo' in changed:
                put_text('promo', new['promo'])
            if 'seller' in changed:
                old = s_new['seller'] if isinstance(s_new.get('seller'), dict) else {}
                s_new['seller'] = {**old, 'name': new['seller']['name'], 'bin': new['seller']['bin']}
            changes: dict[str, bytes | None] = {}
            if s_new != s_raw:
                changes[SETTINGS] = dumps(s_new)
            if i_new != i_raw:
                changes[I18N] = dumps(i_new)
            if not changes:
                return {'commit': snap.head, 'sha': self._settings_sha(cur), 'unchanged': True}
            commit = self._commit(snap, changes, f'Админка: доставка и контакты ({user})', user, MSG_CONFLICT_SETTINGS)
            return {'commit': commit, 'sha': self._settings_sha(self._settings_view(s_new, i_new))}
