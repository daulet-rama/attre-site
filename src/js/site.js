// attré — прототип. Без фреймворков: переключатель «в наличии» и счётчик фото.
(function () {
  var root = document.documentElement;

  // «Только в наличии»: состояние в адресе (?instock=1), чтобы ссылкой можно было поделиться.
  var toggle = document.querySelector('[data-stock-toggle]');
  var count = document.querySelector('[data-count]');
  function cards() { return document.querySelectorAll('.grid [data-card]'); }
  function visibleCount() {
    var n = 0;
    cards().forEach(function (c) { if (c.offsetParent !== null) n++; });
    return n;
  }
  function apply(on) {
    if (on) root.setAttribute('data-instock', '1'); else root.removeAttribute('data-instock');
    if (toggle) toggle.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (count) count.textContent = count.getAttribute('data-template').replace('{n}', visibleCount());
    document.querySelectorAll('[data-keep-instock]').forEach(function (a) {
      var url = new URL(a.href, location.href);
      if (on) url.searchParams.set('instock', '1'); else url.searchParams.delete('instock');
      a.href = url.pathname + url.search;
    });
  }
  if (toggle) {
    var params = new URLSearchParams(location.search);
    apply(params.get('instock') === '1');
    toggle.addEventListener('click', function () {
      var on = toggle.getAttribute('aria-pressed') !== 'true';
      apply(on);
      var url = new URL(location.href);
      if (on) url.searchParams.set('instock', '1'); else url.searchParams.delete('instock');
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    });
  }

  // Строка категорий прокручивается: активная вкладка должна быть на виду.
  var cur = document.querySelector('.tabs__scroll [aria-current="page"]');
  if (cur) {
    var sc = cur.parentNode;
    sc.scrollLeft += cur.getBoundingClientRect().left - sc.getBoundingClientRect().left - (sc.clientWidth - cur.offsetWidth) / 2;
  }

  // Галерея: «2 / 3» при пролистывании.
  document.querySelectorAll('[data-gallery]').forEach(function (g) {
    var track = g.querySelector('.gallery__track');
    var out = g.querySelector('.gallery__count');
    var total = track.children.length;
    if (!out || total < 2) { if (out) out.hidden = true; return; }
    var last = -1;
    function update() {
      var i = Math.round(track.scrollLeft / track.clientWidth);
      if (i !== last) { last = i; out.textContent = (i + 1) + ' / ' + total; }
    }
    track.addEventListener('scroll', update, { passive: true });
    update();
  });
})();
