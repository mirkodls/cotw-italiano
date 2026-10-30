"""Segnalazione errori: trova la battuta da poche parole e prepara il messaggio per Discord."""
import os
import re
import json
import unicodedata
from . import aggiornamenti

TIPI = ['Testo sbagliato (sottotitolo o menu)', 'Voce: pronuncia sbagliata', 'Voce tagliata o troppo veloce',
        'Voce mancante (si sente in inglese)', 'Voce e sottotitolo diversi', 'Crash o problema del gioco', 'Altro']


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


def cerca(testo, massimo=40):
    parole = [p for p in _norm(testo).split() if len(p) > 1]
    if not parole:
        return []
    out = []
    for b in battute():
        if all(p in b['_n'] for p in parole):
            out.append(b)
            if len(out) >= massimo:
                break
    return out


def messaggio(tipo, battuta=None, commento='', versione_mod=None, versione_programma=None, frase_libera=''):
    righe = ['**Segnalazione CotW Italiano**', '**Tipo:** %s' % tipo]
    if battuta:
        righe.append('**Battuta:** `%s` - %s (%s)' % (battuta['id'], battuta.get('chi', '?'), battuta.get('mappa', '?')))
        righe.append('**Testo:** "%s"' % battuta.get('it', ''))
    elif frase_libera:
        righe.append('**Frase (non trovata nell\'elenco):** "%s"' % frase_libera)
    if commento.strip():
        righe.append('**Commento:** %s' % commento.strip())
    righe.append('_Mod %s - programma %s_' % (versione_mod or '?', versione_programma or '?'))
    return '\n'.join(righe)
