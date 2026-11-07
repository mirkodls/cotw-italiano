// Postino di CotW Italiano (Cloudflare Worker, gratis).
//  1) Segnalazioni: riceve la segnalazione dal programma e la gira nel canale Discord.
//  2) Contributi: chi aiuta a doppiare le battute nuove (con la SUA chiave ElevenLabs, usata solo sul suo PC)
//     prenota delle battute, poi manda qui SOLO gli audio. Gli audio restano nel deposito (KV) finche' l'autore
//     non li scarica con RICEVI_CONTRIBUTI.bat.
// Impostazioni del Worker (Settings -> Variables and Secrets / Bindings):
//   WEBHOOK            segreto: webhook del canale Discord delle segnalazioni
//   WEBHOOK_CONTRIBUTI segreto (facoltativo): webhook del canale dove annunciare i contributi (altrimenti WEBHOOK)
//   ADMIN              segreto: password dell'autore per scaricare i contributi e leggere le segnalazioni
//   DEPOSITO           binding KV namespace: il deposito degli audio (e delle segnalazioni)
//   BOT_DISCORD        segreto (facoltativo): token del bot che legge i messaggi scritti a mano nel canale
//   CANALE             variabile (facoltativa): id del canale Discord delle segnalazioni
const REPO = 'mirkodls/cotw-italiano';
const LIMITE_ORA_PER_PC = 40;      // segnalazioni all'ora dalla stessa connessione (solo contro lo spam)
const LIMITE_ORA_TOTALE = 300;     // tetto generale all'ora (contro lo spam)
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
  // id -> chi: tenuto in una chiave sola (aggiornata a ogni audio). Se manca, si ricostruisce dal deposito.
  const r = await env.DEPOSITO.get('ricevuti', 'json');
  if (r) return r;
  const out = await ricevutiDaLista(env);
  await env.DEPOSITO.put('ricevuti', JSON.stringify(out));
  return out;
}

async function ricevutiDaLista(env) {
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
    const ric = await ricevuti(env);                 // subito "fatta" per tutti
    ric[id] = chi;
    await env.DEPOSITO.put('ricevuti', JSON.stringify(ric));
    const pren = await leggiPrenotate(env);
    if (pren[id]) { delete pren[id]; await env.DEPOSITO.put('prenotate', JSON.stringify(pren)); }
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

// Confronto "a tempo costante": il tempo non dipende da quanti caratteri sono giusti (niente indizi sulla password).
function ugualiSicuro(a, b) {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

async function admin(req, env, url) {
  if (!env.ADMIN || !ugualiSicuro(req.headers.get('X-Admin') || '', env.ADMIN)) return risposta({ errore: 'password' }, 403);
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
    if (req.method === 'DELETE') {
      await env.DEPOSITO.delete('audio:' + id);
      const ric = await ricevuti(env);
      if (ric[id]) { delete ric[id]; await env.DEPOSITO.put('ricevuti', JSON.stringify(ric)); }
      return risposta({ ok: true });
    }
  }
  if (parte === 'ricevuti/ricostruisci' && req.method === 'POST') {
    const out = await ricevutiDaLista(env);
    await env.DEPOSITO.put('ricevuti', JSON.stringify(out));
    return risposta({ ok: true, n: Object.keys(out).length });
  }
  // ---- messaggi scritti a mano nel canale Discord (bot: segreto BOT_DISCORD) ----
  if (parte === 'discord' && req.method === 'GET') {
    if (!env.BOT_DISCORD) return risposta({ errore: 'manca il segreto BOT_DISCORD' }, 503);
    const canale = url.searchParams.get('canale') || env.CANALE || '';
    if (!/^[0-9]{5,25}$/.test(canale)) return risposta({ errore: 'canale' }, 400);
    const dopo = url.searchParams.get('dopo') || '';
    let q = 'https://discord.com/api/v10/channels/' + canale + '/messages?limit=100';
    if (/^[0-9]{5,25}$/.test(dopo)) q += '&after=' + dopo;
    const r = await fetch(q, { headers: { Authorization: 'Bot ' + env.BOT_DISCORD, 'User-Agent': 'CotW-Italiano-postino' } });
    if (!r.ok) return risposta({ errore: 'discord', codice: r.status, dettaglio: (await r.text()).slice(0, 200) }, 502);
    const l = await r.json();
    return risposta({ messaggi: l.map(m => ({ id: m.id, t: Date.parse(m.timestamp), autore: (m.author || {}).username,
      bot: !!(m.webhook_id || (m.author || {}).bot), testo: m.content || '',
      allegati: (m.attachments || []).map(x => x.url) })).sort((x, y) => x.t - y.t) });
  }
  // ---- segnalazioni (per l'app sviluppatore) ----
  if (parte === 'segnalazioni' && req.method === 'GET') {
    const da = parseInt(url.searchParams.get('da')) || 0;      // solo quelle dopo questo momento (ms)
    const stati = (await env.DEPOSITO.get('stati_segn', 'json')) || {};
    const out = [];
    let cursor;
    do {
      const l = await env.DEPOSITO.list({ prefix: 'segn:', cursor });
      for (const k of l.keys) {
        const m = k.metadata || {};
        if ((m.t || 0) <= da) continue;
        out.push({ id: k.name.slice(5), t: m.t, stato: stati[k.name.slice(5)] || 'nuova',
                   testo: await env.DEPOSITO.get(k.name) });
        if (out.length >= 200) break;
      }
      cursor = l.list_complete || out.length >= 200 ? null : l.cursor;
    } while (cursor);
    return risposta({ segnalazioni: out.sort((a, b) => a.t - b.t) });
  }
  if (parte.startsWith('segnalazioni/') && req.method === 'POST') {      // stato: vista / corretta / scartata
    const id = decodeURIComponent(parte.slice(13));
    let d; try { d = await req.json(); } catch (e) { return risposta({ errore: 'formato' }, 400); }
    if (!['nuova', 'vista', 'corretta', 'scartata'].includes(d.stato)) return risposta({ errore: 'stato' }, 400);
    const stati = (await env.DEPOSITO.get('stati_segn', 'json')) || {};
    stati[id] = d.stato;
    await env.DEPOSITO.put('stati_segn', JSON.stringify(stati));
    return risposta({ ok: true });
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
  const id = ora.toString(36) + Math.random().toString(36).slice(2, 8);
  if (env.DEPOSITO) await env.DEPOSITO.put('segn:' + id, testo, { metadata: { t: ora } });
  const r = await fetch(env.WEBHOOK, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: testo + '\n`#' + id + '`', username: 'Segnalazioni CotW Italiano', allowed_mentions: { parse: [] } }),
  });
  if (!r.ok) return risposta({ errore: 'discord', codice: r.status }, 502);
  return risposta({ ok: true, id });
}

async function statoSegnalazioni(env, url) {
  // il programma chiede lo stato delle SUE segnalazioni (gli id li conosce solo chi le ha mandate)
  const ids = (url.searchParams.get('ids') || '').split(',').filter(Boolean).slice(0, 200);
  const stati = env.DEPOSITO ? ((await env.DEPOSITO.get('stati_segn', 'json')) || {}) : {};
  const out = {};
  for (const id of ids) out[id] = stati[id] || 'nuova';
  return risposta({ stati: out });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const ip = req.headers.get('CF-Connecting-IP') || '?';
    try {
      if (url.pathname.startsWith('/contributi')) return await contributi(req, env, url, ip);
      if (url.pathname.startsWith('/admin')) return await admin(req, env, url);
      if (url.pathname === '/segnalazioni/stato') return await statoSegnalazioni(env, url);
      if (req.method === 'GET') return new Response('Postino CotW Italiano attivo.');
      if (req.method === 'POST') return await segnalazione(req, env, ip);
      return risposta({ errore: 'metodo' }, 405);
    } catch (e) {
      return risposta({ errore: 'interno', dettaglio: String(e).slice(0, 200) }, 500);
    }
  },
};
