// attré · Вариант 3 — поверх site.js (меню, проявление фото): нижние листы, вид сетки 2 ↔ 1,
// фото плиток меню по требованию, фокус не уходит из открытого меню или листа.
(function () {
  var d = document, root = d.documentElement;
  var KEY = 'attre-v3-cols';
  var menu = d.querySelector('[data-menu]');

  // ——— Фокус внутри открытого окна ———
  function focusables(box) {
    return Array.prototype.filter.call(
      box.querySelectorAll('a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'),
      function (el) { return el.getClientRects().length > 0; });
  }
  function trap(e, box) {
    var f = focusables(box);
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1], a = d.activeElement;
    if (e.shiftKey && (a === first || a === box || !box.contains(a))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (a === last || !box.contains(a))) { e.preventDefault(); first.focus(); }
  }

  // ——— Фото плиток меню: грузим, только когда меню вот-вот откроют (или в простое после загрузки) ———
  function hydrate() {
    if (!menu) return;
    menu.querySelectorAll('img[data-src]').forEach(function (i) {
      var done = function () { i.classList.add('is-in'); };
      i.addEventListener('load', done, { once: true });
      i.addEventListener('error', done, { once: true });
      i.srcset = i.getAttribute('data-srcset');
      i.src = i.getAttribute('data-src');
      i.removeAttribute('data-src');
      i.removeAttribute('data-srcset');
    });
  }
  var burger = d.querySelector('[data-menu-open]');
  if (burger) ['pointerdown', 'focus', 'click'].forEach(function (ev) { burger.addEventListener(ev, hydrate); });

  // Текущий раздел в ряду вкладок меню — на виду (ряд прокручивается вбок)
  var tabs = menu && menu.querySelector('.menu__tabs');
  var curTab = tabs && tabs.querySelector('[aria-current]');
  if (curTab) {
    var r = curTab.getBoundingClientRect(), rb = tabs.getBoundingClientRect();
    if (r.right > rb.right - 20) tabs.scrollLeft += r.left - rb.left - 20;
  }
  window.addEventListener('load', function () {
    var c = navigator.connection;
    if (c && (c.saveData || /2g/.test(c.effectiveType || ''))) return;
    setTimeout(hydrate, 3000);
  });

  // ——— Нижние листы ———
  var sheets = d.querySelectorAll('[data-sheet]');
  var cur = null, trigger = null, scrim = null;
  if (sheets.length) {
    scrim = d.createElement('div');
    scrim.className = 'scrim';
    scrim.setAttribute('aria-hidden', 'true');
    d.body.appendChild(scrim);
    scrim.addEventListener('click', function () { close(); });
    // в конец body: так лист не зависит от липких и трансформированных предков
    sheets.forEach(function (s) {
      d.body.appendChild(s);
      s.setAttribute('role', 'dialog');
      s.setAttribute('aria-modal', 'true');
      s.tabIndex = -1;
    });
  }
  function open(id, btn) {
    var s = d.getElementById(id);
    if (!s || !scrim) return;
    if (cur) close(true);
    cur = s; trigger = btn || null;
    s.querySelectorAll('.sheet__body').forEach(function (b) { b.scrollTop = 0; });
    s.classList.add('is-open');
    scrim.classList.add('is-on');
    root.classList.add('sheet-lock');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    setTimeout(function () { if (cur === s) s.focus({ preventScroll: true }); }, 30);
  }
  function close(quiet) {
    if (!cur) return;
    cur.classList.remove('is-open');
    scrim.classList.remove('is-on');
    root.classList.remove('sheet-lock');
    if (trigger) {
      trigger.setAttribute('aria-expanded', 'false');
      if (!quiet) trigger.focus({ preventScroll: true });
    }
    cur = null; trigger = null;
  }
  d.addEventListener('click', function (e) {
    var o = e.target.closest('[data-sheet-open]');
    if (o) { e.preventDefault(); open(o.getAttribute('data-sheet-open'), o); return; }
    if (cur && e.target.closest('[data-sheet-close]')) close();
  });

  d.addEventListener('keydown', function (e) {
    if (cur) {
      if (e.key === 'Escape') close();
      else if (e.key === 'Tab') trap(e, cur);
      return;
    }
    if (e.key === 'Tab' && menu && menu.classList.contains('is-open')) trap(e, menu);
  });

  // ——— Вид сетки: 2 ↔ 1 (на планшете 3 ↔ 2, на компьютере 4 ↔ 2), запоминаем выбор ———
  var vbtn = d.querySelector('[data-view]');
  var grid = d.querySelector('.grid--cat');
  if (vbtn && grid) {
    var out = vbtn.querySelector('[data-view-n]');
    var bar = vbtn.parentNode;
    var count = function () {
      var n = getComputedStyle(grid).gridTemplateColumns.split(' ').filter(Boolean).length;
      if (n) out.textContent = n;
    };
    var sizes = function () {
      var big = root.classList.contains('v-big');
      var s = big ? '(min-width: 960px) 50vw, (min-width: 600px) 50vw, 100vw'
                  : '(min-width: 960px) 25vw, (min-width: 600px) 33vw, 50vw';
      grid.querySelectorAll('img').forEach(function (i) {
        i.sizes = (i.loading === 'lazy' ? 'auto, ' : '') + s;
      });
    };
    vbtn.addEventListener('click', function () {
      // карточка, которую сейчас видно первой, остаётся на месте после перестройки сетки
      var top = bar.getBoundingClientRect().bottom, anchor = null, cards = grid.children;
      for (var k = 0; k < cards.length; k++) {
        if (cards[k].getBoundingClientRect().bottom > top + 1) { anchor = cards[k]; break; }
      }
      var big = root.classList.toggle('v-big');
      try { localStorage.setItem(KEY, big ? '1' : '2'); } catch (err) { /* приватный режим */ }
      sizes();
      count();
      if (anchor && anchor !== cards[0]) {
        window.scrollTo(0, Math.max(0, anchor.getBoundingClientRect().top + window.pageYOffset - top - 8));
      }
    });
    if (root.classList.contains('v-big')) sizes();
    count();
    window.addEventListener('resize', count);
  }
})();
