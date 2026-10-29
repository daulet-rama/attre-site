// Вход: логотип, «Админка магазина», выбор имени (если пользователей несколько), пароль, «Войти».

import { api, humane } from './api.js';
import { h, icon } from './dom.js';
import { I, LOGO } from './icons.js';
import { store } from './util.js';

const LAST = 'attre-admin-user';

export function mountLogin(root, { users = [], message = '', overlay = false, onDone }) {
  const many = users.length > 1;
  let chosen = users.length === 1 ? users[0] : null;
  const remembered = store(LAST);
  if (many && remembered && users.includes(remembered)) chosen = remembered;

  const whoErr = h('p', { class: 'fld__err', id: 'login-who-err', hidden: true });
  const chips = users.map((u) => h('button', {
    type: 'button', class: 'chip chip--big', role: 'radio', 'aria-checked': String(u === chosen), tabindex: u === chosen || (!chosen && u === users[0]) ? '0' : '-1',
    onclick: () => pick(u),
  }, u));
  const whoBox = many && h('div', { class: 'fld login__who' },
    h('p', { class: 'fld__l', id: 'login-who-l' }, 'Кто входит?'),
    h('div', { class: 'chips', role: 'radiogroup', 'aria-labelledby': 'login-who-l', 'aria-describedby': 'login-who-err', onkeydown: arrows }, chips),
    whoErr);

  const userField = h('input', { type: 'text', name: 'username', autocomplete: 'username', class: 'sr-only', tabindex: '-1', 'aria-hidden': 'true', value: chosen || '' });
  const pw = h('input', {
    id: 'login-pw', class: 'inp', type: 'password', name: 'password', autocomplete: 'current-password',
    required: true, 'aria-describedby': 'login-pw-err', autocapitalize: 'off', spellcheck: 'false',
    oninput: () => setErr(pwBox, pwErr, ''),
  });
  const eye = h('button', {
    type: 'button', class: 'pw__eye', 'aria-label': 'Показать пароль', 'aria-pressed': 'false',
    onclick: () => {
      const show = pw.type === 'password';
      pw.type = show ? 'text' : 'password';
      eye.setAttribute('aria-pressed', String(show));
      eye.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль');
      eye.replaceChildren(icon(show ? I.eyeOff : I.eye));
      pw.focus();
    },
  }, icon(I.eye));
  const pwErr = h('p', { class: 'fld__err', id: 'login-pw-err', hidden: true });
  const pwBox = h('div', { class: 'fld' },
    h('label', { class: 'fld__l', for: 'login-pw' }, 'Пароль'),
    h('div', { class: 'pw' }, pw, eye),
    pwErr);
  const submit = h('button', { type: 'submit', class: 'btn btn--ink btn--block' }, 'Войти');
  const general = h('p', { class: 'login__err', role: 'alert', hidden: true });

  const form = h('form', { class: 'login__box', novalidate: true, onsubmit: (e) => { e.preventDefault(); send(); } },
    h('div', { class: 'login__logo', html: LOGO }),
    h('h1', { class: 'login__t' }, 'Админка магазина'),
    message && h('p', { class: 'login__msg' }, message),
    whoBox,
    userField,
    pwBox,
    general,
    submit,
    h('p', { class: 'login__help' }, 'Забыли пароль? Напишите Даулету — он подскажет.'));
  root.replaceChildren(h('div', { class: overlay ? 'login login--over' : 'login' }, form));
  root.classList.remove('boot');
  root.removeAttribute('aria-busy');
  // Курсор в пароль, если имя уже известно (на телефоне клавиатура сама не откроется — только по нажатию)
  if (!many || chosen) requestAnimationFrame(() => pw.focus());

  function pick(u) {
    chosen = u;
    userField.value = u;
    chips.forEach((c) => {
      const on = c.textContent === u;
      c.setAttribute('aria-checked', String(on));
      c.tabIndex = on ? 0 : -1;
    });
    if (whoBox) setErr(whoBox, whoErr, '');
  }

  function arrows(e) {
    const i = chips.indexOf(document.activeElement);
    if (i < 0) return;
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = chips[(i + d + chips.length) % chips.length];
    next.focus();
    pick(next.textContent);
  }

  function setErr(box, el, msg) {
    // как ошибки остальных полей: красным, со значком ⚠
    el.replaceChildren(...(msg ? [icon(I.alert), h('span', null, msg)] : []));
    el.hidden = !msg;
    box.classList.toggle('is-err', !!msg);
  }

  async function send() {
    general.hidden = true;
    let bad = false;
    if (many && !chosen) {
      setErr(whoBox, whoErr, 'Выберите, кто входит');
      bad = true;
    }
    if (!pw.value) {
      setErr(pwBox, pwErr, 'Впишите пароль');
      bad = true;
    }
    if (bad) {
      (many && !chosen ? chips[0] : pw).focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Входим…';
    try {
      const body = { password: pw.value };
      if (chosen) body.name = chosen;
      const r = await api('/api/login', { method: 'POST', body, auth: false });
      if (chosen) store(LAST, chosen);
      onDone((r && r.user) || chosen || 'Админ');
    } catch (e) {
      submit.disabled = false;
      submit.textContent = 'Войти';
      if (e.status === 401) {
        setErr(pwBox, pwErr, e.message || 'Пароль не подошёл. Проверьте раскладку (русская или английская) и большие буквы.');
        pw.select();
        pw.focus();
      } else if (e.field === 'name' && !many) {
        let list = [];
        try {
          list = ((await api('/api/login', { auth: false })).users || []).filter((u) => typeof u === 'string');
        } catch {
          list = [];
        }
        if (list.length > 1) {
          mountLogin(root, { users: list, message: 'Выберите, кто входит, и введите пароль ещё раз.', overlay, onDone });
          return;
        }
        general.textContent = humane(e);
        general.hidden = false;
      } else {
        general.textContent = humane(e);
        general.hidden = false;
      }
    }
  }
}
