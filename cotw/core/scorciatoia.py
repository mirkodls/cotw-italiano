"""Segnalare mentre giochi: una scorciatoia (di base Ctrl+Alt+S, si cambia in Impostazioni) apre la finestrella
"Segnala errore" sopra il gioco. Valida in tutto Windows (RegisterHotKey), anche col gioco in primo piano."""
import os
import sys
import threading

from . import percorsi

PREDEFINITA = 'Ctrl+Alt+S'
_MOD = {'alt': 0x0001, 'ctrl': 0x0002, 'shift': 0x0004}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY, _WM_QUIT = 0x0312, 0x0012


def attiva():
    """Impostazione dell'utente (Impostazioni). Di base accesa."""
    return percorsi.leggi_config().get('scorciatoia', True) is not False


def tasti():
    """Scorciatoia scelta dall'utente, es. 'Ctrl+Alt+S'."""
    t = percorsi.leggi_config().get('scorciatoia_tasti')
    return t if isinstance(t, str) and valida(t) else PREDEFINITA


def _tasto_vk(nome):
    n = nome.upper()
    if len(n) == 1 and ('A' <= n <= 'Z' or '0' <= n <= '9'):
        return ord(n)
    if n.startswith('F') and n[1:].isdigit() and 1 <= int(n[1:]) <= 24:
        return 0x70 + int(n[1:]) - 1
    return None


def scomponi(testo):
    """'Ctrl+Alt+S' -> (modificatori, codice tasto) per Windows, oppure None se non va bene.
    Serve almeno Ctrl o Alt (i tasti da soli il gioco li usa), piu' una lettera, un numero o F1-F24."""
    parti = [p.strip() for p in str(testo or '').split('+') if p.strip()]
    if len(parti) < 2:
        return None
    mod = 0
    for p in parti[:-1]:
        m = _MOD.get(p.lower())
        if m is None:
            return None
        mod |= m
    vk = _tasto_vk(parti[-1])
    if vk is None or not (mod & (_MOD['ctrl'] | _MOD['alt'])):
        return None
    return mod, vk


def valida(testo):
    return scomponi(testo) is not None


class Tasto:
    """Tasto(testo, callback).avvia() -> True se Windows ha dato la scorciatoia (False: la usa gia' un altro
    programma). La callback viene chiamata dal thread del tasto: in Qt passala con un Signal."""

    def __init__(self, testo, callback):
        self.testo, self.callback = testo, callback
        self._tid, self._ok = None, None
        self._pronto = threading.Event()

    def avvia(self):
        if sys.platform != 'win32' or not scomponi(self.testo):
            return False
        threading.Thread(target=self._giro, daemon=True).start()
        self._pronto.wait(3)
        return bool(self._ok)

    def _giro(self):
        import ctypes
        from ctypes import wintypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        self._tid = k32.GetCurrentThreadId()
        mod, vk = scomponi(self.testo)
        self._ok = bool(u32.RegisterHotKey(None, 1, mod | _MOD_NOREPEAT, vk))
        self._pronto.set()
        if not self._ok:
            return
        msg = wintypes.MSG()
        try:
            while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == _WM_HOTKEY:
                    try:
                        self.callback()
                    except Exception:
                        pass
        finally:
            u32.UnregisterHotKey(None, 1)

    def ferma(self):
        if self._tid and sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)


def libera(testo):
    """True se la scorciatoia si puo' usare (nessun altro programma la tiene). Fuori da Windows: True."""
    if sys.platform != 'win32':
        return True
    t = Tasto(testo, lambda: None)
    ok = t.avvia()
    t.ferma()
    return ok


# ---------------- finestra in primo piano (Windows e' severo con chi "ruba" il primo piano) ----------------
def primo_piano_attuale():
    if sys.platform != 'win32':
        return None
    import ctypes
    return ctypes.windll.user32.GetForegroundWindow()


def porta_davanti(hwnd):
    """Porta davanti una finestra (la nostra o quella del gioco quando si torna a giocare)."""
    if sys.platform != 'win32' or not hwnd:
        return
    import ctypes
    u32 = ctypes.windll.user32
    try:
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)                 # SW_RESTORE
        if not u32.SetForegroundWindow(hwnd):
            u32.keybd_event(0x12, 0, 0, 0)          # un tocco di Alt sblocca il primo piano
            u32.keybd_event(0x12, 0, 2, 0)
            u32.SetForegroundWindow(hwnd)
    except Exception:
        pass


# ---------------- avvio del "compagno di gioco" (processo a parte, senza finestre finche' non serve) ----------------
def comando_programma(*argomenti):
    """Come rilanciare questo programma (exe oppure python + CotW_Italiano.py) con altri argomenti."""
    from . import programma
    exe = programma.cartella_exe()
    if exe:
        return [os.path.join(exe, programma.NOME_EXE)] + list(argomenti)
    radice = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    py = sys.executable
    pw = os.path.join(os.path.dirname(py), 'pythonw.exe')
    return [pw if os.path.isfile(pw) else py, os.path.join(radice, 'CotW_Italiano.py')] + list(argomenti)


def avvia_compagno():
    """Scorciatoia attiva finche' il gioco e' aperto. Se il compagno c'e' gia', il nuovo esce da solo."""
    if not attiva():
        return
    import subprocess
    try:
        subprocess.Popen(comando_programma('--compagno'), close_fds=True,
                         creationflags=0x00000008 | 0x00000200 if sys.platform == 'win32' else 0)
    except Exception:
        pass
