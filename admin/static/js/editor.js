// Редактор товара: основное · цена и наличие · цвета и фото · описание и размеры (+ переводы, свёрнуто).
// Цена и наличие (и скидка) — сразу после «Основного»: их меняют чаще всего, а цвета с фото длинные (у сохранённого
// товара они свёрнуты в строки «● молочный · кожа · 4 фото — Изменить»). Под названием — строка-оглавление.
// Справа (на телефоне — по кнопке) живое превью «Так будет на сайте». Внизу липкая панель «Сохранить и опубликовать».
// Всё введённое и не сохранённое лежит в черновике на этом устройстве (draft.js): Safari на iPhone не переспрашивает
// при закрытии вкладки и сам перезагружает её после «Камеры». Неизвестные поля товара сохраняются как были;
// старый товар без variants переводится на цвета (старые фото → один цвет).

import { api, humane } from './api.js';
import { h, icon, flash, reveal } from './dom.js';
import { readDraft, writeDraft, dropDraft, draftBar } from './draft.js';
import {
  field, input, textarea, withUnit, radios, toggles, switcher, check, section, fold, staleTr,
  showErrors, clearErrors, clearError, setError, autoClear, focusField, errorsText, PLAIN, LANG_ATTR,
} from './form.js';
import { I } from './icons.js';
import { getMeta, loadMeta, catLabel, productUrl, paletteKey } from './meta.js';
import { Photos, imgFromPath, badText } from './photos.js';
import { createPreview } from './preview.js';
import { setLeaveGuard, clearLeaveGuard, go, replaceUrl } from './router.js';
import * as status from './status.js';
import { swatch } from './swatch.js';
import { dialog, sheet, toast, clearToasts, onScreen, placeToasts } from './ui.js';
import {
  clone, tri, triTrim, uid, cap, norm, groupDigits, parseIntField, parseNumField, numToField, plural, LANGS, txt, money, NBSP,
} from './util.js';

const LEGACY_FIELDS = ['images', 'colors', 'color', 'materials'];
const PATTERN_KEYS = new Set(['leopard', 'zebra', 'cow', 'dalmatian']);   // узоры кружочков сайта (themes/v4.py vswatch)
const LANG_NAME = { kz: 'Қазақша', en: 'English' };
const SALE_STEPS = [10, 20, 30];      // быстрые кнопки скидки, % от обычной цены

// Перечень в сообщении внизу: «Проверьте: название, категорию, фото.» (винительный падеж)
const WHAT = [
  [/^name(\.ru)?$/, 'название'], [/^name\./, 'перевод названия'], [/^cat$/, 'категорию'], [/^type/, 'тип'],
  [/^variants\.\d+\.color$/, 'цвет'], [/^variants\.\d+\.name/, 'название цвета'], [/^variants\.\d+\.images$/, 'фото'],
  [/^variants\.\d+\.material/, 'материал'], [/^variants/, 'цвета'], [/^price$/, 'цену'], [/^sale_price$/, 'цену со скидкой'],
  [/^stock$/, 'остаток'],
  [/^size/, 'размер'], [/^desc/, 'описание'], [/^strap/, 'ручки и ремни'],
];
const what = (f) => (WHAT.find(([re]) => re.test(String(f || ''))) || [null, null])[1];

export function mountEditor(main, { slug: startSlug }) {
  const meta = getMeta();
  const L = meta.limits;
  let slug = startSlug;
  let original = null;
  let sha = null;
  let form = null;
  let base = '';
  let baseForm = null;       // форма, как её открыли (до правок): с ней сравниваем «что поменял человек»
  let legacy = false;
  let saving = false;
  let dead = false;
  let saved = null;          // {commit, since, wasPub} — последнее сохранение, ждём его на сайте
  let siteUrl = '';          // адрес товара на сайте (сервер присылает его после сохранения)
  let photos = null;
  let preview = null;
  let sheetPv = null;
  let raf = 0;
  let draftKey = slug || 'new';
  let pending = null;        // черновик с прошлого раза: человек ещё не решил, восстановить его или удалить
  let mine = null;           // после «товар изменили в другом месте»: {from, base, groups} — несохранённые правки
  let typeRef = null;        // знакомый тип (из подсказок), на который сейчас похоже поле «Тип»
  let lastType = null;       // последний знакомый тип: его переводы можно заменить переводами нового
  let autoTr = null;         // переводы типа до нашей подстановки — вернуть, если тип дописали дальше
  let discarded = false;     // человек сам отказался от правок («Уйти без сохранения», удалил товар) — черновик не нужен
  // Группы полей — для «есть ли несохранённое», «какие поля поменял человек» и «вернуть мои правки»
  // (поверх свежей версии переносятся только они: правки второй основательницы в других полях остаются).
  const GROUPS = [
    { key: 'published', label: 'Показывать на сайте', get: (f) => f.published, show: (f) => (f.published ? 'да' : 'нет') },
    { key: 'name', label: 'Название', get: (f) => triTrim(f.name), show: (f) => f.name.ru.trim() },
    { key: 'type', label: 'Тип', get: (f) => triTrim(f.type), show: (f) => f.type.ru.trim() },
    { key: 'cat', label: 'Категория', get: (f) => f.cat, show: (f) => (meta.cat[f.cat] ? catLabel(meta.cat[f.cat]) : '') },
    { key: 'isNew', label: 'Новинка', get: (f) => f.isNew, show: (f) => (f.isNew ? 'да' : 'нет') },
    { key: 'popular', label: 'Популярное', get: (f) => f.popular, show: (f) => (f.popular ? 'да' : 'нет') },
    {
      key: 'avail', label: 'Наличие', fields: ['avail', 'stock'], get: (f) => [f.avail, f.avail === 'in' ? normInt(f.stock) : ''],
      show: (f) => ({ in: 'в наличии', soon: 'скоро в наличии', sold: 'продано' }[f.avail] + (f.avail === 'in' && f.stock.trim() ? `, остаток ${f.stock.trim()}` : '')),
    },
    { key: 'price', label: 'Цена', get: (f) => normInt(f.price), show: (f) => (Number.isInteger(parseIntField(f.price)) ? money(parseIntField(f.price)) : 'пусто (цена по запросу)') },
    // выключенная скидка — «нет», что бы ни лежало в поле (его помним, чтобы вернуть, но не сохраняем)
    {
      key: 'sale', label: 'Скидка', fields: ['sale', 'salePrice'], get: (f) => (f.sale ? normInt(f.salePrice) : null),
      show: (f) => (!f.sale ? 'нет' : Number.isInteger(parseIntField(f.salePrice)) ? `цена со скидкой ${money(parseIntField(f.salePrice))}` : f.salePrice.trim() || 'пусто'),
    },
    { key: 'desc', label: 'Описание', get: (f) => triTrim(f.desc), show: (f) => f.desc.ru.trim() },
    { key: 'strap', label: 'Ручки и ремни', get: (f) => triTrim(f.strap), show: (f) => f.strap.ru.trim() },
    { key: 'size', label: 'Размер', get: (f) => ['w', 'h', 'd'].map((k) => normNum(f.size[k])), show: (f) => ['w', 'h', 'd'].map((k) => f.size[k].trim() || '—').join(' × ') },
    {
      key: 'variants', label: 'Цвета и фото',
      get: (f) => f.variants.map((v) => [v.color, triTrim(v.name), v.mats, v.images.map((i) => i.ref || `new:${i.uid}`)]),
      show: (f) => f.variants.map((v) => (meta.pal[v.color] ? v.name.ru.trim() || meta.pal[v.color].name.ru : 'без цвета')).join(', '),
    },
  ];

  const refs = {};
  const root = h('div', { class: 'ed' });
  main.replaceChildren(root);
  const guard = {
    dirty: () => !!form && !dead && isDirty(),
    discard: () => {
      discarded = true;
      dropDraft(draftKey);
    },
  };
  setLeaveGuard(guard);
  const unsub = status.onChange(() => showNotice());
  const onHide = () => {
    if (document.visibilityState === 'hidden') persistDraft();   // ушли в «Камеру» или «Фото» — черновик сразу
  };
  document.addEventListener('visibilitychange', onHide);
  window.addEventListener('pagehide', persistDraft);
  loading();
  load();

  return { destroy, title: () => (form && form.name.ru.trim()) || (slug ? 'Товар' : 'Новый товар') };

  // ——— Загрузка ———

  function loading() {
    root.replaceChildren(h('div', { class: 'state state--load' }, h('span', { class: 'spin spin--l', 'aria-hidden': 'true' }),
      h('p', null, slug ? 'Открываем товар…' : 'Готовим новый товар…')));
    placeToasts();
  }

  function failed(e) {
    const missing = e.status === 404;
    root.replaceChildren(h('div', { class: 'state' },
      h('h1', { class: 'state__t' }, missing ? 'Такого товара нет' : 'Не получилось открыть товар'),
      h('p', { class: 'state__p' }, missing ? 'Возможно, его уже удалили, или в адресе ошибка.' : humane(e)),
      h('div', { class: 'state__btns' },
        !missing && h('button', { type: 'button', class: 'btn btn--ink', onclick: () => { loading(); load(); } }, 'Попробовать ещё раз'),
        h('a', { class: 'btn btn--line', href: '/', 'data-link': '' }, icon(I.back), 'Все товары'))));
  }

  async function load() {
    try {
      if (slug) {
        const r = await api(`/api/products/${encodeURIComponent(slug)}`);
        if (dead) return;
        original = (r && r.product) || {};
        sha = (r && r.sha) || null;
      } else {
        original = null;
        sha = null;
      }
      form = toForm(original);
      baseForm = toForm(original);
      base = snap();
      resetType();
      checkDraft();
      build();
    } catch (e) {
      if (!dead) failed(e);
    }
  }

  function destroy() {
    persistDraft();
    dead = true;
    clearLeaveGuard(guard);
    unsub();
    cancelAnimationFrame(raf);
    document.removeEventListener('visibilitychange', onHide);
    window.removeEventListener('pagehide', persistDraft);
    if (photos) photos.destroy();
  }

  // ——— Данные товара ⇄ форма ———

  function newVariant() {
    return { uid: uid(), color: '', name: tri(), mats: [], images: [], extra: {}, open: true };
  }

  function guessColor(cols) {
    for (const c of Array.isArray(cols) ? cols : []) {
      const k = paletteKey(c);
      if (k) return k;
    }
    return '';
  }

  function pathsOf(list) {
    return (Array.isArray(list) ? list : []).map((x) => (x && typeof x === 'object' ? x.image : x)).filter((x) => typeof x === 'string' && x);
  }

  function fromVariant(v) {
    const mats = Array.isArray(v.materials) && v.materials.length ? v.materials.filter((k) => typeof k === 'string') : v.material ? [v.material] : [];
    return { uid: uid(), color: typeof v.color === 'string' ? v.color : '', name: tri(v.name), mats, images: pathsOf(v.images).map(imgFromPath), extra: clone(v), open: false };
  }

  function toForm(p) {
    legacy = false;
    if (!p) {
      return {
        published: true, name: tri(), type: tri(), cat: meta.leafCats.length === 1 ? meta.leafCats[0].key : '',
        isNew: false, popular: false, avail: 'in', price: '', sale: false, salePrice: '', stock: '', desc: tri(), strap: tri(),
        size: { w: '', h: '', d: '' }, variants: [newVariant()],
      };
    }
    // скидка из файла — как есть (даже больше цены: проверка перед сохранением объяснит); 0 и минус — «скидки нет»
    const sale = typeof p.sale_price === 'number' && p.sale_price > 0;
    let variants = Array.isArray(p.variants) && p.variants.length ? p.variants.filter((v) => v && typeof v === 'object').map(fromVariant) : null;
    if (!variants || !variants.length) {
      legacy = true;
      const mats = (Array.isArray(p.materials) ? p.materials : p.material ? [p.material] : []).filter((k) => typeof k === 'string' && k);
      variants = [{ uid: uid(), color: guessColor(p.colors), name: tri(), mats, images: pathsOf(p.images).map(imgFromPath), extra: {}, open: true }];
    }
    for (const v of variants) if (!palOf(v) || !v.images.length) v.open = true;   // неполный цвет — сразу раскрыт
    const stock = typeof p.stock === 'number' ? p.stock : null;
    const size = p.size && typeof p.size === 'object' ? p.size : {};
    return {
      published: p.published !== false,
      name: tri(p.name), type: tri(p.type), cat: typeof p.cat === 'string' ? p.cat : '',
      isNew: !!p.new, popular: !!p.popular,
      avail: stock === 0 ? 'sold' : p.soon ? 'soon' : 'in',
      price: typeof p.price === 'number' ? groupDigits(p.price) : '',
      sale, salePrice: sale ? groupDigits(p.sale_price) : '',
      stock: stock && stock > 0 ? String(stock) : '',
      desc: tri(p.desc), strap: tri(p.strap),
      size: { w: numToField(size.w), h: numToField(size.h), d: numToField(size.d) },
      variants,
    };
  }

  function normInt(s) {
    const n = parseIntField(s);
    return Number.isNaN(n) ? `?${s}` : n;
  }

  function normNum(s) {
    const n = parseNumField(s);
    return Number.isNaN(n) ? `?${s}` : n;
  }

  /** Слепок формы для «есть ли несохранённое» (пробелы по краям и формат цены не считаются изменением). */
  function snapOf(f) {
    return JSON.stringify(GROUPS.map((g) => g.get(f)));
  }

  function snap() {
    return snapOf(form);
  }

  function isDirty() {
    return snap() !== base;
  }

  /** Какие группы полей в from отличаются от b. */
  function changedGroups(from, b) {
    return GROUPS.filter((g) => JSON.stringify(g.get(from)) !== JSON.stringify(g.get(b)));
  }

  /** Перенести в target только эти группы полей из from. */
  function applyGroups(target, from, groups) {
    for (const g of groups) {
      for (const k of g.fields || [g.key]) target[k] = k === 'variants' ? from[k] : clone(from[k]);
    }
    return target;
  }

  function buildProduct() {
    const p = original ? clone(original) : {};
    delete p.slug;
    if (legacy) for (const k of LEGACY_FIELDS) delete p[k];
    p.published = form.published;
    p.cat = form.cat;
    p.name = triTrim(form.name);
    p.type = triTrim(form.type);
    p.new = form.isNew;
    p.popular = form.popular;
    p.soon = form.avail === 'soon';
    const pr = parseIntField(form.price);
    p.price = Number.isInteger(pr) ? pr : null;
    const sp = parseIntField(form.salePrice);
    p.sale_price = form.sale && Number.isInteger(sp) ? sp : null;     // null — скидки нет, сервер уберёт поле из файла
    if (form.avail === 'sold') p.stock = 0;
    else {
      const st = parseIntField(form.stock);
      p.stock = Number.isInteger(st) && st > 0 ? st : null;
    }
    p.desc = triTrim(form.desc);
    p.strap = triTrim(form.strap);
    const size = p.size && typeof p.size === 'object' && !Array.isArray(p.size) ? p.size : {};
    const num = (s) => {
      const x = parseNumField(s);
      return Number.isFinite(x) ? x : null;
    };
    p.size = { ...size, w: num(form.size.w), h: num(form.size.h), d: num(form.size.d) };
    p.variants = form.variants.map((v) => {
      const o = clone(v.extra) || {};
      o.color = v.color;
      const nm = triTrim(v.name);
      if (nm.ru || nm.kz || nm.en) o.name = nm;
      else delete o.name;
      if (v.mats.length > 1) {   // несколько материалов (так было в старом товаре) — оставляем как было
        o.materials = v.mats.slice();
        delete o.material;
      } else {
        delete o.materials;
        if (v.mats.length) o.material = v.mats[0];
        else delete o.material;
      }
      o.images = v.images.map((i) => i.ref);
      return o;
    });
    return p;
  }

  // ——— Черновик на этом устройстве ———

  function draftShape(f) {
    return {
      published: f.published, name: f.name, type: f.type, cat: f.cat, isNew: f.isNew, popular: f.popular, avail: f.avail,
      price: f.price, sale: f.sale, salePrice: f.salePrice, stock: f.stock, desc: f.desc, strap: f.strap, size: f.size,
      variants: f.variants.map((v) => ({
        color: v.color, name: v.name, mats: v.mats, extra: v.extra, open: !!v.open,
        // фото, которые ещё грузятся или не подошли, в черновик не попадают: файла с телефона в нём не сохранить
        images: v.images.filter((i) => i.state === 'ok' && i.ref).map((i) => ({ ref: i.ref, thumb: i.thumb || '' })),
      })),
    };
  }

  function thumbOf(ref) {
    const up = /^upload:(up_[0-9a-f]{20})$/.exec(ref);
    return up ? `/api/uploads/${up[1]}` : imgFromPath(ref).thumb;
  }

  function fromShape(f) {
    if (!f || typeof f !== 'object') return null;
    const s = (x) => (typeof x === 'string' ? x : '');
    const size = f.size && typeof f.size === 'object' ? f.size : {};
    const vs = (Array.isArray(f.variants) ? f.variants : []).filter((v) => v && typeof v === 'object').map((v) => ({
      uid: uid(), color: s(v.color), name: tri(v.name),
      mats: Array.isArray(v.mats) ? v.mats.filter((k) => typeof k === 'string') : [],
      extra: v.extra && typeof v.extra === 'object' && !Array.isArray(v.extra) ? v.extra : {}, open: v.open !== false,
      images: (Array.isArray(v.images) ? v.images : []).filter((i) => i && typeof i.ref === 'string' && i.ref)
        .map((i) => ({ uid: uid(), ref: i.ref, thumb: (typeof i.thumb === 'string' && i.thumb) || thumbOf(i.ref), state: 'ok' })),
    }));
    for (const v of vs) if (!meta.pal[v.color] || !v.images.length) v.open = true;
    return {
      published: f.published !== false, name: tri(f.name), type: tri(f.type), cat: s(f.cat), isNew: !!f.isNew, popular: !!f.popular,
      avail: ['in', 'soon', 'sold'].includes(f.avail) ? f.avail : 'in', price: s(f.price),
      sale: f.sale === true, salePrice: s(f.salePrice), stock: s(f.stock),
      desc: tri(f.desc), strap: tri(f.strap), size: { w: s(size.w), h: s(size.h), d: s(size.d) },
      variants: vs.length ? vs : [newVariant()],
    };
  }

  /** Черновик с прошлого раза, если в нём есть что-то, чего нет в открытом товаре. */
  function checkDraft() {
    pending = null;
    const d = readDraft(draftKey);
    if (!d) return;
    const f = fromShape(d.form);
    if (!f || snapOf(f) === base) {
      dropDraft(draftKey);
      return;
    }
    pending = d;
  }

  function persistDraft() {
    if (!form || dead || !baseForm || discarded) return;
    if (isDirty()) writeDraft(draftKey, { form: draftShape(form), base: draftShape(baseForm), sha, name: form.name.ru.trim() });
    else if (pending) writeDraft(draftKey, { form: pending.form, base: pending.base, sha: pending.sha, name: pending.name }, pending.at);
    else dropDraft(draftKey);
  }

  /** Восстановить черновик. Переносятся только поля, которые человек поменял (против той версии, с которой
   *  начинал): если товар тем временем сохраняли на другом телефоне, его правки в других полях не пропадут. */
  function restoreDraft() {
    const d = pending;
    pending = null;
    const from = d && fromShape(d.form);
    if (!from) return;
    const was = fromShape(d.base) || toForm(null);
    form = applyGroups(toForm(original), from, changedGroups(from, was));
    resetType();
    build();
    persistDraft();
    toast('Черновик восстановлен. Проверьте и нажмите «Сохранить и опубликовать».', { kind: 'ok' });
  }

  function deleteDraft() {
    pending = null;
    dropDraft(draftKey);
    if (refs.draft) refs.draft.remove();
    refs.draft = null;
    persistDraft();
  }

  // ——— Подписи ———

  function palOf(v) {
    return meta.pal[v.color] || null;
  }

  /** Кружочек цвета как на сайте: свой hex или узор у цвета товара важнее палитры (core.clean_variants). */
  function swatchOf(v) {
    const p = palOf(v);
    if (!p) return null;
    const x = v.extra || {};
    const hex = typeof x.hex === 'string' && /^#[0-9a-f]{6}$/i.test(x.hex.trim()) ? x.hex.trim() : p.hex;
    const pattern = PATTERN_KEYS.has(x.pattern) ? x.pattern : p.pattern;
    return { hex, pattern };
  }

  function shadeName(v) {
    return v.name.ru.trim() || (palOf(v) ? palOf(v).name.ru : '');
  }

  function label(v) {
    return shadeName(v) || `цвет ${form.variants.indexOf(v) + 1}`;
  }

  function titleText() {
    return form.name.ru.trim() || (slug ? 'Без названия' : 'Новый товар');
  }
  function subText() {
    const c = meta.cat[form.cat];
    return [original && original.id ? `арт. ${original.id}` : '', c ? catLabel(c) : ''].filter(Boolean).join(' · ');
  }

  /** Сохранённое состояние «Показывать на сайте»: true / false, null — товар ещё не сохраняли. */
  function wasPublished() {
    return original ? original.published !== false : null;
  }

  /** Подсказка под переключателем — по сохранённому состоянию: пока не сохранили, сайт показывает прежнее. */
  function pubHint(on) {
    const was = wasPublished();
    if (was === null) return on ? 'Выключите, чтобы спрятать товар, не удаляя.' : 'Товар сохранится скрытым — на сайте его не будет.';
    if (on) return was ? 'Выключите, чтобы спрятать товар, не удаляя.' : 'После сохранения товар появится на сайте.';
    return was ? 'После сохранения товар пропадёт с сайта (здесь он останется).' : 'Товар скрыт — на сайте его не видно.';
  }

  // ——— Экран ———

  /** Подсказка под русским полем: русский поменяли, а казахский и английский остались от прежнего текста. */
  function trWarn(key) {
    const w = staleTr({
      orig: original ? tri(original[key]) : tri(),
      cur: () => form[key],
      onOpen: () => {
        const c = refs.tr && refs.tr[`${key}.kz`];
        if (!c) return;
        const d = c.closest('details');
        if (d) d.open = true;
        if (c.fit) c.fit();
        c.scrollIntoView({ block: 'center' });
        c.focus({ preventScroll: true });
      },
      onClear: () => {
        for (const l of ['kz', 'en']) {
          form[key][l] = '';
          const c = refs.tr && refs.tr[`${key}.${l}`];
          if (c) c.value = '';
        }
        changed();
      },
    });
    refs.warn[key] = w;
    w.update();
    return w;
  }

  function build() {
    if (photos) photos.destroy();
    refs.warn = {};
    photos = new Photos({
      variants: () => form.variants, changed, label, palette: (k) => meta.pal[k] || null, max: L.photos_max,
      bad: badPhotos, refresh: refreshRow,
    });
    preview = createPreview();

    refs.title = h('h1', { class: 'ed__h' }, titleText());
    refs.sub = h('p', { class: 'ed__sub' }, subText());
    refs.pub = switcher({
      id: 'f-published', checked: form.published, label: 'Показывать на сайте', hint: pubHint,
      onchange: (v) => {
        form.published = v;
        changed();
      },
    });
    refs.notice = h('div', { class: 'notice', role: 'status', 'aria-live': 'polite', hidden: true });
    refs.draft = pending ? draftBar({
      at: pending.at, what: slug ? 'черновик' : `новый товар${pending.name ? ` «${pending.name}»` : ''}`,
      note: pending.sha && sha && pending.sha !== sha
        ? 'Пока черновик лежал, этот товар сохраняли ещё раз: восстановятся только поля, которые вы меняли.' : '',
      onRestore: restoreDraft, onDrop: deleteDraft,
    }) : null;
    const head = h('div', { class: 'ed__top' },
      h('a', { class: 'back', href: '/', 'data-link': '' }, icon(I.back), 'Все товары'),
      h('div', { class: 'ed__ttl' }, refs.title, refs.sub, buildToc()),
      refs.draft,
      mineNote(),
      refs.notice,
      refs.pubRow = h('div', { class: 'ed__pubrow', 'data-field': 'published' }, refs.pub, h('p', { class: 'fld__err', hidden: true })),
      h('button', { type: 'button', class: 'btn btn--line ed__pvbtn', onclick: openPreview }, icon(I.eye), 'Посмотреть, как на сайте'));

    refs.form = h('form', { class: 'ed__form', novalidate: true, onsubmit: (e) => { e.preventDefault(); save(); } },
      buildMain(), buildPrice(), buildColors(), buildDesc(), slug && buildDanger(), buildSavebar());
    autoClear(refs.form);
    refs.form.addEventListener('keydown', (e) => {   // Enter в однострочном поле не отправляет форму случайно
      if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type !== 'file') e.preventDefault();
    });

    const aside = h('aside', { class: 'ed__pv', 'aria-labelledby': 'pv-t' },
      h('h2', { class: 'sec__t', id: 'pv-t' }, 'Так будет на сайте'),
      h('p', { class: 'ed__pvhint' }, 'Меняется сразу, пока вы печатаете. Нажмите на кружочки — фото поменяются.'),
      preview.el);
    root.replaceChildren(head, h('div', { class: 'ed__cols' }, refs.form, aside));
    placeToasts();
    updatePreview();
    updateState();
    showNotice();
  }

  /** Строка-оглавление под названием: на телефоне форма длинная — сразу к нужному разделу. */
  function buildToc() {
    refs.tocColors = h('span', null, `Цвета (${form.variants.length})`);
    const go2 = (id) => () => {
      const el = document.getElementById(id);
      if (!el) return;
      reveal(el, { block: 'start' });
      const t = el.querySelector('.sec__t');
      if (t) {
        t.setAttribute('tabindex', '-1');
        t.focus({ preventScroll: true });
      }
    };
    return h('nav', { class: 'toc', 'aria-label': 'Разделы товара' },
      h('button', { type: 'button', class: 'toc__a', onclick: go2('sec-main') }, 'Основное'),
      h('button', { type: 'button', class: 'toc__a', onclick: go2('sec-price') }, 'Цена и наличие'),
      h('button', { type: 'button', class: 'toc__a', onclick: go2('sec-colors') }, refs.tocColors),
      h('button', { type: 'button', class: 'toc__a', onclick: go2('sec-desc') }, 'Описание'));
  }

  function buildMain() {
    const name = input({
      id: 'f-name', value: form.name.ru, maxlength: 120, placeholder: 'например, Altea', enterkeyhint: 'next',
      oninput: (v) => {
        form.name.ru = v;
        refs.title.textContent = titleText();
        trPlaceholders();
        changed();
      },
    });
    const cat = radios({
      options: meta.leafCats.map((c) => ({ value: c.key, label: catLabel(c) })), value: form.cat, cls: 'chips chips--big',
      onchange: (v) => {
        form.cat = v;
        refs.sub.textContent = subText();
        changed();
      },
    });
    refs.type = input({
      id: 'f-type', value: form.type.ru, placeholder: 'например, тоут', enterkeyhint: 'next', ...PLAIN,
      oninput: (v) => {
        form.type.ru = v;
        syncType(false);
        trPlaceholders();
        renderTypes();
        changed();
      },
      onblur: () => syncType(true),
    });
    refs.types = h('div', { class: 'sugg', role: 'group', 'aria-label': 'Типы, которые уже есть' });
    renderTypes();
    const id = original && original.id;
    return section({ title: 'Основное', id: 'sec-main' },
      field({ name: 'name', label: 'Название', req: true, control: name, below: trWarn('name'), hint: 'Как на сайте и в сообщении в WhatsApp. До 60 знаков.' }),
      field({ name: 'cat', label: 'Категория', req: true, control: cat, id: 'f-cat', hint: 'Раздел каталога, в котором товар будет на сайте.' }),
      field({ name: 'type', label: 'Тип', opt: true, control: refs.type, after: refs.types, below: trWarn('type'), hint: 'Нажмите подсказку или впишите свой. Покупатели видят тип под названием.' }),
      field({
        label: 'Артикул', id: 'f-id',
        control: h('p', { class: 'ed__art' }, id ? h('span', { class: 'tnum' }, id) : h('span', { class: 'mute' }, 'появится сам после сохранения')),
        hint: id ? 'Номер товара, по нему ищут в WhatsApp. Не меняется.' : null,
      }));
  }

  function renderTypes() {
    const q = norm(form.type.ru);
    const exact = meta.types.some((t) => norm(t.ru) === q);
    const list = exact ? [] : meta.types.filter((t) => !q || norm(t.ru).includes(q)).slice(0, 14);
    refs.types.replaceChildren(...list.map((t) => h('button', { type: 'button', class: 'chip chip--s', onclick: () => pickType(t) }, t.ru)));
    refs.types.hidden = !list.length;
  }

  function matchType(ru) {
    const q = norm(ru);
    return q ? meta.types.find((x) => norm(x.ru) === q) || null : null;
  }

  function resetType() {
    typeRef = form ? matchType(form.type.ru) : null;
    lastType = typeRef;
    autoTr = null;
  }

  /** Переводы знакомого типа: пустые қаз/eng (или переводы прежнего знакомого типа) — заменяем его переводами. */
  function useType(t) {
    const prev = { kz: form.type.kz, en: form.type.en };
    let did = false;
    for (const l of ['kz', 'en']) {
      const cur = form.type[l];
      if (!cur.trim() || (lastType && cur === (lastType[l] || ''))) {
        if (cur !== (t[l] || '')) did = true;
        form.type[l] = t[l] || '';
      }
    }
    if (did && !autoTr) autoTr = prev;
    typeRef = t;
    lastType = t;
    updTypeTr();
  }

  /** Тип вписали целиком (а не нажали подсказку) — то же, что нажатие: написание и переводы знакомого типа.
   *  final — человек ушёл с поля: тогда и написание как у знакомого («Хобо» → «хобо»). */
  function syncType(final) {
    const t = matchType(form.type.ru);
    if (t && t !== typeRef) useType(t);
    else if (!t && typeRef) {
      if (autoTr) {
        for (const l of ['kz', 'en']) if (form.type[l] === (typeRef[l] || '')) form.type[l] = autoTr[l];
      }
      autoTr = null;
      typeRef = null;
      updTypeTr();
    }
    if (final && t && form.type.ru !== t.ru) {
      form.type.ru = t.ru;
      refs.type.value = t.ru;
      trPlaceholders();
      changed();
    }
  }

  function updTypeTr() {
    for (const l of ['kz', 'en']) {
      const inp = refs.tr && refs.tr[`type.${l}`];
      if (inp) inp.value = form.type[l];
    }
  }

  function pickType(t) {
    form.type.ru = t.ru;
    refs.type.value = t.ru;
    if (t !== typeRef) useType(t);
    clearError(refs.type.closest('.fld'));
    trPlaceholders();
    renderTypes();
    changed();
    refs.type.focus({ preventScroll: true });
  }

  function buildColors() {
    refs.vars = h('div', { class: 'vars' });
    const first = form.variants[0];
    const note = legacy && original && h('div', { class: 'note' }, icon(I.info), h('p', null,
      'Этот товар заведён по-старому: все фото лежат в одном цвете. ',
      first && palOf(first) ? `Мы отметили цвет «${palOf(first).name.ru}» — проверьте. ` : 'Выберите для него цвет. ',
      'Если на фото несколько цветов — добавьте цвета и перенесите в них фото: нажмите на фото → «Перенести в другой цвет».'));
    const wrap = h('div', { class: 'fld fld--vars', 'data-field': 'variants' },
      h('p', { class: 'fld__err', hidden: true }),
      refs.vars,
      refs.addVar = h('button', { type: 'button', class: 'btn btn--line btn--add', onclick: addVariant }, icon(I.plus), 'Добавить цвет'));
    renderVariants();
    return section({
      title: 'Цвета и фото', id: 'sec-colors', req: true,
      intro: 'У каждого цвета — свои фото. Первый цвет — основной: его фото видно в каталоге.',
    }, note, wrap);
  }

  function renderVariants() {
    refs.vars.replaceChildren(...form.variants.map((v, i) => (v.open ? variantBlock(v, i) : variantRow(v, i))));
    if (refs.addVar) refs.addVar.hidden = form.variants.length >= L.colors_max;
    if (refs.tocColors) refs.tocColors.textContent = `Цвета (${form.variants.length})`;
    renderTrShades();
  }

  /** Цвет можно свернуть: выбран кружочек, есть фото, ничего не грузится и нет ошибок. */
  function complete(v) {
    return !!palOf(v) && v.images.length > 0 && v.images.every((i) => i.state === 'ok');
  }

  function matsText(v) {
    return v.mats.map((k) => meta.mat[k] && meta.mat[k].name.ru).filter(Boolean).join(', ');
  }

  /** Свёрнутый цвет: «[фото] ● молочный · кожа · 4 фото — Изменить»; «Сделать основным» — у второго и дальше. */
  function variantRow(v, i) {
    const n = form.variants.length;
    const k = v.images.length;
    const shot = v.images.find((x) => x.state === 'ok' && (x.thumb || x.local));
    const meta1 = [matsText(v), `${k} фото`].filter(Boolean).join(' · ');
    return h('div', { class: 'var var--row', 'data-field': `variants.${i}`, 'data-var': v.uid },
      h('button', {
        type: 'button', class: 'vrow', 'aria-expanded': 'false',
        'aria-label': `Цвет ${i + 1}: ${shadeName(v)}${i === 0 && n > 1 ? ', основной' : ''}, ${meta1}. Изменить`,
        onclick: () => openVariant(v),
      },
      shot ? h('img', { class: 'vrow__ph', src: shot.thumb || shot.local, alt: '', decoding: 'async' }) : h('span', { class: 'vrow__ph vrow__ph--none' }, icon(I.photo)),
      h('span', { class: 'vrow__t' },
        h('span', { class: 'vrow__name' }, swatch(swatchOf(v), 'sw--m'), h('span', { class: 'vrow__nm' }, shadeName(v)),
          i === 0 && n > 1 && h('span', { class: 'var__main' }, 'основной')),
        h('span', { class: 'vrow__meta' }, meta1)),
      h('span', { class: 'vrow__go' }, 'Изменить')),
      i > 0 && h('button', { type: 'button', class: 'link vrow__main', onclick: () => moveVariant(i, -i) }, icon(I.star), 'Сделать основным'),
      h('p', { class: 'fld__err', hidden: true }));
  }

  function openVariant(v) {
    v.open = true;
    renderVariants();
    const el = refs.vars.querySelector(`[data-var="${v.uid}"]`);
    if (!el) return;
    reveal(el, { block: 'start' });
    const t = el.querySelector('.var__collapse') || el.querySelector('.pal__o[tabindex="0"]');
    if (t) setTimeout(() => t.focus({ preventScroll: true }), 300);
  }

  function closeVariant(v) {
    v.open = false;
    renderVariants();
    const el = refs.vars.querySelector(`[data-var="${v.uid}"]`);
    if (!el) return;
    el.scrollIntoView({ block: 'nearest' });
    const b = el.querySelector('.vrow');
    if (b) b.focus({ preventScroll: true });
  }

  /** Фото цвета поменялись, а он свёрнут (перенесли фото из другого цвета) — обновить строку. */
  function refreshRow(v) {
    if (v.open || !refs.vars) return;
    const i = form.variants.indexOf(v);
    const el = refs.vars.querySelector(`[data-var="${v.uid}"]`);
    if (i >= 0 && el) el.replaceWith(variantRow(v, i));
  }

  /** Раскрыть цвета, в которых есть ошибка (иначе красное не видно). */
  function openFor(fields) {
    let any = false;
    for (const f of fields) {
      const m = /^variants\.(\d+)/.exec(String(f || ''));
      const v = m && form.variants[Number(m[1])];
      if (v && !v.open) {
        v.open = true;
        any = true;
      }
    }
    if (any) renderVariants();
  }

  function variantBlock(v, i) {
    const n = form.variants.length;
    const headSw = h('span', { class: 'var__sw' });
    const headName = h('span', { class: 'var__name' });
    const shadeHint = h('span');
    const updHead = () => {
      headSw.replaceChildren(swatch(swatchOf(v), 'sw--m'));
      headName.textContent = palOf(v) ? shadeName(v) : 'выберите цвет';
      headName.classList.toggle('mute', !palOf(v));
      const p = palOf(v);
      shadeHint.textContent = p
        ? `Пусто — «${p.name.ru}». Можно точнее: «карамельный», «шоколадный».`
        : 'Как назвать цвет покупателю, например «карамельный».';
    };
    const move = n > 1 && h('div', { class: 'var__move' },
      h('button', { type: 'button', class: 'ibtn ibtn--line', title: 'Поднять выше', 'aria-label': `Цвет ${i + 1}: поднять выше`, disabled: i === 0, onclick: () => moveVariant(i, -1) }, icon(I.up)),
      h('button', { type: 'button', class: 'ibtn ibtn--line', title: 'Опустить ниже', 'aria-label': `Цвет ${i + 1}: опустить ниже`, disabled: i === n - 1, onclick: () => moveVariant(i, 1) }, icon(I.down)));
    const head = h('div', { class: 'var__head' }, headSw,
      h('h3', { class: 'var__t' }, h('span', { class: 'var__no' }, `Цвет ${i + 1}`), headName, i === 0 && n > 1 && h('span', { class: 'var__main' }, 'основной')),
      move);
    const tools = (i > 0 || complete(v)) && h('div', { class: 'var__tools' },
      i > 0 && h('button', { type: 'button', class: 'link', onclick: () => moveVariant(i, -i) }, icon(I.star), 'Сделать основным'),
      complete(v) && h('button', { type: 'button', class: 'link var__collapse', onclick: () => closeVariant(v) }, icon(I.up), 'Свернуть'));

    const pal = radios({
      options: meta.palette.map((c) => ({ value: c.key, label: c.name.ru, render: () => [swatch(c, 'sw--xl'), h('span', { class: 'pal__l' }, c.name.ru)] })),
      value: v.color, cls: 'pal', item: 'pal__o',
      onchange: (k) => {
        if (v.extra && v.color !== k) {   // свой оттенок кружочка был у прежнего цвета — к новому не подходит
          delete v.extra.hex;
          delete v.extra.pattern;
        }
        v.color = k;
        updHead();
        renderTrShades();
        changed();
      },
    });
    const shade = input({
      id: `v-${v.uid}-name`, value: v.name.ru, placeholder: 'например, карамельный', maxlength: 60, ...PLAIN,
      oninput: (val) => {
        v.name.ru = val;
        updHead();
        changed();
      },
    });
    shade.addEventListener('change', renderTrShades);
    // переименовали оттенок («карамельный» → «медовый»), а перевод остался от прежнего названия
    const shadeWarn = staleTr({
      orig: tri(v.extra && v.extra.name),
      cur: () => v.name,
      onOpen: () => {
        renderTrShades();
        const c = document.getElementById(`v-${v.uid}-name-kz`);
        if (!c) return;
        const d = c.closest('details');
        if (d) d.open = true;
        c.scrollIntoView({ block: 'center' });
        c.focus({ preventScroll: true });
      },
      onClear: () => {
        v.name.kz = '';
        v.name.en = '';
        renderTrShades();
        changed();
      },
    });
    refs.warn[`shade:${v.uid}`] = shadeWarn;
    shadeWarn.update();
    const mats = toggles({
      options: meta.materials.map((m) => ({ value: m.key, label: cap(m.name.ru) })),
      isOn: (k) => v.mats.includes(k),
      onToggle: (k) => {
        v.mats = v.mats.length === 1 && v.mats[0] === k ? [] : [k];
        changed();
      },
    });
    const count = h('span', { class: 'var__count' });
    const photoFld = h('div', { class: 'fld fld--photos', 'data-field': `variants.${i}.images` },
      h('p', { class: 'fld__l' }, 'Фото', h('span', { class: 'req', 'aria-hidden': 'true' }, ' *'), count),
      h('p', { class: 'fld__hint' }, 'Первое фото — главное: его видно в каталоге. Лучше вертикальные, на светлом фоне.'),
      h('p', { class: 'fld__err', hidden: true }),
      photos.view(v, count));
    const el = h('div', { class: 'var', 'data-field': `variants.${i}`, 'data-var': v.uid },
      head,
      tools,
      h('p', { class: 'fld__err', hidden: true }),
      field({ name: `variants.${i}.color`, label: 'Цвет', req: true, control: pal, id: `v-${v.uid}-color`, hint: 'Выберите самый близкий — по нему покупатели ищут в фильтре «цвет».' }),
      field({ name: `variants.${i}.name`, label: 'Название цвета на сайте', opt: true, control: shade, below: shadeWarn, hint: shadeHint }),
      field({ name: `variants.${i}.material`, label: 'Материал', opt: true, control: mats, id: `v-${v.uid}-mat`, hint: 'Нажмите ещё раз, чтобы снять выбор.' }),
      photoFld,
      n > 1 && h('button', { type: 'button', class: 'link link--danger var__del', onclick: () => deleteVariant(v) }, icon(I.trash), 'Удалить этот цвет'));
    updHead();
    const bad = v.images.filter((x) => x.state === 'err');
    if (bad.length) setTimeout(() => badPhotos(v), 0);   // блок перерисовали — вернуть текст ошибки под «Фото»
    return el;
  }

  /** Файлы не подошли или не загрузились: под «Фото» — полный текст с именами файлов (на плитке — коротко). */
  function badPhotos(v) {
    if (dead || !refs.vars) return;
    if (!v.open) {
      v.open = true;
      renderVariants();
    }
    const i = form.variants.indexOf(v);
    const all = v.images.filter((x) => x.state === 'err');
    if (i < 0 || !all.length) return;
    const lines = all.slice(0, 3).map(badText);
    if (all.length > 3) lines.push(`И ещё ${all.length - 3} — тоже отмечены красным.`);
    setError(root, `variants.${i}.images`, lines.join(' '));
  }

  function addVariant() {
    const v = newVariant();
    form.variants.push(v);
    renderVariants();
    changed();
    const el = refs.vars.querySelector(`[data-var="${v.uid}"]`);
    reveal(el, { block: 'start' });
    setTimeout(() => {
      const b = el && el.querySelector('.pal__o[tabindex="0"]');
      if (b) b.focus({ preventScroll: true });
    }, 350);
  }

  function moveVariant(i, d) {
    const j = i + d;
    if (j < 0 || j >= form.variants.length || i === j) return;
    const [v] = form.variants.splice(i, 1);
    form.variants.splice(j, 0, v);
    renderVariants();
    changed();
    const el = refs.vars.querySelector(`[data-var="${v.uid}"]`);
    if (!el) return;
    flash(el);
    (el.querySelector('.var__head') || el).scrollIntoView({ block: 'nearest' });
    const btns = el.querySelectorAll('.var__move button');
    const want = btns[d < 0 ? 0 : 1];
    const btn = want && !want.disabled ? want : Array.from(btns).find((b) => !b.disabled) || el.querySelector('.vrow');
    if (btn) btn.focus({ preventScroll: true });
    if (j === 0) toast(`«${label(v)}» теперь основной цвет — его фото будет в каталоге.`, { kind: 'ok', timeout: 3500 });
  }

  async function deleteVariant(v) {
    const i = form.variants.indexOf(v);
    if (i < 0) return;
    const nm = palOf(v) ? `«${shadeName(v)}»` : `№ ${i + 1}`;
    const k = v.images.length;
    const ok = await dialog({
      title: `Удалить цвет ${nm}?`,
      text: k
        ? `Вместе с ним из товара уберутся его фото (${k} шт.). Это произойдёт, когда вы нажмёте «Сохранить и опубликовать».`
        : 'Цвет уберётся из товара, когда вы нажмёте «Сохранить и опубликовать».',
      buttons: [{ label: 'Не удалять', value: false, kind: 'ink' }, { label: 'Удалить цвет', value: true, kind: 'danger-line' }],
      dismiss: false,
    });
    if (!ok) return;
    for (const img of v.images) {
      if (img.abort) img.abort();
      photos.free(img);
    }
    form.variants.splice(form.variants.indexOf(v), 1);
    renderVariants();
    changed();
    const next = refs.vars.querySelectorAll('.var')[Math.min(i, form.variants.length - 1)];
    if (next) (next.querySelector('.var__head') || next).scrollIntoView({ block: 'nearest' });
  }

  function buildPrice() {
    const price = input({
      id: 'f-price', value: form.price, inputmode: 'numeric', placeholder: 'например, 45 000', enterkeyhint: 'done',
      oninput: (v) => {
        form.price = v;
        clearSaleErr();               // «сначала укажите обычную цену», «меньше обычной (…)» — правят и здесь
        updSale();
        changed();
      },
      onblur: (v, el) => {
        const n = parseIntField(v);
        if (Number.isInteger(n)) {
          el.value = groupDigits(n);
          form.price = el.value;
        }
      },
    });
    const big =(t, s) => [h('span', { class: 'opt3__dot', 'aria-hidden': 'true' }), h('span', { class: 'opt3__txt' }, h('span', { class: 'opt3__t' }, t), h('span', { class: 'opt3__s' }, s))];
    const avail = radios({
      options: [
        { value: 'in', render: () => big('В наличии', 'можно купить: кнопка «в корзину»') },
        { value: 'soon', render: () => big('Скоро в наличии', 'вместо «в корзину» — «узнать о поступлении»') },
        { value: 'sold', render: () => big('Продано', 'товар остаётся на сайте с пометкой «продано»') },
      ],
      value: form.avail, cls: 'opts3', item: 'opt3',
      onchange: (v) => {
        form.avail = v;
        refs.stockF.hidden = v !== 'in';
        changed();
      },
    });
    const stock = input({
      id: 'f-stock', value: form.stock, inputmode: 'numeric', placeholder: 'например, 2', maxlength: 6,
      oninput: (v) => {
        form.stock = v;
        changed();
      },
    });
    refs.stockF = field({
      name: 'stock', label: 'Остаток', opt: true, control: withUnit(stock, 'шт.'),
      hint: 'Сколько штук осталось. Если 1 — на сайте будет пометка «остался 1». Пусто — просто «в наличии».',
    });
    refs.stockF.hidden = form.avail !== 'in';
    const marks = h('div', { class: 'checks' },
      check({ id: 'f-new', checked: form.isNew, label: 'Новинка', hint: 'в блоке «новинки» на главной и с пометкой «новинка» в каталоге (пометку заменяют «продано», «скоро в наличии» и «остался 1»)', onchange: (v) => { form.isNew = v; changed(); } }),
      check({ id: 'f-pop', checked: form.popular, label: 'Популярное', hint: 'в блоке «популярное» на главной', onchange: (v) => { form.popular = v; changed(); } }));
    return section({ title: 'Цена и наличие', id: 'sec-price' },
      field({ name: 'price', label: 'Цена', control: withUnit(price, '₸'), hint: 'Только цифры. Пусто — на сайте будет «цена по запросу».' }),
      buildSale(),
      field({ name: 'availability', label: 'Наличие', control: avail, id: 'f-avail' }),
      refs.stockF,
      field({ label: 'Метки', opt: true, control: marks, group: true }));
  }

  // ——— Скидка: переключатель под ценой; включили — «Цена со скидкой», рядом живое «скидка 20 %», кнопки −10/−20/−30 %.
  // Выключили — поле прячется, но набранное помним (включите снова — вернётся); сохраняется только включённая скидка.

  function buildSale() {
    refs.saleSw = switcher({
      id: 'f-sale', checked: form.sale, label: 'Скидка', hint: saleHint,
      onchange: (v) => {
        form.sale = v;
        refs.saleBox.hidden = !v;
        if (!v) clearSaleErr();         // скидку выключили — её ошибка больше не нужна
        updSale();
        changed();
      },
    });
    refs.saleInp = input({
      id: 'f-sale-price', value: form.salePrice, inputmode: 'numeric', placeholder: 'например, 36 000', enterkeyhint: 'done',
      oninput: (v) => {
        form.salePrice = v;
        updSale();
        changed();
      },
      onblur: (v, el) => {
        const n = parseIntField(v);
        if (Number.isInteger(n)) {
          el.value = groupDigits(n);
          form.salePrice = el.value;
        }
      },
    });
    refs.salePct = h('p', { class: 'sale__pct tnum', id: 'f-sale-pct' });
    refs.saleBtns = SALE_STEPS.map((pct) => h('button', { type: 'button', class: 'chip sale__q tnum', 'aria-pressed': 'false', onclick: () => quickSale(pct) }, `−${pct}${NBSP}%`));
    refs.saleF = field({
      name: 'sale_price', label: 'Цена со скидкой', control: h('div', { class: 'fld__row' }, withUnit(refs.saleInp, '₸'), refs.salePct),
      after: h('div', { class: 'chips sale__qs', role: 'group', 'aria-label': 'Скидка от обычной цены' }, refs.saleBtns),
      hint: 'Нажмите −10 %, −20 % или −30 % — цена посчитается сама. Или впишите свою.',
    });
    refs.saleInp.setAttribute('aria-describedby', `${refs.salePct.id} ${refs.saleInp.getAttribute('aria-describedby') || ''}`.trim());
    refs.saleBox = h('div', { class: 'sale__box', hidden: !form.sale }, refs.saleF);
    updSale();
    return h('div', { class: 'sale' }, refs.saleSw, refs.saleBox);
  }

  /** Подсказка под «Скидкой» — по сохранённому товару: пока не сохранили, на сайте всё по-прежнему. */
  function saleHint(on) {
    if (on) return 'На сайте старая цена будет зачёркнута, а новая — красным.';
    const keep = parseIntField(form.salePrice);
    const back = Number.isInteger(keep) && keep > 0 ? ` Включите снова — вернётся ${money(keep)}.` : '';
    if (original && typeof original.sale_price === 'number' && original.sale_price > 0) return `После сохранения скидка пропадёт — на сайте будет обычная цена.${back}`;
    return back ? `Скидка выключена.${back}` : 'Включите, если вещь продаётся дешевле обычной цены.';
  }

  /** Цена со скидкой pct % от обычной, вниз до 10 ₸ (45 990 −30 % → 32 190); обычной цены нет — null. */
  function saleBy(pct) {
    const pr = parseIntField(form.price);
    if (!Number.isInteger(pr) || pr <= 0) return null;
    const v = Math.floor((pr * (100 - pct)) / 1000) * 10;
    return v > 0 ? v : null;
  }

  function quickSale(pct) {
    const v = saleBy(pct);
    if (!v) return;
    form.salePrice = groupDigits(v);
    refs.saleInp.value = form.salePrice;
    clearSaleErr();                       // ошибку у поля исправили кнопкой
    updSale();
    changed();
  }

  /** Ошибку у «Цены со скидкой» правят и не в самом поле: кнопкой −N %, обычной ценой, выключив скидку. Убрать её
   *  и сообщение внизу (как autoClear у поля, которое начали править); что не так сейчас — скажет подсказка рядом. */
  function clearSaleErr() {
    if (!refs.saleF || !refs.saleF.classList.contains('is-err')) return;
    clearError(refs.saleF);
    clearToasts('err');
  }

  /** Живая подсказка рядом с полем: «скидка 20 %» или что не так (красным). */
  function saleNote() {
    const pr = parseIntField(form.price);
    const sp = parseIntField(form.salePrice);
    if (Number.isNaN(pr)) return { text: 'проверьте обычную цену', bad: true };
    if (!pr) return { text: 'сначала укажите обычную цену', bad: true };
    if (sp === null) return { text: '', bad: false };
    if (Number.isNaN(sp)) return { text: 'только цифры', bad: true };
    if (sp === 0) return { text: 'не может быть 0', bad: true };
    if (sp >= pr) return { text: sp === pr ? 'равна обычной цене' : 'больше обычной цены', bad: true };
    const pct = Math.min(99, Math.round((1 - sp / pr) * 100));
    return { text: pct < 1 ? `скидка меньше 1${NBSP}%` : `скидка ${pct}${NBSP}%`, bad: false };
  }

  function updSale() {
    if (!refs.salePct) return;
    const n = saleNote();
    refs.salePct.textContent = n.text;
    refs.salePct.hidden = !n.text;
    refs.salePct.classList.toggle('is-bad', n.bad);
    const sp = parseIntField(form.salePrice);
    refs.saleBtns.forEach((b, i) => {
      const v = saleBy(SALE_STEPS[i]);
      b.disabled = !v;
      b.setAttribute('aria-pressed', String(!!v && v === sp));
      b.title = v ? money(v) : 'Сначала укажите обычную цену';
    });
  }

  function buildDesc() {
    const desc = textarea({
      id: 'f-desc', value: form.desc.ru, rows: 4, placeholder: 'Пара предложений о вещи: из чего сделана, что помещается, с чем носить.',
      oninput: (v) => {
        form.desc.ru = v;
        trPlaceholders();
        changed();
      },
    });
    const cells = ['w', 'h', 'd'].map((k, j) => {
      const inp = input({
        id: `f-size-${k}`, value: form.size[k], inputmode: 'decimal', placeholder: '—', maxlength: 6,
        oninput: (v) => {
          form.size[k] = v;
          changed();
        },
      });
      return h('div', { class: 'size__c', 'data-field': `size.${k}` },
        h('label', { class: 'size__l', for: inp.id }, ['ширина', 'высота', 'глубина'][j]), inp, h('p', { class: 'fld__err', hidden: true }));
    });
    const sizeRow = h('div', { class: 'size' }, cells[0], h('span', { class: 'size__x', 'aria-hidden': 'true' }, '×'), cells[1],
      h('span', { class: 'size__x', 'aria-hidden': 'true' }, '×'), cells[2], h('span', { class: 'size__u' }, 'см'));
    const strap = textarea({
      id: 'f-strap', value: form.strap.ru, rows: 2, placeholder: 'например, съёмный ремень 120 см, регулируется',
      oninput: (v) => {
        form.strap.ru = v;
        trPlaceholders();
        changed();
      },
    });
    return section({ title: 'Описание и размеры', id: 'sec-desc' },
      field({ name: 'desc', label: 'Описание', opt: true, control: desc, below: trWarn('desc'), hint: 'Пусто — на странице товара просто не будет описания.' }),
      field({ name: 'size', label: 'Размер, см', opt: true, control: sizeRow, group: true, hint: 'Ширина × высота × глубина. Заполните все три — иначе на сайте будет «уточняется».' }),
      field({ name: 'strap', label: 'Ручки и ремни', opt: true, control: strap, below: trWarn('strap'), hint: 'Как на сайте в «характеристиках». Пусто — там будет «уточняется».' }),
      buildTranslations());
  }

  function buildTranslations() {
    refs.tr = {};
    const row = (key, title, multi = false) => h('div', { class: 'tr__row' },
      h('p', { class: 'tr__l' }, title),
      ['kz', 'en'].map((l) => {
        const id = `f-${key}-${l}`;
        const onin = (v) => {
          form[key][l] = v;
          changed();
        };
        const ctl = multi ? textarea({ id, value: form[key][l], rows: 2, oninput: onin, lang: LANG_ATTR[l] })
          : input({ id, value: form[key][l], oninput: onin, lang: LANG_ATTR[l], ...(key === 'type' ? PLAIN : {}) });
        refs.tr[`${key}.${l}`] = ctl;
        return field({ name: `${key}.${l}`, label: LANG_NAME[l], control: ctl, cls: 'fld--tr' });
      }));
    refs.trShades = h('div', { class: 'tr__shades' });
    const el = fold({ title: 'Казахский и английский', hint: 'необязательно · пусто — на сайте покажется русский текст', cls: 'fold--tr' },
      row('name', 'Название'), row('type', 'Тип'), row('desc', 'Описание', true), row('strap', 'Ручки и ремни', true), refs.trShades);
    el.addEventListener('toggle', () => {
      if (el.open) for (const c of el.querySelectorAll('textarea')) c.fit && c.fit();
    });
    trPlaceholders();
    renderTrShades();
    return el;
  }

  function trPlaceholders() {
    if (!refs.tr) return;
    for (const key of ['name', 'type', 'desc', 'strap']) {
      const ru = form[key].ru.trim().replace(/\s+/g, ' ');
      for (const l of ['kz', 'en']) {
        const c = refs.tr[`${key}.${l}`];
        if (c) c.placeholder = ru ? (ru.length > 70 ? `${ru.slice(0, 70)}…` : ru) : '';
      }
    }
  }

  function renderTrShades() {
    if (!refs.trShades) return;
    const rows = form.variants.filter((v) => v.name.ru.trim() || v.name.kz.trim() || v.name.en.trim()).map((v) => h('div', { class: 'tr__row' },
      h('p', { class: 'tr__l' }, `Цвет «${shadeName(v) || label(v)}»`),
      ['kz', 'en'].map((l) => field({
        label: LANG_NAME[l], cls: 'fld--tr',
        control: input({
          id: `v-${v.uid}-name-${l}`, value: v.name[l], placeholder: v.name.ru.trim(), lang: LANG_ATTR[l], ...PLAIN,
          oninput: (val) => {
            v.name[l] = val;
            changed();
          },
        }),
      }))));
    refs.trShades.replaceChildren(...rows);
  }

  function buildDanger() {
    return h('section', { class: 'sec sec--danger', 'aria-labelledby': 'sec-del-t' },
      h('h2', { class: 'sec__t', id: 'sec-del-t' }, 'Удаление'),
      h('p', { class: 'sec__intro' }, 'Удаляется навсегда, вместе с фото. Если товар закончился — лучше отметьте «Продано» или выключите «Показывать на сайте» вверху.'),
      h('button', { type: 'button', class: 'btn btn--danger-line', onclick: onDelete }, icon(I.trash), 'Удалить товар'));
  }

  function buildSavebar() {
    refs.saveL = h('span', null, 'Сохранить и опубликовать');
    refs.saveBtn = h('button', { type: 'submit', class: 'btn btn--ink savebar__save' }, refs.saveL);
    refs.cancelBtn = h('button', { type: 'button', class: 'btn btn--line savebar__cancel', onclick: onCancel }, 'Закрыть');
    refs.state = h('p', { class: 'savebar__state', 'aria-live': 'polite' });
    return h('div', { class: 'savebar' },
      refs.state,
      h('div', { class: 'savebar__btns' },
        h('button', { type: 'button', class: 'btn btn--line savebar__pv', 'aria-label': 'Посмотреть, как будет на сайте', onclick: openPreview },
          icon(I.eye), h('span', { class: 'savebar__pvl', 'aria-hidden': 'true' }, 'Превью')),
        refs.cancelBtn,
        refs.saveBtn));
  }

  // ——— Изменения: состояние панели и превью ———

  function changed(v) {
    if (v && v.uid && refs.vars) {
      const w = refs.vars.querySelector(`[data-var="${v.uid}"] .fld--photos.is-err`);
      if (w && v.images.length && !v.images.some((i) => i.state === 'err')) {
        clearError(w);
        clearToasts('err');
      } else if (w) badPhotos(v);                    // убрали одно из неподошедших — обновить перечень
    }
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (dead || !form || !refs.state) return;
      updateState();
      updatePreview();
      for (const w of Object.values(refs.warn || {})) w.update();
      persistDraft();
    });
  }

  function updateState() {
    const dirty = isDirty();
    const up = photos.pending();
    const bad = photos.failed();
    refs.state.textContent = up
      ? `Загружается ${up} ${plural(up, 'фото', 'фото', 'фото')}…`
      : bad ? (photos.retryable() ? 'Есть фото, которые не загрузились — нажмите на них «Повторить» или уберите' : 'Уберите фото, отмеченные красным')
        : dirty ? 'Есть несохранённые изменения' : slug ? 'Всё сохранено' : 'Новый товар ещё не сохранён';
    refs.state.classList.toggle('is-dirty', dirty || !!bad);
    root.classList.toggle('is-dirty', dirty);
    refs.cancelBtn.textContent = dirty ? 'Отменить правки' : 'Закрыть';
    refs.saveBtn.classList.toggle('is-idle', !!slug && !dirty && !saving);   // без правок — бледнее (нажать можно)
  }

  function previewModel() {
    const vs = [];
    let skipped = 0;
    for (const v of form.variants) {
      const p = palOf(v);
      const imgs = v.images.filter((i) => i.state === 'ok' && (i.thumb || i.local)).map((i) => i.thumb || i.local);
      if (!p || !imgs.length) {
        skipped++;
        continue;
      }
      vs.push({ key: v.color, name: shadeName(v), ...swatchOf(v), mats: matsText(v), images: imgs });
    }
    const size = ['w', 'h', 'd'].map((k) => parseNumField(form.size[k]));
    const price = parseIntField(form.price);
    const sp = parseIntField(form.salePrice);
    const st = parseIntField(form.stock);
    return {
      name: form.name.ru.trim() || 'Название товара', type: form.type.ru.trim(), id: (original && original.id) || '',
      price: Number.isInteger(price) && price > 0 ? price : null,
      // как на сайте: скидка есть, только если цена задана и 0 < цена со скидкой < цена
      sale: form.sale && Number.isInteger(price) && Number.isInteger(sp) && sp > 0 && sp < price ? sp : null,
      stock: form.avail === 'sold' ? 0 : Number.isInteger(st) && st > 0 ? st : null,
      sold: form.avail === 'sold', soon: form.avail === 'soon', isNew: form.isNew,
      published: form.published, wasPublished: wasPublished(),
      desc: form.desc.ru.trim(), strap: form.strap.ru.trim(),
      size: size.every((x) => Number.isFinite(x) && x > 0) ? size.map((x) => String(x)) : null,
      variants: vs,
      skipped: skipped && vs.length
        ? `${skipped} ${plural(skipped, 'цвет', 'цвета', 'цветов')} без фото или без выбранного кружочка — на сайте ${skipped === 1 ? 'его' : 'их'} не будет.`
        : '',
    };
  }

  function updatePreview() {
    const m = previewModel();
    preview.update(m);
    if (sheetPv) sheetPv.update(m);
  }

  function openPreview() {
    sheetPv = createPreview();
    sheetPv.update(previewModel());
    sheet({
      title: 'Так будет на сайте', cls: 'sheet--pv',
      body: [h('p', { class: 'ed__pvhint' }, 'Нажмите на кружочки — фото поменяются.'), sheetPv.el],
      onClose: () => { sheetPv = null; },
    });
  }

  // ——— Проверка перед отправкой (те же правила, что на сервере) ———

  function validate() {
    const errs = [];
    const add = (f, msg) => errs.push({ field: f, msg });
    const name = form.name.ru.trim();
    if (!name) add('name', 'Впишите название товара.');
    else if (name.length > L.name_max) add('name', `Слишком длинное название: ${name.length} ${plural(name.length, 'знак', 'знака', 'знаков')}, можно до ${L.name_max}.`);
    if (!form.cat || !meta.cat[form.cat] || !meta.cat[form.cat].leaf) add('cat', 'Выберите категорию.');
    if (!form.variants.length) add('variants', 'Добавьте хотя бы один цвет.');
    else if (form.variants.length > L.colors_max) add('variants', `Не больше ${L.colors_max} цветов у одного товара.`);
    const seen = new Map();
    form.variants.forEach((v, i) => {
      const p = palOf(v);
      if (!p) add(`variants.${i}.color`, 'Выберите цвет — нажмите на кружочек.');
      else if (seen.has(v.color) && !v.name.ru.trim()) {
        add(`variants.${i}.name`, `Цвет «${p.name.ru}» уже есть выше (цвет ${seen.get(v.color) + 1}). Впишите название цвета, чтобы покупатель их различал, — например «тёмный ${p.name.ru}» или «карамельный».`);
      }
      if (p && !seen.has(v.color)) seen.set(v.color, i);
      const up = v.images.filter((x) => x.state === 'up').length;
      const bad = v.images.filter((x) => x.state === 'err');
      if (up) add(`variants.${i}.images`, 'Подождите, пока загрузятся все фото, и нажмите «Сохранить и опубликовать» ещё раз.');
      else if (bad.length) {
        add(`variants.${i}.images`, bad.some((x) => x.retry && x.file)
          ? 'Есть фото, которые не загрузились: нажмите на них «Повторить» или уберите.'
          : `Уберите фото, отмеченные красным: ${bad.length === 1 ? 'этот файл не подошёл' : 'эти файлы не подошли'}.`);
      } else if (!v.images.length) add(`variants.${i}.images`, 'Добавьте хотя бы одно фото этого цвета.');
      else if (v.images.length > L.photos_max) add(`variants.${i}.images`, `В одном цвете — не больше ${L.photos_max} фото. Уберите лишние.`);
      for (const l of LANGS) {
        if (v.name[l].trim().length > L.shade_max) add(l === 'ru' ? `variants.${i}.name` : `variants.${i}.name.${l}`, `Название цвета — не длиннее ${L.shade_max} знаков.`);
      }
    });
    const pr = parseIntField(form.price);
    if (Number.isNaN(pr)) add('price', 'В цене — только цифры, например 45 000.');
    else if (pr > L.price_max) add('price', `Цена больше ${groupDigits(L.price_max)} ₸ — проверьте, нет ли лишнего нуля.`);
    if (form.sale) {                       // те же правила, что на сервере (catalog.sale_in)
      const sp = parseIntField(form.salePrice);
      if (Number.isNaN(sp)) add('sale_price', 'В цене со скидкой — только цифры, например 36 000.');
      else if (sp === 0) add('sale_price', 'Цена со скидкой не может быть 0. Скидка не нужна — выключите её.');
      else if (Number.isNaN(pr)) { /* обычная цена с ошибкой — она уже отмечена выше */ }
      else if (!pr) add('sale_price', 'Сначала укажите обычную цену — скидка считается от неё.');
      else if (sp === null) add('sale_price', 'Впишите цену со скидкой или нажмите −10 %, −20 %, −30 %. Скидка не нужна — выключите её.');
      else if (sp >= pr) add('sale_price', `Цена со скидкой должна быть меньше обычной (${money(pr)}).`);
    }
    if (form.avail === 'in') {
      const st = parseIntField(form.stock);
      if (Number.isNaN(st)) add('stock', 'Остаток — целое число, например 2.');
      else if (st === 0) add('stock', 'Остаток 0 — значит, товар продан. Выберите «Продано» выше или оставьте поле пустым.');
      else if (st > L.stock_max) add('stock', 'Слишком большой остаток — проверьте число.');
    }
    for (const k of ['w', 'h', 'd']) {
      const x = parseNumField(form.size[k]);
      if (Number.isNaN(x)) add(`size.${k}`, 'Только число, например 25 или 12,5.');
      else if (x !== null && (x < L.size_min || x > L.size_max)) add(`size.${k}`, `От ${L.size_min} до ${L.size_max} см.`);
    }
    const max = { name: L.name_max, type: L.type_max, desc: L.text_max, strap: L.text_max };
    for (const key of Object.keys(max)) {
      for (const l of LANGS) {
        if (key === 'name' && l === 'ru') continue;
        const len = form[key][l].trim().length;
        if (len > max[key]) add(l === 'ru' ? key : `${key}.${l}`, `Слишком длинный текст: ${len} ${plural(len, 'знак', 'знака', 'знаков')}, можно до ${max[key]}.`);
      }
    }
    return errs;
  }

  // ——— Сохранение, отмена, удаление ———

  /** Пока идёт «Сохраняем…» (с GitHub это 2–5 с), поля не трогаются: после ответа форма перестраивается
   *  из сохранённого, и набранное за эти секунды пропало бы. */
  function setBusy(on) {
    if (!refs.saveBtn) return;
    refs.saveBtn.disabled = on;
    refs.saveBtn.classList.toggle('is-busy', on);
    refs.saveL.textContent = on ? 'Сохраняем…' : 'Сохранить и опубликовать';
    refs.cancelBtn.disabled = on;
    root.classList.toggle('is-saving', on);
    for (const el of [refs.pubRow, refs.draft, ...refs.form.querySelectorAll(':scope > .sec')]) if (el) el.inert = on;
    if (!on) updateState();
  }

  async function save() {
    if (saving || !form) return;
    clearToasts();                        // прежние подсказки про другое состояние — не закрывают поля над панелью
    clearErrors(root);
    const errs = validate();
    if (errs.length) {
      openFor(errs.map((e) => e.field));
      focusField(showErrors(root, errs));
      toast(errorsText(errs, what), { kind: 'err', timeout: 7000 });
      return;
    }
    if (slug && !isDirty()) {
      toast('Изменений нет — сохранять нечего.');
      return;
    }
    saving = true;
    setBusy(true);
    const wasPub = wasPublished();
    try {
      const product = buildProduct();
      let commit = null;
      if (slug) {
        const r = await api(`/api/products/${encodeURIComponent(slug)}`, { method: 'PUT', body: { product, sha } });
        commit = r && r.commit;
        siteUrl = (r && r.url) || siteUrl;
      } else {
        const r = await api('/api/products', { method: 'POST', body: { product } });
        commit = r && r.commit;
        slug = r && r.slug;
        siteUrl = (r && r.url) || '';
        if (slug) replaceUrl(`/product/${slug}`);
      }
      dropDraft(draftKey);                 // сохранено — черновик больше не нужен
      draftKey = slug || 'new';
      pending = null;
      mine = null;
      if (dead) return;
      saved = { commit, since: Date.now(), wasPub };
      if (commit) status.expect(commit);
      loadMeta(true).catch(() => {});
      await reloadAfterSave();
      const nowPub = form ? form.published : true;
      const msg = !status.tracked() ? 'Сохранено.'
        : nowPub ? 'Сохранено. Публикуем на сайт — обычно это 2–3 минуты.'
          : wasPub ? 'Сохранено. Товар пропадёт с сайта через 2–3 минуты.' : 'Сохранено. Товар скрыт — на сайте его нет.';
      if (!onScreen(refs.notice)) toast(msg, { kind: 'ok' });   // сообщение вверху и так видно — не дублируем
    } catch (e) {
      if (!dead) onSaveError(e);
    } finally {
      saving = false;
      if (!dead) setBusy(false);
    }
  }

  async function reloadAfterSave() {
    const wasOpen = form ? form.variants.map((v) => !!v.open) : [];
    try {
      const r = await api(`/api/products/${encodeURIComponent(slug)}`);
      if (dead) return;
      original = (r && r.product) || {};
      sha = (r && r.sha) || null;
      if (photos) photos.destroy();
      form = toForm(original);
      baseForm = toForm(original);
      if (wasOpen.length === form.variants.length) form.variants.forEach((v, i) => { v.open = v.open || wasOpen[i]; });
      base = snap();
      resetType();
      const y = window.scrollY;
      build();
      window.scrollTo(0, y);
    } catch {
      base = snap();
      toast('Сохранено, но страница не обновилась. Обновите её, прежде чем менять что-то ещё.', { kind: 'err', timeout: 12000 });
      updateState();
    }
  }

  function onSaveError(e) {
    if (e.status === 409) {
      conflict();
      return;
    }
    if (e.status === 401) return;   // поверх экрана уже открыт вход; после него — «Сохранить» ещё раз
    if (e.field) {
      openFor([e.field]);
      const w = setError(root, e.field, e.message);
      if (w) {
        focusField(w);
        toast(errorsText([{ field: e.field, msg: e.message }], what), { kind: 'err', timeout: 9000 });
        return;
      }
    }
    toast(humane(e), { kind: 'err', timeout: 9000 });
  }

  async function conflict() {
    const v = await dialog({
      title: 'Товар изменили в другом месте',
      text: 'Пока вы редактировали, этот товар сохранили с другого телефона или в другой вкладке. Загрузите свежую версию — '
        + 'ваши несохранённые правки админка покажет сверху, и их можно будет вернуть одной кнопкой. Или останьтесь и скопируйте длинный текст.',
      buttons: [{ label: 'Загрузить свежую версию', value: true, kind: 'ink' }, { label: 'Остаться и скопировать правки', value: false, kind: 'line' }],
      dismiss: false,
    });
    if (!v) return;
    const from = form;
    const groups = changedGroups(from, baseForm);
    mine = groups.length ? { from, groups } : null;
    saved = null;
    dropDraft(draftKey);                   // правки — в «Ваши несохранённые правки» (и снова в черновике, если вернуть)
    pending = null;
    loading();
    load();
  }

  /** После «товар изменили в другом месте»: что человек поменял и не сохранил — и «Вернуть мои правки». */
  function mineNote() {
    if (!mine) return null;
    const short = (s) => (s.length > 160 ? `${s.slice(0, 160)}…` : s);
    const el = h('div', { class: 'note note--mine', role: 'status' },
      icon(I.info),
      h('div', { class: 'note__in' },
        h('p', null, h('b', null, 'Ваши несохранённые правки. '), 'Товар уже изменили в другом месте — ниже свежая версия. Ваши правки:'),
        h('ul', { class: 'mine' }, mine.groups.map((g) => h('li', null, h('span', { class: 'mine__k' }, `${g.label}: `), h('span', { class: 'mine__v' }, short(g.show(mine.from) || 'пусто'))))),
        h('p', { class: 'note__btns' },
          h('button', { type: 'button', class: 'btn btn--ink', onclick: applyMine }, 'Вернуть мои правки'),
          h('button', { type: 'button', class: 'btn btn--line', onclick: () => { mine = null; el.remove(); } }, 'Не нужно'))));
    return el;
  }

  /** Поверх свежей версии — только поля, которые человек менял; правки второй основательницы в других полях остаются. */
  function applyMine() {
    if (!mine) return;
    applyGroups(form, mine.from, mine.groups);
    mine = null;
    resetType();
    build();
    persistDraft();
    toast('Ваши правки вернулись поверх свежей версии. Проверьте и нажмите «Сохранить и опубликовать».', { kind: 'ok', timeout: 7000 });
  }

  async function onCancel() {
    if (!isDirty()) {                      // «Закрыть»
      clearLeaveGuard(guard);
      go('/');
      return;
    }
    const ok = await dialog({
      title: 'Отменить правки?',
      text: slug ? 'Всё, что вы поменяли после последнего сохранения, пропадёт — товар останется таким, как сейчас на сайте.' : 'Всё, что вы ввели, пропадёт — товар не сохранится.',
      buttons: [{ label: 'Продолжить редактирование', value: false, kind: 'ink' }, { label: 'Да, отменить правки', value: true, kind: 'danger-line' }],
      dismiss: false,
    });
    if (!ok) return;
    dropDraft(draftKey);
    pending = null;
    mine = null;
    if (!slug) {                           // пустой новый товар не нужен — к списку
      discarded = true;
      clearLeaveGuard(guard);
      go('/');
      return;
    }
    form = toForm(original);
    base = snap();
    resetType();
    build();
    flash(root.querySelector('.ed__ttl'));
    toast('Правки отменены — товар как был.');
  }

  async function onDelete() {
    const name = txt(original && original.name).trim() || form.name.ru.trim() || 'этот товар';
    const v = await dialog({
      title: `Удалить «${name}» навсегда?`,
      text: 'Фото тоже удалятся. Можно вместо этого просто скрыть товар — он пропадёт с сайта, но останется здесь.',
      buttons: [
        { label: 'Не удалять', value: null, kind: 'ink' },
        { label: 'Просто скрыть', value: 'hide', kind: 'line' },
        { label: 'Удалить навсегда', value: 'del', kind: 'danger-line' },
      ],
      dismiss: null,
    });
    if (v === 'hide') {
      form.published = false;
      refs.pub.set(false);
      changed();
      await save();
      return;
    }
    if (v !== 'del') return;
    setBusy(true);
    try {
      const r = await api(`/api/products/${encodeURIComponent(slug)}?sha=${encodeURIComponent(sha || '')}`, { method: 'DELETE', body: {} });
      if (r && r.commit) status.expect(r.commit);
      discarded = true;
      dropDraft(draftKey);
      clearLeaveGuard(guard);
      toast(status.tracked() ? `«${name}» удалён. Сайт обновится через 2–3 минуты.` : `«${name}» удалён.`, { kind: 'ok' });
      go('/');
    } catch (e) {
      setBusy(false);
      if (e.status === 409) conflict();
      else if (e.status !== 401) toast(humane(e), { kind: 'err', timeout: 8000 });
    }
  }

  // ——— Сообщение после сохранения: «Публикуем…» → «Опубликовано · Открыть товар на сайте» ———

  function showNotice() {
    const el = refs.notice;
    if (!el || dead) return;
    if (!saved) {
      el.hidden = true;
      return;
    }
    const st = status.stateOf(saved.commit, saved.since);
    const url = siteUrl || productUrl(slug);
    const pub = !form || form.published;
    let kids;
    if (st === 'busy') {
      kids = [h('span', { class: 'spin', 'aria-hidden': 'true' }), h('p', null, h('b', null, 'Сохранено. '),
        pub ? 'Публикуем на сайт… обычно 2–3 минуты.' : saved.wasPub ? 'Убираем товар с сайта… обычно 2–3 минуты.' : 'Товар скрыт — на сайте его нет.')];
    } else if (st === 'failed') kids = [icon(I.alert), h('p', null, h('b', null, 'Сохранено, но сайт не обновился. '), 'Повторять не нужно — сообщите Даулету.')];
    else if (st === 'unknown') kids = [icon(I.check), h('p', null, h('b', null, 'Сохранено.'))];
    else {
      kids = [icon(I.check), h('p', null, h('b', null, 'Опубликовано. '),
        !pub ? 'Товар скрыт — на сайте его не видно.'
          : url ? h('a', { href: url, target: '_blank', rel: 'noopener', class: 'ulink' }, 'Открыть товар на сайте', icon(I.ext)) : 'Изменения уже на сайте.')];
    }
    el.dataset.state = st;
    el.replaceChildren(...kids, h('button', {
      type: 'button', class: 'ibtn notice__x', 'aria-label': 'Скрыть сообщение',
      onclick: () => {
        saved = null;
        el.hidden = true;
      },
    }, icon(I.close)));
    el.hidden = false;
  }
}
