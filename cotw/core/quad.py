"""Volume del quad (solo il suono che senti tu, non cambia cosa sentono gli animali).
Legge il banco audio originale dagli archivi (sola lettura) e scrive la copia modificata nella dropzone."""
import os
import re
import math
import struct
from . import archivi

INTERNO = 'sound/fmod_banks/vehicles.fmod_bankc'


def file_dropzone(dz):
    return os.path.join(dz, *INTERNO.split('/'))


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
        ripristina(dz)
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
    for p in pos:
        struct.pack_into('<f', d, p, db)
    out = file_dropzone(dz)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(d)
    os.replace(tmp, out)
    return len(pos)


def ripristina(dz):
    """Torna al suono originale: toglie il banco modificato dalla dropzone."""
    f = file_dropzone(dz)
    if os.path.isfile(f):
        os.remove(f)
