"""Смена пароля в админке: хеш и проверка, файл .admin/users.json (чужой ключ, незнакомые имена, испорченный),
вход по записи файла и по переменной, POST /api/password (успех, cookie, ошибки, счётчик попыток, CSRF), запись
только этого файла, GitHubStore (поддельный GitHub), гонки, перечитывание раз в минуту, хранилище недоступно."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeTimedSerializer

from app.config import ConfigError
from app.main import MSG_BAD_PASSWORD, MSG_BAD_REQUEST, MSG_CHANGED, MSG_LOGIN, create_app
from app.passwords import (MSG_RACE, MSG_WRONG, PATH, Passwords, hash_password, make_record, new_password_problem,
                           pepper_for, pepper_id, verify)
from app.store import MSG_DOWN, GitHubStore, StoreError
from conftest import CSRF, PASSWORDS, git, make_config
from fake_github import TOKEN, FakeGitHub

NEW = 'новый-пароль-Дамиры'
NEW_Z = 'zhanna-new-pass'
CHANGED = {'error': MSG_CHANGED, 'reason': 'password'}     # 401: вход был, но пароль с тех пор сменили


# ——————————————————————————— помощники ———————————————————————————

def mk_app(cfg, tmp_path, store=None):
    return create_app(cfg, store, static_dir=tmp_path / 'no-static', login_delay=0)


def client(app) -> TestClient:
    """Ещё одно «устройство» для той же админки (без своего запуска/остановки приложения)."""
    return TestClient(app, base_url='http://localhost')


def login(c, name='Дамира', password=None, **headers):
    return c.post('/api/login', json={'name': name, 'password': password or PASSWORDS[name]},
                  headers={**CSRF, **headers})


def change(c, current, new, **headers):
    return c.post('/api/password', json={'current': current, 'new': new}, headers={**CSRF, **headers})


def users_doc(repo) -> dict:
    return json.loads((repo / PATH).read_text('utf-8'))


def put_file(repo, data: bytes | str, message='Даулет правит пароли'):
    """Файл паролей «руками» — как если бы Даулет правил его на GitHub."""
    f = repo / PATH
    f.parent.mkdir(exist_ok=True)
    f.write_bytes(data.encode('utf-8') if isinstance(data, str) else data)
    git(repo, 'add', PATH)
    git(repo, 'commit', '-q', '-m', message)


def doc_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def app_pepper(cfg) -> bytes:
    return pepper_for(cfg.session_secret, cfg.password_pepper)


def later(app, seconds: float):
    """Часы файла паролей — вперёд (перечитывание раз в минуту без ожидания)."""
    pw: Passwords = app.state.passwords
    shift = seconds + (pw.clock() - time.monotonic())
    pw.clock = lambda: time.monotonic() + shift


@pytest.fixture
def app(cfg, tmp_path):
    return mk_app(cfg, tmp_path)


@pytest.fixture
def dam(app):
    """Дамира вошла (её первое устройство); приложение запущено."""
    with client(app) as c:
        assert login(c).status_code == 200
        yield c


# ——————————————————————————— хеш, ключ, правила ———————————————————————————

def test_hash_and_verify():
    pepper = b'p' * 32
    rec = make_record('пароль-1', pepper)
    salt = base64.b64decode(rec['salt'], validate=True)
    assert len(salt) == 16 and len(rec['hash']) == 64 and int(rec['hash'], 16) >= 0
    assert datetime.fromisoformat(rec['changed']).tzinfo is not None
    # ровно формула из README: HMAC-SHA256(pepper, scrypt(пароль, salt, n=2**14, r=8, p=1, dklen=32))
    key = hashlib.scrypt('пароль-1'.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    assert rec['hash'] == hmac.new(pepper, key, hashlib.sha256).hexdigest() == hash_password('пароль-1', salt, pepper)
    assert verify('пароль-1', rec, pepper)
    assert not verify('пароль-2', rec, pepper) and not verify('Пароль-1', rec, pepper)
    assert not verify('пароль-1', rec, b'q' * 32)                       # другой ключ — не подходит
    assert make_record('пароль-1', pepper)['hash'] != rec['hash']       # соль каждый раз своя
    # «й» одной буквой и «и» + значок — один и тот же пароль
    assert hash_password('мой-пароль', salt, pepper) == hash_password('мой-пароль', salt, pepper)


@pytest.mark.parametrize('bad', [None, 'x', {}, {'salt': 'AAAA', 'hash': '0' * 64},            # соль не 16 байт
                                 {'salt': '!!!', 'hash': '0' * 64}, {'hash': '0' * 64},
                                 {'salt': base64.b64encode(b's' * 16).decode(), 'hash': 'xyz'},
                                 {'salt': base64.b64encode(b's' * 16).decode(), 'hash': '0' * 63}])
def test_verify_broken_record_is_false(bad):
    assert verify('что угодно', bad, b'p' * 32) is False


def test_verify_odd_input_does_not_crash():
    rec = make_record('пароль-1', b'p' * 32)
    assert verify(None, rec, b'p' * 32) is False and verify('\ud800', rec, b'p' * 32) is False


def test_pepper(repo, tmp_path):
    secret = 's' * 40
    assert pepper_for(secret) == hmac.new(secret.encode(), b'attre-admin password pepper v1', hashlib.sha256).digest()
    assert pepper_for(secret, 'P' * 32) == b'P' * 32
    pid = pepper_id(pepper_for(secret))
    assert len(pid) == 16 and int(pid, 16) >= 0 and pid != pepper_id(b'P' * 32)
    assert pid == hmac.new(pepper_for(secret), b'id', hashlib.sha256).hexdigest()[:16]
    with pytest.raises(ConfigError) as ex:
        make_config(repo, tmp_path, PASSWORD_PEPPER='короткий')
    assert 'PASSWORD_PEPPER' in str(ex.value) and 'короткий' not in str(ex.value)
    cfg = make_config(repo, tmp_path, PASSWORD_PEPPER='p' * 40)
    assert cfg.password_pepper == 'p' * 40 and 'p' * 40 not in repr(cfg)
    assert make_config(repo, tmp_path).password_pepper is None


@pytest.mark.parametrize('new, name, current, words', [
    ('', 'Дамира', '', 'Придумайте новый пароль.'),
    (None, 'Дамира', '', 'Придумайте новый пароль.'),
    (12345678, 'Дамира', '', 'Придумайте новый пароль.'),
    ('1234567', 'Дамира', '', 'слишком короткий — нужно не меньше 8 символов'),
    ('x' * 129, 'Дамира', '', 'слишком длинный — не больше 128 символов'),
    (' пароль-123', 'Дамира', '', 'Уберите пробелы в начале и в конце'),
    ('пароль-123 ', 'Дамира', '', 'Уберите пробелы в начале и в конце'),
    ('пароль-123 ', 'Дамира', '', 'Уберите пробелы в начале и в конце'),
    ('пароль\t123', 'Дамира', '', 'невидимые служебные символы'),
    ('пароль​123', 'Дамира', '', 'невидимые служебные символы'),
    ('пароль‮123', 'Дамира', '', 'невидимые служебные символы'),
    ('пароль\ud800123', 'Дамира', '', 'невидимые служебные символы'),
    ('пароль\n1234', 'Дамира', '', 'невидимые служебные символы'),
    ('АЛЕКСАНДРА', 'Александра', '', 'не должен совпадать с вашим именем'),
    ('пАРОЛЬ-123', 'Дамира', 'Пароль-123', 'совпадает с текущим'),
])
def test_new_password_rules(new, name, current, words):
    assert words in new_password_problem(new, name, current)


@pytest.mark.parametrize('new', ['12345678', 'x' * 128, 'пароль с пробелами внутри', 'Дамира-2026', 'zima-2026-kz'])
def test_new_password_ok(new):
    assert new_password_problem(new, 'Дамира', 'старый-пароль') is None


# ——————————————————————————— файл и вход ———————————————————————————

def test_file_with_foreign_pepper_ignored(repo, cfg, tmp_path, caplog):
    """Файл записан другим ключом (поменяли SESSION_SECRET или PASSWORD_PEPPER): не используется целиком,
    вход — по паролям из переменных, в журнале — предупреждение."""
    other = b'o' * 32
    put_file(repo, doc_bytes({'pepper_id': pepper_id(other), 'users': {'Дамира': make_record('из-чужого-файла', other)}}))
    caplog.set_level(logging.INFO, logger='attre')
    with client(mk_app(cfg, tmp_path)) as c:
        assert login(c, 'Дамира', 'из-чужого-файла').status_code == 401
        assert login(c).status_code == 200
    assert any(r.levelno == logging.WARNING and 'другим ключом' in r.getMessage() for r in caplog.records)


def test_login_by_file_record_and_by_variable(repo, cfg, tmp_path, caplog):
    """Запись в файле — пароль из переменной для этого человека больше не действует; у кого записи нет — по
    переменной. Записи для имён, которых нет в переменных, не действуют; имя в файле — без учёта регистра."""
    pepper = app_pepper(cfg)
    put_file(repo, doc_bytes({'pepper_id': pepper_id(pepper), 'users': {
        'Незнакомка': make_record('пароль-незнакомки', pepper),
        'дамира': make_record('пароль-из-файла', pepper),
    }}))
    caplog.set_level(logging.INFO, logger='attre')
    with client(mk_app(cfg, tmp_path)) as c:
        assert c.get('/api/login').json() == {'users': ['Дамира', 'Жанна']}
        assert login(c, 'Незнакомка', 'пароль-незнакомки').status_code == 401
        assert login(c, 'Дамира').status_code == 401                              # стартовый больше не подходит
        assert login(c, 'Дамира', 'пароль-из-файла').json() == {'user': 'Дамира'}
        assert login(c, 'Жанна').json() == {'user': 'Жанна'}                      # у Жанны записи нет
    assert any('Незнакомка' in r.getMessage() and 'не действуют' in r.getMessage() for r in caplog.records)


def test_broken_and_corrupt_files(repo, cfg, tmp_path, caplog):
    """Испорченная запись — для этого человека пароль из переменной (другие записи действуют); испорченный JSON —
    файл не используется целиком. В журнал — один раз, а не при каждом перечитывании."""
    pepper = app_pepper(cfg)
    put_file(repo, doc_bytes({'pepper_id': pepper_id(pepper), 'users': {
        'Дамира': {'salt': 'испорчено', 'hash': '0' * 64}, 'Жанна': make_record(NEW_Z, pepper)}}))
    caplog.set_level(logging.INFO, logger='attre')
    app = mk_app(cfg, tmp_path)
    with client(app) as c:
        assert login(c).status_code == 200 and login(c, 'Жанна', NEW_Z).status_code == 200
        assert login(c, 'Жанна').status_code == 401
        put_file(repo, '{"pepper_id": "не json')
        later(app, 61)
        assert login(c, 'Жанна').status_code == 200 and login(c, 'Жанна', NEW_Z).status_code == 401
        later(app, 61)
        assert login(c).status_code == 200
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert sum('испорчена запись «Дамира»' in m for m in warnings) == 1
    assert sum('испорчен JSON' in m for m in warnings) == 1


# ——————————————————————————— смена пароля через API ———————————————————————————

def test_change_password_flow(app, dam, repo, caplog):
    caplog.set_level(logging.DEBUG, logger='attre')
    other_device = client(app)
    assert login(other_device).status_code == 200
    zhanna = client(app)
    assert login(zhanna, 'Жанна').status_code == 200
    old_cookie = dam.cookies.get('attre_session')
    head = git(repo, 'rev-parse', 'HEAD')

    r = change(dam, PASSWORDS['Дамира'], NEW)
    assert r.status_code == 200 and r.json() == {}
    cookie = r.headers['set-cookie'].lower()
    assert 'attre_session=' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie
    assert dam.cookies.get('attre_session') != old_cookie
    assert dam.get('/api/session').json() == {'user': 'Дамира'}                 # новая cookie этого устройства
    r = other_device.get('/api/session')                                        # её прежние входы — недействительны,
    assert r.status_code == 401 and r.json() == CHANGED                         # и окно входа скажет почему
    stale = client(app)
    stale.cookies.set('attre_session', old_cookie)
    assert stale.get('/api/session').json() == CHANGED
    assert other_device.get('/api/products').json() == CHANGED
    assert zhanna.get('/api/session').json() == {'user': 'Жанна'}               # вход Жанны не тронут
    junk = client(app)                                                          # чужая или испорченная cookie —
    junk.cookies.set('attre_session', old_cookie[:-3] + 'abc')                  # просто «войдите»
    assert junk.get('/api/session').json() == {'error': MSG_LOGIN}

    fresh = client(app)
    assert login(fresh, 'Дамира', PASSWORDS['Дамира']).json() == {'error': MSG_BAD_PASSWORD, 'field': 'password'}
    assert login(fresh, 'Дамира', NEW).json() == {'user': 'Дамира'}
    assert login(fresh, 'Жанна').status_code == 200

    # один коммит, только файл паролей; формат — как у файлов сайта
    assert git(repo, 'rev-parse', 'HEAD~1') == head
    assert git(repo, 'log', '-1', '--format=%an|%s') == 'Дамира|Админка: смена пароля (Дамира)'
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD') == PATH
    raw = (repo / PATH).read_text('utf-8')
    doc = json.loads(raw)
    assert raw == json.dumps(doc, ensure_ascii=False, indent=2) + '\n' and '"Дамира"' in raw
    assert list(doc) == ['pepper_id', 'users'] and doc['pepper_id'] == app.state.passwords.pepper_id
    assert list(doc['users']) == ['Дамира'] and set(doc['users']['Дамира']) == {'salt', 'hash', 'changed'}
    # смена пароля сайт не меняет: полоса публикации её не ждёт
    assert app.state.store.last_commit is None
    assert dam.get('/api/status').json()['publish']['commit'] is None
    # пароли — ни в журнале, ни в ответах, ни в git
    text = '\n'.join(r.getMessage() for r in caplog.records)
    assert 'смена пароля: Дамира' in text
    assert all(p not in text for p in (NEW, *PASSWORDS.values()))
    assert NEW not in git(repo, 'log', '-p', '-1') and NEW not in r.text


def test_change_password_twice_and_back(app, dam):
    """Сменить ещё раз (текущий — уже из файла), в том числе обратно на стартовый."""
    assert change(dam, PASSWORDS['Дамира'], NEW).status_code == 200
    assert change(dam, PASSWORDS['Дамира'], 'ещё-один-пароль').json() == {'error': MSG_WRONG, 'field': 'current'}
    assert change(dam, NEW, PASSWORDS['Дамира']).status_code == 200
    c = client(app)
    assert login(c, 'Дамира', NEW).status_code == 401 and login(c).status_code == 200
    assert dam.get('/api/session').status_code == 200


def test_wrong_current_counted_and_blocked(repo, tmp_path):
    """Неверный текущий пароль — в общем счётчике с входом: после 10 ошибок с адреса — 429 и для смены,
    и для входа; другой адрес — можно."""
    cfg = make_config(repo, tmp_path, TRUST_PROXY='railway')
    app = mk_app(cfg, tmp_path)
    with client(app) as c:
        assert login(c, **{'X-Real-IP': '203.0.113.9'}).status_code == 200
        for i in range(10):
            r = change(c, f'неверный-{i}', NEW, **{'X-Real-IP': '198.51.100.7'})
            assert r.status_code == 400 and r.json() == {'error': 'Текущий пароль неверный.', 'field': 'current'}
        r = change(c, PASSWORDS['Дамира'], NEW, **{'X-Real-IP': '198.51.100.7'})
        assert r.status_code == 429 and int(r.headers['retry-after']) > 0
        assert r.json()['error'].startswith('Слишком много неверных паролей. Попробуйте через ') and 'минут' in r.text
        assert login(c, **{'X-Real-IP': '198.51.100.7'}).status_code == 429            # и вход с этого адреса
        assert change(c, PASSWORDS['Дамира'], NEW, **{'X-Real-IP': '203.0.113.9'}).status_code == 200


@pytest.mark.parametrize('payload, field, words', [
    ({'new': NEW}, 'current', 'Впишите текущий пароль.'),
    ({'current': '', 'new': NEW}, 'current', 'Впишите текущий пароль.'),
    ({'current': 123, 'new': NEW}, 'current', 'Впишите текущий пароль.'),
    ({'current': PASSWORDS['Дамира']}, 'new', 'Придумайте новый пароль.'),
    ({'current': PASSWORDS['Дамира'], 'new': ['x']}, 'new', 'Придумайте новый пароль.'),
    ({'current': PASSWORDS['Дамира'], 'new': '1234567'}, 'new', 'не меньше 8 символов'),
    ({'current': PASSWORDS['Дамира'], 'new': 'x' * 129}, 'new', 'не больше 128 символов'),
    ({'current': PASSWORDS['Дамира'], 'new': ' пробел-в-начале'}, 'new', 'Уберите пробелы'),
    ({'current': PASSWORDS['Дамира'], 'new': 'пароль​невидимый'}, 'new', 'невидимые служебные символы'),
    ({'current': PASSWORDS['Дамира'], 'new': PASSWORDS['Дамира'].upper()}, 'new', 'совпадает с текущим'),
])
def test_new_password_errors(dam, repo, payload, field, words):
    head = git(repo, 'rev-parse', 'HEAD')
    r = dam.post('/api/password', json=payload, headers=CSRF)
    assert r.status_code == 400 and r.json()['field'] == field and words in r.json()['error']
    assert git(repo, 'rev-parse', 'HEAD') == head and not (repo / PATH).exists()
    assert login(client(dam.app)).status_code == 200                                 # стартовый пароль на месте


def test_new_password_equal_to_name(repo, tmp_path):
    cfg = make_config(repo, tmp_path, ADMIN_USERS='Александра:пароль-александры;Жанна:zhanna-pass-2')
    with client(mk_app(cfg, tmp_path)) as c:
        assert login(c, 'Александра', 'пароль-александры').status_code == 200
        r = change(c, 'пароль-александры', 'АЛЕКСАНДРА')
        assert r.json() == {'error': 'Новый пароль не должен совпадать с вашим именем.', 'field': 'new'}


def test_new_password_errors_not_counted(dam):
    """Ошибки нового пароля — не попытки подбора: счётчик не растёт."""
    for _ in range(12):
        assert change(dam, PASSWORDS['Дамира'], 'коротко').status_code == 400
    assert change(dam, PASSWORDS['Дамира'], NEW).status_code == 200


def test_password_api_protected(app, dam):
    anon = client(app)
    r = anon.post('/api/password', json={'current': PASSWORDS['Дамира'], 'new': NEW}, headers=CSRF)
    assert r.status_code == 401 and r.json() == {'error': 'Войдите, чтобы продолжить.'}
    r = dam.post('/api/password', json={'current': PASSWORDS['Дамира'], 'new': NEW})          # без X-Requested-With
    assert r.status_code == 403 and 'Обновите страницу' in r.json()['error']
    r = dam.post('/api/password', content=f'current=x&new={NEW}',
                 headers={**CSRF, 'Content-Type': 'application/x-www-form-urlencoded'})
    assert r.status_code == 415
    r = dam.post('/api/password', content='{нет', headers={**CSRF, 'Content-Type': 'application/json'})
    assert r.status_code == 400 and r.json() == {'error': MSG_BAD_REQUEST}
    r = dam.post('/api/password', json=['x'], headers=CSRF)
    assert r.status_code == 400 and r.json() == {'error': MSG_BAD_REQUEST}
    r = dam.post('/api/password', json={'current': 'x' * 5000, 'new': NEW}, headers=CSRF)
    assert r.status_code == 413                                                   # как у входа — до 4 КБ
    assert login(client(app)).status_code == 200                                  # ничего не поменялось


def test_single_password_mode(repo, tmp_path):
    cfg = make_config(repo, tmp_path, ADMIN_USERS='', ADMIN_PASSWORD='общий-пароль')
    with client(mk_app(cfg, tmp_path)) as c:
        assert c.post('/api/login', json={'password': 'общий-пароль'}, headers=CSRF).json() == {'user': 'Админ'}
        assert change(c, 'общий-пароль', 'новый-общий-пароль').status_code == 200
        assert list(users_doc(repo)['users']) == ['Админ']
        assert c.post('/api/login', json={'password': 'общий-пароль'}, headers=CSRF).status_code == 401
        assert c.post('/api/login', json={'password': 'новый-общий-пароль'}, headers=CSRF).status_code == 200


def test_change_keeps_others_and_unknown_fields(app, dam, repo):
    """Чужие записи (и записи незнакомых имён), прочие поля файла — как были; то же имя другими буквами —
    заменяется записью с именем как в переменных."""
    pepper = app.state.passwords.pepper
    zhanna = make_record(NEW_Z, pepper)
    put_file(repo, doc_bytes({'note': 'служебное', 'pepper_id': pepper_id(pepper), 'users': {
        'Жанна': zhanna, 'дамира': make_record('старый-из-файла', pepper), 'Бывшая': {'salt': 'x', 'hash': 'y'}}}))
    later(app, 61)
    c = client(app)
    assert login(c, 'Дамира', 'старый-из-файла').status_code == 200
    assert dam.get('/api/session').status_code == 401              # вход по стартовому паролю уже не действует
    assert change(c, PASSWORDS['Дамира'], NEW).json()['field'] == 'current'        # стартовый уже не текущий
    assert change(c, 'старый-из-файла', NEW).status_code == 200
    doc = users_doc(repo)
    assert list(doc) == ['note', 'pepper_id', 'users'] and doc['note'] == 'служебное'
    assert list(doc['users']) == ['Жанна', 'Бывшая', 'Дамира'] and doc['users']['Жанна'] == zhanna
    assert doc['users']['Бывшая'] == {'salt': 'x', 'hash': 'y'}


# ——————————————————————————— перечитывание, сброс, недоступное хранилище ———————————————————————————

def test_reset_by_deleting_record_picked_up_within_a_minute(app, dam, repo):
    """Даулет удаляет запись на GitHub (сброс забытого пароля): через минуту снова действует пароль из
    переменной, а входы, выданные по сменённому паролю, — нет. Раньше минуты файл не перечитывается."""
    assert change(dam, PASSWORDS['Дамира'], NEW).status_code == 200
    doc = users_doc(repo)
    del doc['users']['Дамира']
    put_file(repo, doc_bytes(doc), 'Сброс пароля Дамиры')
    c = client(app)
    assert login(c, 'Дамира', NEW).status_code == 200                            # ещё не перечитан
    assert dam.get('/api/session').status_code == 200
    later(app, 61)
    assert dam.get('/api/session').status_code == 401                            # запрос с cookie перечитал файл
    assert login(c, 'Дамира', NEW).status_code == 401
    assert login(c).status_code == 200


def test_store_down_uses_last_read_version(app, dam, monkeypatch, caplog):
    store = app.state.store
    real = store.snapshot
    down = {'on': False}

    def snapshot(fresh=False):
        if down['on']:
            raise StoreError(MSG_DOWN, 503)
        return real(fresh=fresh)

    monkeypatch.setattr(store, 'snapshot', snapshot)
    assert change(dam, PASSWORDS['Дамира'], NEW).status_code == 200
    caplog.set_level(logging.WARNING, logger='attre')
    down['on'] = True
    later(app, 61)
    c = client(app)
    assert login(c, 'Дамира', NEW).status_code == 200                            # по последней прочитанной версии
    assert login(c).status_code == 401
    assert dam.get('/api/session').status_code == 200
    assert any('не прочитан' in r.getMessage() for r in caplog.records)
    r = change(dam, NEW, 'ещё-новее-пароль')                                     # записать без GitHub нельзя
    assert r.status_code == 503 and r.json() == {'error': MSG_DOWN}


def test_store_down_from_start_no_login_by_old_passwords(cfg, tmp_path, monkeypatch):
    """Файл ещё ни разу не прочитан (GitHub не ответил после запуска): по паролям из переменных не пускаем —
    их могли сменить как раз потому, что они кому-то известны. GitHub ожил — вход как обычно."""
    app = mk_app(cfg, tmp_path)
    store = app.state.store
    real = store.snapshot
    down = {'on': True}

    def snapshot(fresh=False):
        if down['on']:
            raise StoreError(MSG_DOWN, 503)
        return real(fresh=fresh)

    monkeypatch.setattr(store, 'snapshot', snapshot)
    with client(app) as c:
        r = login(c)
        assert r.status_code == 503 and r.json() == {'error': MSG_DOWN}
        down['on'] = False
        assert login(c).status_code == 503                                       # повтор — не чаще раза в 10 с
        later(app, 11)
        assert login(c).status_code == 200


def test_store_down_from_start_no_entry_by_cookies(cfg, tmp_path, monkeypatch):
    """То же для входов по cookie: пока файл после запуска не прочитан, сверить отпечаток не с чем — 503, а не
    вход. Иначе прошла бы cookie, выданная по стартовому паролю до его смены (потерянный телефон, из-за которого
    пароль и меняли). GitHub ожил — такая cookie не действует, а выданная после смены — действует."""
    first = mk_app(cfg, tmp_path)
    with client(first) as phone:
        laptop = client(first)
        assert login(phone).status_code == 200 and login(laptop).status_code == 200
        lost = phone.cookies.get('attre_session')                                # выдана по стартовому паролю
        assert change(laptop, PASSWORDS['Дамира'], NEW).status_code == 200
        fresh_cookie = laptop.cookies.get('attre_session')

    app = mk_app(cfg, tmp_path)                                                  # перезапуск, GitHub лежит
    store = app.state.store
    real = store.snapshot
    down = {'on': True}

    def snapshot(fresh=False):
        if down['on']:
            raise StoreError(MSG_DOWN, 503)
        return real(fresh=fresh)

    monkeypatch.setattr(store, 'snapshot', snapshot)
    with client(app) as thief:
        owner = client(app)
        thief.cookies.set('attre_session', lost)
        owner.cookies.set('attre_session', fresh_cookie)
        for c in (thief, owner):
            r = c.get('/api/session')
            assert r.status_code == 503 and r.json() == {'error': MSG_DOWN}
        r = thief.post('/api/uploads', files={'file': ('a.jpg', b'not a photo', 'image/jpeg')}, headers=CSRF)
        assert r.status_code == 503
        assert client(app).get('/api/session').json() == {'error': MSG_LOGIN}    # без cookie — просто «войдите»
        down['on'] = False
        later(app, 11)
        assert thief.get('/api/session').json() == CHANGED
        assert owner.get('/api/session').json() == {'user': 'Дамира'}


def test_file_read_at_startup(repo, cfg, tmp_path, monkeypatch):
    """Боевой запуск (prewarm): файл паролей читается сразу после старта, а не при первом запросе."""
    pepper = app_pepper(cfg)
    put_file(repo, doc_bytes({'pepper_id': pepper_id(pepper), 'users': {'Жанна': make_record(NEW_Z, pepper)}}))
    app = create_app(cfg, static_dir=tmp_path / 'no-static', prewarm=True, login_delay=0)
    monkeypatch.setattr(app.state.catalog, 'products', lambda: [])              # превью здесь не нужны
    pw: Passwords = app.state.passwords
    with client(app):
        deadline = time.monotonic() + 10
        while not pw.loaded and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pw.loaded and pw.record('Жанна') is not None and pw.record('Дамира') is None


def test_session_secret_change_resets_file(repo, cfg, tmp_path, caplog):
    """Новый SESSION_SECRET (без PASSWORD_PEPPER) — файл другим ключом: все снова по паролям из переменных.
    С PASSWORD_PEPPER смена SESSION_SECRET пароли не сбрасывает (только выкидывает всех из админки)."""
    with client(mk_app(cfg, tmp_path)) as c:
        assert login(c).status_code == 200 and change(c, PASSWORDS['Дамира'], NEW).status_code == 200
    caplog.set_level(logging.WARNING, logger='attre')
    other = make_config(repo, tmp_path, SESSION_SECRET='другой-ключ-' + 'y' * 40)
    with client(mk_app(other, tmp_path)) as c:
        assert login(c, 'Дамира', NEW).status_code == 401 and login(c).status_code == 200
    assert any('другим ключом' in r.getMessage() for r in caplog.records)

    peppered = make_config(repo, tmp_path, PASSWORD_PEPPER='p' * 40)
    with client(mk_app(peppered, tmp_path)) as c:
        assert login(c).status_code == 200 and change(c, PASSWORDS['Дамира'], 'пароль-с-перцем').status_code == 200
    moved = make_config(repo, tmp_path, PASSWORD_PEPPER='p' * 40, SESSION_SECRET='третий-ключ-' + 'z' * 40)
    with client(mk_app(moved, tmp_path)) as c:
        assert login(c).status_code == 401 and login(c, 'Дамира', 'пароль-с-перцем').status_code == 200


def _forge(secret: str, user: str, key: bytes, material: str) -> str:
    """Cookie, собранная «снаружи»: подпись SESSION_SECRET и отпечаток по формуле с ключом key."""
    fp = hmac.new(key, material.encode('utf-8'), hashlib.sha256).hexdigest()[:20]
    return URLSafeTimedSerializer(secret, salt='attre-admin-session').dumps({'u': user, 'k': fp, 's': int(time.time())})


@pytest.mark.parametrize('pepper_env', [None, 'перец-' + 'q' * 40])
def test_cookie_not_forged_from_session_secret_and_public_file(repo, tmp_path, pepper_env):
    """Сменённый пароль: hash — в публичном репозитории, а pepper_id позволяет проверять догадки о SESSION_SECRET.
    Поэтому в отпечатке cookie ещё и стартовый пароль (и PASSWORD_PEPPER, если задан): зная только SESSION_SECRET
    и файл, вход не подделать — как и до смены пароля."""
    extra = {'PASSWORD_PEPPER': pepper_env} if pepper_env else {}
    cfg = make_config(repo, tmp_path, **extra)
    secret, start = cfg.session_secret, PASSWORDS['Дамира']
    app = mk_app(cfg, tmp_path)
    with client(app) as c:
        assert login(c).status_code == 200 and change(c, start, NEW).status_code == 200
        h = users_doc(repo)['users']['Дамира']['hash']
        guessed = secret.encode() + b'\0' + pepper_for(secret)          # всё, что выводится из SESSION_SECRET
        attempts = {
            'SESSION_SECRET + hash': _forge(secret, 'Дамира', secret.encode(), f'Дамира\0файл\0{h}'),
            'SESSION_SECRET + hash + ключ из SESSION_SECRET': _forge(secret, 'Дамира', guessed, f'Дамира\0файл\0{h}'),
        }
        if pepper_env:                       # стартовый пароль угадан, а PASSWORD_PEPPER — нет
            attempts['+ стартовый пароль, без PASSWORD_PEPPER'] = _forge(secret, 'Дамира', guessed,
                                                                       f'Дамира\0файл\0{h}\0{start}')
        for what, cookie in attempts.items():
            atk = client(app)
            atk.cookies.set('attre_session', cookie)
            assert atk.get('/api/session').status_code == 401, what
        # проверка самой подделки: со всеми секретами она проходит — значит, отказы выше именно из-за них
        key = secret.encode() + b'\0' + pepper_for(secret, pepper_env)
        ok = client(app)
        ok.cookies.set('attre_session', _forge(secret, 'Дамира', key, f'Дамира\0файл\0{h}\0{start}'))
        assert ok.get('/api/session').json() == {'user': 'Дамира'}


def test_start_password_change_logs_out_but_own_password_stays(repo, cfg, tmp_path):
    """Стартовый пароль в ADMIN_USERS поменяли, а у человека свой (сменённый) пароль: её входы перестают
    действовать (стартовый — часть отпечатка), но входит она по-прежнему своим паролем; новый стартовый не подходит."""
    with client(mk_app(cfg, tmp_path)) as c:
        assert login(c).status_code == 200 and change(c, PASSWORDS['Дамира'], NEW).status_code == 200
        cookie = c.cookies.get('attre_session')
    moved = make_config(repo, tmp_path, ADMIN_USERS=f'Дамира:другой-стартовый-1;Жанна:{PASSWORDS["Жанна"]}')
    with client(mk_app(moved, tmp_path)) as c:
        c.cookies.set('attre_session', cookie)
        assert c.get('/api/session').json() == CHANGED
        assert login(c, 'Дамира', 'другой-стартовый-1').status_code == 401
        assert login(c, 'Дамира', NEW).json() == {'user': 'Дамира'}


# ——————————————————————————— гонки ———————————————————————————

def _together(app, monkeypatch, *calls):
    """Запросы одновременно: каждый проходит вход и проверки и ждёт остальных перед сменой пароля."""
    auth = app.state.auth
    real = auth.change_password
    barrier = threading.Barrier(len(calls), timeout=10)

    def change_password(*a, **kw):
        barrier.wait()
        return real(*a, **kw)

    monkeypatch.setattr(auth, 'change_password', change_password)
    out = [None] * len(calls)
    threads = [threading.Thread(target=lambda i=i, f=f: out.__setitem__(i, f())) for i, f in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return out


def test_two_people_change_at_once(app, dam, repo, monkeypatch):
    """Дамира и Жанна меняют пароль в одну секунду: записи идут по очереди, файл со свежей версии — обе на месте."""
    zh = client(app)
    assert login(zh, 'Жанна').status_code == 200
    r1, r2 = _together(app, monkeypatch, lambda: change(dam, PASSWORDS['Дамира'], NEW),
                       lambda: change(zh, PASSWORDS['Жанна'], NEW_Z))
    assert r1.status_code == 200 and r2.status_code == 200
    assert set(users_doc(repo)['users']) == {'Дамира', 'Жанна'}
    assert git(repo, 'log', '-2', '--format=%s').count('смена пароля') == 2
    c = client(app)
    assert login(c, 'Дамира', NEW).status_code == 200 and login(c, 'Жанна', NEW_Z).status_code == 200
    assert dam.get('/api/session').status_code == 200 and zh.get('/api/session').status_code == 200


def test_same_person_two_devices_at_once(app, dam, repo, monkeypatch):
    """Одна и та же — с двух устройств одновременно: смены идут по очереди, первая не перезаписывается молча.
    Второе устройство видит, что его вход уже не действует (пароль только что сменили на первом), — 401 «пароль
    сменили» и окно входа, а не «Текущий пароль неверный» (он был введён верно), и попытка не идёт в счётчик."""
    second = client(app)
    assert login(second).status_code == 200
    r1, r2 = _together(app, monkeypatch, lambda: change(dam, PASSWORDS['Дамира'], NEW),
                       lambda: change(second, PASSWORDS['Дамира'], 'другой-новый-пароль'))
    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 401]
    loser = r1 if r1.status_code == 401 else r2
    assert loser.json() == CHANGED
    assert not app.state.auth.limiter._fails                                     # не попытка подбора
    winner_pw = NEW if r1.status_code == 200 else 'другой-новый-пароль'
    loser_pw = 'другой-новый-пароль' if winner_pw == NEW else NEW
    c = client(app)
    assert login(c, 'Дамира', winner_pw).status_code == 200 and login(c, 'Дамира', loser_pw).status_code == 401
    assert git(repo, 'log', '-1', '--format=%s') == 'Админка: смена пароля (Дамира)'
    assert git(repo, 'log', '-2', '--format=%s').count('смена пароля') == 1


def test_change_after_reset_not_yet_reread(app, dam, repo):
    """Даулет сбросил пароль (удалил запись на GitHub), а админка ещё не перечитала файл: смена со старым входом —
    401 «пароль сменили» (окно входа), а не «Текущий пароль неверный» и не попытка в счётчике."""
    assert change(dam, PASSWORDS['Дамира'], NEW).status_code == 200
    doc = users_doc(repo)
    del doc['users']['Дамира']
    put_file(repo, doc_bytes(doc), 'Сброс пароля Дамиры')
    assert dam.get('/api/session').status_code == 200                           # ещё не перечитан
    assert change(dam, NEW, 'ещё-один-пароль').json() == CHANGED
    assert not app.state.auth.limiter._fails
    assert dam.get('/api/session').json() == CHANGED                            # свежая версия уже в памяти
    assert login(client(app)).status_code == 200                                # снова стартовый


def test_login_and_change_at_once_do_not_exceed_counter(app, dam, monkeypatch):
    """9 неудач с адреса, и тут же одновременно неверный вход и неверный текущий пароль с него же: проверяется
    только одна попытка (10-я), вторая получает 429 — вход и смена ждут друг друга на одной блокировке попыток."""
    auth = app.state.auth
    for _ in range(9):
        auth.limiter.fail('testclient')
    real_ok, real_fresh = auth._ok, app.state.passwords.fresh
    barrier = threading.Barrier(2, timeout=1.5)     # без общей блокировки обе проверки встретились бы здесь

    def meet():
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass                                    # вторая ждёт блокировку попыток — так и задумано

    def slow_ok(*a, **kw):
        meet()
        return real_ok(*a, **kw)

    def slow_fresh(*a, **kw):
        state = real_fresh(*a, **kw)
        meet()
        return state

    monkeypatch.setattr(auth, '_ok', slow_ok)
    monkeypatch.setattr(app.state.passwords, 'fresh', slow_fresh)
    out = {}
    threads = [threading.Thread(target=lambda: out.__setitem__('login', login(client(app), 'Дамира', 'нет').status_code)),
               threading.Thread(target=lambda: out.__setitem__('change', change(dam, 'нет', NEW).status_code))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sorted(out.values()) in ([400, 429], [401, 429]), out
    assert len(auth.limiter._fails['testclient']) == 10


def test_external_write_between_read_and_commit(app, dam, repo, monkeypatch):
    """Файл изменили в другом месте между чтением и записью (Даулет на GitHub, вторая копия админки при деплое):
    409 и ничего не записано; повтор — поверх свежей версии, чужая правка не теряется."""
    store = app.state.store
    real = store.commit
    pepper = app.state.passwords.pepper
    zhanna = make_record(NEW_Z, pepper)
    hits = []

    def commit(changes, message, author, expect=None, **kw):
        if PATH in changes and not hits:
            hits.append(1)
            put_file(repo, doc_bytes({'pepper_id': pepper_id(pepper), 'users': {'Жанна': zhanna}}))
        return real(changes, message, author, expect, **kw)

    monkeypatch.setattr(store, 'commit', commit)
    r = change(dam, PASSWORDS['Дамира'], NEW)
    assert r.status_code == 409 and r.json() == {'error': MSG_RACE}
    assert list(users_doc(repo)['users']) == ['Жанна']                            # наша запись не легла поверх
    assert dam.get('/api/session').status_code == 200                            # вход не сломан
    assert change(dam, PASSWORDS['Дамира'], NEW).status_code == 200
    assert users_doc(repo)['users']['Жанна'] == zhanna and 'Дамира' in users_doc(repo)['users']


def test_concurrent_wrong_logins_do_not_bypass_counter(app):
    """Двадцать неверных попыток входа одновременно с одного адреса: проверено ровно 10, остальным — 429."""
    c = client(app)
    out = []
    threads = [threading.Thread(target=lambda: out.append(login(c, 'Дамира', 'нет').status_code)) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sorted(out) == [401] * 10 + [429] * 10


# ——————————————————————————— GitHubStore (поддельный GitHub) ———————————————————————————

@pytest.fixture
def gh(repo, tmp_path):
    files = {rel: (repo / rel).read_bytes() for rel in git(repo, 'ls-files', '-z').split('\0') if rel}
    fake = FakeGitHub(files)
    cfg = make_config(repo, tmp_path, STORE='github', GITHUB_TOKEN=TOKEN, GITHUB_REPO=fake.repo)
    # head_ttl=0: голову ветки не кэшируем (в жизни её кэш — 15 с, меньше минуты перечитывания паролей)
    store = GitHubStore(TOKEN, fake.repo, 'main', transport=fake.transport(), sleep=lambda s: None, status_ttl=0,
                        head_ttl=0)
    app = mk_app(cfg, tmp_path, store)
    with client(app) as c:
        assert login(c, 'Жанна').status_code == 200
        yield app, c, fake


def test_github_commits_users_file(gh):
    app, c, fake = gh
    head = fake.head()
    fake.race_on_patch = 1                         # в ту же секунду кто-то записал другой файл — повтор поверх него
    r = change(c, PASSWORDS['Жанна'], NEW_Z)
    assert r.status_code == 200 and r.json() == {}
    commit = fake.commits[fake.head()]
    assert commit['message'] == 'Админка: смена пароля (Жанна)' and commit['author'] == 'Жанна'
    assert fake.commits[commit['parents'][0]]['parents'] == [head]               # поверх чужого коммита
    files = fake.files()
    assert 'data/race.json' in files
    doc = json.loads(files[PATH])
    assert files[PATH] == doc_bytes(doc) and list(doc['users']) == ['Жанна']
    assert doc['pepper_id'] == app.state.passwords.pepper_id
    trees = [b for m, p, b in fake.requests if m == 'POST' and p.endswith('/git/trees')]
    assert {e['path'] for e in trees[-1]['tree']} == {PATH}                      # пишется только файл паролей
    assert c.get('/api/session').json() == {'user': 'Жанна'}
    st = c.get('/api/status').json()
    assert st['publish']['commit'] is None and st['publish']['state'] == 'unknown'   # сайт не публикуется
    other = client(app)
    assert login(other, 'Жанна').status_code == 401 and login(other, 'Жанна', NEW_Z).status_code == 200
    assert not fake.bad_headers


def test_github_reset_on_github_picked_up(gh):
    """Даулет удаляет запись Жанны прямо на GitHub — админка через минуту снова пускает по стартовому паролю."""
    app, c, fake = gh
    assert change(c, PASSWORDS['Жанна'], NEW_Z).status_code == 200
    doc = json.loads(fake.files()[PATH])
    del doc['users']['Жанна']
    fake.push_external(PATH, doc_bytes(doc), 'Сброс пароля Жанны')
    other = client(app)
    assert login(other, 'Жанна', NEW_Z).status_code == 200                       # раньше минуты — прежний
    later(app, 61)
    assert login(other, 'Жанна', NEW_Z).status_code == 401
    assert login(other, 'Жанна').status_code == 200


def test_github_reset_within_a_minute_despite_head_cache(repo, tmp_path):
    """Голова ветки в GitHubStore кэшируется на 15 с; перечитывая файл паролей раз в минуту, админка спрашивает её
    у GitHub заново — сброс подхватывается через минуту, а не через минуту и ещё до 15 с."""
    files = {rel: (repo / rel).read_bytes() for rel in git(repo, 'ls-files', '-z').split('\0') if rel}
    fake = FakeGitHub(files)
    cfg = make_config(repo, tmp_path, STORE='github', GITHUB_TOKEN=TOKEN, GITHUB_REPO=fake.repo)
    store = GitHubStore(TOKEN, fake.repo, 'main', transport=fake.transport(), sleep=lambda s: None, status_ttl=0)
    assert store._head_ttl == 15.0                                               # кэш головы — как в жизни
    app = mk_app(cfg, tmp_path, store)
    with client(app) as c:
        assert login(c, 'Жанна').status_code == 200 and change(c, PASSWORDS['Жанна'], NEW_Z).status_code == 200
        assert c.get('/api/products').status_code == 200                         # голова ветки — в кэше
        doc = json.loads(fake.files()[PATH])
        del doc['users']['Жанна']
        fake.push_external(PATH, doc_bytes(doc), 'Сброс пароля Жанны')
        later(app, 61)                                                           # кэш головы ещё свежий (< 15 с)
        assert login(c, 'Жанна', NEW_Z).status_code == 401
        assert login(c, 'Жанна').status_code == 200
