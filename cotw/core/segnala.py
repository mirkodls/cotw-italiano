"""Segnalazione errori: trova la battuta da poche parole e prepara il messaggio per Discord."""
import os
import re
import json
import time
import base64
import unicodedata
from . import aggiornamenti, rete, percorsi

TIPI = ['Audio: pronuncia sbagliata',
        'Audio: voce tagliata o troppo veloce',
        'Audio: si sente in inglese',
        'Audio: la voce dice una cosa diversa dalla scritta',
        'Audio: voce sbagliata (uomo/donna, personaggio sbagliato)',
        'Scritto: errore di ortografia',
        'Scritto: parola sbagliata',
        'Scritto: la frase non ha senso / traduzione sbagliata',
        'Scritto: punteggiatura (manca un punto, una virgola...)',
        'Scritto: testo rimasto in inglese',
        'Altro (crash, il programma non funziona...)']
_MAPPE = ['Hirschfelden', 'Layton Lake', 'Medved-Taiga', 'Vurhonga Savanna', 'Parque Fernando', 'Yukon Valley',
          'Cuatro Colinas', 'Silver Ridge Peaks', 'Te Awaroa', 'Rancho del Arroyo', 'Mississippi Acres',
          'Revontuli Coast', 'New England', 'Emerald Coast', 'Sundarpatan', 'Salzwiesen Park', 'Askiy Ridge',
          'Scozia', 'Peru']
MAPPE = ['Non lo so / menu del gioco'] + sorted(_MAPPE, key=str.lower) + ['Eventi']


def _norm(t):
    t = unicodedata.normalize('NFKD', t.lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]+', ' ', t)


_CACHE = {'mtime': None, 'righe': []}


def battute():
    """Elenco delle battute scaricato con gli aggiornamenti: [{'id','chi','mappa','it'}, ...]."""
    p = os.path.join(aggiornamenti.cartella_cache(), 'battute.json')
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return []
    if _CACHE['mtime'] != mt:
        dati = json.load(open(p, encoding='utf-8'))
        for b in dati:
            b['_n'] = _norm(b.get('it', '') + ' ' + b.get('chi', ''))
        _CACHE.update(mtime=mt, righe=dati)
    return _CACHE['righe']


ALTRO = 'Altro'


def _mappa(b):
    m = b.get('mappa') or '?'
    return ALTRO if m == '?' else m


def mappe():
    """[(mappa, numero di frasi)] in ordine alfabetico, 'Eventi' e 'Altro' in fondo."""
    conta = {}
    for b in battute():
        conta[_mappa(b)] = conta.get(_mappa(b), 0) + 1
    fondo = [m for m in ('Eventi', ALTRO) if m in conta]
    return sorted(((m, n) for m, n in conta.items() if m not in fondo), key=lambda x: x[0].lower()) + \
        [(m, conta[m]) for m in fondo]


def personaggi(mappa=None):
    """[(personaggio, numero di frasi)] della mappa (o di tutte)."""
    conta = {}
    for b in battute():
        if mappa and _mappa(b) != mappa:
            continue
        conta[b.get('chi', '?')] = conta.get(b.get('chi', '?'), 0) + 1
    return sorted(conta.items(), key=lambda x: x[0].lower())


def cerca(testo, mappa=None, chi=None, massimo=400):
    if mappa and mappa not in {m for m, _ in mappe()}:
        mappa = None
    """Frasi che contengono tutte le parole scritte, dentro la mappa/personaggio scelti.
    Senza parole: tutte le frasi della mappa/personaggio scelti (se nessuno dei due e' scelto, niente)."""
    parole = [p for p in _norm(testo).split() if len(p) > 1]
    if not parole and not mappa and not chi:
        return []
    out = []
    for b in battute():
        if mappa and _mappa(b) != mappa:
            continue
        if chi and b.get('chi') != chi:
            continue
        if all(p in b['_n'] for p in parole):
            out.append(b)
            if len(out) >= massimo:
                break
    return out


def messaggio(tipo, mappa='', frase='', commento='', battuta=None, autore='', versione_mod=None,
             versione_programma=None):
    righe = ['**Segnalazione CotW Italiano**' + (' da %s' % autore.strip()[:40] if autore.strip() else ''),
             '**Tipo:** %s' % tipo]
    if mappa and not mappa.startswith('Non lo so'):
        righe.append('**Mappa:** %s' % mappa)
    if frase.strip():
        righe.append('**Frase segnalata:** "%s"' % frase.strip()[:500])
    if battuta:
        righe.append('**Battuta trovata:** `%s` - %s (%s): "%s"' % (battuta['id'], battuta.get('chi', '?'),
                                                                  battuta.get('mappa', '?'), battuta.get('it', '')))
    if commento.strip():
        righe.append('**Cosa non va:** %s' % commento.strip()[:800])
    righe.append('_Mod %s - programma %s_' % (versione_mod or '?', versione_programma or '?'))
    return '\n'.join(righe)


# ---------------- invio diretto al Discord ----------------
LIMITE_ORA = 5          # segnalazioni massime per ora dallo stesso PC (contro lo spam)
LIMITE_GIORNO = 20


def _webhook():
    """L'indirizzo del canale e' in online.json, leggermente mascherato (solo per non farlo trovare ai bot
    che cercano webhook nei repository: chi legge il codice puo' ricavarlo comunque)."""
    w = rete.leggi_online().get('segnalazioni')
    if not w:
        return None
    try:
        return base64.b64decode(w.encode('ascii')).decode('utf-8')[::-1]
    except Exception:
        return None


def maschera(url):
    """Per l'autore: trasforma l'URL del webhook nella forma da mettere in online.json."""
    return base64.b64encode(url.strip()[::-1].encode('utf-8')).decode('ascii')


def _registro():
    return os.path.join(percorsi.dati_app(), 'segnalazioni_inviate.json')


def _inviate():
    try:
        return [t for t in json.load(open(_registro(), encoding='utf-8')) if t > time.time() - 86400]
    except Exception:
        return []


def invia(testo):
    """Manda la segnalazione direttamente nel canale. Errore leggibile se non si puo'."""
    fatte = _inviate()
    if len([t for t in fatte if t > time.time() - 3600]) >= LIMITE_ORA or len(fatte) >= LIMITE_GIORNO:
        raise RuntimeError('Hai gia\' mandato molte segnalazioni: grazie! Riprova piu\' tardi.')
    url = _webhook()
    if not url:
        raise RuntimeError('L\'invio diretto non e\' disponibile in questo momento.')
    rete.invia_webhook(url, testo)
    fatte.append(time.time())
    try:
        json.dump(fatte, open(_registro(), 'w', encoding='utf-8'))
    except OSError:
        pass
