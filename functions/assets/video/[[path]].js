// Cloudflare Pages Function: видео главной кусками (206 Partial Content). Safari на iPhone играет видео, только если
// сервер отвечает на заголовок Range кодом 206, а сам Pages на Range отдаёт 200 и весь файл
// (https://developers.cloudflare.com/pages/configuration/serving-pages/). Срабатывает только на /assets/video/*,
// остальной сайт — обычная статика. Папка functions/ лежит рядом с site/: wrangler берёт её из папки, где запущен.
// К ответам функций _headers не применяется, поэтому Cache-Control ставится здесь — тот же, что у фото (build.py).
const CACHE = 'public, max-age=600, stale-while-revalidate=86400';

export async function onRequest({ request, env }) {
  if (request.method !== 'GET' && request.method !== 'HEAD') return env.ASSETS.fetch(request);
  const m = /^bytes=(\d*)-(\d*)$/.exec((request.headers.get('Range') || '').trim());
  if (!m || (m[1] === '' && m[2] === '')) return cached(await env.ASSETS.fetch(request));   // без Range: 200 или 304 по ETag
  const res = await env.ASSETS.fetch(new Request(request.url));   // целый файл: без Range и условий If-*
  if (res.status !== 200) return res;
  const ifRange = request.headers.get('If-Range');
  if (ifRange && ifRange !== res.headers.get('ETag')) return cached(res);   // файл сменился после прошлого куска — целиком
  const buf = await res.arrayBuffer();
  const size = buf.byteLength;
  let start, end;
  if (m[1] === '') { start = Math.max(0, size - Number(m[2])); end = size - 1; }   // bytes=-500 — последние 500 байт
  else { start = Number(m[1]); end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1); }
  if (start >= size || start > end) {
    return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${size}`, 'Accept-Ranges': 'bytes' } });
  }
  const h = new Headers(res.headers);
  h.set('Accept-Ranges', 'bytes');
  h.set('Cache-Control', CACHE);
  h.set('Content-Range', `bytes ${start}-${end}/${size}`);
  h.delete('Content-Length');   // длину куска поставит платформа
  h.delete('Content-Encoding');
  return new Response(buf.slice(start, end + 1), { status: 206, headers: h });   // у HEAD тело отбросит платформа
}

// Ответ статики как есть, но с Accept-Ranges и нашим сроком кэша (и у 304: браузер обновляет по нему сохранённое)
function cached(res) {
  const out = new Response(res.body, res);
  out.headers.set('Accept-Ranges', 'bytes');
  if (out.ok || out.status === 304) out.headers.set('Cache-Control', CACHE);
  return out;
}
