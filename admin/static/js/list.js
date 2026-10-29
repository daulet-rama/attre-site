// Товары: «+ Добавить товар», поиск по названию и артикулу, фильтры-чипы, сетка карточек с бейджами
// (у товара со скидкой — «Скидка −20 %», старая цена зачёркнута, новая красным).
// «Изменить порядок» → список с перетаскиванием (за ⋮⋮) и стрелками ↑ ↓ → «Сохранить порядок».

import { api, humane } from './api.js';
import { h, icon, flash } from './dom.js';
import { I } from './icons.js';
import { getMeta, catLabel, paletteKey } from './meta.js';
import { setLeaveGuard, clearLeaveGuard } from './router.js';
import { sortable } from './sortable.js';
import * as status from './status.js';
import { swatch } from './swatch.js';
import { dialog, toast, placeToasts } from './ui.js';
import { txt, norm, money, plural, NBSP } from './util.js';

// Поиск, фильтр и прокрутка помнятся, пока открыта вкладка: вернулись из товара — всё на месте
const keep = { q: '', f: 'all', y: 0 };

// Поиск «как слышится»: названия на сайте латиницей (Tokyo, Capri), а на телефоне чаще русская раскладка —
// «токио», «капри», «гамбург» находят Tokyo, Capri, Hamburg. Сравниваем упрощённую латиницу.
const TR = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ж: 'zh', з: 'z', и: 'i', й: 'i', к: 'k', л: 'l', м: 'm', н: 'n',
  о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch', ъ: '', ы: 'i',
  ь: '', э: 'e', ю: 'yu', я: 'ya', ә: 'a', ғ: 'g', қ: 'k', ң: 'n', ө: 'o', ұ: 'u', ү: 'u', һ: 'h', і: 'i',
};

function loose(s) {
  return Array.from(norm(s), (c) => TR[c] ?? c).join('')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]/g, '')
    .replace(/ph/g, 'f').replace(/ck/g, 'k').replace(/c(?=[eiy])/g, 's').replace(/[cq]/g, 'k')
    .replace(/w/g, 'v').replace(/x/g, 'ks').replace(/y/g, 'i').replace(/h/g, 'g')
    .replace(/(.)\1+/g, '$1');
}

/** Фото не открылось (файл ещё не загружен или удалён) — серая заглушка вместо «битой» картинки. */
function noImg(e) {
  e.target.replaceWith(h('span', { class: 'pc__noimg' }, icon(I.photo), 'фото не открылось'));
}

function normItem(p) {
  const num = (x) => (typeof x === 'number' && Number.isFinite(x) ? x : null);
  const price = num(p.price);
  const sale = num(p.sale_price);
  return {
    slug: String(p.slug || ''),
    id: p.id == null ? '' : String(p.id),
    name: txt(p.name).trim() || 'Без названия',
    names: p.name && typeof p.name === 'object' ? [p.name.ru, p.name.kz, p.name.en].filter(Boolean).join(' ') : txt(p.name),
    type: txt(p.type).trim(),
    cat: p.cat || '',
    price,
    sale: price && sale > 0 && sale < price ? sale : null,      // как на сайте: иначе скидки нет
    stock: num(p.stock),
    soon: !!p.soon,
    isNew: !!p.new,
    popular: !!p.popular,
    published: p.published !== false,
    colors: (Array.isArray(p.colors) ? p.colors : []).map((c) => (typeof c === 'string' ? c : c && (c.color || c.key))).filter(Boolean),
    thumb: typeof p.thumb === 'string' && p.thumb ? p.thumb : null,
    photos: typeof p.photos === 'number' ? p.photos : Array.isArray(p.photos) ? p.photos.length : null,
  };
}

export function mountList(main) {
  const meta = getMeta();
  let items = null;
  let order = null;         // режим порядка: массив slug в новом порядке
  let dead = false;
  let onResize = null;
  const root = h('div', { class: 'list' });
  main.replaceChildren(root);
  const guard = { dirty: () => !!order && order.join() !== items.map((p) => p.slug).join() };
  skeleton();
  load();

  return {
    destroy() {
      dead = true;
      if (!order) keep.y = window.scrollY;
      clearLeaveGuard(guard);
      if (onResize) window.removeEventListener('resize', onResize);
    },
    title: () => 'Товары',
  };

  function filters() {
    return [
      { key: 'all', label: 'Все', test: () => true },
      ...meta.leafCats.map((c) => ({ key: `cat:${c.key}`, label: catLabel(c), test: (p) => p.cat === c.key })),
      { key: 'hidden', label: 'Скрытые', test: (p) => !p.published },
      { key: 'noprice', label: 'Без цены', test: (p) => !p.price },
      { key: 'sale', label: 'Со скидкой', test: (p) => !!p.sale },
      { key: 'soon', label: 'Скоро в наличии', test: (p) => p.soon && p.stock !== 0 },
      { key: 'sold', label: 'Проданные', test: (p) => p.stock === 0 },
    ];
  }

  function skeleton() {
    root.replaceChildren(
      h('div', { class: 'list__head' }, h('h1', { class: 'list__h' }, 'Товары')),
      h('ul', { class: 'grid grid--skel', 'aria-hidden': 'true' }, Array.from({ length: 8 }, () => h('li', { class: 'pc pc--skel' }, h('span', { class: 'pc__ph' }), h('span', { class: 'skel' }), h('span', { class: 'skel skel--s' })))),
      h('p', { class: 'sr-only', role: 'status' }, 'Загружаем товары…'));
  }

  async function load() {
    try {
      const list = await api('/api/products');
      if (dead) return;
      items = (Array.isArray(list) ? list : []).map(normItem).filter((p) => p.slug);
      render();
      if (keep.y) requestAnimationFrame(() => window.scrollTo(0, keep.y));
    } catch (e) {
      if (dead) return;
      root.replaceChildren(h('div', { class: 'state' },
        h('h1', { class: 'state__t' }, 'Не получилось загрузить товары'),
        h('p', { class: 'state__p' }, humane(e)),
        h('div', { class: 'state__btns' }, h('button', { type: 'button', class: 'btn btn--ink', onclick: () => { skeleton(); load(); } }, 'Попробовать ещё раз'))));
    }
  }

  // ——— Обычный вид: поиск, фильтры, сетка ———

  function render() {
    const fs = filters();
    if (!fs.some((f) => f.key === keep.f)) keep.f = 'all';
    const count = h('span', { class: 'list__n tnum' }, String(items.length));
    const search = h('input', {
      type: 'search', class: 'inp search__in', id: 'list-q', value: keep.q, placeholder: 'Название, артикул или цвет',
      autocomplete: 'off', enterkeyhint: 'search', 'aria-label': 'Поиск по названию, артикулу или цвету',
    });
    const clearQ = h('button', { type: 'button', class: 'search__x', 'aria-label': 'Очистить поиск', hidden: !keep.q }, icon(I.close));
    const chips = h('div', { class: 'fchips', role: 'group', 'aria-label': 'Показать' });
    const grid = h('ul', { class: 'grid', 'aria-label': 'Товары' });
    const empty = h('div', { class: 'list__empty', hidden: true });
    const shown = h('p', { class: 'list__shown', 'aria-live': 'polite' });

    const head = h('div', { class: 'list__head' },
      h('h1', { class: 'list__h' }, 'Товары', count),
      h('button', { type: 'button', class: 'btn btn--line list__order', onclick: startOrder, disabled: items.length < 2 }, icon(I.move), 'Изменить порядок'),
      h('a', { class: 'btn btn--ink list__add', href: '/product/new', 'data-link': '' }, icon(I.plus), 'Добавить товар'));
    const tools = h('div', { class: 'list__tools' },
      h('div', { class: 'search' }, icon(I.search), search, clearQ),
      chips);
    root.replaceChildren(head, tools, shown, grid, empty);

    function draw() {
      const q = norm(keep.q);
      const lq = loose(q);
      const digits = q.replace(/\D/g, '');
      const f = fs.find((x) => x.key === keep.f) || fs[0];
      const hay = (p) => `${p.names} ${p.type} ${p.colors.map((k) => (meta.pal[paletteKey(k)] || { name: { ru: '' } }).name.ru).join(' ')}`;
      // «как слышится» — только с начала слова: «ток» находит Tokyo, но не Stockholm
      const soundsLike = (p) => {
        const words = norm(p.names).split(/[\s\-–—_.,«»"()]+/).filter(Boolean);
        return words.some((_, i) => loose(words.slice(i).join(' ')).startsWith(lq));
      };
      const matchQ = (p) => !q || norm(hay(p)).includes(q)
        || (lq.length >= 2 && soundsLike(p))
        || (digits && digits.length === q.length && (p.id === digits || p.id.replace(/^0+/, '') === digits.replace(/^0+/, '')));
      const byQ = items.filter(matchQ);
      chips.replaceChildren(...fs.map((x) => {
        const n = byQ.filter(x.test).length;
        return h('button', {
          type: 'button', class: `chip chip--f${n ? '' : ' is-zero'}`, 'aria-pressed': String(x.key === keep.f),
          onclick: () => {
            keep.f = x.key;
            draw();
          },
        }, x.label, h('span', { class: 'chip__n tnum' }, String(n)));
      }));
      const list = byQ.filter(f.test);
      grid.replaceChildren(...list.map(card));
      grid.hidden = !list.length;
      clearQ.hidden = !keep.q;
      shown.textContent = q || keep.f !== 'all'
        ? `Показано ${list.length} ${plural(list.length, 'товар', 'товара', 'товаров')} из ${items.length}`
        : '';
      shown.hidden = !shown.textContent;
      empty.hidden = !!list.length;
      if (!list.length) {
        empty.replaceChildren(...[
          h('p', { class: 'list__empty-t' }, items.length ? (q ? `По запросу «${keep.q.trim()}» ничего не нашли.` : emptyText(f.key)) : 'Товаров пока нет.'),
          items.length
            ? (q || keep.f !== 'all') && h('button', { type: 'button', class: 'btn btn--line', onclick: () => { keep.q = ''; keep.f = 'all'; search.value = ''; draw(); } }, 'Показать все товары')
            : h('a', { class: 'btn btn--ink', href: '/product/new', 'data-link': '' }, icon(I.plus), 'Добавить первый товар'),
        ].filter(Boolean));
      }
    }

    // На телефоне фильтры прокручиваются вбок: у края, за которым есть ещё кнопки, — затухание (видно, что есть ещё)
    const edges = () => {
      const max = chips.scrollWidth - chips.clientWidth;
      chips.classList.toggle('is-more-r', max > 2 && chips.scrollLeft < max - 2);
      chips.classList.toggle('is-more-l', max > 2 && chips.scrollLeft > 2);
    };
    chips.addEventListener('scroll', edges, { passive: true });
    if (onResize) window.removeEventListener('resize', onResize);
    onResize = edges;
    window.addEventListener('resize', onResize, { passive: true });
    requestAnimationFrame(edges);

    search.addEventListener('input', () => {
      keep.q = search.value;
      draw();
      edges();
    });
    clearQ.addEventListener('click', () => {
      keep.q = '';
      search.value = '';
      draw();
      search.focus();
    });
    draw();
  }

  function emptyText(key) {
    return {
      hidden: 'Скрытых товаров нет — все видны на сайте.',
      noprice: 'У всех товаров есть цена.',
      sale: 'Товаров со скидкой нет.',
      soon: 'Товаров «скоро в наличии» нет.',
      sold: 'Проданных товаров нет.',
    }[key] || 'В этом разделе пока нет товаров.';
  }

  function badges(p) {
    const out = [];
    if (!p.published) out.push(['Скрыт', 'off']);
    if (p.photos === 0) out.push(['Нет фото', 'warn']);
    if (p.stock === 0) out.push(['Продано', 'sold']);
    else if (p.soon) out.push(['Скоро', '']);
    if (p.sale) out.push([saleLabel(p), 'sale']);
    if (p.isNew) out.push(['Новинка', 'new']);
    if (p.popular) out.push(['Популярное', '']);
    return out;
  }

  /** «Скидка −20 %» — проценты считаются так же, как подсказка в форме (45 000 → 36 000 — 20 %). */
  function saleLabel(p) {
    const pct = Math.min(99, Math.round((1 - p.sale / p.price) * 100));
    return pct < 1 ? 'Скидка' : `Скидка −${pct}${NBSP}%`;
  }

  function priceLine(p) {
    if (!p.price) return 'цена по запросу';
    if (!p.sale) return money(p.price);
    return [h('span', { class: 'sr-only' }, 'было '), h('s', { class: 'pc__old' }, money(p.price)),
      h('span', { class: 'sr-only' }, ', сейчас '), h('span', { class: 'pc__new' }, money(p.sale))];
  }

  function dots(p) {
    const cs = p.colors.map((k) => meta.pal[paletteKey(k)]).filter(Boolean);
    const seen = new Set();
    const uniq = cs.filter((c) => (seen.has(c.key) ? false : seen.add(c.key)));
    if (!uniq.length) return null;
    return h('span', { class: 'pc__sw', title: uniq.map((c) => c.name.ru).join(', ') },
      uniq.slice(0, 8).map((c) => swatch(c, 'sw--s')),
      uniq.length > 8 && h('span', { class: 'pc__more' }, `+${uniq.length - 8}`),
      h('span', { class: 'sr-only' }, `Цвета: ${uniq.map((c) => c.name.ru).join(', ')}`));
  }

  function card(p) {
    const bs = badges(p);
    return h('li', { class: `pc${p.published ? '' : ' pc--off'}${p.stock === 0 ? ' pc--sold' : ''}` },
      h('a', { class: 'pc__a', href: `/product/${p.slug}`, 'data-link': '' },
        h('span', { class: 'pc__ph' },
          p.thumb ? h('img', { src: p.thumb, alt: '', loading: 'lazy', decoding: 'async', onerror: noImg }) : h('span', { class: 'pc__noimg' }, icon(I.photo), 'нет фото'),
          bs.length > 0 && h('span', { class: 'pc__tags' }, bs.map(([t, k]) => h('span', { class: `badge${k ? ` badge--${k}` : ''}` }, t)))),
        h('span', { class: 'pc__cap' },
          h('span', { class: 'pc__name' }, p.name),
          h('span', { class: 'pc__meta' }, [p.id && `арт. ${p.id}`, p.type].filter(Boolean).join(' · ')),
          h('span', { class: `pc__price tnum${p.price ? '' : ' mute'}` }, priceLine(p)),
          dots(p))));
  }

  // ——— Режим «Изменить порядок» ———

  function startOrder() {
    order = items.map((p) => p.slug);
    keep.y = window.scrollY;
    setLeaveGuard(guard);
    renderOrder();
    placeToasts();
    window.scrollTo(0, 0);
  }

  function stopOrder() {
    order = null;
    clearLeaveGuard(guard);
    render();
    placeToasts();
    requestAnimationFrame(() => window.scrollTo(0, keep.y));
  }

  function renderOrder() {
    const bySlug = Object.fromEntries(items.map((p) => [p.slug, p]));
    const list = h('ol', { class: 'olist', 'aria-label': 'Порядок товаров в каталоге' });
    const saveBtn = h('button', { type: 'button', class: 'btn btn--ink savebar__save', onclick: saveOrder }, 'Сохранить порядок');
    const state = h('p', { class: 'savebar__state', 'aria-live': 'polite' });
    const head = h('div', { class: 'obar' },
      h('h1', { class: 'list__h' }, 'Порядок в каталоге'),
      h('p', { class: 'obar__h' }, 'Тяните за ', h('span', { class: 'obar__grip' }, icon(I.drag)), ' или двигайте стрелками. Первый в списке — первый в каталоге сайта.'));
    const bar = h('div', { class: 'savebar savebar--order' }, state, h('div', { class: 'savebar__btns' },
      h('button', { type: 'button', class: 'btn btn--line savebar__cancel', onclick: cancelOrder }, 'Отмена'),
      saveBtn));
    root.replaceChildren(head, list, bar);

    function row(slug, i) {
      const p = bySlug[slug];
      const n = order.length;
      const c = meta.cat[p.cat];
      return h('li', { class: 'orow', 'data-slug': slug },
        h('span', { class: 'orow__n tnum' }, String(i + 1)),
        h('span', { class: 'orow__ph' }, p.thumb ? h('img', { src: p.thumb, alt: '', loading: 'lazy', draggable: 'false' }) : icon(I.photo)),
        h('span', { class: 'orow__t' }, h('span', { class: 'orow__name' }, h('span', { class: 'orow__nm' }, p.name), !p.published && h('span', { class: 'badge badge--off' }, 'Скрыт')),
          h('span', { class: 'orow__meta' }, [c ? catLabel(c) : '', p.id && `арт. ${p.id}`].filter(Boolean).join(' · '))),
        h('span', { class: 'orow__btns' },
          h('button', { type: 'button', class: 'ibtn ibtn--line orow__top', title: 'В самое начало', 'aria-label': `«${p.name}» — в самое начало`, disabled: i === 0, onclick: () => move(slug, 0, 'top') }, icon(I.top)),
          h('button', { type: 'button', class: 'ibtn ibtn--line', title: 'Выше', 'aria-label': `«${p.name}» — выше`, disabled: i === 0, onclick: () => move(slug, i - 1, 'up') }, icon(I.up)),
          h('button', { type: 'button', class: 'ibtn ibtn--line', title: 'Ниже', 'aria-label': `«${p.name}» — ниже`, disabled: i === n - 1, onclick: () => move(slug, i + 1, 'down') }, icon(I.down))),
        h('span', { class: 'orow__grip', title: 'Тяните, чтобы переставить', 'aria-hidden': 'true' }, icon(I.drag)));
    }

    function draw(focus) {
      list.replaceChildren(...order.map(row));
      saveBtn.disabled = !guard.dirty();
      state.textContent = guard.dirty() ? 'Порядок изменён — не забудьте сохранить' : 'Пока ничего не переставлено';
      state.classList.toggle('is-dirty', guard.dirty());
      if (focus) {
        const li = list.querySelector(`[data-slug="${CSS.escape(focus.slug)}"]`);
        if (li) {
          flash(li);
          li.scrollIntoView({ block: 'nearest' });
          const btns = li.querySelectorAll('.orow__btns button');
          const want = { top: 0, up: 1, down: 2 }[focus.which];
          const b = btns[want] && !btns[want].disabled ? btns[want] : Array.from(btns).find((x) => !x.disabled);
          if (b) b.focus({ preventScroll: true });
        }
      }
    }

    function move(slug, to, which) {
      const from = order.indexOf(slug);
      if (from < 0 || to < 0 || to >= order.length || from === to) return;
      order.splice(from, 1);
      order.splice(to, 0, slug);
      draw({ slug, which });
    }

    sortable(list, {
      item: '.orow', handle: '.orow__grip',
      onEnd: (from, to) => {
        const [s] = order.splice(from, 1);
        order.splice(to, 0, s);
        draw({ slug: s, which: 'none' });
      },
    });
    draw();

    async function saveOrder() {
      if (!guard.dirty()) return;
      saveBtn.disabled = true;
      saveBtn.textContent = 'Сохраняем…';
      try {
        const r = await api('/api/products/order', { method: 'POST', body: { slugs: order } });
        if (r && r.commit) status.expect(r.commit);
        const pos = Object.fromEntries(order.map((s, i) => [s, i]));
        items.sort((a, b) => pos[a.slug] - pos[b.slug]);
        toast(status.tracked() ? 'Порядок сохранён. Сайт обновится через 2–3 минуты.' : 'Порядок сохранён.', { kind: 'ok' });
        keep.y = 0;
        stopOrder();
      } catch (e) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Сохранить порядок';
        if (e.status !== 401) toast(humane(e), { kind: 'err', timeout: 9000 });
      }
    }

    async function cancelOrder() {
      if (guard.dirty()) {
        const ok = await dialog({
          title: 'Отменить перестановку?',
          text: 'Новый порядок не сохранится — в каталоге останется прежний.',
          buttons: [{ label: 'Продолжить переставлять', value: false, kind: 'ink' }, { label: 'Да, отменить', value: true, kind: 'danger-line' }],
          dismiss: false,
        });
        if (!ok) return;
      }
      stopOrder();
    }
  }
}
