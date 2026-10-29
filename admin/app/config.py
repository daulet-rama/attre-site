"""Настройки админки из переменных окружения (DESIGN.md → «Переменные окружения»).

Секреты (пароли, токен, ключ подписи cookie) не попадают ни в repr, ни в сообщения об ошибках.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


class ConfigError(Exception):
    """Не хватает переменной окружения или она задана неверно. Текст — по-русски, для журнала при старте."""


MIN_PASSWORD = 12      # в боевом режиме (STORE=github): за формой входа — токен с правом записи в репозиторий сайта
# Разных символов в ключе (SESSION_SECRET, PASSWORD_PEPPER) в боевом режиме — не меньше: отсекает заглушки вроде
# «xxxx…» или «secretsecret…». В сгенерированном ключе из 32+ символов их практически всегда больше — даже в hex
# (16 возможных) их в среднем 14, а меньше 8 — реже раза на миллион. Придуманную фразу так не распознать — поэтому
# в README ключи только генерируются: по pepper_id в публичном .admin/users.json догадку о ключе можно проверить.
MIN_DISTINCT = 8


@dataclass(frozen=True)
class Config:
    store: str                                         # 'github' | 'local'
    users: dict[str, str] = field(repr=False)          # имя → пароль
    session_secret: str = field(repr=False)
    site_url: str = ''
    tmp_dir: Path = Path(tempfile.gettempdir()) / 'attre-admin'
    port: int = 8000
    github_token: str | None = field(default=None, repr=False)
    github_repo: str = ''
    github_branch: str = 'main'
    local_repo: Path | None = None
    trust_proxy: bool = False      # адрес посетителя — из X-Real-IP / X-Forwarded-For прокси Railway (auth.client_ip)
    # ключ к файлу сменённых паролей .admin/users.json; не задан — производный от SESSION_SECRET (passwords.py)
    password_pepper: str | None = field(default=None, repr=False)

    @property
    def user_names(self) -> list[str]:
        return list(self.users)


def parse_users(raw: str) -> dict[str, str]:
    """`Имя:пароль;Имя2:пароль2` → {имя: пароль}. Пароль может содержать «:», но не «;»."""
    users: dict[str, str] = {}
    seen: set[str] = set()
    for n, part in enumerate(raw.split(';'), 1):
        part = part.strip()
        if not part:
            continue
        name, sep, password = part.partition(':')
        name, password = name.strip(), password.strip()
        if not sep or not name or not password:
            raise ConfigError(f'ADMIN_USERS: запись № {n} должна выглядеть как «Имя:пароль» '
                              '(записи разделяются «;»)')
        if len(name) > 40:
            raise ConfigError(f'ADMIN_USERS: имя в записи № {n} длиннее 40 символов')
        if name.casefold() in seen:
            raise ConfigError(f'ADMIN_USERS: имя «{name}» встречается дважды')
        seen.add(name.casefold())
        users[name] = password
    return users


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env

    def get(name: str, default: str = '') -> str:
        return (env.get(name) or default).strip()

    problems: list[str] = []
    store = get('STORE', 'github').lower()
    if store not in ('github', 'local'):
        problems.append('STORE должна быть «github» или «local»')

    users: dict[str, str] = {}
    source = 'ADMIN_USERS'
    if get('ADMIN_USERS'):
        try:
            users = parse_users(get('ADMIN_USERS'))
        except ConfigError as ex:
            problems.append(str(ex))
        else:
            if not users:
                problems.append('ADMIN_USERS пустой — нужно «Имя:пароль;Имя2:пароль2»')
    elif get('ADMIN_PASSWORD'):
        users, source = {'Админ': get('ADMIN_PASSWORD')}, 'ADMIN_PASSWORD'
    else:
        problems.append('нужен ADMIN_USERS («Имя:пароль;Имя2:пароль2») или ADMIN_PASSWORD')
    if store == 'github':      # локально (STORE=local, без токена) можно и короткий пароль — удобнее разработке
        problems += weak_passwords(users, source)

    secret = get('SESSION_SECRET')
    if len(secret) < 32:
        problems.append('SESSION_SECRET — не короче 32 случайных символов (например: python -c '
                        '"import secrets; print(secrets.token_urlsafe(48))")')
    elif store == 'github' and not looks_random(secret):
        problems.append(f'SESSION_SECRET похож на заглушку, а не на случайный ключ (меньше {MIN_DISTINCT} разных '
                        'символов) — сгенерируйте: python3 -c "import secrets; print(secrets.token_urlsafe(48))"')
    pepper = get('PASSWORD_PEPPER') or None
    if pepper and len(pepper) < 32:
        problems.append('PASSWORD_PEPPER — не короче 32 случайных символов (или не задавайте: тогда ключ к файлу '
                        'паролей берётся из SESSION_SECRET)')
    elif pepper and store == 'github' and not looks_random(pepper):
        problems.append(f'PASSWORD_PEPPER похож на заглушку, а не на случайный ключ (меньше {MIN_DISTINCT} разных '
                        'символов) — сгенерируйте так же, как SESSION_SECRET')

    token, repo, branch, local_repo = None, '', get('GITHUB_BRANCH', 'main'), None
    if store == 'github':
        token = get('GITHUB_TOKEN') or None
        repo = get('GITHUB_REPO')
        if not token:
            problems.append('для STORE=github нужен GITHUB_TOKEN (fine-grained, один репозиторий: '
                            'Contents — чтение и запись, Actions — чтение, Metadata — чтение)')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            problems.append('GITHUB_REPO — в виде «владелец/репозиторий», например daulet-rama/attre-site')
        if not re.fullmatch(r'[A-Za-z0-9._/-]+', branch) or '..' in branch:
            problems.append('GITHUB_BRANCH — имя ветки, например main')
    elif store == 'local':
        raw = get('LOCAL_REPO')
        if not raw:
            problems.append('для STORE=local нужен LOCAL_REPO — путь к рабочей копии репозитория сайта')
        else:
            local_repo = Path(raw).expanduser().resolve()
            if not (local_repo / '.git').exists():
                problems.append(f'LOCAL_REPO: в папке {local_repo} нет git-репозитория')
            elif not (local_repo / 'data' / 'products').is_dir():
                problems.append(f'LOCAL_REPO: в папке {local_repo} нет data/products — это не репозиторий сайта')

    site_url = get('SITE_URL')
    if not site_url and repo and '/' in repo:
        owner, name = repo.split('/', 1)
        site_url = f'https://{owner.lower()}.github.io/{name}/v4/'
    if site_url and not re.match(r'https?://', site_url):
        problems.append('SITE_URL — адрес сайта, начинается с https://')
    if site_url and not site_url.endswith('/'):
        site_url += '/'

    try:
        port = int(get('PORT', '8000'))
    except ValueError:
        problems.append('PORT — число')
        port = 8000

    # Прокси Railway сам ставит X-Real-IP и X-Forwarded-For (то, что прислал браузер, он перезаписывает).
    # Без прокси этим заголовкам верить нельзя: их может подставить кто угодно.
    raw_trust = get('TRUST_PROXY').lower()
    if raw_trust in ('', 'auto'):
        trust_proxy = bool(get('RAILWAY_ENVIRONMENT_NAME') or get('RAILWAY_ENVIRONMENT'))
    elif raw_trust in ('railway', '1', 'true', 'yes', 'on'):
        trust_proxy = True
    elif raw_trust in ('0', 'false', 'no', 'off'):
        trust_proxy = False
    else:
        problems.append('TRUST_PROXY — «railway» (верить адресу посетителя от прокси Railway) или «0»')
        trust_proxy = False

    if problems:
        raise ConfigError('Админка не запущена — проверьте переменные окружения:\n  • ' + '\n  • '.join(problems))

    return Config(
        store=store, users=users, session_secret=secret, site_url=site_url,
        tmp_dir=Path(get('TMP_DIR') or Path(tempfile.gettempdir()) / 'attre-admin'),
        port=port, github_token=token, github_repo=repo, github_branch=branch, local_repo=local_repo,
        trust_proxy=trust_proxy, password_pepper=pepper,
    )


def looks_random(key: str) -> bool:
    """Не заглушка ли ключ: разных символов не меньше MIN_DISTINCT (сам ключ не печатаем)."""
    return len(set(key)) >= MIN_DISTINCT


def weak_passwords(users: dict[str, str], source: str = 'ADMIN_USERS') -> list[str]:
    """Пароли, которые легко подобрать: короче MIN_PASSWORD символов или совпадают с именем. Сами пароли не печатаем."""
    out = []
    for name, password in users.items():
        who = f'пароль для «{name}»' if source == 'ADMIN_USERS' else 'пароль'
        if len(password) < MIN_PASSWORD:
            out.append(f'{source}: {who} короче {MIN_PASSWORD} символов — придумайте длиннее '
                       '(например: python3 -c "import secrets; print(secrets.token_urlsafe(12))")')
        elif password.casefold() == name.casefold():
            out.append(f'{source}: {who} совпадает с именем')
    return out
