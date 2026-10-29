"""Пароли, которые основательницы меняют сами (README.md → «Пароли и пользователи»).

Кто есть — по-прежнему из переменных окружения (ADMIN_USERS / ADMIN_PASSWORD); там же стартовые пароли.
Сменённый в админке пароль лежит в репозитории сайта, в файле .admin/users.json — в корне, а не в admin/:
правки admin/** перезапускают админку на Railway, а .admin/** сайт не пересобирает (paths-ignore в pages.yml):

    {"pepper_id": "<16 hex>", "users": {"Дамира": {"salt": "<base64, 16 байт>", "hash": "<64 hex>", "changed": "<ISO>"}}}

hash = HMAC-SHA256(pepper, scrypt(пароль в NFC и UTF-8, salt, n=2**14, r=8, p=1, dklen=32)).
pepper — PASSWORD_PEPPER (если задан) или HMAC-SHA256(SESSION_SECRET, «attre-admin password pepper v1»). Его нет
в репозитории, а репозиторий публичный: без pepper по файлу нельзя проверить ни одной догадки, даже для простого
пароля. pepper_id = HMAC-SHA256(pepper, «id»)[:16 hex]. Не совпал (поменяли SESSION_SECRET или PASSWORD_PEPPER) —
файл не используется целиком, вход снова по паролям из переменных: так владелец сбрасывает пароли всем сразу.

Файл читается через Store при старте (main.warm), при первой надобности и сразу после своей записи, дальше — не
чаще раза в 60 с, и каждый раз голова ветки спрашивается у GitHub заново (не из 15-секундного кэша): если Даулет
удалит на GitHub запись человека (сброс забытого пароля), админка подхватит это в течение минуты. Хранилище не
ответило — вход по последней прочитанной версии. Записи для имён, которых нет в переменных, не действуют.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .catalog import LOCK_WAIT, MSG_LOCKED, CatalogError
from .store import ConflictError, Store, StoreError, git_blob_sha

log = logging.getLogger('attre.passwords')

PATH = '.admin/users.json'
TTL = 60.0                # прочитанный файл перечитываем не чаще раза в минуту
RETRY = 10.0              # файл ещё ни разу не прочитался (GitHub не ответил) — пробуем чаще
MIN_LEN, MAX_LEN = 8, 128
SALT_BYTES = 16
SCRYPT = {'n': 2 ** 14, 'r': 8, 'p': 1, 'dklen': 32}     # одна проверка — около 16 МБ памяти и 30–60 мс
PEPPER_LABEL = b'attre-admin password pepper v1'
HASH_RE = re.compile(r'[0-9a-f]{64}')
# Невидимые символы: управляющие (Cc), форматирующие (Cf: нулевой ширины, направление текста), половинки
# суррогатных пар (Cs), разделители строк и абзацев. Такой пароль не набрать заново на другой клавиатуре.
BAD_CATEGORIES = frozenset({'Cc', 'Cf', 'Cs', 'Zl', 'Zp'})

# Тон — как у входа (main.MSG_BAD_PASSWORD): что проверить, а не «неверный»
MSG_WRONG = 'Текущий пароль не подошёл. Проверьте раскладку (русская или английская) и большие буквы.'
MSG_RACE = ('Не получилось сменить пароль: в это же время пароли меняли в другом месте. '
            'Нажмите «Сменить пароль» ещё раз.')

_SLOTS = threading.BoundedSemaphore(2)       # scrypt одновременно — не больше двух (память)


# ——————————————————————————— ключ, хеш, правила ———————————————————————————

def pepper_for(session_secret: str, password_pepper: str | None = None) -> bytes:
    """Ключ к файлу паролей: PASSWORD_PEPPER или производный от SESSION_SECRET (в репозиторий не попадает)."""
    if password_pepper:
        return password_pepper.encode('utf-8')
    return hmac.new(session_secret.encode('utf-8'), PEPPER_LABEL, hashlib.sha256).digest()


def pepper_id(pepper: bytes) -> str:
    """По нему видно, тем ли ключом записан файл (сам ключ по нему не узнать)."""
    return hmac.new(pepper, b'id', hashlib.sha256).hexdigest()[:16]


def _utf8(password: str) -> bytes:
    # NFC: «й» одной буквой и «и» + значок — один и тот же пароль; surrogatepass — кривой ввод не роняет проверку
    return unicodedata.normalize('NFC', password).encode('utf-8', 'surrogatepass')


def hash_password(password: str, salt: bytes, pepper: bytes) -> str:
    with _SLOTS:
        key = hashlib.scrypt(_utf8(password), salt=salt, **SCRYPT)
    return hmac.new(pepper, key, hashlib.sha256).hexdigest()


def make_record(password: str, pepper: bytes, now: datetime | None = None) -> dict:
    salt = secrets.token_bytes(SALT_BYTES)
    return {'salt': base64.b64encode(salt).decode('ascii'), 'hash': hash_password(password, salt, pepper),
            'changed': (now or datetime.now(timezone.utc)).isoformat(timespec='seconds')}


def record_salt(record: Any) -> bytes | None:
    """Соль записи, если запись правильная (соль — base64 из 16 байт, hash — 64 hex); иначе None."""
    if not isinstance(record, dict):
        return None
    salt, digest = record.get('salt'), record.get('hash')
    if not isinstance(salt, str) or not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
        return None
    try:
        raw = base64.b64decode(salt, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if len(raw) == SALT_BYTES else None


def verify(password: Any, record: dict, pepper: bytes) -> bool:
    """Подходит ли пароль к записи. Сравнение — за постоянное время."""
    salt = record_salt(record)
    if salt is None or not isinstance(password, str):
        return False
    return hmac.compare_digest(hash_password(password, salt, pepper), record['hash'])


def _fold(s: str) -> str:
    return unicodedata.normalize('NFC', s).casefold()


def new_password_problem(new: Any, name: str, current: Any = '') -> str | None:
    """Что не так с новым паролем (текст для человека) или None. Те же правила — в static/js/password.js."""
    if not isinstance(new, str) or not new:
        return 'Придумайте новый пароль.'
    if any(unicodedata.category(ch) in BAD_CATEGORIES for ch in new):
        return 'В новом пароле есть невидимые служебные символы. Наберите его заново с клавиатуры.'
    if new != new.strip():
        return 'Уберите пробелы в начале и в конце нового пароля.'
    if len(new) < MIN_LEN:
        return f'Новый пароль слишком короткий — нужно не меньше {MIN_LEN} символов.'
    if len(new) > MAX_LEN:
        return f'Новый пароль слишком длинный — не больше {MAX_LEN} символов.'
    if _fold(new) == _fold(name or ''):
        return 'Новый пароль не должен совпадать с вашим именем.'
    if isinstance(current, str) and current and _fold(new) == _fold(current):
        return 'Новый пароль совпадает с текущим — придумайте другой.'
    return None


def dumps(doc: dict) -> bytes:
    """Формат файлов сайта: json с отступом 2, кириллица как есть, перевод строки в конце."""
    return (json.dumps(doc, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


# ——————————————————————————— файл ———————————————————————————

@dataclass(frozen=True)
class FileState:
    """Одна прочитанная версия файла."""
    sha: str | None                               # blob sha файла (None — файла нет)
    records: dict[str, dict] = field(default_factory=dict)   # имя (как в переменных) → действующая запись
    doc: dict | None = None                       # содержимое, которое можно дописывать (None — начать заново)
    problem: str | None = None                    # почему файл не используется (для журнала)
    unknown: tuple[str, ...] = ()                 # имена из файла, которых нет в переменных
    broken: tuple[str, ...] = ()                  # испорченные записи известных имён


class Passwords:
    """Сменённые пароли: последняя прочитанная версия .admin/users.json (перечитывается не чаще раза в ttl),
    проверка и запись. Потокобезопасно: версия заменяется целиком, читает файл один поток за раз, а чтение,
    начатое до записи, записанную версию не затрёт."""

    def __init__(self, store: Store, pepper: bytes, names: list[str], *, ttl: float = TTL, retry: float = RETRY,
                 clock: Callable[[], float] = time.monotonic):
        self.store, self.pepper, self.pepper_id = store, pepper, pepper_id(pepper)
        self.names = list(names)
        self._canon = {n.casefold(): n for n in self.names}
        self.ttl, self.retry, self.clock = ttl, retry, clock
        self.error: StoreError | None = None      # почему не прочитали в последний раз
        self._state: FileState | None = None      # None — ещё ни разу не прочитали
        self._checked: float | None = None        # когда последний раз пробовали прочитать
        self._gen = 0                             # номер версии в памяти: растёт при каждой замене
        self._logged: tuple | None = None         # о чём уже написали в журнал (не повторять каждую минуту)
        self._read_lock = threading.Lock()
        self._state_lock = threading.Lock()

    # ——— чтение ———
    @property
    def loaded(self) -> bool:
        return self._state is not None

    def record(self, name: str) -> dict | None:
        """Действующая запись человека (без обращения к хранилищу) или None — тогда пароль из переменных."""
        state = self._state
        return state.records.get(name) if state else None

    def stale(self) -> bool:
        if self._checked is None:
            return True
        return self.clock() - self._checked >= (self.ttl if self._state is not None else self.retry)

    def needs_check(self) -> bool:
        """Нужно ли звать ensure(): версии ещё нет (может, её как раз читают — тогда подождать) или пора перечитать."""
        return self._state is None or self.stale()

    def ensure(self) -> bool:
        """Перечитать файл, если пора. → есть ли прочитанная версия (хранилище не ответило — остаётся прежняя).
        Версии ещё нет, а файл в это время читает другой поток — ждём его, а не отвечаем «нет»: иначе запросы,
        пришедшие сразу после запуска, остались бы без сменённых паролей."""
        if not self.needs_check():
            return True
        with self._read_lock:
            if not self.stale():                  # пока ждали, файл перечитал сосед
                return self.loaded
            self._checked = self.clock()
            try:
                # fresh: голова ветки — с GitHub, а не из её кэша на 15 с (иначе сброс на GitHub подхватывался бы
                # до 75 с вместо обещанной минуты); это один запрос в минуту
                self._read(fresh=True)
            except StoreError as ex:
                self.error = ex
                log.warning('файл паролей %s не прочитан (%s) — %s', PATH, ex.message,
                            'вход по прочитанной раньше версии' if self.loaded else 'вход подождёт хранилище')
            except Exception:   # noqa: BLE001 — сбой чтения не роняет запросы: остаёмся на прежней версии
                log.exception('файл паролей %s не прочитан', PATH)
            return self.loaded

    def fresh(self) -> FileState:
        """Файл прямо сейчас (голова ветки — с GitHub, не из кэша). Для смены пароля, под writing()."""
        return self._read(fresh=True)

    def _read(self, fresh: bool) -> FileState:
        gen = self._gen
        snap = self.store.snapshot(fresh=fresh)
        sha = snap.blob_sha(PATH)
        state = self.parse(snap.read(PATH) if sha else None, sha)
        self._set(state, gen)
        return state

    def _set(self, state: FileState, gen: int | None = None):
        """Новая версия в памяти. gen — номер версии, при которой начали читать: если с тех пор файл записали
        (номер вырос), прочитанное старее записанного и не нужно."""
        with self._state_lock:
            if gen is not None and gen != self._gen:
                return
            self._gen += 1
            self._state, self.error, self._checked = state, None, self.clock()
            note = (state.sha, state.problem, state.unknown, state.broken)
            if note == self._logged:              # в журнал — только когда что-то поменялось
                return
            self._logged = note
        if state.problem:
            log.warning('%s', state.problem)
        if state.broken:
            log.warning('файл паролей %s: испорчена запись %s — для неё действует пароль из переменных окружения',
                        PATH, ', '.join(f'«{n}»' for n in state.broken))
        if state.unknown:
            log.info('файл паролей %s: записи %s не действуют — таких имён нет в переменных окружения', PATH,
                     ', '.join(f'«{n}»' for n in state.unknown))

    def parse(self, data: bytes | None, sha: str | None) -> FileState:
        if data is None:
            return FileState(sha=None)
        try:
            doc = json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return FileState(sha=sha, problem=f'файл паролей {PATH} не читается (испорчен JSON) — не используем '
                                              'его: вход по паролям из переменных окружения')
        if not isinstance(doc, dict) or not isinstance(doc.get('users'), dict):
            return FileState(sha=sha, problem=f'файл паролей {PATH} устроен не так (нет «users») — не используем '
                                              'его: вход по паролям из переменных окружения')
        if doc.get('pepper_id') != self.pepper_id:
            return FileState(sha=sha, problem=f'файл паролей {PATH} записан с другим ключом (поменяли SESSION_SECRET '
                                              'или PASSWORD_PEPPER) — не используем его: вход по паролям из '
                                              'переменных окружения')
        users = doc['users']
        records: dict[str, dict] = {}
        unknown, broken = [], []
        for key, rec in users.items():
            name = self._canon.get(key.casefold())
            if name is None:
                unknown.append(key)
            elif key != name and name in users:
                continue                          # «дамира» при записи «Дамира» (как в переменных) — не главная
            elif record_salt(rec) is None:
                broken.append(name)
            else:
                records[name] = rec
        return FileState(sha=sha, records=records, doc=doc, unknown=tuple(unknown), broken=tuple(broken))

    # ——— проверка ———
    def verify(self, password: Any, record: dict) -> bool:
        return verify(password, record, self.pepper)

    # ——— запись ———
    @contextmanager
    def writing(self):
        """Одна запись за раз — общая очередь с товарами и настройками (store.write_lock)."""
        if not self.store.write_lock.acquire(timeout=LOCK_WAIT):
            raise CatalogError(MSG_LOCKED, status=503)
        try:
            yield
        finally:
            self.store.write_lock.release()

    def save(self, name: str, password: str, base: FileState) -> dict:
        """Записать новый пароль человека поверх версии base. Её sha — защита от одновременной записи: если файл
        с тех пор изменился (Даулет на GitHub, вторая копия админки при деплое) — CatalogError 409, ничего
        не записано. Чужие записи и прочие поля файла остаются как были. Вызывать под writing(). → новая запись."""
        doc = dict(base.doc) if base.doc is not None else {}
        users = dict(doc.get('users') or {})
        for key in [k for k in users if k.casefold() == name.casefold() and k != name]:
            del users[key]                        # то же имя другими буквами — убираем, чтобы не путаться
        record = make_record(password, self.pepper)
        users[name] = record
        doc['pepper_id'], doc['users'] = self.pepper_id, users
        data = dumps(doc)
        try:
            self.store.commit({PATH: data}, f'Админка: смена пароля ({name})', name, expect={PATH: base.sha},
                              publish=False)
        except ConflictError:
            raise CatalogError(MSG_RACE, status=409) from None
        self._set(self.parse(data, git_blob_sha(data)))      # записанное и есть свежая версия файла
        return record
