"""Каталог: чтение (наследие → variants), проверка, запись в формате сайта, транслит, порядок, настройки."""
from __future__ import annotations

import json
import re

import pytest

import threading

from app import catalog as catalog_mod
from app.catalog import (MEDIA, MSG_CONFLICT_DATA, MSG_SALE, PRODUCTS, Catalog, CatalogError, Conflict, NotFound, dumps,
                         int_in, media_path, sale_of, site_order, size_in, small_json, translit, tri_in)
from app.images import Uploads, process_upload
from app.store import LocalStore
from conftest import first_photo, git, jpeg_bytes, product_doc, product_photos


@pytest.fixture
def cat(repo, tmp_path):
    return Catalog(LocalStore(repo), Uploads(tmp_path / 'up'), 'https://example.test/')


def upload(cat, size=(900, 1200)):
    return 'upload:' + cat.uploads.save(process_upload(jpeg_bytes(size)))


def read(repo, slug):
    return json.loads((repo / PRODUCTS / f'{slug}.json').read_text('utf-8'))


def new_product(**kw):
    p = {'name': {'ru': 'Новая сумка'}, 'cat': 'bags', 'variants': [{'color': 'black', 'images': []}]}
    p.update(kw)
    return p


def pool(repo) -> list[str]:
    """Фото, которые точно есть в репозитории (имена берём из данных: они меняются вместе с сайтом)."""
    return sorted(f'media/products/{f.name}' for f in (repo / 'media' / 'products').glob('*.jpg'))


def fill(obj, photos):
    """'P0', 'P1'… в тестовых данных → настоящие фото из репозитория."""
    if isinstance(obj, str) and re.fullmatch(r'P\d+', obj):
        return photos[int(obj[1:])]
    if isinstance(obj, list):
        return [fill(x, photos) for x in obj]
    if isinstance(obj, dict):
        return {k: fill(v, photos) for k, v in obj.items()}
    return obj


# ——— помощники ———

@pytest.mark.parametrize('src, slug', [
    ('Altea', 'altea'), ('Алтея', 'alteya'), ('Жёлтая шуба', 'zheltaya-shuba'), ('Щука и ёж', 'shchuka-i-ezh'),
    ('Цветочек «Мини»', 'tsvetochek-mini'), ('Юла Чача', 'yula-chacha'), ('Сыр', 'syr'), ('Хобо', 'hobo'),
    ('Қазақ', 'kazak'), ('Әсем сөмке', 'asem-somke'), ('Ұлы Үй', 'uly-uy'), ('Ғалым Ңң', 'galym-nn'),
    ('Һ і', 'h-i'), ('attré Café', 'attre-cafe'), ('  Copenhagen   Mini  ', 'copenhagen-mini'), ('№ 5', 'no-5'),
    ('★★★', ''), ('Сумка-ведро 2.0', 'sumka-vedro-2-0'),
])
def test_translit(src, slug):
    assert translit(src) == slug


def test_translit_long_cut_on_dash():
    s = translit('очень длинное название сумки для проверки обрезки адреса страницы товара')
    assert len(s) <= 50 and not s.endswith('-') and s.startswith('ochen-dlinnoe')


def test_int_and_size_and_text_helpers():
    assert int_in('45 000', 'price', 0, 10_000_000, 'm') == 45000
    assert int_in('45 000 ₸', 'price', 0, 10_000_000, 'm') == 45000
    assert int_in(45000.0, 'price', 0, 10_000_000, 'm') == 45000
    assert int_in('', 'price', 0, 1, 'm') is None and int_in(None, 'price', 0, 1, 'm') is None
    for bad in (1.5, '1.5', 'abc', -1, True, 10_000_001, [1]):
        with pytest.raises(CatalogError) as ex:
            int_in(bad, 'price', 0, 10_000_000, 'сообщение')
        assert ex.value.field == 'price' and ex.value.message == 'сообщение'
    assert size_in('25,5', 'size.w', 'Ширина') == 25.5 and size_in(30.0, 'size.w', 'Ширина') == 30
    for bad in (0, 201, 'x', True):
        with pytest.raises(CatalogError):
            size_in(bad, 'size.w', 'Ширина')
    t = tri_in({'ru': '  Altea \n', 'kz': None}, 'name', 'Название', 60)
    assert t == {'ru': 'Altea', 'kz': '', 'en': ''}
    assert tri_in('Просто строка', 'type', 'Тип', 60)['ru'] == 'Просто строка'
    assert tri_in({'ru': 'а\r\n\r\n\r\nб\x07'}, 'desc', 'Описание', 2000, multiline=True)['ru'] == 'а\n\nб'
    with pytest.raises(CatalogError) as ex:
        tri_in({'kz': 'x' * 61}, 'name', 'Название', 60)
    assert ex.value.field == 'name.kz' and 'казахском' in ex.value.message


def test_site_order_like_core():
    assert site_order(10) == 10 and site_order(0) == 9999 and site_order(-10) == 9999 and site_order(None) == 9999
    assert site_order('20') == 20


def test_media_path():
    assert media_path('media/products/altea-1.jpg') == 'media/products/altea-1.jpg'
    assert media_path('altea-1.jpg') == 'media/products/altea-1.jpg'
    assert media_path({'image': 'x/y/altea-2.JPG'}) == 'media/products/altea-2.JPG'
    assert media_path('../../etc/passwd') is None and media_path('') is None and media_path(5) is None


# ——— чтение ———

def test_legacy_product_read_as_one_variant(cat, legacy):
    data = cat.product('altea')
    p = data['product']
    assert data['sha'] == cat.store.blob_sha('data/products/altea.json')
    assert p['slug'] == 'altea' and p['id'] == '001' and p['published'] is True
    for k in ('images', 'colors', 'color', 'materials'):
        assert k not in p
    # старый «white» в палитре теперь «молочный» (milky); на первом фото Altea и правда молочная
    assert p['variants'] == [{'color': 'milky', 'name': {'ru': '', 'kz': '', 'en': ''}, 'material': 'leather',
                              'images': [f'media/products/altea-{i}.jpg' for i in range(1, 6)]}]
    assert p['size'] == {'w': None, 'h': None, 'd': None} and p['price'] is None


def test_legacy_without_palette_color_asks_to_choose(cat, legacy):
    v = cat.product('monbasa')['product']['variants']        # старый цвет «animal» в новой палитре нет
    assert v[0]['color'] == '' and v[0]['material'] == 'pony' and v[0]['images']


def test_legacy_first_palette_color_and_materials(cat, legacy):
    assert cat.product('tokyo')['product']['variants'][0]['color'] == 'yellow'    # mustard → жёлтый
    assert cat.product('innsbruck')['product']['variants'][0]['color'] == 'red'   # первый из старого списка
    v = cat.product('london')['product']['variants'][0]
    assert v['material'] == 'suede' and v['materials'] == ['suede', 'leather']   # оба материала не теряем
    assert 'materials' not in cat.product('seattle')['product']['variants'][0]


def test_product_not_found(cat):
    with pytest.raises(NotFound):
        cat.product('nope')
    with pytest.raises(NotFound):
        cat.product('../settings')


def test_products_list_sorted_like_site(cat, repo):
    items = cat.products()
    assert len(items) == len(list((repo / PRODUCTS).glob('*.json'))) and items[0]['slug'] == 'altea'
    orders = [site_order(x['order']) for x in items]
    assert orders == sorted(orders)
    a = items[0]
    doc = product_doc(repo, 'altea')
    assert a['name'] == 'Altea' and a['type'] == 'сумка-ведро'
    assert a['colors'] == [v['color'] for v in doc['variants']] and a['photos'] == len(product_photos(repo, 'altea'))
    assert a['thumb'].startswith(f'/api/media/{first_photo(repo, "altea").rsplit("/", 1)[1]}?w=480&v=')
    assert set(a) >= {'slug', 'id', 'name', 'cat', 'type', 'price', 'stock', 'soon', 'new', 'popular', 'published',
                      'order', 'colors', 'thumb', 'photos'}


def test_meta(cat):
    m = cat.meta(['Дамира', 'Жанна'])
    assert [c['key'] for c in m['palette']][:3] == ['black', 'blue', 'brown'] and len(m['palette']) == 15
    leopard = next(c for c in m['palette'] if c['key'] == 'leopard')
    assert leopard['hex'] is None and leopard['pattern'] == 'leopard' and leopard['name']['ru'] == 'леопардовый'
    cats = {c['key']: c for c in m['categories']}
    assert cats['acc']['leaf'] is False and cats['cardholder']['parent'] == 'acc' and cats['bags']['leaf']
    assert cats['acc']['count'] == cats['cardholder']['count'] + cats['charms']['count']
    assert [x['key'] for x in m['materials']] == ['leather', 'suede', 'pony', 'textile', 'eco-leather']
    assert {'ru': 'сумка-ведро', 'kz': 'шелек сөмке', 'en': 'bucket bag'} in m['types']
    assert m['users'] == ['Дамира', 'Жанна'] and m['site_url'] == 'https://example.test/'


# ——— проверки ———

@pytest.mark.parametrize('patch, field', [
    ({'name': {'ru': ''}}, 'name.ru'),
    ({'name': {'ru': 'x' * 61}}, 'name.ru'),
    ({'cat': 'acc'}, 'cat'),                                 # родитель — не лист
    ({'cat': 'shoes'}, 'cat'),
    ({'variants': []}, 'variants'),
    ({'variants': [{'color': 'white', 'images': ['P0']}]}, 'variants.0.color'),
    ({'variants': [{'color': 'black', 'images': []}]}, 'variants.0.images'),
    ({'variants': [{'color': 'black', 'images': ['media/products/nope.jpg']}]}, 'variants.0.images'),
    ({'variants': [{'color': 'black', 'images': ['upload:up_00000000000000000000']}]}, 'variants.0.images'),
    ({'variants': [{'color': 'black', 'images': [f'P{i}' for i in range(9)]}]}, 'variants.0.images'),
    ({'variants': [{'color': 'black', 'material': 'gold', 'images': ['P0']}]}, 'variants.0.material'),
    ({'variants': [{'color': 'brown', 'images': ['P0']}, {'color': 'brown', 'images': ['P1']}]},
     'variants.1.name.ru'),
    ({'price': -1}, 'price'), ({'price': 1.5}, 'price'), ({'price': 10_000_001}, 'price'), ({'price': 'дорого'}, 'price'),
    ({'stock': -1}, 'stock'), ({'stock': 0.5}, 'stock'),
    ({'size': {'w': 0}}, 'size.w'), ({'size': {'h': 201}}, 'size.h'), ({'size': {'d': 'глубокая'}}, 'size.d'),
    ({'desc': {'ru': 'x' * 2001}}, 'desc.ru'), ({'strap': {'en': 'x' * 2001}}, 'strap.en'),
])
def test_validation(cat, repo, patch, field):
    base = new_product(variants=[{'color': 'black', 'images': ['P0']}])
    base.update(patch)
    base = fill(base, pool(repo))
    with pytest.raises(CatalogError) as ex:
        cat.create(base, 'Дамира')
    assert ex.value.field == field and ex.value.status == 400
    assert ex.value.message and ex.value.message[0].isupper()


def test_duplicate_color_with_shade_name_ok(cat, repo):
    p0, p1 = pool(repo)[:2]
    r = cat.create(new_product(variants=[
        {'color': 'brown', 'images': [p0]},
        {'color': 'brown', 'name': {'ru': 'карамельный'}, 'images': [p1]}]), 'Жанна')
    vs = read(repo, r['slug'])['variants']
    assert vs == [{'color': 'brown', 'images': [p0]},
                  {'color': 'brown', 'name': {'ru': 'карамельный', 'kz': '', 'en': ''}, 'images': [p1]}]


# ——— создание ———

def test_create_product(cat, repo):
    up1, up2 = upload(cat), upload(cat, (1200, 900))
    p0 = pool(repo)[0]
    next_id = str(max(int(json.loads(f.read_text('utf-8'))['id']) for f in (repo / PRODUCTS).glob('*.json')) + 1)
    before = git(repo, 'rev-parse', 'HEAD')
    r = cat.create({'name': {'ru': 'Жёлтая Шуба', 'kz': '', 'en': 'Yellow'}, 'cat': 'charms',
                    'type': {'ru': 'брелок'}, 'price': '12 500', 'stock': None, 'new': True,
                    'desc': {'ru': 'Мягкий.\n\nТёплый.'}, 'size': {'w': '10', 'h': 12.5, 'd': None},
                    'slug': 'hack', 'id': '999', 'order': -5, 'evil': 'x',
                    'variants': [{'color': 'yellow', 'material': 'pony', 'images': [up1, up2, up1]},
                                 {'color': 'milky', 'images': [p0, up2]}]}, 'Жанна')
    assert r['slug'] == 'zheltaya-shuba' and r['url'] == 'https://example.test/ru/p/zheltaya-shuba/'
    assert r['commit'] == git(repo, 'rev-parse', 'HEAD') != before
    raw = (repo / PRODUCTS / 'zheltaya-shuba.json').read_bytes()
    doc = json.loads(raw)
    assert raw == dumps(doc)                                               # формат как у сайта
    assert list(doc) == ['id', 'published', 'order', 'cat', 'name', 'type', 'new', 'popular', 'soon', 'price',
                         'stock', 'desc', 'strap', 'size', 'variants']
    assert doc['id'] == next_id.zfill(3) and doc['published'] is True and doc['price'] == 12500
    assert doc['size'] == {'w': 10, 'h': 12.5, 'd': None} and doc['desc']['ru'] == 'Мягкий.\n\nТёплый.'
    assert 'evil' not in doc and 'slug' not in doc
    v1, v2 = doc['variants']
    assert v1['material'] == 'pony' and len(v1['images']) == 2              # повтор того же фото — один раз
    assert all(p.startswith('media/products/zheltaya-shuba-yellow-') and p.endswith('.jpg') for p in v1['images'])
    assert v2['images'][0] == p0 and v2['images'][1] == v1['images'][1]
    for p in v1['images']:
        assert (repo / p).is_file()
    log = git(repo, 'log', '-1', '--format=%an|%s')
    assert log == 'Жанна|Админка: новый товар «Жёлтая Шуба» (Жанна)'
    changed = git(repo, 'show', '--name-only', '--format=', 'HEAD').splitlines()
    assert 'data/products/zheltaya-shuba.json' in changed and len([c for c in changed if c.startswith(MEDIA)]) == 2


def test_create_order_first_with_renumber(cat, repo):
    """Сейчас минимальный order = 10: «−10» дало бы 0, а сайт ставит 0 в конец — все получают 1010, 1020…"""
    p0, p1 = pool(repo)[:2]
    altea_before = read(repo, 'altea')
    r = cat.create(new_product(variants=[{'color': 'black', 'images': [p0]}]), 'Дамира')
    assert read(repo, r['slug'])['order'] == 1000
    assert read(repo, 'altea')['order'] == 1010 and read(repo, 'bergen')['order'] == 1020
    first = cat.products()[0]
    assert first['slug'] == r['slug']
    raw_altea = (repo / PRODUCTS / 'altea.json').read_bytes()
    assert raw_altea == dumps(json.loads(raw_altea))
    assert json.loads(raw_altea) == {**altea_before, 'order': 1010}        # чужие товары: только order
    assert list(json.loads(raw_altea)) == list(altea_before)
    r2 = cat.create(new_product(name={'ru': 'Ещё'}, variants=[{'color': 'red', 'images': [p1]}]), 'Дамира')
    assert read(repo, r2['slug'])['order'] == 990                         # теперь просто «минимальный − 10»
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD').splitlines() == [f'data/products/{r2["slug"]}.json']
    assert [x['slug'] for x in cat.products()[:3]] == [r2['slug'], r['slug'], 'altea']


def test_create_unique_slug(cat, repo):
    v = [{'color': 'black', 'images': pool(repo)[:1]}]
    assert cat.create(new_product(name={'ru': 'Altea'}, variants=v), 'Дамира')['slug'] == 'altea-2'
    assert cat.create(new_product(name={'ru': 'ALTEA'}, variants=v), 'Дамира')['slug'] == 'altea-3'
    assert cat.create(new_product(name={'ru': '★'}, variants=v), 'Дамира')['slug'] == 'tovar'
    assert cat.create(new_product(name={'ru': 'Order'}, variants=v), 'Дамира')['slug'] == 'order-2'


# ——— изменение ———

def test_update_legacy_converts_and_keeps_unknown_fields(cat, repo, legacy):
    doc = read(repo, 'altea')
    doc['focus'] = {'x': 0.4, 'y': 0.5}                                   # поле, которого нет в форме
    (repo / PRODUCTS / 'altea.json').write_bytes(dumps(doc))
    git(repo, 'commit', '-qam', 'focus')
    got = cat.product('altea')
    p = got['product']
    assert p['focus'] == {'x': 0.4, 'y': 0.5}
    p['variants'][0]['color'] = 'milky'
    p['variants'][0]['images'] = p['variants'][0]['images'][:3]          # два фото убрали
    p['price'] = 45000
    r = cat.update('altea', p, got['sha'], 'Дамира')
    raw = (repo / PRODUCTS / 'altea.json').read_bytes()
    new = json.loads(raw)
    assert raw == dumps(new) and r['commit'] == git(repo, 'rev-parse', 'HEAD')
    assert new['focus'] == {'x': 0.4, 'y': 0.5} and new['id'] == '001' and new['order'] == 10
    for k in ('images', 'colors', 'color', 'materials'):
        assert k not in new
    keys = list(new)
    assert list(doc)[list(doc).index('images') - 1] == 'stock'
    assert keys[keys.index('variants') - 1] == 'stock' and keys[-1] == 'focus'   # variants — на месте старого images
    assert new['variants'] == [{'color': 'milky', 'material': 'leather',
                                'images': [f'media/products/altea-{i}.jpg' for i in (1, 2, 3)]}]
    assert new['price'] == 45000
    # фото, на которые больше никто не ссылается, удалены тем же коммитом
    changed = sorted(git(repo, 'show', '--name-status', '--format=', 'HEAD').splitlines())
    assert changed == ['D\tmedia/products/altea-4.jpg', 'D\tmedia/products/altea-5.jpg', 'M\tdata/products/altea.json']
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: «Altea» — сохранено (Дамира)'


def test_update_conflict_and_noop(cat, repo):
    got = cat.product('bergen')
    p = got['product']
    first = cat.update('bergen', {**p, 'price': 30000}, got['sha'], 'Дамира')
    head = git(repo, 'rev-parse', 'HEAD')
    with pytest.raises(Conflict) as ex:                                     # вторая вкладка со старой версией
        cat.update('bergen', {**p, 'price': 31000}, got['sha'], 'Жанна')
    assert ex.value.status == 409 and 'Обновите страницу' in ex.value.message
    assert git(repo, 'rev-parse', 'HEAD') == head
    fresh = cat.product('bergen')
    with pytest.raises(CatalogError) as ex:                                 # без sha — просим обновить страницу
        cat.update('bergen', {**fresh['product'], 'price': 1}, None, 'Жанна')
    assert ex.value.status == 400 and ex.value.field == 'sha'
    same = cat.update('bergen', fresh['product'], 'не тот sha', 'Жанна')    # ничего не изменилось — не спорим
    assert same['unchanged'] and same['commit'] == head == first['commit']


def test_order_change_meanwhile_is_not_a_conflict(cat, repo):
    """Пока товар открыт в редакторе, другая основательница поменяла порядок или добавила товар — сохраняем."""
    got = cat.product('bergen')
    other = cat.product('altea')
    slugs = [x['slug'] for x in cat.products()]
    cat.reorder(slugs[::-1], 'Жанна')                                      # у bergen поменялся только order
    r = cat.update('bergen', {**got['product'], 'price': 39000}, got['sha'], 'Дамира')
    doc = read(repo, 'bergen')
    assert doc['price'] == 39000 and doc['order'] == 10 * (slugs[::-1].index('bergen') + 1)
    assert r['commit'] == git(repo, 'rev-parse', 'HEAD')
    cat.delete('altea', other['sha'], 'Дамира')                            # и удалить по старой версии можно
    assert not (repo / PRODUCTS / 'altea.json').exists()


def test_update_does_not_delete_photos_used_elsewhere(cat, repo):
    got = cat.product('bergen')
    p = got['product']
    own = product_photos(repo, 'bergen')
    p['variants'] = [{**p['variants'][0], 'images': [first_photo(repo, 'altea')]}]   # взяли чужое фото, свои убрали
    cat.update('bergen', p, got['sha'], 'Дамира')
    changed = git(repo, 'show', '--name-status', '--format=', 'HEAD').splitlines()
    assert sorted(changed) == sorted(['M\tdata/products/bergen.json'] + [f'D\t{x}' for x in own])
    assert not any('altea' in c for c in changed)
    got = cat.product('altea')
    with pytest.raises(NotFound):
        cat.update('nope', got['product'], got['sha'], 'Дамира')


def test_update_new_upload_named_by_slug_and_color(cat, repo):
    got = cat.product('seattle')
    p = got['product']
    p['variants'].append({'color': 'light-blue', 'images': [upload(cat)]})
    cat.update('seattle', p, got['sha'], 'Жанна')
    v = read(repo, 'seattle')['variants']
    assert v[1]['color'] == 'light-blue' and v[1]['images'][0].startswith('media/products/seattle-light-blue-')
    assert len(v[1]['images'][0].rsplit('-', 1)[1]) == len('abcdef.jpg')


def test_hide_last_visible_product_refused(cat, repo):
    for slug in list(cat.raw_products(cat.store.snapshot())):
        if slug != 'altea':
            (repo / PRODUCTS / f'{slug}.json').unlink()
    git(repo, 'commit', '-qam', 'один товар')
    got = cat.product('altea')
    with pytest.raises(CatalogError) as ex:
        cat.update('altea', {**got['product'], 'published': False}, got['sha'], 'Дамира')
    assert ex.value.field == 'published'
    with pytest.raises(CatalogError):
        cat.delete('altea', got['sha'], 'Дамира')


def test_variant_materials(cat, repo, legacy):
    got = cat.product('london')                         # старый товар: замша и кожа
    p = got['product']
    v = p['variants'][0]
    v.pop('material')                                   # форма шлёт либо список (если материалов несколько)…
    cat.update('london', p, got['sha'], 'Дамира')
    saved = read(repo, 'london')['variants'][0]
    assert saved['materials'] == ['suede', 'leather'] and 'material' not in saved
    got = cat.product('london')
    p = got['product']
    p['variants'][0].pop('materials')
    p['variants'][0]['material'] = 'pony'               # …либо один материал
    cat.update('london', p, got['sha'], 'Дамира')
    saved = read(repo, 'london')['variants'][0]
    assert saved['material'] == 'pony' and 'materials' not in saved
    got = cat.product('london')
    p = got['product']
    p['variants'][0]['materials'] = ['pony', 'gold']
    with pytest.raises(CatalogError) as ex:
        cat.update('london', p, got['sha'], 'Дамира')
    assert ex.value.field == 'variants.0.material'


def test_update_keeps_variant_key_order(cat, repo):
    """Ключи цвета (name, hex, material, images) остаются на своих местах: в истории git меняется только то,
    что поменяли в форме. Форма присылает товар таким, каким его получила (JSON сохраняет порядок ключей)."""
    slug = next(f.stem for f in sorted((repo / PRODUCTS).glob('*.json'))
                if any('hex' in v for v in json.loads(f.read_text('utf-8')).get('variants') or []))
    before = read(repo, slug)
    got = cat.product(slug)
    p = json.loads(json.dumps(got['product']))
    p['price'] = 12345
    cat.update(slug, p, got['sha'], 'Дамира')
    after = read(repo, slug)
    assert [list(v) for v in after['variants']] == [list(v) for v in before['variants']]
    assert after == {**before, 'price': 12345} and list(after) == list(before)
    diff = git(repo, 'show', '--format=', '--unified=0', 'HEAD').splitlines()
    assert [x for x in diff if x[:1] in '+-' and not x.startswith(('+++', '---'))] == [
        '-  "price": null,', '+  "price": 12345,']


def test_unknown_variant_keys_only_known_ones_kept(cat, repo):
    got = cat.product('verona')
    p = got['product']
    p['variants'][0].update(hex='#123456', uid='u1abc', _ui=True)
    cat.update('verona', p, got['sha'], 'Дамира')
    v = read(repo, 'verona')['variants'][0]
    assert v['hex'] == '#123456' and 'uid' not in v and '_ui' not in v


# ——— скидка (sale_price) ———

def diff_lines(repo) -> list[str]:
    diff = git(repo, 'show', '--format=', '--unified=0', 'HEAD').splitlines()
    return [x for x in diff if x[:1] in '+-' and not x.startswith(('+++', '---'))]


def test_sale_of_like_site():
    """Скидка есть, только если цена задана и 0 < sale_price < price — иначе на сайте обычная цена. Числа — как их
    читает сайт (core.clean_product): float(), копейки отбрасываются, «45 000» с пробелом — не число."""
    assert sale_of(45000, 36000) == 36000 and sale_of(45000.0, 36000.0) == 36000 and sale_of(45000, 44999) == 44999
    assert sale_of('45000', '36000') == 36000 and sale_of(45000.9, 36000.7) == 36000      # файл исправили руками
    assert sale_of(45000, 44999.5) == 44999 and sale_of(45000, 1.5) == 1
    for price, sale in ((None, 36000), (0, 1), (0.5, 0.2), (45000, 45000), (45000, 45000.4), (45000, 50000),
                        (45000, 0), (45000, 0.9), (45000, -1), (45000, None), (45000, 'дёшево'), ('45 000', 36000),
                        (45000, '36 000'), (45000, float('nan')), (float('inf'), 36000), (45000, [36000]),
                        (45000, 10 ** 400)):
        assert sale_of(price, sale) is None, (price, sale)


def test_sale_price_create_list_and_form(cat, repo):
    r = cat.create(new_product(price='45 000', sale_price='36 000 ₸', variants=[{'color': 'black', 'images': pool(repo)[:1]}]),
                   'Дамира')
    doc = read(repo, r['slug'])
    assert doc['price'] == 45000 and doc['sale_price'] == 36000
    keys = list(doc)
    assert keys[keys.index('price') + 1] == 'sale_price' and keys[keys.index('sale_price') + 1] == 'stock'
    assert cat.product(r['slug'])['product']['sale_price'] == 36000
    item = next(x for x in cat.products() if x['slug'] == r['slug'])
    assert item['price'] == 45000 and item['sale_price'] == 36000
    other = next(x for x in cat.products() if x['slug'] == 'altea')
    assert other['sale_price'] is None and cat.product('altea')['product']['sale_price'] is None


def test_sale_price_not_written_without_discount(cat, repo):
    for empty in (None, ''):
        r = cat.create(new_product(name={'ru': f'Без скидки {empty!r}'}, price=45000, sale_price=empty,
                                   variants=[{'color': 'black', 'images': pool(repo)[:1]}]), 'Дамира')
        assert 'sale_price' not in read(repo, r['slug'])


@pytest.mark.parametrize('price, sale, words', [
    (45000, 45000, 'Цена со скидкой должна быть меньше обычной (45 000 ₸).'),     # равна цене
    (45000, '50 000', 'Цена со скидкой должна быть меньше обычной (45 000 ₸).'),  # больше цены
    (None, 36000, 'Сначала укажите обычную цену'),
    ('', '36 000', 'Сначала укажите обычную цену'),
    (0, 36000, 'Сначала укажите обычную цену'),                     # 0 на сайте — тоже «цена по запросу»
    (45000, -1, MSG_SALE), (45000, '-36000', MSG_SALE), (45000, 0, MSG_SALE),
    (45000, 'дёшево', MSG_SALE), (45000, 1.5, MSG_SALE), (45000, '36 000,50', MSG_SALE), (45000, True, MSG_SALE),
    (45000, [36000], MSG_SALE), (45000, 10_000_001, MSG_SALE), (45000, 10 ** 30, MSG_SALE), (45000, '9' * 50, MSG_SALE),
    (45000, float('inf'), MSG_SALE), (45000, float('nan'), MSG_SALE),             # Infinity / NaN в JSON запроса
])
def test_sale_price_validation(cat, repo, price, sale, words):
    got = cat.product('bergen')
    head = git(repo, 'rev-parse', 'HEAD')
    with pytest.raises(CatalogError) as ex:
        cat.update('bergen', {**got['product'], 'price': price, 'sale_price': sale}, got['sha'], 'Дамира')
    assert ex.value.field == 'sale_price' and ex.value.status == 400 and ex.value.message.startswith(words)
    assert git(repo, 'rev-parse', 'HEAD') == head
    with pytest.raises(CatalogError) as ex:                                 # и у нового товара — то же
        cat.create(new_product(price=price, sale_price=sale, variants=[{'color': 'black', 'images': pool(repo)[:1]}]),
                   'Дамира')
    assert ex.value.field == 'sale_price' and ex.value.message.startswith(words)


def test_sale_price_on_change_off(cat, repo):
    """Включили скидку — одна новая строка сразу после цены; поменяли — одна строка; выключили — строки нет."""
    before = read(repo, 'bergen')
    got = cat.product('bergen')
    cat.update('bergen', {**got['product'], 'price': 52000, 'sale_price': 41600}, got['sha'], 'Дамира')
    assert diff_lines(repo) == ['-  "price": null,', '+  "price": 52000,', '+  "sale_price": 41600,']
    got = cat.product('bergen')
    assert got['product']['sale_price'] == 41600
    cat.update('bergen', {**got['product'], 'sale_price': '39 000'}, got['sha'], 'Жанна')
    assert diff_lines(repo) == ['-  "sale_price": 41600,', '+  "sale_price": 39000,']
    got = cat.product('bergen')
    cat.update('bergen', {**got['product'], 'sale_price': None}, got['sha'], 'Дамира')   # выключили скидку
    assert diff_lines(repo) == ['-  "sale_price": 39000,']
    after = read(repo, 'bergen')
    assert 'sale_price' not in after and after == {**before, 'price': 52000} and list(after) == list(before)
    got = cat.product('bergen')
    assert cat.update('bergen', got['product'], got['sha'], 'Дамира')['unchanged']   # без скидки — без изменений


def test_sale_price_from_file_shown_as_is(cat, repo):
    """Неправильную скидку (вписали в файл руками) сайт не показывает — и список тоже; форма показывает её как есть,
    а при сохранении проверка объясняет, что не так."""
    doc = read(repo, 'bergen')
    (repo / PRODUCTS / 'bergen.json').write_bytes(dumps({**doc, 'price': 45000, 'sale_price': 60000}))
    git(repo, 'commit', '-qam', 'скидка руками')
    got = cat.product('bergen')
    assert got['product']['price'] == 45000 and got['product']['sale_price'] == 60000
    assert next(x for x in cat.products() if x['slug'] == 'bergen')['sale_price'] is None
    with pytest.raises(CatalogError) as ex:
        cat.update('bergen', got['product'], got['sha'], 'Дамира')
    assert ex.value.field == 'sale_price' and 'меньше обычной' in ex.value.message


def test_sale_price_legacy_product(cat, repo, legacy):
    """Старый товар (без variants) со скидкой: переходит на variants, а sale_price — сразу после price."""
    got = cat.product('altea')
    p = {**got['product'], 'price': 45000, 'sale_price': 36000}
    p['variants'][0]['color'] = 'milky'
    cat.update('altea', p, got['sha'], 'Дамира')
    new = read(repo, 'altea')
    keys = list(new)
    assert new['sale_price'] == 36000 and keys[keys.index('price') + 1] == 'sale_price'
    assert 'images' not in new and new['variants'][0]['color'] == 'milky'


@pytest.mark.parametrize('price, sale, shown', [
    ('45000', 36000.5, 36000),        # строкой и с копейками — сайт берёт 36 000, и список тоже
    (45000, '36 000', None),          # «36 000» с пробелом сайт числом не считает — скидки на сайте нет
])
def test_sale_price_list_like_site_for_hand_edited(cat, repo, price, sale, shown):
    doc = read(repo, 'bergen')
    (repo / PRODUCTS / 'bergen.json').write_bytes(dumps({**doc, 'price': price, 'sale_price': sale}))
    git(repo, 'commit', '-qam', 'скидка руками')
    assert next(x for x in cat.products() if x['slug'] == 'bergen')['sale_price'] == shown


# ——— удаление и порядок ———

def test_delete_product_and_photos(cat, repo):
    sha = cat.product('tokyo')['sha']
    with pytest.raises(Conflict):
        cat.delete('tokyo', 'f' * 40, 'Дамира')
    with pytest.raises(CatalogError) as ex:
        cat.delete('tokyo', '', 'Дамира')
    assert ex.value.status == 400
    r = cat.delete('tokyo', sha, 'Дамира')
    assert r['commit'] == git(repo, 'rev-parse', 'HEAD')
    assert not (repo / PRODUCTS / 'tokyo.json').exists()
    assert not list((repo / MEDIA).glob('tokyo-*'))
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: удалён «Tokyo» (Дамира)'
    with pytest.raises(NotFound):
        cat.delete('tokyo', sha, 'Дамира')


def test_reorder(cat, repo):
    slugs = [x['slug'] for x in cat.products()]
    old = {s: read(repo, s)['order'] for s in slugs}
    new = [slugs[2], slugs[0], slugs[1]] + slugs[3:]
    r = cat.reorder(new, 'Жанна')
    assert [x['slug'] for x in cat.products()] == new
    assert [read(repo, s)['order'] for s in new] == [10 * (i + 1) for i in range(len(new))]
    changed = set(git(repo, 'show', '--name-only', '--format=', 'HEAD').splitlines())
    # одним коммитом и только те файлы, где order правда поменялся
    assert changed == {f'data/products/{s}.json' for i, s in enumerate(new) if old[s] != 10 * (i + 1)}
    assert {f'data/products/{s}.json' for s in new[:3]} <= changed
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: порядок товаров (Жанна)'
    assert cat.reorder(new, 'Жанна') == {'commit': r['commit'], 'unchanged': True}
    with pytest.raises(Conflict):
        cat.reorder(new + ['nope'], 'Жанна')
    with pytest.raises(CatalogError):
        cat.reorder([new[0], new[0]], 'Жанна')
    cat.reorder([slugs[5]], 'Жанна')                                        # неполный список: остальные — следом
    assert cat.products()[0]['slug'] == slugs[5]


# ——— магазин и доставка ———

def test_settings_read(cat):
    s = cat.settings()
    assert s['contacts']['whatsapp'] == '77067232349' and s['contacts']['address']['ru'].startswith('Алматы')
    assert s['delivery']['free_from'] == 70000 and len(s['delivery']['kz']) == 2
    assert s['delivery']['world']['ru'] and s['promo']['ru'] and set(s['seller']) == {'name', 'bin'}
    assert s['sha']


def test_settings_save(cat, repo):
    s = cat.settings()
    i18n_before = json.loads((repo / 'data/i18n.json').read_text('utf-8'))
    s['contacts']['whatsapp'] = '+7 (701) 111-22-33'
    s['contacts']['instagram'] = 'https://www.instagram.com/attre.new/'
    s['contacts']['hours'] = {'ru': 'Часы работы: 10:00–21:00', 'kz': '', 'en': ''}
    s['delivery']['kz'].append({'price': 0, 'name': {'ru': 'Самовывоз'}, 'days': {'ru': 'сегодня'}})
    s['promo'] = {'ru': 'Скидка 10 %', 'kz': '', 'en': 'Sale 10 %'}
    s['seller'] = {'name': 'ИП Тест', 'bin': '9001 0130 0123'}
    r = cat.save_settings(s, 'Дамира')
    assert r['commit'] == git(repo, 'rev-parse', 'HEAD') and r['sha'] != s['sha']
    st = json.loads((repo / 'data/settings.json').read_text('utf-8'))
    assert st['whatsapp'] == '77011112233' and st['instagram'] == 'attre.new'
    assert st['delivery']['kz'][2] == {'price': 0, 'name': {'ru': 'Самовывоз', 'kz': '', 'en': ''},
                                       'days': {'ru': 'сегодня', 'kz': '', 'en': ''}}
    assert st['seller'] == {'name': 'ИП Тест', 'bin': '900101300123'}
    raw = (repo / 'data/i18n.json').read_bytes()
    i18n = json.loads(raw)
    assert raw == dumps(i18n)
    t = i18n['t']
    # сайт берёт эти тексты как есть — пустой казахский заполняется русским
    assert t['hours'] == {'ru': 'Часы работы: 10:00–21:00', 'kz': 'Часы работы: 10:00–21:00',
                          'en': 'Часы работы: 10:00–21:00'}
    assert t['promo'] == {'ru': 'Скидка 10 %', 'kz': 'Скидка 10 %', 'en': 'Sale 10 %'}
    changed_keys = {k for k in t if t[k] != i18n_before['t'].get(k)}
    assert changed_keys == {'hours', 'promo'}                               # остальные тексты сайта не тронуты
    again = cat.settings()
    assert again['sha'] == r['sha'] and again['promo']['kz'] == '' and again['promo']['en'] == 'Sale 10 %'
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: доставка и контакты (Дамира)'
    assert cat.save_settings(again, 'Дамира')['unchanged']


def test_settings_partial_and_conflict(cat, repo):
    s = cat.settings()
    cat.save_settings({'sha': s['sha'], 'promo': {'ru': 'Новая полоса'}}, 'Жанна')
    # тот же старый sha, но другой блок — можно (никто не трогал контакты)
    cat.save_settings({'sha': s['sha'], 'contacts': {**s['contacts'], 'email': 'new@attre.kz'}}, 'Дамира')
    assert json.loads((repo / 'data/settings.json').read_text('utf-8'))['email'] == 'new@attre.kz'
    # а полосу со старым sha — нельзя: её уже поменяли
    with pytest.raises(Conflict):
        cat.save_settings({'sha': s['sha'], 'promo': {'ru': 'Моя полоса'}}, 'Дамира')
    with pytest.raises(CatalogError) as ex:
        cat.save_settings({'promo': {'ru': 'x'}}, 'Дамира')
    assert ex.value.field == 'sha'


@pytest.mark.parametrize('block, value, field', [
    ('contacts', {'whatsapp': '12345'}, 'contacts.whatsapp'),
    ('contacts', {'instagram': 'плохой ник'}, 'contacts.instagram'),
    ('contacts', {'email': 'not-an-email'}, 'contacts.email'),
    ('contacts', {'map_url': '2gis.kz'}, 'contacts.map_url'),
    ('contacts', {'map_url': 'http://2gis.kz/almaty/firm/1'}, 'contacts.map_url'),      # только https
    ('contacts', {'address': {'ru': ''}}, 'contacts.address.ru'),
    ('delivery', {'free_from': -5}, 'delivery.free_from'),
    ('delivery', {'kz': [{'price': None, 'name': {'ru': 'Курьер'}}]}, 'delivery.kz.0.price'),
    ('delivery', {'kz': [{'price': 100, 'name': {'ru': ''}}]}, 'delivery.kz.0.name.ru'),
    ('delivery', {'world': {'ru': ''}}, 'delivery.world.ru'),
    ('promo', {'ru': ''}, 'promo.ru'),
    ('seller', {'name': 'ИП Тест', 'bin': ''}, 'seller.bin'),
    ('seller', {'name': 'ИП Тест', 'bin': '123'}, 'seller.bin'),
])
def test_settings_validation(cat, block, value, field):
    s = cat.settings()
    with pytest.raises(CatalogError) as ex:
        cat.save_settings({'sha': s['sha'], block: value}, 'Дамира')
    assert ex.value.field == field and ex.value.status == 400


# ——— проверка «чужих» полей и текстов ———

@pytest.mark.parametrize('patch', [
    {'hex': {'x': '<svg onload=alert(1)>'}}, {'hex': '#12345'}, {'hex': 'red'},
    {'pattern': 'x" onmouseover="alert(1)'}, {'pattern': ['leopard']},
    {'published': 'nope'}, {'published': 0},
])
def test_variant_site_fields_checked(cat, patch):
    """hex, pattern и published цвета сохраняются как были — но только правильные (как их понимает core.py)."""
    got = cat.product('verona')
    p = got['product']
    p['variants'][0].update(patch)
    with pytest.raises(CatalogError) as ex:
        cat.update('verona', p, got['sha'], 'Дамира')
    assert ex.value.field == 'variants.0' and 'обновите страницу' in ex.value.message.lower()


def test_variant_site_fields_ok(cat, repo):
    got = cat.product('verona')
    p = got['product']
    p['variants'][0].update(hex='#A1b2C3', pattern='croc', published=False)
    cat.update('verona', p, got['sha'], 'Дамира')
    v = read(repo, 'verona')['variants'][0]
    assert v['hex'] == '#A1b2C3' and v['pattern'] == 'croc' and v['published'] is False


def test_unknown_stored_fields_must_be_small(cat, repo):
    """Поле, которое уже есть в файле (его форма не знает), приходит обратно — только небольшим и неглубоким."""
    doc = read(repo, 'verona')
    doc['variants'][0]['note'] = 'старое'
    (repo / PRODUCTS / 'verona.json').write_bytes(dumps(doc))
    git(repo, 'commit', '-qam', 'note')
    got = cat.product('verona')
    p = got['product']
    deep = cur = {}
    for _ in range(600):                                  # раньше такая вложенность роняла сервер (RecursionError)
        cur['x'] = {}
        cur = cur['x']
    for bad in (deep, 'x' * 3000, [[[[['глубоко']]]]]):
        p['variants'][0]['note'] = bad
        with pytest.raises(CatalogError) as ex:
            cat.update('verona', p, got['sha'], 'Дамира')
        assert ex.value.field == 'variants.0'
    p['variants'][0]['note'] = {'ok': [1, 2, 'три']}
    cat.update('verona', p, got['sha'], 'Дамира')
    assert read(repo, 'verona')['variants'][0]['note'] == {'ok': [1, 2, 'три']}


def test_small_json():
    assert small_json(None) and small_json('x') and small_json({'a': [1, {'b': True}]})
    assert not small_json({'a': {'b': {'c': {'d': {'e': 1}}}}}) and not small_json('x' * 2001)
    assert not small_json({1: 'x'}) and not small_json(float('nan')) and not small_json({'a': {1, 2}})


def test_bidi_controls_removed(cat, repo):
    """Символы направления текста (U+202A–U+202E, U+2066–U+2069) «переворачивают» название — убираем."""
    r = cat.create(new_product(name={'ru': 'Al\u202etea\u2066 мини\u2069'},
                               variants=[{'color': 'black', 'images': pool(repo)[:1]}]), 'Дамира')
    assert read(repo, r['slug'])['name']['ru'] == 'Altea мини'


def test_photo_delete_conflicts_with_commit_meanwhile(cat, repo):
    """Фото «ничьё» по снимку, а между снимком и записью чужой коммит начал на него ссылаться в другом товаре —
    удалять нельзя: 409 «данные только что изменились», фото на месте."""
    got = cat.product('bergen')
    p = got['product']
    photo = p['variants'][0]['images'][-1]
    p['variants'][0]['images'] = p['variants'][0]['images'][:-1]
    real = cat.store._commit

    def racing(changes, message, author, expect):
        if photo in changes:                              # «Даулет руками» — прямо перед записью админки
            doc = read(repo, 'altea')
            doc['variants'][0]['images'].append(photo)
            (repo / PRODUCTS / 'altea.json').write_bytes(dumps(doc))
            git(repo, 'commit', '-qam', 'чужая правка')
        return real(changes, message, author, expect)

    cat.store._commit = racing
    with pytest.raises(Conflict) as ex:
        cat.update('bergen', p, got['sha'], 'Дамира')
    assert ex.value.message == MSG_CONFLICT_DATA
    assert (repo / photo).is_file() and git(repo, 'log', '-1', '--format=%s') == 'чужая правка'


def test_write_lock_wait_limited(cat, monkeypatch):
    """Чужое сохранение висит (GitHub медленный) — не ждём бесконечно, а говорим «попробуйте через минуту»."""
    monkeypatch.setattr(catalog_mod, 'LOCK_WAIT', 0.2)
    held, release = threading.Event(), threading.Event()

    def hold():
        with cat.store.write_lock:
            held.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(5)
    try:
        got = cat.product('bergen')
        with pytest.raises(CatalogError) as ex:
            cat.update('bergen', {**got['product'], 'price': 1}, got['sha'], 'Дамира')
        assert ex.value.status == 503 and 'через минуту' in ex.value.message
    finally:
        release.set()
        t.join()
