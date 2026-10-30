"""Trova le cartelle importanti: gioco, dropzone, salvataggi, dati del programma.
Non modifica niente: legge soltanto."""
import os
import re
import sys
import glob
import json
import subprocess

EXE_GIOCO = 'theHunterCotW_F.exe'
NOME_APP = 'CotW Italiano'

IS_WIN = sys.platform.startswith('win')


def dati_app():
    """Cartella dei dati del programma (impostazioni, stato, backup)."""
    base = os.environ.get('APPDATA') if IS_WIN else os.path.expanduser('~/.config')
    if os.environ.get('COTW_DATI'):          # solo per le prove
        base = os.environ['COTW_DATI']
    d = os.path.join(base, NOME_APP)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------- impostazioni ----------------
def _file_config():
    return os.path.join(dati_app(), 'impostazioni.json')


def leggi_config():
    try:
        with open(_file_config(), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def salva_config(cfg):
    tmp = _file_config() + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _file_config())


# ---------------- gioco ----------------
def _librerie_steam():
    cand = []
    steam = None
    if IS_WIN:
        try:
            import winreg
            for root, key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                              (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
                try:
                    with winreg.OpenKey(root, key) as k:
                        for nome in ('SteamPath', 'InstallPath'):
                            try:
                                steam = winreg.QueryValueEx(k, nome)[0]
                                break
                            except OSError:
                                pass
                except OSError:
                    pass
                if steam:
                    break
        except Exception:
            pass
    basi = [steam] if steam else []
    basi += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    for b in basi:
        if not b:
            continue
        b = os.path.normpath(b)
        cand.append(b)
        vdf = os.path.join(b, 'steamapps', 'libraryfolders.vdf')
        try:
            txt = open(vdf, encoding='utf-8', errors='ignore').read()
            for p in re.findall(r'"path"\s+"([^"]+)"', txt):
                cand.append(os.path.normpath(p.replace('\\\\', '\\')))
        except Exception:
            pass
    for lettera in 'CDEFGH':
        cand += [lettera + r':\SteamLibrary', lettera + r':\Steam', lettera + r':\Games\Steam']
    visti, out = set(), []
    for c in cand:
        if c.lower() not in visti:
            visti.add(c.lower())
            out.append(c)
    return out


def e_cartella_gioco(p):
    return bool(p) and os.path.isfile(os.path.join(p, EXE_GIOCO))


def trova_gioco():
    """Restituisce la cartella del gioco (quella con theHunterCotW_F.exe) o None."""
    cfg = leggi_config()
    if e_cartella_gioco(cfg.get('cartella_gioco')):
        return cfg['cartella_gioco']
    for lib in _librerie_steam():
        p = os.path.join(lib, 'steamapps', 'common', 'theHunterCotW')
        if e_cartella_gioco(p):
            return p
    # Epic Games
    for p in glob.glob(r'C:\Program Files\Epic Games\theHunter*') + glob.glob(r'C:\Program Files\Epic Games\*Hunter*'):
        if e_cartella_gioco(p):
            return p
    return None


def dropzone(gioco):
    """La dropzone attiva, oppure quella disattivata (dropzone_off) se la mod e' spenta."""
    on = os.path.join(gioco, 'dropzone')
    off = os.path.join(gioco, 'dropzone_off')
    if os.path.isdir(on) or not os.path.isdir(off):
        return on
    return off


def mod_attiva(gioco):
    return os.path.isdir(os.path.join(gioco, 'dropzone'))


def gioco_in_esecuzione():
    if not IS_WIN:
        return False
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + EXE_GIOCO, '/NH'],
                             capture_output=True, text=True, creationflags=0x08000000).stdout
        return EXE_GIOCO.lower() in out.lower()
    except Exception:
        return False


# ---------------- salvataggi ----------------
def cartella_documenti():
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)   # CSIDL_PERSONAL = Documenti (anche su OneDrive)
            if buf.value:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


def profili_salvataggi():
    """Cartelle Saves\\<numero> che contengono il file delle missioni."""
    cfg = leggi_config()
    radici = []
    if cfg.get('cartella_salvataggi'):
        radici.append(cfg['cartella_salvataggi'])
    radici.append(os.path.join(cartella_documenti(), 'Avalanche Studios', 'COTW', 'Saves'))
    out = []
    for r in radici:
        if os.path.isfile(os.path.join(r, 'missions_missiondata_adf')):
            out.append(r)
        for d in sorted(glob.glob(os.path.join(r, '*'))):
            if os.path.isfile(os.path.join(d, 'missions_missiondata_adf')) and d not in out:
                out.append(d)
    return out


def cartella_risorse():
    """Cartella 'risorse' del programma (anche quando e' un .exe)."""
    base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, 'risorse')
