// Кружочек цвета: заливка hex палитры или узор принта (леопард, коровий, зебра — те же градиенты, что на сайте).
// Светлые (молочный) — с тонкой серой обводкой, иначе на белом не видно.

import { h, esc } from './dom.js';
import { isLight } from './util.js';

export const PATTERNS = new Set(['leopard', 'cow', 'zebra', 'dalmatian']);

function parts(c) {
  if (c && PATTERNS.has(c.pattern)) return { cls: ` sw--${c.pattern}`, style: '' };
  if (c && c.hex) return { cls: isLight(c.hex) ? ' sw--light' : '', style: `background:${c.hex}` };
  return { cls: ' sw--none', style: '' };
}

export function swatch(c, cls = '') {
  const p = parts(c);
  const el = h('span', { class: `sw${p.cls}${cls ? ' ' + cls : ''}`, 'aria-hidden': 'true' });
  if (p.style) el.setAttribute('style', p.style);
  return el;
}

export function swatchHtml(c, cls = '') {
  const p = parts(c);
  return `<span class="sw${p.cls}${cls ? ' ' + cls : ''}"${p.style ? ` style="${esc(p.style)}"` : ''} aria-hidden="true"></span>`;
}
