// Postino delle segnalazioni di CotW Italiano (Cloudflare Worker, gratis).
// Riceve la segnalazione dal programma e la gira nel canale Discord.
// L'indirizzo del webhook NON e' qui: sta nel segreto WEBHOOK delle impostazioni del Worker.
const LIMITE_ORA_PER_PC = 5;       // segnalazioni all'ora dalla stessa connessione
const LIMITE_ORA_TOTALE = 120;     // tetto generale all'ora (contro lo spam)
const visti = new Map();           // indirizzo -> orari degli invii (memoria del Worker, indicativa)
let totale = [];

function risposta(dati, stato = 200) {
  return new Response(JSON.stringify(dati), { status: stato, headers: { 'Content-Type': 'application/json' } });
}

export default {
  async fetch(req, env) {
    if (req.method === 'GET') return new Response('Postino CotW Italiano attivo.');
    if (req.method !== 'POST') return risposta({ errore: 'metodo' }, 405);
    if (!env.WEBHOOK) return risposta({ errore: 'manca il segreto WEBHOOK' }, 500);

    const ora = Date.now();
    const ip = req.headers.get('CF-Connecting-IP') || '?';
    const miei = (visti.get(ip) || []).filter(t => ora - t < 3600e3);
    totale = totale.filter(t => ora - t < 3600e3);
    if (miei.length >= LIMITE_ORA_PER_PC || totale.length >= LIMITE_ORA_TOTALE) return risposta({ errore: 'troppe' }, 429);

    let d;
    try { d = await req.json(); } catch (e) { return risposta({ errore: 'formato' }, 400); }
    const testo = String((d && d.testo) || '').slice(0, 1900).trim();
    if (!testo.startsWith('**Segnalazione CotW Italiano**') || testo.length < 40) return risposta({ errore: 'formato' }, 400);

    miei.push(ora); visti.set(ip, miei); totale.push(ora);
    if (visti.size > 5000) visti.clear();

    const r = await fetch(env.WEBHOOK, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: testo, username: 'Segnalazioni CotW Italiano', allowed_mentions: { parse: [] } }),
    });
    if (!r.ok) return risposta({ errore: 'discord', codice: r.status }, 502);
    return risposta({ ok: true });
  },
};
