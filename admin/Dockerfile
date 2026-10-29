# Админка attré — образ для Railway (корень сервиса — папка admin/, см. README.md).
#   docker build -t attre-admin .                                    # из папки admin/
#   docker run --rm -p 8000:8000 --env-file .env attre-admin          # STORE=github; значения в .env — без кавычек
# В образе нет git: он нужен только режиму STORE=local, а его запускают без Docker.
# Базовый образ закреплён версией и digest: пересборка (каждый push в admin/**) берёт ровно тот Python,
# на котором прогнаны тесты. Обновить — README → «Зависимости».
FROM python:3.12.16-slim@sha256:8523d6abeb48ceae0b7240d30c5808fc26cb79c1a635bacdf19cf3baecfbec07

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Зависимости — отдельным слоем: заново ставятся, только когда меняется requirements.lock
# (в нём закреплено всё, вместе с зависимостями зависимостей)
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Код и фронт принадлежат root: пользователю приложения — только чтение.
# Писать он может лишь во временную папку (TMP_DIR, по умолчанию /tmp/attre-admin) и в свой домашний каталог.
COPY app/ ./app/
COPY static/ ./static/

RUN useradd --uid 10001 --user-group --create-home --shell /usr/sbin/nologin attre
USER attre

EXPOSE 8000

# Ровно один процесс uvicorn: очередь записи в репозиторий и счётчик попыток входа живут в памяти.
# PORT задаёт Railway (локально — 8000). exec — чтобы сигнал остановки получал сам uvicorn, а не оболочка.
# --timeout-graceful-shutdown 50: при деплое начатое сохранение успевает дойти до GitHub (Railway ждёт
#   RAILWAY_DEPLOYMENT_DRAINING_SECONDS=60, см. README); --no-server-header — не сообщаем, на чём работает сервер.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --no-server-header --timeout-graceful-shutdown 50"]
