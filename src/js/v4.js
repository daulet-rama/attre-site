// attré · Вариант 4 «Витрина». Меню и нижние листы (фокус внутри, Esc), строки details, ленты со свайпом
// (слайдер главной, фото товара, подборки: стрелки для мыши, счётчик «1 / 5»; фото в карточках — с полосками),
// избранное и корзина (localStorage), цвета (кружочки в карточке и на товаре меняют фото; в корзину идёт выбранный цвет),
// фильтр и сортировка каталога, видео «за кадром». Анимаций при прокрутке нет: фото просто стоят на местах.
// Без JS всё видно и листается пальцем; не работают только избранное, корзина, фильтр и сортировка.
(function () {
  'use strict';
  var d = document, root = d.documentElement, w = window;
  w.__v4 = 1;
  root.classList.add('js');   // скрипт пришёл позже 6-секундной страховки — возвращаем полный режим

  var mq = function (q) { return w.matchMedia ? w.matchMedia(q) : { matches: false }; };
  var still = mq('(prefers-reduced-motion: reduce)');
  var fine = mq('(hover: hover) and (pointer: fine)');   // мышь: второе фото — по наведению
  var each = function (sel, fn, ctx) { Array.prototype.forEach.call((ctx || d).querySelectorAll(sel), fn); };
  var fill = function (s, k, v) { return String(s).split('{' + k + '}').join(v); };
  var hasIO = 'IntersectionObserver' in w;
  var conn = navigator.connection;
  var thrifty = !!(conn && (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || '')));
  var T = {};
  try { T = JSON.parse(d.getElementById('v4-t').textContent); } catch (e) { /* без текстов остаются подписи из разметки */ }
  // Цена как в core.money(): 24 900 ₸ (по-английски 24,900 ₸) — фильтр каталога и корзина
  var money = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, T.sep || ' ') + ' ₸'; };

  // ——— Низ страницы: пока голубая плашка подвала на экране, холст под страницей тоже голубой —
  // пружинящая прокрутка iPhone не показывает белое под плашкой; сверху страницы холст остаётся белым ———
  var brand = d.querySelector('.ftr__brand');
  if (brand && hasIO) {
    new IntersectionObserver(function (es) { root.classList.toggle('at-end', es[es.length - 1].isIntersecting); }).observe(brand);
  }

  // ——— Меню и нижние листы: открыт один, подложка общая ———
  var scrim = d.createElement('div');
  scrim.className = 'scrim';
  scrim.setAttribute('aria-hidden', 'true');
  d.body.appendChild(scrim);
  var panel = null, opener = null;
  each('[data-panel]', function (p) {
    if (p.hasAttribute('data-sheet')) d.body.appendChild(p);   // лист — в конец body: не зависит от липких предков
    p.setAttribute('role', 'dialog');
    p.setAttribute('aria-modal', 'true');
    p.tabIndex = -1;
  });
  function expanded(p, on) {
    each('[aria-controls="' + p.id + '"]', function (b) { b.setAttribute('aria-expanded', on ? 'true' : 'false'); });
  }
  function open(p, btn) {
    if (panel) close(false);
    panel = p;
    opener = btn || null;
    p.scrollTop = 0;
    each('.sheet__body', function (b) { b.scrollTop = 0; }, p);
    p.classList.add('is-open');
    scrim.classList.add('is-on');
    root.classList.add('is-locked');
    expanded(p, true);
    var f = p.querySelector('[data-close]') || p;
    setTimeout(function () { if (panel === p) f.focus({ preventScroll: true }); }, 50);
  }
  function close(back) {
    if (!panel) return;
    var p = panel;
    panel = null;
    p.classList.remove('is-open');
    scrim.classList.remove('is-on');
    root.classList.remove('is-locked');
    expanded(p, false);
    if (back && opener) opener.focus({ preventScroll: true });
    opener = null;
  }
  function trap(ev, box) {
    var f = Array.prototype.filter.call(
      box.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'),
      function (x) { return x.getClientRects().length > 0; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1], a = d.activeElement;
    var inside = box.contains(a) && a !== box;
    if (ev.shiftKey && (a === first || !inside)) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && (a === last || !inside)) { ev.preventDefault(); first.focus(); }
  }
  d.addEventListener('click', function (ev) {
    var el = ev.target;
    if (!el || !el.closest) return;
    var btn = el.closest('[data-open]');
    if (btn) {
      var p = d.getElementById(btn.getAttribute('data-open'));
      if (p) { ev.preventDefault(); if (panel === p) close(true); else open(p, btn); }
      return;
    }
    if (!panel) return;
    if (el === scrim || el.closest('[data-close]')) { close(true); return; }
    var a = el.closest('a[href]');
    if (a && panel.contains(a)) close(false);   // переход по ссылке из панели — панель закрываем
  });
  d.addEventListener('keydown', function (ev) {
    if (!panel) return;
    if (ev.key === 'Escape' || ev.key === 'Esc') { ev.preventDefault(); close(true); return; }
    if (ev.key === 'Tab') trap(ev, panel);
  });

  // ——— Строки details: высота плавно 0fr → 1fr (CSS); без движения — родное поведение ———
  each('details.acc', function (dt) {
    var sum = dt.querySelector('summary');
    var body = dt.querySelector('.acc__body');
    if (!sum || !body) return;
    var closing = 0;
    if (dt.open) dt.classList.add('is-open');
    dt.addEventListener('toggle', function () {   // поиск по странице и reduced motion открывают сами
      if (dt.open) { if (!closing) dt.classList.add('is-open'); }
      else dt.classList.remove('is-open');
    });
    sum.addEventListener('click', function (ev) {
      if (still.matches) return;
      ev.preventDefault();
      if (dt.classList.contains('is-open')) {
        dt.classList.remove('is-open');
        var token = closing = setTimeout(function () {
          if (closing === token) { closing = 0; dt.open = false; }
        }, 480);
      } else {
        clearTimeout(closing);
        closing = 0;
        if (!dt.open) { dt.open = true; void body.offsetHeight; }   // старт из 0fr
        dt.classList.add('is-open');
      }
    });
  });

  // ——— Фото в карточке листаются вправо-влево: полоски внизу, у мыши — стрелки ———
  // Второе фото грузим, когда карточка подходит к экрану (свайп сразу попадёт на готовое фото),
  // остальные — как только человек начал листать эту карточку.
  function eager(i) { if (i && i.loading === 'lazy') i.loading = 'eager'; }
  function cardGal(c) {
    if (c.__gal !== undefined) return c.__gal;
    var t = c.querySelector('.vc__track'), box = c.querySelector('.vc__bars');
    c.__gal = null;
    if (!t || !box) return null;   // у карточки без полосок фото одно у всех цветов
    var g = { t: t, imgs: t.children, bars: box.children, all: false, aim: null, aimT: 0,
              prev: c.querySelector('[data-vstep="-1"]'), next: c.querySelector('[data-vstep="1"]') };
    g.step = function () { return g.imgs.length > 1 ? g.imgs[1].offsetLeft - g.imgs[0].offsetLeft : 0; };
    g.refresh = function () {   // другой цвет — другие фото: полоски по их числу, лента — с первого
      var n = g.imgs.length, html = '';
      for (var k = 0; k < n && n > 1; k++) html += k ? '<i></i>' : '<i class="is-on"></i>';
      box.innerHTML = html;
      g.all = false;
      t.scrollLeft = 0;
      if (g.prev) g.prev.hidden = true;
      if (g.next) g.next.hidden = n < 2;
      g.update();
    };
    g.update = function () {
      var s = g.step();
      if (!s) return;   // карточка скрыта (избранное, фильтр)
      var x = t.scrollLeft, i = Math.round(x / s), seen = Math.max(1, Math.round((t.clientWidth + 2) / s));
      for (var k = 0; k < g.bars.length; k++) g.bars[k].classList.toggle('is-on', k >= i && k < i + seen);
      if (g.prev) g.prev.hidden = x <= 2;
      if (g.next) g.next.hidden = x >= t.scrollWidth - t.clientWidth - 2;
    };
    g.loadAll = function () { if (!g.all) { g.all = true; Array.prototype.forEach.call(g.imgs, eager); } };
    var raf = 0;
    t.addEventListener('scroll', function () {
      g.loadAll();
      if (!raf) raf = requestAnimationFrame(function () { raf = 0; g.update(); });
    }, { passive: true });
    c.__gal = g;
    g.update();
    return g;
  }
  var gals = Array.prototype.slice.call(d.querySelectorAll('.vc--gal'));
  gals.forEach(cardGal);
  var soon = hasIO ? new IntersectionObserver(function (es) {
    es.forEach(function (en) {
      if (!en.isIntersecting) return;
      soon.unobserve(en.target);
      var g = cardGal(en.target);
      if (g) eager(g.imgs[1]);
    });
  }, { rootMargin: '600px 0px' }) : null;
  gals.forEach(function (c) { if (soon) soon.observe(c); else eager((cardGal(c) || { imgs: [] }).imgs[1]); });
  function galsUpdate(box) {
    each('.vc--gal', function (c) { var g = cardGal(c); if (g) g.update(); }, box);
  }
  var rsT = 0;
  w.addEventListener('resize', function () { clearTimeout(rsT); rsT = setTimeout(function () { galsUpdate(d); }, 150); });
  d.addEventListener('click', function (ev) {
    var b = ev.target && ev.target.closest && ev.target.closest('[data-vstep]');
    if (!b) return;
    var c = b.closest('.vc'), g = c && cardGal(c);
    if (!g) return;
    ev.preventDefault();
    g.loadAll();
    var t = g.t, m = t.scrollWidth - t.clientWidth;
    var from = g.aim !== null ? g.aim : t.scrollLeft;   // быстрые повторные нажатия — от цели, а не от середины пути
    g.aim = Math.max(0, Math.min(m, from + Number(b.getAttribute('data-vstep')) * g.step()));
    clearTimeout(g.aimT);
    g.aimT = setTimeout(function () { g.aim = null; }, 700);
    t.scrollTo({ left: g.aim, behavior: still.matches ? 'auto' : 'smooth' });
  });
  if (fine.matches) {   // мышь навелась — второе фото уже грузим
    d.addEventListener('pointerover', function (ev) {
      var c = ev.target && ev.target.closest && ev.target.closest('.vc--gal');
      var g = c && cardGal(c);
      if (g) eager(g.imgs[1]);
    }, { passive: true });
  }

  // ——— Цвет в карточке: кружочек меняет фото на фото этого цвета, ссылка ведёт на товар в этом цвете (?c=black).
  // Фото цвета лежат в <template> и грузятся только после выбора; прежние фото остаются в запасе — без повторной загрузки ———
  function cardColor(c, vid, quiet) {
    var cur = c.getAttribute('data-v'), tr = c.querySelector('.vc__track');
    if (!tr || !vid || vid === cur) return;
    var keep = c.__vs || (c.__vs = {});
    var tpl = c.querySelector('template[data-v="' + vid + '"]');
    var next = keep[vid] || (tpl ? Array.prototype.slice.call(tpl.content.cloneNode(true).children) : null);
    if (!next || !next.length) return;
    var sizes = tr.firstElementChild ? tr.firstElementChild.getAttribute('sizes') : null;   // размер карточки мог смениться (фильтр)
    keep[cur] = Array.prototype.slice.call(tr.children);
    while (tr.firstChild) tr.removeChild(tr.firstChild);
    next.forEach(function (im) { if (sizes) im.setAttribute('sizes', sizes); tr.appendChild(im); });
    if (!quiet) eager(next[0]);
    c.setAttribute('data-v', vid);
    var main = vid === c.getAttribute('data-v0');
    each('.vc__ph, .vc__a', function (a) {
      var h = a.getAttribute('href').split('?')[0];
      a.setAttribute('href', main ? h : h + '?c=' + vid);
    }, c);
    each('.vc__c', function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-v') === vid ? 'true' : 'false'); }, c);
    var g = cardGal(c);
    if (g) g.refresh();
  }
  d.addEventListener('click', function (ev) {
    var b = ev.target && ev.target.closest && ev.target.closest('.vc__c');
    if (!b) return;
    ev.preventDefault();
    var c = b.closest('.vc');
    if (!c) return;
    c.__byFilter = false;   // выбор человека — фильтр его не переключает обратно
    cardColor(c, b.getAttribute('data-v'));
  });
  if (fine.matches) {   // мышь: цвет меняется уже при наведении на кружочек (как в примере заказчицы) и так и остаётся
    d.addEventListener('pointerover', function (ev) {
      var b = ev.target && ev.target.closest && ev.target.closest('.vc__c'), c = b && b.closest('.vc');
      if (!c || b.getAttribute('data-v') === c.getAttribute('data-v')) return;
      c.__byFilter = false;
      cardColor(c, b.getAttribute('data-v'));
    }, { passive: true });
  }

  // ——— Ленты: слайдер главной и фото товара (по одному, по кругу, полоски), подборки (страницами) ———
  each('[data-rail]', function (r) {
    var track = r.querySelector('[data-track]');
    if (!track) return;
    var items = track.children, n = 0;
    var slides = r.getAttribute('data-rail') === 'slides';
    var box = r.querySelector('.rail__bars'), bars = box ? box.children : [];
    var prev = r.querySelector('[data-step="-1"]'), next = r.querySelector('[data-step="1"]');
    var step = function () { return (items.length > 1 && items[1].offsetLeft - items[0].offsetLeft) || track.clientWidth; };
    var max = function () { return track.scrollWidth - track.clientWidth; };
    var cur = -1;
    var update = function () {
      var x = track.scrollLeft;
      if (n > 1 && bars.length) {
        var i = Math.max(0, Math.min(n - 1, Math.round(x / step())));
        if (i !== cur) {
          cur = i;
          for (var k = 0; k < bars.length; k++) bars[k].classList.toggle('is-on', k === i);
        }
      }
      if (!slides) {
        if (prev) prev.disabled = x <= 2;
        if (next) next.disabled = x >= max() - 2;
      }
    };
    var raf = 0;
    track.addEventListener('scroll', function () {
      if (!raf) raf = requestAnimationFrame(function () { raf = 0; update(); });
    }, { passive: true });
    w.addEventListener('resize', update);
    // Число фото и полоски — заново, когда на странице товара выбрали другой цвет
    var setup = r.__refresh = function () {
      n = items.length;
      [box, prev, next].forEach(function (x) { if (x) x.hidden = n < 2; });
      if (n > 1) track.tabIndex = 0; else track.removeAttribute('tabindex');   // листается стрелками клавиатуры
      if (box) {
        var html = '';
        for (var k = 0; k < n && n > 1; k++) html += '<i></i>';
        box.innerHTML = html;
      }
      cur = -1;
      track.scrollLeft = 0;
      update();
    };
    setup();
    var aim = null, aimT = 0;   // куда уже едем: быстрые повторные нажатия считаются от цели, а не от середины пути
    var go = function (dir) {
      var x = aim !== null ? aim : track.scrollLeft, m = max(), s = step(), to;
      if (slides) {
        to = x + dir * s;
        if (dir > 0 && x >= m - 2) to = 0;          // с последнего — на первое
        else if (dir < 0 && x <= 2) to = m;         // с первого — на последнее
      } else {
        to = x + dir * s * Math.max(1, Math.floor(track.clientWidth / s));   // страница — сколько карточек видно
      }
      aim = Math.max(0, Math.min(m, to));
      clearTimeout(aimT);
      aimT = setTimeout(function () { aim = null; }, 700);
      track.scrollTo({ left: aim, behavior: still.matches ? 'auto' : 'smooth' });
    };
    if (prev) prev.addEventListener('click', function () { go(-1); });
    if (next) next.addEventListener('click', function () { go(1); });
  });
  // Остальные фото слайдера и товара — после загрузки страницы, чтобы при свайпе они уже были
  w.addEventListener('load', function () {
    each('.pg img[loading="lazy"], .hero img[loading="lazy"]', function (i) {
      if (i.getClientRects().length) i.loading = 'eager';   // скрытые на ноутбуке слайды не качаем
    });
  });
  // Строка категорий: текущая — на виду
  each('.tabs__in', function (sc) {
    var a = sc.querySelector('[aria-current]');
    if (a && sc.scrollWidth > sc.clientWidth) sc.scrollLeft = a.offsetLeft - (sc.clientWidth - a.offsetWidth) / 2;
  });

  // ——— Избранное: список адресов вещей в localStorage (живёт после перезагрузки, но только в этом браузере) ———
  var KEY = 'attre-fav', mem = [];
  function read() {
    try {
      var v = JSON.parse(w.localStorage.getItem(KEY) || '[]');
      if (Array.isArray(v)) return v.filter(function (s) { return typeof s === 'string'; });
    } catch (e) { /* приватный режим или хранилище запрещено — список живёт, пока открыта страница */ }
    return mem.slice();
  }
  function write(list) {
    mem = list.slice();
    try { w.localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* см. read() */ }
  }
  var favGrid = d.querySelector('[data-fav-grid]');
  function favPage(list) {
    var cards = {}, shown = [], lost = false;
    each('[data-slug]', function (li) { cards[li.getAttribute('data-slug')] = li; }, favGrid);
    var known = list.filter(function (s) { return cards[s]; });
    if (known.length < list.length) {   // вещь сняли с сайта — убираем из списка, чтобы не врал счётчик
      write(known);
      each('[data-fav-n]', function (el) { el.textContent = known.length ? String(known.length) : ''; });
      list = known;
    }
    for (var i = list.length - 1; i >= 0; i--) if (cards[list[i]]) shown.push(cards[list[i]]);   // недавние — первыми
    each('[data-slug]', function (li) {
      var on = shown.indexOf(li) >= 0;
      if (!on && !li.hidden && li.contains(d.activeElement)) lost = true;
      li.hidden = !on;
    }, favGrid);
    shown.forEach(function (li) { favGrid.appendChild(li); });
    var empty = d.querySelector('[data-fav-empty]'), send = d.querySelector('[data-fav-send]'), wa = d.querySelector('[data-fav-wa]');
    if (empty) empty.hidden = shown.length > 0;
    if (send) send.hidden = !shown.length;
    if (wa && shown.length && T.wa) {
      var lines = shown.map(function (li) {
        var a = li.querySelector('a[href]');
        return fill(fill(fill(T.waItem, 'name', li.getAttribute('data-name')), 'id', li.getAttribute('data-id')), 'url', a ? a.href : '');
      });
      wa.href = 'https://wa.me/' + T.wa + '?text=' + encodeURIComponent(T.waFav + '\n' + lines.join('\n'));
    }
    if (lost) { var m = d.getElementById('main'); if (m) m.focus({ preventScroll: true }); }
  }
  function sync() {
    var list = read();
    each('[data-fav]', function (b) {
      var on = list.indexOf(b.getAttribute('data-fav')) >= 0;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      if (T.favAdd) b.title = on ? T.favDel : T.favAdd;
    });
    each('[data-fav-n]', function (el) { el.textContent = list.length ? String(list.length) : ''; });
    if (favGrid) favPage(list);
  }
  d.addEventListener('click', function (ev) {
    var b = ev.target && ev.target.closest && ev.target.closest('[data-fav]');
    if (!b) return;
    ev.preventDefault();
    var s = b.getAttribute('data-fav'), list = read(), i = list.indexOf(s);
    if (i >= 0) list.splice(i, 1); else list.push(s);
    write(list);
    sync();
  });
  w.addEventListener('storage', function (ev) { if (ev.key === KEY) sync(); });   // другая вкладка
  w.addEventListener('pageshow', function (ev) { if (ev.persisted) { close(false); sync(); } });   // «назад» из кэша
  sync();

  // ——— Корзина: [{slug, v, qty}] в localStorage, как избранное; v — выбранный цвет (одна вещь в двух цветах — две строки).
  // Заказ — готовое сообщение в WhatsApp: сервера нет, личных данных человек на сайте не вводит, сообщение отправляет сам ———
  var CART = 'attre-cart', QMAX = 5, cartMem = [];
  var ckey = function (x) { return x.slug + '|' + (x.v || ''); };
  function cartRead() {
    var v = null, seen = {};
    try { v = JSON.parse(w.localStorage.getItem(CART) || '[]'); } catch (e) { /* см. read() */ }
    if (!Array.isArray(v)) v = cartMem;
    return v.filter(function (x) {
      if (!x || typeof x.slug !== 'string' || seen[ckey(x)]) return false;
      return (seen[ckey(x)] = true);
    }).map(function (x) {
      return { slug: x.slug, v: typeof x.v === 'string' ? x.v : '', qty: Math.max(1, Math.min(QMAX, Math.floor(Number(x.qty)) || 1)) };
    });
  }
  function cartWrite(list) {
    cartMem = list.map(function (x) { return { slug: x.slug, v: x.v || '', qty: x.qty }; });
    try { w.localStorage.setItem(CART, JSON.stringify(cartMem)); } catch (e) { /* см. read() */ }
  }
  // v0 — основной цвет: запись из корзины, сделанной до появления цветов (без v), считается им
  function cartFind(list, s, v, v0) {
    for (var i = 0; i < list.length; i++) {
      var x = list[i];
      if (x.slug === s && ((x.v || '') === (v || '') || (!x.v && v && v === v0))) return x;
    }
    return null;
  }
  var cartBox = d.querySelector('[data-cart-list]');
  function cartPage(list) {
    var rows = {}, first = {}, lost = false;
    each('[data-slug]', function (li) {
      var s = li.getAttribute('data-slug');
      rows[s + '|' + (li.getAttribute('data-v') || '')] = li;
      if (!first[s]) first[s] = li;   // строка основного цвета — первая у вещи
    }, cartBox);
    // вещь или её цвет сняли с сайта — убираем; запись без цвета — основной цвет; количество — не больше предела
    // строки (у штучной вещи — остаток); одинаковые позиции складываем
    var fixed = [], same = {};
    list.forEach(function (x) {
      var li = rows[ckey(x)];
      if (!li && !x.v && first[x.slug]) { li = first[x.slug]; x = { slug: x.slug, v: li.getAttribute('data-v') || '', qty: x.qty }; }
      if (!li) return;
      var max = Number(li.getAttribute('data-max')) || QMAX, k = ckey(x);
      if (same[k]) { same[k].qty = Math.min(max, same[k].qty + x.qty); return; }
      fixed.push(same[k] = { slug: x.slug, v: x.v || '', qty: Math.min(x.qty, max) });
    });
    if (JSON.stringify(fixed) !== JSON.stringify(list)) { cartWrite(fixed); list = fixed; }
    var shown = list.map(function (x) { return rows[ckey(x)]; }).reverse();   // недавние — первыми
    each('[data-slug]', function (li) {
      var on = shown.indexOf(li) >= 0;
      if (!on && !li.hidden && li.contains(d.activeElement)) lost = true;
      li.hidden = !on;
    }, cartBox);
    // Переставляем строки, только если порядок другой: перенос в DOM снимает фокус с нажатой кнопки «+»
    var now = Array.prototype.filter.call(cartBox.children, function (li) { return shown.indexOf(li) >= 0; });
    if (now.some(function (li, i) { return li !== shown[i]; })) shown.forEach(function (li) { cartBox.appendChild(li); });
    var sum = 0, priced = true, lines = [];
    shown.forEach(function (li) {
      var x = cartFind(list, li.getAttribute('data-slug'), li.getAttribute('data-v'));
      var max = Number(li.getAttribute('data-max')) || QMAX, price = Number(li.getAttribute('data-price')) || 0;
      var q = li.querySelector('[data-cart-qty]'), out = li.querySelector('[data-cart-sum]');
      if (q) q.textContent = String(x.qty);
      each('[data-cart-step]', function (b) {   // aria-disabled, а не disabled: нажатая кнопка не теряет фокус
        var up = b.getAttribute('data-cart-step') === '1';
        b.setAttribute('aria-disabled', (up ? x.qty >= max : x.qty <= 1) ? 'true' : 'false');
      }, li);
      if (out && price) out.textContent = money(price * x.qty);
      if (li.hasAttribute('data-off')) return;   // продано или «скоро в наличии» — в заказ не идёт
      if (price) sum += price * x.qty; else priced = false;
      var a = li.querySelector('a[href]'), col = li.getAttribute('data-color');
      var item = { n: lines.length + 1, name: li.getAttribute('data-name'), color: col && T.waColor ? fill(T.waColor, 'color', col) : '',
        id: li.getAttribute('data-id'), qty: x.qty, url: a ? a.href : '' };
      lines.push(Object.keys(item).reduce(function (s, k) { return fill(s, k, item[k]); }, T.waCartItem || ''));
    });
    var empty = d.querySelector('[data-cart-empty]'), send = d.querySelector('[data-cart-send]');
    var total = d.querySelector('[data-cart-total]'), dlv = d.querySelector('[data-cart-dlv]'), wa = d.querySelector('[data-cart-wa]');
    cartBox.hidden = !shown.length;
    if (empty) empty.hidden = shown.length > 0;
    if (send) send.hidden = !lines.length;
    if (total && T.cartAsk) total.textContent = priced ? money(sum) : T.cartAsk;   // у всех вещей есть цена — сумма
    if (dlv) dlv.hidden = !priced;
    if (wa && lines.length && T.wa) {
      var msg = [T.waCart].concat(lines, '', priced ? fill(T.waCartTotal, 'sum', money(sum)) : T.waCartAsk, T.waCartBonus);
      wa.href = 'https://wa.me/' + T.wa + '?text=' + encodeURIComponent(msg.join('\n'));
    }
    if (lost) { var m = d.getElementById('main'); if (m) m.focus({ preventScroll: true }); }
    return list;
  }
  function cartSync() {
    var list = cartRead();
    if (cartBox) list = cartPage(list);
    var n = list.reduce(function (s, x) { return s + x.qty; }, 0);   // в шапке — число вещей с учётом количества
    each('[data-cart-n]', function (el) { el.textContent = n ? String(n) : ''; });
    each('[data-cart-add]', function (b) {   // товар: «в корзину» ↔ «перейти в корзину» — для выбранного цвета
      var s = b.getAttribute('data-cart-add'), on = !!cartFind(list, s, b.getAttribute('data-v'), b.getAttribute('data-v0'));
      b.hidden = on;
      each('[data-cart-go="' + s + '"]', function (a) { a.hidden = !on; });
    });
  }
  d.addEventListener('click', function (ev) {
    var b = ev.target && ev.target.closest && ev.target.closest('[data-cart-add], [data-cart-step], [data-cart-del]');
    if (!b) return;
    ev.preventDefault();
    if (b.getAttribute('aria-disabled') === 'true') return;
    var list = cartRead(), s = b.getAttribute('data-cart-add');
    if (s) {
      var v = b.getAttribute('data-v') || '';
      if (!cartFind(list, s, v, b.getAttribute('data-v0'))) list.push({ slug: s, v: v, qty: 1 });
      cartWrite(list);
      cartSync();
      var go = d.querySelector('[data-cart-go="' + s + '"]'), live = d.querySelector('[data-cart-live]');
      if (go) go.focus({ preventScroll: true });   // кнопка скрылась — фокус на ссылку, что встала на её место
      if (live && T.cartAdded) live.textContent = T.cartAdded;
      return;
    }
    var li = b.closest('[data-slug]'), x = li && cartFind(list, li.getAttribute('data-slug'), li.getAttribute('data-v'));
    if (!x) return;
    if (b.hasAttribute('data-cart-del')) list.splice(list.indexOf(x), 1);
    else x.qty = Math.max(1, Math.min(Number(li.getAttribute('data-max')) || QMAX, x.qty + Number(b.getAttribute('data-cart-step'))));
    cartWrite(list);
    cartSync();
  });
  w.addEventListener('storage', function (ev) { if (ev.key === CART) cartSync(); });
  w.addEventListener('pageshow', function (ev) { if (ev.persisted) cartSync(); });
  cartSync();

  // ——— Товар: цвет — кружочки под «в корзину». Выбор меняет фото, строки «цвет» и «материал», цвет для корзины
  // и текст сообщения в WhatsApp; адрес запоминает цвет (?c=black) — ссылкой можно поделиться ———
  var pick = d.querySelector('.pcol');
  if (pick) {
    var pg = d.querySelector('.pg'), ptrack = pg && pg.querySelector('[data-track]');
    var radios = pick.querySelectorAll('input[name="pcol"]'), v0 = radios.length ? radios[0].value : '';
    var waBtn = d.querySelector('[data-wa-c]'), pkeep = {};
    var setColor = function (inp, initial) {
      var vid = inp.value, was = pg && pg.getAttribute('data-v');
      each('[data-pcol-name]', function (el) { el.textContent = inp.getAttribute('data-name'); });
      each('[data-pcol-mat]', function (el) { el.textContent = inp.getAttribute('data-mat'); });
      if (pg && ptrack && was && vid !== was) {
        var tpl = pg.querySelector('template[data-pv="' + vid + '"]');
        var next = pkeep[vid] || (tpl ? Array.prototype.slice.call(tpl.content.cloneNode(true).children) : null);
        if (next && next.length) {
          pkeep[was] = Array.prototype.slice.call(ptrack.children);
          while (ptrack.firstChild) ptrack.removeChild(ptrack.firstChild);
          next.forEach(function (f, i) { if (i < 2) eager(f.querySelector('img')); ptrack.appendChild(f); });
          pg.setAttribute('data-v', vid);
          if (pg.__refresh) pg.__refresh();
        }
      }
      each('[data-cart-add]', function (b) { b.setAttribute('data-v', vid); });
      var link = location.pathname + (vid === v0 ? '' : '?c=' + vid);
      if (waBtn && T.waProductC && T.wa) {
        var msg = [['name', waBtn.getAttribute('data-wa-name')], ['color', inp.getAttribute('data-name')], ['id', waBtn.getAttribute('data-wa-id')],
                   ['url', waBtn.getAttribute('data-wa-url') + (vid === v0 ? '' : '?c=' + vid)]]
          .reduce(function (m, kv) { return fill(m, kv[0], kv[1]); }, T.waProductC);
        waBtn.href = 'https://wa.me/' + T.wa + '?text=' + encodeURIComponent(msg);
      }
      if (!initial) { try { history.replaceState(null, '', link + location.hash); } catch (e) { /* file:// */ } }
      cartSync();
    };
    pick.addEventListener('change', function (ev) { if (ev.target && ev.target.name === 'pcol') setColor(ev.target); });
    var cm = /[?&]c=([a-z0-9-]+)/.exec(location.search);   // пришли из карточки, где выбрали цвет
    var start = cm && pick.querySelector('input[name="pcol"][value="' + cm[1] + '"]');
    if (start && start.value !== v0) { start.checked = true; setColor(start, true); }
    w.addEventListener('pageshow', function (ev) {   // «назад» из кэша: браузер мог вернуть отметку — фото под неё
      var on = pick.querySelector('input[name="pcol"]:checked');
      if (ev.persisted && on && pg && on.value !== pg.getAttribute('data-v')) setColor(on, true);
    });
  }

  // ——— Каталог: фильтр (материал, цвет, цена) и сортировка; ритм витрины перестраивается под найденное ———
  var SIZES = { w1: '(min-width: 600px) 25vw, 100vw', w2: '(min-width: 600px) 25vw, 100vw', h: '(min-width: 600px) 25vw, 50vw' };
  function rhythm(n) {   // как rhythm() в themes/v4.py
    var out = [];
    for (var i = 0; i < n; i++) {
      var c = i % 3;
      out.push({ k: c === 0 ? 'w' : c === 1 ? 'h' : 'h2', r: c === 0 && Math.floor(i / 3) % 2 === 1 && i + 2 < n });
    }
    if (n % 3 === 2) { out[n - 2] = { k: 'h', r: false }; out[n - 1] = { k: 'h2', r: false }; }
    return out;
  }
  var grid = d.querySelector('[data-grid]'), form = d.querySelector('[data-filter]');
  function relayout(list) {
    var ks = rhythm(list.length);
    list.forEach(function (c, i) {
      var k = ks[i], wide = k.k === 'w';
      if (c.classList.contains('vc--w') !== wide) {   // карточка сменила размер — её фото снова с первого
        var tr = c.querySelector('.vc__track');
        if (tr) tr.scrollLeft = 0;
      }
      c.classList.toggle('vc--w', wide);
      c.classList.toggle('vc--2', k.k === 'h2');
      c.classList.toggle('vc--r', k.r);
      var sz = wide ? (c.classList.contains('vc--one') ? SIZES.w1 : SIZES.w2) : SIZES.h;
      each('.vc__img', function (im) { if (im.getAttribute('sizes') !== sz) im.setAttribute('sizes', sz); }, c);
    });
    requestAnimationFrame(function () { galsUpdate(grid); });
  }
  if (grid && form) {
    var words = function (el, a) { return (el.getAttribute(a) || '').split(' ').filter(Boolean); };
    var all = Array.prototype.map.call(grid.children, function (c, i) {
      return { el: c, i: i, mat: words(c, 'data-mat'), col: words(c, 'data-col'), price: Number(c.getAttribute('data-price')) || 0,
               isNew: c.hasAttribute('data-new'), pop: c.hasAttribute('data-pop'), sold: c.hasAttribute('data-sold') };
    });
    var range = form.querySelector('[data-range]');
    var lo = range ? Number(range.getAttribute('data-min')) : 0, hi = range ? Number(range.getAttribute('data-max')) : 0;
    var rMin = form.querySelector('input[name="min"]'), rMax = form.querySelector('input[name="max"]');
    var bar = form.querySelector('[data-fill]');
    var none = d.querySelector('[data-none]'), nOut = d.querySelector('[data-n]'), fc = d.querySelector('[data-fcount]');
    var show = form.querySelector('[data-f-show]');
    var live = !!(rMin && rMax && !rMin.disabled);
    var picked = function (name) {
      return Array.prototype.filter.call(form.querySelectorAll('input[name="' + name + '"]'), function (x) { return x.checked; })
        .map(function (x) { return x.value; });
    };
    var state = function () {
      var r = form.querySelector('input[name="sort"]:checked');
      return { sort: r ? r.value : 'rec', mat: picked('mat'), col: picked('col'),
               min: live ? Number(rMin.value) : lo, max: live ? Number(rMax.value) : hi };
    };
    var narrowed = function (s) { return s.min > lo || s.max < hi; };
    var any = function (want, has) { return !want.length || want.some(function (x) { return has.indexOf(x) >= 0; }); };
    var match = function (c, s) {
      return any(s.mat, c.mat) && any(s.col, c.col) && (!narrowed(s) || (c.price && c.price >= s.min && c.price <= s.max));
    };
    var cmp = function (sort) {
      return function (a, b) {
        if (a.sold !== b.sold) return a.sold ? 1 : -1;   // проданные — в конце при любой сортировке
        var k = 0;
        if (sort === 'new') k = b.isNew - a.isNew;
        else if (sort === 'pop') k = b.pop - a.pop;
        else if (sort === 'asc' || sort === 'desc') {
          if (!a.price !== !b.price) return a.price ? -1 : 1;   // «цена по запросу» — после вещей с ценой
          k = sort === 'asc' ? a.price - b.price : b.price - a.price;
        }
        return k || a.i - b.i;
      };
    };
    var paint = function () {   // бегунок: полоса между ручками и подписи «от — до»
      if (!rMin || !rMax) return;
      var a = Number(rMin.value), b = Number(rMax.value), span = (hi - lo) || 1;
      if (bar) { bar.style.left = ((a - lo) / span * 100) + '%'; bar.style.right = ((hi - b) / span * 100) + '%'; }
      rMin.style.zIndex = a > lo + span / 2 ? 3 : 1;   // у правого края левую ручку тоже можно взять
      var oa = form.querySelector('[data-out="min"]'), ob = form.querySelector('[data-out="max"]');
      if (oa) oa.textContent = money(a);
      if (ob) ob.textContent = money(b);
    };
    var remember = function (s) {   // фильтр живёт в адресе: ссылкой можно поделиться, «назад» вернёт к нему
      var q = [];
      if (s.sort !== 'rec') q.push('sort=' + s.sort);
      if (s.mat.length) q.push('mat=' + s.mat.join(','));
      if (s.col.length) q.push('col=' + s.col.join(','));
      if (narrowed(s)) q.push('price=' + s.min + '-' + s.max);
      try { history.replaceState(null, '', location.pathname + (q.length ? '?' + q.join('&') : '') + location.hash); } catch (e) { /* file:// */ }
    };
    var restore = function () {
      var q = {};
      location.search.replace(/^\?/, '').split('&').forEach(function (kv) {
        var p = kv.split('=');
        if (p[0]) { try { q[p[0]] = decodeURIComponent(p[1] || ''); } catch (e) { /* битый адрес */ } }
      });
      each('input[name="sort"]', function (x) { if (x.value === q.sort) x.checked = true; }, form);
      ['mat', 'col'].forEach(function (name) {
        var want = (q[name] || '').split(',');
        each('input[name="' + name + '"]', function (x) { x.checked = want.indexOf(x.value) >= 0; }, form);
      });
      var m = /^(\d+)-(\d+)$/.exec(q.price || '');
      if (m && live) { rMin.value = m[1]; rMax.value = m[2]; }
    };
    var tint = function (list, cols) {   // фильтр «цвет»: карточка показывает фото подходящего цвета, без фильтра — основного
      list.forEach(function (c) {
        var el = c.el, btns = el.querySelectorAll('.vc__c');
        if (!btns.length) return;
        var cur = el.querySelector('.vc__c[aria-pressed="true"]'), want = null;
        if (cols.length) {
          if (cur && cols.indexOf(cur.getAttribute('data-k')) >= 0) return;
          for (var i = 0; i < btns.length && !want; i++) if (cols.indexOf(btns[i].getAttribute('data-k')) >= 0) want = btns[i].getAttribute('data-v');
          if (want) { el.__byFilter = true; cardColor(el, want, true); }
        } else if (el.__byFilter) {
          el.__byFilter = false;
          cardColor(el, el.getAttribute('data-v0'), true);
        }
      });
    };
    var apply = function (save) {
      var s = state();
      var list = all.filter(function (c) { return match(c, s); }).sort(cmp(s.sort));
      tint(list, s.col);
      all.forEach(function (c) { c.el.hidden = list.indexOf(c) < 0; });
      list.forEach(function (c) { grid.appendChild(c.el); });
      relayout(list.map(function (c) { return c.el; }));
      if (nOut) nOut.textContent = list.length;
      if (show && T.show) show.textContent = fill(T.show, 'n', list.length);
      var k = s.mat.length + s.col.length + (narrowed(s) ? 1 : 0);
      if (fc) fc.textContent = k ? '(' + k + ')' : '';
      if (none) none.hidden = list.length > 0;
      if (save) remember(s);
    };
    form.addEventListener('input', function (ev) {
      var x = ev.target;
      if (live && (x === rMin || x === rMax)) {   // ручки не перескакивают друг через друга
        var gap = Number(rMin.step) || 50;
        if (Number(rMin.value) > Number(rMax.value) - gap) {
          if (x === rMin) rMin.value = Number(rMax.value) - gap; else rMax.value = Number(rMin.value) + gap;
        }
        paint();
      }
      apply(true);
    });
    form.addEventListener('change', function () { apply(true); });   // старые Safari шлют у радио только change
    form.addEventListener('submit', function (ev) { ev.preventDefault(); });
    form.addEventListener('reset', function () { setTimeout(function () { paint(); apply(true); }, 0); });
    each('[data-f-reset]', function (b) { if (!form.contains(b)) b.addEventListener('click', function () { form.reset(); }); });
    restore();
    paint();
    apply(false);
  }

  // ——— Видео «за кадром»: играет без звука, пока на экране; кнопка пауза/смотреть ———
  // При «уменьшить движение» и экономии трафика само не запускается.
  each('[data-film]', function (v) {
    var btn = v.parentNode.querySelector('[data-film-btn]');
    v.removeAttribute('controls');
    var wish = null;   // выбор человека важнее автозапуска
    var auto = !still.matches && !thrifty;
    var label = function () { if (btn && T.play) btn.textContent = v.paused ? T.play : T.pause; };
    var play = function () { var pr = v.play(); if (pr && pr.catch) pr.catch(label); };
    v.addEventListener('play', label);
    v.addEventListener('pause', label);
    var toggle = function () {
      if (v.paused) { wish = 'play'; play(); } else { wish = 'pause'; v.pause(); }
    };
    if (btn) btn.addEventListener('click', toggle);
    v.addEventListener('click', toggle);   // надписей на видео нет — пауза нажатием на само видео
    if (hasIO) {
      new IntersectionObserver(function (es) {
        if (es[0].isIntersecting) { if (wish === 'play' || (wish === null && auto)) play(); }
        else if (!v.paused) v.pause();
      }, { threshold: 0.3 }).observe(v);
    }
    label();
  });
})();
