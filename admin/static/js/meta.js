// Справочники админки (/api/meta): палитра из 15 цветов, категории, материалы, типы, адрес сайта.

import { api } from './api.js';
import { tri, cap } from './util.js';

let meta = null;

export const getMeta = () => meta;

export async function loadMeta(force = false) {
  if (meta && !force) return meta;
  meta = normalize(await api('/api/meta'));
  return meta;
}

export function usersFrom(list) {
  return (Array.isArray(list) ? list : [])
    .map((u) => (typeof u === 'string' ? u : u && (u.name || u.user)))
    .filter((u) => typeof u === 'string' && u.trim());
}

function byOrder(a, b) {
  return (a.order ?? 999) - (b.order ?? 999) || String(a.key).localeCompare(String(b.key));
}

function normalize(m) {
  const palette = (m.palette || []).filter((c) => c && c.key).map((c) => ({
    key: c.key, hex: c.hex || null, pattern: c.pattern || null, name: tri(c.name),
  }));
  const parents = new Set((m.categories || []).map((c) => c && c.parent).filter(Boolean));
  const cats = (m.categories || []).filter((c) => c && c.key).map((c) => ({
    key: c.key, name: tri(c.name), parent: c.parent || null, order: c.order ?? 999,
    count: c.count ?? 0, leaf: typeof c.leaf === 'boolean' ? c.leaf : !parents.has(c.key),
  })).sort(byOrder);
  for (const c of cats) if (!c.name.ru) c.name.ru = c.key;
  const materials = (m.materials || []).filter((x) => x && x.key).map((x) => ({
    key: x.key, name: tri(x.name), order: x.order ?? 999,
  })).sort(byOrder);
  const seen = new Set();
  const types = [];
  for (const t of m.types || []) {
    const v = tri(t);
    const k = v.ru.trim().toLowerCase();
    if (k && !seen.has(k)) {
      seen.add(k);
      types.push(v);
    }
  }
  const lim = m.limits && typeof m.limits === 'object' ? m.limits : {};
  const limits = Object.fromEntries(Object.entries(LIMITS).map(([k, v]) => [k, Number.isFinite(lim[k]) ? lim[k] : v]));
  let site = typeof m.site_url === 'string' ? m.site_url : '';
  if (site && !site.endsWith('/')) site += '/';
  return {
    palette,
    pal: Object.fromEntries(palette.map((c) => [c.key, c])),
    cats,
    cat: Object.fromEntries(cats.map((c) => [c.key, c])),
    leafCats: cats.filter((c) => c.leaf),
    materials,
    mat: Object.fromEntries(materials.map((x) => [x.key, x])),
    types,
    site,
    users: usersFrom(m.users),
    limits,
  };
}

// Пределы полей (сервер присылает свои в /api/meta → limits; эти — на случай, если не прислал)
const LIMITS = {
  name_max: 60, type_max: 60, shade_max: 60, text_max: 2000, photos_max: 8, colors_max: 20,
  price_max: 10000000, stock_max: 100000, size_min: 1, size_max: 200,
};

// Старые ключи цветов (до палитры из 15 цветов) → ближайший цвет палитры: так старые товары показываются кружочками
// (те же замены, что делает сервер; «animal» не угадываем — это мог быть леопард, корова или зебра)
const LEGACY_COLORS = { white: 'milky', mustard: 'yellow', turquoise: 'light-blue' };

/** Ключ палитры для цвета товара (в том числе старого) или null. */
export function paletteKey(c) {
  if (!meta || typeof c !== 'string') return null;
  if (meta.pal[c]) return c;
  const k = LEGACY_COLORS[c];
  return k && meta.pal[k] ? k : null;
}

export const catLabel = (c) => cap((c && c.name && c.name.ru) || (c && c.key) || '');

/** Адрес товара на сайте (русская версия). */
export function productUrl(slug) {
  return meta && meta.site && slug ? `${meta.site}ru/p/${slug}/` : '';
}
