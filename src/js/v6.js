// attré · Вариант 6 «Музей» — поверх site.js (меню, Esc, липкая кнопка).
// Здесь: фото «оседают» при появлении (один раз, IntersectionObserver, после загрузки картинки);
// обложка открывается шторкой, когда фото готово; Ken Burns на паузе вне экрана;
// экспонат, у которого задержались, медленно «поворачивается» — показывает второе фото и возвращается
// (только один, только на экране, второе фото грузится по требованию); строки товара плавно закрываются;
// фокус не уходит из открытого меню.
// Скрытые состояния есть только под html.js и только при prefers-reduced-motion: no-preference (см. v6.css).
(function () {
  var d = document, root = d.documentElement;
  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var still = !!(mq && mq.matches);
  var hasIO = 'IntersectionObserver' in window;
  var each = function (sel, fn, ctx) { Array.prototype.forEach.call((ctx || d).querySelectorAll(sel), fn); };
  var show = function (el) { el.classList.add('is-in'); };
  var safe = function (fn, fallback) {
    try { fn(); } catch (err) { if (fallback) fallback(); }
  };
  var showAll = function () { each('.rv, [data-cover]', show); };

  // Скрипт пришёл позже 6-секундной страховки: всё уже видно — возвращаем html.js без повторных появлений
  if (!root.classList.contains('js')) {
    showAll();
    root.classList.add('js');
  }

  // Картинка готова к показу: загружена и раскодирована, либо ошибка, либо вышло время
  function ready(img, fn, wait) {
    var done = false;
    var go = function () { if (!done) { done = true; fn(); } };
    if (!img) { go(); return; }
    var decode = function () {
      if (img.decode) img.decode().then(go, go); else go();
    };
    if (img.complete && img.naturalWidth) decode();
    else {
      img.addEventListener('load', decode);
      img.addEventListener('error', go);
    }
    setTimeout(go, wait || 2500);
  }

  // ——— «Оседание»: рамка поднимается и проявляется, фото внутри уменьшается до 1 ———
  // Одновременно оседает не больше CAP элементов (рамка и фото внутри — два); если при быстрой
  // прокрутке на экран въехало больше, лишние появляются сразу, уже «осевшими» (класс is-now).
  safe(function () {
    if (still || !hasIO) { each('.rv', show); return; }
    var CAP = 6, busy = 0;
    var settle = function (el) {
      var cost = el.querySelector('.rv__img') ? 2 : 1;
      if (busy + cost > CAP) { el.classList.add('is-now'); show(el); return; }
      busy += cost;
      show(el);
      setTimeout(function () { busy -= cost; }, 1250);
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        io.unobserve(el);
        ready(el.querySelector('img'), function () { requestAnimationFrame(function () { settle(el); }); });
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });
    each('.rv', function (el) { if (!el.classList.contains('is-in')) io.observe(el); });
  }, function () { each('.rv', show); });

  // ——— Обложка: шторка, когда фото готово; Ken Burns — только пока обложка на экране ———
  safe(function () {
    var cover = d.querySelector('[data-cover]');
    if (!cover) return;
    if (still || cover.classList.contains('is-in')) show(cover);
    else ready(cover.querySelector('img'), function () {
      // два кадра: сначала браузер рисует закрытую шторку, потом начинается переход
      requestAnimationFrame(function () { requestAnimationFrame(function () { show(cover); }); });
    }, 2000);
    if (hasIO && !still) {
      new IntersectionObserver(function (entries) {
        cover.classList.toggle('is-off', !entries[0].isIntersecting);
      }).observe(cover);
    }
  }, function () { each('[data-cover]', show); });

  // ——— Экспонат «поворачивается»: вторая фотография проявляется и уходит ———
  safe(function () {
    var frames = Array.prototype.slice.call(d.querySelectorAll('[data-alt-src]'));
    var conn = navigator.connection || {};
    if (!frames.length || still || !hasIO || conn.saveData) return;
    var WAIT = 2400;   // сколько смотреть на первое фото, прежде чем «повернуть»
    var HOLD = 5200;   // второе фото на экране (вместе с переходом 1.2 s)
    var REST = 6000;   // первое фото до следующего поворота
    var active = null, timer = 0;

    var stop = function () { clearTimeout(timer); timer = 0; };
    var step = function (fr, on, delay) {
      timer = setTimeout(function () {
        if (active !== fr) return;
        fr.classList.toggle('is-alt', on);
        step(fr, !on, on ? HOLD : REST);
      }, delay);
    };
    // второе фото подгружаем, только когда экспонат стал «активным»
    var prep = function (fr) {
      if (fr.__alt) return fr.__alt.__ok === true;
      var main = fr.querySelector('img');
      var alt = d.createElement('img');
      alt.className = 'ex__alt';
      alt.alt = '';
      alt.setAttribute('aria-hidden', 'true');
      alt.decoding = 'async';
      alt.width = 600;
      alt.height = 800;
      if (main && main.getAttribute('sizes')) alt.sizes = main.getAttribute('sizes');
      alt.srcset = fr.getAttribute('data-alt-srcset') || '';
      alt.src = fr.getAttribute('data-alt-src');
      alt.addEventListener('load', function () {
        var go = function () {
          alt.__ok = true;
          if (active === fr && !timer) step(fr, true, WAIT);
        };
        if (alt.decode) alt.decode().then(go, go); else go();
      });
      fr.__alt = alt;
      (main ? main.parentNode : fr).appendChild(alt);
      return false;
    };
    var pick = function () {
      var best = null, top = 0.6;
      frames.forEach(function (fr) { if ((fr.__r || 0) >= top) { best = fr; top = fr.__r; } });
      if (best === active) return;
      stop();
      if (active) active.classList.remove('is-alt');   // прежний экспонат мягко «поворачивается» обратно
      active = best;
      if (best && prep(best)) step(best, true, WAIT);
    };
    var quiet = function (fr) {   // ушёл с экрана — без анимации возвращаем первое фото
      if (!fr.classList.contains('is-alt')) return;
      fr.classList.add('is-quiet');
      fr.classList.remove('is-alt');
      void fr.offsetWidth;
      fr.classList.remove('is-quiet');
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        en.target.__r = en.isIntersecting ? en.intersectionRatio : 0;
        if (!en.isIntersecting) quiet(en.target);
      });
      pick();
    }, { threshold: [0, 0.6, 0.75, 0.9, 1] });
    frames.forEach(function (fr) { io.observe(fr); });
    d.addEventListener('visibilitychange', function () {
      if (d.hidden) { stop(); active = null; } else pick();
    });
  });

  // ——— Строки товара: закрываются плавно (открываются — CSS-анимацией) ———
  safe(function () {
    if (still) return;
    each('details.acc', function (dt) {
      var sum = dt.querySelector('summary');
      if (!sum) return;
      sum.addEventListener('click', function (ev) {
        if (!dt.open || dt.classList.contains('is-closing')) return;
        ev.preventDefault();
        dt.classList.add('is-closing');
        setTimeout(function () { dt.open = false; dt.classList.remove('is-closing'); }, 240);
      });
    });
  });

  // ——— Меню: Tab не уходит из открытой панели (открытие, Esc и закрытие — в site.js) ———
  safe(function () {
    var menu = d.querySelector('[data-menu]');
    if (!menu) return;
    d.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Tab' || !menu.classList.contains('is-open')) return;
      var f = Array.prototype.filter.call(menu.querySelectorAll('a[href], button:not([disabled])'),
        function (x) { return x.getClientRects().length > 0; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1], a = d.activeElement;
      if (ev.shiftKey && (a === first || !menu.contains(a))) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && (a === last || !menu.contains(a))) { ev.preventDefault(); first.focus(); }
    });
    // Вернулись «назад» из кэша браузера с открытым меню — закрываем
    window.addEventListener('pageshow', function (ev) {
      if (ev.persisted && menu.classList.contains('is-open')) {
        var x = menu.querySelector('[data-menu-close]');
        if (x) x.click();
      }
    });
  });

  window.__v6 = 1;
})();
