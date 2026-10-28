// attré · Вариант 4 «Витрина». Меню и нижние листы (фокус внутри, Esc), строки details, ленты со свайпом
// (слайдер главной, фото товара, подборки: стрелки для мыши, счётчик «1 / 5»; фото в карточках — с полосками),
// избранное и корзина (localStorage),
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
    var t = c.querySelector('.vc__track');
    c.__gal = null;
    if (!t || t.children.length < 2) return null;
    var g = { t: t, imgs: t.children, bars: c.querySelectorAll('.vc__bars i'), all: false, aim: null, aimT: 0,
              prev: c.querySelector('[data-vstep="-1"]'), next: c.querySelector('[data-vstep="1"]') };
    g.step = function () { return g.imgs[1].offsetLeft - g.imgs[0].offsetLeft; };
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

  // ——— Ленты: слайдер главной и фото товара (по одному, по кругу, полоски), подборки (страницами) ———
  each('[data-rail]', function (r) {
    var track = r.querySelector('[data-track]');
    if (!track) return;
    var items = track.children, n = items.length;
    var slides = r.getAttribute('data-rail') === 'slides';
    var box = r.querySelector('.rail__bars'), bars = box ? box.children : [];
    var prev = r.querySelector('[data-step="-1"]'), next = r.querySelector('[data-step="1"]');
    if (n < 2) { [box, prev, next].forEach(function (x) { if (x) x.hidden = true; }); return; }
    track.tabIndex = 0;   // листается стрелками клавиатуры
    var step = function () { return (items[1].offsetLeft - items[0].offsetLeft) || track.clientWidth; };
    var max = function () { return track.scrollWidth - track.clientWidth; };
    var cur = -1;
    var update = function () {
      var x = track.scrollLeft;
      if (bars.length) {
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
    update();
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

  // ——— Корзина: [{slug, qty}] в localStorage, как избранное. Заказ — готовое сообщение в WhatsApp: сервера нет,
  // личных данных человек на сайте не вводит, сообщение отправляет сам ———
  var CART = 'attre-cart', QMAX = 5, cartMem = [];
  function cartRead() {
    var v = null, seen = {};
    try { v = JSON.parse(w.localStorage.getItem(CART) || '[]'); } catch (e) { /* см. read() */ }
    if (!Array.isArray(v)) v = cartMem;
    return v.filter(function (x) {
      if (!x || typeof x.slug !== 'string' || seen[x.slug]) return false;
      return (seen[x.slug] = true);
    }).map(function (x) { return { slug: x.slug, qty: Math.max(1, Math.min(QMAX, Math.floor(Number(x.qty)) || 1)) }; });
  }
  function cartWrite(list) {
    cartMem = list.map(function (x) { return { slug: x.slug, qty: x.qty }; });
    try { w.localStorage.setItem(CART, JSON.stringify(cartMem)); } catch (e) { /* см. read() */ }
  }
  function cartFind(list, s) {
    for (var i = 0; i < list.length; i++) if (list[i].slug === s) return list[i];
    return null;
  }
  var cartBox = d.querySelector('[data-cart-list]');
  function cartPage(list) {
    var rows = {}, lost = false;
    each('[data-slug]', function (li) { rows[li.getAttribute('data-slug')] = li; }, cartBox);
    // вещь сняли с сайта — убираем; количество — не больше предела строки (у штучной вещи — остаток)
    var fixed = list.filter(function (x) { return rows[x.slug]; }).map(function (x) {
      return { slug: x.slug, qty: Math.min(x.qty, Number(rows[x.slug].getAttribute('data-max')) || QMAX) };
    });
    if (JSON.stringify(fixed) !== JSON.stringify(list)) { cartWrite(fixed); list = fixed; }
    var shown = list.map(function (x) { return rows[x.slug]; }).reverse();   // недавние — первыми
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
      var x = cartFind(list, li.getAttribute('data-slug'));
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
      var a = li.querySelector('a[href]'), item = { n: lines.length + 1, name: li.getAttribute('data-name'),
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
    each('[data-cart-add]', function (b) {   // товар: «в корзину» ↔ «перейти в корзину»
      var s = b.getAttribute('data-cart-add'), on = !!cartFind(list, s);
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
      if (!cartFind(list, s)) list.push({ slug: s, qty: 1 });
      cartWrite(list);
      cartSync();
      var go = d.querySelector('[data-cart-go="' + s + '"]'), live = d.querySelector('[data-cart-live]');
      if (go) go.focus({ preventScroll: true });   // кнопка скрылась — фокус на ссылку, что встала на её место
      if (live && T.cartAdded) live.textContent = T.cartAdded;
      return;
    }
    var li = b.closest('[data-slug]'), x = li && cartFind(list, li.getAttribute('data-slug'));
    if (!x) return;
    if (b.hasAttribute('data-cart-del')) list.splice(list.indexOf(x), 1);
    else x.qty = Math.max(1, Math.min(Number(li.getAttribute('data-max')) || QMAX, x.qty + Number(b.getAttribute('data-cart-step'))));
    cartWrite(list);
    cartSync();
  });
  w.addEventListener('storage', function (ev) { if (ev.key === CART) cartSync(); });
  w.addEventListener('pageshow', function (ev) { if (ev.persisted) cartSync(); });
  cartSync();

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
    var apply = function (save) {
      var s = state();
      var list = all.filter(function (c) { return match(c, s); }).sort(cmp(s.sort));
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
