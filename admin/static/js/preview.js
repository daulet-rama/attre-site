// Живое превью «Так будет на сайте»: карточка каталога и блок товара — та же разметка и те же правила,
// что в themes/v4.py (card, product, tag, vswatch): бирка «продано → скоро в наличии → остался 1 → новинка»,
// «цена по запросу» без цены, скидка (старая цена зачёркнута, рядом новая красным), кружочки цветов меняют фото,
// «цвет: молочный», кнопка «в корзину».
// Перерисовываются только изменившиеся части: фото не мигают, пока человек печатает.

import { esc } from './dom.js';
import { SITE } from './icons.js';
import { swatchHtml } from './swatch.js';
import { money } from './util.js';

// Тексты сайта (data/i18n.json → t.*, русская версия)
const T = {
  price_request: 'цена по запросу', sold: 'продано', soon: 'скоро в наличии', last: 'остался 1', new_tag: 'новинка',
  cart_add: 'в корзину', wa_btn_soon: 'узнать о поступлении', wa_btn_sold: 'спросить о похожих', p_color: 'цвет',
  p_type: 'тип', p_material: 'материал', p_size: 'размеры', p_strap: 'ручки и ремни', p_made: 'производство',
  made_in: 'Гуанчжоу, Китай', todo: 'уточняется', details: 'характеристики', ref: 'арт.',
  price_old: 'старая цена', price_sale: 'цена со скидкой',
};

const priceText = (m) => (m.price ? money(m.price) : T.price_request);

/** Цена для карточки и страницы: со скидкой — старая зачёркнута, рядом новая красным, без процента
 *  (та же разметка, что price_html в themes/v4.py). */
const priceHtml = (m) => (m.price && m.sale
  ? `<span class="sr-only">${T.price_old}:</span><s class="price__was">${esc(money(m.price))}</s> `
    + `<span class="sr-only">${T.price_sale}:</span><span class="price__now">${esc(money(m.sale))}</span>`
  : esc(priceText(m)));

function tag(m) {
  if (m.sold) return `<p class="tag">${T.sold}</p>`;
  if (m.soon) return `<p class="tag tag--on">${T.soon}</p>`;
  if (m.stock === 1) return `<p class="tag tag--on">${T.last}</p>`;
  if (m.isNew) return `<p class="tag tag--on tag--new">${T.new_tag}</p>`;
  return '';
}

// Карточка — две рядом, как на телефоне 390px; рядом — кадр «крупной» карточки (первая и каждая третья в каталоге
// на телефоне — во всю ширину, 4:5: кадр чуть обрезан сверху и снизу). Страница товара — как на телефоне:
// полоса «название — цена — в корзину» после сведений и прилипает к низу (src/css/v4.css → .pp__bar).
const SKELETON = `<div data-part="notes"></div>
<section class="pv__sec"><h3 class="pv__cap">Карточка в каталоге</h3>
<div class="pv__cards"><div class="pv__card"><div class="vc" data-vc><div class="vc__media" data-part="cimg"></div><div data-part="ctext"></div></div></div>
<figure class="pv__wide"><div class="pv__wph" data-part="wimg"></div><figcaption>Первая в каталоге на телефоне — крупная: кадр чуть обрезан сверху и снизу</figcaption></figure></div></section>
<section class="pv__sec"><h3 class="pv__cap">Страница товара</h3>
<div class="pv__page"><article class="pp"><div class="pg" data-part="pimg"></div><div data-part="ptext" class="pp__side"></div></article></div></section>`;

/**
 * Модель готовит editor.js: {name, type, id, price, sale (цена со скидкой | null), stock, sold, soon, isNew, published,
 *   wasPublished (true | false | null — новый товар), desc, strap, size: [w,h,d] | null,
 *   variants: [{key, name, hex, pattern, mats, images: [url]}], skipped: 'текст' | ''}
 */
export function createPreview() {
  const el = document.createElement('div');
  el.className = 'pv';
  let model = null;
  let mode = '';
  let parts = {};
  const cache = {};
  const st = { cv: 0, pv: 0, slide: 0 };

  function set(name, html) {
    if (cache[name] === html) return;
    cache[name] = html;
    parts[name].innerHTML = html;
  }

  function notes(m) {
    const out = [];
    // по сохранённому состоянию: выключили «Показывать на сайте», но ещё не сохранили — товар пока на сайте
    if (!m.published && m.wasPublished === false) out.push('<p class="pv__note pv__note--off">Товар скрыт — на сайте его сейчас не видно.</p>');
    else if (!m.published) out.push('<p class="pv__note pv__note--off">Товар будет скрыт — на сайте его не будет.</p>');
    else if (m.wasPublished === false) out.push('<p class="pv__note">Сейчас товар скрыт. После сохранения он появится на сайте — вот так:</p>');
    if (m.skipped) out.push(`<p class="pv__note">${esc(m.skipped)}</p>`);
    return out.join('');
  }

  function draw() {
    if (!model) return;
    const m = model;
    if (!m.variants.length) {
      mode = 'empty';
      parts = {};
      for (const k of Object.keys(cache)) delete cache[k];
      el.innerHTML = `${notes(m)}<p class="pv__note">Пока нет ни одного цвета с фото — без фото товар на сайте не появится.</p>
<div class="pv__empty"><span>Здесь появится карточка, когда вы добавите фото</span></div>`;
      return;
    }
    if (mode !== 'full') {
      mode = 'full';
      el.innerHTML = SKELETON;
      parts = Object.fromEntries(Array.from(el.querySelectorAll('[data-part]')).map((x) => [x.dataset.part, x]));
      for (const k of Object.keys(cache)) delete cache[k];
    }
    const vs = m.variants;
    st.cv = Math.min(st.cv, vs.length - 1);
    st.pv = Math.min(st.pv, vs.length - 1);
    const multi = vs.length > 1 && !m.sold;
    const cv = multi ? st.cv : 0;
    el.querySelector('[data-vc]').classList.toggle('vc--sold', m.sold);
    set('notes', notes(m));

    // Карточка каталога (полоски внизу — сколько фото у цвета: на сайте фото карточки листаются)
    const shots = m.sold ? 1 : vs[cv].images.length;
    const bars = shots > 1 ? `<span class="vc__bars" aria-hidden="true">${vs[cv].images.map((_, i) => `<i${i === 0 ? ' class="is-on"' : ''}></i>`).join('')}</span>` : '';
    set('cimg', `<span class="vc__track"><img class="vc__img" src="${esc(vs[cv].images[0])}" alt=""></span>${bars}`);
    set('wimg', `<img src="${esc(vs[cv].images[0])}" alt="">`);
    const dots = multi
      ? `<div class="vc__sw vc__sw--pick">${vs.map((x, i) => `<button class="vc__c" type="button" data-pv-c="${i}" aria-pressed="${i === cv}" title="${esc(x.name)}">${swatchHtml(x, 'sw--s')}</button>`).join('')}</div>`
      : `<p class="vc__sw" title="${esc(vs.map((x) => x.name).join(', '))}">${vs.map((x) => swatchHtml(x, 'sw--s')).join('')}</p>`;
    set('ctext', `<div class="vc__cap">${tag(m)}<h4 class="vc__name">${esc(m.name)}</h4>${m.type ? `<p class="vc__meta">${esc(m.type)}</p>` : ''}<p class="vc__price tnum">${priceHtml(m)}</p></div>${dots}<span class="fav" aria-hidden="true">${SITE.heart}</span>`);

    // Страница товара: фото выбранного цвета листаются стрелками, полоски — сколько фото и какое сейчас
    const cur = vs[st.pv];
    const n = cur.images.length;
    st.slide = Math.min(st.slide, n - 1);
    const k = st.slide;
    set('pimg', `<figure class="pg__slide"><img src="${esc(cur.images[k])}" alt=""></figure>${n > 1
      ? `<span class="rail__bars">${cur.images.map((_, i) => `<i${i === k ? ' class="is-on"' : ''}></i>`).join('')}</span>
<button class="pg__arr pg__arr--prev" type="button" data-pv-s="-1" aria-label="Предыдущее фото"${k === 0 ? ' disabled' : ''}>${ARR}</button>
<button class="pg__arr pg__arr--next" type="button" data-pv-s="1" aria-label="Следующее фото"${k === n - 1 ? ' disabled' : ''}>${ARR}</button>` : ''}`);

    const buy = !m.sold && !m.soon;
    const acts = buy
      ? `<span class="pbtn pbtn--ink">${T.cart_add}</span><span class="pbtn pbtn--ico">${SITE.wa}</span>`
      : `<span class="pbtn">${SITE.wa}<span>${m.sold ? T.wa_btn_sold : T.wa_btn_soon}</span></span>`;
    const todo = `<span class="todo">${T.todo}</span>`;
    const spec = [
      [T.p_type, m.type ? esc(m.type) : todo],
      [T.p_color, esc(cur.name)],
      [T.p_material, cur.mats ? esc(cur.mats) : todo],
      [T.p_size, m.size ? `<span class="tnum">${m.size.map(esc).join(' × ')} см</span>` : todo],
      [T.p_strap, m.strap ? esc(m.strap) : todo],
      [T.p_made, T.made_in],
    ].map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join('');
    set('ptext', `<div class="pp__bar"><div class="pp__head"><h4 class="pp__name">${esc(m.name)}</h4><p class="pp__price tnum">${priceHtml(m)}</p></div>
<div class="pp__acts">${acts}<span class="fav fav--box" aria-hidden="true">${SITE.heart}</span></div></div>
<div class="pp__info"><div class="pcol"><p class="pcol__t">${T.p_color}: <span>${esc(cur.name)}</span></p>
<div class="pcol__opts">${vs.map((x, i) => `<button class="pcol__o" type="button" data-pv-p="${i}" aria-pressed="${i === st.pv}" title="${esc(x.name)}">${swatchHtml(x)}</button>`).join('')}</div></div>
${tag(m)}${m.type ? `<p class="pp__type">${esc(m.type)}</p>` : ''}<p class="pp__ref">${T.ref} <span class="tnum">${esc(m.id || '—')}</span></p>
${m.desc ? `<p class="pp__desc">${esc(m.desc)}</p>` : ''}
<div class="pp__accs"><div class="acc"><p class="acc__s"><span>${T.details}</span>${SITE.plus}</p><dl class="spec">${spec}</dl></div></div></div>`);
  }

  el.addEventListener('click', (e) => {
    const c = e.target.closest('[data-pv-c]');
    const p = e.target.closest('[data-pv-p]');
    const s = e.target.closest('[data-pv-s]');
    if (c) st.cv = Number(c.dataset.pvC);
    else if (p) {
      st.pv = Number(p.dataset.pvP);
      st.slide = 0;
    } else if (s) st.slide = Math.max(0, st.slide + Number(s.dataset.pvS));
    else return;
    draw();
  });
  // На компьютере цвет карточки меняется уже при наведении мышью на кружочек — как на сайте (палец — нажатием)
  el.addEventListener('pointerover', (e) => {
    if (e.pointerType !== 'mouse') return;
    const c = e.target.closest('[data-pv-c]');
    if (c && Number(c.dataset.pvC) !== st.cv) {
      st.cv = Number(c.dataset.pvC);
      draw();
    }
  });

  return {
    el,
    update(m) {
      model = m;
      draw();
    },
  };
}

const ARR = '<svg class="ico" viewBox="0 0 20 14" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true"><path d="M1 7h17M12.5 1.5 18 7l-5.5 5.5"/></svg>';
