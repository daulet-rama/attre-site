// attré · Вариант 4 «Витрина». site.js подключён ради общего флага; всё поведение темы — здесь:
// меню и нижние листы (фокус внутри, Esc), плавные строки details, проявление фото при появлении,
// мягкая смена второго фото у видимых карточек, счётчик и стрелки галереи.
// Без JS всё видно: скрытые состояния в CSS — только при html.js; движение — только без reduced motion.
(function () {
  'use strict';
  var d = document, root = d.documentElement, w = window;
  w.__v4 = 1;
  root.classList.add('js');   // скрипт пришёл позже 6-секундной страховки — возвращаем полный режим

  var mq = function (q) { return w.matchMedia ? w.matchMedia(q) : { matches: false }; };
  var still = mq('(prefers-reduced-motion: reduce)');
  var fine = mq('(hover: hover) and (pointer: fine)');   // мышь: второе фото — по наведению
  var broad = mq('(min-width: 600px)');                    // крупная карточка — два фото рядом
  var moving = function () { return !still.matches; };
  var each = function (sel, fn, ctx) { Array.prototype.forEach.call((ctx || d).querySelectorAll(sel), fn); };
  var hasIO = 'IntersectionObserver' in w;
  var conn = navigator.connection;
  var thrifty = !!(conn && (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || '')));

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
      box.querySelectorAll('a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'),
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
  w.addEventListener('pageshow', function (ev) { if (ev.persisted) close(false); });

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
      if (!moving()) return;
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

  // ——— Фото: готово (загружено и раскодировано) ———
  function ready(imgs, fn, ms) {
    var left = imgs.length, done = false;
    var fin = function () { if (!done) { done = true; fn(); } };
    if (!left) { fin(); return; }
    var one = function () { if (--left <= 0) fin(); };
    imgs.forEach(function (i) {
      if (i.decode) i.decode().then(one, one);
      else if (i.complete) one();
      else { i.addEventListener('load', one); i.addEventListener('error', one); }
    });
    setTimeout(fin, ms || 2600);   // сеть медленная — не держим витрину пустой
  }
  function real(i) {
    var s = i.getAttribute('src') || '';
    return s && s.indexOf('data:') !== 0 && i.getClientRects().length > 0;
  }
  function hydrate(i) {   // второе фото карточки: адрес подставляем только когда оно нужно
    if (!i || !i.hasAttribute('data-src')) return;
    i.addEventListener('load', function () { i.classList.add('is-ld'); }, { once: true });
    var ss = i.getAttribute('data-srcset');
    if (ss) i.srcset = ss;
    i.src = i.getAttribute('data-src');
    i.removeAttribute('data-src');
    i.removeAttribute('data-srcset');
  }
  function pairShown(card) { return broad.matches && !!card && card.classList.contains('vc--w'); }
  function prime(box) {
    each('img[loading="lazy"]', function (i) { i.loading = 'eager'; }, box);
    each('img[data-src]', function (i) {
      if (pairShown(i.closest('.vc')) || fine.matches) hydrate(i);
    }, box);
  }

  // Обложка и главное фото товара «оседают», когда фото готово. Ушли с экрана или досмотрели —
  // движение заканчиваем (is-rest): меньше одновременных анимаций и снимаем will-change.
  each('[data-settle]', function (box) {
    var img = box.querySelector('img');
    var rest = function () { box.classList.add('is-rest'); };
    var go = function () { box.classList.add('is-in'); };
    if (!img || !moving()) { go(); rest(); return; }
    ready([img], go, 3000);
    img.addEventListener('transitionend', function (ev) { if (ev.propertyName === 'scale') rest(); });
    if (hasIO) {
      var io = new IntersectionObserver(function (es) {
        if (!es[0].isIntersecting && box.classList.contains('is-in')) { rest(); io.disconnect(); }
      });
      io.observe(box);
    }
  });

  // ——— Проявление при появлении: один раз, когда фото рядом с экраном и готово ———
  // Наблюдаем карточку, а не саму «штору»: у элемента с clip-path IntersectionObserver видит площадь 0,
  // а ленивые фото внутри полностью обрезанного блока Chrome не грузит — их грузит prime().
  var pending = Array.prototype.slice.call(d.querySelectorAll('[data-rv]'));
  var nears = Array.prototype.slice.call(d.querySelectorAll('[data-rv], [data-near]'));
  function show(b) {
    if (b.__rv) return;
    b.__rv = 1;
    prime(b);
    if (!moving()) { b.classList.add('is-in'); return; }
    ready(Array.prototype.filter.call(b.querySelectorAll('img'), real), function () { b.classList.add('is-in'); });
  }
  if (!hasIO) {
    nears.forEach(prime);
    pending.forEach(show);
  } else {
    var near = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) { near.unobserve(en.target); prime(en.target); } });
    }, { rootMargin: '600px 0px 900px 0px' });
    nears.forEach(function (b) { near.observe(b); });
    var rio = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) { rio.unobserve(en.target); show(en.target); } });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });
    pending.forEach(function (b) { rio.observe(b); });
    // Страховка: после остановки прокрутки всё, что на экране и ещё скрыто, проявляем
    var sweepT = 0;
    var sweep = function () {
      var vw = w.innerWidth || root.clientWidth, vh = w.innerHeight || root.clientHeight;
      pending = pending.filter(function (b) {
        if (b.__rv) return false;
        var r = b.getBoundingClientRect();
        if (r.width && r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw) { show(b); return false; }
        return true;
      });
    };
    w.addEventListener('scroll', function () { clearTimeout(sweepT); sweepT = setTimeout(sweep, 500); }, { passive: true });
    w.addEventListener('load', function () { setTimeout(sweep, 1500); });
  }
  if (broad.addEventListener) {
    broad.addEventListener('change', function () {
      if (broad.matches) each('.vc--w.is-in .vc__img--b[data-src]', hydrate);
    });
  }
  if (fine.matches) {   // мышь: второе фото подгружаем и по наведению, если до него не дошла очередь
    d.addEventListener('pointerover', function (ev) {
      var c = ev.target && ev.target.closest && ev.target.closest('.vc');
      if (c) hydrate(c.querySelector('.vc__img--b[data-src]'));
    }, { passive: true });
  }

  // ——— Второе фото сменяет первое: только видимые карточки, по одной за раз, раз в ~4 c ———
  var cards = [];
  if (hasIO && moving() && !fine.matches && !thrifty) {
    each('[data-vc]', function (c) {
      var m = c.querySelector('.vc__media'), b = c.querySelector('.vc__img--b');
      if (m && b) cards.push({ el: c, m: m, b: b, t: 0, vis: false });
    });
  }
  var timer = 0, lastFlip = 0;
  function eligible(c) {
    return c.vis && c.b.classList.contains('is-ld') && c.el.classList.contains('is-in') && !pairShown(c.el);
  }
  function tick() {
    if (d.hidden || panel) return;
    var now = Date.now();
    if (now - lastFlip < 1400) return;   // смена идёт 1.2 c — следующая только после неё
    var best = null;
    cards.forEach(function (c) {
      if (eligible(c) && now - c.t >= 4000 && (!best || c.t < best.t)) best = c;
    });
    if (!best) return;
    best.m.classList.toggle('is-alt');
    best.t = now;
    lastFlip = now;
  }
  function pace() {   // таймер живёт, только пока на экране есть такие карточки
    var any = cards.some(function (c) { return c.vis; });
    if (any && !timer) timer = setInterval(tick, 200);
    else if (!any && timer) { clearInterval(timer); timer = 0; }
  }
  if (cards.length) {
    var vio = new IntersectionObserver(function (es) {
      var now = Date.now();
      es.forEach(function (en) {
        var c = en.target.__v4;
        var v = en.isIntersecting && en.intersectionRatio >= 0.5;
        if (v && !c.vis) { c.t = now; hydrate(c.b); }   // первая смена — не раньше чем через ~4 c на экране
        c.vis = v;
      });
      pace();
    }, { threshold: [0, 0.5] });
    cards.forEach(function (c) { c.el.__v4 = c; vio.observe(c.el); });
  }

  // ——— Галерея товара: счётчик «2 / 5», стрелки по кругу, следующее фото — заранее ———
  each('[data-pg]', function (g) {
    var track = g.querySelector('.pg__track');
    var out = g.querySelector('.pg__count');
    var slides = track ? track.children : [];
    var n = slides.length;
    if (!track || n < 2) return;
    track.tabIndex = 0;   // листается стрелками клавиатуры
    var index = function () {
      var wd = track.clientWidth;
      return wd ? Math.max(0, Math.min(n - 1, Math.round(track.scrollLeft / wd))) : 0;
    };
    var cur = -1;
    var update = function () {
      var i = index();
      if (i === cur) return;
      cur = i;
      if (out) out.textContent = (i + 1) + ' / ' + n;
      if (slides[i].hasAttribute('data-rv')) show(slides[i]);   // на случай, если наблюдатель не сработал
      var nx = slides[i + 1] && slides[i + 1].querySelector('img[loading="lazy"]');
      if (nx) nx.loading = 'eager';
    };
    var raf = 0;
    track.addEventListener('scroll', function () {
      if (!raf) raf = requestAnimationFrame(function () { raf = 0; update(); });
    }, { passive: true });
    update();
    each('[data-step]', function (b) {
      b.addEventListener('click', function () {
        var i = index() + Number(b.getAttribute('data-step'));
        if (i < 0) i = n - 1; else if (i >= n) i = 0;
        track.scrollTo({ left: i * track.clientWidth, behavior: moving() ? 'smooth' : 'auto' });
      });
    }, g);
  });
})();
