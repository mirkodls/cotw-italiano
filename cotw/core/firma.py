"""Firma degli aggiornamenti (Ed25519).
L'autore firma versione.json e il blocco "programma" di online.json con la sua chiave PRIVATA, che sta solo sul suo PC
dentro la cassaforte cifrata dell'app amministratore. Qui dentro c'e' solo la chiave PUBBLICA: serve a controllare
che i file scaricati li abbia firmati davvero l'autore e che nessuno li abbia cambiati.
La verifica e' scritta in Python puro (RFC 8032), cosi' il programma non ha bisogno di altre librerie."""
import json
import hashlib

# Chiavi pubbliche dell'autore (esadecimale, 32 byte). Piu' di una = cambio chiave senza bloccare nessuno.
CHIAVI_PUBBLICHE = [
    '71c92d55e9385fd2c54c93b39eab21ad24698bd82f49824cfc281977f8790d76',      # Mirko Del Sette, creata il 05/11/2026
]


class FirmaNonValida(RuntimeError):
    pass


def canonico(dati):
    """I byte che si firmano: il dizionario senza il campo 'firma', con le chiavi in ordine."""
    d = {k: v for k, v in dati.items() if k != 'firma'}
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


# ---------------- Ed25519, solo verifica (RFC 8032) ----------------
_p = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _inv(x):
    return pow(x, _p - 2, _p)


def _add(P, Q):
    X1, Y1, Z1, T1 = P
    X2, Y2, Z2, T2 = Q
    A = (Y1 - X1) * (Y2 - X2) % _p
    B = (Y1 + X1) * (Y2 + X2) % _p
    C = T1 * 2 * _d * T2 % _p
    D = Z1 * 2 * Z2 % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _uguali(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _recupera_x(y, segno):
    if y >= _p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1)
    if x2 == 0:
        return None if segno else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _I % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != segno:
        x = _p - x
    return x


def _decomprimi(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, 'little')
    segno = y >> 255
    y &= (1 << 255) - 1
    x = _recupera_x(y, segno)
    if x is None:
        return None
    return (x, y, 1, x * y % _p)


_gy = 4 * _inv(5) % _p
_G = (_recupera_x(_gy, 0), _gy, 1, _recupera_x(_gy, 0) * _gy % _p)


def verifica_ed25519(pubblica, messaggio, firma):
    """True se 'firma' (64 byte) e' la firma di 'messaggio' fatta con la chiave privata di 'pubblica' (32 byte)."""
    if len(pubblica) != 32 or len(firma) != 64:
        return False
    A = _decomprimi(pubblica)
    if A is None:
        return False
    R = _decomprimi(firma[:32])
    if R is None:
        return False
    s = int.from_bytes(firma[32:], 'little')
    if s >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(firma[:32] + pubblica + messaggio).digest(), 'little') % _L
    return _uguali(_mul(s, _G), _add(R, _mul(h, A)))


# ---------------- uso nel programma ----------------
def firmato(dati, chiavi=None):
    """True se dati['firma'] e' valida per una delle chiavi pubbliche dell'autore."""
    chiavi = CHIAVI_PUBBLICHE if chiavi is None else chiavi
    try:
        f = bytes.fromhex(str(dati.get('firma', '')))
    except ValueError:
        return False
    if len(f) != 64:
        return False
    msg = canonico(dati)
    for k in chiavi:
        try:
            if verifica_ed25519(bytes.fromhex(k), msg, f):
                return True
        except ValueError:
            continue
    return False


def controlla(dati, cosa='file', chiavi=None):
    if not firmato(dati, chiavi):
        raise FirmaNonValida('Il %s scaricato non ha la firma dell\'autore (o e\' stato modificato): '
                             'per sicurezza non lo uso. Riprova piu\' tardi o avvisa l\'autore su Discord.' % cosa)
    return dati


# ---------------- solo per l'autore (serve la libreria 'cryptography') ----------------
def firma(dati, privata_hex):
    """Restituisce una copia di 'dati' con il campo 'firma'. privata_hex = seme Ed25519 di 32 byte."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    k = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(privata_hex))
    out = {kk: v for kk, v in dati.items() if kk != 'firma'}
    out['firma'] = k.sign(canonico(out)).hex()
    return out


def nuova_coppia():
    """(privata_hex, pubblica_hex) nuove."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as s
    k = Ed25519PrivateKey.generate()
    pr = k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()).hex()
    pu = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()
    return pr, pu


def pubblica_da_privata(privata_hex):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as s
    k = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(privata_hex))
    return k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()


# ---------------- percorsi sicuri nei pacchetti ----------------
def percorso_sicuro(rel):
    """True se 'rel' e' un percorso relativo normale (niente .., niente C:\\, niente / all'inizio)."""
    if not isinstance(rel, str) or not rel or '\\' in rel or ':' in rel or '\x00' in rel:
        return False
    if rel.startswith('/'):
        return False
    parti = rel.split('/')
    return all(x not in ('', '.', '..') for x in parti)
