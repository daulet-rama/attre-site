"""Вход (DESIGN.md → «Безопасность»).

Стартовые пароли — из ADMIN_USERS / ADMIN_PASSWORD; сравниваются их отпечатки SHA-256 через hmac.compare_digest —
по времени ответа не видно ни длины пароля, ни того, сколько символов совпало. Если человек сменил пароль
в админке, у него запись в .admin/users.json (passwords.py): тогда проверка — по ней (scrypt), а пароль из
переменных для него больше не действует. Сессия — подписанная cookie (itsdangerous) на 30 дней; при заходе она
продлевается, но не дольше 90 дней от входа — потом пароль спросят снова. В подписи — отпечаток пароля (у сменённого —
его hash), поэтому любая смена пароля выкидывает старые сессии этого человека. У сменённого пароля в отпечатке ещё
и то, чего нет в публичном репозитории (стартовый пароль, ключ к файлу паролей): одного SESSION_SECRET и hash из
файла мало, чтобы подделать вход.
Перебор: не больше 10 неудачных попыток за 15 минут с одного адреса (у IPv6 — с одной сети /64: у одного
человека их миллиарды). Если неудач со всех адресов вместе больше 30 за 15 минут — «медленный режим»: после
каждой неудачи вход закрыт для всех на минуту (подбор с тысяч адресов ботнета упирается в одну попытку в минуту).
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import threading
import time
from collections import deque

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE = 'attre_session'
MAX_AGE = 30 * 24 * 3600
LIFETIME = 90 * 24 * 3600          # дольше этого от входа сессию не продлеваем
REFRESH_AFTER = 24 * 3600          # сессию старше суток продлеваем при заходе — активных не выкидывает через месяц
CHANGED = 'password'               # причина отказа: cookie наша, но пароль с тех пор сменили (или сбросили)
_CACHED = object()                 # «запись человека — из прочитанной версии файла паролей»


class NeedName(Exception):
    """Пользователей несколько, а имя не выбрано."""


def _digest(password: str) -> bytes:
    return hashlib.sha256(str(password or '').encode('utf-8', 'surrogatepass')).digest()


class Auth:
    """passwords — сменённые в админке пароли (passwords.Passwords); без него — только пароли из переменных."""

    def __init__(self, users: dict[str, str], secret: str, *, fail_delay: float = 1.0, passwords=None):
        if not users:
            raise ValueError('нет ни одного пользователя')
        self.users = dict(users)
        self.passwords = passwords
        self._digests = {u: _digest(p) for u, p in self.users.items()}
        self._nobody = _digest('\0нет такого пользователя\0')
        self._secret = secret.encode('utf-8')
        self._signer = URLSafeTimedSerializer(secret, salt='attre-admin-session')
        self.limiter = LoginLimiter()
        self.fail_delay = fail_delay       # пауза после неверного пароля (main.py, без занятого потока)
        self._attempts = threading.Lock()  # проверки паролей при входе — по одной (см. attempt)

    @property
    def names(self) -> list[str]:
        return list(self.users)

    def _record(self, user: str) -> dict | None:
        return self.passwords.record(user) if self.passwords is not None else None

    def _ok(self, user: str, password: str, record: dict | None) -> bool:
        """Пароль человека: сменённый (запись в файле) или, если записи нет, из переменных окружения."""
        if record is not None:
            return self.passwords.verify(password, record)
        return hmac.compare_digest(_digest(password), self._digests[user])

    def check(self, name: str | None, password: str | None) -> str | None:
        """→ имя пользователя, если пароль верный; иначе None. NeedName — если имя нужно, но не выбрано.
        У сменённого пароля это scrypt (десятки миллисекунд) — из цикла событий вызывать через поток."""
        name = (name or '').strip()
        if not name:
            if len(self.users) > 1:
                raise NeedName()
            name = next(iter(self.users))
        match = next((u for u in self.users if u.casefold() == name.casefold()), None)
        if match is None:
            hmac.compare_digest(_digest(password or ''), self._nobody)    # столько же времени, сколько у своего
            return None
        return match if self._ok(match, password or '', self._record(match)) else None

    def attempt(self, ip: str, name: str | None, password: str | None) -> tuple[str | None, int]:
        """Попытка входа: (имя, 0) — пароль верный, (None, 0) — неверный (уже учтена в счётчике),
        (None, секунд) — с этого адреса пока нельзя. Попытки проверяются по одной (и вместе с проверками
        текущего пароля при смене): пока одна ждёт scrypt, другие с того же адреса не проскочат мимо счётчика."""
        with self._attempts:
            wait = self.limiter.retry_after(ip)
            if wait:
                return None, wait
            user = self.check(name, password)
            if not user:
                self.limiter.fail(ip)
            return user, 0

    def change_password(self, user: str, current: str, new: str, ip: str,
                        cookie: str | None = None) -> tuple[str, int]:
        """Смена своего пароля (в потоке: GitHub и scrypt). Новый пароль проверен заранее (new_password_problem).
        → ('ok', 0) | ('wrong', 0) — текущий не подошёл (учтено в счётчике попыток) | ('wait', секунд) |
        ('stale', 0) — cookie запроса уже не действует: пароль этого человека только что сменили на другом
        устройстве (или сбросили) — тут нужен вход заново, а не «неверный текущий пароль» и не попытка в счётчике.
        Текущий пароль сверяется со свежей версией файла (не с кэшем) под общей блокировкой записи: две
        одновременные смены идут по очереди, и вторая уже видит пароль, поставленный первой. Сама проверка —
        под той же блокировкой попыток, что и вход: смена и вход с одного адреса не обходят счётчик вдвоём."""
        pw = self.passwords
        with pw.writing():
            wait = self.limiter.retry_after(ip)
            if wait:                                  # заблокированный адрес не заставит читать GitHub
                return 'wait', wait
            state = pw.fresh()
            record = state.records.get(user)
            if cookie is not None and self.read_cookie(cookie, record) is None:
                return 'stale', 0
            with self._attempts:
                wait = self.limiter.retry_after(ip)
                if wait:
                    return 'wait', wait
                if not self._ok(user, current, record):
                    self.limiter.fail(ip)
                    return 'wrong', 0
            pw.save(user, new, state)
            return 'ok', 0

    def _fingerprint(self, user: str, record=_CACHED) -> str:
        """Отпечаток пароля человека для подписи cookie. record — его запись в файле паролей (None — записи нет);
        по умолчанию — из прочитанной версии файла."""
        if record is _CACHED:
            record = self._record(user)
        start = self.users[user]
        if record is None:
            material, key = f'{user}\0{start}', self._secret
        else:
            # Пароль сменён в админке — отпечаток от его hash: новая смена (или сброс записи) — старые входы не
            # действуют. hash лежит в публичном репозитории, поэтому в отпечатке ещё стартовый пароль и ключ к файлу
            # паролей (PASSWORD_PEPPER, если задан): по одному SESSION_SECRET вход не подделать.
            material = f'{user}\0файл\0{record["hash"]}\0{start}'
            key = self._secret + b'\0' + self.passwords.pepper
        return hmac.new(key, material.encode('utf-8', 'surrogatepass'), hashlib.sha256).hexdigest()[:20]

    def make_cookie(self, user: str, started: float | None = None) -> str:
        """started — когда человек вошёл паролем (при продлении сессии переносится в новую cookie)."""
        return self._signer.dumps({'u': user, 'k': self._fingerprint(user), 's': int(started or time.time())})

    def check_cookie(self, value: str | None, record=_CACHED) -> tuple[tuple[str, float, float] | None, str | None]:
        """Cookie → ((имя, когда выдана, когда был вход паролем), None) или (None, причина): CHANGED — cookie наша
        и не истекла, но пароль человека с тех пор сменили или сбросили; None — нет cookie, чужая или истекла.
        record — сверить с этой записью файла паролей (свежей), а не с прочитанной раньше."""
        if not value or len(value) > 1000:
            return None, None
        try:
            data, issued = self._signer.loads(value, max_age=MAX_AGE, return_timestamp=True)
        except (BadSignature, SignatureExpired, ValueError, TypeError):
            return None, None
        user = data.get('u') if isinstance(data, dict) else None
        if user not in self.users:
            return None, None
        issued = issued.timestamp()
        started = data.get('s')
        if not isinstance(started, (int, float)) or isinstance(started, bool) or started > issued + 60:
            started = issued                         # cookie, выданная до этого правила, — считаем от её выдачи
        if time.time() - started > LIFETIME:
            return None, None
        if not hmac.compare_digest(str(data.get('k', '')), self._fingerprint(user, record)):
            return None, CHANGED
        return (user, issued, float(started)), None

    def read_cookie(self, value: str | None, record=_CACHED) -> tuple[str, float, float] | None:
        """Cookie → (имя, когда выдана, когда был вход паролем) или None."""
        return self.check_cookie(value, record)[0]

    @staticmethod
    def needs_refresh(issued: float) -> bool:
        return time.time() - issued > REFRESH_AFTER

    @staticmethod
    def max_age(started: float) -> int:
        """Сколько ещё жить cookie: 30 дней, но не дальше 90 дней от входа."""
        return max(0, min(MAX_AGE, int(started + LIFETIME - time.time())))


class LoginLimiter:
    """Неудачные попытки по адресу в скользящем окне + общий тормоз на все адреса. Память ограничена."""

    def __init__(self, max_attempts: int = 10, window: float = 15 * 60, max_ips: int = 10000,
                 global_max: int = 30, global_pause: float = 60):
        self.max_attempts, self.window, self.max_ips = max_attempts, window, max_ips
        self.global_max, self.global_pause = global_max, global_pause
        self._fails: dict[str, deque] = {}
        self._all: deque = deque()            # время всех неудач (последние global_max * 4)
        self._lock = threading.Lock()

    def _prune(self, ip: str, now: float) -> deque:
        q = self._fails.get(ip)
        if q is None:
            return deque()
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            self._fails.pop(ip, None)
        return q

    def retry_after(self, ip: str) -> int:
        """Сколько секунд ждать (0 — можно пробовать)."""
        now = time.monotonic()
        with self._lock:
            wait = 0
            q = self._prune(ip, now)
            if len(q) >= self.max_attempts:
                wait = max(1, int(self.window - (now - q[0])) + 1)
            while self._all and now - self._all[0] > self.window:
                self._all.popleft()
            if len(self._all) > self.global_max:
                since = now - self._all[-1]
                if since < self.global_pause:
                    wait = max(wait, int(self.global_pause - since) + 1)
            return wait

    def fail(self, ip: str):
        now = time.monotonic()
        with self._lock:
            if ip not in self._fails and len(self._fails) >= self.max_ips:
                for old in list(self._fails)[: self.max_ips // 10]:
                    self._fails.pop(old, None)
            q = self._fails.setdefault(ip, deque())
            q.append(now)
            while len(q) > self.max_attempts * 2:
                q.popleft()
            self._all.append(now)
            while len(self._all) > self.global_max * 4:
                self._all.popleft()


def _parse_ip(value: str | None):
    s = (value or '').strip()
    if s.startswith('[') and ']' in s:              # [2001:db8::1]:443
        s = s[1:s.index(']')]
    elif s.count(':') == 1:                          # 203.0.113.7:51234
        s = s.split(':', 1)[0]
    try:
        return ipaddress.ip_address(s)
    except ValueError:
        return None


def client_ip(headers, peer: str | None, trust_proxy: bool = False) -> str:
    """Адрес для счётчика попыток входа.

    За прокси Railway (trust_proxy): X-Real-IP, а если его нет — первый адрес X-Forwarded-For. Край Railway ставит
    оба заголовка сам и то, что прислал браузер, перезаписывает; последний адрес в цепочке — это уже узел Railway
    (у всех посетителей он один, и счётчик стал бы общим). Без прокси — адрес соединения: заголовкам там верить нельзя.
    IPv6 сводится к сети /64 — столько адресов обычно у одного подключения."""
    ip = None
    if trust_proxy:
        ip = _parse_ip(headers.get('x-real-ip'))
        if ip is None:
            ip = _parse_ip((headers.get('x-forwarded-for') or '').split(',')[0])
    if ip is None:
        ip = _parse_ip(peer)
        if ip is None:
            return (peer or 'unknown')[:64]
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f'{ip}/64', strict=False))
    return str(ip)


def is_local_host(host: str | None) -> bool:
    """localhost, 127.0.0.1, [::1], *.localhost и адреса домашней сети — там cookie без Secure (обычный http)."""
    host = (host or '').strip('[]').lower()
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local
