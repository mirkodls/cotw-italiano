"""Scaricamento da GitHub (Release del repository mirkodls/cotw-italiano).
Tutto passa da qui: elenco versioni (versione.json) e pacchetti .zip. Verifica sempre l'impronta SHA-256."""
import os
import json
import hashlib
import urllib.request

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


def leggi_manifest(timeout=20):
    """Scarica versione.json. Restituisce il dizionario, oppure None se non c'e' ancora nessuna versione pubblicata."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url_manifest(), headers=_UA), timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError('GitHub ha risposto con un errore (%d). Riprova piu\' tardi.' % e.code)
    except urllib.error.URLError:
        raise RuntimeError('Non riesco a collegarmi a GitHub: controlla la connessione a internet.')


def scarica(url, destinazione, sha_atteso=None, avanzamento=None, fermati=None):
    """Scarica in destinazione (prima in .part). avanzamento(byte_fatti, byte_totali). Controlla lo SHA-256."""
    os.makedirs(os.path.dirname(destinazione), exist_ok=True)
    if sha_atteso and os.path.isfile(destinazione) and sha256_file(destinazione) == sha_atteso:
        return destinazione                      # gia' scaricato e integro
    part = destinazione + '.part'
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=60) as r, open(part, 'wb') as f:
            tot = int(r.headers.get('Content-Length') or 0)
            fatti = 0
            while True:
                if fermati and fermati():
                    raise RuntimeError('Scaricamento interrotto.')
                b = r.read(1 << 18)
                if not b:
                    break
                f.write(b)
                h.update(b)
                fatti += len(b)
                if avanzamento:
                    avanzamento(fatti, tot)
    except urllib.error.HTTPError as e:
        raise RuntimeError('Il file non si scarica (errore %d): %s' % (e.code, url))
    except urllib.error.URLError:
        raise RuntimeError('Connessione interrotta durante lo scaricamento. Riprova.')
    if sha_atteso and h.hexdigest() != sha_atteso:
        os.remove(part)
        raise RuntimeError('Il file scaricato e\' rovinato (controllo di integrita\' fallito). Riprova.')
    os.replace(part, destinazione)
    return destinazione


def url_online():
    """Piccolo file di impostazioni nel repository (si cambia senza fare una nuova versione del programma)."""
    return os.environ.get('COTW_URL_ONLINE') or 'https://raw.githubusercontent.com/%s/main/online.json' % REPO


def leggi_online(timeout=15):
    try:
        with urllib.request.urlopen(urllib.request.Request(url_online(), headers=_UA), timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return {}


def invia_postino(url, testo, timeout=25):
    """Manda la segnalazione al 'postino' (Cloudflare Worker), che la gira nel canale Discord.
    L'indirizzo del canale lo conosce solo il postino: nel programma non c'e'."""
    corpo = json.dumps({'testo': testo[:1900]}).encode('utf-8')
    h = dict(_UA)
    h['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=corpo, headers=h, method='POST'), timeout=timeout):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RuntimeError('Troppe segnalazioni in poco tempo: riprova tra un po\'.')
        raise RuntimeError('Il servizio delle segnalazioni ha risposto con un errore (%d).' % e.code)
    except urllib.error.URLError:
        raise RuntimeError('Non riesco a collegarmi al servizio delle segnalazioni: controlla la connessione a internet.')
