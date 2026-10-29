"""Вход (DESIGN.md → «Безопасность»).

Пароли — из ADMIN_USERS / ADMIN_PASSWORD; сравниваются их отпечатки SHA-256 через hmac.compare_digest — по времени
ответа не видно ни длины пароля, ни того, сколько символов совпало. Сессия — подписанная cookie (itsdangerous)
на 30 дней; при заходе она продлевается, но не дольше 90 дней от входа — потом пароль спросят снова.
В подписи — отпечаток пароля, поэтому смена пароля в переменных окружения выкидывает старые сессии.
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


class NeedName(Exception):
    """Пользователей несколько, а имя не выбрано."""


def _digest(password: str) -> bytes:
    return hashlib.sha256(str(password or '').encode('utf-8')).digest()


class Auth:
    def __init__(self, users: dict[str, str], secret: str, *, fail_delay: float = 1.0):
        if not users:
            raise ValueError('нет ни одного пользователя')
        self.users = dict(users)
        self._digests = {u: _digest(p) for u, p in self.users.items()}
        self._nobody = _digest('\0нет такого пользователя\0')
        self._secret = secret.encode('utf-8')
        self._signer = URLSafeTimedSerializer(secret, salt='attre-admin-session')
        self.limiter = LoginLimiter()
        self.fail_delay = fail_delay       # пауза после неверного пароля (main.py, без занятого потока)

    @property
    def names(self) -> list[str]:
        return list(self.users)

    def check(self, name: str | None, password: str | None) -> str | None:
        """→ имя пользователя, если пароль верный; иначе None. NeedName — если имя нужно, но не выбрано."""
        name = (name or '').strip()
        if not name:
            if len(self.users) > 1:
                raise NeedName()
            name = next(iter(self.users))
        match = next((u for u in self.users if u.casefold() == name.casefold()), None)
        expected = self._digests[match] if match else self._nobody
        ok = hmac.compare_digest(_digest(password or ''), expected)
        return match if ok and match else None

    def _fingerprint(self, user: str) -> str:
        return hmac.new(self._secret, f'{user}\0{self.users[user]}'.encode('utf-8'), hashlib.sha256).hexdigest()[:20]

    def make_cookie(self, user: str, started: float | None = None) -> str:
        """started — когда человек вошёл паролем (при продлении сессии переносится в новую cookie)."""
        return self._signer.dumps({'u': user, 'k': self._fingerprint(user), 's': int(started or time.time())})

    def read_cookie(self, value: str | None) -> tuple[str, float, float] | None:
        """Cookie → (имя, когда выдана, когда был вход паролем) или None."""
        if not value or len(value) > 1000:
            return None
        try:
            data, issued = self._signer.loads(value, max_age=MAX_AGE, return_timestamp=True)
        except (BadSignature, SignatureExpired, ValueError, TypeError):
            return None
        user = data.get('u') if isinstance(data, dict) else None
        if user not in self.users or not hmac.compare_digest(str(data.get('k', '')), self._fingerprint(user)):
            return None
        issued = issued.timestamp()
        started = data.get('s')
        if not isinstance(started, (int, float)) or isinstance(started, bool) or started > issued + 60:
            started = issued                         # cookie, выданная до этого правила, — считаем от её выдачи
        if time.time() - started > LIFETIME:
            return None
        return user, issued, float(started)

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
