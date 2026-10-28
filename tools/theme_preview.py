"""Быстрая сборка одной темы без перерезки фото: python3 tools/theme_preview.py v1
Нужна хотя бы одна полная сборка (python3 build.py), чтобы в site/assets лежали фото.
Пишет только site/<подпапка темы>/ и копирует src/ поверх site/assets (стили и скрипты тем)."""
import shutil
import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import core  # noqa: E402
from build import THEMES  # noqa: E402

name = sys.argv[1]
sub = next(s for n, s, *_ in THEMES if n == name)
shutil.copytree(ROOT / 'src', core.OUT_ROOT / 'assets', dirs_exist_ok=True)
for p in core.DATA['products']:
    p['images'] = [f"{p['slug']}-{i + 1}" for i in range(len(p['srcs']))]
for item in [core.HOME['cover'], *core.HOME['banners']]:
    stem = Path(item['image']).stem
    item['_stem'], item['_ratio'] = stem, item.get('ratio', 2 / 3)
    item['_widths'] = [w for w in (750, 1125, 1600) if (core.OUT_ROOT / 'assets' / 'img' / 'home' / f'{stem}-{w}.webp').exists()]
theme = import_module(f'themes.{name}')
core.set_theme(name, sub)
out = core.CTX['out']
if sub and out.exists():
    shutil.rmtree(out)
n = 0
for l in core.LANGS:
    lang = l['code']
    core.write(f'{lang}/index.html', theme.home(lang))
    core.write(f'{lang}/catalog/index.html', theme.catalog(lang))
    core.write(f'{lang}/info/index.html', theme.info(lang))
    n += 3
    for c in core.present_cats():
        core.write(f'{lang}/c/{c}/index.html', theme.catalog(lang, c)); n += 1
    for p in core.DATA['products']:
        core.write(f'{lang}/p/{p["slug"]}/index.html', theme.product(p, lang)); n += 1
print(f'{name}: {n} страниц → {out}')
