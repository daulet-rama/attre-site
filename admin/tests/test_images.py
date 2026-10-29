"""Фото: JPEG, PNG с прозрачностью, HEIC, поворот по EXIF, плохие файлы, временные загрузки."""
from __future__ import annotations

import io
import os
import time

import pytest
from PIL import Image, ImageCms

from app.images import (MSG_BROKEN, MSG_EMPTY, MSG_NOT_PHOTO, MSG_TOO_BIG, MSG_TOO_MANY_PX, ImageError, Uploads,
                        preview, preview_width, process_upload)
from conftest import heic_bytes, jpeg_bytes, open_image, png_rgba_bytes


def test_jpeg_big_is_resized_progressive_without_exif():
    p = process_upload(jpeg_bytes((3000, 4000), exif_orientation=1))
    im = open_image(p.jpeg)
    assert im.format == 'JPEG' and im.mode == 'RGB'
    assert im.size == (1500, 2000) == (p.width, p.height)
    assert im.info.get('progressive') or im.info.get('progression')
    assert 'exif' not in im.info                                       # геопозиция с телефона не уходит на сайт
    t = open_image(p.thumb)
    assert t.size == (480, 640)


def test_small_jpeg_keeps_size():
    p = process_upload(jpeg_bytes((800, 600)))
    assert (p.width, p.height) == (800, 600)
    assert open_image(p.thumb).size == (450, 600)        # превью — кадр 3:4, как на сайте; не растягиваем


def test_thumb_framed_like_site():
    """Превью в админке режется так же, как фото на сайте (core.fit_34): однотонный фон — продлеваем,
    иначе — обрезаем по центру. Иначе «Так будет на сайте» показывало бы другое."""
    from PIL import Image, ImageDraw
    from app.images import fit_34
    flat = Image.new('RGB', (1600, 1200), (240, 240, 238))
    ImageDraw.Draw(flat).rectangle((100, 300, 1500, 900), fill=(200, 30, 30))   # вещь почти во всю ширину
    framed = fit_34(flat)
    assert framed.size == (1600, 2133)                                   # фон продлён сверху и снизу
    assert framed.getpixel((5, 5)) == (240, 240, 238) and framed.getpixel((120, 1066)) == (200, 30, 30)
    t = open_image(process_upload(_jpeg(flat)).thumb)
    assert t.size == (480, 640) and t.getpixel((40, 320))[0] > 150       # край вещи на месте — не обрезан
    busy = fit_34(open_image(jpeg_bytes((1600, 1200))))                  # полосы по краям — фон не однотонный
    assert busy.size == (900, 1200)


def _jpeg(im) -> bytes:
    import io
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=95)
    return buf.getvalue()


def test_exif_orientation_applied():
    p = process_upload(jpeg_bytes((400, 200), exif_orientation=6))   # снято «боком» — сохраняем стоя
    assert (p.width, p.height) == (200, 400)


def test_png_transparency_becomes_white():
    p = process_upload(png_rgba_bytes())
    im = open_image(p.jpeg)
    assert im.mode == 'RGB' and im.size == (400, 600)
    r, g, b = im.getpixel((10, 10))
    assert min(r, g, b) > 245                                          # фон — белый, не чёрный
    r, g, b = im.getpixel((200, 300))
    assert r > 150 and g < 60 and b < 60                               # сама вещь на месте


def test_palette_png_with_transparency():
    im = Image.new('P', (100, 100), 0)
    im.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    im.paste(1, (40, 40, 60, 60))
    buf = io.BytesIO()
    im.save(buf, 'PNG', transparency=0)
    out = open_image(process_upload(buf.getvalue()).jpeg)
    assert min(out.getpixel((5, 5))) > 245


def test_heic():
    p = process_upload(heic_bytes((800, 600)))
    im = open_image(p.jpeg)
    assert im.format == 'JPEG' and im.size == (800, 600)
    r, g, b = im.getpixel((400, 300))
    assert b > 150 and r < 80


def test_webp():
    buf = io.BytesIO()
    Image.new('RGB', (300, 400), (10, 200, 10)).save(buf, 'WEBP')
    assert process_upload(buf.getvalue()).width == 300


def test_srgb_profile_kept_colors():
    im = Image.new('RGB', (100, 100), (120, 60, 30))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=95, icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    r, g, b = open_image(process_upload(buf.getvalue()).jpeg).getpixel((50, 50))
    assert abs(r - 120) < 8 and abs(g - 60) < 8 and abs(b - 30) < 8


@pytest.mark.parametrize('data, message', [
    (b'', MSG_EMPTY),
    (b'not an image at all' * 10, MSG_NOT_PHOTO),
    (b'GIF89a' + b'\0' * 100, MSG_NOT_PHOTO),
])
def test_bad_files(data, message):
    with pytest.raises(ImageError) as ex:
        process_upload(data)
    assert ex.value.message == message


def test_gif_rejected_even_if_valid():
    buf = io.BytesIO()
    Image.new('RGB', (10, 10)).save(buf, 'GIF')
    with pytest.raises(ImageError) as ex:
        process_upload(buf.getvalue())
    assert ex.value.message == MSG_NOT_PHOTO


def test_truncated_jpeg():
    data = jpeg_bytes((1200, 1600))
    with pytest.raises(ImageError):
        process_upload(data[: len(data) // 3])


def test_too_big():
    with pytest.raises(ImageError) as ex:
        process_upload(b'\xff\xd8' + b'0' * (30 * 1024 * 1024 + 1))
    assert ex.value.message == MSG_TOO_BIG


def test_pixel_bomb_rejected_before_decoding():
    im = Image.new('L', (8000, 7000), 0)                          # 56 Мп PNG сжимается в килобайты
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    with pytest.raises(ImageError) as ex:
        process_upload(buf.getvalue())
    assert ex.value.message == MSG_TOO_MANY_PX


def test_avif_not_accepted():
    """AVIF нет в договоре (JPEG, PNG, WEBP, HEIC): лишний разборщик на входе не нужен."""
    buf = io.BytesIO()
    Image.new('RGB', (40, 40), (10, 20, 30)).save(buf, 'AVIF')
    with pytest.raises(ImageError) as ex:
        process_upload(buf.getvalue())
    assert ex.value.message == MSG_NOT_PHOTO


def test_broken_heic_is_a_clear_error():
    data = heic_bytes((800, 600))
    with pytest.raises(ImageError) as ex:
        process_upload(data[: len(data) // 2])
    assert ex.value.message in (MSG_BROKEN, MSG_NOT_PHOTO)


def test_progressive_jpeg_pixel_limit():
    """Прогрессивный JPEG не декодируется уменьшенным (libjpeg держит коэффициенты всего кадра): выше 50 Мп — нет."""
    im = Image.new('L', (7200, 7200), 128)                      # 51,8 Мп
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=20, progressive=True)
    with pytest.raises(ImageError) as ex:
        process_upload(buf.getvalue())
    assert ex.value.message == MSG_TOO_MANY_PX
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=20)                             # обычный (baseline) — можно, он декодируется уменьшенным
    assert max(process_upload(buf.getvalue()).width, 1) == 2000


def test_preview_and_widths():
    t = open_image(preview(jpeg_bytes((1650, 2200)), 480))
    assert t.size == (480, 640)
    assert preview_width(None) == 480 and preview_width('100') == 240 and preview_width('5000') == 960
    assert preview_width('abc') == 480


def test_uploads_store(tmp_path):
    up = Uploads(tmp_path)
    uid = up.save(process_upload(jpeg_bytes((600, 800))))
    assert uid.startswith('up_') and up.exists(uid)
    assert open_image(up.read(uid)).size == (600, 800)
    assert up.thumb_path(uid).name == f'{uid}_t.jpg'
    for bad in ('../etc/passwd', 'up_../../x', 'up_123', '', None, 'up_' + 'g' * 20):
        assert not up.exists(bad) and up.read(bad) is None and up.thumb_path(bad) is None
    old = time.time() - 25 * 3600                                      # загрузки живут 24 часа
    os.utime(tmp_path / f'{uid}.jpg', (old, old))
    assert not up.exists(uid)
    up.cleanup(force=True)
    assert not (tmp_path / f'{uid}.jpg').exists()
    f = up.store_preview('a' * 40, 480, b'jpeg')
    assert up.cached_preview('a' * 40, 480) == f and up.cached_preview('a' * 40, 240) is None
