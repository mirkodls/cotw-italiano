"""Segnalazione errori: trova la battuta da poche parole e prepara il messaggio per Discord."""
import os
import re
import json
import time
import unicodedata
from . import aggiornamenti, rete, percorsi

TIPI = ['Audio (la voce)', 'Testo (la scritta)', 'Entrambi (voce e scritta)']
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
        try:
            with open(p, encoding='utf-8') as f:
                dati = json.load(f)
        except (OSError, ValueError):
            return []                            # file rovinato/a meta': alla prossima scaricata si sistema
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
# Piu' segnalazioni arrivano, meglio e'. Se il postino e' occupato (o internet manca) la segnalazione resta
# in coda sul PC e parte da sola appena si puo'. Ognuna finisce nello storico, con il suo stato.
LIMITE_ORA = 40         # solo contro lo spam: oltre, si mette in coda (non si perde niente)


def _postino():
    """Indirizzo del postino (Cloudflare Worker) scritto in online.json del repository. Non e' un segreto:
    il segreto (il webhook del canale) sta solo nelle impostazioni del Worker."""
    return rete.postino()


def _file(nome):
    return os.path.join(percorsi.dati_app(), nome)


def _leggi(nome, vuoto):
    try:
        with open(_file(nome), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return vuoto


def _scrivi(nome, dati):
    try:
        tmp = _file(nome) + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(dati, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _file(nome))
    except OSError:
        pass


def storico():
    """[{'n','t','tipo','mappa','frase','commento','id','stato'}] dalla piu' recente.
    stato: in_coda / nuova / vista / corretta / scartata"""
    return sorted(_leggi('segnalazioni_storico.json', []), key=lambda x: -x.get('t', 0))


def _salva_storico(voce):
    st = _leggi('segnalazioni_storico.json', [])
    for i, v in enumerate(st):
        if v.get('n') == voce['n']:
            st[i] = voce
            break
    else:
        st.append(voce)
    _scrivi('segnalazioni_storico.json', st[-500:])


def _inviate_ultima_ora():
    return [t for t in _leggi('segnalazioni_inviate.json', []) if t > time.time() - 3600]


def _spedisci(voce):
    """True se partita. Occupato/senza internet -> False (resta in coda)."""
    url = _postino()
    if not url or len(_inviate_ultima_ora()) >= LIMITE_ORA:
        return False
    try:
        r = rete.invia_postino(url, voce['testo'])
    except rete.Occupato:
        return False
    except RuntimeError as e:
        if 'collegarmi' in str(e):
            return False
        raise
    fatte = _inviate_ultima_ora() + [time.time()]
    _scrivi('segnalazioni_inviate.json', fatte)
    voce['id'] = r if isinstance(r, str) else None
    voce['stato'] = 'nuova'
    return True


def invia(testo, info=None):
    """Manda la segnalazione. 'inviata' oppure 'in_coda' (parte da sola appena si puo').
    Errore solo se il postino rifiuta proprio la segnalazione."""
    voce = dict(info or {}, testo=testo, t=time.time(), n='%d' % (time.time() * 1000), stato='in_coda')
    try:
        ok = _spedisci(voce)
    finally:
        _salva_storico(voce)
    return 'inviata' if ok else 'in_coda'


def in_coda():
    return [v for v in _leggi('segnalazioni_storico.json', []) if v.get('stato') == 'in_coda']


def svuota_coda():
    """Prova a spedire quelle rimaste in coda. Restituisce quante sono partite."""
    n = 0
    for v in in_coda():
        try:
            if not _spedisci(v):
                break
        except Exception:
            continue
        _salva_storico(v)
        n += 1
    return n


def aggiorna_stati():
    """Chiede al postino lo stato delle proprie segnalazioni (corretta = spunta verde). Restituisce lo storico."""
    st = _leggi('segnalazioni_storico.json', [])
    ids = [v['id'] for v in st if v.get('id') and v.get('stato') not in ('corretta', 'scartata')]
    url = _postino()
    if ids and url:
        try:
            q = url.rstrip('/') + '/segnalazioni/stato?ids=' + ','.join(ids[-200:])
            stati = rete.leggi_json_url(q).get('stati', {})
            for v in st:
                if v.get('id') in stati:
                    v['stato'] = stati[v['id']]
            _scrivi('segnalazioni_storico.json', st)
        except Exception:
            pass
    return storico()
