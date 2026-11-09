"""Volume del quad (solo il suono che senti tu, non cambia cosa sentono gli animali).
Legge il banco audio originale dagli archivi (sola lettura) e scrive la copia modificata nella dropzone."""
import os
import re
import math
import struct
import shutil
import hashlib
from . import archivi, percorsi

INTERNO = 'sound/fmod_banks/vehicles.fmod_bankc'


def file_dropzone(dz):
    return os.path.join(dz, *INTERNO.split('/'))


# Regola del programma: tocca solo i suoi file. Se nella dropzone c'era gia' il banco dei veicoli di un'altra mod,
# lo mette da parte e lo rimette quando torni al volume originale.
def _backup():
    return os.path.join(percorsi.dati_app(), 'backup_altre_mod', 'quad', 'vehicles.fmod_bankc')


def _sha(f):
    try:
        with open(f, 'rb') as x:
            return hashlib.sha256(x.read()).hexdigest()
    except OSError:
        return None


def _fatto_da_noi(f, originale, pos):
    """Il file e' il banco originale con cambiati solo i volumi (cioe' scritto da questo programma)?"""
    s = percorsi.leggi_config().get('quad_sha')
    if s:
        return _sha(f) == s
    try:
        with open(f, 'rb') as x:
            d = bytearray(x.read())
    except OSError:
        return True
    if len(d) != len(originale):
        return False
    o = bytearray(originale)
    for p in pos:
        d[p:p + 4] = o[p:p + 4]
    return bytes(d) == originale


def _e_mio(f):
    """True se il file nella dropzone l'ha scritto il programma (o se non si sa: versioni fino alla 0.5.14)."""
    s = percorsi.leggi_config().get('quad_sha')
    return s is None or _sha(f) == s


def _eventi(d):
    """Posizioni del volume (float in dB) di ogni evento dei veicoli nel banco FMOD."""
    pos = []
    for m in re.finditer(b'IBSB', bytes(d)):
        o = m.start()
        sz = struct.unpack_from('<I', d, o + 4)[0]
        rec = d[o + 8:o + 8 + sz]
        if rec[18:34] == b'\0' * 16:          # bus radice, non e' un evento
            continue
        bo = o + 8 + sz + (sz & 1)
        if d[bo:bo + 4] != b'BUS ':
            continue
        pos.append(bo + 8 + 11)
    return pos


def volume_attuale(dz):
    """Percentuale attuale (100 = originale) letta dal file nella dropzone."""
    f = file_dropzone(dz)
    if not os.path.isfile(f):
        return 100
    try:
        d = open(f, 'rb').read()
        p = _eventi(d)
        if not p:
            return None
        db = struct.unpack_from('<f', d, p[0])[0]
        return 0 if db <= -79 else int(round(100 * 10 ** (db / 20)))
    except Exception:
        return None


def applica(gioco, dz, percentuale):
    """Crea il banco con il volume scelto. Restituisce il numero di suoni modificati."""
    perc = max(0.0, min(200.0, float(percentuale)))
    if abs(perc - 100) < 0.5:
        ripristina(dz, gioco)
        return 0
    d = archivi.leggi(gioco, INTERNO)
    if not d:
        raise RuntimeError('Non trovo i suoni dei veicoli negli archivi del gioco.')
    d = bytearray(d)
    if d[:4] != b'RIFF' or d[8:12] != b'FEV ':
        raise RuntimeError('Il banco audio del quad ha un formato diverso dal previsto (gioco aggiornato?). Non cambio niente.')
    db = -80.0 if perc <= 0.5 else 20 * math.log10(perc / 100.0)
    pos = _eventi(d)
    if not pos:
        raise RuntimeError('Nessun suono dei veicoli trovato. Non cambio niente.')
    originale = bytes(d)
    for p in pos:
        struct.pack_into('<f', d, p, db)
    out = file_dropzone(dz)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.isfile(out) and not os.path.isfile(_backup()) and not _fatto_da_noi(out, originale, pos):
        os.makedirs(os.path.dirname(_backup()), exist_ok=True)
        shutil.copy2(out, _backup())             # banco di un'altra mod: lo tengo da parte
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(d)
    os.replace(tmp, out)
    cfg = percorsi.leggi_config()
    cfg['quad_sha'] = hashlib.sha256(bytes(d)).hexdigest()
    percorsi.salva_config(cfg)
    return len(pos)


def ripristina(dz, gioco=None):
    """Torna al suono originale: toglie il banco modificato dalla dropzone (solo se e' nostro)."""
    f = file_dropzone(dz)
    mio = _e_mio(f) if os.path.isfile(f) else False
    if mio and not percorsi.leggi_config().get('quad_sha') and gioco:
        try:                                     # non si sa chi l'ha scritto: controllo che sia davvero il nostro
            d = archivi.leggi(gioco, INTERNO)
            if d:
                mio = _fatto_da_noi(f, bytes(d), _eventi(bytearray(d)))
        except Exception:
            pass
    if mio:
        os.remove(f)
    if os.path.isfile(_backup()) and not os.path.isfile(f):
        os.makedirs(os.path.dirname(f), exist_ok=True)
        shutil.move(_backup(), f)                # rimette il banco dell'altra mod
