"""Aggiornamento del programma stesso (l'exe).
La versione nuova e' scritta in online.json del repository (la aggiorna da sola la costruzione automatica su GitHub):
  "programma": {"versione": "0.4.0", "url": "https://github.com/.../CotW_Italiano_0.4.0.zip", "sha256": "...",
                "dimensione": 123, "novita": ["..."]}
Aggiornare: scarica lo zip in %APPDATA%\\CotW Italiano\\aggiornamento, controlla l'impronta, lo estrae, poi un piccolo
script aspetta che il programma si chiuda, copia i file nuovi sopra i vecchi e lo riapre.
Impostazioni, backup e chiave stanno in %APPDATA%: non vengono toccati."""
import os
import sys
import shutil
import zipfile
import subprocess
from . import percorsi, rete
from .. import VERSIONE

NOME_EXE = 'CotW Italiano.exe'


def _num(v):
    try:
        return tuple(int(x) for x in str(v).split('.'))
    except ValueError:
        return (0,)


def cartella_exe():
    """Cartella dell'exe se il programma gira come exe, altrimenti None (avviato da Python: niente auto-aggiornamento)."""
    for p in (sys.executable, sys.argv[0] if sys.argv else ''):
        if p and os.path.basename(p).lower() == NOME_EXE.lower() and os.path.isfile(p):
            return os.path.dirname(os.path.abspath(p))
    return None


def disponibile(online):
    """Dati della versione nuova se e' piu' recente di questa, altrimenti None."""
    p = (online or {}).get('programma') or {}
    if p.get('versione') and p.get('url') and _num(p['versione']) > _num(VERSIONE):
        return p
    return None


def prepara(info, avanzamento=None, fermati=None):
    """Scarica e controlla la versione nuova. Restituisce la cartella con i file nuovi (quella che contiene l'exe)."""
    base = os.path.join(percorsi.dati_app(), 'aggiornamento')
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base, exist_ok=True)
    zp = os.path.join(base, 'programma.zip')
    rete.scarica(info['url'], zp, info.get('sha256'),
                 (lambda a, b: avanzamento(a >> 20, max(b, info.get('dimensione', 0)) >> 20 or 1, 'Scarico (MB)'))
                 if avanzamento else None, fermati)
    dest = os.path.join(base, 'nuova')
    with zipfile.ZipFile(zp) as z:
        for m in z.namelist():                       # niente percorsi strani fuori dalla cartella
            if m.startswith(('/', '\\')) or '..' in m.replace('\\', '/').split('/'):
                raise RuntimeError('Pacchetto del programma non valido.')
        z.extractall(dest)
    os.remove(zp)
    for cart, _, files in os.walk(dest):
        if NOME_EXE in files:
            return cart
    raise RuntimeError('Nel pacchetto scaricato manca %s.' % NOME_EXE)


def installa_e_riavvia(nuova, argomenti=None):
    """Avvia lo script che sostituisce i file appena il programma si chiude. Dopo questa chiamata il programma va chiuso."""
    app = cartella_exe()
    if not app:
        raise RuntimeError('Il programma non e\' avviato come exe: aggiorna a mano.')
    script = os.path.join(percorsi.dati_app(), 'aggiornamento', 'aggiorna.cmd')
    righe = ['@echo off', 'chcp 65001 >nul', 'set "PIDV=%d"' % os.getpid(), ':attendi',
             'tasklist /FI "PID eq %PIDV%" /NH | find "%PIDV%" >nul',
             'if errorlevel 1 goto copia',
             'ping -n 2 127.0.0.1 >nul',
             'goto attendi',
             ':copia',
             'robocopy "%s" "%s" /E /R:10 /W:1 /NFL /NDL /NJH /NJS /NP >nul' % (nuova, app),
             'start "" "%s"%s' % (os.path.join(app, NOME_EXE), ''.join(' "%s"' % a.replace('%', '%%').replace('"', '')
                                                                        for a in (argomenti or [])))]
    with open(script, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(righe) + '\r\n')
    # finestra nascosta + gruppo separato: lo script sopravvive alla chiusura del programma
    subprocess.Popen(['cmd', '/c', script], creationflags=0x08000000 | 0x00000200, close_fds=True)
