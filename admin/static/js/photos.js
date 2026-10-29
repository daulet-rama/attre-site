// Фото одного цвета: миниатюры 3:4 с номером, «★ Главное» у первого, «Сделать главным», стрелки ←/→, удаление,
// загрузка нескольких сразу с процентами, перетаскивание файлов (компьютер) и перестановка мышью.
// Нажатие на фото открывает лист с теми же действиями крупно и «Перенести в другой цвет».
// Большие фото с телефона уменьшаются до 2000 px ещё на телефоне (shrink) — по мобильной сети это в разы быстрее.

import { uploadFile } from './api.js';
import { h, icon, flash } from './dom.js';
import { I } from './icons.js';
import { sortable } from './sortable.js';
import { swatch } from './swatch.js';
import { dialog, sheet, toast } from './ui.js';
import { plural, uid } from './util.js';

export const MAX = 8;
const MAX_BYTES = 30 * 1024 * 1024;
const OK_EXT = /\.(jpe?g|png|webp|heic|heif)$/i;
const OK_TYPE = /^image\/(jpeg|jpg|pjpeg|png|webp|heic|heif|heic-sequence|heif-sequence)$/i;
const PREVIEW_TYPE = /^image\/(jpeg|jpg|pjpeg|png|webp)$/i;
const PARALLEL = 2;
const SHRINK_SIDE = 2000;                     // как и на сервере: длинная сторона мастер-копии
const SHRINK_MIN = 1.5 * 1024 * 1024;         // меньше — отправляем как есть
const SHRINK_MAX = 15 * 1024 * 1024;          // больше — скорее всего огромное разрешение: телефону не по силам
const SHRINK_TYPE = /^image\/(jpeg|jpg|pjpeg|png|webp|heic|heif)$/i;

/**
 * Большое фото (3–6 МБ с телефона) → JPEG с длинной стороной 2000 px прямо на телефоне. 8 таких фото по мобильной
 * сети — 30–60 секунд, уменьшенные — несколько секунд; сервер всё равно сделал бы из них 2000 px (и повернёт,
 * и переведёт цвета так же). Прозрачный фон — белый, как на сервере. Не вышло (браузер не умеет HEIC, мало
 * памяти) — отправляем оригинал: сервер справится сам.
 */
async function shrink(file) {
  if (!file || file.size < SHRINK_MIN || file.size > SHRINK_MAX || !SHRINK_TYPE.test(file.type || '')) return file;
  let url = null;
  let canvas = null;
  try {
    url = URL.createObjectURL(file);
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    await img.decode();
    const w = img.naturalWidth, hh = img.naturalHeight;      // уже с поворотом по EXIF, как браузер его показывает
    const k = Math.min(1, SHRINK_SIDE / Math.max(w, hh));
    if (!w || !hh || k >= 1) return file;
    canvas = document.createElement('canvas');
    canvas.width = Math.round(w * k);
    canvas.height = Math.round(hh * k);
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.92));
    if (!blob || blob.size >= file.size) return file;
    const name = `${String(file.name || 'photo').replace(/\.[^.]+$/, '') || 'photo'}.jpg`;
    return new File([blob], name, { type: 'image/jpeg', lastModified: file.lastModified || Date.now() });
  } catch {
    return file;
  } finally {
    if (url) URL.revokeObjectURL(url);
    if (canvas) canvas.width = canvas.height = 0;            // отдать память сразу (важно на iPhone)
  }
}

/** Полный текст для человека: «Файл «IMG_2041.MOV» не подошёл. Это видео, а нужно фото.» */
export function badText(img) {
  const name = img.name ? `«${img.name}»` : '';
  const why = String(img.error || '').replace(/^Этот файл не подходит\.\s*/, '');   // «не подошёл» уже сказано
  return img.retry
    ? `Фото ${name} не загрузилось. ${why}`.replace(/\s+/g, ' ').trim()
    : `Файл ${name} не подошёл. ${why}`.replace(/\s+/g, ' ').trim();
}

export function imgFromPath(path) {
  const file = String(path).split('/').pop();
  return { uid: uid(), ref: String(path), thumb: `/api/media/${encodeURIComponent(file)}?w=480`, state: 'ok' };
}

/** Понятная причина, почему файл не подходит — ещё до отправки. */
export function precheck(f) {
  if (!f.size) return 'Файл пустой — выберите другое фото.';
  if (f.size > MAX_BYTES) return `Файл ${Math.round(f.size / 1048576)} МБ — это больше 30 МБ. Выберите фото поменьше.`;
  const typeOk = f.type ? OK_TYPE.test(f.type) : false;
  if (!typeOk && !OK_EXT.test(f.name || '')) {
    if (f.type && f.type.startsWith('video/')) return 'Это видео, а нужно фото.';
    if (f.type && f.type.startsWith('image/')) return 'Такой формат фото не подходит. Подходят JPEG, PNG, WEBP и фото с iPhone (HEIC).';
    return 'Это не фото. Подходят JPEG, PNG, WEBP и фото с iPhone (HEIC).';
  }
  return null;
}

const okImg = (i) => i.state === 'ok' && i.ref;

/**
 * ctx: {variants(): [], changed(v), label(v): 'молочный' | 'Цвет 2', palette(key), max,
 *       bad(v, [img]) — файлы не подошли или не загрузились (показать полный текст под «Фото»),
 *       refresh(v) — у цвета поменялись фото, а его блок сейчас свёрнут (обновить строку)}
 */
export class Photos {
  constructor(ctx) {
    this.ctx = ctx;
    this.max = ctx.max || MAX;
    this.queue = [];
    this.active = 0;
    this.views = new Map();   // uid цвета → {list, drop, full, wrap, input, counter}
    this.jobs = new Set();    // идущие загрузки — отменить, если ушли со страницы
    this.locals = new Set();  // адреса превью из файлов на устройстве — освободить
    this.dead = false;
    this.onDocDrag = (e) => {
      if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files')) e.preventDefault();
    };
    document.addEventListener('dragover', this.onDocDrag);
    document.addEventListener('drop', this.onDocDrag);
  }

  destroy() {
    this.dead = true;
    document.removeEventListener('dragover', this.onDocDrag);
    document.removeEventListener('drop', this.onDocDrag);
    for (const job of this.jobs) job.abort();
    for (const url of this.locals) URL.revokeObjectURL(url);
    this.jobs.clear();
    this.locals.clear();
    this.queue = [];
  }

  pending() {
    return this.ctx.variants().reduce((n, v) => n + v.images.filter((i) => i.state === 'up').length, 0);
  }

  failed() {
    return this.ctx.variants().reduce((n, v) => n + v.images.filter((i) => i.state === 'err').length, 0);
  }

  /** Сколько неудачных можно «Повторить» (сбой связи); остальные файлы не подошли — их только убрать. */
  retryable() {
    return this.ctx.variants().reduce((n, v) => n + v.images.filter((i) => i.state === 'err' && i.retry && i.file).length, 0);
  }

  /** Блок фото для цвета v: сетка миниатюр + большая зона «Добавить фото». counter — «3 из 8» в подписи. */
  view(v, counter = null) {
    const list = h('ul', { class: 'photos', 'aria-label': 'Фото этого цвета' });
    const inputEl = h('input', {
      type: 'file', multiple: true, accept: 'image/*,.heic,.heif', class: 'drop__in',
      'aria-label': 'Добавить фото — можно выбрать несколько сразу',
    });
    inputEl.addEventListener('change', () => {
      const files = Array.from(inputEl.files || []);
      inputEl.value = '';
      this.add(v, files);
    });
    const drop = h('label', { class: 'drop' },
      inputEl,
      h('span', { class: 'drop__ico' }, icon(I.plus)),
      h('span', { class: 'drop__txt' },
        h('span', { class: 'drop__t' }, 'Добавить фото'),
        h('span', { class: 'drop__h' }, 'можно выбрать несколько сразу', h('span', { class: 'drop__mouse' }, ' или перетащить сюда'))));
    const full = h('p', { class: 'photos__full', hidden: true });
    const wrap = h('div', { class: 'phw' }, list, drop, full);

    // Файлы, перетащенные мышью на блок фото
    let depth = 0;
    wrap.addEventListener('dragenter', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth++;
      wrap.classList.add('is-over');
    });
    wrap.addEventListener('dragover', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    });
    wrap.addEventListener('dragleave', () => {
      depth = Math.max(0, depth - 1);
      if (!depth) wrap.classList.remove('is-over');
    });
    wrap.addEventListener('drop', (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      wrap.classList.remove('is-over');
      this.add(v, Array.from(e.dataTransfer.files || []));
    });

    // Перестановка мышью (на телефоне — стрелки: палец листает страницу)
    sortable(list, {
      item: '.ph', handle: '.ph__pic', mouseOnly: true,
      onEnd: (from, to) => {
        const [img] = v.images.splice(from, 1);
        v.images.splice(to, 0, img);
        this.render(v);
        this.ctx.changed(v);
      },
      onFinish: () => this.render(v),   // пока тянули, могло догрузиться фото — дорисовываем
    });

    this.views.set(v.uid, { list, drop, full, wrap, input: inputEl, counter });
    this.render(v);
    return wrap;
  }

  render(v) {
    const view = this.views.get(v.uid);
    if (!view) return;
    if (view.list.querySelector('.is-drag')) return;   // не перерисовываем под рукой — дорисуем, когда отпустят
    const n = v.images.length;
    view.list.replaceChildren(...v.images.map((img, j) => this.tile(v, img, j, n)));
    view.list.hidden = !n;
    view.drop.classList.toggle('drop--big', !n);
    view.drop.hidden = n >= this.max;
    view.full.hidden = n < this.max;
    view.full.textContent = `В этом цвете уже ${this.max} фото — больше добавить нельзя. Удалите лишнее или добавьте ещё один цвет.`;
    const counter = view.counter;
    if (counter) {
      const up = v.images.filter((i) => i.state === 'up').length;
      counter.textContent = up ? `загружается ${up} ${plural(up, 'фото', 'фото', 'фото')}…` : `${n} из ${this.max}`;
      counter.classList.toggle('is-busy', !!up);
    }
  }

  tile(v, img, j, n) {
    const num = j + 1;
    const pic = h('button', {
      type: 'button', class: 'ph__pic', 'aria-label': `Фото ${num}${j === 0 ? ', главное' : ''} — открыть действия`,
      onclick: () => this.actions(v, img),
    });
    const src = img.thumb || img.local;
    if (src) {
      const im = h('img', { src, alt: '', draggable: 'false', decoding: 'async' });
      im.addEventListener('load', () => {
        if (img.thumb && img.local && im.src.endsWith(img.thumb)) this.free(img);
      });
      im.addEventListener('error', () => im.replaceWith(h('span', { class: 'ph__noimg' }, icon(I.photo))));
      pic.append(im);
    } else {
      pic.append(h('span', { class: 'ph__noimg' }, icon(I.photo)));
    }
    const box = h('div', { class: 'ph__box' }, pic, h('span', { class: 'ph__n', 'aria-hidden': 'true' }, String(num)));
    if (img.state === 'up') {
      const pct = Math.round((img.progress || 0) * 100);
      box.append(h('div', { class: 'ph__up' },
        h('span', { class: 'ph__bar' }, h('i', { style: `width:${Math.max(4, pct)}%` })),
        h('span', { class: 'ph__pct' }, pctText(img))));
    }
    if (img.state === 'err') {
      // на плитке — коротко (она шириной с палец), полный текст с именем файла — под «Фото» (ctx.bad)
      box.append(h('div', { class: 'ph__err', title: badText(img) },
        icon(I.alert),
        h('p', { class: 'ph__et' }, img.retry ? 'Не загрузилось' : 'Не подошёл'),
        img.name && h('p', { class: 'ph__fn' }, img.name),
        img.file && img.retry && h('button', { type: 'button', class: 'ph__retry', onclick: () => this.retry(v, img) }, 'Повторить')));
    }
    box.append(h('button', {
      type: 'button', class: 'ph__x', title: img.state === 'ok' ? 'Удалить фото' : 'Убрать',
      'aria-label': img.state === 'ok' ? `Удалить фото ${num}` : `Убрать фото ${num}`,
      onclick: () => this.remove(v, img),
    }, icon(I.close)));
    if (img.state !== 'err' && n > 1) {
      box.append(h('div', { class: 'ph__nav' },
        h('button', { type: 'button', class: 'ph__arr', title: 'Сдвинуть левее', 'aria-label': `Сдвинуть фото ${num} левее`, disabled: j === 0, onclick: () => this.move(v, j, j - 1, 'prev') }, icon(I.left)),
        h('button', { type: 'button', class: 'ph__arr', title: 'Сдвинуть правее', 'aria-label': `Сдвинуть фото ${num} правее`, disabled: j === n - 1, onclick: () => this.move(v, j, j + 1, 'next') }, icon(I.right))));
    }
    const foot = j === 0
      ? h('p', { class: 'ph__star' }, icon(I.star), 'Главное')
      : h('button', { type: 'button', class: 'ph__mk', disabled: img.state === 'err', onclick: () => this.move(v, j, 0, 'main') }, 'Сделать главным');
    return h('li', { class: `ph${j === 0 ? ' ph--main' : ''}${img.state === 'up' ? ' is-up' : ''}${img.state === 'err' ? ' is-bad' : ''}`, 'data-img': img.uid }, box, foot);
  }

  /** Обновить только полоску загрузки (часто — без перерисовки сетки). */
  progress(img) {
    const li = document.querySelector(`.ph[data-img="${img.uid}"]`);
    if (!li) return;
    const pct = Math.round((img.progress || 0) * 100);
    const bar = li.querySelector('.ph__bar i');
    const label = li.querySelector('.ph__pct');
    if (bar) bar.style.width = `${Math.max(4, pct)}%`;
    if (label) label.textContent = pctText(img);
  }

  free(img) {
    if (!img.local) return;
    URL.revokeObjectURL(img.local);
    this.locals.delete(img.local);
    img.local = null;
  }

  owner(img) {
    return this.ctx.variants().find((v) => v.images.includes(img)) || null;
  }

  add(v, files) {
    if (!files.length) return;
    const room = this.max - v.images.length;
    if (room <= 0) {
      toast(`В одном цвете — не больше ${this.max} фото. Удалите лишнее или добавьте ещё один цвет.`, { kind: 'err' });
      return;
    }
    const take = files.slice(0, room);
    if (files.length > room) {
      toast(`Добавлено ${room} ${plural(room, 'фото', 'фото', 'фото')} из ${files.length}: в одном цвете — не больше ${this.max}.`);
    }
    const bad = [];
    for (const f of take) {
      const img = { uid: uid(), ref: null, thumb: null, local: null, state: 'up', progress: 0, file: f, name: f.name || '' };
      const why = precheck(f);
      if (why) {
        img.state = 'err';
        img.error = why;
        img.retry = false;
        bad.push(img);
      } else {
        if (PREVIEW_TYPE.test(f.type)) {
          img.local = URL.createObjectURL(f);
          this.locals.add(img.local);
        }
        this.queue.push(img);
      }
      v.images.push(img);
    }
    this.render(v);
    this.ctx.changed(v);
    if (bad.length && this.ctx.bad) this.ctx.bad(v, bad);
    this.pump();
  }

  retry(v, img) {
    img.state = 'up';
    img.progress = 0;
    img.error = null;
    this.queue.push(img);
    this.render(v);
    this.ctx.changed(v);
    this.pump();
  }

  pump() {
    while (!this.dead && this.active < PARALLEL && this.queue.length) {
      const img = this.queue.shift();
      if (img.state !== 'up' || !this.owner(img)) continue;
      this.active++;
      this.send(img);
    }
  }

  /** Одно фото: уменьшить на телефоне (если большое) → отправить с процентами → превью с сервера. */
  async send(img) {
    let cancelled = false;
    img.prep = true;
    img.abort = () => { cancelled = true; };
    this.progress(img);
    const file = await shrink(img.file);
    img.prep = false;
    if (cancelled || this.dead || img.state !== 'up' || !this.owner(img)) {
      this.active--;
      img.abort = null;
      if (!this.dead) this.pump();
      return;
    }
    const job = uploadFile(file, {
      onProgress: (p) => {
        img.progress = p;
        this.progress(img);
      },
    });
    img.abort = job.abort;
    this.jobs.add(job);
    let failed = false;
    try {
      const r = await job.promise;
      img.state = 'ok';
      img.ref = `upload:${r.upload}`;
      img.thumb = r.thumb || `/api/uploads/${encodeURIComponent(r.upload)}`;
      img.file = null;
    } catch (e) {
      if (!(e && e.name === 'AbortError')) {
        img.state = 'err';
        img.error = (e && e.message) || 'Не получилось загрузить фото.';
        img.retry = !(e && (e.status === 400 || e.status === 413 || e.status === 415 || e.status === 422));
        failed = true;
      }
    } finally {
      this.active--;
      this.jobs.delete(job);
      img.abort = null;
    }
    if (this.dead) return;
    const owner = this.owner(img);
    if (owner) this.render(owner);
    this.ctx.changed(owner);
    if (failed && owner && this.ctx.bad) this.ctx.bad(owner, [img]);
    this.pump();
  }

  async remove(v, img) {
    const j = v.images.indexOf(img);
    if (j < 0) return false;
    if (img.state === 'ok') {
      const ok = await dialog({
        title: `Удалить фото № ${j + 1}?`,
        text: 'Фото уберётся, когда вы нажмёте «Сохранить и опубликовать». Передумали — кнопка «Отменить правки» внизу отменит все несохранённые правки этого товара.',
        buttons: [{ label: 'Не удалять', value: false, kind: 'ink' }, { label: 'Удалить фото', value: true, kind: 'danger-line' }],
        dismiss: false,
      });
      if (!ok) return false;
    }
    if (img.abort) img.abort();
    this.free(img);
    const k = v.images.indexOf(img);
    if (k >= 0) v.images.splice(k, 1);
    this.render(v);
    this.ctx.changed(v);
    const view = this.views.get(v.uid);
    if (view) {
      const next = view.list.querySelector(`.ph:nth-child(${Math.min(k + 1, v.images.length)}) .ph__pic`);
      (next || view.input).focus({ preventScroll: true });
    }
    return true;
  }

  /** Переставить фото: from → to. which — какую кнопку вернуть в фокус после перерисовки. */
  move(v, from, to, which) {
    if (to < 0 || to >= v.images.length || from === to) return;
    const [img] = v.images.splice(from, 1);
    v.images.splice(to, 0, img);
    this.render(v);
    this.ctx.changed(v);
    const li = document.querySelector(`.ph[data-img="${img.uid}"]`);
    flash(li);
    if (li) {
      const btn = which === 'prev' ? li.querySelectorAll('.ph__arr')[0] : which === 'next' ? li.querySelectorAll('.ph__arr')[1] : li.querySelector('.ph__pic');
      const target = btn && !btn.disabled ? btn : li.querySelector('.ph__pic');
      if (target) target.focus({ preventScroll: true });
    }
    if (which === 'main') toast('Это фото теперь главное — его видно в каталоге.', { kind: 'ok', timeout: 3000 });
  }

  moveTo(v, img, target) {
    if (target.images.length >= this.max) {
      toast(`В цвете «${this.ctx.label(target)}» уже ${this.max} фото — сначала удалите там лишнее.`, { kind: 'err' });
      return false;
    }
    const j = v.images.indexOf(img);
    if (j < 0) return false;
    v.images.splice(j, 1);
    target.images.push(img);
    this.render(v);
    this.render(target);
    if (this.ctx.refresh) this.ctx.refresh(target);
    this.ctx.changed(v);
    flash(document.querySelector(`.ph[data-img="${img.uid}"]`));
    toast(`Фото перенесено в цвет «${this.ctx.label(target)}».`, { kind: 'ok', timeout: 3000 });
    return true;
  }

  /** Лист с крупным фото и действиями — удобнее пальцем, чем маленькие кнопки на миниатюре. */
  actions(v, img) {
    const j = v.images.indexOf(img);
    if (j < 0) return;
    const n = v.images.length;
    const others = this.ctx.variants().filter((o) => o !== v);
    const act = (ico, label, run, cls = '') => h('button', { type: 'button', class: `act ${cls}`, onclick: run }, icon(ico), h('span', null, label));
    const src = img.thumb || img.local;
    let s = null;
    const body = h('div', { class: 'pha' },
      h('div', { class: 'pha__pic' }, src ? h('img', { src, alt: `Фото ${j + 1}` }) : h('span', { class: 'ph__noimg' }, icon(I.photo))),
      h('div', { class: 'pha__acts' },
        j === 0
          ? h('p', { class: 'pha__main' }, icon(I.star), 'Это главное фото — его видно в каталоге')
          : img.state !== 'err' && act(I.star, 'Сделать главным', () => { s.close(); this.move(v, j, 0, 'main'); }),
        j > 0 && img.state !== 'err' && act(I.left, 'Сдвинуть левее', () => { s.close(); this.move(v, j, j - 1, 'prev'); }),
        j < n - 1 && img.state !== 'err' && act(I.right, 'Сдвинуть правее', () => { s.close(); this.move(v, j, j + 1, 'next'); }),
        others.length > 0 && img.state === 'ok' && h('div', { class: 'pha__move' },
          h('p', { class: 'pha__mt' }, 'Перенести в другой цвет'),
          h('div', { class: 'chips' }, others.map((o) => h('button', {
            type: 'button', class: 'chip chip--sw',
            onclick: () => { if (this.moveTo(v, img, o)) s.close(); },
          }, swatch(this.ctx.palette(o.color), 'sw--m'), this.ctx.label(o))))),
        act(I.trash, img.state === 'ok' ? 'Удалить фото' : 'Убрать', async () => {
          if (await this.remove(v, img)) s.close();
        }, 'act--danger')));
    s = sheet({ title: `Фото ${j + 1} из ${n}`, body, cls: 'sheet--photo' });
  }
}

function hasFiles(e) {
  return e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');
}

function pctText(img) {
  if (img.prep) return 'Готовим…';
  const pct = Math.round((img.progress || 0) * 100);
  return pct >= 99 ? 'Обработка…' : `Загрузка ${pct}%`;
}

export { okImg };
