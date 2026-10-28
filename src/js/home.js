// attré — главная: запуск истории «not mass.», часы Алматы, плавающая панель.
// Шторка и герой — чистый CSS; здесь только то, что зависит от прокрутки и времени.
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasIO = 'IntersectionObserver' in window;

  // История: силуэты гаснут волной, одна вещь становится фото. Один раз.
  var story = document.querySelector('[data-story]');
  if (story) {
    if (reduce || !hasIO) story.classList.add('is-play');
    else {
      var io = new IntersectionObserver(function (es) {
        if (es[0].isIntersecting) { story.classList.add('is-play'); io.disconnect(); }
      }, { threshold: 0.45 });
      io.observe(story.querySelector('.story__stage'));
    }
  }

  // Плавающая панель «каталог + WhatsApp»: видна после героя, прячется у финала.
  var dock = document.querySelector('.dock');
  var hero = document.querySelector('.hero');
  var fin = document.querySelector('.fin');
  if (dock && hero && hasIO) {
    var heroGone = false, finIn = false;
    var sync = function () { dock.classList.toggle('is-on', heroGone && !finIn); };
    new IntersectionObserver(function (es) { heroGone = !es[0].isIntersecting; sync(); }, { threshold: 0.15 }).observe(hero);
    if (fin) new IntersectionObserver(function (es) { finIn = es[0].isIntersecting; sync(); }).observe(fin);
  } else if (dock) dock.classList.add('is-on');

  // Часы Алматы.
  var clock = document.querySelector('[data-clock]');
  if (clock) {
    var fmt;
    try { fmt = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Almaty', hour: '2-digit', minute: '2-digit' }); }
    catch (e) { fmt = null; }
    var tick = function () { if (fmt) clock.textContent = fmt.format(new Date()); };
    if (fmt) { tick(); setInterval(tick, 15000); } else clock.hidden = true;
  }
})();
