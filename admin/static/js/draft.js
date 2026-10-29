// Черновик формы на этом устройстве (localStorage). Safari на iPhone не спрашивает «Уйти со страницы?»: введённое,
// но не сохранённое пропало бы, если закрыть вкладку, случайно потянуть страницу вниз (обновление) или если Safari
// сам перезагрузит вкладку после «Камеры» или «Фото». Поэтому каждое изменение кладём в черновик, а при открытии
// товара (или «Магазина и доставки») предлагаем: «Есть несохранённый черновик от 14:32 — Восстановить / Удалить».
// Новые фото в черновике — по номеру загрузки: на сервере они живут сутки, поэтому и черновик живёт сутки.

import { h, icon } from './dom.js';
import { I } from './icons.js';

const PREFIX = 'attre-admin-draft:';
export const DRAFT_TTL = 24 * 3600 * 1000;

function ls() {
  try {
    return window.localStorage;
  } catch {
    return null;   // приватный режим, запрет сайта на хранение данных
  }
}

/** Черновик по ключу (адрес товара, «new», «settings») или null; устаревший — удаляется. */
export function readDraft(key) {
  const s = ls();
  if (!s) return null;
  let d = null;
  try {
    d = JSON.parse(s.getItem(PREFIX + key) || 'null');
  } catch {
    d = null;
  }
  if (!d || typeof d !== 'object' || typeof d.at !== 'number' || !d.form || typeof d.form !== 'object' || Date.now() - d.at > DRAFT_TTL) {
    dropDraft(key);
    return null;
  }
  return d;
}

/** Записать черновик: {form, sha?, …}. at — когда сделан (по умолчанию — сейчас). */
export function writeDraft(key, data, at = Date.now()) {
  const s = ls();
  if (!s) return;
  try {
    s.setItem(PREFIX + key, JSON.stringify({ ...data, at }));
  } catch {
    // место кончилось — без черновика, форма работает как раньше
  }
}

export function dropDraft(key) {
  const s = ls();
  if (!s) return;
  try {
    s.removeItem(PREFIX + key);
  } catch {
    // нечего делать
  }
}

/** Убрать черновики старше суток (вызывается при старте админки). */
export function cleanupDrafts() {
  const s = ls();
  if (!s) return;
  try {
    const keys = [];
    for (let i = 0; i < s.length; i++) {
      const k = s.key(i);
      if (k && k.startsWith(PREFIX)) keys.push(k.slice(PREFIX.length));
    }
    for (const k of keys) readDraft(k);
  } catch {
    // нечего делать
  }
}

/** «14:32», «вчера в 14:32». */
export function draftTime(at) {
  const d = new Date(at);
  const hm = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  const today = new Date();
  return d.toDateString() === today.toDateString() ? hm : `вчера в ${hm}`;
}

/**
 * Полоса «Есть несохранённый черновик от 14:32 — [Восстановить] [Удалить черновик]».
 * note — дополнительная строка (например, «товар с тех пор сохраняли ещё раз»).
 */
export function draftBar({ at, what = 'черновик', note = '', onRestore, onDrop }) {
  const el = h('div', { class: 'draft', role: 'status' },
    icon(I.info),
    h('div', { class: 'draft__in' },
      h('p', null, h('b', null, `Есть несохранённый ${what} от ${draftTime(at)}.`), ' Вы что-то ввели и не сохранили — например, закрылась вкладка.'),
      note && h('p', { class: 'draft__note' }, note),
      h('p', { class: 'draft__btns' },
        h('button', { type: 'button', class: 'btn btn--ink draft__ok', onclick: () => onRestore() }, 'Восстановить'),
        h('button', { type: 'button', class: 'btn btn--line draft__no', onclick: () => onDrop() }, 'Удалить черновик'))));
  return el;
}
