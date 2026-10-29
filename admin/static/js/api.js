// Запросы к серверу админки. Все изменяющие — JSON и с заголовком X-Requested-With: attre-admin (защита от CSRF).
// Ошибки сервера приходят как {"error": "понятный текст", "field"?: "..."} — показываем текст как есть.

const MARK = { 'X-Requested-With': 'attre-admin' };

export class ApiError extends Error {
  constructor(status, message, field = null, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.field = field;
    this.data = data;
  }
}

let authLost = null;
/** Что делать, если сессия кончилась посреди работы (показать вход поверх экрана). */
export function onAuthLost(fn) {
  authLost = fn;
}

/** Показать вход поверх экрана самим — для запросов с auth: false, которым сначала нужно закрыть своё окно. */
export function reportAuthLost(err) {
  if (authLost) authLost(err);
}

// Запрос, ответ на который выдаст этому устройству новый вход (смена пароля). Пока он идёт, ответ 401 на другой
// запрос мог прийти со старой cookie — окно входа сначала дождётся его (app.js → showRelogin).
let renewing = null;
export function whileRenewing(promise) {
  const settled = promise.then(() => {}, () => {});
  renewing = settled;
  settled.then(() => {
    if (renewing === settled) renewing = null;
  });
  return promise;
}
/** → Promise, который выполнится, когда такого запроса нет (или он закончился). */
export function renewed() {
  return renewing || Promise.resolve();
}

/** Текст ошибки для человека: ответ сервера — как есть, сбой в самой странице — общими словами (подробности — в консоль). */
export function humane(e) {
  if (e instanceof ApiError) return e.message;
  console.error(e);
  return 'На странице что-то сломалось. Обновите её — если не поможет, сообщите Даулету.';
}

export const OFFLINE = 'Нет связи с интернетом. Проверьте подключение и попробуйте ещё раз.';

function fallback(status) {
  if (status === 400 || status === 422) return 'Проверьте, всё ли заполнено правильно.';
  if (status === 401) return 'Нужно войти заново.';
  if (status === 403) return 'Сервер отклонил запрос. Обновите страницу и попробуйте ещё раз.';
  if (status === 404) return 'Не нашли — возможно, это уже удалили.';
  if (status === 409) return 'Пока вы работали, это уже изменили в другом месте.';
  if (status === 413) return 'Слишком большой файл.';
  if (status === 429) return 'Слишком много попыток. Подождите немного и попробуйте снова.';
  if (status >= 500) return 'Сервер сейчас не отвечает как надо. Попробуйте ещё раз через минуту. Если не получится — сообщите Даулету.';
  return 'Что-то пошло не так. Попробуйте ещё раз.';
}

function errorFrom(status, data) {
  let msg = null;
  if (data && typeof data.error === 'string' && data.error.trim()) msg = data.error.trim();
  else if (data && typeof data.detail === 'string' && /[а-яё]/i.test(data.detail)) msg = data.detail;
  return new ApiError(status, msg || fallback(status), (data && typeof data.field === 'string' && data.field) || null, data);
}

function parse(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * api('/api/products') — GET; api(path, {method: 'PUT', body}) — JSON.
 * auth: false — не показывать окно входа при 401 (для самого входа и проверки сессии).
 */
export async function api(path, { method = 'GET', body, signal, auth = true } = {}) {
  const opts = { method, credentials: 'same-origin', headers: { Accept: 'application/json', ...MARK }, signal, cache: 'no-store' };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new ApiError(0, OFFLINE);
  }
  const data = parse(await res.text().catch(() => ''));
  if (res.ok) return data ?? {};
  const err = errorFrom(res.status, data);
  if (res.status === 401 && auth && authLost) authLost(err);
  throw err;
}

/**
 * Загрузка одного фото с процентами (fetch не умеет показывать ход отправки — XMLHttpRequest умеет).
 * Возвращает {promise, abort}; promise → {upload, thumb, width, height}.
 */
export function uploadFile(file, { onProgress } = {}) {
  const xhr = new XMLHttpRequest();
  const promise = new Promise((resolve, reject) => {
    xhr.open('POST', '/api/uploads');
    xhr.setRequestHeader('X-Requested-With', MARK['X-Requested-With']);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.timeout = 5 * 60 * 1000;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      const data = parse(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300 && data && data.upload) return resolve(data);
      const err = errorFrom(xhr.status, data);
      if (xhr.status === 413 && !(data && data.error)) err.message = 'Файл слишком большой — выберите фото поменьше.';
      if (xhr.status === 401 && authLost) authLost(err);
      reject(err);
    };
    xhr.onerror = () => reject(new ApiError(0, 'Не получилось отправить фото — нет связи. Нажмите «Повторить».'));
    xhr.ontimeout = () => reject(new ApiError(0, 'Фото отправлялось слишком долго. Проверьте интернет и нажмите «Повторить».'));
    xhr.onabort = () => {
      const e = new Error('отменено');
      e.name = 'AbortError';
      reject(e);
    };
    const fd = new FormData();
    fd.append('file', file, file.name || 'photo.jpg');
    xhr.send(fd);
  });
  return { promise, abort: () => xhr.abort() };
}
