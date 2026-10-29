// «Сменить пароль» — окно из меню в шапке (на телефоне — кружок с буквой, на компьютере — имя): текущий пароль,
// новый (не короче 8 символов), повтор; у каждого поля «глаз». Повтор и простые правила проверяются до отправки,
// текущий пароль — на сервере (POST /api/password). После смены этому устройству сервер выдаёт новый вход, а прежние
// входы этого человека на других устройствах перестают действовать — об этом сообщение после смены.

import { api, humane, reportAuthLost, whileRenewing } from './api.js';
import { h, icon } from './dom.js';
import { clearError, clearErrors, field, setError } from './form.js';
import { I } from './icons.js';
import { formDialog, toast } from './ui.js';

const MIN = 8;
const MAX = 128;
// Невидимые символы — как на сервере (passwords.BAD_CATEGORIES): управляющие, нулевой ширины, разделители строк
const BAD = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
export const DONE = 'Пароль изменён. На других устройствах войдите заново — с новым паролем.';

const fold = (s) => String(s || '').normalize('NFC').toLowerCase();

/** Что не так с новым паролем — те же правила и тексты, что на сервере (passwords.new_password_problem). */
export function problem(pw, name, current) {
  if (!pw) return 'Придумайте новый пароль.';
  if (BAD.test(pw)) return 'В новом пароле есть невидимые служебные символы. Наберите его заново с клавиатуры.';
  if (pw !== pw.trim()) return 'Уберите пробелы в начале и в конце нового пароля.';
  const n = [...pw].length;
  if (n < MIN) return `Новый пароль слишком короткий — нужно не меньше ${MIN} символов.`;
  if (n > MAX) return `Новый пароль слишком длинный — не больше ${MAX} символов.`;
  if (fold(pw) === fold(name)) return 'Новый пароль не должен совпадать с вашим именем.';
  if (current && fold(pw) === fold(current)) return 'Новый пароль совпадает с текущим — придумайте другой.';
  return null;
}

function pwField(name, label, { hint, autocomplete, enterkeyhint }) {
  const input = h('input', {
    id: `pwc-${name}`, class: 'inp', type: 'password', name: `pwc-${name}`, autocomplete, enterkeyhint,
    autocapitalize: 'none', autocorrect: 'off', spellcheck: 'false',
  });
  const eye = h('button', { type: 'button', class: 'pw__eye', 'aria-label': 'Показать пароль', 'aria-pressed': 'false', 'aria-controls': input.id }, icon(I.eye));
  eye.addEventListener('click', () => {
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    eye.setAttribute('aria-pressed', String(show));
    eye.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль');
    eye.replaceChildren(icon(show ? I.eyeOff : I.eye));
    input.focus();
  });
  const box = field({ name, label, hint, control: h('div', { class: 'pw' }, input, eye), id: input.id });
  return { box, input };
}

/** Enter в поле: следующее поле пустое — перейти в него; всё заполнено — отправить. */
function nextOnEnter(from, to) {
  from.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || e.isComposing || to.value) return;
    e.preventDefault();
    to.focus();
  });
}

/** Открыть окно смены пароля. → Promise: true — пароль сменён. */
export function changePassword({ user }) {
  const cur = pwField('current', 'Текущий пароль', { autocomplete: 'current-password', enterkeyhint: 'next' });
  const nw = pwField('new', 'Новый пароль', { hint: `Не короче ${MIN} символов`, autocomplete: 'new-password', enterkeyhint: 'next' });
  const rep = pwField('repeat', 'Повторите новый пароль', { autocomplete: 'new-password', enterkeyhint: 'done' });
  const inputs = { current: cur.input, new: nw.input, repeat: rep.input };
  nextOnEnter(cur.input, nw.input);
  nextOnEnter(nw.input, rep.input);
  // Имя — для менеджера паролей телефона: он предложит обновить сохранённый пароль именно этого входа
  const username = h('input', { type: 'text', name: 'username', autocomplete: 'username', class: 'sr-only', tabindex: '-1', 'aria-hidden': 'true', value: user || '' });
  const body = h('div', { class: 'pwc' }, username, cur.box, nw.box, rep.box);
  body.addEventListener('input', (e) => {
    const w = e.target.closest && e.target.closest('.fld');
    if (w) clearError(w);
    if (e.target === nw.input) clearError(rep.box);   // новый поменяли — «не совпадают» уже не про то
  });

  function focusField(name, select = false) {
    const el = inputs[name];
    el.focus();
    if (select) el.select();
  }

  return formDialog({
    title: 'Сменить пароль',
    body,
    submitLabel: 'Сменить пароль',
    busyLabel: 'Меняем пароль…',
    focus: cur.input,
    cls: 'dlg--pw',
    onSubmit: async (ctl) => {
      clearErrors(body);
      const c = cur.input.value, n = nw.input.value, r = rep.input.value;
      const errs = [];
      if (!c) errs.push(['current', 'Впишите текущий пароль.']);
      const bad = problem(n, user, c);
      if (bad) errs.push(['new', bad]);
      else if (!r) errs.push(['repeat', 'Повторите новый пароль.']);
      else if (r !== n) errs.push(['repeat', 'Пароли не совпадают. Наберите новый пароль ещё раз.']);
      if (errs.length) {
        for (const [f, msg] of errs) setError(body, f, msg);
        // повтор не совпал — набранное выделено: новое набирается поверх, не стирая точки по одной
        focusField(errs[0][0], errs[0][0] === 'repeat');
        return false;
      }
      try {
        // ответ принесёт новый вход этому устройству: пока он идёт, окно входа из-за 401 на другой запрос ждёт его
        await whileRenewing(api('/api/password', { method: 'POST', body: { current: c, new: n }, auth: false }));
      } catch (e) {
        if (e.status === 401) {
          // вход истёк или пароль уже сменили на другом устройстве: смена здесь больше не нужна — сначала
          // закрываем это окно, потом вход поверх экрана (пока окно открыто, Esc и Tab достаются ему, а не входу)
          ctl.close();
          reportAuthLost(e);
          return false;
        }
        if (e.field === 'current' || e.field === 'new') {
          setError(body, e.field, e.message);
          focusField(e.field, e.field === 'current');
          return false;
        }
        ctl.error(humane(e));
        return false;
      }
      toast(DONE, { kind: 'ok', timeout: 10000 });
      return true;
    },
  });
}
