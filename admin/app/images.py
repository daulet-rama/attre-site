"""Фото (DESIGN.md → «Фото»).

Принимаем JPEG, PNG, WEBP, HEIC/HEIF (фото с iPhone), до 30 МБ; проверка — открыть Pillow, расширению и MIME не верим.
В репозиторий: поворот по EXIF, прозрачность → белый фон, цвета → sRGB (у iPhone — Display P3: без перевода сайт
показал бы цвета сумок тусклее), длинная сторона ≤ 2000, JPEG q88 progressive, без EXIF (там бывает геопозиция).
Превью для админки — JPEG шириной 480 в кадре 3:4, как его режет сайт (core.fit_34): фото на однотонном фоне
продлевается фоном, остальные обрезаются по центру — превью «Так будет на сайте» совпадает с сайтом.
Временные загрузки — TMP_DIR/<upload_id>.jpg (+ _t.jpg), живут 24 часа; превью фото из репозитория кэшируются
на диске в TMP_DIR/media/.
"""
from __future__ import annotations

import io
import logging
import math
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:          # без pillow-heif HEIC не откроется — будет понятная ошибка «файл не подходит»
    pillow_heif = None

try:
    from PIL import ImageCms
    _SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
except (ImportError, OSError):
    ImageCms = None
    _SRGB = None

log = logging.getLogger('attre.images')

MAX_BYTES = 30 * 1024 * 1024
MAX_SIDE = 2000
THUMB_W = 480
PREVIEW_WIDTHS = (240, 480, 960)
PREVIEW_VERSION = 'f34'   # как режется превью (кадр 3:4, как на сайте); поменяли нарезку — меняем, и старые копии
                          # в кэше браузера (?v=…, «навсегда») и на диске больше не используются
UPLOAD_TTL = 24 * 3600
CACHE_TTL = 14 * 24 * 3600
FORMATS = {'JPEG', 'MPO', 'PNG', 'WEBP', 'HEIF', 'HEIC'}   # MPO — так Pillow называет часть JPEG с камер
OPENERS = ('JPEG', 'PNG', 'WEBP', 'HEIF')   # какие разборщики Pillow вообще пробовать (меньше кода на входе)
# Предел по пикселям — до декодирования (память на Railway не бесконечна). Обычный (baseline) JPEG декодируется
# сразу уменьшенным, ему можно больше (200 Мп с Android): 256 Мп — около 80 МБ памяти. Прогрессивный JPEG так
# не умеет (libjpeg держит коэффициенты всего кадра: 144 Мп — почти 900 МБ), ему и остальным — до 50 Мп
# (48 Мп HEIC с iPhone проходят).
MAX_PIXELS_JPEG = 260_000_000
MAX_PIXELS_OTHER = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS_JPEG

UPLOAD_RE = re.compile(r'up_[0-9a-f]{20}')

MSG_NOT_PHOTO = 'Этот файл не подходит. Нужно фото: JPEG, PNG, WEBP или HEIC (с iPhone).'
MSG_TOO_BIG = 'Фото больше 30 МБ. Выберите фото поменьше.'
MSG_TOO_MANY_PX = 'У фото слишком большое разрешение. Выберите фото поменьше.'
MSG_BROKEN = 'Фото не открывается — возможно, файл повреждён или загрузился не до конца. Попробуйте ещё раз.'
MSG_EMPTY = 'Файл пустой. Выберите фото ещё раз.'


class ImageError(Exception):
    """Файл не годится как фото. message — по-русски, для человека."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class Processed:
    jpeg: bytes        # для репозитория: ≤ 2000px, sRGB, q88 progressive
    thumb: bytes       # превью для админки: ширина ≤ 480
    width: int
    height: int


def _open(data: bytes, target_side: int) -> Image.Image:
    if not data:
        raise ImageError(MSG_EMPTY)
    if len(data) > MAX_BYTES:
        raise ImageError(MSG_TOO_BIG)
    try:
        im = Image.open(io.BytesIO(data), formats=OPENERS)
        if im.format not in FORMATS:
            raise ImageError(MSG_NOT_PHOTO)
        w, h = im.size
        jpeg = im.format in ('JPEG', 'MPO')
        progressive = jpeg and bool(im.info.get('progressive') or im.info.get('progression'))
        if w * h > (MAX_PIXELS_JPEG if jpeg and not progressive else MAX_PIXELS_OTHER):
            raise ImageError(MSG_TOO_MANY_PX)
        if jpeg and max(w, h) > target_side:
            # JPEG можно сразу декодировать уменьшенным в 2/4/8 раз: 48 Мп открываются быстрее и без лишней памяти
            k = target_side / max(w, h)
            im.draft(im.mode, (math.ceil(w * k), math.ceil(h * k)))
        im.load()
    except ImageError:
        raise
    except Image.DecompressionBombError as ex:
        raise ImageError(MSG_TOO_MANY_PX) from ex
    except UnidentifiedImageError as ex:
        raise ImageError(MSG_NOT_PHOTO) from ex
    except (OSError, ValueError, SyntaxError, EOFError, TypeError, RuntimeError, MemoryError) as ex:
        raise ImageError(MSG_BROKEN) from ex   # RuntimeError — так отвечают декодеры HEIF при битом файле
    return im


def _flatten(im: Image.Image) -> Image.Image:
    """Прозрачность → белый фон; любые режимы → RGB (через профиль ICC, если он есть, — в sRGB)."""
    icc = im.info.get('icc_profile')
    has_alpha = im.mode in ('RGBA', 'LA', 'PA', 'RGBa', 'La') or 'transparency' in im.info
    if im.mode in ('I;16', 'I;16L', 'I;16B', 'I;16N', 'I'):
        im = im.point(lambda v: v / 256).convert('L')    # 16-битные PNG
    elif im.mode == 'F':
        im = im.convert('L')
    if has_alpha:
        rgba = im.convert('RGBA')
        bg = Image.new('RGB', rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel('A'))
        im = bg
    elif im.mode == 'P':
        im = im.convert('RGB')
    if icc and ImageCms is not None and im.mode in ('RGB', 'L', 'CMYK'):
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            if 'srgb' not in (ImageCms.getProfileDescription(src) or '').lower():
                im = ImageCms.profileToProfile(im, src, _SRGB, outputMode='RGB')
        except (ImageCms.PyCMSError, OSError, ValueError, TypeError) as ex:
            log.info('профиль цвета не применён: %s', ex)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    return im


def _jpeg(im: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality, progressive=True, optimize=True)
    return buf.getvalue()


def fit_34(im: Image.Image) -> Image.Image:
    """Кадр 3:4 — ровно как core.fit_34 на сайте (без точки фокуса: она бывает только у главного фото товара).
    Фото на однотонном студийном фоне не обрезаем, а продлеваем фон краёв, чтобы вещь осталась целиком;
    остальные кадры обрезаем по центру (по высоте — чуть выше середины)."""
    w, h = im.size
    target = 3 / 4
    strip = max(4, round(min(w, h) * 0.02))
    edges = [im.crop((0, 0, w, strip)), im.crop((0, h - strip, w, h)), im.crop((0, 0, strip, h)),
             im.crop((w - strip, 0, w, h))]
    uniform = all(max(ImageStat.Stat(x).stddev) < 9 for x in edges)
    if uniform and abs(w / h - target) > 0.01:
        if w / h > target:   # шире — добавляем фон сверху и снизу
            nh = round(w / target)
            top = (nh - h) // 2
            out = Image.new('RGB', (w, nh))
            if top > 0:
                out.paste(im.crop((0, 0, w, 2)).resize((w, top)).filter(ImageFilter.GaussianBlur(6)), (0, 0))
            if nh - h - top > 0:
                out.paste(im.crop((0, h - 2, w, h)).resize((w, nh - h - top)).filter(ImageFilter.GaussianBlur(6)),
                          (0, top + h))
            out.paste(im, (0, top))
            return out
        nw = round(h * target)   # уже — добавляем фон слева и справа
        left = (nw - w) // 2
        out = Image.new('RGB', (nw, h))
        if left > 0:
            out.paste(im.crop((0, 0, 2, h)).resize((left, h)).filter(ImageFilter.GaussianBlur(6)), (0, 0))
        if nw - w - left > 0:
            out.paste(im.crop((w - 2, 0, w, h)).resize((nw - w - left, h)).filter(ImageFilter.GaussianBlur(6)),
                      (left + w, 0))
        out.paste(im, (left, 0))
        return out
    fx, fy = .5, .45
    cw = min(w, h * target)
    ch = cw / target
    left = min(max(fx * w - cw / 2, 0), w - cw)
    top = min(max(fy * h - ch / 2, 0), h - ch)
    return im.crop((round(left), round(top), round(left + cw), round(top + ch)))


def _thumb(im: Image.Image, width: int) -> bytes:
    """Превью для админки: кадр 3:4, как на сайте, шириной не больше width."""
    t = fit_34(im)
    t.thumbnail((width, width * 3), Image.LANCZOS)
    return _jpeg(t, 82)


def _prepare(data: bytes, side: int) -> Image.Image:
    im = _open(data, side)
    try:
        # in_place: без поворота не делаем лишнюю полную копию кадра (обычный exif_transpose возвращает копию всегда)
        ImageOps.exif_transpose(im, in_place=True)
    except (OSError, ValueError, TypeError, KeyError, SyntaxError):
        pass                       # испорченный EXIF — оставляем как есть
    try:
        return _flatten(im)
    except (OSError, ValueError, TypeError, RuntimeError, MemoryError) as ex:
        raise ImageError(MSG_BROKEN) from ex


def process_upload(data: bytes) -> Processed:
    """Фото от человека → мастер-копия для репозитория + превью для админки."""
    im = _prepare(data, MAX_SIDE)
    try:
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        return Processed(jpeg=_jpeg(im, 88), thumb=_thumb(im, THUMB_W), width=im.width, height=im.height)
    except (OSError, ValueError, TypeError, RuntimeError, MemoryError) as ex:
        raise ImageError(MSG_BROKEN) from ex


def preview(data: bytes, width: int = THUMB_W) -> bytes:
    """Превью фото из репозитория."""
    im = _prepare(data, width * 3)
    try:
        return _thumb(im, width)
    except (OSError, ValueError, TypeError, RuntimeError, MemoryError) as ex:
        raise ImageError(MSG_BROKEN) from ex


def preview_width(w: str | int | None) -> int:
    """?w= → ближайшая ширина из PREVIEW_WIDTHS (не больше 960), чтобы кэш не разрастался."""
    try:
        w = int(w) if w not in (None, '') else THUMB_W
    except (TypeError, ValueError):
        w = THUMB_W
    return next((x for x in PREVIEW_WIDTHS if x >= w), PREVIEW_WIDTHS[-1])


def _write_atomic(path: Path, data: bytes):
    tmp = path.with_name(f'.{path.name}.{secrets.token_hex(4)}.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Uploads:
    """Временные загрузки и кэш превью на диске."""

    def __init__(self, root: str | os.PathLike, ttl: float = UPLOAD_TTL, cache_ttl: float = CACHE_TTL):
        self.root = Path(root)
        self.cache = self.root / 'media'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.ttl, self.cache_ttl = ttl, cache_ttl
        self._last_cleanup = 0.0

    # ——— загрузки ———
    def save(self, p: Processed) -> str:
        upload_id = 'up_' + secrets.token_hex(10)
        _write_atomic(self.root / f'{upload_id}.jpg', p.jpeg)
        _write_atomic(self.root / f'{upload_id}_t.jpg', p.thumb)
        self.cleanup()
        return upload_id

    def _file(self, upload_id: str, suffix: str) -> Path | None:
        if not isinstance(upload_id, str) or not UPLOAD_RE.fullmatch(upload_id):
            return None
        f = self.root / f'{upload_id}{suffix}.jpg'
        try:
            if time.time() - f.stat().st_mtime > self.ttl:
                return None
        except OSError:
            return None
        return f

    def exists(self, upload_id: str) -> bool:
        return self._file(upload_id, '') is not None

    def read(self, upload_id: str) -> bytes | None:
        f = self._file(upload_id, '')
        try:
            return f.read_bytes() if f else None
        except OSError:
            return None

    def thumb_path(self, upload_id: str) -> Path | None:
        return self._file(upload_id, '_t')

    # ——— кэш превью фото из репозитория (ключ — blob sha: новое содержимое — новый ключ;
    #     «f34» — превью в кадре 3:4, как на сайте: старые превью без кадра в кэше не используются) ———
    def cached_preview(self, sha: str, width: int) -> Path | None:
        f = self.cache / f'{sha}-{width}-{PREVIEW_VERSION}.jpg'
        return f if f.exists() else None

    def store_preview(self, sha: str, width: int, data: bytes) -> Path:
        f = self.cache / f'{sha}-{width}-{PREVIEW_VERSION}.jpg'
        _write_atomic(f, data)
        return f

    def cleanup(self, force: bool = False):
        """Старше 24 ч — загрузки, старше 14 дней — превью. Не чаще раза в 10 минут."""
        now = time.time()
        if not force and now - self._last_cleanup < 600:
            return
        self._last_cleanup = now
        for folder, pattern, ttl in ((self.root, 'up_*.jpg', self.ttl), (self.cache, '*.jpg', self.cache_ttl),
                                     (self.root, '.*.tmp', 3600), (self.cache, '.*.tmp', 3600)):
            for f in folder.glob(pattern):
                try:
                    if now - f.stat().st_mtime > ttl:
                        f.unlink()
                except OSError:
                    pass
