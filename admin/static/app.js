// Админка attré — вход в приложение. Без сборщиков: ES-модули из ./js/.
// Порядок: есть ли вход (/api/session) → справочники (/api/meta) → шапка и полоса публикации → экран по адресу.

import { api, onAuthLost, humane } from './js/api.js';
import { h, icon } from './js/dom.js';
import { I } from './js/icons.js';
import { mountLogin } from './js/login.js';
import { loadMeta, getMeta, usersFrom } from './js/meta.js';
import { setRenderer, interceptLinks, parse, canLeave, replaceUrl } from './js/router.js';
import { cleanupDrafts } from './js/draft.js';
import { mountShell } from './js/shell.js';
import * as status from './js/status.js';
import { toast, clearToasts, onScreen, placeToasts } from './js/ui.js';
import { store } from './js/util.js';
import { mountList } from './js/list.js';
import { mountEditor } from './js/editor.js';
import { mountSettings } from './js/settings.js';

const app = document.getElementById('app');
let shell = null;
let view = null;
let user = null;
let users = [];
let relogin = false;

// Отметка «входили на этом устройстве» (не секрет: сама сессия — в cookie, её странице не видно). Без отметки
// сразу показываем вход и не спрашиваем сервер о сессии — так в консоли нет лишней ошибки 401 при первом открытии.
const SIGNED = 'attre-admin-signed-in';
let lastPub = null;

async function boot() {
  if (store(SIGNED) !== '1') {
    users = await usersFromMeta();
    return showLogin('');
  }
  try {
    const s = await api('/api/session', { auth: false });
    user = (s && s.user) || 'Админ';
  } catch (e) {
    if (e.status === 401) {
      store(SIGNED, null);
      users = usersFrom(e.data && e.data.users);
      if (!users.length) users = await usersFromMeta();
      return showLogin('');
    }
    return fatal(e);
  }
  start();
}

/** Имена для экрана входа: из ответа /api/session; если там нет — GET /api/login, затем /api/meta. */
async function usersFromMeta() {
  for (const path of ['/api/login', '/api/meta']) {
    try {
      const list = usersFrom((await api(path, { auth: false })).users);
      if (list.length) return list;
    } catch {
      // нет такого адреса или нужен вход — пробуем следующий
    }
  }
  return [];
}

function showLogin(message) {
  shell = null;
  document.title = 'Вход — attré · админка';
  mountLogin(app, {
    users, message,
    onDone: (u) => {
      user = u;
      store(SIGNED, '1');
      start();
    },
  });
}

async function start() {
  try {
    await loadMeta();
  } catch (e) {
    if (e.status === 401) return showLogin('');
    return fatal(e);
  }
  const meta = getMeta();
  if (meta.users.length) users = meta.users;
  shell = mountShell(app, { user, siteUrl: meta.site, onLogout: logout });
  status.attach(shell.pub);
  render();
}

// Публикация закончилась, пока человек работает, — короткое сообщение, но только если ни полосы под шапкой,
// ни сообщения вверху товара сейчас не видно (на телефоне они уезжают при прокрутке): одно и то же трижды не нужно
status.onChange((st) => {
  const seen = () => onScreen(document.querySelector('.pub')) || onScreen(document.querySelector('.notice:not([hidden])'));
  if (lastPub === 'busy' && st === 'done' && !seen()) toast('Готово — изменения уже на сайте.', { kind: 'ok' });
  if (lastPub === 'busy' && st === 'failed' && !seen()) toast(status.FAILED, { kind: 'err', timeout: 12000 });
  lastPub = st;
});

function render() {
  if (!shell) return;
  if (view && view.destroy) view.destroy();
  view = null;
  let r = parse();
  if (r.name === 'unknown') {
    replaceUrl('/');
    r = parse('/');
  }
  shell.setTab(r.name === 'settings' ? 'settings' : 'list');
  window.scrollTo(0, 0);
  if (r.name === 'list') view = mountList(shell.main);
  else if (r.name === 'editor') view = mountEditor(shell.main, { slug: r.slug });
  else view = mountSettings(shell.main);
  placeToasts();
  updateTitle();
}

function updateTitle() {
  const t = view && view.title ? view.title() : '';
  document.title = t ? `${t} — attré · админка` : 'attré · админка';
}

async function logout() {
  if (!(await canLeave())) return;
  store(SIGNED, null);
  try {
    await api('/api/logout', { method: 'POST', body: {}, auth: false });
  } catch {
    // выходим в любом случае: экран входа покажется, а сессия кончится сама
  }
  if (view && view.destroy) view.destroy();
  view = null;
  status.stop();
  showLogin('Вы вышли из админки.');
}

/** Вход истёк посреди работы: окно входа поверх экрана, всё введённое остаётся на месте. */
function showRelogin() {
  if (relogin || !shell) {
    if (!shell && !relogin) showLogin('');
    return;
  }
  relogin = true;
  clearToasts();
  const layer = h('div', { class: 'relogin', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Вход' });
  document.body.append(layer);
  document.documentElement.classList.add('is-locked');
  mountLogin(layer, {
    users, overlay: true,
    message: 'Вход истёк — войдите снова. Всё, что вы ввели, останется на экране.',
    onDone: (u) => {
      user = u;
      store(SIGNED, '1');
      relogin = false;
      layer.remove();
      document.documentElement.classList.remove('is-locked');
      if (shell) shell.setUser(u);
      status.refresh();
      // экран не загрузился из-за истёкшего входа (а не форма с правками) — просто открываем его заново
      if (shell && shell.main.querySelector('.state:not(.state--load)') && !shell.main.querySelector('form')) render();
      else toast('Вы снова вошли. Повторите последнее действие.', { kind: 'ok' });
    },
  });
}

function fatal(e) {
  document.title = 'attré · админка';
  app.classList.remove('boot');
  app.removeAttribute('aria-busy');
  app.replaceChildren(h('div', { class: 'state state--page' },
    icon(I.alert),
    h('h1', { class: 'state__t' }, 'Админка не открылась'),
    h('p', { class: 'state__p' }, humane(e)),
    h('div', { class: 'state__btns' }, h('button', { type: 'button', class: 'btn btn--ink', onclick: () => location.reload() }, 'Обновить страницу'))));
}

// Заголовок вкладки — по названию товара, когда оно загрузилось или поменялось
document.addEventListener('input', () => updateTitle());
setInterval(updateTitle, 1500);

setRenderer(render);
interceptLinks(document);
onAuthLost(showRelogin);
cleanupDrafts();
boot();
