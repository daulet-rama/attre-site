// Общие мелочи: тексты на трёх языках, числа, деньги, склонения.

export const NBSP = ' ';
export const LANGS = ['ru', 'kz', 'en'];

const str = (x) => (x == null ? '' : String(x));

/** Текст поля: строка или {ru,kz,en} → русский вариант. */
export function txt(v, lang = 'ru') {
  if (v == null) return '';
  if (typeof v === 'string' || typeof v === 'number') return String(v);
  return str(v[lang] ?? (lang === 'ru' ? '' : v.ru));
}

/** Поле на трёх языках: всегда объект {ru,kz,en} со строками. */
export function tri(v) {
  if (v && typeof v === 'object' && !Array.isArray(v)) return { ru: str(v.ru), kz: str(v.kz), en: str(v.en) };
  return { ru: str(typeof v === 'string' ? v : ''), kz: '', en: '' };
}

/** То же, с обрезанными пробелами — так и уходит на сервер. */
export function triTrim(v) {
  const t = tri(v);
  return { ru: t.ru.trim(), kz: t.kz.trim(), en: t.en.trim() };
}

export const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');

export function clone(o) {
  return o == null ? o : JSON.parse(JSON.stringify(o));
}

let seq = 0;
export const uid = () => 'u' + (++seq).toString(36) + Math.random().toString(36).slice(2, 7);

export function norm(s) {
  return str(s).toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

/** Разряды пробелом: 45000 → «45 000». */
export function groupDigits(n) {
  return str(n).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

export function money(n) {
  return groupDigits(n) + NBSP + '₸';
}

const SPACES = /[\s   ]/g;

/** Целое из поля: '' → null, «45 000» → 45000, мусор → NaN. */
export function parseIntField(s) {
  const t = str(s).replace(SPACES, '').replace(/(₸|тг|тенге)$/i, '');
  if (!t) return null;
  if (!/^\d+$/.test(t)) return NaN;
  return parseInt(t, 10);
}

/** Число с дробью из поля: «12,5» → 12.5. */
export function parseNumField(s) {
  const t = str(s).replace(SPACES, '').replace(',', '.').replace(/см$/i, '');
  if (!t) return null;
  if (!/^\d+(\.\d+)?$/.test(t)) return NaN;
  return parseFloat(t);
}

/** Число → текст поля: 12.5 → «12,5». */
export function numToField(v) {
  if (v == null || v === '') return '';
  const n = Number(v);
  return Number.isFinite(n) ? String(n).replace('.', ',') : str(v);
}

/** 1 фото, 2 фото, 5 товаров: plural(n, 'товар', 'товара', 'товаров'). */
export function plural(n, one, few, many) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b === 1) return one;
  if (b >= 2 && b <= 4) return few;
  return many;
}

/** Светлый кружочек (молочный) на белом не виден без обводки — та же формула, что в themes/v4.py. */
export function isLight(hex) {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(str(hex));
  if (!m) return false;
  const [r, g, b] = [m[1], m[2], m[3]].map((x) => parseInt(x, 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.82;
}

export function sameCommit(a, b) {
  if (!a || !b) return false;
  const x = String(a), y = String(b);
  return x.startsWith(y) || y.startsWith(x);
}

export function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    return null;
  }
  return value;
}
