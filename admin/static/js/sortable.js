// Перетаскивание мышью или пальцем: держим за ручку (или за сам элемент), остальные раздвигаются.
// Работает и для списка (строки), и для сетки (фото). На телефоне в сетке фото — стрелки (палец листает страницу).

/**
 * sortable(container, {item: '.ph', handle: '.ph__pic', mouseOnly: true, onEnd(fromIndex, toIndex)})
 * Возвращает функцию отключения.
 */
export function sortable(container, { item, handle = null, mouseOnly = false, onEnd, onFinish }) {
  let drag = null;

  function onDown(e) {
    if (e.button !== 0 || drag) return;
    if (mouseOnly && e.pointerType !== 'mouse') return;
    const grip = handle ? e.target.closest(handle) : e.target.closest(item);
    if (!grip || !container.contains(grip)) return;
    if (!handle && e.target.closest('button, a, input, textarea, select, label')) return;
    const el = grip.closest(item);
    if (!el || el.classList.contains('is-fixed')) return;
    drag = { el, x: e.clientX, y: e.clientY, id: e.pointerId, on: false, from: index(el), ph: null, rect: null, raf: 0, py: e.clientY, px: e.clientX };
    window.addEventListener('pointermove', onMove, { passive: false });
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    if (handle && e.pointerType !== 'mouse') e.preventDefault();
  }

  function items() {
    return Array.from(container.querySelectorAll(`:scope > ${item}`));
  }

  function index(el) {
    return items().filter((x) => !x.classList.contains('sort-ph')).indexOf(el);
  }

  function begin() {
    const { el } = drag;
    const r = el.getBoundingClientRect();
    drag.rect = r;
    const ph = document.createElement(el.tagName);
    ph.className = `${el.className} sort-ph`;
    ph.style.height = `${r.height}px`;
    ph.setAttribute('aria-hidden', 'true');
    el.before(ph);
    drag.ph = ph;
    drag.css = el.getAttribute('style');
    Object.assign(el.style, {
      position: 'fixed', left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px`,
      zIndex: '200', pointerEvents: 'none', margin: '0',
    });
    el.classList.add('is-drag');
    document.documentElement.classList.add('is-dragging');
    drag.on = true;
    tick();
  }

  function onMove(e) {
    if (!drag || e.pointerId !== drag.id) return;
    drag.px = e.clientX;
    drag.py = e.clientY;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.on) {
      if (Math.hypot(dx, dy) < 6) return;
      begin();
    }
    e.preventDefault();
    drag.el.style.transform = `translate(${dx}px, ${dy}px)`;
    place(e.clientX, e.clientY);
  }

  function place(x, y) {
    const under = document.elementFromPoint(x, y);
    const over = under && under.closest(item);
    if (!over || over === drag.el || over === drag.ph || !container.contains(over) || over.classList.contains('is-fixed')) return;
    const r = over.getBoundingClientRect();
    const rowLike = r.width > container.getBoundingClientRect().width * 0.6;   // строка списка — сравниваем по высоте
    const after = rowLike ? y > r.top + r.height / 2 : x > r.left + r.width / 2;
    if (after) over.after(drag.ph);
    else over.before(drag.ph);
  }

  // Прокрутка страницы, когда тянем к краю экрана
  function tick() {
    if (!drag || !drag.on) return;
    const edge = 70, H = window.innerHeight;
    let v = 0;
    if (drag.py < edge) v = -Math.ceil((edge - drag.py) / 6);
    else if (drag.py > H - edge) v = Math.ceil((drag.py - (H - edge)) / 6);
    if (v) {
      window.scrollBy(0, v);
      place(drag.px, drag.py);
    }
    drag.raf = requestAnimationFrame(tick);
  }

  function onUp(e) {
    if (!drag || (e && e.pointerId !== drag.id)) return;
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    window.removeEventListener('pointercancel', onUp);
    const d = drag;
    drag = null;
    if (!d.on) return;
    cancelAnimationFrame(d.raf);
    const alive = d.ph.isConnected;   // список могли перерисовать, пока тянули (например, догрузилось фото)
    if (alive) d.ph.replaceWith(d.el);
    if (d.css == null) d.el.removeAttribute('style');
    else d.el.setAttribute('style', d.css);
    d.el.classList.remove('is-drag');
    document.documentElement.classList.remove('is-dragging');
    // после перетаскивания не открывать то, на чём отпустили
    const stop = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
    window.addEventListener('click', stop, { capture: true, once: true });
    setTimeout(() => window.removeEventListener('click', stop, { capture: true }), 50);
    const to = alive ? index(d.el) : -1;
    if (to >= 0 && d.from >= 0 && to !== d.from && onEnd) onEnd(d.from, to);
    else if (onFinish) onFinish();
  }

  container.addEventListener('pointerdown', onDown);
  return () => container.removeEventListener('pointerdown', onDown);
}
