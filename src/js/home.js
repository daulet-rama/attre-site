// attré — главная: запуск истории «not mass.», часы Алматы, плавающая панель.
// Шторка и герой — чистый CSS; здесь только то, что зависит от прокрутки и времени.
(function () {
  window.__home = 1;
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
    var heroGone = false, finIn = false, ftrIn = false;
    var sync = function () { dock.classList.toggle('is-on', heroGone && !finIn && !ftrIn); };
    new IntersectionObserver(function (es) { heroGone = !es[0].isIntersecting; sync(); }, { threshold: 0.15 }).observe(hero);
    if (fin) new IntersectionObserver(function (es) { finIn = es[0].isIntersecting; sync(); }).observe(fin);
    var ftr = document.querySelector('.ftr');
    if (ftr) new IntersectionObserver(function (es) { ftrIn = es[0].isIntersecting; sync(); }).observe(ftr);
  } else if (dock) dock.classList.add('is-on');

  // Часы Алматы: Казахстан с 01.03.2024 живёт на едином UTC+5 без летнего времени.
  // Фиксированное смещение надёжнее старых баз часовых поясов на телефонах.
  var clock = document.querySelector('[data-clock]');
  if (clock) {
    var p2 = function (n) { return (n < 10 ? '0' : '') + n; };
    var tick = function () { var d = new Date(Date.now() + 5 * 36e5); clock.textContent = p2(d.getUTCHours()) + ':' + p2(d.getUTCMinutes()); };
    tick(); setInterval(tick, 15000);
  }
})();
