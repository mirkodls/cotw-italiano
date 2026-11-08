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
import time
import shutil
import zipfile
import subprocess
from . import percorsi, rete, firma
from .. import VERSIONE

NOME_EXE = 'CotW Italiano.exe'
# Ultima spiaggia: pagina fissa (scritta qui, non presa da internet) dove scaricare a mano l'ultima versione
SITO_SCARICA = 'https://github.com/mirkodls/cotw-italiano#-scarica'
GIORNI_SENZA_FIRMA = 3          # c'e' una versione nuova ma questo programma non riesce a verificarla da tot giorni
GIORNI_SENZA_CONTATTO = 7       # non riesce a leggere online.json da tot giorni (es. certificati, come la 0.5.9)


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


def canale():
    """'anteprima' = riceve anche le versioni di prova (l'autore e chi prova le novita' prima degli altri)."""
    return 'anteprima' if percorsi.leggi_config().get('canale') == 'anteprima' else 'normale'


def disponibile(online, chiavi=None, canale_scelto=None):
    """Dati della versione nuova se e' piu' recente di questa, altrimenti None.
    Dalla 0.5.7 il blocco "programma" di online.json deve avere la firma dell'autore: senza firma valida
    l'aggiornamento non viene proposto (nessuno puo' far installare un programma diverso).
    Dalla 0.5.14 c'e' anche il blocco "anteprima" (versione di prova, firmata anche lei): lo vede solo chi ha scelto il
    canale anteprima. Quando l'autore la promuove, lo STESSO file passa nel blocco "programma" per tutti."""
    o = online or {}
    blocchi = ['programma'] + (['anteprima'] if (canale_scelto or canale()) == 'anteprima' else [])
    migliore = None
    for nome in blocchi:
        p = o.get(nome)
        if not isinstance(p, dict) or not p.get('versione') or not p.get('url'):
            continue
        if _num(p['versione']) <= _num(VERSIONE) or not firma.firmato(p, chiavi):
            continue
        if migliore is None or _num(p['versione']) > _num(migliore['versione']):
            migliore = dict(p, anteprima=(nome == 'anteprima'))
    return migliore


# ---------------- ultima spiaggia: se l'aggiornamento automatico non riesce ----------------
def _ora():
    return int(time.time())


def segna_tentativo(info):
    """Prima di chiudersi per aggiornare: al prossimo avvio si capisce se la versione e' davvero cambiata."""
    cfg = percorsi.leggi_config()
    cfg['agg_tentativo'] = {'da': VERSIONE, 'a': str(info.get('versione')), 'quando': _ora()}
    percorsi.salva_config(cfg)


def segna_fallito(motivo=''):
    cfg = percorsi.leggi_config()
    cfg['agg_falliti'] = int(cfg.get('agg_falliti') or 0) + 1
    cfg['agg_ultimo_errore'] = str(motivo)[:300]
    cfg.pop('agg_tentativo', None)
    percorsi.salva_config(cfg)


def controlla_esito():
    """All'avvio. 'ok' = l'aggiornamento e' andato; 'fallito' = era partito ma la versione e' ancora quella vecchia
    (installer non partito, bloccato dall'antivirus, chiuso a meta'...); None = niente in sospeso."""
    try:
        cfg = percorsi.leggi_config()
        t = cfg.get('agg_tentativo')
        if not isinstance(t, dict):
            return None
        if _num(VERSIONE) >= _num(t.get('a')):
            cfg.pop('agg_tentativo', None)
            cfg['agg_falliti'] = 0
            cfg.pop('agg_ultimo_errore', None)
            percorsi.salva_config(cfg)
            return 'ok'
        segna_fallito('Il programma si e\' riaperto ma e\' ancora la versione %s.' % VERSIONE)
        return 'fallito'
    except Exception:
        return None


def stato_a_mano(online, chiavi=None):
    """None, oppure perche' conviene scaricare a mano la versione nuova dal sito (SITO_SCARICA):
    'falliti' = l'aggiornamento automatico e' fallito 2 volte o piu';
    'senza_firma' = online c'e' una versione nuova ma da GIORNI_SENZA_FIRMA giorni questo programma non riesce a
                    verificarla (non la installa: la indica solo, e il link e' fisso nel programma);
    'senza_contatto' = da GIORNI_SENZA_CONTATTO giorni non riesce a leggere gli aggiornamenti."""
    try:
        cfg = percorsi.leggi_config()
        prima = dict(cfg)
        ora = _ora()
        p = (online or {}).get('programma') if isinstance(online, dict) else None
        motivo = None
        if online:
            cfg['online_ok'] = ora
        else:
            cfg.setdefault('online_ok', ora)
            if ora - int(cfg.get('online_ok') or ora) > GIORNI_SENZA_CONTATTO * 86400:
                motivo = 'senza_contatto'
        v = p.get('versione') if isinstance(p, dict) else None
        if online and v and _num(v) > _num(VERSIONE):
            if disponibile(online, chiavi, canale_scelto='normale'):
                cfg.pop('senza_firma_dal', None)
                if int(cfg.get('agg_falliti') or 0) >= 2:
                    motivo = 'falliti'
            else:
                cfg.setdefault('senza_firma_dal', ora)
                if ora - int(cfg['senza_firma_dal']) > GIORNI_SENZA_FIRMA * 86400:
                    motivo = 'senza_firma'
        elif online:
            cfg.pop('senza_firma_dal', None)
            if v and _num(v) <= _num(VERSIONE):
                cfg['agg_falliti'] = 0
        if cfg != prima:
            percorsi.salva_config(cfg)
        return motivo
    except Exception:
        return None


TESTI_A_MANO = {
    'falliti': 'L\'aggiornamento automatico del programma non e\' riuscito. Scarica a mano l\'ultima versione dal sito '
               'ufficiale e installala sopra questa (impostazioni e traduzione restano).',
    'senza_firma': 'C\'e\' una versione nuova del programma, ma questa versione non riesce ad aggiornarsi da sola. '
                   'Scaricala a mano dal sito ufficiale e installala sopra questa (impostazioni e traduzione restano).',
    'senza_contatto': 'Da piu\' di %d giorni non riesco a controllare gli aggiornamenti. Se internet funziona, prova '
                      '"Prova la connessione" oppure scarica a mano l\'ultima versione dal sito ufficiale.'
                      % GIORNI_SENZA_CONTATTO,
}


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


def script_aggiornamento(nuova, app, argomenti=None, pid=None, gia_installato=None):
    """Righe dello script che sostituisce i file appena il programma si chiude.
    Restituisce (righe, apri_installer_normale). Separato da installa_e_riavvia per la prova automatica."""
    gia_installato = installato() if gia_installato is None else gia_installato
    righe = ['@echo off', 'chcp 65001 >nul', 'set "PIDV=%d"' % (pid or os.getpid()), ':attendi',
             'tasklist /FI "PID eq %PIDV%" /NH | find "%PIDV%" >nul',
             'if errorlevel 1 goto copia',
             'ping -n 2 127.0.0.1 >nul',
             'goto attendi',
             ':copia']
    if nuova.lower().endswith('.exe') and not gia_installato:
        # veniva da uno zip estratto chissa' dove: installazione normale (scegli dove, icona sul desktop);
        # alla fine l'installer stesso riapre il programma, che poi cancella la cartella vecchia
        righe.append('start "" "%s"' % nuova)
        return righe, True
    if nuova.lower().endswith('.exe'):              # gia' installato: stessa cartella, con la barra dell'installer
        righe.append('start "" /wait "%s" /SILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL /DIR="%s"' % (nuova, app))
    else:
        righe.append('robocopy "%s" "%s" /E /R:10 /W:1 /NFL /NDL /NJH /NJS /NP >nul' % (nuova, app))
    righe.append('start "" "%s"%s' % (os.path.join(app, NOME_EXE), ''.join(' "%s"' % a.replace('%', '%%').replace('"', '')
                                                                           for a in (argomenti or []))))
    return righe, False


def installa_e_riavvia(nuova, argomenti=None):
    """Avvia lo script che sostituisce i file appena il programma si chiude. Dopo questa chiamata il programma va chiuso."""
    app = cartella_exe()
    if not app:
        raise RuntimeError('Il programma non e\' avviato come exe: aggiorna a mano.')
    script = os.path.join(percorsi.dati_app(), 'aggiornamento', 'aggiorna.cmd')
    righe, installer_normale = script_aggiornamento(nuova, app, argomenti)
    if installer_normale:
        cfg = percorsi.leggi_config()
        cfg['cartella_vecchia'] = app
        percorsi.salva_config(cfg)
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

