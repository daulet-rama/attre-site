// attré, вариант 1: меню-панель под шапкой, вкладки на странице товара, стрелка галереи.
// Мягкое проявление фото (img.fade) делает общий site.js. Без этого скрипта всё видно:
// меню стоит списком под шапкой, вкладки идут разделами подряд, галерея листается пальцем.
(function () {
  var d = document, root = d.documentElement;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Меню: бургер ↔ крестик, панель под шапкой, страница под ней затемнена.
  // Закрывается тем же бургером, тапом по затемнению, Esc, переходом по ссылке и уходом фокуса из шапки.
  var btn = d.querySelector('[data-v1-menu-btn]');
  var menu = d.querySelector('[data-v1-menu]');
  var top = d.querySelector('[data-v1-top]');
  var shade = d.querySelector('[data-v1-shade]');
  if (btn && menu && top) {
    var isOpen = function () { return root.classList.contains('v1-menu-open'); };
    var set = function (open, back) {
      root.classList.toggle('v1-menu-open', open);
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
    // Возврат «назад» из кэша браузера — меню закрыто.
    window.addEventListener('pageshow', function () { if (isOpen()) set(false); });
  }

  // Галерея товара: тап по стрелке листает дальше, с последнего фото — на первое.
  d.querySelectorAll('[data-v1-gal]').forEach(function (g) {
    var track = g.querySelector('.gal__track');
    var next = g.querySelector('.gal__next');
    if (!track || !next || track.children.length < 2) return;
    next.addEventListener('click', function () {
      var w = track.clientWidth, n = track.children.length;
      var i = Math.round(track.scrollLeft / w);
      var to = i >= n - 1 ? 0 : (i + 1) * w;
      if (track.scrollTo) track.scrollTo({ left: to, behavior: reduce ? 'auto' : 'smooth' });
      else track.scrollLeft = to;
    });
    g.classList.add('is-ready');
  });

  // Вкладки «характеристики / доставка / возврат» (шаблон WAI-ARIA Tabs: стрелки, Home, End).
  d.querySelectorAll('[data-v1-tabs]').forEach(function (box) {
    var tabs = [].slice.call(box.querySelectorAll('[role="tab"]'));
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
        var n = tabs.length, j = -1;
        if (e.key === 'ArrowRight') j = (i + 1) % n;
        else if (e.key === 'ArrowLeft') j = (i + n - 1) % n;
        else if (e.key === 'Home') j = 0;
        else if (e.key === 'End') j = n - 1;
        if (j < 0) return;
        e.preventDefault();
        select(j, true);
      });
    });
    box.classList.add('is-ready');
    select(0);
  });
})();
