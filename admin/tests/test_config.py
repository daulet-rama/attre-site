"""Переменные окружения: понятные ошибки при старте, секреты не печатаются."""
from __future__ import annotations

import pytest

from app.config import ConfigError, load_config, parse_users

SECRET = 'test-session-secret-0123456789-abcdefgh'


def gh_env(**kw):
    return {'STORE': 'github', 'GITHUB_TOKEN': 'tok-123', 'GITHUB_REPO': 'daulet-rama/attre-site',
            'ADMIN_USERS': 'Дамира:pw-damira-77;Жанна:два:с:двоеточием', 'SESSION_SECRET': SECRET, **kw}


def test_github_ok_and_defaults():
    cfg = load_config(gh_env())
    assert cfg.store == 'github' and cfg.github_branch == 'main' and cfg.port == 8000
    assert cfg.users == {'Дамира': 'pw-damira-77', 'Жанна': 'два:с:двоеточием'}
    assert cfg.site_url == 'https://daulet-rama.github.io/attre-site/v4/'     # по умолчанию — из GITHUB_REPO
    assert 'tok-123' not in repr(cfg) and SECRET not in repr(cfg) and 'pw-damira-77' not in repr(cfg)


def test_site_url_slash_added():
    assert load_config(gh_env(SITE_URL='https://attre.kz/v4')).site_url == 'https://attre.kz/v4/'


def test_store_defaults_to_github():
    env = gh_env()
    env.pop('STORE')
    assert load_config(env).store == 'github'


def test_single_password():
    cfg = load_config(gh_env(ADMIN_USERS='', ADMIN_PASSWORD='общий-пароль-1'))
    assert cfg.users == {'Админ': 'общий-пароль-1'}


@pytest.mark.parametrize('env, words', [
    ({'ADMIN_USERS': 'Дамира:1234;Жанна:zhanna-pass-22'}, 'пароль для «Дамира» короче 12'),
    ({'ADMIN_USERS': 'Дамира:pw-damira-77;damirapassword:DamiraPassword'}, 'совпадает с именем'),
    ({'ADMIN_USERS': '', 'ADMIN_PASSWORD': 'attre2024'}, 'ADMIN_PASSWORD: пароль короче 12'),
])
def test_weak_passwords_refused_in_production(env, words):
    """За формой входа — токен с правом записи в репозиторий: в боевом режиме короткий пароль не запустится."""
    with pytest.raises(ConfigError) as ex:
        load_config(gh_env(**env))
    assert words in str(ex.value)
    assert '1234' not in str(ex.value) and 'attre2024' not in str(ex.value)   # сам пароль не печатаем


@pytest.mark.parametrize('env, words', [
    ({'SESSION_SECRET': 'x' * 48}, 'SESSION_SECRET похож на заглушку'),
    ({'SESSION_SECRET': 'secret' * 8}, 'SESSION_SECRET похож на заглушку'),
    ({'PASSWORD_PEPPER': 'p' * 40}, 'PASSWORD_PEPPER похож на заглушку'),
])
def test_placeholder_keys_refused_in_production(env, words):
    """По pepper_id в публичном .admin/users.json догадку о ключе можно проверить — заглушка вместо случайного
    ключа в боевом режиме не запустится (сам ключ не печатаем)."""
    with pytest.raises(ConfigError) as ex:
        load_config(gh_env(**env))
    assert words in str(ex.value) and next(iter(env.values())) not in str(ex.value)


def test_generated_keys_ok():
    """Сгенерированные ключи проходят: hex (16 возможных символов), uuid, token_urlsafe."""
    import secrets
    import uuid
    for key in (secrets.token_hex(16), secrets.token_hex(32), f'{uuid.uuid4()}', secrets.token_urlsafe(48)):
        assert load_config(gh_env(SESSION_SECRET=key, PASSWORD_PEPPER=key[::-1])).password_pepper == key[::-1]


def test_placeholder_keys_ok_locally(repo):
    cfg = load_config({'STORE': 'local', 'LOCAL_REPO': str(repo), 'ADMIN_USERS': 'Дамира:тест',
                       'SESSION_SECRET': 'x' * 40, 'PASSWORD_PEPPER': 'p' * 40})
    assert cfg.password_pepper == 'p' * 40


def test_short_password_ok_locally(repo):
    cfg = load_config({'STORE': 'local', 'LOCAL_REPO': str(repo), 'ADMIN_USERS': 'Дамира:тест', 'SESSION_SECRET': SECRET})
    assert cfg.users == {'Дамира': 'тест'}


def test_trust_proxy():
    assert load_config(gh_env()).trust_proxy is False
    assert load_config(gh_env(RAILWAY_ENVIRONMENT_NAME='production')).trust_proxy is True   # на Railway — сам
    assert load_config(gh_env(TRUST_PROXY='railway')).trust_proxy is True
    assert load_config(gh_env(TRUST_PROXY='0', RAILWAY_ENVIRONMENT_NAME='production')).trust_proxy is False
    with pytest.raises(ConfigError) as ex:
        load_config(gh_env(TRUST_PROXY='может быть'))
    assert 'TRUST_PROXY' in str(ex.value)


def test_local(repo):
    cfg = load_config({'STORE': 'local', 'LOCAL_REPO': str(repo), 'ADMIN_PASSWORD': 'x', 'SESSION_SECRET': SECRET})
    assert cfg.local_repo == repo.resolve() and cfg.github_token is None


@pytest.mark.parametrize('env, words', [
    ({'GITHUB_TOKEN': ''}, 'GITHUB_TOKEN'),
    ({'GITHUB_REPO': 'attre-site'}, 'GITHUB_REPO'),
    ({'SESSION_SECRET': 'short'}, 'SESSION_SECRET'),
    ({'ADMIN_USERS': '', 'ADMIN_PASSWORD': ''}, 'ADMIN_USERS'),
    ({'ADMIN_USERS': 'безпароля'}, 'ADMIN_USERS'),
    ({'ADMIN_USERS': 'Дамира:1;дамира:2'}, 'дважды'),
    ({'ADMIN_USERS': ';;'}, 'ADMIN_USERS'),
    ({'STORE': 'ftp'}, 'STORE'),
    ({'STORE': 'local', 'LOCAL_REPO': ''}, 'LOCAL_REPO'),
    ({'STORE': 'local', 'LOCAL_REPO': '/nonexistent/attre'}, 'LOCAL_REPO'),
    ({'SITE_URL': 'attre.kz'}, 'SITE_URL'),
    ({'PORT': 'abc'}, 'PORT'),
])
def test_errors_are_clear(env, words):
    with pytest.raises(ConfigError) as ex:
        load_config(gh_env(**env))
    text = str(ex.value)
    assert words in text and text.startswith('Админка не запущена')
    assert 'tok-123' not in text and SECRET not in text and 'pw-damira-77' not in text


def test_all_problems_at_once():
    with pytest.raises(ConfigError) as ex:
        load_config({'STORE': 'github'})
    text = str(ex.value)
    for name in ('GITHUB_TOKEN', 'GITHUB_REPO', 'SESSION_SECRET', 'ADMIN_USERS'):
        assert name in text


def test_parse_users_spaces():
    assert parse_users(' Дамира : пароль 1 ; Жанна:x ') == {'Дамира': 'пароль 1', 'Жанна': 'x'}
