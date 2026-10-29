// Поля формы: подпись, подсказка серым, ошибка красным рядом с полем; крупные чипы, переключатели, флажки.
// У каждого поля есть data-field — по нему находим место для ошибки (и своей, и пришедшей с сервера).

import { h, icon } from './dom.js';
import { I } from './icons.js';
import { clearToasts } from './ui.js';
import { uid } from './util.js';

/** Поле «как написано»: без заглавной буквы в начале, автозамены и проверки орфографии (iPhone пишет «Хобо»). */
export const PLAIN = { autocapitalize: 'none', autocorrect: 'off', spellcheck: 'false' };

/** Язык поля перевода: проверка орфографии и экранный диктор — казахские и английские. */
export const LANG_ATTR = { kz: 'kk', en: 'en' };

/**
 * Обёртка поля. label — подпись, hint — подсказка, req — обязательное (звёздочка), opt — «необязательно».
 * control — сам элемент ввода (или группа); если в нём есть input/textarea — связываем с подписью и подсказкой.
 * after — сразу под полем (подсказки-чипы), below — под подсказкой и ошибкой (предупреждение о переводе).
 */
export function field({ name, label, hint, req = false, opt = false, control, cls = '', id = null, after = null, below = null, group = false }) {
  const isInput = control && /^(INPUT|TEXTAREA|SELECT)$/.test(control.tagName);
  const inner = !isInput && !group && control && control.querySelector ? control.querySelectorAll('input:not(.sr-only), textarea') : [];
  const target = isInput ? control : inner.length === 1 ? inner[0] : null;   // одно поле внутри (с «₸») — подпись к нему
  const cid = id || (target && target.id) || (control && control.id) || `f-${uid()}`;
  if (target && !target.id) target.id = cid;
  const hintEl = hint ? h('p', { class: 'fld__hint', id: `${cid}-hint` }, hint) : null;
  const errEl = h('p', { class: 'fld__err', id: `${cid}-err`, hidden: true });
  const lab = label && h(target ? 'label' : 'p', { class: 'fld__l', id: `${cid}-l`, for: target ? target.id : null },
    label,
    req && h('span', { class: 'req', 'aria-hidden': 'true' }, ' *'),
    req && h('span', { class: 'sr-only' }, ' (обязательно)'),
    opt && h('span', { class: 'fld__opt' }, 'необязательно'));
  const el = h('div', { class: `fld ${cls}`, 'data-field': name || null }, lab, control, after, hintEl, errEl, below);
  if (target) target.setAttribute('aria-describedby', [hintEl && hintEl.id, errEl.id].filter(Boolean).join(' '));
  if (!target && control && lab && control.setAttribute && !control.getAttribute('aria-labelledby') && control.getAttribute('role')) {
    control.setAttribute('aria-labelledby', lab.id);
    if (hintEl) control.setAttribute('aria-describedby', `${hintEl.id} ${errEl.id}`);
  }
  return el;
}

export function input({ id, value = '', placeholder = '', type = 'text', inputmode, maxlength, autocomplete = 'off', cls = '', oninput, onblur, enterkeyhint, pattern, autocapitalize, autocorrect, spellcheck, lang }) {
  const el = h('input', {
    id, type, class: `inp ${cls}`, value, placeholder, inputmode, maxlength, autocomplete, enterkeyhint, pattern, lang,
    autocapitalize: autocapitalize ?? (type === 'email' || type === 'url' ? 'off' : null),
    autocorrect: autocorrect ?? null,
    spellcheck: spellcheck ?? (type === 'text' ? null : 'false'),
  });
  if (oninput) el.addEventListener('input', () => oninput(el.value, el));
  if (onblur) el.addEventListener('blur', () => onblur(el.value, el));
  return el;
}

/** Многострочное поле, которое растёт по тексту. */
export function textarea({ id, value = '', placeholder = '', rows = 3, oninput, maxlength, lang }) {
  const el = h('textarea', { id, class: 'inp inp--area', rows, placeholder, maxlength, value, lang });
  const fit = () => {
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight + 2, 0)}px`;
  };
  el.addEventListener('input', () => {
    fit();
    if (oninput) oninput(el.value, el);
  });
  el.fit = fit;
  requestAnimationFrame(fit);
  return el;
}

/** Поле с подписью справа внутри рамки: «₸», «см», «шт.». */
export function withUnit(inp, unit) {
  return h('div', { class: 'unit' }, inp, h('span', { class: 'unit__u', 'aria-hidden': 'true' }, unit));
}

/**
 * Выбор одного из нескольких (крупные кнопки): стрелки на клавиатуре двигают выбор.
 * options: [{value, label, hint?, render?}]. Возвращает элемент с .set(value).
 */
export function radios({ options, value, onchange, cls = 'chips', item = 'chip', labelledby }) {
  let cur = value;
  const btns = options.map((o) => {
    const b = h('button', { type: 'button', class: item, role: 'radio', 'aria-checked': String(o.value === cur), 'data-value': o.value },
      o.render ? o.render(o) : o.label);
    b.addEventListener('click', () => {
      set(o.value);
      onchange(o.value);
    });
    return b;
  });
  const el = h('div', { class: cls, role: 'radiogroup', 'aria-labelledby': labelledby || null }, btns);
  function roving() {
    const i = Math.max(0, options.findIndex((o) => o.value === cur));
    btns.forEach((b, j) => { b.tabIndex = j === i ? 0 : -1; });
  }
  function set(v) {
    cur = v;
    btns.forEach((b, j) => b.setAttribute('aria-checked', String(options[j].value === v)));
    roving();
  }
  el.addEventListener('keydown', (e) => {
    const i = btns.indexOf(document.activeElement);
    if (i < 0) return;
    const k = e.key;
    let j = null;
    if (k === 'ArrowRight' || k === 'ArrowDown') j = (i + 1) % btns.length;
    else if (k === 'ArrowLeft' || k === 'ArrowUp') j = (i - 1 + btns.length) % btns.length;
    else if (k === 'Home') j = 0;
    else if (k === 'End') j = btns.length - 1;
    if (j == null) return;
    e.preventDefault();
    btns[j].focus();
    btns[j].click();
  });
  roving();
  el.set = set;
  el.buttons = btns;
  return el;
}

/** Кнопки-переключатели (можно выбрать и снять): материалы. */
export function toggles({ options, isOn, onToggle, cls = 'chips', labelledby }) {
  const btns = options.map((o) => h('button', {
    type: 'button', class: 'chip', 'aria-pressed': String(isOn(o.value)),
    onclick: () => {
      onToggle(o.value);
      refresh();
    },
  }, o.label));
  const el = h('div', { class: cls, role: 'group', 'aria-labelledby': labelledby || null }, btns);
  function refresh() {
    btns.forEach((b, i) => b.setAttribute('aria-pressed', String(isOn(options[i].value))));
  }
  el.refresh = refresh;
  return el;
}

/** Переключатель «вкл/выкл» с подписью и подсказкой (подсказка может меняться от состояния). */
export function switcher({ id, checked, label, hint, onchange }) {
  const box = h('input', { type: 'checkbox', id, class: 'switch__in', role: 'switch', checked });
  const hintEl = h('span', { class: 'switch__hint', id: `${id}-hint` });
  box.setAttribute('aria-describedby', hintEl.id);
  const el = h('label', { class: 'switch', for: id },
    box,
    h('span', { class: 'switch__track', 'aria-hidden': 'true' }, h('span', { class: 'switch__knob' })),
    h('span', { class: 'switch__txt' }, h('span', { class: 'switch__l' }, label), hintEl));
  const upd = () => {
    hintEl.textContent = typeof hint === 'function' ? hint(box.checked) : hint || '';
    el.classList.toggle('is-on', box.checked);
  };
  box.addEventListener('change', () => {
    upd();
    onchange(box.checked);
  });
  upd();
  el.set = (v) => {
    box.checked = !!v;
    upd();
  };
  return el;
}

/** Флажок с подписью и пояснением: «Новинка», «Популярное». */
export function check({ id, checked, label, hint, onchange }) {
  const box = h('input', { type: 'checkbox', id, class: 'check__in', checked });
  box.addEventListener('change', () => onchange(box.checked));
  return h('label', { class: 'check', for: id },
    box,
    h('span', { class: 'check__box', 'aria-hidden': 'true' }, icon(I.check)),
    h('span', { class: 'check__txt' }, h('span', { class: 'check__l' }, label), hint && h('span', { class: 'check__hint' }, hint)));
}

/** Раздел формы: заголовок капсом с разрядкой — крупный и жирный, чтобы в длинной форме глаз находил разделы. */
export function section({ title, id, req = false, intro = null }, ...kids) {
  return h('section', { class: 'sec', id, 'aria-labelledby': `${id}-t` },
    h('h2', { class: 'sec__t', id: `${id}-t` }, title, req && h('span', { class: 'req', 'aria-hidden': 'true' }, ' *')),
    intro && h('p', { class: 'sec__intro' }, intro),
    kids);
}

/**
 * «Перевод остался от прежнего текста»: русский поменяли, а казахский и английский — нет (на қаз/eng сайте
 * осталось бы старое: прежние часы работы, прежний тип). orig — как было при открытии, cur() — как сейчас.
 * «Поправить перевод» открывает блок переводов, «Убрать старый перевод» очищает его — сайт покажет русский.
 */
export function staleTr({ orig, cur, onOpen, onClear }) {
  const o = { ru: String(orig.ru || ''), kz: String(orig.kz || ''), en: String(orig.en || '') };
  const el = h('div', { class: 'trwarn', role: 'status', hidden: true },
    icon(I.info),
    h('div', { class: 'trwarn__in' },
      h('p', null, 'Вы поменяли русский текст, а казахский и английский остались прежними.'),
      h('p', { class: 'trwarn__btns' },
        h('button', { type: 'button', class: 'link', onclick: () => onOpen() }, 'Поправить перевод'),
        h('button', { type: 'button', class: 'link', onclick: () => { onClear(); update(); } }, 'Убрать старый перевод (будет русский)'))));
  function update() {
    const c = cur();
    el.hidden = !(c.ru.trim() !== o.ru.trim() && (o.kz.trim() || o.en.trim()) && c.kz === o.kz && c.en === o.en);
  }
  el.update = update;
  return el;
}

/** Свёрнутый блок «Казахский и английский (необязательно)». */
export function fold({ title, hint, open = false, cls = '' }, ...kids) {
  const d = h('details', { class: `fold ${cls}` },
    h('summary', { class: 'fold__s' }, h('span', { class: 'fold__t' }, title, hint && h('span', { class: 'fold__hint' }, hint)), icon(I.chevron)),
    h('div', { class: 'fold__in' }, kids));
  if (open) d.open = true;
  return d;
}

// ——— Ошибки ———

/** Сообщение внизу об ошибках формы: одна — её текст; несколько — «Проверьте: название, категорию, фото.»
 *  what(field) → слово для перечня (в винительном падеже) или null. */
export function errorsText(errs, what) {
  if (errs.length === 1) return errs[0].msg;
  const words = [...new Set(errs.map((e) => what(e.field)).filter(Boolean))];
  return words.length ? `Проверьте: ${words.join(', ')}.` : 'Проверьте места, отмеченные красным.';
}

function normPath(path) {
  return String(path || '').replace(/\[(\d+)\]/g, '.$1').replace(/^(product|body|settings)\./, '').replace(/^\.+/, '');
}

/** Найти поле по пути ошибки: «variants.1.images» → блок фото второго цвета (или ближайший родитель). */
export function findField(root, path) {
  let p = normPath(path);
  while (p) {
    const el = root.querySelector(`[data-field="${CSS.escape(p)}"]`);
    if (el) return el;
    const i = p.lastIndexOf('.');
    if (i < 0) break;
    p = p.slice(0, i);
  }
  return null;
}

export function setError(root, path, msg) {
  const w = findField(root, path);
  if (!w) return null;
  const e = w.querySelector(':scope > .fld__err');
  if (e) {
    e.replaceChildren(icon(I.alert), h('span', null, msg));
    e.hidden = false;
  }
  w.classList.add('is-err');
  for (const inp of w.querySelectorAll(':scope > input, :scope > textarea, :scope > .unit > input, :scope > .pw > input')) inp.setAttribute('aria-invalid', 'true');
  return w;
}

export function clearError(w) {
  if (!w) return;
  w.classList.remove('is-err');
  const e = w.querySelector(':scope > .fld__err');
  if (e) {
    e.hidden = true;
    e.replaceChildren();
  }
  for (const inp of w.querySelectorAll('[aria-invalid]')) inp.removeAttribute('aria-invalid');
}

export function clearErrors(root) {
  for (const w of root.querySelectorAll('.is-err')) clearError(w);
}

/** Показать список ошибок [{field, msg}] и вернуть первое поле (к нему прокрутим). */
export function showErrors(root, errs) {
  let first = null;
  for (const e of errs) {
    const w = setError(root, e.field, e.msg);
    if (w) {
      const d = w.closest('details');
      if (d) d.open = true;
      if (!first) first = w;
    }
  }
  return first;
}

/** Снимать ошибку с поля, как только человек начал его исправлять. */
export function autoClear(root) {
  const handler = (e) => {
    const w = e.target.closest && e.target.closest('.is-err');
    if (w) {
      clearError(w);
      clearToasts('err');
    }
  };
  root.addEventListener('input', handler);
  root.addEventListener('click', (e) => {
    if (e.target.closest && e.target.closest('[role="radio"], [aria-pressed], .check, .switch')) handler(e);
  });
}

export function focusField(w) {
  if (!w) return;
  const d = w.closest('details');
  if (d && !d.open) d.open = true;
  const f = w.querySelector('input:not([type="hidden"]):not(.sr-only), textarea, [role="radio"][tabindex="0"], button');
  w.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  if (f) setTimeout(() => f.focus({ preventScroll: true }), 250);
}
