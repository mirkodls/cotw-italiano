"""Opzioni di avvio del gioco: le scrive in Steam (a Steam CHIUSO) oppure crea un collegamento sul desktop
che avvia il gioco con le mod (per chi gioca senza launcher)."""
import os
import re
import glob
import shutil
import subprocess
import time
from . import percorsi

OPZIONI = '--vfs-fs dropzone --vfs-archive archives_win64 --vfs-fs .'
# "Controllo prima di giocare": Steam avvia prima CotW Italiano.exe, che controlla gli aggiornamenti e poi avvia il gioco
# (%command% e' il gioco: Steam lo sostituisce da solo). Esempio:  "C:\...\CotW Italiano.exe" --gioco %command% --vfs-fs ...
_RX_CONTROLLO = re.compile(r'"[^"]*?CotW Italiano\.exe"\s+--gioco\s+%command%\s*', re.I)


def _dec(v):
    """Valore VDF (come sta nel file, con \\ e \") -> testo normale."""
    return re.sub(r'\\(.)', r'\1', v)


def _enc(v):
    return v.replace('\\', '\\\\').replace('"', '\\"')


def prefisso_controllo(exe):
    return '"%s" --gioco %%command%% ' % exe


def controllo_attivo(opzioni):
    """Percorso dell'exe se nelle opzioni di Steam c'e' il controllo prima di giocare, altrimenti None."""
    m = _RX_CONTROLLO.search(opzioni or '')
    return re.search(r'"([^"]+)"', m.group(0)).group(1) if m else None
APP_ID = '518790'          # theHunter: Call of the Wild su Steam


# ---------------- lettore/scrittore VDF (formato di configurazione di Steam) ----------------
def _token(testo):
    i, n = 0, len(testo)
    while i < n:
        c = testo[i]
        if c.isspace():
            i += 1
        elif c == '/' and testo.startswith('//', i):
            i = testo.find('\n', i)
            i = n if i < 0 else i
        elif c in '{}':
            yield c
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and testo[j] != '"':
                if testo[j] == '\\' and j + 1 < n:
                    buf.append(testo[j:j + 2])
                    j += 2
                else:
                    buf.append(testo[j])
                    j += 1
            yield ('s', ''.join(buf))
            i = j + 1
        else:
            j = i
            while j < n and not testo[j].isspace() and testo[j] not in '{}"':
                j += 1
            yield ('s', testo[i:j])
            i = j


def vdf_leggi(testo):
    """Restituisce una lista di coppie [chiave, valore]; il valore e' una stringa o una lista di coppie."""
    toks = _token(testo)

    def blocco():
        out = []
        for t in toks:
            if t == '}':
                return out
            if t == '{':
                raise ValueError('graffa inattesa')
            chiave = t[1]
            v = next(toks)
            out.append([chiave, blocco() if v == '{' else v[1]])
        return out
    return blocco()


def vdf_scrivi(coppie, livello=0):
    righe = []
    tab = '\t' * livello
    for k, v in coppie:
        if isinstance(v, list):
            righe.append('%s"%s"\n%s{\n%s%s}\n' % (tab, k, tab, vdf_scrivi(v, livello + 1), tab))
        else:
            righe.append('%s"%s"\t\t"%s"\n' % (tab, k, v))
    return ''.join(righe)


def _figlio(coppie, chiave, crea=False):
    for k, v in coppie:
        if k.lower() == chiave.lower() and isinstance(v, list):
            return v
    if crea:
        nuovo = []
        coppie.append([chiave, nuovo])
        return nuovo
    return None


def _blocco_app(radice, crea=False):
    nodo = radice
    for k in ('UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps'):
        nodo = _figlio(nodo, k, crea)
        if nodo is None:
            return None
    return _figlio(nodo, APP_ID, crea)


# ---------------- Steam ----------------
def cartella_steam():
    for lib in percorsi._librerie_steam():
        if os.path.isdir(os.path.join(lib, 'userdata')):
            return lib
    return None


def file_config_steam():
    s = cartella_steam()
    if not s:
        return []
    return sorted(glob.glob(os.path.join(s, 'userdata', '*', 'config', 'localconfig.vdf')),
                  key=os.path.getmtime, reverse=True)


def steam_in_esecuzione():
    if not percorsi.IS_WIN:
        return False
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq steam.exe', '/NH'],
                             capture_output=True, text=True, creationflags=0x08000000).stdout
        return 'steam.exe' in out.lower()
    except Exception:
        return False


def _leggi_file(f):
    return vdf_leggi(open(f, encoding='utf-8', errors='replace').read())


def stato_steam():
    """'impostate', 'diverse' (ci sono altre opzioni), 'mancano', 'nessun_steam' + testo attuale."""
    files = file_config_steam()
    if not files:
        return 'nessun_steam', ''
    for f in files:
        try:
            app = _blocco_app(_leggi_file(f))
        except Exception:
            continue
        if app is None:
            continue
        for k, v in app:
            if k.lower() == 'launchoptions':
                v = _dec(v)
                if '--vfs-fs dropzone' in v:
                    return 'impostate', v
                return ('diverse' if v.strip() else 'mancano'), v
        return 'mancano', ''
    return 'mancano', ''


def imposta_steam(togli=False, controllo_exe=None, togli_controllo=False):
    """Scrive (o toglie) le opzioni di avvio in Steam. Steam deve essere CHIUSO. Fa un backup di ogni file.
    controllo_exe: attiva il controllo prima di giocare con questo exe.  togli_controllo: lo toglie (le opzioni restano)."""
    if steam_in_esecuzione():
        raise RuntimeError('Steam e\' aperto: chiudilo del tutto (anche dall\'icona vicino all\'orologio) e riprova.')
    files = file_config_steam()
    if not files:
        raise RuntimeError('Non trovo la configurazione di Steam su questo PC.')
    con_gioco = []
    for f in files:
        try:
            if _blocco_app(_leggi_file(f)) is not None:
                con_gioco.append(f)
        except Exception:
            pass
    bersagli = con_gioco or files[:1]          # gli account che hanno il gioco (o il piu' recente)
    bdir = os.path.join(percorsi.dati_app(), 'backup_steam')
    os.makedirs(bdir, exist_ok=True)
    for f in bersagli:
        radice = _leggi_file(f)
        app = _blocco_app(radice, crea=not togli)
        if app is None:
            continue
        att = next((c for c in app if c[0].lower() == 'launchoptions'), None)
        val = _dec(att[1]) if att else ''
        if togli:
            if att:
                nuovo = _RX_CONTROLLO.sub('', val).replace(OPZIONI, '').strip()
                if nuovo:
                    att[1] = _enc(nuovo)
                else:
                    app.remove(att)
        else:
            if att is None:
                att = ['LaunchOptions', '']
                app.append(att)
            resto = _RX_CONTROLLO.sub('', val).strip()
            if '--vfs-fs dropzone' not in resto:
                resto = (resto + ' ' + OPZIONI).strip()
            if controllo_exe and not togli_controllo:
                nuovo = prefisso_controllo(controllo_exe) + resto
            elif togli_controllo:
                nuovo = resto
            else:
                vecchio = controllo_attivo(val)         # se c'era il controllo prima di giocare, resta
                nuovo = (prefisso_controllo(vecchio) + resto) if vecchio else resto
            att[1] = _enc(nuovo)
        account = os.path.basename(os.path.dirname(os.path.dirname(f)))
        dst = os.path.join(bdir, 'localconfig_%s_%s.vdf' % (account, time.strftime('%Y%m%d_%H%M%S')))
        n = 2
        while os.path.exists(dst):
            dst = dst[:-4].rsplit('__', 1)[0] + '__%d.vdf' % n
            n += 1
        shutil.copy2(f, dst)
        tmp = f + '.cotw_tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as o:
            o.write(vdf_scrivi(radice))
        os.replace(tmp, f)
    return len(bersagli)


# ---------------- collegamento sul desktop (senza launcher) ----------------
def crea_collegamento(gioco, nome='theHunter COTW con mod', programma_exe=None):
    """programma_exe: il collegamento apre prima CotW Italiano (controllo aggiornamenti) e poi il gioco."""
    if not percorsi.IS_WIN:
        raise RuntimeError('Funziona solo su Windows.')
    exe = os.path.join(gioco, percorsi.EXE_GIOCO)
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)   # Desktop (anche su OneDrive)
        if buf.value:
            desktop = buf.value
    except Exception:
        pass
    lnk = os.path.join(desktop, nome + '.lnk')
    bersaglio, argomenti, cartella = exe, OPZIONI, gioco
    if programma_exe:
        bersaglio, argomenti, cartella = programma_exe, '--gioco "%s" %s' % (exe, OPZIONI), os.path.dirname(programma_exe)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{l}');$s.TargetPath='{t}';"
          "$s.Arguments='{a}';$s.WorkingDirectory='{w}';$s.IconLocation='{e},0';$s.Save()").format(
        l=lnk.replace("'", "''"), t=bersaglio.replace("'", "''"), e=exe.replace("'", "''"),
        a=argomenti.replace("'", "''"), w=cartella.replace("'", "''"))
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
                       capture_output=True, text=True, creationflags=0x08000000)
    if r.returncode != 0 or not os.path.isfile(lnk):
        raise RuntimeError('Non sono riuscito a creare il collegamento: ' + (r.stderr or '').strip()[:300])
    return lnk
