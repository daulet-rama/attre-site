// attré, вариант 2 (по мотивам ushatava.ru): меню слева, шторки справа, листалки фото, полоса бонуса.
// Без фреймворков. Без JS всё видно: меню и шторки — обычные блоки (скрытые состояния — только под html.js).
(function () {
  window.__v2 = 1;
  var d = document, root = d.documentElement;
  root.classList.add('js');   // если скрипт пришёл позже 6-секундной страховки — возвращаем полный режим
  var still = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var each = function (sel, fn, ctx) { Array.prototype.forEach.call((ctx || d).querySelectorAll(sel), fn); };

  // Полоса бонуса: крестик прячет её на 7 дней (метку читает inline-скрипт в <head>, чтобы не мигала).
  each('[data-promo-close]', function (b) {
    b.addEventListener('click', function () {
      root.classList.add('promo-off');
      try { localStorage.setItem('attre-v2-promo', String(Date.now())); } catch (err) { /* приватный режим */ }
      var logo = d.querySelector('.hdr__logo');
      if (logo) logo.focus({ preventScroll: true });
    });
  });

  // Панели: меню (слева) и шторки (справа). Открыта одна, подложка общая.
  var scrim = d.querySelector('[data-scrim]');
  var panel = null, opener = null;
  each('[data-panel]', function (p) {
    p.setAttribute('role', 'dialog');
    p.setAttribute('aria-modal', 'true');
    p.setAttribute('tabindex', '-1');
    var label = p.getAttribute('data-label');
    if (label) p.setAttribute('aria-label', label);
  });
  var mark = function (p, on) {
    each('[data-open="' + p.id + '"]', function (b) { b.setAttribute('aria-expanded', on ? 'true' : 'false'); });
  };
  var close = function (back) {
    if (!panel) return;
    var p = panel;
    panel = null;
    p.classList.remove('is-open');
    root.classList.remove('lock');
    if (scrim) scrim.classList.remove('is-on');
    mark(p, false);
    if (back && opener) opener.focus({ preventScroll: true });   // без прокрутки: кнопка в липкой строке
    opener = null;
  };
  var open = function (p, btn) {
    if (panel) close(false);
    panel = p;
    opener = btn;
    p.classList.add('is-open');
    root.classList.add('lock');
    if (scrim) scrim.classList.add('is-on');
    mark(p, true);
    var x = p.querySelector('[data-close]') || p;
    setTimeout(function () { if (panel === p) x.focus({ preventScroll: true }); }, 30);
  };
  d.addEventListener('click', function (ev) {
    var el = ev.target;
    if (!el || !el.closest) return;
    var btn = el.closest('[data-open]');
    if (btn) {
      var p = d.getElementById(btn.getAttribute('data-open'));
      if (p) { ev.preventDefault(); open(p, btn); }
      return;
    }
    if (!panel) return;
    if (el === scrim || el.closest('[data-close]')) { close(true); return; }
    var a = el.closest('a[href]');
    if (a && panel.contains(a)) close(false);   // переход по ссылке из панели — панель закрываем
  });
  d.addEventListener('keydown', function (ev) {
    if (!panel) return;
    if (ev.key === 'Escape') { ev.preventDefault(); close(true); return; }
    if (ev.key !== 'Tab') return;
    var f = Array.prototype.filter.call(
      panel.querySelectorAll('a[href], button:not([disabled]), summary, [tabindex="0"]'),
      function (x) { return x.getClientRects().length > 0; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1], cur = d.activeElement;
    var inside = panel.contains(cur) && cur !== panel;
    if (ev.shiftKey && (cur === first || !inside)) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && (cur === last || !inside)) { ev.preventDefault(); first.focus(); }
  });
  window.addEventListener('pageshow', function (ev) { if (ev.persisted) close(false); });

  // Ленты фото: номер первого видимого кадра.
  var index = function (track) {
    var first = track.firstElementChild;
    var w = first ? first.getBoundingClientRect().width : 0;
    return w ? Math.round(track.scrollLeft / w) : 0;
  };
  var onScroll = function (track, fn) {
    var raf = 0;
    track.addEventListener('scroll', function () {
      if (!raf) raf = requestAnimationFrame(function () { raf = 0; fn(); });
    }, { passive: true });
  };

  // Карточки каталога: точки под лентой из двух видимых фото.
  each('[data-slider]', function (s) {
    var track = s.querySelector('.pc__track');
    var dots = s.querySelectorAll('.dots i');
    if (!track || dots.length < 2) return;
    var cur = 0;
    onScroll(track, function () {
      var i = Math.min(dots.length - 1, Math.max(0, index(track)));
      if (i === cur) return;
      dots[cur].classList.remove('is-on');
      dots[i].classList.add('is-on');
      cur = i;
    });
  });

  // Галерея товара: счётчик «2 / 5» и стрелки (по кругу, чтобы фокус не терялся на краях).
  each('[data-pg]', function (g) {
    var track = g.querySelector('.pg__track');
    var out = g.querySelector('.pg__count');
    var n = track ? track.children.length : 0;
    if (n < 2) return;
    onScroll(track, function () {
      if (out) out.textContent = (Math.min(n - 1, Math.max(0, index(track))) + 1) + ' / ' + n;
    });
    each('[data-step]', function (b) {
      b.addEventListener('click', function () {
        var w = track.firstElementChild.getBoundingClientRect().width;
        if (!w) return;
        var max = Math.round((track.scrollWidth - track.clientWidth) / w);
        if (max < 1) return;
        var i = index(track) + Number(b.getAttribute('data-step'));
        if (i < 0) i = max; else if (i > max) i = 0;
        track.scrollTo({ left: i * w, behavior: still && still.matches ? 'auto' : 'smooth' });
      });
    }, g);
  });
})();
