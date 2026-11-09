"""Scaricamento da GitHub (Release del repository mirkodls/cotw-italiano).
Tutto passa da qui: elenco versioni (versione.json) e pacchetti .zip. Verifica sempre l'impronta SHA-256
e la firma dell'autore su versione.json (cotw/core/firma.py)."""
import os
import ssl
import json
import time
import hashlib
import http.client
import urllib.error
import urllib.request
from . import firma


def _contesto_ssl():
    """Certificati di Windows + quelli di certifi (inclusi nel programma).
    Python, a differenza del browser, non scarica da solo i certificati radice che mancano a Windows: su alcuni PC
    github.com falliva con "unable to get local issuer certificate". Con certifi in piu' la verifica funziona lo stesso
    (resta sempre ATTIVA: niente scorciatoie)."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


CONTESTO_SSL = _contesto_ssl()
urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=CONTESTO_SSL)))

REPO = 'mirkodls/cotw-italiano'
PAGINA = 'https://github.com/%s' % REPO
DISCORD = 'https://discord.gg/xPgHkstTDn'
KOFI = 'https://ko-fi.com/mirkodls'
_UA = {'User-Agent': 'CotW-Italiano (https://github.com/mirkodls/cotw-italiano)'}


def url_manifest():
    return os.environ.get('COTW_URL_MANIFEST') or '%s/releases/latest/download/versione.json' % PAGINA


def url_pacchetto(tag, nome):
    base = os.environ.get('COTW_URL_ASSET') or '%s/releases/download/' % PAGINA
    return '%s%s/%s' % (base, tag, nome)


def sha256_file(percorso, blocco=1 << 20):
    h = hashlib.sha256()
    with open(percorso, 'rb') as f:
        for b in iter(lambda: f.read(blocco), b''):
            h.update(b)
    return h.hexdigest()


def _nome_file_ok(n):
    return isinstance(n, str) and firma.percorso_sicuro(n) and '/' not in n


def controlla_manifest(m):
    """versione.json deve avere la firma dell'autore e solo percorsi/nomi di file normali (niente .. o C:)."""
    firma.controlla(m, 'file delle versioni (versione.json)')
    for comp in (m.get('componenti') or {}).values():
        for rel in (comp.get('file') or {}):
            if not firma.percorso_sicuro(rel):
                raise firma.FirmaNonValida('Nella versione online c\'e\' un file con un percorso non valido: %s' % rel)
        for p in comp.get('pacchetti') or []:
            if not _nome_file_ok(p.get('nome')) or not _nome_file_ok(p.get('tag')):
                raise firma.FirmaNonValida('Nella versione online c\'e\' un pacchetto con un nome non valido.')
            if isinstance(p.get('contiene'), list) and not all(firma.percorso_sicuro(r) for r in p['contiene']):
                raise firma.FirmaNonValida('Nella versione online c\'e\' un pacchetto con percorsi non validi.')
    for k, v in m.items():
        if isinstance(v, dict) and 'nome' in v and 'tag' in v:
            if not _nome_file_ok(v.get('nome')) or not _nome_file_ok(v.get('tag')):
                raise firma.FirmaNonValida('Nella versione online c\'e\' un file con un nome non valido (%s).' % k)
    return m


def leggi_manifest(timeout=20):
    """Scarica versione.json e controlla la firma dell'autore.
    Restituisce il dizionario, oppure None se non c'e' ancora nessuna versione pubblicata."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url_manifest(), headers=_UA), timeout=timeout) as r:
            return controlla_manifest(json.loads(r.read().decode('utf-8')))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError('GitHub ha risposto con un errore (%d). Riprova piu\' tardi.' % e.code)
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        raise RuntimeError('Non riesco a collegarmi a GitHub: controlla la connessione a internet.')
    except ValueError:
        raise RuntimeError('GitHub ha mandato un file delle versioni rovinato. Riprova tra qualche minuto.')


def scarica(url, destinazione, sha_atteso=None, avanzamento=None, fermati=None, tentativi=4):
    """Scarica in destinazione (prima in .part). avanzamento(byte_fatti, byte_totali). Controlla lo SHA-256.
    Se la connessione cade riprende da dove era arrivato (fino a 'tentativi' volte, anche alla volta dopo)."""
    os.makedirs(os.path.dirname(destinazione), exist_ok=True)
    if sha_atteso and os.path.isfile(destinazione) and sha256_file(destinazione) == sha_atteso:
        return destinazione                      # gia' scaricato e integro
    part = destinazione + '.part'
    ultimo = None
    for n in range(tentativi):
        try:
            _scarica_pezzo(url, part, avanzamento, fermati)
            break
        except _Interrotto:
            raise RuntimeError('Scaricamento interrotto.')
        except urllib.error.HTTPError as e:
            if e.code == 416:                    # il pezzo salvato non va bene (file cambiato online): da capo
                _togli(part)
                ultimo = e
                continue
            raise RuntimeError('Il file non si scarica (errore %d): %s' % (e.code, url))
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            ultimo = e
            time.sleep(min(2 * (n + 1), 6))
    else:
        raise RuntimeError('Connessione interrotta durante lo scaricamento (%s). Riprova: ripartira\' da dove si e\' '
                           'fermato.' % type(ultimo).__name__)
    if sha_atteso and sha256_file(part) != sha_atteso:
        _togli(part)
        raise RuntimeError('Il file scaricato e\' rovinato (controllo di integrita\' fallito). Riprova.')
    os.replace(part, destinazione)
    return destinazione


class _Interrotto(Exception):
    pass


def _togli(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _scarica_pezzo(url, part, avanzamento, fermati):
    """Scarica (o continua a scaricare) in part. Usa Range se c'e' gia' un pezzo."""
    gia = os.path.getsize(part) if os.path.isfile(part) else 0
    h = dict(_UA)
    if gia:
        h['Range'] = 'bytes=%d-' % gia
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        if gia and r.status != 206:              # il server non riprende: da capo
            gia = 0
        tot = int(r.headers.get('Content-Length') or 0) + gia
        fatti = gia
        with open(part, 'ab' if gia else 'wb') as f:
            while True:
                if fermati and fermati():
                    raise _Interrotto()
                b = r.read(1 << 18)
                if not b:
                    break
                f.write(b)
                fatti += len(b)
                if avanzamento:
                    avanzamento(fatti, tot)
        if tot > gia and fatti < tot:
            raise http.client.IncompleteRead(b'', tot - fatti)


def url_online():
    """Piccolo file di impostazioni nel repository (si cambia senza fare una nuova versione del programma)."""
    return os.environ.get('COTW_URL_ONLINE') or 'https://raw.githubusercontent.com/%s/main/online.json' % REPO


def leggi_online(timeout=15):
    try:
        with urllib.request.urlopen(urllib.request.Request(url_online(), headers=_UA), timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return {}


def postino(online=None):
    """Indirizzo del postino (Cloudflare Worker). Dalla 0.5.8 si legge dal blocco "servizi" di online.json, che deve
    avere la firma dell'autore: cosi' nessuno puo' dirottare segnalazioni e contributi su un altro server.
    None se manca o non e' firmato (le segnalazioni restano in coda sul PC)."""
    s = (online if online is not None else leggi_online()).get('servizi')
    if not isinstance(s, dict) or not firma.firmato(s):
        return None
    u = s.get('postino')
    return u.rstrip('/') if isinstance(u, str) and u.startswith(('https://', 'http://127.0.0.1')) else None


class Occupato(RuntimeError):
    """Il postino ha ricevuto troppe segnalazioni in poco tempo: si riprova piu' tardi da soli."""


def invia_postino(url, testo, timeout=25):
    """Manda la segnalazione al 'postino' (Cloudflare Worker), che la gira nel canale Discord.
    L'indirizzo del canale lo conosce solo il postino: nel programma non c'e'."""
    corpo = json.dumps({'testo': testo[:1900]}).encode('utf-8')
    h = dict(_UA)
    h['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=corpo, headers=h, method='POST'), timeout=timeout) as r:
            try:
                return json.loads(r.read().decode('utf-8') or '{}').get('id') or True
            except Exception:
                return True
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise Occupato()
        raise RuntimeError('Il servizio delle segnalazioni ha risposto con un errore (%d).' % e.code)
    except urllib.error.URLError:
        raise RuntimeError('Non riesco a collegarmi al servizio delle segnalazioni: controlla la connessione a internet.')


def leggi_json_url(url, timeout=15):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8') or '{}')
