// Адреса в браузере (History API): /, /product/<адрес товара>, /product/new, /settings.
// Перед уходом со страницы с несохранёнными изменениями спрашиваем — и по ссылкам, и по кнопке «назад»,
// и при закрытии вкладки (там браузер показывает своё окно). Safari на iPhone при закрытии вкладки и при
// перезагрузке не спрашивает — на этот случай введённое лежит в черновике (draft.js).

import { confirmLeave } from './ui.js';

let renderer = () => {};
let guard = null;      // {dirty: () => boolean, ask?: () => Promise<boolean>, discard?: () => void}
let shown = location.pathname + location.search;

export function setRenderer(fn) {
  renderer = fn;
}

export function setLeaveGuard(g) {
  guard = g;
}

export function clearLeaveGuard(g) {
  if (!g || guard === g) guard = null;
}

/** Есть ли на экране несохранённые правки (без вопросов человеку). */
export function hasUnsaved() {
  return !!(guard && guard.dirty());
}

/** Можно ли уйти с текущего экрана: если есть несохранённое — спросить. Согласились потерять правки —
 *  guard.discard() (убрать черновик: человек сам решил, что правки не нужны). */
export async function canLeave() {
  if (!guard || !guard.dirty()) return true;
  const g = guard;
  const ok = await (g.ask ? g.ask() : confirmLeave());
  if (ok) {
    if (g.discard) g.discard();
    if (guard === g) guard = null;
  }
  return ok;
}

export function parse(path = location.pathname) {
  const p = path.replace(/\/+$/, '') || '/';
  if (p === '/') return { name: 'list' };
  if (p === '/settings') return { name: 'settings' };
  if (p === '/product/new') return { name: 'editor', slug: null };
  const m = /^\/product\/([a-z0-9][a-z0-9_-]*)$/.exec(p);
  if (m) return { name: 'editor', slug: m[1] };
  return { name: 'unknown' };
}

export async function go(path, { replace = false } = {}) {
  if (!(await canLeave())) return false;
  const same = path === location.pathname + location.search;   // та же страница — обновить, но не плодить историю
  history[replace || same ? 'replaceState' : 'pushState'](null, '', path);
  shown = location.pathname + location.search;
  renderer();
  return true;
}

/** Поменять адрес без перерисовки (новый товар после сохранения получил свой адрес). */
export function replaceUrl(path) {
  history.replaceState(null, '', path);
  shown = location.pathname + location.search;
}

window.addEventListener('popstate', async () => {
  const target = location.pathname + location.search;
  if (guard && guard.dirty()) {
    history.pushState(null, '', shown);   // остаёмся на месте, пока человек решает
    if (!(await canLeave())) return;
    history.replaceState(null, '', target);
  }
  shown = location.pathname + location.search;
  renderer();
});

window.addEventListener('beforeunload', (e) => {
  if (!guard || !guard.dirty()) return;
  e.preventDefault();
  e.returnValue = '';
});

/** Ссылки с data-link открываются внутри админки, без перезагрузки страницы. */
export function interceptLinks(root = document) {
  root.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a[data-link]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    go(a.getAttribute('href'));
  });
}
