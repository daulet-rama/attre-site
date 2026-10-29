"""Хранилище файлов сайта (DESIGN.md → «Хранилище»).

* LocalStore — рабочая копия репозитория + git CLI (git add/rm, git commit --author), без push. Разработка и тесты.
* GitHubStore — GitHub REST API: дерево ветки, содержимое через blobs, коммит через Git Data API
  (blobs по одному → tree с base_tree → commit → PATCH ref), повтор, если ветка ушла вперёд (но не при отказе,
  когда ветка на месте — защита ветки и т. п.). Ответ на PATCH потерялся (таймаут, обрыв, перезапуск при деплое) —
  ветку перечитываем: если она уже на нашем коммите, сохранение удалось. Голову ветки спрашивает один запрос
  на всех (кэш 15 с); если GitHub не ответил, чтение получает последнюю известную голову, запись — ошибку.
* Писать можно только товары, настройки, тексты сайта и фото товаров (WRITABLE_RE).

Оба читают закоммиченное состояние ветки: путь → blob sha (sha как у git, по нему же — защита от одновременной правки).
Все записи идут через одну блокировку на процесс (`write_lock`, reentrant: каталог держит её на всё
«прочитать → проверить → записать», а `commit` берёт её ещё раз).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import subprocess
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable
from urllib.parse import quote

import httpx

log = logging.getLogger('attre.store')

AUTHOR_EMAIL = 'admin@attre.local'
COMMITTER = 'Админка attré'
# Админка пишет только эти файлы: товары, настройки магазина, тексты сайта и фото товаров. Токен GitHub может
# писать и build.py / core.py (их выполняет GitHub Actions) — узкий список ограничивает вред от ошибки в коде админки.
WRITABLE_RE = re.compile(r'data/products/[a-z0-9][a-z0-9_-]{0,79}\.json|data/settings\.json|data/i18n\.json'
                         r'|media/products/[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?i:jpe?g|png|webp)')


class StoreError(Exception):
    """Хранилище недоступно или отказало. message — по-русски, можно показать человеку."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


class ConflictError(Exception):
    """Файл изменился с тех пор, как его прочитали: сохранять поверх нельзя."""

    def __init__(self, path: str):
        super().__init__(path)
        self.path = path


def git_blob_sha(data: bytes) -> str:
    """sha, который git (и GitHub) присвоит файлу с таким содержимым."""
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def check_path(path: str) -> str:
    """Путь внутри репозитория: относительный, без «..», только файлы из WRITABLE_RE."""
    if not isinstance(path, str) or not path or '\\' in path or '\0' in path or path.startswith('/'):
        raise ValueError(f'недопустимый путь: {path!r}')
    parts = PurePosixPath(path).parts
    if any(p in ('', '.', '..') for p in parts) or PurePosixPath(path).as_posix() != path:
        raise ValueError(f'недопустимый путь: {path!r}')
    if not WRITABLE_RE.fullmatch(path):
        raise ValueError(f'админка пишет только товары, настройки, тексты и фото товаров: {path!r}')
    return path


def clean_author(name: str) -> str:
    return re.sub(r'[<>\n\r\t\0]', '', str(name or '')).strip()[:60] or 'Админ'


class _LRU:
    """Кэш по неизменяемым ключам (sha): ограничен числом элементов и суммарным размером.
    Элементы крупнее max_item_bytes (фото) не кэшируются — у превью свой кэш на диске."""

    def __init__(self, max_items: int = 256, max_bytes: int | None = None, max_item_bytes: int | None = None):
        self.max_items, self.max_bytes, self.max_item_bytes = max_items, max_bytes, max_item_bytes
        self._d: OrderedDict = OrderedDict()
        self._size = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._d.get(key)
            if item is None:
                return None
            self._d.move_to_end(key)
            return item[0]

    def put(self, key, value, size: int = 0):
        if self.max_item_bytes is not None and size > self.max_item_bytes:
            return
        with self._lock:
            if key in self._d:
                return
            self._d[key] = (value, size)
            self._size += size
            while len(self._d) > self.max_items or (self.max_bytes is not None and self._size > self.max_bytes):
                _, (_, old_size) = self._d.popitem(last=False)
                self._size -= old_size

    def clear(self):
        with self._lock:
            self._d.clear()
            self._size = 0


class Snapshot:
    """Состояние ветки на один коммит: всё, что читается в одном запросе, — из одного снимка."""

    def __init__(self, store: 'Store', head: str, tree: dict[str, str]):
        self.store, self.head, self.tree = store, head, tree

    def list(self, prefix: str = '') -> dict[str, str]:
        return {p: s for p, s in self.tree.items() if p.startswith(prefix)}

    def blob_sha(self, path: str) -> str | None:
        return self.tree.get(path)

    def read(self, path: str) -> bytes | None:
        sha = self.tree.get(path)
        return None if sha is None else self.store.read_blob(sha)

    def read_many(self, paths: Iterable[str]) -> dict[str, bytes | None]:
        paths = list(paths)
        shas = {p: self.tree.get(p) for p in paths}
        blobs = self.store.read_blobs([s for s in shas.values() if s])
        return {p: (blobs.get(s) if s else None) for p, s in shas.items()}


class Store:
    """Общий интерфейс (DESIGN.md): head, list, read, blob_sha, commit. Плюс снимок, статус публикации."""

    kind = ''

    def __init__(self):
        self.write_lock = threading.RLock()
        self.last_commit: str | None = None       # последний коммит этой админки (для статуса публикации)
        self.last_commit_at: float | None = None
        self._blobs = _LRU(max_items=4000, max_bytes=48 * 1024 * 1024, max_item_bytes=512 * 1024)

    # ——— то, что реализуют наследники ———
    def head(self, fresh: bool = False) -> str:
        raise NotImplementedError

    def _tree(self, commit: str) -> dict[str, str]:
        raise NotImplementedError

    def _fetch_blob(self, sha: str) -> bytes:
        raise NotImplementedError

    def _commit(self, changes: dict[str, bytes | None], message: str, author: str,
                expect: dict[str, str | None]) -> tuple[str, bool]:
        """→ (sha головы после записи, был ли создан новый коммит)."""
        raise NotImplementedError

    # ——— общее ———
    def snapshot(self, fresh: bool = False) -> Snapshot:
        head = self.head(fresh=fresh)
        return Snapshot(self, head, self._tree(head))

    def list(self, prefix: str) -> dict[str, str]:
        return self.snapshot().list(prefix)

    def read(self, path: str) -> bytes | None:
        return self.snapshot().read(path)

    def blob_sha(self, path: str) -> str | None:
        return self.snapshot().blob_sha(path)

    def read_blob(self, sha: str) -> bytes:
        data = self._blobs.get(sha)
        if data is None:
            data = self._fetch_blob(sha)
            self._blobs.put(sha, data, len(data))
        return data

    def read_blobs(self, shas: list[str]) -> dict[str, bytes]:
        return {s: self.read_blob(s) for s in dict.fromkeys(shas)}

    def commit(self, changes: dict[str, bytes | None], message: str, author: str,
               expect: dict[str, str | None] | None = None) -> str:
        """Один коммит: путь → новое содержимое (None — удалить). → sha коммита.
        expect: путь → какой blob sha должен быть у файла сейчас (None — файла быть не должно);
        если хоть один не совпал — ConflictError, ничего не записано."""
        for p in list(changes) + list(expect or {}):
            check_path(p)
        for p, v in changes.items():
            if v is not None and not isinstance(v, (bytes, bytearray)):
                raise TypeError(f'{p}: содержимое должно быть bytes')
        with self.write_lock:
            sha, created = self._commit(dict(changes), message, clean_author(author), dict(expect or {}))
            if created:
                self.last_commit, self.last_commit_at = sha, time.time()
            return sha

    def publish_status(self) -> dict:
        return {'state': 'unknown', 'commit': self.last_commit, 'url': None, 'started': None, 'finished': None}

    def close(self):
        pass


def _check_expect(tree: dict[str, str], expect: dict[str, str | None]):
    for path, sha in expect.items():
        if tree.get(path) != sha:
            raise ConflictError(path)


# ——————————————————————————— локальная папка + git ———————————————————————————

class LocalStore(Store):
    kind = 'local'

    def __init__(self, root: str | os.PathLike):
        super().__init__()
        self.root = Path(root).resolve()
        if not (self.root / '.git').exists():
            raise StoreError(f'В папке {self.root} нет git-репозитория', 500)
        self._trees = _LRU(max_items=8)
        self.head()

    def _git(self, *args: str, config: tuple[str, ...] = (), timeout: float = 120) -> bytes:
        env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C'}
        cmd = ['git', '-C', str(self.root), '-c', 'core.quotepath=off']
        for c in config:
            cmd += ['-c', c]
        cmd += list(args)
        try:
            res = subprocess.run(cmd, capture_output=True, env=env, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError) as ex:
            raise StoreError(f'Не получилось запустить git: {ex}', 500) from ex
        if res.returncode != 0:
            err = res.stderr.decode('utf-8', 'replace').strip()[:500]
            log.error('git %s: %s', args[0], err)
            raise StoreError(f'git {args[0]} не сработал: {err}', 500)
        return res.stdout

    def head(self, fresh: bool = False) -> str:
        return self._git('rev-parse', '--verify', 'HEAD^{commit}').decode().strip()

    def _tree(self, commit: str) -> dict[str, str]:
        tree = self._trees.get(commit)
        if tree is None:
            tree = {}
            for entry in self._git('ls-tree', '-r', '-z', '--full-tree', commit).split(b'\0'):
                if not entry:
                    continue
                meta, _, path = entry.partition(b'\t')
                mode, typ, sha = meta.decode().split()
                if typ == 'blob':
                    tree[path.decode('utf-8')] = sha
            self._trees.put(commit, tree)
        return tree

    def _fetch_blob(self, sha: str) -> bytes:
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError(sha)
        return self._git('cat-file', 'blob', sha)

    def _commit(self, changes, message, author, expect):
        head = self.head()
        tree = self._tree(head)
        _check_expect(tree, expect)
        writes = {p: bytes(v) for p, v in changes.items() if v is not None and tree.get(p) != git_blob_sha(bytes(v))}
        deletes = [p for p, v in changes.items() if v is None and p in tree]
        if not writes and not deletes:
            return head, False
        for path, data in writes.items():
            full = self.root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            tmp = full.with_name(f'.{full.name}.tmp-{os.getpid()}')
            tmp.write_bytes(data)
            os.replace(tmp, full)
        if writes:
            self._git('add', '--', *writes)
        if deletes:
            self._git('rm', '-q', '--ignore-unmatch', '--', *deletes)
        self._git('commit', '-q', '--no-verify', '-m', message, '--author', f'{author} <{AUTHOR_EMAIL}>',
                  '--', *writes, *deletes,
                  config=(f'user.name={COMMITTER}', f'user.email={AUTHOR_EMAIL}', 'commit.gpgsign=false'))
        sha = self.head()
        log.info('коммит %s: %s', sha[:10], message)
        return sha, True


# ——————————————————————————— GitHub REST API ———————————————————————————

MSG_DOWN = 'GitHub не отвечает, попробуйте через минуту.'
MSG_RATE = 'GitHub временно ограничил число запросов. Попробуйте через несколько минут.'
MSG_TOKEN = 'GitHub не принимает ключ доступа админки. Сообщите Даулету.'
MSG_RIGHTS = 'У админки нет прав на этот репозиторий на GitHub. Сообщите Даулету.'
MSG_NOREPO = 'Репозиторий или ветка не найдены на GitHub. Сообщите Даулету.'
MSG_BUSY = ('Не получилось сохранить: на GitHub одновременно шли другие изменения. '
            'Попробуйте ещё раз через минуту.')
MSG_REFUSED = 'GitHub не принял сохранение. Сообщите Даулету.'

READ_TIMEOUT = httpx.Timeout(15.0, connect=5.0)     # чтение: не держим поток минутами, если GitHub тормозит
WRITE_TIMEOUT = httpx.Timeout(60.0, connect=5.0)    # запись: фото по несколько мегабайт


def _retry_after(resp: httpx.Response) -> int | None:
    """Retry-After в секундах (так GitHub отвечает при вторичном лимите) или None."""
    value = (resp.headers.get('retry-after') or '').strip()
    return int(value) if value.isdigit() else None


class GitHubStore(Store):
    kind = 'github'
    API = 'https://api.github.com'

    def __init__(self, token: str, repo: str, branch: str = 'main', *, transport: httpx.BaseTransport | None = None,
                 api_url: str = API, head_ttl: float = 15.0, status_ttl: float = 4.0,
                 sleep: Callable[[float], None] = time.sleep, workers: int = 6):
        super().__init__()
        if not token:
            raise StoreError(MSG_TOKEN, 500)
        self.repo, self.branch = repo, branch
        self._r = f'/repos/{repo}'
        self._client = httpx.Client(
            base_url=api_url, transport=transport, follow_redirects=True, timeout=READ_TIMEOUT,
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'attre-admin'})
        self._head_ttl, self._status_ttl, self._sleep, self._workers = head_ttl, status_ttl, sleep, workers
        self._head: tuple[str, float, float] | None = None   # (sha, когда начали запрос, когда пришёл ответ)
        self._head_err: tuple[StoreError, float] | None = None   # последняя неудача запроса головы и когда
        self._head_lock = threading.Lock()                    # короткая: только чтение и запись полей выше
        self._head_fetch = threading.Lock()                   # один запрос головы к GitHub на всех
        self._commit_trees = _LRU(max_items=64)     # sha коммита → sha дерева
        self._trees = _LRU(max_items=8)             # sha коммита → {путь: blob sha}
        self._status: tuple[dict, float] | None = None

    def close(self):
        self._client.close()

    # ——— HTTP ———
    def _request(self, method: str, url: str, *, ok: tuple[int, ...] = (200,), allow: tuple[int, ...] = (),
                 retry: bool | None = None, rate_retry: bool = False, **kw) -> httpx.Response:
        """Запрос к API. Сбой сети или 5xx повторяется один раз — у чтения (GET) и там, где retry=True (создание
        blobs, trees, commits: лишний объект git ничему не мешает). Запись ветки (PATCH) не повторяется — см. _commit.
        rate_retry — при 403/429 с Retry-After не больше 30 с подождать и повторить один раз.
        allow — коды, которые вызывающий разберёт сам (их ответ возвращается как есть)."""
        attempts = 2 if (method == 'GET' if retry is None else retry) else 1
        timeout = READ_TIMEOUT if method == 'GET' else WRITE_TIMEOUT
        waited = not rate_retry
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._client.request(method, url, timeout=timeout, **kw)
            except httpx.TimeoutException as ex:
                log.warning('GitHub %s %s: таймаут (%s)', method, url, type(ex).__name__)
                err = StoreError(MSG_DOWN, 504)
            except httpx.HTTPError as ex:
                log.warning('GitHub %s %s: сбой сети (%s)', method, url, type(ex).__name__)
                err = StoreError(MSG_DOWN, 503)
            else:
                if resp.status_code in ok or resp.status_code in allow:
                    return resp
                pause = _retry_after(resp)
                if not waited and resp.status_code in (403, 429) and pause is not None and pause <= 30:
                    waited = True
                    log.warning('GitHub %s %s → %s, просит подождать %s с — ждём и повторяем', method, url,
                                resp.status_code, pause)
                    self._sleep(max(1, pause))
                    attempt -= 1
                    continue
                err = self._error(method, url, resp)
                if resp.status_code < 500:
                    raise err
            if attempt >= attempts:
                raise err
            self._sleep(0.5)

    @staticmethod
    def _message(resp: httpx.Response) -> str:
        try:
            return str(resp.json().get('message') or '')[:200]
        except (ValueError, AttributeError):
            return ''

    @classmethod
    def _error(cls, method: str, url: str, resp: httpx.Response) -> StoreError:
        code = resp.status_code
        gh_msg = cls._message(resp)
        log.warning('GitHub %s %s → %s %s', method, url, code, gh_msg)
        limited = resp.headers.get('x-ratelimit-remaining') == '0' or 'rate limit' in gh_msg.lower()
        if code == 401:
            return StoreError(MSG_TOKEN, 502)
        if code in (403, 429) and (limited or code == 429 or resp.headers.get('retry-after')):
            return StoreError(MSG_RATE, 503)
        if code == 403:
            return StoreError(MSG_RIGHTS, 502)
        if code == 404:
            return StoreError(MSG_NOREPO, 502)
        if code >= 500:
            return StoreError(MSG_DOWN, 503)
        return StoreError(f'GitHub ответил ошибкой ({code}). Попробуйте ещё раз.', 502)

    # ——— чтение ———
    def head(self, fresh: bool = False) -> str:
        """sha головы ветки. Кэш на head_ttl секунд; fresh — только то, что GitHub ответил уже после вызова.
        Запрос к GitHub один на всех: 40 миниатюр списка, пришедшие разом, ждут один ответ, а не шлют 40 запросов.
        Если GitHub не ответил, обычное чтение (не fresh) получает последнюю известную голову — список товаров
        и фото из кэша продолжают открываться; запись всегда спрашивает GitHub заново."""
        asked = time.monotonic()
        with self._head_lock:
            h = self._head
            if not fresh and h and asked - h[2] < self._head_ttl:
                return h[0]
        with self._head_fetch:
            with self._head_lock:
                h, err = self._head, self._head_err
            # пока ждали, сосед уже принёс голову: для fresh — если его запрос начался после нашего вызова,
            # для обычного чтения — если ответ пришёл после нашего вызова (или кэш ещё не устарел)
            if h and (h[1] >= asked or (not fresh and (h[2] >= asked or time.monotonic() - h[2] < self._head_ttl))):
                return h[0]
            if err and err[1] >= asked:                  # сосед только что спрашивал — GitHub не ответил
                if not fresh and h:
                    return h[0]
                raise err[0]
            started = time.monotonic()
            try:
                resp = self._request('GET', f'{self._r}/git/ref/heads/{quote(self.branch, safe="/")}')
                sha = resp.json()['object']['sha']
            except StoreError as ex:
                with self._head_lock:
                    self._head_err = (ex, time.monotonic())
                if not fresh and h:
                    log.warning('голова ветки — из кэша: GitHub не ответил (%s)', ex.message)
                    return h[0]
                raise
            with self._head_lock:
                self._head, self._head_err = (sha, started, time.monotonic()), None
            return sha

    def _commit_tree(self, commit: str) -> str:
        tree_sha = self._commit_trees.get(commit)
        if tree_sha is None:
            tree_sha = self._request('GET', f'{self._r}/git/commits/{commit}').json()['tree']['sha']
            self._commit_trees.put(commit, tree_sha)
        return tree_sha

    def _tree(self, commit: str) -> dict[str, str]:
        tree = self._trees.get(commit)
        if tree is None:
            data = self._request('GET', f'{self._r}/git/trees/{self._commit_tree(commit)}',
                                 params={'recursive': '1'}).json()
            if data.get('truncated'):
                raise StoreError('GitHub отдал список файлов не целиком — сообщите Даулету.', 502)
            tree = {e['path']: e['sha'] for e in data.get('tree', []) if e.get('type') == 'blob'}
            self._trees.put(commit, tree)
        return tree

    def _fetch_blob(self, sha: str) -> bytes:
        data = self._request('GET', f'{self._r}/git/blobs/{sha}').json()
        if data.get('encoding') == 'base64':
            return base64.b64decode(data.get('content') or '')
        return str(data.get('content') or '').encode('utf-8')

    def read_blobs(self, shas: list[str]) -> dict[str, bytes]:
        """Несколько файлов сразу: недостающие в кэше качаются параллельно (49 товаров — около секунды)."""
        out: dict[str, bytes] = {}
        missing = []
        for s in dict.fromkeys(shas):
            data = self._blobs.get(s)
            if data is None:
                missing.append(s)
            else:
                out[s] = data
        if len(missing) == 1:
            fetched = [self._fetch_blob(missing[0])]
        elif missing:
            with ThreadPoolExecutor(max_workers=min(self._workers, len(missing))) as pool:
                fetched = list(pool.map(self._fetch_blob, missing))
        else:
            fetched = []
        for s, data in zip(missing, fetched):
            self._blobs.put(s, data, len(data))
            out[s] = data
        return out

    # ——— запись ———
    def _create_blob(self, data: bytes) -> str:
        resp = self._request('POST', f'{self._r}/git/blobs', ok=(201,), retry=True, rate_retry=True,
                             json={'content': base64.b64encode(data).decode('ascii'), 'encoding': 'base64'})
        return resp.json()['sha']

    def _landed(self, commit: str) -> bool:
        """Ответ на запись ветки не дошёл (таймаут, обрыв, 5xx, перезапуск при деплое), но GitHub мог её применить:
        перечитываем ветку. Указывает на наш коммит — значит, сохранено."""
        for _ in range(2):
            self._sleep(1.0)
            try:
                if self.head(fresh=True) == commit:
                    return True
            except StoreError:
                pass
        return False

    def _done(self, commit: str, tree: str, message: str) -> tuple[str, bool]:
        self._commit_trees.put(commit, tree)
        now = time.monotonic()
        with self._head_lock:
            self._head, self._head_err = (commit, now, now), None
        self._status = None
        log.info('коммит %s: %s', commit[:10], message)
        return commit, True

    def _commit(self, changes, message, author, expect):
        # Фото — отдельными blobs, заранее (от головы ветки они не зависят) и по одному: GitHub просит создавать
        # объекты последовательно, иначе срабатывает вторичный лимит. JSON — прямо в запросе дерева (`content`).
        local = {p: (bytes(v), git_blob_sha(bytes(v))) for p, v in changes.items() if v is not None}
        blob_sha: dict[str, str] = {}
        for p in (p for p in local if not p.endswith('.json')):
            sha = self._create_blob(local[p][0])
            if sha != local[p][1]:
                log.warning('GitHub вернул для %s другой sha blob: %s', p, sha)
            blob_sha[p] = sha
        ref_url = f'{self._r}/git/refs/heads/{quote(self.branch, safe="/")}'
        head = None
        for attempt in range(3):
            head = head or self.head(fresh=True)
            tree = self._tree(head)
            _check_expect(tree, expect)
            entries = []
            for path, value in changes.items():
                if value is None:
                    if path in tree:
                        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None})
                    continue
                data, sha = local[path]
                if tree.get(path) == sha:
                    continue                                 # содержимое то же — не трогаем
                entry = {'path': path, 'mode': '100644', 'type': 'blob'}
                if path in blob_sha:
                    entry['sha'] = blob_sha[path]
                else:
                    entry['content'] = data.decode('utf-8')
                entries.append(entry)
            if not entries:
                return head, False
            new_tree = self._request('POST', f'{self._r}/git/trees', ok=(201,), retry=True,
                                     json={'base_tree': self._commit_tree(head), 'tree': entries}).json()['sha']
            new_commit = self._request('POST', f'{self._r}/git/commits', ok=(201,), retry=True, json={
                'message': message, 'tree': new_tree, 'parents': [head],
                'author': {'name': author, 'email': AUTHOR_EMAIL}}).json()['sha']
            try:
                resp = self._request('PATCH', ref_url, allow=(409, 422), json={'sha': new_commit, 'force': False})
            except StoreError as ex:
                if ex.status in (503, 504) and self._landed(new_commit):
                    log.warning('GitHub не ответил на запись ветки, но коммит %s уже в ветке — сохранено',
                                new_commit[:10])
                    return self._done(new_commit, new_tree, message)
                raise
            if resp.status_code == 200:
                return self._done(new_commit, new_tree, message)
            # 409/422: обычно ветка ушла вперёд (кто-то записал раньше) — тогда повторяем поверх новой головы.
            # Если голова та же, это не гонка (защита ветки, правило репозитория…): повтор не поможет.
            gh_msg = self._message(resp)
            now = self.head(fresh=True)
            if now == head:
                log.error('GitHub не принял запись ветки %s (%s): %s', self.branch, resp.status_code, gh_msg)
                raise StoreError(MSG_REFUSED, 502)
            log.info('ветка %s ушла вперёд (%s) — повтор %d', self.branch, resp.status_code, attempt + 1)
            head = now
            self._sleep(0.5 * (attempt + 1))
        raise StoreError(MSG_BUSY, 503)

    # ——— статус публикации (GitHub Actions) ———
    @staticmethod
    def _run_state(run: dict) -> str:
        status, conclusion = run.get('status'), run.get('conclusion')
        if status == 'completed':
            return 'done' if conclusion == 'success' else 'failed'
        if status == 'in_progress':
            return 'building'
        return 'queued'          # queued, requested, waiting, pending

    def publish_status(self) -> dict:
        now = time.monotonic()
        if self._status and now - self._status[1] < self._status_ttl:
            return dict(self._status[0])
        target = self.last_commit
        out = {'state': 'unknown', 'commit': target, 'url': None, 'started': None, 'finished': None}
        try:
            runs = self._request('GET', f'{self._r}/actions/runs',
                                 params={'branch': self.branch, 'per_page': '5'}).json().get('workflow_runs') or []
        except StoreError as ex:
            log.warning('статус публикации недоступен: %s', ex.message)
            return out
        runs.sort(key=lambda r: str(r.get('created_at') or ''), reverse=True)
        run = None
        # сайт собирает workflow «pages» (.github/workflows/pages.yml); прочие прогоны — запасной вариант
        runs.sort(key=lambda r: 'pages' not in f"{r.get('name') or ''} {r.get('path') or ''}".lower())
        if target:
            run = next((r for r in runs if r.get('head_sha') == target), None)
            if run is None:
                # Actions ещё не завёл прогон (обычно несколько секунд после коммита)
                fresh = self.last_commit_at and time.time() - self.last_commit_at < 600
                out['state'] = 'queued' if fresh else 'unknown'
            elif run.get('status') == 'completed' and run.get('conclusion') in ('cancelled', 'skipped'):
                newer = [r for r in runs if str(r.get('created_at') or '') > str(run.get('created_at') or '')]
                if newer:          # прогон отменён, потому что за ним пришёл более новый — смотрим на новый
                    run = newer[0]
        elif runs:
            run = max(runs, key=lambda r: ('pages' in f"{r.get('name') or ''} {r.get('path') or ''}".lower(),
                                           str(r.get('created_at') or '')))
        if run is not None:
            done = run.get('status') == 'completed'
            out.update(state=self._run_state(run), commit=run.get('head_sha') or target, url=run.get('html_url'),
                       started=run.get('run_started_at') or run.get('created_at'),
                       finished=run.get('updated_at') if done else None)
        self._status = (dict(out), now)
        return out
