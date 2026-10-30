"""Backup dei salvataggi (con nome) e azzeramento delle missioni per rigiocarle in italiano."""
import os
import re
import shutil
import time
from . import percorsi

FILE = 'missions_missiondata_adf'
_NOME = '_nome.txt'
_ORIGINE = '_origine.txt'
_SPECIALI = (_NOME, _ORIGINE)


def file_azzerato():
    return os.path.join(percorsi.cartella_risorse(), FILE)


def _cartella_backup():
    d = os.path.join(percorsi.dati_app(), 'backup_salvataggi')
    os.makedirs(d, exist_ok=True)
    return d


def cartella_backup():
    return _cartella_backup()


def backup(profilo, nome=''):
    """Copia TUTTA la cartella del profilo. 'nome' = come lo vuole chiamare l'utente. Restituisce la cartella."""
    if not os.path.isdir(profilo):
        raise RuntimeError('La cartella dei salvataggi non esiste: %s' % profilo)
    pulito = re.sub(r'[^\w\- ]+', '', nome or '').strip().replace(' ', '_')[:40]
    base = time.strftime('%Y-%m-%d_%H%M%S') + ('_' + pulito if pulito else '')
    dst = os.path.join(_cartella_backup(), base)
    n = 2
    while os.path.exists(dst):
        dst = os.path.join(_cartella_backup(), '%s_%d' % (base, n))
        n += 1
    shutil.copytree(profilo, dst)
    with open(os.path.join(dst, _ORIGINE), 'w', encoding='utf-8') as f:
        f.write(profilo)
    with open(os.path.join(dst, _NOME), 'w', encoding='utf-8') as f:
        f.write(nome.strip() or 'Backup')
    return dst


def elenco_backup():
    d = _cartella_backup()
    out = []
    for n in sorted(os.listdir(d), reverse=True):
        p = os.path.join(d, n)
        if not os.path.isdir(p):
            continue
        def leggi(f, dflt=''):
            try:
                return open(os.path.join(p, f), encoding='utf-8').read().strip()
            except OSError:
                return dflt
        data = n[:17].replace('_', ' ')
        try:
            data = time.strftime('%d/%m/%Y %H:%M', time.strptime(n[:17], '%Y-%m-%d_%H%M%S'))
        except ValueError:
            pass
        out.append({'cartella': p, 'nome': leggi(_NOME, n), 'data': data, 'origine': leggi(_ORIGINE)})
    return out


def rinomina(cartella, nuovo_nome):
    with open(os.path.join(cartella, _NOME), 'w', encoding='utf-8') as f:
        f.write(nuovo_nome.strip() or 'Backup')


def elimina(cartella):
    if os.path.normcase(os.path.dirname(os.path.normpath(cartella))) != os.path.normcase(_cartella_backup()):
        raise RuntimeError('Questa non e\' una cartella di backup del programma.')
    shutil.rmtree(cartella)


def azzera(profilo):
    src = file_azzerato()
    if not os.path.isfile(src):
        raise RuntimeError('Manca il file delle missioni azzerate nella cartella "risorse" del programma.')
    if not os.path.isfile(os.path.join(profilo, FILE)):
        raise RuntimeError('In questa cartella non trovo il file delle missioni: e\' la cartella giusta?')
    b = backup(profilo, 'Prima di azzerare le missioni')
    shutil.copyfile(src, os.path.join(profilo, FILE))
    return b


def ripristina(cartella_backup, profilo=None):
    """Rimette i file del backup nella cartella del profilo (prima salva lo stato attuale in un altro backup)."""
    if profilo is None:
        profilo = open(os.path.join(cartella_backup, _ORIGINE), encoding='utf-8').read().strip()
    if not os.path.isdir(profilo):
        raise RuntimeError('La cartella dei salvataggi originale non esiste piu\': %s' % profilo)
    backup(profilo, 'Automatico prima del ripristino')
    for n in os.listdir(cartella_backup):
        if n in _SPECIALI:
            continue
        s = os.path.join(cartella_backup, n)
        d = os.path.join(profilo, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    return profilo
