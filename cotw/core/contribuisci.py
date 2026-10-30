"""Contribuisci: chi vuole aiuta a doppiare le battute nuove con il SUO account ElevenLabs (gratuito va benissimo).
- La chiave si usa SOLO su questo PC (va solo a api.elevenlabs.io). Se l'utente vuole, si salva cifrata da Windows.
- Le battute da fare le prepara l'autore (da_doppiare_<versione>.json nella Release): testo con le pronunce gia'
  sistemate, voce, frase prima/dopo, velocita'. Qui si manda a ElevenLabs esattamente quello.
- Al postino arrivano SOLO gli audio (mp3), una battuta alla volta, appena fatti (se si interrompe non si perde niente)."""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from . import percorsi, rete, aggiornamenti

LINK_ACCOUNT = 'https://elevenlabs.io/app/sign-up'
LINK_CHIAVE = 'https://elevenlabs.io/app/settings/api-keys'
MARGINE = 300            # crediti che lasciamo sempre liberi sull'account di chi aiuta
MAX_PER_GIRO = 60


class CreditiFiniti(Exception):
    pass


def _api():
    return os.environ.get('COTW_URL_ELEVEN') or 'https://api.elevenlabs.io/v1'


# ---------------- chiave (cifrata con Windows, solo per questo utente di questo PC) ----------------
def _file_chiave():
    return os.path.join(percorsi.dati_app(), 'chiave_elevenlabs.bin')


def _dpapi(dati, cifra):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(dati, len(dati))
    ingresso, uscita = BLOB(len(dati), buf), BLOB()
    f = ctypes.windll.crypt32.CryptProtectData if cifra else ctypes.windll.crypt32.CryptUnprotectData
    if not f(ctypes.byref(ingresso), None, None, None, None, 0, ctypes.byref(uscita)):
        raise OSError('cifratura di Windows non riuscita')
    try:
        return ctypes.string_at(uscita.pbData, uscita.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(uscita.pbData)


def salva_chiave(chiave):
    """True se salvata. Su Windows SOLO cifrata: se la cifratura non riesce non si salva niente."""
    dati = chiave.strip().encode('utf-8')
    try:
        if sys.platform == 'win32':
            dati = b'DPAPI' + _dpapi(dati, True)
        with open(_file_chiave(), 'wb') as f:
            f.write(dati)
        return True
    except Exception:
        return False


def leggi_chiave():
    try:
        dati = open(_file_chiave(), 'rb').read()
        if dati.startswith(b'DPAPI'):
            dati = _dpapi(dati[5:], False)
        return dati.decode('utf-8').strip()
    except Exception:
        return ''


def dimentica_chiave():
    try:
        os.remove(_file_chiave())
    except OSError:
        pass


# ---------------- ElevenLabs (dal PC di chi aiuta) ----------------
def _richiesta(metodo, url, chiave, corpo=None, timeout=120):
    h = {'xi-api-key': chiave, 'User-Agent': 'CotW-Italiano'}
    dati = None
    if corpo is not None:
        h['Content-Type'] = 'application/json'
        dati = json.dumps(corpo).encode('utf-8')
    return urllib.request.urlopen(urllib.request.Request(url, data=dati, headers=h, method=metodo), timeout=timeout)


def _errore_el(e):
    try:
        t = e.read().decode('utf-8', 'replace')
    except Exception:
        t = ''
    return e.code, t


def crediti(chiave):
    """Crediti rimasti sull'account. None se la chiave non ha il permesso di leggerli (si puo' usare lo stesso)."""
    try:
        with _richiesta('GET', _api() + '/user/subscription', chiave, timeout=30) as r:
            s = json.loads(r.read().decode('utf-8'))
            return max(0, int(s['character_limit']) - int(s['character_count']))
    except urllib.error.HTTPError as e:
        cod, t = _errore_el(e)
        if cod == 401 and 'missing_permissions' in t:
            return None
        if cod in (401, 403):
            raise RuntimeError('La chiave non e\' valida. Controlla di averla copiata tutta.')
        raise RuntimeError('ElevenLabs ha risposto con un errore (%d).' % cod)
    except urllib.error.URLError:
        raise RuntimeError('Non riesco a collegarmi a ElevenLabs: controlla internet.')


def genera(chiave, doc, b):
    """Una battuta -> mp3 (bytes). Stesse impostazioni dell'autore."""
    corpo = {'text': b['testo'], 'model_id': doc['modello'], 'language_code': 'it',
             'voice_settings': dict(doc['impostazioni'], speed=b.get('vel', 1.0))}
    if b.get('prec'):
        corpo['previous_text'] = b['prec']
    if b.get('succ'):
        corpo['next_text'] = b['succ']
    url = '%s/text-to-speech/%s?output_format=%s' % (_api(), b['voce'], doc.get('formato', 'mp3_44100_128'))
    for tentativo in range(4):
        try:
            with _richiesta('POST', url, chiave, corpo) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            cod, t = _errore_el(e)
            if 'quota' in t.lower() or 'credits' in t.lower():
                raise CreditiFiniti()
            if cod == 429 or cod >= 500:
                time.sleep(5 * (tentativo + 1))
                continue
            if cod in (401, 403):
                raise RuntimeError('ElevenLabs non accetta la chiave (%d): serve il permesso "Text to Speech".' % cod)
            raise RuntimeError('ElevenLabs ha risposto con un errore (%d): %s' % (cod, t[:200]))
        except urllib.error.URLError:
            time.sleep(5 * (tentativo + 1))
    raise RuntimeError('ElevenLabs non risponde: riprova piu\' tardi.')


# ---------------- elenco battute e postino ----------------
def elenco(manifest):
    """Scarica (se serve) l'elenco delle battute da doppiare della versione online. None se non ce ne sono."""
    d = (manifest or {}).get('da_doppiare')
    if not d:
        return None
    dest = os.path.join(aggiornamenti.cartella_cache(), 'da_doppiare.json')
    rete.scarica(rete.url_pacchetto(d['tag'], d['nome']), dest, d.get('sha256'))
    return json.load(open(dest, encoding='utf-8'))


def _postino():
    u = rete.leggi_online().get('postino')
    if not (isinstance(u, str) and u.startswith(('https://', 'http://127.0.0.1'))):
        raise RuntimeError('Il servizio dei contributi non e\' disponibile in questo momento.')
    return u.rstrip('/')


def _post(url, corpo=None, dati=None, timeout=30):
    h = dict(rete._UA)
    if corpo is not None:
        dati = json.dumps(corpo).encode('utf-8')
        h['Content-Type'] = 'application/json'
    else:
        h['Content-Type'] = 'audio/mpeg'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=dati, headers=h, method='POST'), timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RuntimeError('Troppe richieste in poco tempo: riprova tra un po\'.')
        raise RuntimeError('Il servizio dei contributi ha risposto con un errore (%d).' % e.code)
    except urllib.error.URLError:
        raise RuntimeError('Non riesco a collegarmi al servizio dei contributi: controlla internet.')


def stato():
    """{'totale','fatte','prenotate','libere'} dal postino, oppure None."""
    try:
        with urllib.request.urlopen(urllib.request.Request(_postino() + '/contributi/stato', headers=rete._UA),
                                    timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def doppia(chiave, doc, chi, avanzamento=None, fermati=None):
    """Prenota, genera e consegna. Restituisce (fatte, motivo_fine)."""
    post = _postino()
    per_id = {b['id']: b for b in doc['battute']}
    cr = crediti(chiave)
    medio = max(1, sum(len(b['testo']) for b in doc['battute']) // max(1, len(doc['battute'])))
    quante = MAX_PER_GIRO if cr is None else min(MAX_PER_GIRO, max(0, (cr - MARGINE) // medio))
    if quante < 1:
        return 0, 'Sul tuo account non ci sono abbastanza crediti questo mese.'
    pren = _post(post + '/contributi/prenota', {'chi': chi, 'quante': quante})
    ids = [i for i in pren.get('ids', []) if i in per_id]
    if not ids:
        return 0, 'In questo momento tutte le battute sono gia\' fatte o prenotate da altri. Grazie lo stesso!'
    fatte, spesi, motivo, consegnate = 0, 0, '', set()
    for n, i in enumerate(ids):
        if fermati and fermati():
            motivo = 'Interrotto da te.'
            break
        b = per_id[i]
        if cr is not None and spesi + len(b['testo']) > cr - MARGINE:
            motivo = 'Crediti del mese quasi finiti: mi fermo qui.'
            break
        if avanzamento:
            avanzamento(n, len(ids), '%s: %s' % (b.get('chi', ''), b.get('sottotitolo', b['testo'])[:60]))
        try:
            mp3 = genera(chiave, doc, b)
        except CreditiFiniti:
            motivo = 'Crediti del mese finiti: mi fermo qui.'
            break
        spesi += len(b['testo'])
        _post('%s/contributi/audio?%s' % (post, urllib.parse.urlencode({'id': i, 'chi': chi})), dati=mp3, timeout=60)
        fatte += 1
        consegnate.add(i)
    if avanzamento:
        avanzamento(len(ids), len(ids), 'Fatto')
    resto = [i for i in ids if i not in consegnate]
    if resto:                                   # le battute non fatte tornano subito libere per gli altri
        try:
            _post(post + '/contributi/libera', {'chi': chi, 'ids': resto})
        except Exception:
            pass
    if fatte:
        try:
            _post(post + '/contributi/fine', {'chi': chi, 'fatte': fatte})
        except Exception:
            pass
        conta = percorsi.leggi_config()
        conta['battute_doppiate'] = conta.get('battute_doppiate', 0) + fatte
        percorsi.salva_config(conta)
    return fatte, motivo
