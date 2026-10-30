"""Lettura (SOLA LETTURA) degli archivi del gioco: archives_win64\\game*.tab / .arc."""
import os
import glob
import struct

_M = 0xffffffff


def _rot(x, k):
    return ((x << k) | (x >> (32 - k))) & _M


def hashlittle(testo):
    """Hash lookup3 (Bob Jenkins) usato dal motore Apex per i percorsi dei file."""
    data = testo.encode() if isinstance(testo, str) else testo
    n = len(data)
    a = b = c = (0xdeadbeef + n) & _M
    i = 0
    while n > 12:
        a = (a + int.from_bytes(data[i:i + 4], 'little')) & _M
        b = (b + int.from_bytes(data[i + 4:i + 8], 'little')) & _M
        c = (c + int.from_bytes(data[i + 8:i + 12], 'little')) & _M
        a = (a - c) & _M; a ^= _rot(c, 4); c = (c + b) & _M
        b = (b - a) & _M; b ^= _rot(a, 6); a = (a + c) & _M
        c = (c - b) & _M; c ^= _rot(b, 8); b = (b + a) & _M
        a = (a - c) & _M; a ^= _rot(c, 16); c = (c + b) & _M
        b = (b - a) & _M; b ^= _rot(a, 19); a = (a + c) & _M
        c = (c - b) & _M; c ^= _rot(b, 4); b = (b + a) & _M
        i += 12
        n -= 12
    if n == 0:
        return c
    t = data[i:] + b'\0' * 12
    a = (a + int.from_bytes(t[0:4], 'little')) & _M
    b = (b + int.from_bytes(t[4:8], 'little')) & _M
    c = (c + int.from_bytes(t[8:12], 'little')) & _M
    c ^= b; c = (c - _rot(b, 14)) & _M
    a ^= c; a = (a - _rot(c, 11)) & _M
    b ^= a; b = (b - _rot(a, 25)) & _M
    c ^= b; c = (c - _rot(b, 16)) & _M
    a ^= c; a = (a - _rot(c, 4)) & _M
    b ^= a; b = (b - _rot(a, 14)) & _M
    c ^= b; c = (c - _rot(b, 24)) & _M
    return c


def trova(gioco, percorso_interno):
    """Cerca un file negli archivi del gioco. Restituisce (file_arc, offset, dimensione) o None."""
    h = hashlittle(percorso_interno)
    for tab in sorted(glob.glob(os.path.join(gioco, 'archives_win64', 'game*.tab'))):
        try:
            b = open(tab, 'rb').read()
        except OSError:
            continue
        for i in range(12, len(b) - 11, 12):
            hh, o, s = struct.unpack_from('<III', b, i)
            if hh == h:
                return tab[:-4] + '.arc', o, s
    return None


def leggi(gioco, percorso_interno):
    pos = trova(gioco, percorso_interno)
    if not pos:
        return None
    with open(pos[0], 'rb') as f:
        f.seek(pos[1])
        return f.read(pos[2])
