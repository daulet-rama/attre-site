// attré, вариант 5 «Лента». Без фреймворков, поверх site.js (тот ведёт только липкую кнопку WhatsApp).
// Меню-панель под шапкой; лента главной (экран на виду «оживает», фото вещи сменяются, как сторис);
// плитки сетки проявляются по очереди; вид каталога «3 / 2»; галерея товара со «сторис»-полоской;
// вкладки. Без этого скрипта всё видно: скрытые состояния в CSS — только при html.js.
(function () {
  window.__v5 = 1;
  var d = document, root = d.documentElement;
  root.classList.add('js');   // скрипт пришёл позже 6-секундной страховки — возвращаем полный режим
  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var still = function () { return !!(mq && mq.matches); };
  var hasIO = 'IntersectionObserver' in window;
  var each = function (sel, fn, ctx) { Array.prototype.forEach.call((ctx || d).querySelectorAll(sel), fn); };
  // Ошибка в одной части не должна оставить страницу с невидимыми фото: откатываемся в режим без JS
  var run = function (fn) {
    try { fn(); } catch (err) {
      root.classList.remove('js');
      if (window.console && console.error) console.error(err);
    }
  };

  // ——— Меню: бургер ↔ крестик, панель под шапкой, страница затемнена ———
  // Закрывается бургером, тапом по затемнению, Esc, переходом по ссылке и уходом фокуса из шапки.
  run(function () {
    var btn = d.querySelector('[data-v5-menu-btn]');
    var menu = d.querySelector('[data-v5-menu]');
    var top = d.querySelector('[data-v5-top]');
    var shade = d.querySelector('[data-v5-shade]');
    if (!btn || !menu || !top) return;
    var isOpen = function () { return root.classList.contains('v5-menu-open'); };
    var set = function (open, back) {
      root.classList.toggle('v5-menu-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) menu.scrollTop = 0;
      else if (back) btn.focus();
    };
    btn.addEventListener('click', function () { set(!isOpen()); });
    if (shade) shade.addEventListener('click', function () { set(false); });
    menu.addEventListener('click', function (e) { if (e.target.closest('a')) set(false); });
    d.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.key === 'Esc') && isOpen()) { e.preventDefault(); set(false, true); }
    });
    top.addEventListener('focusout', function (e) {
      if (isOpen() && e.relatedTarget && !top.contains(e.relatedTarget)) set(false);
    });
    window.addEventListener('pageshow', function () { if (isOpen()) set(false); });
  });

  // ——— Лента главной ———
  // Экран, видный на ≥ 60 %, получает .is-live один раз: фото отъезжает 1.06 → 1 (6 с), подпись проявляется.
  // Сторис: пока экран на виду, фото вещи сменяются (показ 5 с — время заполнения полоски, растворение 1.2 с).
  // Следующее фото грузится только тогда, когда до него дошла очередь; вне экрана и в фоне — пауза.
  function Show(reel) {
    var base = reel.getAttribute('data-base');
    var sizes = reel.getAttribute('data-sizes') || '100vw';
    var more = JSON.parse(reel.getAttribute('data-more') || '[]');
    var stage = reel.querySelector('.reel__stage');
    var dots = Array.prototype.slice.call(reel.querySelectorAll('.reel__dots i'));
    var slides = [{ el: stage.querySelector('.reel__slide'), ok: true }];
    more.forEach(function (m) { slides.push({ stem: m[0], bg: m[1], el: null, ok: false }); });
    if (slides.length < 2 || dots.length !== slides.length) return null;
    var i = 0, on = false, started = false, waiting = false;

    function next() { return (i + 1) % slides.length; }
    function build(k) {
      var s = slides[k];
      if (s.el || s.bad) return;
      var el = d.createElement('div');
      el.className = 'reel__slide' + (s.bg ? '' : ' reel__slide--plain');
      el.setAttribute('aria-hidden', 'true');
      if (s.bg) el.style.setProperty('--bg', s.bg);
      var ph = d.createElement('div');
      ph.className = 'reel__ph';
      var img = d.createElement('img');
      img.className = 'reel__img';
      img.alt = '';
      img.decoding = 'async';
      img.width = 1200;
      img.height = 1600;
      img.sizes = sizes;
      img.srcset = base + s.stem + '-600.webp 600w, ' + base + s.stem + '-1200.webp 1200w';
      img.src = base + s.stem + '-1200.webp';
      ph.appendChild(img);
      el.appendChild(ph);
      s.el = el;
      var ready = function () { s.ok = true; if (waiting && on && slides[next()] === s) advance(); };
      var fail = function () {
        s.bad = true;
        if (el.parentNode) el.parentNode.removeChild(el);
        var k2 = slides.indexOf(s);
        if (k2 > -1) {
          slides.splice(k2, 1);
          var dot = dots.splice(k2, 1)[0];
          if (dot && dot.parentNode) dot.parentNode.removeChild(dot);
          if (k2 < i) i -= 1;
        }
        if (slides.length < 2) { reel.classList.remove('has-show'); waiting = false; return; }
        if (waiting && on) advance();
      };
      img.addEventListener('load', function () {
        if (img.decode) img.decode().then(ready, ready); else ready();
      }, { once: true });
      img.addEventListener('error', fail, { once: true });
      stage.appendChild(el);
    }
    function tick() {
      var dot = dots[i];
      dot.classList.remove('is-done');
      dot.classList.remove('is-run');
      void dot.offsetWidth;   // перезапуск анимации полоски
      dot.classList.add('is-run');
      build(next());
    }
    function advance() {
      if (slides.length < 2) return;
      var j = next(), s = slides[j];
      if (!s.ok) { waiting = true; if (!s.el) build(j); return; }
      waiting = false;
      // новое фото растворяется поверх прежнего; прежнее прячем, когда новое уже непрозрачно
      var prev = slides[i].el;
      prev.classList.remove('is-cur');
      prev.classList.add('is-prev');
      s.el.classList.remove('is-prev');
      s.el.classList.add('is-cur');
      setTimeout(function () { if (!prev.classList.contains('is-cur')) prev.classList.remove('is-prev'); }, 1300);
      dots[i].classList.remove('is-run');
      dots[i].classList.add('is-done');
      if (j === 0) dots.forEach(function (x) { x.classList.remove('is-done'); x.classList.remove('is-run'); });
      i = j;
      tick();
    }
    dots.forEach(function (dot) {
      dot.firstElementChild.addEventListener('animationend', function () {
        if (dots[i] === dot && on) advance();
      });
    });
    reel.classList.add('has-show');
    return {
      set: function (v) {
        on = v;
        reel.classList.toggle('is-paused', !v);
        if (!v) return;
        if (!started) { started = true; tick(); }
        else if (waiting) advance();
      }
    };
  }

  run(function () {
    var reels = d.querySelectorAll('[data-reel]');
    if (!reels.length) return;
    if (!hasIO) { each('[data-reel]', function (r) { r.classList.add('is-live'); }); return; }
    var c = navigator.connection;
    var lite = !!(c && (c.saveData || /(^|-)2g$/.test(c.effectiveType || '')));
    var seen = [];
    var sync = function () {
      var vis = d.visibilityState !== 'hidden';
      seen.forEach(function (x) { if (x.show) x.show.set(vis && x.on); });
    };
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        var x = e.target.__v5;
        var h = window.innerHeight || root.clientHeight;
        var on = e.isIntersecting && (e.intersectionRatio >= .6 || e.intersectionRect.height >= h * .6);
        if (on) e.target.classList.add('is-live');
        x.on = on;
      });
      sync();
    }, { threshold: [0, .2, .4, .6, .8, 1] });
    each('[data-reel]', function (r) {
      var x = { on: false, show: null };
      if (!still() && !lite && r.hasAttribute('data-more')) {
        try { x.show = Show(r); } catch (err) { x.show = null; }
      }
      r.__v5 = x;
      seen.push(x);
      io.observe(r);
    });
    d.addEventListener('visibilitychange', sync);
  });

  // ——— Плитки сетки: проявляются по очереди, когда на виду и фото загрузилось ———
  // Очередь отпускает по одной плитке раз в 100 мс (проявление .6 с): одновременно движется не больше 6 плиток.
  run(function () {
    var items = d.querySelectorAll('.rv');
    if (!items.length) return;
    if (!hasIO || still()) { each('.rv', function (x) { x.classList.add('is-in'); }); return; }
    var queue = [], timer = 0;
    var pump = function () {
      timer = 0;
      var x = queue.shift();
      if (!x) return;
      x.classList.add('is-in');
      if (queue.length) timer = setTimeout(pump, 100);
    };
    var push = function (x) {
      queue.push(x);
      if (!timer) timer = setTimeout(pump, 0);
    };
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        var x = e.target;
        io.unobserve(x);
        var img = x.querySelector('img');
        if (!img || (img.complete && img.naturalWidth)) { push(x); return; }
        var go = function () { push(x); };
        img.addEventListener('load', go, { once: true });
        img.addEventListener('error', go, { once: true });
      });
    }, { rootMargin: '0px 0px -4% 0px' });
    each('.rv', function (x) { io.observe(x); });
  });

  // ——— Кружки-хайлайты: текущий раздел на виду (ряд прокручивается вбок) ———
  run(function () {
    var row = d.querySelector('.hl__list');
    var cur = row && row.querySelector('[aria-current]');
    if (!cur || row.scrollWidth <= row.clientWidth) return;
    var r = cur.getBoundingClientRect(), rb = row.getBoundingClientRect();
    row.scrollLeft += r.left - rb.left - (row.clientWidth - r.width) / 2;
  });

  // ——— Вид каталога «3 / 2»: запоминаем выбор; первая видимая плитка остаётся на месте ———
  run(function () {
    var bar = d.querySelector('[data-v5-view]');
    var grid = d.querySelector('.grid--cat');
    if (!bar || !grid) return;
    var btns = bar.querySelectorAll('[data-cols]');
    var mark = function () {
      var two = root.classList.contains('v5-two');
      each('[data-cols]', function (b) {
        b.setAttribute('aria-pressed', (b.getAttribute('data-cols') === '2') === two ? 'true' : 'false');
      }, bar);
    };
    Array.prototype.forEach.call(btns, function (b) {
      b.addEventListener('click', function () {
        var two = b.getAttribute('data-cols') === '2';
        if (two === root.classList.contains('v5-two')) return;
        var top = bar.getBoundingClientRect().bottom, anchor = null, tiles = grid.children;
        for (var k = 0; k < tiles.length; k++) {
          if (tiles[k].getBoundingClientRect().bottom > top + 1) { anchor = tiles[k]; break; }
        }
        root.classList.toggle('v5-two', two);
        try { localStorage.setItem('attre-v5-cols', two ? '2' : '3'); } catch (err) { /* приватный режим */ }
        mark();
        if (anchor && anchor !== tiles[0]) {
          window.scrollTo(0, Math.max(0, anchor.getBoundingClientRect().top + window.pageYOffset - top - 2));
        }
        grid.classList.remove('is-swap');
        void grid.offsetWidth;
        grid.classList.add('is-swap');
      });
    });
    mark();
  });

  // ——— Галерея товара: «сторис»-полоска, тап по левой/правой половине, стрелки для мыши и клавиатуры ———
  run(function () {
    each('[data-v5-pg]', function (g) {
      var track = g.querySelector('.pg__track');
      if (!track) return;
      var slides = track.children, n = slides.length;
      var segs = g.querySelectorAll('.pg__bar i');
      var cur = -1, raf = 0;
      var index = function () {
        var w = track.clientWidth;
        return w ? Math.min(n - 1, Math.max(0, Math.round(track.scrollLeft / w))) : 0;
      };
      var mark = function (i) {
        if (i === cur) return;
        cur = i;
        Array.prototype.forEach.call(segs, function (s, k) { s.classList.toggle('is-on', k <= i); });
        slides[i].classList.add('is-live');   // мягкий отъезд фото — один раз при первом показе
      };
      var go = function (i) {
        if (n < 2) return;
        if (i < 0) return;
        if (i >= n) i = 0;
        track.scrollTo({ left: i * track.clientWidth, behavior: still() ? 'auto' : 'smooth' });
      };
      track.addEventListener('scroll', function () {
        if (!raf) raf = requestAnimationFrame(function () { raf = 0; mark(index()); });
      }, { passive: true });
      track.addEventListener('click', function (e) {
        if (n < 2) return;
        var r = track.getBoundingClientRect();
        go(cur + (e.clientX - r.left < r.width / 2 ? -1 : 1));
      });
      each('[data-step]', function (b) {
        b.addEventListener('click', function () { go(cur + Number(b.getAttribute('data-step'))); });
      }, g);
      mark(0);
    });
  });

  // ——— Вкладки «характеристики / доставка / возврат» (WAI-ARIA Tabs: стрелки, Home, End) ———
  run(function () {
    each('[data-v5-tabs]', function (box) {
      var tabs = Array.prototype.slice.call(box.querySelectorAll('[role="tab"]'));
      var panels = tabs.map(function (t) { return d.getElementById(t.getAttribute('aria-controls')); });
      if (!tabs.length || panels.indexOf(null) > -1) return;
      var select = function (i, focus) {
        tabs.forEach(function (t, j) {
          var on = i === j;
          t.setAttribute('aria-selected', on ? 'true' : 'false');
          t.tabIndex = on ? 0 : -1;
          panels[j].hidden = !on;
        });
        if (focus) tabs[i].focus();
      };
      panels.forEach(function (p, j) {
        p.setAttribute('role', 'tabpanel');
        p.setAttribute('aria-labelledby', tabs[j].id);
        p.tabIndex = 0;
      });
      tabs.forEach(function (t, i) {
        t.addEventListener('click', function () { select(i); });
        t.addEventListener('keydown', function (e) {
          var k = tabs.length, j = -1;
          if (e.key === 'ArrowRight') j = (i + 1) % k;
          else if (e.key === 'ArrowLeft') j = (i + k - 1) % k;
          else if (e.key === 'Home') j = 0;
          else if (e.key === 'End') j = k - 1;
          if (j < 0) return;
          e.preventDefault();
          select(j, true);
        });
      });
      box.classList.add('is-ready');
      select(0);
    });
  });
})();
