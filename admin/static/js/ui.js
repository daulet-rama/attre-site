// Окна поверх экрана: подтверждение (dialog), нижний лист (sheet), короткие сообщения (toast).

import { h, icon } from './dom.js';
import { I } from './icons.js';

// ——— Блокировка прокрутки страницы, пока открыто окно (счётчик: окна бывают одно над другим) ———
let locks = 0;
function lock(on) {
  locks = Math.max(0, locks + (on ? 1 : -1));
  document.documentElement.classList.toggle('is-locked', locks > 0);
}

// ——— Слои: клавиши Esc и Tab обрабатывает только верхнее окно ———
const layers = [];
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

document.addEventListener('keydown', (e) => {
  const top = layers[layers.length - 1];
  if (!top) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    top.dismiss();
  } else if (e.key === 'Tab') {
    const list = Array.from(top.panel.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null);
    if (!list.length) {
      e.preventDefault();
      return;
    }
    const first = list[0], last = list[list.length - 1];
    const cur = document.activeElement;
    if (e.shiftKey && (cur === first || !top.panel.contains(cur))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (cur === last || !top.panel.contains(cur))) {
      e.preventDefault();
      first.focus();
    }
  }
}, true);

let n = 0;
const nextId = (p) => `${p}-${++n}`;

/** Убрать сообщения (все или только об ошибках): старые закрывали бы кнопки окна или говорили о том, что уже исправлено. */
export function clearToasts(kind = null) {
  if (!box) return;
  for (const el of Array.from(box.children)) if (!kind || el.classList.contains(`toast--${kind}`)) el.remove();
}

/**
 * Окно с вопросом. buttons: [{label, value, kind: 'ink'|'danger-line'|'line'|'link'}]. Возвращает value нажатой кнопки
 * или dismiss (Esc, нажатие мимо окна). Правило для всех окон: безопасное действие — чёрная кнопка сверху,
 * то, после чего что-то пропадёт, — красная рамка снизу.
 */
export function dialog({ title, text, body, buttons, dismiss = null, focus = null, cls = '' }) {
  return new Promise((resolve) => {
    const prev = document.activeElement;
    const tid = nextId('dlg');
    const did = text ? `${tid}-text` : null;
    const btnEls = buttons.map((b) =>
      h('button', { type: 'button', class: `btn btn--${b.kind || 'line'}`, onclick: () => done(b.value), 'data-v': String(b.value) }, b.label));
    const panel = h('div', { class: `dlg ${cls}`, role: 'alertdialog', 'aria-modal': 'true', 'aria-labelledby': tid, 'aria-describedby': did, tabindex: '-1' },
      h('h2', { class: 'dlg__t', id: tid }, title),
      text && h('p', { class: 'dlg__text', id: did }, text),
      body,
      h('div', { class: 'dlg__btns' }, btnEls));
    const wrap = h('div', { class: 'dlg-wrap' }, panel);
    wrap.addEventListener('click', (e) => {
      if (e.target === wrap) done(dismiss);
    });
    const layer = { panel, dismiss: () => done(dismiss) };
    layers.push(layer);
    clearToasts();
    document.body.append(wrap);
    lock(true);
    requestAnimationFrame(() => {
      wrap.classList.add('is-open');
      const want = focus != null ? btnEls[buttons.findIndex((b) => b.value === focus)] : null;
      (want || btnEls[0] || panel).focus();
    });
    let closed = false;
    function done(v) {
      if (closed) return;
      closed = true;
      layers.splice(layers.indexOf(layer), 1);
      wrap.remove();
      lock(false);
      if (prev && document.contains(prev)) prev.focus({ preventScroll: true });
      resolve(v);
    }
  });
}

/** «Уйти без сохранения?» → true, если человек согласился потерять изменения. */
export async function confirmLeave() {
  const v = await dialog({
    title: 'Уйти без сохранения?',
    text: 'Вы что-то поменяли и ещё не сохранили. Если уйти сейчас, эти изменения пропадут.',
    buttons: [
      { label: 'Остаться на странице', value: false, kind: 'ink' },
      { label: 'Уйти без сохранения', value: true, kind: 'danger-line' },
    ],
    dismiss: false,
  });
  return v === true;
}

/** Нижний лист (на компьютере — окно по центру). Возвращает {close, body}. */
export function sheet({ title, body, cls = '', onClose }) {
  const prev = document.activeElement;
  const tid = nextId('sh');
  const bodyEl = h('div', { class: 'sheet__body' }, body);
  const panel = h('div', { class: `sheet ${cls}`, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: '-1' },
    h('div', { class: 'sheet__head' },
      h('h2', { class: 'sheet__t', id: tid }, title),
      h('button', { type: 'button', class: 'ibtn sheet__x', 'aria-label': 'Закрыть', onclick: () => close() }, icon(I.close))),
    bodyEl);
  const wrap = h('div', { class: 'sheet-wrap' }, panel);
  wrap.addEventListener('click', (e) => {
    if (e.target === wrap) close();
  });
  const layer = { panel, dismiss: () => close() };
  layers.push(layer);
  clearToasts();
  document.body.append(wrap);
  lock(true);
  requestAnimationFrame(() => {
    wrap.classList.add('is-open');
    panel.focus({ preventScroll: true });
  });
  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    layers.splice(layers.indexOf(layer), 1);
    wrap.classList.remove('is-open');
    wrap.classList.add('is-closing');
    setTimeout(() => wrap.remove(), 260);
    lock(false);
    if (prev && document.contains(prev)) prev.focus({ preventScroll: true });
    if (onClose) onClose();
  }
  return { close, body: bodyEl, panel };
}

/** Виден ли элемент на экране сейчас (хоть частью): тогда тост с тем же текстом не нужен. */
export function onScreen(el) {
  if (!el || el.hidden || !el.isConnected) return false;
  const r = el.getBoundingClientRect();
  return r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
}

// ——— Короткие сообщения внизу экрана ———
let box = null;

/** Есть ли на экране липкая панель сохранения: тогда тосты — над ней, а нижний отступ страницы не нужен.
 *  Класс на <html>, а не :has(): после смены экрана Chrome оставлял старый стиль — тост из редактора висел
 *  над списком на высоте исчезнувшей панели. Вызывается при каждом тосте и когда экран построен заново. */
export function placeToasts() {
  document.documentElement.classList.toggle('has-savebar', !!document.querySelector('.savebar'));
}

export function toast(text, { kind = 'info', timeout = 5000, action = null } = {}) {
  if (!box) {
    box = h('div', { class: 'toasts', role: 'status', 'aria-live': 'polite' });
    document.body.append(box);
  }
  placeToasts();
  const ico = kind === 'err' ? I.alert : kind === 'ok' ? I.check : I.info;
  const el = h('div', { class: `toast toast--${kind}` },
    icon(ico),
    h('p', { class: 'toast__t' }, text),
    action && h('button', { type: 'button', class: 'toast__a', onclick: () => { close(); action.run(); } }, action.label),
    h('button', { type: 'button', class: 'toast__x', 'aria-label': 'Закрыть сообщение', onclick: () => close() }, icon(I.close)));
  box.append(el);
  while (box.children.length > 2) box.firstElementChild.remove();
  const timer = setTimeout(close, timeout);
  let gone = false;
  function close() {
    if (gone) return;
    gone = true;
    clearTimeout(timer);
    el.classList.add('is-out');
    setTimeout(() => el.remove(), 220);
  }
  return close;
}
