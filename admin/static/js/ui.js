// Окна поверх экрана: подтверждение (dialog), окно с полями (formDialog), нижний лист (sheet), сообщения (toast).

import { h, icon } from './dom.js';
import { I } from './icons.js';

// ——— Блокировка прокрутки страницы, пока открыто окно (счётчик: окна бывают одно над другим) ———
let locks = 0;
function lock(on) {
  locks = Math.max(0, locks + (on ? 1 : -1));
  document.documentElement.classList.toggle('is-locked', locks > 0);
}

/** Тот же счётчик для окон, которые строятся не здесь (вход поверх экрана, app.js): закрытое под ним окно
 *  не должно снимать блокировку прокрутки, пока вход ещё открыт. */
export function lockScroll(on) {
  lock(on);
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
    // tabIndex < 0 — не по Tab: например, скрытое поле с именем для менеджера паролей
    const list = Array.from(top.panel.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null && el.tabIndex >= 0);
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

/**
 * Окно с полями (смена пароля): слои, Tab, Esc и возврат фокуса — как у dialog(). Отправка — кнопкой submitLabel
 * или Enter: onSubmit(ctl) → true — закрыть окно, false — оставить (ошибки показаны у полей; ctl.error(текст) —
 * общая ошибка над кнопками, ctl.close() — закрыть без отправки). Пока идёт отправка, окно не закрывается.
 * Нажатие мимо окна закрывает его, только пока поля пустые: на телефоне мимо нажимают, чтобы спрятать клавиатуру.
 * На телефоне окно держится над экранной клавиатурой (visualViewport). → Promise: true — отправлено, false — нет.
 */
export function formDialog({ title, text, body, submitLabel, busyLabel, cancelLabel = 'Отмена', onSubmit, focus = null, cls = '' }) {
  return new Promise((resolve) => {
    const prev = document.activeElement;
    let busy = false;          // идёт отправка — окно не закрывается
    let closed = false;
    const tid = nextId('dlg');
    const did = text ? `${tid}-text` : null;
    const submit = h('button', { type: 'submit', class: 'btn btn--ink' }, submitLabel);
    const cancel = h('button', { type: 'button', class: 'btn btn--line', onclick: () => done(false) }, cancelLabel);
    const general = h('p', { class: 'dlg__err', role: 'alert', hidden: true });
    const panel = h('form', {
      class: `dlg dlg--form ${cls}`, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, 'aria-describedby': did,
      tabindex: '-1', novalidate: true, onsubmit: (e) => { e.preventDefault(); send(); },
    },
    h('h2', { class: 'dlg__t', id: tid }, title),
    text && h('p', { class: 'dlg__text', id: did }, text),
    body,
    general,
    h('div', { class: 'dlg__btns' }, submit, cancel));
    const wrap = h('div', { class: 'dlg-wrap dlg-wrap--form' }, panel);
    const empty = () => Array.from(panel.querySelectorAll('input')).every((i) => i.tabIndex < 0 || !i.value);
    wrap.addEventListener('click', (e) => {
      if (e.target === wrap && !busy && empty()) done(false);
    });
    const layer = { panel, dismiss: () => { if (!busy) done(false); } };
    const ctl = {
      error(msg) {
        general.textContent = msg || '';
        general.hidden = !msg;
      },
      close: () => done(false),
    };
    // Экранная клавиатура на телефоне закрывает низ экрана: окно — в видимой части, поле с курсором — на виду
    const vv = window.visualViewport;
    const fit = () => {
      wrap.style.top = `${vv.offsetTop}px`;
      wrap.style.height = `${vv.height}px`;
      wrap.style.bottom = 'auto';
      const a = document.activeElement;
      if (a && panel.contains(a) && a !== panel) (a.closest('.fld') || a).scrollIntoView({ block: 'nearest' });
    };
    if (vv) {
      vv.addEventListener('resize', fit);
      vv.addEventListener('scroll', fit);
    }
    layers.push(layer);
    clearToasts();
    document.body.append(wrap);
    lock(true);
    if (vv) fit();
    requestAnimationFrame(() => {
      wrap.classList.add('is-open');
      (focus || panel).focus();
    });
    async function send() {
      if (busy || closed) return;
      busy = true;
      ctl.error('');
      submit.disabled = true;
      cancel.disabled = true;
      if (busyLabel) submit.textContent = busyLabel;
      let ok = false;
      try {
        ok = await onSubmit(ctl);
      } catch (e) {
        console.error(e);
        ctl.error('На странице что-то сломалось. Обновите её — если не поможет, сообщите Даулету.');
      }
      busy = false;
      submit.disabled = false;
      cancel.disabled = false;
      submit.textContent = submitLabel;
      if (ok) done(true);
    }
    function done(v) {
      if (closed) return;
      closed = true;
      layers.splice(layers.indexOf(layer), 1);
      if (vv) {
        vv.removeEventListener('resize', fit);
        vv.removeEventListener('scroll', fit);
      }
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
