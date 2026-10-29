// Шапка на всех экранах: «attré · админка», вкладки «Товары» / «Магазин и доставка», «Открыть сайт ↗», имя и выход.
// Под шапкой — полоса публикации (status.js).

import { h, icon } from './dom.js';
import { I, LOGO } from './icons.js';

export function mountShell(root, { user, siteUrl, onLogout }) {
  const tabs = [
    { key: 'list', href: '/', label: 'Товары' },
    { key: 'settings', href: '/settings', label: 'Магазин и доставка' },
  ];
  const tabEls = tabs.map((t) => h('a', { class: 'tabs__a', href: t.href, 'data-link': '', 'data-tab': t.key }, t.label));

  // Телефон: кружок с буквой открывает меню «Вы вошли как … · Выйти». Компьютер: имя и «Выйти» прямо в шапке —
  // выпадающее меню там ложилось ровно на «+ Добавить товар», и нажатие мимо выходило из админки.
  const letter = (name) => (name || '?').trim().charAt(0).toUpperCase();
  const initial = h('span', { class: 'top__ava', 'aria-hidden': 'true' }, letter(user));
  const userBtn = h('button', {
    type: 'button', class: 'top__user', 'aria-haspopup': 'true', 'aria-expanded': 'false',
    'aria-label': `${user} — меню`, onclick: () => toggleMenu(),
  }, initial, icon(I.chevron));
  const initial2 = h('span', { class: 'top__ava', 'aria-hidden': 'true' }, letter(user));
  const uname = h('span', { class: 'top__uname' }, user);
  const whoDesk = h('span', { class: 'top__who' }, initial2, uname);
  const outDesk = h('button', { type: 'button', class: 'top__out', onclick: () => onLogout() }, icon(I.logout), 'Выйти');
  const who = h('b', null, user);
  const outBtn = h('button', { type: 'button', class: 'umenu__out', onclick: () => { toggleMenu(false); onLogout(); } }, icon(I.logout), 'Выйти');
  const menu = h('div', { class: 'umenu', hidden: true },
    h('p', { class: 'umenu__who' }, 'Вы вошли как ', who),
    outBtn);

  const site = h('a', { class: 'top__site', href: siteUrl || '#', target: '_blank', rel: 'noopener', hidden: !siteUrl },
    h('span', { class: 'top__site-l' }, 'Открыть сайт'), h('span', { class: 'top__site-s' }, 'Сайт'), icon(I.ext));

  const header = h('header', { class: 'top' },
    h('div', { class: 'top__in' },
      h('a', { class: 'brand', href: '/', 'data-link': '', 'aria-label': 'attré, админка — к списку товаров' },
        h('span', { class: 'brand__logo', html: LOGO }), h('span', { class: 'brand__dot', 'aria-hidden': 'true' }, '·'),
        h('span', { class: 'brand__sub' }, 'админка')),
      h('nav', { class: 'tabs', 'aria-label': 'Разделы админки' }, tabEls),
      h('div', { class: 'top__r' }, site, h('div', { class: 'top__u' }, userBtn, menu), whoDesk, outDesk)));
  const pub = h('div', { class: 'pub', role: 'status', 'aria-live': 'polite', hidden: true });
  const main = h('main', { class: 'main', id: 'main', tabindex: '-1' });
  const chrome = h('div', { class: 'chrome' }, header, pub);
  root.replaceChildren(chrome, main);
  // высота шапки с полосой — для липких блоков ниже (превью справа в редакторе)
  const setH = () => document.documentElement.style.setProperty('--chrome-h', `${chrome.offsetHeight}px`);
  if (window.ResizeObserver) new ResizeObserver(setH).observe(chrome);
  setH();
  root.classList.remove('boot');
  root.removeAttribute('aria-busy');

  function toggleMenu(force) {
    const open = force ?? menu.hidden;
    if (open === !menu.hidden) return;
    menu.hidden = !open;
    userBtn.setAttribute('aria-expanded', String(open));
    if (open) {
      setTimeout(() => {
        document.addEventListener('click', outside, { once: true });
        outBtn.focus({ preventScroll: true });   // фокус — в меню: Esc и Tab работают сразу
      }, 0);
      document.addEventListener('keydown', onKey);
      window.addEventListener('scroll', onScroll, { passive: true });
    } else {
      document.removeEventListener('click', outside);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll);
    }
  }
  function outside(e) {
    if (menu.contains(e.target) || userBtn.contains(e.target)) {
      if (!menu.hidden) document.addEventListener('click', outside, { once: true });
      return;
    }
    toggleMenu(false);
  }
  function onKey(e) {
    if (e.key !== 'Escape' || menu.hidden) return;
    e.preventDefault();
    toggleMenu(false);
    userBtn.focus();
  }
  function onScroll() {
    toggleMenu(false);
  }

  return {
    main,
    pub,
    setTab(key) {
      for (const a of tabEls) {
        if (a.dataset.tab === key) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
      }
    },
    setUser(name) {
      uname.textContent = name;
      who.textContent = name;
      initial.textContent = letter(name);
      initial2.textContent = letter(name);
      userBtn.setAttribute('aria-label', `${name} — меню`);
    },
    setSite(url) {
      if (!url) return;
      site.href = url;
      site.hidden = false;
    },
  };
}
