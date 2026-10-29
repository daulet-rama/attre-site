"""API через fastapi.testclient: вход, перебор, CSRF, товары (создать/изменить/409/удалить/порядок),
фото (JPEG, PNG с прозрачностью, HEIC, плохие), превью, настройки, статус, фронт. LocalStore и GitHubStore."""
from __future__ import annotations

import json
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import LIFETIME, Auth
from app.main import CSP, MSG_BAD_PASSWORD, create_app
from app.store import GitHubStore
from conftest import (CSRF, PASSWORDS, first_photo, git, heic_bytes, jpeg_bytes, make_config, open_image,
                      png_rgba_bytes)
from fake_github import TOKEN, FakeGitHub


@pytest.fixture
def static(tmp_path):
    d = tmp_path / 'static'
    (d / 'js').mkdir(parents=True)
    (d / 'index.html').write_text('<!doctype html><title>attré · админка</title>INDEX', 'utf-8')
    (d / 'app.js').write_text('import "./js/api.js";\n', 'utf-8')
    (d / 'js' / 'api.js').write_text('export const x = 1;\n', 'utf-8')
    return d


@pytest.fixture
def app(cfg, static):
    return create_app(cfg, static_dir=static, login_delay=0)


@pytest.fixture
def anon(app):
    with TestClient(app, base_url='http://localhost') as c:
        yield c


def login(c, name='Дамира', password=None):
    return c.post('/api/login', json={'name': name, 'password': password or PASSWORDS[name]}, headers=CSRF)


@pytest.fixture
def client(anon):
    assert login(anon).status_code == 200
    return anon


def up(c, data: bytes, name='photo.jpg', mime='image/jpeg'):
    return c.post('/api/uploads', files={'file': (name, data, mime)}, headers=CSRF)


# ——— вход ———

def test_health_without_login(anon):
    r = anon.get('/api/health')
    assert r.status_code == 200 and r.json() == {'ok': True}


@pytest.mark.parametrize('path', ['/api/session', '/api/meta', '/api/products', '/api/products/altea',
                                  '/api/settings', '/api/status', '/api/media/altea-1.jpg',
                                  '/api/uploads/up_00000000000000000000'])
def test_login_required(anon, path):
    r = anon.get(path)
    assert r.status_code == 401
    assert r.json() == {'error': 'Войдите, чтобы продолжить.'}          # имена — только в GET /api/login


def test_body_not_parsed_without_session(anon):
    """Без входа тело запроса даже не читается: битый JSON — 401, а не 400; мегабайт — тоже 401."""
    bad = anon.put('/api/products/altea', content='{bad json', headers={**CSRF, 'Content-Type': 'application/json'})
    assert bad.status_code == 401 and bad.json() == {'error': 'Войдите, чтобы продолжить.'}
    big = anon.post('/api/products', content='x' * 900_000, headers={**CSRF, 'Content-Type': 'application/json'})
    assert big.status_code == 401
    assert anon.post('/api/uploads', files={'file': ('a.jpg', b'x', 'image/jpeg')}, headers=CSRF).status_code == 401
    assert anon.post('/api/logout', headers=CSRF).status_code == 200                # выйти можно и без сессии


def test_login_body_limited(anon):
    r = anon.post('/api/login', content='{"password": "' + 'x' * 5000 + '"}',
                  headers={**CSRF, 'Content-Type': 'application/json'})
    assert r.status_code == 413
    r = anon.post('/api/login', content='{нет', headers={**CSRF, 'Content-Type': 'application/json'})
    assert r.status_code == 400 and 'Обновите страницу' in r.json()['error']


def test_login_logout(anon):
    assert anon.get('/api/login').json() == {'users': ['Дамира', 'Жанна']}
    r = login(anon, 'Дамира', 'неправильный')
    assert r.status_code == 401 and r.json() == {'error': MSG_BAD_PASSWORD, 'field': 'password'}
    assert 'раскладку' in MSG_BAD_PASSWORD
    r = anon.post('/api/login', json={'password': PASSWORDS['Жанна']}, headers=CSRF)     # двое — нужно имя
    assert r.status_code == 400 and r.json()['field'] == 'name'
    r = anon.post('/api/login', json={'name': 'Дамира', 'password': ''}, headers=CSRF)
    assert r.status_code == 400 and r.json()['field'] == 'password'
    r = login(anon, 'Жанна')
    assert r.status_code == 200 and r.json() == {'user': 'Жанна'}
    cookie = r.headers['set-cookie'].lower()
    assert 'attre_session=' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie
    assert 'max-age=2592000' in cookie and 'secure' not in cookie            # localhost — без Secure
    assert anon.get('/api/session').json() == {'user': 'Жанна'}
    assert anon.post('/api/logout', headers=CSRF).json() == {}
    assert anon.get('/api/session').status_code == 401


def test_login_name_case_insensitive(anon):
    r = anon.post('/api/login', json={'name': ' дамира ', 'password': PASSWORDS['Дамира']}, headers=CSRF)
    assert r.json() == {'user': 'Дамира'}


def test_cookie_secure_on_real_domain(app):
    with TestClient(app, base_url='https://admin.attre.kz') as c:
        r = login(c)
        assert r.status_code == 200 and 'secure' in r.headers['set-cookie'].lower()
        assert c.get('/api/session').json() == {'user': 'Дамира'}
        assert c.get('/').headers['strict-transport-security'] == 'max-age=31536000'   # https — только https
    with TestClient(app, base_url='http://localhost') as c:
        assert 'strict-transport-security' not in c.get('/').headers


def test_session_lifetime_limited(app, cfg):
    """Сессия продлевается при заходе, но не дольше 90 дней от входа паролем — потом войти заново."""
    auth: Auth = app.state.auth
    old = auth.make_cookie('Дамира', started=time.time() - LIFETIME - 60)
    assert auth.read_cookie(old) is None
    late = auth.make_cookie('Дамира', started=time.time() - LIFETIME + 3600)
    user, _, started = auth.read_cookie(late)
    assert user == 'Дамира' and 3500 < auth.max_age(started) <= 3600              # продлится не дальше 90 дней
    with TestClient(app, base_url='http://localhost') as c:
        c.cookies.set('attre_session', old)
        assert c.get('/api/session').status_code == 401
        c.cookies.set('attre_session', late)
        assert c.get('/api/session').json() == {'user': 'Дамира'}


def test_single_password_mode(repo, tmp_path, static):
    cfg = make_config(repo, tmp_path, ADMIN_USERS='', ADMIN_PASSWORD='общий-пароль')
    with TestClient(create_app(cfg, static_dir=static, login_delay=0), base_url='http://localhost') as c:
        r = c.post('/api/login', json={'password': 'общий-пароль'}, headers=CSRF)
        assert r.json() == {'user': 'Админ'}


@pytest.fixture
def proxied(repo, tmp_path, static):
    """Админка «за прокси Railway»: адрес посетителя — из X-Real-IP / X-Forwarded-For."""
    cfg = make_config(repo, tmp_path, TRUST_PROXY='railway')
    with TestClient(create_app(cfg, static_dir=static, login_delay=0), base_url='http://localhost') as c:
        yield c


def login_from(c, ip, password='нет', **headers):
    return c.post('/api/login', json={'name': 'Дамира', 'password': password},
                  headers={**CSRF, 'X-Real-IP': ip, **headers})


def test_bruteforce_limited(proxied):
    for _ in range(10):
        assert login_from(proxied, '198.51.100.7').status_code == 401
    r = login_from(proxied, '198.51.100.7', PASSWORDS['Дамира'])               # даже верный пароль — подождать
    assert r.status_code == 429 and 'Слишком много попыток' in r.json()['error']
    assert 'минут' in r.json()['error'] and int(r.headers['retry-after']) > 0
    assert login_from(proxied, '203.0.113.7', PASSWORDS['Дамира']).status_code == 200   # другой адрес — пускаем


def test_bruteforce_ipv6_counted_per_network(proxied):
    """У одного подключения IPv6 — миллиарды адресов (/64): считаем их одним."""
    for i in range(10):
        assert login_from(proxied, f'2001:db8:1:2::{i + 1:x}').status_code == 401
    assert login_from(proxied, '2001:db8:1:2:ffff::1', PASSWORDS['Дамира']).status_code == 429
    assert login_from(proxied, '2001:db8:1:3::1', PASSWORDS['Дамира']).status_code == 200


def test_bruteforce_from_many_addresses_slowed_down(proxied):
    """Подбор с тысяч адресов: после 30 неудач за 15 минут со всех адресов — вход закрыт для всех на минуту."""
    for i in range(31):
        assert login_from(proxied, f'192.0.2.{i + 1}').status_code == 401
    r = login_from(proxied, '198.51.100.99', PASSWORDS['Дамира'])
    assert r.status_code == 429 and 0 < int(r.headers['retry-after']) <= 61


def test_forwarded_headers_ignored_without_proxy(anon):
    """Без TRUST_PROXY заголовки X-Real-IP / X-Forwarded-For подставит кто угодно — им не верим."""
    for i in range(10):
        assert login_from(anon, f'192.0.2.{i + 1}', **{'X-Forwarded-For': f'192.0.2.{i + 1}'}).status_code == 401
    assert login_from(anon, '203.0.113.50', PASSWORDS['Дамира']).status_code == 429


def test_failed_login_paused(repo, tmp_path, static):
    """После неверного пароля — пауза (без занятого потока: /api/health в это время отвечает сразу)."""
    cfg = make_config(repo, tmp_path)
    with TestClient(create_app(cfg, static_dir=static, login_delay=0.6), base_url='http://localhost') as c:
        out = {}
        t = threading.Thread(target=lambda: out.update(r=login(c, 'Дамира', 'нет')))
        t0 = time.monotonic()
        t.start()
        time.sleep(0.15)
        h0 = time.monotonic()
        assert c.get('/api/health').status_code == 200 and time.monotonic() - h0 < 0.4
        t.join()
        assert out['r'].status_code == 401 and time.monotonic() - t0 >= 0.6


def test_bad_cookie_and_password_change(app, repo, tmp_path, static):
    with TestClient(app, base_url='http://localhost') as c:
        login(c)
        cookie = c.cookies.get('attre_session')
    with TestClient(app, base_url='http://localhost') as c:
        c.cookies.set('attre_session', cookie[:-3] + ('abc' if not cookie.endswith('abc') else 'xyz'))
        assert c.get('/api/session').status_code == 401                         # подпись не сходится
        c.cookies.set('attre_session', cookie)
        assert c.get('/api/session').json() == {'user': 'Дамира'}
    changed = make_config(repo, tmp_path, ADMIN_USERS='Дамира:новый-пароль;Жанна:zhanna-pass-2')
    with TestClient(create_app(changed, static_dir=static), base_url='http://localhost') as c:
        c.cookies.set('attre_session', cookie)
        assert c.get('/api/session').status_code == 401                         # сменили пароль — сессия умерла


# ——— защита ———

@pytest.mark.parametrize('method, path', [('post', '/api/products'), ('put', '/api/products/altea'),
                                          ('delete', '/api/products/altea'), ('post', '/api/products/order'),
                                          ('put', '/api/settings'), ('post', '/api/login'), ('post', '/api/uploads'),
                                          ('post', '/api/password')])
def test_csrf_header_required(client, method, path):
    r = client.request(method.upper(), path, json={})
    assert r.status_code == 403 and 'Обновите страницу' in r.json()['error']
    assert r.headers['x-frame-options'] == 'DENY' and r.headers['cache-control'] == 'no-store'


def test_json_only(client):
    r = client.post('/api/products', content='product=x', headers={**CSRF, 'Content-Type': 'application/x-www-form-urlencoded'})
    assert r.status_code == 415
    r = client.post('/api/uploads', json={'file': 'x'}, headers=CSRF)
    assert r.status_code == 415 and r.json()['field'] == 'file'
    r = client.put('/api/settings', content='{bad json', headers={**CSRF, 'Content-Type': 'application/json'})
    assert r.status_code == 400 and r.json()['error']


def test_request_size_limited(client):
    r = client.post('/api/products', json={'product': {'desc': {'ru': 'x' * 1_200_000}}}, headers=CSRF)
    assert r.status_code == 413 and r.json() == {'error': 'Слишком большой запрос.'}
    r = up(client, b'\xff' * (31 * 1024 * 1024))
    assert r.status_code == 413 and '30 МБ' in r.json()['error']


def test_security_headers(client):
    r = client.get('/api/products')
    assert r.headers['x-content-type-options'] == 'nosniff' and r.headers['x-frame-options'] == 'DENY'
    assert r.headers['content-security-policy'] == CSP
    for part in ("default-src 'self'", "script-src 'self'", "connect-src 'self'", "form-action 'self'",
                 "frame-ancestors 'none'", "base-uri 'none'", "object-src 'none'"):
        assert part in CSP
    assert r.headers['cache-control'] == 'no-store' and 'noindex' in r.headers['x-robots-tag']
    assert client.get('/').headers['content-security-policy'] == CSP


@pytest.mark.parametrize('path', ['/api/media/..%2F..%2Fdata%2Fsettings.json', '/api/media/%2E%2E',
                                  '/api/media/settings.json', '/api/media/x.jpg', '/api/uploads/..%2Fx',
                                  '/api/products/..%2Fsettings', '/api/products/ALTEA'])
def test_paths_strict(client, path):
    assert client.get(path).status_code == 404


def test_no_secrets_in_responses(client, cfg):
    for path in ('/api/meta', '/api/session', '/api/status', '/api/settings'):
        text = client.get(path).text
        assert cfg.session_secret not in text and all(p not in text for p in PASSWORDS.values())
    assert cfg.session_secret not in repr(cfg) and PASSWORDS['Дамира'] not in repr(cfg)


# ——— каталог ———

def test_meta_and_list(client, repo):
    m = client.get('/api/meta').json()
    assert len(m['palette']) == 15 and m['users'] == ['Дамира', 'Жанна']
    assert {c['key'] for c in m['categories'] if c['leaf']} == {'bags', 'cardholder', 'charms'}
    items = client.get('/api/products').json()
    name = first_photo(repo, 'altea').rsplit('/', 1)[1]
    assert items[0]['slug'] == 'altea' and items[0]['thumb'].startswith(f'/api/media/{name}?w=480')
    p = client.get('/api/products/altea').json()
    assert p['product']['slug'] == 'altea' and len(p['sha']) == 40 and p['product']['variants'][0]['color'] == 'milky'
    assert client.get('/api/products/nope').status_code == 404


def test_product_flow(client, repo):
    r = up(client, jpeg_bytes((3000, 4000)))
    assert r.status_code == 200
    u = r.json()
    assert u['upload'].startswith('up_') and u['thumb'] == f'/api/uploads/{u["upload"]}'
    assert (u['width'], u['height']) == (1500, 2000)
    t = client.get(u['thumb'])
    assert t.status_code == 200 and t.headers['content-type'] == 'image/jpeg' and open_image(t.content).width == 480

    product = {'name': {'ru': 'Лукка'}, 'cat': 'bags', 'type': {'ru': 'тоут'}, 'price': 52000, 'published': True,
               'variants': [{'color': 'brown', 'material': 'suede', 'images': [f'upload:{u["upload"]}']}]}
    r = client.post('/api/products', json={'product': product}, headers=CSRF)
    assert r.status_code == 200, r.text
    slug = r.json()['slug']
    assert slug == 'lukka' and r.json()['commit'] == git(repo, 'rev-parse', 'HEAD')
    assert git(repo, 'log', '-1', '--format=%an|%s') == 'Дамира|Админка: новый товар «Лукка» (Дамира)'
    got = client.get(f'/api/products/{slug}').json()
    img = got['product']['variants'][0]['images'][0]
    assert img.startswith('media/products/lukka-brown-') and (repo / img).is_file()
    assert open_image((repo / img).read_bytes()).size == (1500, 2000)
    assert client.get('/api/products').json()[0]['slug'] == 'lukka'                    # новый — первым

    p = got['product']
    p['price'] = 55000
    r = client.put(f'/api/products/{slug}', json={'product': p, 'sha': got['sha']}, headers=CSRF)
    assert r.status_code == 200 and json.loads((repo / f'data/products/{slug}.json').read_text())['price'] == 55000
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: «Лукка» — сохранено (Дамира)'
    p['price'] = 1                                                                       # та же старая версия
    r = client.put(f'/api/products/{slug}', json={'product': p, 'sha': got['sha']}, headers=CSRF)
    assert r.status_code == 409 and 'Обновите страницу' in r.json()['error']

    bad = {**p, 'variants': [{'color': 'brown', 'images': []}]}
    fresh = client.get(f'/api/products/{slug}').json()
    r = client.put(f'/api/products/{slug}', json={'product': bad, 'sha': fresh['sha']}, headers=CSRF)
    assert r.status_code == 400 and r.json() == {'error': 'Цвет № 1: добавьте хотя бы одно фото.',
                                                 'field': 'variants.0.images'}

    r = client.delete(f'/api/products/{slug}?sha={got["sha"]}', headers=CSRF)
    assert r.status_code == 409
    r = client.delete(f'/api/products/{slug}?sha={fresh["sha"]}', headers=CSRF)
    assert r.status_code == 200 and not (repo / f'data/products/{slug}.json').exists() and not (repo / img).exists()
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: удалён «Лукка» (Дамира)'
    assert client.get(f'/api/products/{slug}').status_code == 404


def test_sale_price_api(client, repo):
    """Скидка: сохраняется числом сразу после цены, ошибки — у поля «Цена со скидкой», выключили — поля нет.
    Ссылка на товар — от корня сайта (/ru/p/<slug>/), без /v4/."""
    got = client.get('/api/products/bergen').json()
    p = {**got['product'], 'price': '45 000', 'sale_price': '36 000'}
    r = client.put('/api/products/bergen', json={'product': p, 'sha': got['sha']}, headers=CSRF)
    assert r.status_code == 200, r.text
    assert r.json()['url'] == 'https://example.test/attre-site/ru/p/bergen/'
    doc = json.loads((repo / 'data/products/bergen.json').read_text())
    assert (doc['price'], doc['sale_price']) == (45000, 36000)
    assert client.get('/api/products/bergen').json()['product']['sale_price'] == 36000
    item = next(x for x in client.get('/api/products').json() if x['slug'] == 'bergen')
    assert (item['price'], item['sale_price']) == (45000, 36000)

    fresh = client.get('/api/products/bergen').json()
    for sale, msg in ((50000, 'Цена со скидкой должна быть меньше обычной (45 000 ₸).'),
                      (-5, 'Цена со скидкой — целое число тенге больше нуля, без копеек и букв, например 36 000.')):
        r = client.put('/api/products/bergen', json={'product': {**fresh['product'], 'sale_price': sale},
                                                     'sha': fresh['sha']}, headers=CSRF)
        assert r.status_code == 400 and r.json() == {'error': msg, 'field': 'sale_price'}
    r = client.put('/api/products/bergen', json={'product': {**fresh['product'], 'price': None},
                                                 'sha': fresh['sha']}, headers=CSRF)
    assert r.status_code == 400 and r.json()['field'] == 'sale_price'
    assert r.json()['error'].startswith('Сначала укажите обычную цену')

    r = client.put('/api/products/bergen', json={'product': {**fresh['product'], 'sale_price': None},
                                                 'sha': fresh['sha']}, headers=CSRF)
    assert r.status_code == 200 and 'sale_price' not in json.loads((repo / 'data/products/bergen.json').read_text())
    assert next(x for x in client.get('/api/products').json() if x['slug'] == 'bergen')['sale_price'] is None


def test_site_links_without_v4(client):
    assert client.get('/api/meta').json()['site_url'] == 'https://example.test/attre-site/'
    assert client.get('/api/status').json()['site_url'] == 'https://example.test/attre-site/'
    got = client.get('/api/products/altea').json()
    r = client.put('/api/products/altea', json={'product': {**got['product'], 'price': 45000}, 'sha': got['sha']},
                   headers=CSRF)
    assert r.status_code == 200 and r.json()['url'] == 'https://example.test/attre-site/ru/p/altea/'


def test_reorder_api(client, repo):
    slugs = [x['slug'] for x in client.get('/api/products').json()]
    r = client.post('/api/products/order', json={'slugs': slugs[::-1]}, headers=CSRF)
    assert r.status_code == 200 and r.json()['commit'] == git(repo, 'rev-parse', 'HEAD')
    assert [x['slug'] for x in client.get('/api/products').json()] == slugs[::-1]
    assert client.post('/api/products/order', json={'slugs': ['nope']}, headers=CSRF).status_code == 409


# ——— фото ———

def test_upload_png_with_transparency(client, cfg):
    r = up(client, png_rgba_bytes(), 'logo.png', 'image/png')
    assert r.status_code == 200
    data = (cfg.tmp_dir / f'{r.json()["upload"]}.jpg').read_bytes()
    assert min(open_image(data).getpixel((5, 5))) > 245


def test_upload_heic(client):
    r = up(client, heic_bytes((800, 600)), 'IMG_0001.HEIC', 'image/heic')
    assert r.status_code == 200 and (r.json()['width'], r.json()['height']) == (800, 600)


@pytest.mark.parametrize('data, name, mime', [(b'%PDF-1.4 not a photo', 'scan.jpg', 'image/jpeg'),
                                              (b'', 'empty.jpg', 'image/jpeg'),
                                              (b'GIF89a' + b'\0' * 50, 'anim.gif', 'image/gif')])
def test_upload_bad_file(client, data, name, mime):
    r = up(client, data, name, mime)
    assert r.status_code == 400 and r.json()['field'] == 'file' and r.json()['error'][0].isupper()


def test_upload_without_file(client):
    r = client.post('/api/uploads', data={'x': '1'}, files={'other': ('a.txt', b'1')}, headers=CSRF)
    assert r.status_code == 400 and r.json() == {'error': 'Выберите фото.', 'field': 'file'}


def test_media_preview_cached(client, cfg, repo):
    name = first_photo(repo, 'altea').rsplit('/', 1)[1]
    r = client.get(f'/api/media/{name}?w=480')
    assert r.status_code == 200 and r.headers['content-type'] == 'image/jpeg'
    assert open_image(r.content).width <= 480 and 'max-age=300' in r.headers['cache-control']
    cached = list((cfg.tmp_dir / 'media').glob('*-480-f34.jpg'))
    assert len(cached) == 1
    etag = r.headers['etag']
    assert client.get(f'/api/media/{name}?w=480', headers={'If-None-Match': etag}).status_code == 304
    thumb = client.get('/api/products').json()[0]['thumb']                 # с ?v= — можно кэшировать навсегда
    assert 'immutable' in client.get(thumb).headers['cache-control']
    old_style = thumb.rsplit('-', 1)[0]                                     # ?v=<sha> без версии нарезки превью
    assert old_style != thumb and 'max-age=300' in client.get(old_style).headers['cache-control']
    assert client.get(f'/api/media/media/products/{name}').status_code == 200


# ——— настройки, статус, фронт ———

def test_settings_api(client, repo):
    s = client.get('/api/settings').json()
    assert s['contacts']['whatsapp'] == '77067232349' and s['sha']
    s['delivery']['free_from'] = 80000
    r = client.put('/api/settings', json=s, headers=CSRF)
    assert r.status_code == 200 and r.json()['sha'] != s['sha']
    assert json.loads((repo / 'data/settings.json').read_text())['delivery']['free_from'] == 80000
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: доставка и контакты (Дамира)'
    s['delivery']['free_from'] = 90000                                    # старый sha, тот же блок
    assert client.put('/api/settings', json=s, headers=CSRF).status_code == 409
    fresh = client.get('/api/settings').json()
    fresh['contacts']['whatsapp'] = '123'
    r = client.put('/api/settings', json=fresh, headers=CSRF)
    assert r.status_code == 400 and r.json()['field'] == 'contacts.whatsapp'


def test_status_local(client, repo):
    r = client.get('/api/status').json()
    assert r == {'head': git(repo, 'rev-parse', 'HEAD'), 'site_url': 'https://example.test/attre-site/',
                 'publish': {'state': 'unknown', 'commit': None, 'url': None, 'started': None, 'finished': None}}


def test_front(anon):
    for path in ('/', '/product/altea', '/products/new', '/settings'):
        r = anon.get(path)
        assert r.status_code == 200 and 'INDEX' in r.text and r.headers['content-type'].startswith('text/html')
        assert r.headers['cache-control'] == 'no-cache'
    for path in ('/static/app.js', '/app.js', '/static/js/api.js'):
        r = anon.get(path)
        assert r.status_code == 200 and 'javascript' in r.headers['content-type']
        again = anon.get(path, headers={'If-None-Match': r.headers['etag']})       # не изменился — 304
        assert again.status_code == 304 and again.headers['cache-control'] == 'no-cache'
    for path in ('/static/nope.js', '/nope.js', '/static/%2E%2E/%2E%2E/app/main.py', '/%2E%2E/app/config.py'):
        r = anon.get(path)
        assert r.status_code == 404 and 'INDEX' not in r.text                  # чужие файлы и HTML вместо JS — нет
    assert anon.get('/api/nope').status_code == 401                           # без входа — ничего не рассказываем
    login(anon)
    r = anon.get('/api/nope')
    assert r.status_code == 404 and r.json() == {'error': 'Нет такого адреса.'}


def test_front_placeholder_without_static(cfg, tmp_path):
    with TestClient(create_app(cfg, static_dir=tmp_path / 'none'), base_url='http://localhost') as c:
        r = c.get('/')
        assert r.status_code == 503 and 'ещё не установлен' in r.text


# ——— то же на GitHubStore (поддельный GitHub) ———

@pytest.fixture
def gh(repo, tmp_path, static):
    """Поддельный GitHub с теми же файлами, что в клоне repo (имена фото тесты берут из данных клона)."""
    files = {rel: (repo / rel).read_bytes() for rel in git(repo, 'ls-files', '-z').split('\0') if rel}
    fake = FakeGitHub(files)
    cfg = make_config(repo, tmp_path, STORE='github', GITHUB_TOKEN=TOKEN, GITHUB_REPO=fake.repo)
    store = GitHubStore(TOKEN, fake.repo, 'main', transport=fake.transport(), sleep=lambda s: None, status_ttl=0)
    with TestClient(create_app(cfg, store, static_dir=static, login_delay=0), base_url='http://localhost') as c:
        assert login(c, 'Жанна').status_code == 200
        yield c, fake


def test_github_product_flow(gh, repo):
    c, fake = gh
    siena = first_photo(repo, 'siena')
    assert c.get('/api/status').json()['publish']['state'] == 'unknown'
    u = up(c, jpeg_bytes((1000, 1300))).json()['upload']
    r = c.post('/api/products', json={'product': {
        'name': {'ru': 'Сиена мини'}, 'cat': 'cardholder',
        'variants': [{'color': 'zebra', 'images': [f'upload:{u}', siena]}]}}, headers=CSRF)
    assert r.status_code == 200, r.text
    slug, commit = r.json()['slug'], r.json()['commit']
    assert slug == 'siena-mini' and commit == fake.head()
    assert fake.commits[commit]['message'] == 'Админка: новый товар «Сиена мини» (Жанна)'
    files = fake.files()
    doc = json.loads(files[f'data/products/{slug}.json'])
    new_img = doc['variants'][0]['images'][0]
    assert new_img.startswith('media/products/siena-mini-zebra-') and files[new_img][:2] == b'\xff\xd8'
    st = c.get('/api/status').json()
    assert st['head'] == commit and st['publish']['state'] == 'queued'
    fake.runs = [{'head_sha': commit, 'status': 'completed', 'conclusion': 'success', 'html_url': 'https://gh/run/1',
                  'created_at': '2026-10-28T10:00:00Z', 'updated_at': '2026-10-28T10:02:30Z'}]
    assert c.get('/api/status').json()['publish']['state'] == 'done'

    got = c.get(f'/api/products/{slug}').json()
    p = got['product']
    p['variants'][0]['images'] = [siena]                                          # своё новое фото убрали
    r = c.put(f'/api/products/{slug}', json={'product': p, 'sha': got['sha']}, headers=CSRF)
    assert r.status_code == 200
    files = fake.files()
    assert new_img not in files and siena in files                                # чужое фото осталось

    fake.push_external(f'data/products/{slug}.json', files[f'data/products/{slug}.json'].replace(b'"cardholder"',
                                                                                                  b'"charms"'))
    r = c.put(f'/api/products/{slug}', json={'product': {**p, 'price': 100}, 'sha': got['sha']}, headers=CSRF)
    assert r.status_code == 409

    fresh = c.get(f'/api/products/{slug}').json()
    r = c.delete(f'/api/products/{slug}?sha={fresh["sha"]}', headers=CSRF)
    assert r.status_code == 200 and f'data/products/{slug}.json' not in fake.files()
    assert c.get(f'/api/media/{first_photo(repo, "altea").rsplit("/", 1)[1]}?w=240').status_code == 200
    assert not fake.bad_headers


def test_github_settings_and_errors(gh):
    import httpx
    c, fake = gh
    s = c.get('/api/settings').json()
    s['promo'] = {'ru': 'Новая полоса', 'kz': '', 'en': ''}
    assert c.put('/api/settings', json=s, headers=CSRF).status_code == 200
    t = json.loads(fake.files()['data/i18n.json'])['t']
    assert t['promo'] == {'ru': 'Новая полоса', 'kz': 'Новая полоса', 'en': 'Новая полоса'}
    s = c.get('/api/settings').json()
    fake.fail_next = [httpx.ConnectTimeout('x'), httpx.ConnectTimeout('x')]
    r = c.put('/api/settings', json={**s, 'promo': {'ru': 'Ещё'}}, headers=CSRF)
    assert r.status_code in (503, 504) and r.json() == {'error': 'GitHub не отвечает, попробуйте через минуту.'}


def test_github_lost_patch_response_is_not_an_error(gh, repo):
    """GitHub записал ветку, а ответ не дошёл (таймаут, обрыв, перезапуск при деплое): админка перечитывает ветку,
    видит свой коммит и отвечает «сохранено». Повторное «Сохранить» не создаёт второй такой же товар."""
    c, fake = gh
    u = up(c, jpeg_bytes((600, 800))).json()['upload']
    fake.lose_patch_response = 1
    before = set(fake.files())
    r = c.post('/api/products', json={'product': {'name': {'ru': 'Пробная сумка'}, 'cat': 'bags',
                                                  'variants': [{'color': 'black', 'images': [f'upload:{u}']}]}},
               headers=CSRF)
    assert r.status_code == 200, r.text
    assert r.json()['slug'] == 'probnaya-sumka' and r.json()['commit'] == fake.head()
    created = {p for p in set(fake.files()) - before if p.startswith('data/products/')}
    assert created == {'data/products/probnaya-sumka.json'}
    assert c.get('/api/status').json()['publish']['state'] == 'queued'          # и публикацию админка ждёт


def test_github_refused_write_is_reported_without_retries(gh):
    """422 на запись ветки, а ветка не ушла вперёд (защита ветки, правило репозитория) — не гонка: сразу понятная
    ошибка «сообщите Даулету», без трёх кругов повторов."""
    c, fake = gh
    s = c.get('/api/settings').json()
    fake.refuse_patch = 5
    r = c.put('/api/settings', json={**s, 'promo': {'ru': 'Новая полоса'}}, headers=CSRF)
    assert r.status_code == 502 and r.json() == {'error': 'GitHub не принял сохранение. Сообщите Даулету.'}
    assert fake.count('PATCH', '/git/refs/heads/main') == 1


def test_github_slow_does_not_block_health(repo, tmp_path, static):
    """GitHub отвечает медленно, а 45 запросов списка ждут голову ветки: /api/health отвечает сразу (async, без
    потоков), а к GitHub уходит один запрос головы на всех."""
    files = {rel: (repo / rel).read_bytes() for rel in git(repo, 'ls-files', '-z').split('\0') if rel}
    fake = FakeGitHub(files)
    cfg = make_config(repo, tmp_path, STORE='github', GITHUB_TOKEN=TOKEN, GITHUB_REPO=fake.repo)
    store = GitHubStore(TOKEN, fake.repo, 'main', transport=fake.transport(), sleep=lambda s: None, head_ttl=0.2)
    with TestClient(create_app(cfg, store, static_dir=static, login_delay=0), base_url='http://localhost') as c:
        assert login(c).status_code == 200
        assert c.get('/api/products').status_code == 200            # деревья и файлы — уже в кэше
        time.sleep(0.3)                                             # голова ветки устарела
        fake.ref_gate = threading.Event()
        before = fake.count('GET', '/git/ref/heads/main')
        results = []
        threads = [threading.Thread(target=lambda: results.append(c.get('/api/products').status_code))
                   for _ in range(45)]
        for t in threads:
            t.start()
        time.sleep(0.5)
        t0 = time.monotonic()
        assert c.get('/api/health').status_code == 200
        assert time.monotonic() - t0 < 1
        fake.ref_gate.set()
        for t in threads:
            t.join(20)
        assert results == [200] * 45
        assert fake.count('GET', '/git/ref/heads/main') - before == 1
