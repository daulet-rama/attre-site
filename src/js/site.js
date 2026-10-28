// attré — минимальный скрипт без фреймворков: меню, мягкое проявление фото,
// счётчик галереи, липкая кнопка на странице товара.
(function () {
  window.__site = 1;
  var d = document, root = d.documentElement;

  // Фото проявляются, когда загрузились (CSS: html.js img.fade). Без JS видны сразу.
  var imgs = d.querySelectorAll('img.fade');
  var show = function (i) { i.classList.add('is-in'); };
  imgs.forEach(function (i) {
    if (i.complete && i.naturalWidth) show(i);
    else { i.addEventListener('load', function () { show(i); }); i.addEventListener('error', function () { show(i); }); }
  });

  // Меню: панель на весь экран, закрывается крестиком, Esc и переходом по ссылке.
  var menu = d.querySelector('[data-menu]');
  var openBtn = d.querySelector('[data-menu-open]');
  if (menu && openBtn) {
    var closeBtn = menu.querySelector('[data-menu-close]');
    var open = function () {
      menu.classList.add('is-open'); root.classList.add('menu-lock');
      openBtn.setAttribute('aria-expanded', 'true');
      setTimeout(function () { closeBtn.focus(); }, 50);
    };
    var close = function (back) {
      menu.classList.remove('is-open'); root.classList.remove('menu-lock');
      openBtn.setAttribute('aria-expanded', 'false');
      if (back) openBtn.focus();
    };
    openBtn.addEventListener('click', open);
    closeBtn.addEventListener('click', function () { close(true); });
    menu.addEventListener('click', function (e) { if (e.target.closest('a')) close(false); });
    d.addEventListener('keydown', function (e) { if (e.key === 'Escape' && menu.classList.contains('is-open')) close(true); });
  }

  // Категории: активная вкладка на виду.
  var cur = d.querySelector('.tabs__scroll [aria-current="page"]');
  if (cur) {
    var sc = cur.parentNode;
    sc.scrollLeft += cur.getBoundingClientRect().left - sc.getBoundingClientRect().left - (sc.clientWidth - cur.offsetWidth) / 2;
  }

  // Галерея: «2 / 4» при пролистывании.
  d.querySelectorAll('[data-gallery]').forEach(function (g) {
    var track = g.querySelector('.gallery__track');
    var out = g.querySelector('.gallery__count');
    var total = track.children.length;
    if (!out || total < 2) { if (out) out.hidden = true; return; }
    var last = -1;
    var update = function () {
      var i = Math.round(track.scrollLeft / track.clientWidth);
      if (i !== last) { last = i; out.textContent = (i + 1) + ' / ' + total; }
    };
    track.addEventListener('scroll', update, { passive: true });
    update();
  });

  // Липкая кнопка WhatsApp: появляется, когда основная кнопка ушла за верх экрана.
  var cta = d.querySelector('[data-cta]');
  var bar = d.querySelector('.buybar');
  if (cta && bar && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (es) {
      var e = es[0];
      bar.classList.toggle('is-on', !e.isIntersecting && e.boundingClientRect.top < 0);
    }).observe(cta);
  }
})();
