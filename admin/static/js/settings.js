// «Магазин и доставка»: доставка по Казахстану и по миру, контакты, полоса сверху сайта, продавец (ИП/ТОО, ИИН/БИН).
// Одна общая кнопка «Сохранить и опубликовать» внизу. Тексты на қаз/eng — в свёрнутых блоках.
// Под доставкой — «На сайте будет так»: способы, цены (0 ₸ сайт пишет словом «бесплатно») и строка «бесплатно от».
// Несохранённое лежит в черновике на этом устройстве (draft.js) — как в редакторе товара.

import { api, humane } from './api.js';
import { h, icon, flash } from './dom.js';
import { readDraft, writeDraft, dropDraft, draftBar } from './draft.js';
import {
  field, input, textarea, withUnit, section, fold, staleTr, showErrors, clearErrors, setError, autoClear, focusField, errorsText, LANG_ATTR,
} from './form.js';
import { I } from './icons.js';
import { setLeaveGuard, clearLeaveGuard } from './router.js';
import * as status from './status.js';
import { dialog, toast, clearToasts, placeToasts } from './ui.js';
import { clone, tri, triTrim, uid, groupDigits, parseIntField, plural, LANGS, money } from './util.js';

const LANG_NAME = { kz: 'Қазақша', en: 'English' };
const MAX_TEXT = 2000;
const DRAFT = 'settings';

// Перечень в сообщении внизу: «Проверьте: WhatsApp, адрес.» (винительный падеж)
const WHAT = [
  [/^contacts\.whatsapp/, 'WhatsApp'], [/^contacts\.instagram/, 'Instagram'], [/^contacts\.pinterest/, 'Pinterest'],
  [/^contacts\.email/, 'e-mail'], [/^contacts\.map_url/, 'ссылку 2ГИС'], [/^contacts\.address/, 'адрес'],
  [/^contacts\.hours/, 'часы работы'], [/^delivery\.free_from/, 'сумму бесплатной доставки'], [/^delivery\.kz/, 'способы доставки'],
  [/^delivery\.world/, 'доставку по миру'], [/^promo/, 'полосу сверху'], [/^seller/, 'продавца'],
];
const what = (f) => (WHAT.find(([re]) => re.test(String(f || ''))) || [null, null])[1];

function digits(s) {
  return String(s || '').replace(/\D/g, '');
}

/** Номер WhatsApp → 11 цифр с 7: «+7 706 723 23 49», «8 706…», «706…» — всё приводим к 77067232349. */
export function normPhone(s) {
  let d = digits(s);
  if (d.length === 11 && d.startsWith('8')) d = `7${d.slice(1)}`;
  if (d.length === 10 && d.startsWith('7')) d = `7${d}`;
  return d;
}

function showPhone(s) {
  const d = normPhone(s);
  if (d.length !== 11) return String(s || '');
  return `+${d[0]} ${d.slice(1, 4)} ${d.slice(4, 7)} ${d.slice(7, 9)} ${d.slice(9)}`;
}

/** Ник из ссылки: «https://www.instagram.com/attre.studio/» или «@attre.studio» → «attre.studio». */
export function nick(s) {
  let t = String(s || '').trim();
  const m = /(?:instagram\.com|pinterest\.[a-z.]+|pin\.it)\/([^/?#\s]+)/i.exec(t);
  if (m) t = m[1];
  return t.replace(/^@+/, '').replace(/\/+$/, '').trim();
}

export function mountSettings(main) {
  let data = null;
  let sha = null;
  let form = null;
  let base = '';
  let baseForm = null;     // как было при открытии — с ним сравниваем «что поменял человек» (черновик)
  let saving = false;
  let dead = false;
  let raf = 0;
  let pending = null;      // черновик с прошлого раза: ещё не решили, восстановить или удалить
  let discarded = false;   // «Уйти без сохранения» — черновик не нужен
  // Поля формы и как их сравнивать (пробелы по краям, формат номера и цены изменением не считаются)
  const int = (s) => {
    const n = parseIntField(s);
    return Number.isNaN(n) ? `?${s}` : n;
  };
  const KEYS = {
    whatsapp: (f) => normPhone(f.whatsapp), instagram: (f) => nick(f.instagram), pinterest: (f) => nick(f.pinterest),
    email: (f) => f.email.trim(), map_url: (f) => f.map_url.trim(), address: (f) => triTrim(f.address), hours: (f) => triTrim(f.hours),
    free_from: (f) => int(f.free_from), kz: (f) => f.kz.map((o) => [triTrim(o.name), triTrim(o.days), int(o.price)]),
    world: (f) => triTrim(f.world), promo: (f) => triTrim(f.promo), seller_name: (f) => f.seller_name.trim(), seller_bin: (f) => digits(f.seller_bin),
  };

  const refs = {};
  const root = h('div', { class: 'st' });
  main.replaceChildren(root);
  const guard = {
    dirty: () => !!form && !dead && snap() !== base,
    discard: () => {
      discarded = true;
      dropDraft(DRAFT);
    },
  };
  setLeaveGuard(guard);
  const onHide = () => {
    if (document.visibilityState === 'hidden') persistDraft();
  };
  document.addEventListener('visibilitychange', onHide);
  window.addEventListener('pagehide', persistDraft);
  loading();
  load();

  return {
    destroy() {
      persistDraft();
      dead = true;
      clearLeaveGuard(guard);
      cancelAnimationFrame(raf);
      document.removeEventListener('visibilitychange', onHide);
      window.removeEventListener('pagehide', persistDraft);
    },
    title: () => 'Магазин и доставка',
  };

  function loading() {
    root.replaceChildren(h('div', { class: 'state state--load' }, h('span', { class: 'spin spin--l', 'aria-hidden': 'true' }), h('p', null, 'Загружаем настройки магазина…')));
    placeToasts();
  }

  async function load() {
    try {
      const r = await api('/api/settings');
      if (dead) return;
      data = r || {};
      sha = data.sha || null;
      form = toForm(data);
      baseForm = toForm(data);
      base = snap();
      checkDraft();
      build();
    } catch (e) {
      if (dead) return;
      root.replaceChildren(h('div', { class: 'state' },
        h('h1', { class: 'state__t' }, 'Не получилось загрузить настройки'),
        h('p', { class: 'state__p' }, humane(e)),
        h('div', { class: 'state__btns' }, h('button', { type: 'button', class: 'btn btn--ink', onclick: () => { loading(); load(); } }, 'Попробовать ещё раз'))));
    }
  }

  function toForm(d) {
    const c = d.contacts || {};
    const dl = d.delivery || {};
    const sl = d.seller || {};
    return {
      whatsapp: showPhone(c.whatsapp), instagram: String(c.instagram || ''), pinterest: String(c.pinterest || ''),
      email: String(c.email || ''), map_url: String(c.map_url || ''), address: tri(c.address), hours: tri(c.hours),
      free_from: typeof dl.free_from === 'number' ? groupDigits(dl.free_from) : '',
      kz: (Array.isArray(dl.kz) ? dl.kz : []).filter((o) => o && typeof o === 'object').map((o) => ({
        uid: uid(), name: tri(o.name), days: tri(o.days), price: typeof o.price === 'number' ? groupDigits(o.price) : '', extra: clone(o),
      })),
      world: tri(dl.world), promo: tri(d.promo),
      seller_name: String(sl.name || ''), seller_bin: String(sl.bin || ''),
    };
  }

  function snapOf(f) {
    return JSON.stringify(Object.values(KEYS).map((get) => get(f)));
  }

  function snap() {
    return snapOf(form);
  }

  // ——— Черновик на этом устройстве ———

  function fromShape(f) {
    if (!f || typeof f !== 'object') return null;
    const s = (x) => (typeof x === 'string' ? x : '');
    return {
      whatsapp: s(f.whatsapp), instagram: s(f.instagram), pinterest: s(f.pinterest), email: s(f.email), map_url: s(f.map_url),
      address: tri(f.address), hours: tri(f.hours), free_from: s(f.free_from),
      kz: (Array.isArray(f.kz) ? f.kz : []).filter((o) => o && typeof o === 'object').map((o) => ({
        uid: uid(), name: tri(o.name), days: tri(o.days), price: s(o.price), extra: o.extra && typeof o.extra === 'object' ? o.extra : {},
      })),
      world: tri(f.world), promo: tri(f.promo), seller_name: s(f.seller_name), seller_bin: s(f.seller_bin),
    };
  }

  function checkDraft() {
    pending = null;
    const d = readDraft(DRAFT);
    if (!d) return;
    const f = fromShape(d.form);
    if (!f || snapOf(f) === base) {
      dropDraft(DRAFT);
      return;
    }
    pending = d;
  }

  function persistDraft() {
    if (!form || dead || !baseForm || discarded) return;
    if (snap() !== base) writeDraft(DRAFT, { form: clone(form), base: clone(baseForm), sha });
    else if (pending) writeDraft(DRAFT, { form: pending.form, base: pending.base, sha: pending.sha }, pending.at);
    else dropDraft(DRAFT);
  }

  /** Восстановить черновик: переносятся только поля, которые человек поменял, — поверх того, что сейчас на сайте. */
  function restoreDraft() {
    const d = pending;
    pending = null;
    const from = d && fromShape(d.form);
    if (!from) return;
    const was = fromShape(d.base) || toForm(data);
    const next = toForm(data);
    for (const [k, get] of Object.entries(KEYS)) {
      if (JSON.stringify(get(from)) !== JSON.stringify(get(was))) next[k] = from[k];
    }
    form = next;
    build();
    persistDraft();
    toast('Черновик восстановлен. Проверьте и нажмите «Сохранить и опубликовать».', { kind: 'ok' });
  }

  function deleteDraft() {
    pending = null;
    dropDraft(DRAFT);
    if (refs.draft) refs.draft.remove();
    refs.draft = null;
    persistDraft();
  }

  function payload() {
    const d = clone(data) || {};
    const f = form;
    const free = parseIntField(f.free_from);
    return {
      contacts: {
        ...(d.contacts || {}),
        whatsapp: normPhone(f.whatsapp), instagram: nick(f.instagram), pinterest: nick(f.pinterest),
        email: f.email.trim(), map_url: f.map_url.trim(), address: triTrim(f.address), hours: triTrim(f.hours),
      },
      delivery: {
        ...(d.delivery || {}),
        free_from: Number.isInteger(free) ? free : null,
        kz: f.kz.map((o) => ({ ...(clone(o.extra) || {}), price: parseIntField(o.price), name: triTrim(o.name), days: triTrim(o.days) })),
        world: triTrim(f.world),
      },
      promo: triTrim(f.promo),
      seller: { ...(d.seller || {}), name: f.seller_name.trim(), bin: digits(f.seller_bin) },
      sha,
    };
  }

  // ——— Экран ———

  function changed() {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (dead || !refs.state) return;
      const dirty = guard.dirty();
      refs.state.textContent = dirty ? 'Есть несохранённые изменения' : 'Всё сохранено';
      refs.state.classList.toggle('is-dirty', dirty);
      refs.cancelBtn.disabled = !dirty || saving;               // отменять нечего — кнопка выключена
      refs.saveBtn.classList.toggle('is-idle', !dirty && !saving);
      refs.promoPv.textContent = form.promo.ru.trim() || 'Текст полосы';
      refs.promoPv.classList.toggle('is-empty', !form.promo.ru.trim());
      refs.sellerPv.textContent = sellerLine();
      renderDlvPv();
      persistDraft();
    });
  }

  /** «На сайте будет так»: доставка по Казахстану, как её рисует сайт (themes/v4.py → delivery). */
  function renderDlvPv() {
    if (!refs.dlvPv) return;
    const rows = form.kz.filter((o) => o.name.ru.trim()).map((o) => {
      const p = parseIntField(o.price);
      return h('li', { class: 'dlvpv__i' },
        h('span', { class: 'dlvpv__n' }, o.name.ru.trim()),
        h('span', { class: 'dlvpv__p tnum' }, Number.isInteger(p) ? (p === 0 ? 'бесплатно' : money(p)) : '— ₸'),
        o.days.ru.trim() && h('span', { class: 'dlvpv__d' }, o.days.ru.trim()));
    });
    const free = parseIntField(form.free_from);
    refs.dlvPv.replaceChildren(...[   // пустые значения (false, null) не выводим — иначе браузер пишет их словами
      h('p', { class: 'seller-box__t' }, 'На сайте будет так:'),
      rows.length ? h('ul', { class: 'dlvpv' }, rows) : h('p', { class: 'dlvpv__none' }, 'Способов нет — на сайте будет общий текст про доставку.'),
      Number.isInteger(free) && free > 0 && h('p', { class: 'dlvpv__free' }, `От ${money(free)} доставка по Казахстану бесплатная.`),
    ].filter(Boolean));
  }

  function sellerLine() {
    const n = form.seller_name.trim(), b = digits(form.seller_bin);
    return n && b ? `Продавец: ${n}, ИИН/БИН ${b}.` : 'Пока не заполнены оба поля — в подвале этой строки нет.';
  }

  function bind(key, opts = {}) {
    return input({
      id: `s-${key}`, value: form[key], ...opts,
      oninput: (v) => {
        form[key] = v;
        changed();
      },
    });
  }

  /** Поле на русском + строка переводов (қаз/eng) для общего свёрнутого блока раздела.
   *  orig — сохранённый текст: если русский поменяли, а перевод остался прежним, под полем — подсказка. */
  function triParts({ name, label, key, obj, hint, multi = false, placeholder = '', req = false, opt = false, trLabel = '', orig = null }) {
    const target = obj || form[key];
    const k = uid();
    const inputs = {};
    const make = (l) => {
      const id = `s-${k}-${l}`;
      const onin = (v) => {
        target[l] = v;
        warn.update();
        changed();
      };
      const ph = l === 'ru' ? placeholder : target.ru;
      const lang = LANG_ATTR[l];
      inputs[l] = multi ? textarea({ id, value: target[l], rows: 2, placeholder: ph, oninput: onin, lang })
        : input({ id, value: target[l], placeholder: ph, oninput: onin, lang });
      return inputs[l];
    };
    const warn = staleTr({
      orig: orig || tri(),
      cur: () => target,
      onOpen: () => {
        const d = inputs.kz.closest('details');
        if (d) d.open = true;
        inputs.kz.scrollIntoView({ block: 'center' });
        inputs.kz.focus({ preventScroll: true });
      },
      onClear: () => {
        for (const l of ['kz', 'en']) {
          target[l] = '';
          inputs[l].value = '';
        }
        changed();
      },
    });
    const ru = make('ru');
    const pair = ['kz', 'en'].map((l) => field({ name: `${name}.${l}`, label: LANG_NAME[l], control: make(l), cls: 'fld--tr' }));
    ru.addEventListener('input', () => {
      for (const f of pair) {
        const c = f.querySelector('input, textarea');
        if (c) c.placeholder = ru.value.trim();
      }
    });
    warn.update();
    return {
      field: field({ name, label, hint, req, opt, control: ru, below: warn }),
      tr: h('div', { class: 'tr__row' }, h('p', { class: 'tr__l' }, trLabel || label), pair),
    };
  }

  /** Свёрнутый блок «Казахский и английский» с переводами нескольких полей раздела. */
  function trFold(rows, cls = '') {
    const f = fold({ title: 'Казахский и английский', hint: 'необязательно · пусто — на сайте покажется русский текст', cls: `fold--tr ${cls}` }, rows);
    f.addEventListener('toggle', () => {
      if (f.open) for (const c of f.querySelectorAll('textarea')) c.fit && c.fit();
    });
    return f;
  }

  function build() {
    refs.kz = h('div', { class: 'dl' });
    refs.state = h('p', { class: 'savebar__state', 'aria-live': 'polite' }, 'Всё сохранено');
    refs.saveL = h('span', null, 'Сохранить и опубликовать');
    refs.saveBtn = h('button', { type: 'submit', class: 'btn btn--ink savebar__save' }, refs.saveL);
    refs.cancelBtn = h('button', { type: 'button', class: 'btn btn--line savebar__cancel', onclick: onCancel, disabled: true }, 'Отменить правки');
    refs.promoPv = h('span', { class: 'promo-pv__t' });
    refs.sellerPv = h('p', { class: 'seller-pv' });
    refs.dlvPv = h('div', { class: 'seller-box dlvpv-box' });
    refs.draft = pending ? draftBar({ at: pending.at, onRestore: restoreDraft, onDrop: deleteDraft }) : null;

    const wa = bind('whatsapp', { type: 'tel', inputmode: 'tel', autocomplete: 'off', placeholder: '+7 706 723 23 49' });
    wa.addEventListener('blur', () => {
      const d = normPhone(wa.value);
      if (d.length === 11) {
        wa.value = showPhone(d);
        form.whatsapp = wa.value;
      }
    });
    const nickInput = (key, ph) => {
      const el = bind(key, { placeholder: ph, autocomplete: 'off' });
      el.setAttribute('autocapitalize', 'off');
      el.setAttribute('spellcheck', 'false');
      el.addEventListener('blur', () => {
        const v = nick(el.value);
        if (v !== el.value) {
          el.value = v;
          form[key] = v;
          changed();
        }
      });
      return h('div', { class: 'unit unit--pre' }, h('span', { class: 'unit__u', 'aria-hidden': 'true' }, '@'), el);
    };
    const free = bind('free_from', { inputmode: 'numeric', placeholder: 'например, 70 000' });
    free.addEventListener('blur', () => {
      const n = parseIntField(free.value);
      if (Number.isInteger(n)) {
        free.value = groupDigits(n);
        form.free_from = free.value;
      }
    });

    const saved = toForm(data);   // как сейчас на сайте — для подсказки «перевод остался от прежнего текста»
    const world = triParts({ name: 'delivery.world', label: 'Текст для покупателей из других стран', trLabel: 'Доставка по миру', key: 'world', orig: saved.world, multi: true, req: true, placeholder: 'Стоимость и сроки уточняйте у нас в WhatsApp.', hint: 'Одна-две фразы — видны на странице товара в «доставке».' });
    const address = triParts({ name: 'contacts.address', label: 'Адрес магазина', key: 'address', orig: saved.address, req: true, placeholder: 'Алматы, ул. Кабанбай батыра, 96', hint: 'Как он должен стоять на сайте, без точки в конце.' });
    const hours = triParts({ name: 'contacts.hours', label: 'Часы работы', key: 'hours', orig: saved.hours, req: true, placeholder: 'Часы работы: 11:00–20:00', hint: 'Как будет написано на сайте, целиком: «Часы работы: 11:00–20:00».' });
    const promo = triParts({ name: 'promo', label: 'Текст полосы', key: 'promo', orig: saved.promo, req: true, placeholder: 'Дарим 2 000 ₸ на первый заказ', hint: 'Короткая фраза: на телефоне она должна поместиться в одну-две строки.' });
    const formEl = h('form', { class: 'st__form', novalidate: true, onsubmit: (e) => { e.preventDefault(); save(); } },
      section({ title: 'Доставка по Казахстану', id: 'st-kz', intro: 'Способы доставки — так они видны на странице товара и в разделе «Покупателям».' },
        h('div', { class: 'fld fld--vars', 'data-field': 'delivery.kz' }, h('p', { class: 'fld__err', hidden: true }), refs.kz,
          refs.addKz = h('button', { type: 'button', class: 'btn btn--line btn--add', onclick: addMethod }, icon(I.plus), 'Добавить способ доставки')),
        field({ name: 'delivery.free_from', label: 'Бесплатная доставка от', opt: true, control: withUnit(free, '₸'), hint: 'Сумма заказа, с которой доставка по Казахстану бесплатная. Пусто — бесплатной доставки нет.' }),
        refs.dlvPv),
      section({ title: 'Доставка по миру', id: 'st-world' }, world.field, trFold([world.tr])),
      section({ title: 'Контакты', id: 'st-contacts', intro: 'Видны в подвале сайта и в меню. На этот WhatsApp приходят заказы из корзины.' },
        field({ name: 'contacts.whatsapp', label: 'WhatsApp', req: true, control: wa, hint: 'Номер целиком, с кодом страны: +7 …' }),
        h('div', { class: 'row2' },
          field({ name: 'contacts.instagram', label: 'Instagram', req: true, control: nickInput('instagram', 'attre.studio'), hint: 'Только ник, без ссылки. Можно вставить ссылку — оставим ник.' }),
          field({ name: 'contacts.pinterest', label: 'Pinterest', req: true, control: nickInput('pinterest', 'attrestudio'), hint: 'Только ник, без ссылки.' })),
        field({ name: 'contacts.email', label: 'E-mail', req: true, control: bind('email', { type: 'email', inputmode: 'email', placeholder: 'attre.studio@gmail.com' }), hint: 'Виден внизу каждой страницы сайта.' }),
        field({ name: 'contacts.map_url', label: 'Ссылка на 2ГИС', req: true, control: bind('map_url', { type: 'url', inputmode: 'url', placeholder: 'https://2gis.kz/almaty/…' }), hint: 'Откройте магазин в 2ГИС → «Поделиться» → скопируйте ссылку (она начинается с https://) и вставьте сюда.' }),
        address.field, hours.field, trFold([address.tr, hours.tr])),
      section({ title: 'Полоса сверху сайта', id: 'st-promo', intro: 'Чёрная полоса над шапкой на всех страницах.' },
        h('div', { class: 'promo-pv', 'aria-hidden': 'true' }, refs.promoPv),
        promo.field, trFold([promo.tr])),
      section({ title: 'Продавец', id: 'st-seller', intro: 'Для подвала сайта — требуется законом для интернет-магазина.' },
        field({ name: 'seller.name', label: 'ИП или ТОО с названием', control: bind('seller_name', { placeholder: 'например, ИП Иванова А. Б.', maxlength: 120 }), hint: 'Заполните оба поля — или оставьте оба пустыми, пока данных нет.' }),
        field({ name: 'seller.bin', label: 'ИИН или БИН', control: bind('seller_bin', { inputmode: 'numeric', placeholder: '12 цифр', maxlength: 14 }), hint: '12 цифр. Для ИП — ИИН, для ТОО — БИН.' }),
        h('div', { class: 'seller-box' }, h('p', { class: 'seller-box__t' }, 'В подвале сайта будет так:'), refs.sellerPv)),
      h('div', { class: 'savebar' }, refs.state, h('div', { class: 'savebar__btns' }, refs.cancelBtn, refs.saveBtn)));
    refs.form = formEl;
    autoClear(formEl);
    formEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.tagName === 'INPUT') e.preventDefault();
    });
    root.replaceChildren(...[
      h('div', { class: 'st__head' }, h('h1', { class: 'st__h' }, 'Магазин и доставка'),
        h('p', { class: 'st__sub' }, 'Контакты, доставка и строки, которые видны на всех страницах сайта.')),
      refs.draft,
      formEl,
    ].filter(Boolean));
    placeToasts();
    renderMethods();
    changed();
  }

  function renderMethods() {
    refs.kz.replaceChildren(...form.kz.map((o, i) => method(o, i)));
    if (refs.addKz) refs.addKz.hidden = form.kz.length >= 10;
    if (!form.kz.length) refs.kz.append(h('p', { class: 'dl__none' }, 'Способов доставки нет — на сайте будет общий текст про доставку.'));
  }

  function method(o, i) {
    const price = input({
      id: `s-kz-${o.uid}-price`, value: o.price, inputmode: 'numeric', placeholder: 'например, 4 000',
      oninput: (v) => {
        o.price = v;
        changed();
      },
    });
    price.addEventListener('blur', () => {
      const n = parseIntField(price.value);
      if (Number.isInteger(n)) {
        price.value = groupDigits(n);
        o.price = price.value;
      }
    });
    const name = triParts({ name: `delivery.kz.${i}.name`, label: 'Название', req: true, obj: o.name, orig: tri(o.extra && o.extra.name), placeholder: 'например, курьер до двери', hint: 'Как способ называется на сайте.' });
    const days = triParts({ name: `delivery.kz.${i}.days`, label: 'Срок', opt: true, obj: o.days, orig: tri(o.extra && o.extra.days), placeholder: 'например, 2–3 рабочих дня', hint: 'Сколько ждать доставку.' });
    return h('div', { class: 'dl__i', 'data-field': `delivery.kz.${i}`, 'data-uid': o.uid },
      h('div', { class: 'dl__head' }, h('h3', { class: 'dl__t' }, `Способ ${i + 1}`),
        h('button', { type: 'button', class: 'link link--danger', onclick: () => removeMethod(o) }, icon(I.trash), 'Удалить')),
      h('p', { class: 'fld__err', hidden: true }),
      name.field,
      h('div', { class: 'row2' },
        field({ name: `delivery.kz.${i}.price`, label: 'Цена', req: true, control: withUnit(price, '₸'), hint: 'Бесплатно — впишите 0 (на сайте будет «бесплатно»).' }),
        days.field),
      trFold([name.tr, days.tr], 'fold--card'));
  }

  function addMethod() {
    const o = { uid: uid(), name: tri(), days: tri(), price: '', extra: {} };
    form.kz.push(o);
    renderMethods();
    changed();
    const el = refs.kz.querySelector(`[data-uid="${o.uid}"]`);
    if (el) {
      el.scrollIntoView({ block: 'center' });
      const f = el.querySelector('input');
      if (f) setTimeout(() => f.focus({ preventScroll: true }), 200);
    }
  }

  async function removeMethod(o) {
    const name = o.name.ru.trim();
    const ok = await dialog({
      title: name ? `Удалить способ «${name}»?` : 'Удалить этот способ доставки?',
      text: 'Он пропадёт с сайта, когда вы нажмёте «Сохранить и опубликовать».',
      buttons: [{ label: 'Не удалять', value: false, kind: 'ink' }, { label: 'Удалить способ', value: true, kind: 'danger-line' }],
      dismiss: false,
    });
    if (!ok) return;
    form.kz.splice(form.kz.indexOf(o), 1);
    renderMethods();
    changed();
  }

  function validate() {
    const errs = [];
    const add = (f, msg) => errs.push({ field: f, msg });
    const f = form;
    const wa = normPhone(f.whatsapp);
    if (!wa) add('contacts.whatsapp', 'Впишите номер WhatsApp — на него приходят заказы.');
    else if (!/^7\d{10}$/.test(wa)) add('contacts.whatsapp', 'Номер — 11 цифр и начинается с 7, например +7 706 723 23 49.');
    const ig = nick(f.instagram);
    if (!ig) add('contacts.instagram', 'Впишите ник в Instagram, например attre.studio.');
    else if (!/^[A-Za-z0-9._]{1,30}$/.test(ig)) add('contacts.instagram', 'Только ник: латинские буквы, цифры, точка и подчёркивание.');
    const pin = nick(f.pinterest);
    if (!pin) add('contacts.pinterest', 'Впишите ник в Pinterest, например attrestudio.');
    else if (!/^[A-Za-z0-9._-]{1,30}$/.test(pin)) add('contacts.pinterest', 'Только ник: латинские буквы, цифры, точка, дефис и подчёркивание.');
    const mail = f.email.trim();
    if (!mail) add('contacts.email', 'Впишите e-mail — он есть в подвале сайта.');
    else if (!/^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/.test(mail) || mail.length > 100) add('contacts.email', 'Проверьте e-mail — например attre.studio@gmail.com.');
    const map = f.map_url.trim();
    if (!map) add('contacts.map_url', 'Вставьте ссылку на магазин в 2ГИС.');
    else if (!/^https:\/\/\S+$/i.test(map) || map.length > 500) add('contacts.map_url', 'Вставьте ссылку целиком — она начинается с https://');
    const free = parseIntField(f.free_from);
    if (Number.isNaN(free)) add('delivery.free_from', 'Только цифры, например 70 000.');
    else if (free !== null && free > 10000000) add('delivery.free_from', 'Слишком большая сумма — проверьте.');
    if (f.kz.length > 10) add('delivery.kz', 'Не больше 10 способов доставки.');
    f.kz.forEach((o, i) => {
      if (!o.name.ru.trim()) add(`delivery.kz.${i}.name`, 'Впишите название способа.');
      const p = parseIntField(o.price);
      if (p === null) add(`delivery.kz.${i}.price`, 'Впишите цену доставки. Бесплатно — 0.');
      else if (Number.isNaN(p)) add(`delivery.kz.${i}.price`, 'Только цифры, например 4 000.');
      else if (p > 1000000) add(`delivery.kz.${i}.price`, 'Слишком большая цена — проверьте.');
      for (const l of LANGS) {
        if (o.name[l].trim().length > 100) add(l === 'ru' ? `delivery.kz.${i}.name` : `delivery.kz.${i}.name.${l}`, 'Название — не длиннее 100 знаков.');
        if (o.days[l].trim().length > 100) add(l === 'ru' ? `delivery.kz.${i}.days` : `delivery.kz.${i}.days.${l}`, 'Срок — не длиннее 100 знаков.');
      }
    });
    const need = [['world', 'delivery.world', 500, 'Напишите текст про доставку по миру.'], ['address', 'contacts.address', 200, 'Напишите адрес магазина.'],
      ['hours', 'contacts.hours', 100, 'Напишите часы работы, например «Часы работы: 11:00–20:00».'], ['promo', 'promo', 200, 'Напишите текст полосы.']];
    for (const [k, name, max, empty] of need) {
      if (!f[k].ru.trim()) add(name, empty);
      for (const l of LANGS) {
        const len = f[k][l].trim().length;
        if (len > max) add(l === 'ru' ? name : `${name}.${l}`, `Слишком длинный текст: ${len} ${plural(len, 'знак', 'знака', 'знаков')}, можно до ${max}.`);
      }
    }
    const bin = digits(f.seller_bin);
    const sname = f.seller_name.trim();
    if (f.seller_bin.trim() && bin.length !== 12) add('seller.bin', `ИИН или БИН — ровно 12 цифр (сейчас ${bin.length}).`);
    else if (sname && !bin) add('seller.bin', 'Впишите ИИН или БИН — без него строка о продавце в подвале не появится. Или очистите оба поля.');
    else if (bin && !sname) add('seller.name', 'Впишите ИП или ТОО с названием — или очистите оба поля.');
    return errs;
  }

  /** Пока идёт «Сохраняем…», поля не трогаются: после ответа форма перестраивается из сохранённого. */
  function setBusy(on) {
    refs.saveBtn.disabled = on;
    refs.saveL.textContent = on ? 'Сохраняем…' : 'Сохранить и опубликовать';
    root.classList.toggle('is-saving', on);
    for (const el of [refs.draft, ...refs.form.querySelectorAll(':scope > .sec')]) if (el) el.inert = on;
    if (on) refs.cancelBtn.disabled = true;
    else changed();
  }

  async function save() {
    if (saving) return;
    clearToasts();
    clearErrors(root);
    const errs = validate();
    if (errs.length) {
      focusField(showErrors(root, errs));
      toast(errorsText(errs, what), { kind: 'err', timeout: 7000 });
      return;
    }
    if (!guard.dirty()) {
      toast('Изменений нет — сохранять нечего.');
      return;
    }
    saving = true;
    setBusy(true);
    try {
      const r = await api('/api/settings', { method: 'PUT', body: payload() });
      if (r && r.commit) status.expect(r.commit);
      dropDraft(DRAFT);
      pending = null;
      const fresh = await api('/api/settings').catch(() => null);
      if (dead) return;
      if (fresh) {
        data = fresh;
        sha = fresh.sha || null;
        form = toForm(fresh);
        baseForm = toForm(fresh);
        base = snap();
        const y = window.scrollY;
        build();
        window.scrollTo(0, y);
      } else {
        base = snap();
        changed();
      }
      toast(status.tracked() ? 'Сохранено. Сайт обновится через 2–3 минуты.' : 'Сохранено.', { kind: 'ok' });
    } catch (e) {
      if (dead) return;
      if (e.status === 409) {
        const v = await dialog({
          title: 'Настройки изменили в другом месте',
          text: 'Пока вы редактировали, их сохранили с другого телефона или в другой вкладке. Если загрузить свежую версию, '
            + 'ваши несохранённые правки пропадут — длинный текст сначала скопируйте.',
          buttons: [{ label: 'Загрузить свежую версию', value: true, kind: 'ink' }, { label: 'Остаться и скопировать правки', value: false, kind: 'line' }],
          dismiss: false,
        });
        if (v) {
          dropDraft(DRAFT);
          pending = null;
          loading();
          load();
        }
      } else if (e.field && setError(root, e.field, e.message)) {
        focusField(root.querySelector('.is-err'));
        toast(e.message, { kind: 'err', timeout: 9000 });
      } else if (e.status !== 401) {
        toast(humane(e), { kind: 'err', timeout: 9000 });
      }
    } finally {
      saving = false;
      if (!dead && refs.saveBtn) setBusy(false);
    }
  }

  async function onCancel() {
    if (!guard.dirty()) return;            // кнопка и так выключена, пока ничего не меняли
    const ok = await dialog({
      title: 'Отменить правки?',
      text: 'Всё, что вы поменяли на этой странице после последнего сохранения, пропадёт — останется то, что сейчас на сайте.',
      buttons: [{ label: 'Продолжить редактирование', value: false, kind: 'ink' }, { label: 'Да, отменить правки', value: true, kind: 'danger-line' }],
      dismiss: false,
    });
    if (!ok) return;
    dropDraft(DRAFT);
    pending = null;
    form = toForm(data);
    base = snap();
    build();
    flash(root.querySelector('.st__head'));
    toast('Правки отменены.');
  }
}
