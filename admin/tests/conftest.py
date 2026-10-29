"""Общее для тестов: временный клон репозитория сайта (данные настоящие), админка на LocalStore, картинки.

Репозиторий для клона — тот, в котором лежит admin/ (или ATTRE_TEST_REPO). Клонируется один раз за прогон,
каждый тест получает свой быстрый локальный клон (git clone --local: объекты по жёстким ссылкам).
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ADMIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ADMIN))

from PIL import Image  # noqa: E402

from app.config import load_config  # noqa: E402

SOURCE = Path(os.environ.get('ATTRE_TEST_REPO') or ADMIN.parent)


def pytest_configure(config):
    # starlette.testclient советует httpx2 вместо httpx — к админке это не относится (только тесты)
    config.addinivalue_line('filterwarnings', 'ignore:.*httpx2.*')
PASSWORDS = {'Дамира': 'пароль-дамиры-1', 'Жанна': 'zhanna-pass-2'}
CSRF = {'X-Requested-With': 'attre-admin'}


def git(cwd, *args) -> str:
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


def _shrink_jpeg(data: bytes) -> bytes:
    im = Image.open(io.BytesIO(data))
    im.draft('RGB', (240, 320))
    im = im.convert('RGB')
    im.thumbnail((240, 320))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=70)
    return buf.getvalue()


@pytest.fixture(scope='session')
def origin_repo(tmp_path_factory) -> Path:
    """Копия репозитория сайта для тестов: клон текущей ветки (данные — настоящие, все файлы как в ветке),
    но фото товаров уменьшены до 240px, а фото главной (админке не нужны) не копируются — иначе каждый тест
    держал бы на диске 120+ МБ. Один коммит без истории; каждый тест клонирует её заново (быстро и мало места)."""
    base = tmp_path_factory.mktemp('origin')
    full, small = base / 'full', base / 'repo'
    branch = git(SOURCE, 'rev-parse', '--abbrev-ref', 'HEAD')
    args = ['clone', '-q', '--depth', '1'] + (['--branch', branch] if branch and branch != 'HEAD' else [])
    subprocess.run(['git', *args, SOURCE.resolve().as_uri(), str(full)], check=True, capture_output=True)
    subprocess.run(['git', 'init', '-q', str(small)], check=True, capture_output=True)
    for rel in git(full, 'ls-files', '-z').split('\0'):
        if not rel or rel.startswith('media/home/'):
            continue
        src, dst = full / rel, small / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        dst.write_bytes(_shrink_jpeg(data) if rel.startswith('media/products/') and rel.endswith('.jpg') else data)
    git(small, 'add', '-A')
    git(small, '-c', 'user.name=Тест', '-c', 'user.email=test@attre.local', 'commit', '-q', '-m', 'копия для тестов')
    shutil.rmtree(full)
    return small


@pytest.fixture
def repo(origin_repo, tmp_path) -> Path:
    dest = tmp_path / 'repo'
    subprocess.run(['git', 'clone', '-q', '--local', str(origin_repo), str(dest)], check=True, capture_output=True)
    git(dest, 'config', 'user.name', 'Тест')                 # для коммитов «руками» внутри тестов
    git(dest, 'config', 'user.email', 'test@attre.local')
    return dest


# ——— данные репозитория, от которых тесты не должны зависеть буквально ———
# Данные сайта меняются (фото переименовывают, товары переводят на variants), поэтому тесты берут имена фото
# из файлов товаров, а товары старого формата (без variants) кладут сами — см. фикстуру legacy.

LEGACY_FILE = Path(__file__).with_name('legacy_products.json')


def product_doc(repo: Path, slug: str) -> dict:
    return json.loads((repo / 'data' / 'products' / f'{slug}.json').read_text('utf-8'))


def product_photos(repo: Path, slug: str) -> list[str]:
    """Все фото товара по порядку: фото цветов (variants) или старый список images."""
    d = product_doc(repo, slug)
    out = list(d.get('images') or [])
    for v in d.get('variants') or []:
        out += v.get('images') or []
    return out


def first_photo(repo: Path, slug: str) -> str:
    return product_photos(repo, slug)[0]


@pytest.fixture
def legacy(repo) -> dict:
    """Товары старого формата (без variants, как до коммита 4f25beb): altea, monbasa, tokyo, innsbruck, london,
    seattle — вместо нынешних файлов, вместе со своими фото altea-1.jpg… Один коммит «старый формат»."""
    docs = json.loads(LEGACY_FILE.read_text('utf-8'))
    for slug, doc in docs.items():
        (repo / 'data' / 'products' / f'{slug}.json').write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + '\n', 'utf-8')
        for i, rel in enumerate(doc.get('images') or []):
            f = repo / rel
            if not f.exists():
                f.write_bytes(jpeg_bytes((240, 320), (60 + 20 * i, 90, 120), quality=70))
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'старый формат товаров')
    return docs


def make_config(repo: Path, tmp: Path, **extra):
    env = {
        'STORE': 'local', 'LOCAL_REPO': str(repo), 'TMP_DIR': str(tmp / 'tmp'),
        'ADMIN_USERS': ';'.join(f'{n}:{p}' for n, p in PASSWORDS.items()),
        'SESSION_SECRET': 'test-secret-0123456789-' + 'x' * 30, 'SITE_URL': 'https://example.test/attre-site/v4/',
        **extra,
    }
    return load_config(env)


@pytest.fixture
def cfg(repo, tmp_path):
    return make_config(repo, tmp_path)


# ——— картинки ———

def jpeg_bytes(size=(1200, 1600), color=(180, 140, 100), exif_orientation: int | None = None, quality=90) -> bytes:
    im = Image.new('RGB', size, color)
    for x in range(0, size[0], 40):                      # немного деталей, чтобы JPEG был похож на фото
        im.paste((color[0] // 2, color[1], 255 - color[2]), (x, 0, x + 8, size[1]))
    buf = io.BytesIO()
    kw = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kw['exif'] = exif.tobytes()
    im.save(buf, 'JPEG', quality=quality, **kw)
    return buf.getvalue()


def png_rgba_bytes(size=(400, 600)) -> bytes:
    """Прозрачный фон, посередине красный квадрат."""
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    im.paste((200, 0, 0, 255), (100, 200, 300, 400))
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


def heic_bytes(size=(800, 600), color=(20, 120, 200)) -> bytes:
    import pillow_heif
    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format='HEIF', quality=80)
    return buf.getvalue()


def open_image(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im.load()
    return im
