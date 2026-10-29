// Шапка на всех экранах: «attré · админка», вкладки «Товары» / «Магазин и доставка», «Открыть сайт ↗»,
// «Как пользоваться ↗» (инструкция GUIDE.md на GitHub), имя («Сменить пароль») и выход. Под шапкой — полоса
// публикации (status.js).

import { h, icon } from './dom.js';
import { I, LOGO } from './icons.js';
import { changePassword } from './password.js';

// Инструкция для основательниц — admin/GUIDE.md в репозитории сайта (GitHub показывает её с картинками)
const GUIDE_URL = 'https://github.com/daulet-rama/attre-site/blob/main/admin/GUIDE.md';

export function mountShell(root, { user, siteUrl, onLogout }) {
  const tabs = [
    { key: 'list', href: '/', label: 'Товары' },
    { key: 'settings', href: '/settings', label: 'Магазин и доставка' },
  ];
  const tabEls = tabs.map((t) => h('a', { class: 'tabs__a', href: t.href, 'data-link': '', 'data-tab': t.key }, t.label));

  // Телефон: кружок с буквой открывает меню «Вы вошли как … · Как пользоваться · Сменить пароль · Выйти»
  // (в строке шапки тесно). Компьютер: «Как пользоваться», имя и «Выйти» прямо в шапке; под именем — меню с одним
  // пунктом «Сменить пароль». «Выйти» в выпадающее меню не кладём: оно ложилось ровно на «+ Добавить товар»,
  // и нажатие мимо выходило из админки (а мимо «Сменить пароль» — лишь откроет окно, его можно закрыть).
  let current = user;
  const letter = (name) => (name || '?').trim().charAt(0).toUpperCase();
  const initial = h('span', { class: 'top__ava', 'aria-hidden': 'true' }, letter(user));
  const userBtn = h('button', {
    type: 'button', class: 'top__user', 'aria-haspopup': 'true', 'aria-expanded': 'false',
    'aria-label': `${user} — меню`, onclick: () => toggleMenu(),
  }, initial, icon(I.chevron));
  const initial2 = h('span', { class: 'top__ava', 'aria-hidden': 'true' }, letter(user));
  const uname = h('span', { class: 'top__uname' }, user);
  const whoDesk = h('button', {
    type: 'button', class: 'top__who', 'aria-haspopup': 'true', 'aria-expanded': 'false',
    'aria-label': `${user} — меню`, onclick: () => toggleDesk(),
  }, initial2, uname, icon(I.chevron));
  const outDesk = h('button', { type: 'button', class: 'top__out', onclick: () => onLogout() }, icon(I.logout), 'Выйти');
  const who = h('b', null, user);
  const outBtn = h('button', { type: 'button', class: 'umenu__out', onclick: () => { toggleMenu(false); onLogout(); } }, icon(I.logout), 'Выйти');
  const helpMenu = h('a', { class: 'umenu__help', href: GUIDE_URL, target: '_blank', rel: 'noopener', onclick: () => toggleMenu(false) },
    icon(I.help), h('span', null, 'Как пользоваться'), icon(I.ext));
  // Окно смены пароля: меню закрываем, фокус — на кнопку меню (на неё он вернётся, когда окно закроется)
  const openPassword = (toggle, btn) => {
    toggle(false);
    btn.focus({ preventScroll: true });
    changePassword({ user: current });
  };
  const pwMenu = h('button', { type: 'button', class: 'umenu__item', onclick: () => openPassword(toggleMenu, userBtn) },
    icon(I.key), 'Сменить пароль');
  const pwDesk = h('button', { type: 'button', class: 'umenu__item', onclick: () => openPassword(toggleDesk, whoDesk) },
    icon(I.key), 'Сменить пароль');
  const menu = h('div', { class: 'umenu', hidden: true },
    h('p', { class: 'umenu__who' }, 'Вы вошли как ', who),
    helpMenu,
    pwMenu,
    outBtn);
  const deskMenu = h('div', { class: 'umenu umenu--desk', hidden: true }, pwDesk);

  const site = h('a', { class: 'top__site', href: siteUrl || '#', target: '_blank', rel: 'noopener', hidden: !siteUrl },
    h('span', { class: 'top__site-l' }, 'Открыть сайт'), h('span', { class: 'top__site-s' }, 'Сайт'), icon(I.ext));
  const help = h('a', { class: 'top__help', href: GUIDE_URL, target: '_blank', rel: 'noopener' }, 'Как пользоваться', icon(I.ext));

  const header = h('header', { class: 'top' },
    h('div', { class: 'top__in' },
      h('a', { class: 'brand', href: '/', 'data-link': '', 'aria-label': 'attré, админка — к списку товаров' },
        h('span', { class: 'brand__logo', html: LOGO }), h('span', { class: 'brand__dot', 'aria-hidden': 'true' }, '·'),
        h('span', { class: 'brand__sub' }, 'админка')),
      h('nav', { class: 'tabs', 'aria-label': 'Разделы админки' }, tabEls),
      h('div', { class: 'top__r' }, site, help, h('div', { class: 'top__u' }, userBtn, menu),
        h('div', { class: 'top__wd' }, whoDesk, deskMenu), outDesk)));
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

  // фокус — в меню (на первый пункт, не на «Выйти»): Esc и Tab работают сразу
  const toggleMenu = dropdown(userBtn, menu, helpMenu);
  const toggleDesk = dropdown(whoDesk, deskMenu, pwDesk);

  /** Выпадающее меню под кнопкой: закрывается нажатием мимо, Esc (фокус — обратно на кнопку) и прокруткой. */
  function dropdown(btn, box, first) {
    function toggle(force) {
      const open = force ?? box.hidden;
      if (open === !box.hidden) return;
      box.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
      if (open) {
        setTimeout(() => {
          document.addEventListener('click', outside, { once: true });
          first.focus({ preventScroll: true });
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
      if (box.contains(e.target) || btn.contains(e.target)) {
        if (!box.hidden) document.addEventListener('click', outside, { once: true });
        return;
      }
      toggle(false);
    }
    function onKey(e) {
      if (e.key !== 'Escape' || box.hidden) return;
      e.preventDefault();
      toggle(false);
      btn.focus();
    }
    function onScroll() {
      toggle(false);
    }
    return toggle;
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
      current = name;
      uname.textContent = name;
      who.textContent = name;
      initial.textContent = letter(name);
      initial2.textContent = letter(name);
      userBtn.setAttribute('aria-label', `${name} — меню`);
      whoDesk.setAttribute('aria-label', `${name} — меню`);
    },
    setSite(url) {
      if (!url) return;
      site.href = url;
      site.hidden = false;
    },
  };
}
