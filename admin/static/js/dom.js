// Маленький помощник для DOM без фреймворков: h('button', {class, onclick}, 'текст', детиш...)

export function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  let value;
  if (props) {
    for (const k of Object.keys(props)) {
      const v = props[k];
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'value') value = v;
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k === 'checked' || k === 'indeterminate') el[k] = !!v;
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else el.setAttribute(k, v === true ? '' : String(v));
    }
  }
  add(el, kids);
  if (value !== undefined) el.value = value;
  return el;
}

export function add(el, kids) {
  for (const c of kids) {
    if (c == null || c === false || c === true) continue;
    if (Array.isArray(c)) add(el, c);
    else el.append(c instanceof Node ? c : String(c));
  }
  return el;
}

/** Разметка-строка → элемент (для значков и превью сайта). */
export function frag(markup) {
  const t = document.createElement('template');
  t.innerHTML = String(markup).trim();
  return t.content;
}

export function icon(markup) {
  return frag(markup).firstElementChild;
}

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Кратко подсветить блок (после перестановки), чтобы глаз нашёл, куда он уехал. */
export function flash(el) {
  if (!el) return;
  el.classList.remove('is-flash');
  void el.offsetWidth;
  el.classList.add('is-flash');
  setTimeout(() => el.classList.remove('is-flash'), 900);
}

/** Прокрутить к элементу так, чтобы он не прятался под шапкой и нижней панелью. */
export function reveal(el, { block = 'center' } = {}) {
  if (!el) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  el.scrollIntoView({ block, behavior: reduce ? 'auto' : 'smooth' });
}
