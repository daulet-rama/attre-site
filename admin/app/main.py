"""Админка attré: FastAPI — API (DESIGN.md → «API») и фронт из admin/static/.

Запуск: `uvicorn app.main:app` из папки admin/ (переменные окружения — DESIGN.md, config.py).
`app` создаётся при первом обращении (см. __getattr__ внизу): тесты импортируют create_app без переменных окружения.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Any

import anyio.to_thread
from fastapi import Body, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders, UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import cookie_parser

from .auth import CHANGED, COOKIE, Auth, NeedName, client_ip, is_local_host
from .catalog import MEDIA, MEDIA_NAME_RE, Catalog, CatalogError
from .config import Config, ConfigError, load_config
from .images import MAX_BYTES, PREVIEW_VERSION, ImageError, Uploads, preview, preview_width, process_upload
from .passwords import MSG_WRONG, Passwords, new_password_problem, pepper_for
from .store import MSG_DOWN, GitHubStore, LocalStore, Store, StoreError

log = logging.getLogger('attre.main')

STATIC_DIR = Path(__file__).resolve().parent.parent / 'static'
JSON_LIMIT = 1024 * 1024                       # JSON-запросы: товар, настройки, порядок — это килобайты
LOGIN_LIMIT = 4 * 1024                         # вход и смена пароля: имя и пароли
PASSWORD_API = ('/api/login', '/api/password')
UPLOAD_LIMIT = MAX_BYTES + 512 * 1024          # фото до 30 МБ + служебные байты multipart
CSRF_HEADER, CSRF_VALUE = 'x-requested-with', 'attre-admin'
OPEN_API = ('/api/health', '/api/login', '/api/logout')   # остальное /api/* — только с действующей сессией
THREADS = 64                                   # потоков для обработчиков (было 40): миниатюры списка идут пачкой
# Скрипты и запросы — только со своего адреса: даже если когда-нибудь найдётся XSS, чужой скрипт не подгрузится
# и данные никуда не уйдут. 'unsafe-inline' — только для стилей (style="…" в разметке), blob: — превью фото с телефона.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; "
       "font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; "
       "object-src 'none'")

MSG_SERVER = 'Что-то пошло не так. Попробуйте ещё раз, а если не получится — сообщите Даулету.'
MSG_BAD_REQUEST = 'Что-то не так с данными на странице. Обновите страницу и попробуйте ещё раз.'
MSG_LOGIN = 'Войдите, чтобы продолжить.'
MSG_CHANGED = 'Пароль сменили — войдите с новым паролем.'
MSG_BAD_PASSWORD = 'Пароль не подошёл. Проверьте раскладку (русская или английская) и большие буквы.'
# 429 при смене пароля. Без «неверных»: счётчик общий на адрес (одна сеть Wi-Fi на двоих) и на всех сразу
# («медленный режим») — блокировку видит и та, кто сама не ошибалась. Дальше — «. Попробуйте через N минут.»
TOO_MANY_PASSWORD = 'Слишком много неудачных попыток ввести пароль'


class RequestTooLarge(Exception):
    pass


class Unauthorized(Exception):
    pass


def _json(status: int, body: dict, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=headers)


def _login_needed(reason: str | None) -> dict:
    """Тело ответа 401. reason «password» — вход был, но пароль с тех пор сменили (на другом устройстве или сбросили):
    окно входа так и скажет, а не «вход истёк» (имена для экрана входа — только в GET /api/login)."""
    if reason == CHANGED:
        return {'error': MSG_CHANGED, 'reason': CHANGED}
    return {'error': MSG_LOGIN}


class Guard:
    """Чистый ASGI-слой: сессия у закрытых адресов /api/* (до разбора тела запроса — аноним не заставит сервер
    разбирать мегабайтный JSON), CSRF-заголовок и JSON у изменяющих запросов, предел размера запроса,
    заголовки безопасности у всех ответов (админку не встраивают в чужие страницы и не индексируют)."""

    def __init__(self, app, auth: Auth | None = None):
        self.app = app
        self.auth = auth

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path, method = scope['path'], scope['method']
        headers = Headers(scope=scope)
        api = path.startswith('/api/')
        upload = path == '/api/uploads'
        https = scope.get('scheme') == 'https'          # за прокси Railway — по X-Forwarded-Proto (uvicorn)
        started = False

        async def send_secure(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
                h = MutableHeaders(scope=message)
                h.setdefault('X-Content-Type-Options', 'nosniff')
                h.setdefault('X-Frame-Options', 'DENY')
                h.setdefault('Referrer-Policy', 'same-origin')
                h.setdefault('Content-Security-Policy', CSP)
                h.setdefault('X-Robots-Tag', 'noindex, nofollow')
                if https:            # браузер больше не пойдёт на адрес админки по http — там пароль можно подменить
                    h.setdefault('Strict-Transport-Security', 'max-age=31536000')
                if api:
                    h.setdefault('Cache-Control', 'no-store')
            await send(message)

        async def reply(status: int, body: dict):
            await JSONResponse(body, status_code=status)(scope, receive, send_secure)

        if api and self.auth is not None and path not in OPEN_API:
            cookie = cookie_parser(headers.get('cookie', '')).get(COOKIE)
            pw = self.auth.passwords
            if cookie and pw is not None and pw.needs_check():
                # сменённые пароли — не старше минуты: отпечаток в cookie сверяется с ними (чтение — в потоке)
                if not await anyio.to_thread.run_sync(pw.ensure):
                    # файл паролей после запуска ещё ни разу не прочитан (GitHub не ответил): сверить не с чем —
                    # не пускаем, как и вход паролем. Иначе снова прошли бы входы, выданные по стартовому паролю
                    # до его смены (например, с потерянного телефона, из-за которого пароль и меняли)
                    return await reply(503, {'error': pw.error.message if pw.error else MSG_DOWN})
            session, reason = self.auth.check_cookie(cookie)
            if not session:
                return await reply(401, _login_needed(reason))

        if api and method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if headers.get(CSRF_HEADER) != CSRF_VALUE:
                return await reply(403, {'error': 'Запрос отклонён. Обновите страницу и попробуйте ещё раз.'})
            ctype = headers.get('content-type', '').split(';')[0].strip().lower()
            has_body = headers.get('content-length', '0') != '0' or 'transfer-encoding' in headers
            if upload and ctype != 'multipart/form-data':
                return await reply(415, {'error': 'Фото нужно отправлять файлом. Обновите страницу.', 'field': 'file'})
            if not upload and has_body and ctype != 'application/json':
                return await reply(415, {'error': MSG_BAD_REQUEST})
        limit = UPLOAD_LIMIT if upload else LOGIN_LIMIT if path in PASSWORD_API else JSON_LIMIT
        too_big = {'error': 'Фото больше 30 МБ. Выберите фото поменьше.', 'field': 'file'} if upload else {
            'error': 'Слишком большой запрос.'}
        try:
            declared = int(headers.get('content-length') or 0)
        except ValueError:
            return await reply(400, {'error': MSG_BAD_REQUEST})
        if declared > limit:
            return await reply(413, too_big)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
                if received > limit:
                    raise RequestTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send_secure)
        except RequestTooLarge:
            if started:
                raise
            await reply(413, too_big)


def _minutes(seconds: int) -> str:
    m = max(1, (seconds + 59) // 60)
    if m % 10 == 1 and m % 100 != 11:
        word = 'минуту'
    elif m % 10 in (2, 3, 4) and m % 100 not in (12, 13, 14):
        word = 'минуты'
    else:
        word = 'минут'
    return f'{m} {word}'


def _too_many(wait: int, what: str = 'Слишком много попыток входа') -> JSONResponse:
    return _json(429, {'error': f'{what}. Попробуйте через {_minutes(wait)}.'}, headers={'Retry-After': str(wait)})


def make_store(cfg: Config) -> Store:
    if cfg.store == 'local':
        return LocalStore(cfg.local_repo)
    return GitHubStore(cfg.github_token, cfg.github_repo, cfg.github_branch)


def create_app(cfg: Config, store: Store | None = None, *, static_dir: Path | None = None,
               prewarm: bool = False, login_delay: float = 1.0) -> FastAPI:
    store = store or make_store(cfg)
    uploads = Uploads(cfg.tmp_dir)
    catalog = Catalog(store, uploads, cfg.site_url)
    passwords = Passwords(store, pepper_for(cfg.session_secret, cfg.password_pepper), list(cfg.users))
    auth = Auth(cfg.users, cfg.session_secret, fail_delay=login_delay, passwords=passwords)
    static = (static_dir or STATIC_DIR).resolve()
    # Фото обрабатываются по одному: пик памяти большого фото — до 0,5–1 ГБ (README → «Стоимость»), а само
    # фото обрабатывается около секунды — очереди из двух-трёх фото не видно.
    upload_slots = threading.BoundedSemaphore(1)
    preview_slots = threading.BoundedSemaphore(4)

    def process(data: bytes):
        with upload_slots:
            return process_upload(data)

    def ensure_preview(name: str, width: int, sha: str) -> Path:
        cached = uploads.cached_preview(sha, width)
        if cached:
            return cached
        with preview_slots:
            cached = uploads.cached_preview(sha, width)
            if cached:
                return cached
            data = store.read_blob(sha)
            return uploads.store_preview(sha, width, preview(data, width))

    def warm():
        """После старта: читаем файл сменённых паролей, проверяем доступ к хранилищу и готовим превью главных фото
        (первый заход быстрее)."""
        passwords.ensure()          # не прочитался — ensure() сам пишет в журнал; повтор — при первом запросе
        try:
            snap = store.snapshot()
            for item in catalog.products():
                if item['thumb']:
                    name = item['thumb'].split('/api/media/', 1)[1].split('?', 1)[0]
                    sha = snap.blob_sha(MEDIA + name)
                    if sha:
                        ensure_preview(name, 480, sha)
            log.info('хранилище %s доступно, превью готовы', store.kind)
        except StoreError as ex:
            log.error('хранилище недоступно: %s', ex.message)
        except Exception:   # noqa: BLE001 — фоновая подготовка не должна ронять админку
            log.exception('не получилось подготовить превью')

    @asynccontextmanager
    async def lifespan(_app):
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = max(limiter.total_tokens, THREADS)
        uploads.cleanup(force=True)
        if prewarm:
            threading.Thread(target=warm, name='attre-prewarm', daemon=True).start()
        yield
        store.close()

    app = FastAPI(title='attré admin', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.cfg, app.state.store, app.state.catalog, app.state.auth, app.state.uploads = (
        cfg, store, catalog, auth, uploads)
    app.state.passwords = passwords
    app.add_middleware(Guard, auth=auth)

    # ——— ошибки → {"error": "...", "field"?: "..."} ———
    @app.exception_handler(CatalogError)
    async def _catalog_error(_req, ex: CatalogError):
        return _json(ex.status, ex.to_json())

    @app.exception_handler(StoreError)
    async def _store_error(_req, ex: StoreError):
        return _json(ex.status, {'error': ex.message})

    @app.exception_handler(ImageError)
    async def _image_error(_req, ex: ImageError):
        return _json(400, {'error': ex.message, 'field': 'file'})

    @app.exception_handler(Unauthorized)
    async def _unauthorized(req, _ex):
        return _json(401, _login_needed(auth.check_cookie(req.cookies.get(COOKIE))[1]))

    @app.exception_handler(RequestTooLarge)
    async def _too_large(req, _ex):
        if req.url.path == '/api/uploads':
            return _json(413, {'error': 'Фото больше 30 МБ. Выберите фото поменьше.', 'field': 'file'})
        return _json(413, {'error': 'Слишком большой запрос.'})

    @app.exception_handler(RequestValidationError)
    async def _validation(_req, _ex):
        return _json(400, {'error': MSG_BAD_REQUEST})

    @app.exception_handler(StarletteHTTPException)
    async def _http(req, ex: StarletteHTTPException):
        if isinstance(ex.__cause__, RequestTooLarge):
            return await _too_large(req, ex)
        messages = {404: 'Нет такого адреса.', 405: 'Так этот адрес не работает.'}
        return _json(ex.status_code, {'error': messages.get(ex.status_code, MSG_BAD_REQUEST)})

    @app.exception_handler(Exception)
    async def _crash(_req, ex: Exception):
        log.error('ошибка сервера: %s', type(ex).__name__)
        return _json(500, {'error': MSG_SERVER})

    # ——— вход ———
    def secure(request: Request) -> bool:
        return request.url.scheme == 'https' or not is_local_host(request.url.hostname)

    def set_session(response: Response, request: Request, user: str, started: float | None = None):
        started = started or time.time()
        response.set_cookie(COOKIE, auth.make_cookie(user, started), max_age=auth.max_age(started), path='/',
                            httponly=True, samesite='lax', secure=secure(request))

    def current_user(request: Request) -> str:
        session = auth.read_cookie(request.cookies.get(COOKIE))
        if not session:
            raise Unauthorized()
        request.state.session = session
        return session[0]

    @app.get('/api/health')
    async def health():
        # async — без пула потоков: отвечает, даже если все потоки ждут медленный GitHub
        return {'ok': True}

    @app.get('/api/login')
    def login_info():
        """Для экрана входа: какие имена показать (пароли, понятно, не отдаём)."""
        return {'users': auth.names}

    async def json_body(request: Request) -> dict | None:
        try:
            payload = await request.json()
        except RequestTooLarge:
            raise
        except Exception:   # noqa: BLE001 — не JSON
            return None
        return payload if isinstance(payload, dict) else None

    def ip_of(request: Request) -> str:
        return client_ip(request.headers, request.client.host if request.client else None, cfg.trust_proxy)

    @app.post('/api/login')
    async def login(request: Request):
        # async: пауза после неверного пароля (asyncio.sleep) не занимает поток; сама проверка — в потоке
        # (у сменённого пароля это scrypt, десятки миллисекунд)
        payload = await json_body(request)
        if payload is None:
            return _json(400, {'error': MSG_BAD_REQUEST})
        ip = ip_of(request)
        wait = auth.limiter.retry_after(ip)
        if wait:
            return _too_many(wait)
        name, password = payload.get('name'), payload.get('password')
        if name is not None and not isinstance(name, str):
            return _json(400, {'error': 'Выберите своё имя.', 'field': 'name'})
        if not isinstance(password, str) or not password:
            return _json(400, {'error': 'Введите пароль.', 'field': 'password'})
        if not await run_in_threadpool(passwords.ensure):
            # файл сменённых паролей ещё ни разу не прочитался (GitHub не ответил после запуска): по старым
            # паролям из переменных не пускаем — их могли сменить как раз потому, что они кому-то известны
            return _json(503, {'error': passwords.error.message if passwords.error else MSG_DOWN})
        try:
            user, wait = await run_in_threadpool(auth.attempt, ip, name, password)
        except NeedName:
            return _json(400, {'error': 'Выберите своё имя.', 'field': 'name'})
        if wait:
            return _too_many(wait)
        if not user:
            log.info('неудачный вход с %s', ip)
            if auth.fail_delay:
                await asyncio.sleep(auth.fail_delay)
            return _json(401, {'error': MSG_BAD_PASSWORD, 'field': 'password'})
        response = _json(200, {'user': user})
        set_session(response, request, user)
        log.info('вход: %s', user)
        return response

    @app.post('/api/password')
    async def change_password(request: Request, user: str = Depends(current_user)):
        """Смена своего пароля: {current, new} → {} и новая cookie этого устройства (старые входы — недействительны)."""
        payload = await json_body(request)
        if payload is None:
            return _json(400, {'error': MSG_BAD_REQUEST})
        ip = ip_of(request)
        wait = auth.limiter.retry_after(ip)
        if wait:
            return _too_many(wait, TOO_MANY_PASSWORD)
        current, new = payload.get('current'), payload.get('new')
        if not isinstance(current, str) or not current:
            return _json(400, {'error': 'Впишите текущий пароль.', 'field': 'current'})
        problem = new_password_problem(new, user, current)
        if problem:
            return _json(400, {'error': problem, 'field': 'new'})
        result, wait = await run_in_threadpool(auth.change_password, user, current, new, ip,
                                               request.cookies.get(COOKIE))
        if result == 'wait':
            return _too_many(wait, TOO_MANY_PASSWORD)
        if result == 'stale':
            # пока шёл запрос, пароль этого человека сменили на другом устройстве (или сбросили): этот вход уже
            # не действует — окно входа, а не «текущий пароль не подошёл» и не попытка в счётчике
            return _json(401, _login_needed(CHANGED))
        if result == 'wrong':
            log.info('смена пароля: неверный текущий пароль (%s, с %s)', user, ip)
            if auth.fail_delay:
                await asyncio.sleep(auth.fail_delay)
            return _json(400, {'error': MSG_WRONG, 'field': 'current'})
        response = _json(200, {})
        set_session(response, request, user)        # это устройство остаётся в админке — уже с новым паролем
        log.info('смена пароля: %s', user)
        return response

    @app.post('/api/logout')
    def logout(request: Request):
        response = _json(200, {})
        response.delete_cookie(COOKIE, path='/', httponly=True, samesite='lax', secure=secure(request))
        return response

    @app.get('/api/session')
    def session(request: Request, user: str = Depends(current_user)):
        response = _json(200, {'user': user})
        _, issued, started = request.state.session
        if auth.needs_refresh(issued):
            set_session(response, request, user, started)   # продлеваем, но не дальше 90 дней от входа паролем
        return response

    # ——— каталог ———
    @app.get('/api/meta')
    def meta(user: str = Depends(current_user)):
        return catalog.meta(auth.names)

    @app.get('/api/products')
    def products(user: str = Depends(current_user)):
        return catalog.products()

    @app.post('/api/products/order')
    def reorder(payload: dict = Body(...), user: str = Depends(current_user)):
        return catalog.reorder(payload.get('slugs'), user)

    @app.get('/api/products/{slug}')
    def product(slug: str, user: str = Depends(current_user)):
        return catalog.product(slug)

    @app.post('/api/products')
    def create(payload: dict = Body(...), user: str = Depends(current_user)):
        return catalog.create(payload.get('product'), user)

    @app.put('/api/products/{slug}')
    def update(slug: str, payload: dict = Body(...), user: str = Depends(current_user)):
        return catalog.update(slug, payload.get('product'), payload.get('sha'), user)

    @app.delete('/api/products/{slug}')
    def delete(slug: str, sha: str | None = None, user: str = Depends(current_user)):
        return catalog.delete(slug, sha, user)

    # ——— фото ———
    @app.post('/api/uploads')
    async def upload(request: Request, user: str = Depends(current_user)):
        try:
            form = await request.form(max_files=1, max_fields=5)
        except RequestTooLarge:
            raise
        except Exception:   # noqa: BLE001 — оборванная или кривая отправка
            return _json(400, {'error': 'Фото не дошло до сервера. Попробуйте ещё раз.', 'field': 'file'})
        try:
            file = form.get('file')
            if not isinstance(file, UploadFile):
                return _json(400, {'error': 'Выберите фото.', 'field': 'file'})
            data = await file.read()
        finally:
            await form.close()
        processed = await run_in_threadpool(process, data)
        upload_id = await run_in_threadpool(uploads.save, processed)
        return {'upload': upload_id, 'thumb': f'/api/uploads/{upload_id}',
                'width': processed.width, 'height': processed.height}

    @app.get('/api/uploads/{upload_id}')
    def upload_thumb(upload_id: str, user: str = Depends(current_user)):
        path = uploads.thumb_path(upload_id)
        if path is None:
            return _json(404, {'error': 'Загрузка устарела — добавьте фото заново.'})
        return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=86400'})

    @app.get('/api/media/{file:path}')
    def media(file: str, request: Request, w: str | None = None, v: str | None = None,
              user: str = Depends(current_user)):
        name = file[len(MEDIA):] if file.startswith(MEDIA) else file
        if '/' in name or not MEDIA_NAME_RE.fullmatch(name):
            return _json(404, {'error': 'Фото не найдено.'})
        width = preview_width(w)
        sha = store.snapshot().blob_sha(MEDIA + name)
        if sha is None:
            return _json(404, {'error': 'Фото не найдено.'})
        etag = f'"{sha[:16]}-{width}-{PREVIEW_VERSION}"'
        v_sha, _, v_ver = (v or '').partition('-')     # ?v=<начало sha>-<версия нарезки>
        fresh = len(v_sha) >= 7 and sha.startswith(v_sha) and v_ver == PREVIEW_VERSION
        cache = 'private, max-age=31536000, immutable' if fresh else (
            'private, max-age=300')
        if request.headers.get('if-none-match') == etag:
            return Response(status_code=304, headers={'ETag': etag, 'Cache-Control': cache})
        try:
            path = ensure_preview(name, width, sha)
        except ImageError:
            return _json(404, {'error': 'Фото не открывается.'})
        return FileResponse(path, media_type='image/jpeg', headers={'ETag': etag, 'Cache-Control': cache})

    # ——— магазин и доставка ———
    @app.get('/api/settings')
    def get_settings(user: str = Depends(current_user)):
        return catalog.settings()

    @app.put('/api/settings')
    def put_settings(payload: dict = Body(...), user: str = Depends(current_user)):
        return catalog.save_settings(payload, user)

    # ——— публикация ———
    @app.get('/api/status')
    def status(user: str = Depends(current_user)):
        try:
            head = store.head()
        except StoreError as ex:
            return {'head': None, 'site_url': cfg.site_url, 'error': ex.message,
                    'publish': {'state': 'unknown', 'commit': store.last_commit, 'url': None, 'started': None,
                                'finished': None}}
        return {'head': head, 'publish': store.publish_status(), 'site_url': cfg.site_url}

    @app.api_route('/api/{rest:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], include_in_schema=False)
    def api_404(rest: str):
        return _json(404, {'error': 'Нет такого адреса.'})

    # ——— фронт: файлы из static/, на остальные адреса — index.html (адреса вида /product/altea) ———
    placeholder = ('<!doctype html><meta charset="utf-8"><title>attré · админка</title>'
                   '<p style="font:16px system-ui;padding:24px">Интерфейс админки ещё не установлен.</p>')

    def static_file(path: Path, request: Request, media_type: str | None = None) -> Response:
        """Файл фронта: всегда перепроверяется (no-cache), но без изменений отдаётся как 304 — быстро на телефоне."""
        st = path.stat()
        etag = '"' + hashlib.md5(f'{st.st_mtime_ns}-{st.st_size}'.encode()).hexdigest() + '"'
        headers = {'Cache-Control': 'no-cache', 'ETag': etag}
        if request.headers.get('if-none-match') == etag:
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type=media_type, headers=headers)

    @app.get('/{path:path}', include_in_schema=False)
    def front(path: str, request: Request):
        # index.html подключает /static/app.js и /static/app.css; файлы отдаём и без префикса /static/
        rel = path[len('static/'):] if path.startswith('static/') else path
        if rel:
            target = (static / rel).resolve()
            if static in target.parents and target.is_file():
                return static_file(target, request)
            if path.startswith('static/') or '.' in PurePosixPath(rel).name:
                return _json(404, {'error': 'Нет такого файла.'})   # не подменяем app.js страницей index.html
        index = static / 'index.html'
        if index.is_file():
            return static_file(index, request, 'text/html')
        return HTMLResponse(placeholder, status_code=503)

    return app


def _setup_logging():
    lg = logging.getLogger('attre')
    if not lg.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        lg.addHandler(handler)
        lg.setLevel(logging.INFO)
        lg.propagate = False


def app_from_env() -> FastAPI:
    _setup_logging()
    try:
        cfg = load_config()
        return create_app(cfg, prewarm=True)
    except (ConfigError, StoreError) as ex:
        print(str(ex), file=sys.stderr, flush=True)
        raise SystemExit(1) from None
    except OSError as ex:          # например, нет прав на TMP_DIR
        print(f'Админка не запущена: {ex}', file=sys.stderr, flush=True)
        raise SystemExit(1) from None


def __getattr__(name: str) -> Any:
    if name == 'app':
        value = app_from_env()
        globals()['app'] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


if __name__ == '__main__':
    import os

    import uvicorn

    uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.environ.get('PORT') or 8000), proxy_headers=True,
                forwarded_allow_ips='*', server_header=False, timeout_graceful_shutdown=50)
