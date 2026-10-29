// Полоса публикации под шапкой: «Всё сохранённое — уже на сайте ✓» / «Публикуем на сайт…» /
// «Сайт не обновился. Ваши изменения сохранены — повторять не нужно. Сообщите Даулету».
// «Всё сохранённое», а не «все изменения»: внизу формы в это время может быть «Есть несохранённые изменения».
// Опрашиваем /api/status раз в 5 секунд, пока идёт публикация (и после каждого сохранения), иначе — при возврате на вкладку.

import { api } from './api.js';
import { h, icon } from './dom.js';
import { I } from './icons.js';
import { sameCommit } from './util.js';

export const FAILED = 'Сайт не обновился. Ваши изменения сохранены — повторять не нужно. Сообщите Даулету.';
const FAILED_REST = 'Ваши изменения сохранены — повторять не нужно. Сообщите Даулету.';
const BUSY = new Set(['queued', 'building']);
const POLL = 5000;
const GIVE_UP = 20 * 60 * 1000;   // публикация обычно 2–3 минуты; через 20 — перестаём ждать

let last = null;          // ответ сервера: {state, commit, url, started, finished, head, site_url}
let waiting = null;       // {commit, since} — наше последнее сохранение, ждём его на сайте
let timer = null;
let bar = null;
let running = false;
const subs = new Set();

/** Состояние публикации конкретного сохранения: 'busy' | 'done' | 'failed' | 'unknown'. */
export function stateOf(commit, since) {
  if (!last) return 'busy';
  const s = last.state;
  if (s === 'unknown') return 'unknown';
  const mine = sameCommit(last.commit, commit);
  const later = last.started && Date.parse(last.started) >= since - 2000;   // сборка началась после сохранения — оно в ней есть
  if (mine || later) {
    if (s === 'done' || s === 'idle') return 'done';
    if (s === 'failed') return 'failed';
  }
  if (Date.now() - since > GIVE_UP) return s === 'failed' ? 'failed' : 'done';
  return 'busy';
}

function current() {
  if (!last) return 'hidden';
  if (waiting) {
    const s = stateOf(waiting.commit, waiting.since);
    if (s !== 'busy') waiting = null;
    if (s === 'unknown') return 'hidden';
    return s;
  }
  if (last.state === 'unknown') return 'hidden';
  if (BUSY.has(last.state)) return 'busy';
  if (last.state === 'failed') return 'failed';
  return 'done';
}

function render() {
  const st = current();
  if (bar) {
    bar.dataset.state = st;
    bar.hidden = st === 'hidden';
    // значок — в строке с текстом: при переносе на две строки он не висит отдельно у левого края
    const line = st === 'busy'
      ? [h('span', { class: 'spin', 'aria-hidden': 'true' }), ' Публикуем на сайт… ', h('span', { class: 'pub__soft' }, 'обычно 2–3 минуты')]
      : st === 'failed'
        ? [icon(I.alert), ' ', h('b', null, 'Сайт не обновился.'), ` ${FAILED_REST}`]
        : ['Всё сохранённое — уже на сайте ', icon(I.check)];
    bar.replaceChildren(h('p', { class: 'pub__in' }, line));
  }
  for (const fn of subs) fn(st);
  return st;
}

function schedule(st) {
  clearTimeout(timer);
  timer = null;
  if (!running || document.hidden) return;
  if (st === 'busy') timer = setTimeout(refresh, POLL);
}

export async function refresh() {
  clearTimeout(timer);
  if (!running) return;
  try {
    const r = await api('/api/status');
    const p = (r && r.publish) || {};
    last = { state: p.state || 'unknown', commit: p.commit || null, url: p.url || null,
      started: p.started || null, finished: p.finished || null, head: r.head || null, site_url: r.site_url || '' };
  } catch (e) {
    if (e && e.status === 401) return;   // окно входа покажет api.js
    // нет связи — оставляем прошлое состояние и пробуем ещё раз
    if (running) timer = setTimeout(refresh, POLL * 2);
    return;
  }
  schedule(render());
}

/** После сохранения: сразу показываем «публикуем» и следим, пока коммит не окажется на сайте. */
export function expect(commit) {
  waiting = { commit, since: Date.now() };
  if (!last || last.state !== 'unknown') last = { ...(last || {}), state: 'queued' };
  schedule(render());
  clearTimeout(timer);
  timer = setTimeout(refresh, 2000);
}

/** Отслеживается ли публикация (в STORE=local — нет: сохраняем, но на сайт ничего не уходит). */
export function tracked() {
  return !last || last.state !== 'unknown';
}

export function onChange(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function attach(el) {
  bar = el;
  running = true;
  render();
  refresh();
}

export function stop() {
  running = false;
  clearTimeout(timer);
  bar = null;
  waiting = null;
}

document.addEventListener('visibilitychange', () => {
  if (!running) return;
  if (document.hidden) clearTimeout(timer);
  else refresh();
});
