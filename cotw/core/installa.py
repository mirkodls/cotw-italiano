"""Installa / rimuove i componenti della mod (Testo, Audio) nella dropzone.
Regola: il programma tocca SOLO i file che installa lui. Se al posto di un suo file c'era un file
di un'altra mod, ne fa un backup e lo rimette quando il componente viene rimosso."""
import os
import filecmp
import json
import shutil
import time
from . import percorsi

COMPONENTI = {
    'testo': {'nome': 'Testo italiano', 'descrizione': 'Sottotitoli, menu, missioni e interfaccia in italiano',
              'cartella_pacchetto': 'mod ita testo'},
    'audio': {'nome': 'Doppiaggio italiano', 'descrizione': 'Le voci italiane di tutti i personaggi',
              'cartella_pacchetto': 'mod audio ita'},
}


# ---------------- stato (cosa ha installato il programma) ----------------
def _file_stato():
    return os.path.join(percorsi.dati_app(), 'stato.json')


def leggi_stato():
    try:
        with open(_file_stato(), encoding='utf-8') as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault('componenti', {})
    return s


def salva_stato(s):
    tmp = _file_stato() + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False)
    os.replace(tmp, _file_stato())


def _cartella_backup(comp):
    d = os.path.join(percorsi.dati_app(), 'backup_altre_mod', comp)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------- pacchetti ----------------
def trova_pacchetto(sorgente, comp):
    """Dentro la cartella sorgente (es. Desktop\\mod italiano\\MOD) trova la 'dropzone' del componente."""
    if not sorgente:
        return None
    cand = [os.path.join(sorgente, COMPONENTI[comp]['cartella_pacchetto'], 'dropzone'),
            os.path.join(sorgente, 'dropzone')]
    for c in cand:
        if os.path.isdir(c) and _file_del_componente(c, comp):
            return c
    return None


def _file_del_componente(radice, comp):
    """Elenco dei file (percorso relativo con /) che appartengono al componente dentro una cartella dropzone."""
    out = []
    for cart, _, files in os.walk(radice):
        for n in files:
            rel = os.path.relpath(os.path.join(cart, n), radice).replace(os.sep, '/')
            low = rel.lower()
            if comp == 'audio' and low.startswith('sound/dialogue/') and low.endswith('.wavc'):
                out.append(rel)
            elif comp == 'testo' and low in ('settings/hp_settings/string_ids.stringlookup', 'ui/ui_localization.stringlookup'):
                out.append(rel)
    return sorted(out)


def info_pacchetto(sorgente):
    """Per ogni componente: quanti file e quanti MB ci sono nel pacchetto."""
    r = {}
    for comp in COMPONENTI:
        p = trova_pacchetto(sorgente, comp)
        if not p:
            r[comp] = None
            continue
        fl = _file_del_componente(p, comp)
        mb = sum(os.path.getsize(os.path.join(p, *f.split('/'))) for f in fl) / 1e6
        r[comp] = {'cartella': p, 'file': len(fl), 'mb': mb}
    return r


# ---------------- riconoscere una mod gia' presente ----------------
def riconosci_esistenti(sorgente, dz):
    """Se nella dropzone ci sono gia' TUTTI i file di un componente, identici a quelli del pacchetto
    (es. installati prima con i .bat), li registra come installati senza ricopiare niente."""
    if not sorgente or not dz or not os.path.isdir(dz):
        return []
    stato = leggi_stato()
    trovati = []
    for comp in COMPONENTI:
        if stato['componenti'].get(comp, {}).get('file'):
            continue
        pac = trova_pacchetto(sorgente, comp)
        if not pac:
            continue
        fl = _file_del_componente(pac, comp)
        presenti = {}
        for rel in fl:
            src = os.path.join(pac, *rel.split('/'))
            dst = os.path.join(dz, *rel.split('/'))
            try:
                if os.path.getsize(dst) != os.path.getsize(src):
                    break
            except OSError:
                break
            presenti[rel] = os.path.getsize(src)
        if fl and len(presenti) == len(fl):
            stato['componenti'][comp] = {'file': presenti, 'backup': {}, 'installato_il': 'prima del programma',
                                         'sorgente': sorgente, 'riconosciuto': True}
            trovati.append(comp)
    if trovati:
        salva_stato(stato)
    return trovati


# ---------------- stato installazione ----------------
def stato_componente(dz, comp, sorgente=None):
    """'installato', 'parziale', 'presente' (file della mod non installati dal programma), 'non installato'."""
    s = leggi_stato()['componenti'].get(comp)
    if not s or not s.get('file'):
        pac = trova_pacchetto(sorgente, comp) if sorgente else None
        if pac and dz:
            n = sum(1 for rel in _file_del_componente(pac, comp) if os.path.isfile(os.path.join(dz, *rel.split('/'))))
            if n:
                return 'presente', n
        return 'non installato', 0
    tot = len(s['file'])
    presenti = sum(1 for f in s['file'] if os.path.isfile(os.path.join(dz, *f.split('/'))))
    if presenti == tot:
        return 'installato', presenti
    if presenti == 0:
        return 'non installato', 0
    return 'parziale', presenti


def _miei_file(stato, escluso=None):
    m = set()
    for c, v in stato['componenti'].items():
        if c != escluso:
            m.update(v.get('file', {}))
    return m


def _uguali(a, b):
    """Confronto completo, byte per byte."""
    try:
        return os.path.getsize(a) == os.path.getsize(b) and filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def installa(comp, sorgente, dz, avanzamento=None, fermati=None, versione=None):
    """Copia i file del componente nella dropzone. avanzamento(fatti, totale, testo).
    Restituisce (file del componente, file copiati davvero)."""
    pac = trova_pacchetto(sorgente, comp)
    if not pac:
        raise RuntimeError('Nel pacchetto non trovo i file di "%s".' % COMPONENTI[comp]['nome'])
    fl = _file_del_componente(pac, comp)
    stato = leggi_stato()
    vecchio = stato['componenti'].get(comp, {})
    gia_miei = set(vecchio.get('file', {}))
    backup = dict(vecchio.get('backup', {}))
    altri_miei = _miei_file(stato, escluso=comp)
    bdir = _cartella_backup(comp)
    registrati = {}
    copiati = 0
    tot = len(fl)
    for i, rel in enumerate(fl):
        if fermati and fermati():
            break
        src = os.path.join(pac, *rel.split('/'))
        dst = os.path.join(dz, *rel.split('/'))
        if os.path.isfile(dst) and rel not in gia_miei and rel not in altri_miei and rel not in backup:
            # c'era un file non nostro: se e' uguale al nostro lo consideriamo nostro, altrimenti backup
            if not _uguali(src, dst):
                b = os.path.join(bdir, *rel.split('/'))
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(dst, b)
                backup[rel] = b
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not (os.path.isfile(dst) and _uguali(src, dst)):
            shutil.copyfile(src, dst)
            copiati += 1
        registrati[rel] = os.path.getsize(src)
        if avanzamento and (i % 25 == 0 or i == tot - 1):
            avanzamento(i + 1, tot, rel)
    # i file nostri della versione precedente che non ci sono piu' nel pacchetto vanno tolti
    for rel in gia_miei - set(registrati):
        if fermati and fermati():
            break
        _togli(dz, rel, backup)
    stato['componenti'][comp] = {'file': registrati, 'backup': backup, 'versione': versione,
                                 'installato_il': time.strftime('%Y-%m-%d %H:%M'), 'sorgente': sorgente}
    salva_stato(stato)
    return len(registrati), copiati


def _togli(dz, rel, backup):
    dst = os.path.join(dz, *rel.split('/'))
    if os.path.isfile(dst):
        os.remove(dst)
    b = backup.pop(rel, None)
    if b and os.path.isfile(b):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(b, dst)                      # rimette il file dell'altra mod
    # cartelle rimaste vuote
    d = os.path.dirname(dst)
    while os.path.normcase(d) != os.path.normcase(dz) and os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
        d = os.path.dirname(d)


def rimuovi(comp, dz, avanzamento=None):
    stato = leggi_stato()
    v = stato['componenti'].get(comp)
    if not v:
        return 0
    fl = list(v.get('file', {}))
    backup = dict(v.get('backup', {}))
    for i, rel in enumerate(fl):
        _togli(dz, rel, backup)
        if avanzamento and (i % 25 == 0 or i == len(fl) - 1):
            avanzamento(i + 1, len(fl), rel)
    stato['componenti'].pop(comp, None)
    salva_stato(stato)
    return len(fl)


# ---------------- attiva / disattiva tutte le mod ----------------
def disattiva_mod(gioco):
    on, off = os.path.join(gioco, 'dropzone'), os.path.join(gioco, 'dropzone_off')
    if not os.path.isdir(on):
        return
    if os.path.exists(off):
        raise RuntimeError('Esiste gia\' una cartella "dropzone_off" nel gioco: rinominala o spostala, poi riprova.')
    os.rename(on, off)


def attiva_mod(gioco):
    on, off = os.path.join(gioco, 'dropzone'), os.path.join(gioco, 'dropzone_off')
    if os.path.isdir(on):
        return
    if not os.path.isdir(off):
        os.makedirs(on)
        return
    os.rename(off, on)
