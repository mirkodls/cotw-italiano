"""Aggiornamento del programma stesso (l'exe).
La versione nuova e' scritta in online.json del repository (la aggiorna da sola la costruzione automatica su GitHub,
poi l'autore la FIRMA con l'app amministratore: senza firma valida il programma non si aggiorna):
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
from . import percorsi, rete, firma
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


def installato():
    """True se il programma e' stato messo con l'installer (c'e' il disinstallatore accanto all'exe)."""
    c = cartella_exe()
    return bool(c and os.path.isfile(os.path.join(c, 'unins000.exe')))


def disponibile(online):
    """Dati della versione nuova se e' piu' recente di questa, altrimenti None.
    Dalla 0.5.7 il blocco "programma" di online.json deve avere la firma dell'autore: senza firma valida
    l'aggiornamento non viene proposto (nessuno puo' far installare un programma diverso)."""
    p = (online or {}).get('programma') or {}
    if p.get('versione') and p.get('url') and _num(p['versione']) > _num(VERSIONE) and firma.firmato(p):
        return p
    return None


def prepara(info, avanzamento=None, fermati=None):
    """Scarica e controlla la versione nuova. Con l'installer (Windows): restituisce il percorso del Setup .exe.
    Altrimenti: la cartella con i file nuovi estratti dallo zip (quella che contiene l'exe)."""
    base = os.path.join(percorsi.dati_app(), 'aggiornamento')
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base, exist_ok=True)
    if info.get('setup_url') and sys.platform == 'win32':
        sp = os.path.join(base, 'CotW_Italiano_Setup.exe')
        rete.scarica(info['setup_url'], sp, info.get('setup_sha256'),
                     (lambda a, b: avanzamento(a >> 20, max(b >> 20, 1), 'Scarico')) if avanzamento else None, fermati)
        return sp
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
             ':copia']
    if nuova.lower().endswith('.exe') and not installato():
        # veniva da uno zip estratto chissa' dove: installazione normale (scegli dove, icona sul desktop);
        # alla fine l'installer stesso riapre il programma, che poi cancella la cartella vecchia
        cfg = percorsi.leggi_config()
        cfg['cartella_vecchia'] = app
        percorsi.salva_config(cfg)
        righe.append('start "" "%s"' % nuova)
        with open(script, 'w', encoding='utf-8') as f:
            f.write('\r\n'.join(righe) + '\r\n')
        subprocess.Popen(['cmd', '/c', script], creationflags=0x08000000 | 0x00000200, close_fds=True)
        return
    if nuova.lower().endswith('.exe'):              # gia' installato: stessa cartella, con la barra dell'installer
        righe.append('start "" /wait "%s" /SILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL /DIR="%s"' % (nuova, app))
    else:
        righe.append('robocopy "%s" "%s" /E /R:10 /W:1 /NFL /NDL /NJH /NJS /NP >nul' % (nuova, app))
    righe += [
             'start "" "%s"%s' % (os.path.join(app, NOME_EXE), ''.join(' "%s"' % a.replace('%', '%%').replace('"', '')
                                                                        for a in (argomenti or [])))]
    with open(script, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(righe) + '\r\n')
    # finestra nascosta + gruppo separato: lo script sopravvive alla chiusura del programma
    subprocess.Popen(['cmd', '/c', script], creationflags=0x08000000 | 0x00000200, close_fds=True)


def pulisci_cartella_vecchia():
    """Dopo l'installazione: cancella la cartella dove stava estratto il programma vecchio (solo se e' davvero sua).
    Restituisce (cartella_vecchia, cancellata) oppure None."""
    cfg = percorsi.leggi_config()
    vecchia = cfg.get('cartella_vecchia')
    attuale = cartella_exe()
    if not vecchia or not attuale or os.path.normcase(os.path.abspath(vecchia)) == os.path.normcase(attuale):
        return None
    ok = False
    if os.path.isdir(vecchia) and os.path.isfile(os.path.join(vecchia, NOME_EXE)) \
            and os.path.isfile(os.path.join(vecchia, 'LICENZA_TRADUZIONE.txt')) \
            and not os.path.isfile(os.path.join(vecchia, 'unins000.exe')) \
            and len(os.listdir(vecchia)) < 200:                # solo la cartella del programma, niente altro
        shutil.rmtree(vecchia, ignore_errors=True)
        ok = not os.path.exists(vecchia)
    cfg.pop('cartella_vecchia', None)
    percorsi.salva_config(cfg)
    return vecchia, ok

