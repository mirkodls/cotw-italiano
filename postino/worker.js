// Postino di CotW Italiano (Cloudflare Worker, gratis).
//  1) Segnalazioni: riceve la segnalazione dal programma e la gira nel canale Discord.
//  2) Contributi: chi aiuta a doppiare le battute nuove (con la SUA chiave ElevenLabs, usata solo sul suo PC)
//     prenota delle battute, poi manda qui SOLO gli audio. Gli audio restano nel deposito (KV) finche' l'autore
//     non li scarica con RICEVI_CONTRIBUTI.bat.
// Impostazioni del Worker (Settings -> Variables and Secrets / Bindings):
//   WEBHOOK            segreto: webhook del canale Discord delle segnalazioni
//   WEBHOOK_CONTRIBUTI segreto (facoltativo): webhook del canale dove annunciare i contributi (altrimenti WEBHOOK)
//   ADMIN              segreto: password dell'autore per scaricare i contributi
//   DEPOSITO           binding KV namespace: il deposito degli audio
const REPO = 'mirkodls/cotw-italiano';
const LIMITE_ORA_PER_PC = 5;       // segnalazioni all'ora dalla stessa connessione
const LIMITE_ORA_TOTALE = 120;     // tetto generale all'ora (contro lo spam)
const PRENOTA_MAX = 60;            // battute per prenotazione
const PRENOTA_ORE = 3;             // dopo 3 ore le battute prenotate e non consegnate tornano libere
const AUDIO_MAX = 1024 * 1024;     // un audio non puo' superare 1 MB
const visti = new Map();           // indirizzo -> orari (memoria del Worker, indicativa)
let totale = [];
let elenco = { t: 0, ids: null, versione: null };

function risposta(dati, stato = 200) {
  return new Response(JSON.stringify(dati), { status: stato, headers: { 'Content-Type': 'application/json' } });
}

function troppi(chiave, limite) {
  const ora = Date.now();
  const l = (visti.get(chiave) || []).filter(t => ora - t < 3600e3);
  if (l.length >= limite) return true;
  l.push(ora); visti.set(chiave, l);
  if (visti.size > 5000) visti.clear();
  return false;
}

function pulisciNome(s) {
  return String(s || '').replace(/[@`*_~|<>\[\]\\]/g, '').replace(/\s+/g, ' ').trim().slice(0, 32) || 'Anonimo';
}

async function discord(url, testo) {
  if (!url) return;
  try { await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: testo, username: 'CotW Italiano', allowed_mentions: { parse: [] } }),
  }); } catch (e) { /* l'annuncio non e' indispensabile */ }
}

// elenco delle battute da doppiare (pubblicato dall'autore su GitHub insieme alla versione)
async function battuteDaDoppiare(env) {
  if (elenco.ids && Date.now() - elenco.t < 300e3) return elenco;
  const base = env.GITHUB || ('https://github.com/' + REPO + '/releases');
  const r = await fetch(base + '/latest/download/versione.json');
  let ids = [], versione = null;
  if (r.ok) {
    const m = await r.json();
    const d = m.da_doppiare;
    if (d && d.nome && d.tag) {
      const r2 = await fetch(base + '/download/' + d.tag + '/' + d.nome);
      if (r2.ok) { const j = await r2.json(); ids = (j.battute || []).map(b => b.id); versione = j.versione || d.tag; }
    }
  }
  elenco = { t: Date.now(), ids, versione };
  return elenco;
}

async function ricevuti(env) {
  // id -> chi, dagli audio gia' nel deposito
  const out = {};
  let cursor;
  do {
    const l = await env.DEPOSITO.list({ prefix: 'audio:', cursor });
    for (const k of l.keys) out[k.name.slice(6)] = (k.metadata && k.metadata.chi) || '?';
    cursor = l.list_complete ? null : l.cursor;
  } while (cursor);
  return out;
}

async function leggiPrenotate(env) {
  const p = await env.DEPOSITO.get('prenotate', 'json');
  const ora = Date.now(), out = {};
  for (const [id, v] of Object.entries(p || {})) if (v[0] > ora) out[id] = v;
  return out;
}

async function contributi(req, env, url, ip) {
  if (!env.DEPOSITO) return risposta({ errore: 'deposito non configurato' }, 503);
  const parte = url.pathname.replace(/^\/contributi\/?/, '');

  if (parte === 'stato' && req.method === 'GET') {
    const e = await battuteDaDoppiare(env);
    const ric = await ricevuti(env), pren = await leggiPrenotate(env);
    const fatte = e.ids.filter(id => ric[id]).length;
    const occupate = e.ids.filter(id => !ric[id] && pren[id]).length;
    return risposta({ versione: e.versione, totale: e.ids.length, fatte, prenotate: occupate,
                      libere: e.ids.length - fatte - occupate });
  }

  if (parte === 'prenota' && req.method === 'POST') {
    if (troppi('p:' + ip, 12)) return risposta({ errore: 'troppe' }, 429);
    let d; try { d = await req.json(); } catch (e) { return risposta({ errore: 'formato' }, 400); }
    const chi = pulisciNome(d.chi);
    const quante = Math.max(1, Math.min(PRENOTA_MAX, parseInt(d.quante) || 20));
    const e = await battuteDaDoppiare(env);
    const ric = await ricevuti(env), pren = await leggiPrenotate(env);
    const scelte = [];
    for (const id of e.ids) {
      if (ric[id] || pren[id]) continue;
      scelte.push(id);
      if (scelte.length >= quante) break;
    }
    const scade = Date.now() + PRENOTA_ORE * 3600e3;
    for (const id of scelte) pren[id] = [scade, chi];
    if (scelte.length) await env.DEPOSITO.put('prenotate', JSON.stringify(pren));
    return risposta({ versione: e.versione, ids: scelte, scadenza_ore: PRENOTA_ORE });
  }

  if (parte === 'audio' && req.method === 'POST') {
    if (troppi('a:' + ip, 400)) return risposta({ errore: 'troppe' }, 429);
    const id = url.searchParams.get('id') || '';
    const chi = pulisciNome(url.searchParams.get('chi'));
    const e = await battuteDaDoppiare(env);
    if (!e.ids.includes(id)) return risposta({ errore: 'battuta non richiesta' }, 400);
    const b = new Uint8Array(await req.arrayBuffer());
    const mp3 = b.length > 1000 && b.length <= AUDIO_MAX &&
      ((b[0] === 0x49 && b[1] === 0x44 && b[2] === 0x33) || (b[0] === 0xFF && (b[1] & 0xE0) === 0xE0));
    if (!mp3) return risposta({ errore: 'audio non valido' }, 400);
    await env.DEPOSITO.put('audio:' + id, b, { metadata: { chi, t: Date.now() } });
    return risposta({ ok: true });
  }

  if (parte === 'libera' && req.method === 'POST') {          // chi si ferma prima restituisce le battute non fatte
    let d; try { d = await req.json(); } catch (e) { return risposta({ errore: 'formato' }, 400); }
    const chi = pulisciNome(d.chi);
    const pren = await leggiPrenotate(env);
    let n = 0;
    for (const id of (d.ids || []).slice(0, PRENOTA_MAX)) if (pren[id] && pren[id][1] === chi) { delete pren[id]; n++; }
    if (n) await env.DEPOSITO.put('prenotate', JSON.stringify(pren));
    return risposta({ ok: true, liberate: n });
  }

  if (parte === 'fine' && req.method === 'POST') {
    if (troppi('f:' + ip, 6)) return risposta({ errore: 'troppe' }, 429);
    let d; try { d = await req.json(); } catch (e) { return risposta({ errore: 'formato' }, 400); }
    const chi = pulisciNome(d.chi);
    const n = Math.max(0, Math.min(1000, parseInt(d.fatte) || 0));
    if (n > 0) await discord(env.WEBHOOK_CONTRIBUTI || env.WEBHOOK,
      '\u{1F399}️ **' + chi + '** ha appena doppiato **' + n + '** ' + (n === 1 ? 'battuta' : 'battute') + ' per la mod italiana. Grazie!');
    return risposta({ ok: true });
  }

  return risposta({ errore: 'sconosciuto' }, 404);
}

async function admin(req, env, url) {
  if (!env.ADMIN || req.headers.get('X-Admin') !== env.ADMIN) return risposta({ errore: 'password' }, 403);
  if (!env.DEPOSITO) return risposta({ errore: 'deposito non configurato' }, 503);
  const parte = url.pathname.replace(/^\/admin\/?/, '');
  if (parte === 'audio' && req.method === 'GET') {
    const out = [];
    let cursor;
    do {
      const l = await env.DEPOSITO.list({ prefix: 'audio:', cursor });
      for (const k of l.keys) out.push({ id: k.name.slice(6), chi: (k.metadata || {}).chi, t: (k.metadata || {}).t });
      cursor = l.list_complete ? null : l.cursor;
    } while (cursor);
    return risposta({ audio: out });
  }
  if (parte.startsWith('audio/')) {
    const id = decodeURIComponent(parte.slice(6));
    if (req.method === 'GET') {
      const v = await env.DEPOSITO.get('audio:' + id, 'arrayBuffer');
      return v ? new Response(v, { headers: { 'Content-Type': 'audio/mpeg' } }) : risposta({ errore: 'non c\'e\'' }, 404);
    }
    if (req.method === 'DELETE') { await env.DEPOSITO.delete('audio:' + id); return risposta({ ok: true }); }
  }
  return risposta({ errore: 'sconosciuto' }, 404);
}

async function segnalazione(req, env, ip) {
  if (!env.WEBHOOK) return risposta({ errore: 'manca il segreto WEBHOOK' }, 500);
  const ora = Date.now();
  totale = totale.filter(t => ora - t < 3600e3);
  if (totale.length >= LIMITE_ORA_TOTALE || troppi('s:' + ip, LIMITE_ORA_PER_PC)) return risposta({ errore: 'troppe' }, 429);
  let d;
  try { d = await req.json(); } catch (e) { return risposta({ errore: 'formato' }, 400); }
  const testo = String((d && d.testo) || '').slice(0, 1900).trim();
  if (!testo.startsWith('**Segnalazione CotW Italiano**') || testo.length < 40) return risposta({ errore: 'formato' }, 400);
  totale.push(ora);
  const r = await fetch(env.WEBHOOK, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: testo, username: 'Segnalazioni CotW Italiano', allowed_mentions: { parse: [] } }),
  });
  if (!r.ok) return risposta({ errore: 'discord', codice: r.status }, 502);
  return risposta({ ok: true });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const ip = req.headers.get('CF-Connecting-IP') || '?';
    try {
      if (url.pathname.startsWith('/contributi')) return await contributi(req, env, url, ip);
      if (url.pathname.startsWith('/admin')) return await admin(req, env, url);
      if (req.method === 'GET') return new Response('Postino CotW Italiano attivo.');
      if (req.method === 'POST') return await segnalazione(req, env, ip);
      return risposta({ errore: 'metodo' }, 405);
    } catch (e) {
      return risposta({ errore: 'interno', dettaglio: String(e).slice(0, 200) }, 500);
    }
  },
};
