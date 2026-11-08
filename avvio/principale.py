"""AVVIO di CotW Italiano: il programmino SEPARATO che aggiorna il programma vero (regole in AGGIORNAMENTI_SICURI.txt).
E' l'exe "CotW Italiano.exe" nella cartella di installazione: icone, Steam e collegamenti aprono lui, lui apre il
programma vero, che sta in una cartella per versione:

    <installazione>\\CotW Italiano.exe            <- questo AVVIO (un solo file, cambia raramente)
    <installazione>\\programma\\0.5.15\\...         <- programma vero (Qt ecc.)
    <installazione>\\programma\\0.5.14\\...         <- versione precedente, tenuta da parte per tornare indietro
    <installazione>\\programma\\stato.json          <- quale versione si usa, quale e' in prova, quali sono rotte

Regole:
 1. aggiornatore separato: se il programma nuovo e' rotto, questo funziona lo stesso (e' un altro file, altro Python);
 2. si aggiorna da solo con DUE copie: scarica l'avvio nuovo accanto, lo prova, solo allora lo scambia;
 3. ritorno automatico: la versione nuova deve dire "sono ok" (file avvio_ok.txt nella sua cartella); se si chiude
    con un errore prima di dirlo, si torna da soli alla precedente e quella nuova viene segnata come rotta;
 4. scarica solo cio' che e' scritto in online.json con la FIRMA dell'autore e con l'impronta SHA-256 giusta;
 7. se qualcosa va storto c'e' sempre il pulsante per scaricare a mano dal sito ufficiale.
Niente librerie esterne: solo Python, tkinter (finestre) e certifi (certificati)."""
import os
import re
import sys
import json
import time
import shutil
import zipfile
import hashlib
import threading
import subprocess
import urllib.request

from . import AVVIO_VERSIONE
from cotw.core import firma

NOME_EXE = 'CotW Italiano.exe'
NOME_APP = 'CotW Italiano'
REPO = 'mirkodls/cotw-italiano'
SITO_SCARICA = 'https://github.com/mirkodls/cotw-italiano#-scarica'
FILE_OK = 'avvio_ok.txt'
_UA = {'User-Agent': 'CotW-Italiano-Avvio/%s (https://github.com/%s)' % (AVVIO_VERSIONE, REPO)}
PROVA = os.environ.get('COTW_AVVIO_PROVA') == '1'          # prova automatica: niente finestre, risposte da sole
IS_WIN = sys.platform == 'win32'


# ---------------- cartelle e stato ----------------
def exe_avvio():
    return os.path.abspath(os.environ.get('COTW_AVVIO_EXE') or sys.argv[0])


def cartella_app():
    return os.path.dirname(exe_avvio())


def cartella_programmi():
    return os.path.join(cartella_app(), 'programma')


def dati_app():
    base = os.environ.get('COTW_DATI') or (os.environ.get('APPDATA') if IS_WIN else os.path.expanduser('~/.config'))
    d = os.path.join(base, NOME_APP)
    os.makedirs(d, exist_ok=True)
    return d


def registro(testo):
    try:
        with open(os.path.join(dati_app(), 'avvio.log'), 'a', encoding='utf-8') as f:
            f.write('%s  %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), testo))
    except Exception:
        pass


def _num(v):
    try:
        return tuple(int(x) for x in str(v).split('.'))
    except ValueError:
        return (0,)


def versioni():
    """Versioni del programma presenti (cartelle con dentro l'exe), dalla piu' nuova."""
    c = cartella_programmi()
    out = []
    try:
        for n in os.listdir(c):
            if re.fullmatch(r'\d+(\.\d+)*', n) and os.path.isfile(os.path.join(c, n, NOME_EXE)):
                out.append(n)
    except OSError:
        pass
    return sorted(out, key=_num, reverse=True)


def _file_stato():
    return os.path.join(cartella_programmi(), 'stato.json')


def leggi_stato():
    try:
        with open(_file_stato(), encoding='utf-8') as f:
            s = json.load(f)
            return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def salva_stato(s):
    os.makedirs(cartella_programmi(), exist_ok=True)
    tmp = _file_stato() + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _file_stato())


def scegli_versione(s):
    """Decide quale versione aprire. Una versione piu' nuova (scaricata da qui o messa dall'installer) diventa quella
    attuale IN PROVA, e la vecchia resta da parte come precedente. Le versioni rotte non si riprovano mai."""
    presenti = versioni()
    rotte = set(s.get('rotte') or [])
    buone = [v for v in presenti if v not in rotte]
    att = s.get('attuale') if s.get('attuale') in presenti else None
    if buone and (att is None or _num(buone[0]) > _num(att)):
        nuova = buone[0]
        if att and att != nuova:
            s['precedente'] = att
        elif s.get('precedente') not in presenti:
            s.pop('precedente', None)
        s['attuale'] = nuova
        s['in_prova'] = nuova
        salva_stato(s)
        registro('versione nuova in prova: %s (precedente %s)' % (nuova, s.get('precedente')))
    elif att is None and presenti:              # tutte rotte: meglio aprire la piu' nuova che niente
        s['attuale'] = presenti[0]
        salva_stato(s)
    return s.get('attuale')


def pulisci_vecchie(s):
    """Tiene solo la versione attuale e la precedente (piu' quelle rotte, cosi' non si riscaricano)."""
    tieni = {s.get('attuale'), s.get('precedente')}
    for v in versioni():
        if v not in tieni and v not in (s.get('rotte') or []):
            shutil.rmtree(os.path.join(cartella_programmi(), v), ignore_errors=True)
    for v in list(s.get('rotte') or []):           # rotte piu' vecchie dell'attuale: non servono piu'
        if _num(v) < _num(s.get('attuale')):
            shutil.rmtree(os.path.join(cartella_programmi(), v), ignore_errors=True)
            s['rotte'].remove(v)
    shutil.rmtree(os.path.join(cartella_programmi(), '_scarico'), ignore_errors=True)


# ---------------- finestre (tkinter) ----------------
_tk = None


def _radice():
    global _tk
    if _tk is None:
        import tkinter
        _tk = tkinter.Tk()
        _tk.withdraw()
        _tk.title(NOME_APP)
    return _tk


def chiedi(titolo, testo):
    if PROVA:
        registro('[prova] domanda: %s -> si' % titolo)
        return True
    from tkinter import messagebox
    return messagebox.askyesno(titolo, testo, parent=_radice())


def avvisa(titolo, testo, con_link=False):
    registro('avviso: %s: %s' % (titolo, testo.replace('\n', ' ')))
    if PROVA:
        return
    from tkinter import messagebox
    if con_link:
        if messagebox.askyesno(titolo, testo + '\n\nApro la pagina per scaricarlo a mano?', icon='warning',
                               parent=_radice()):
            import webbrowser
            webbrowser.open(SITO_SCARICA)
    else:
        messagebox.showwarning(titolo, testo, parent=_radice())


class Barra:
    """Finestrella con la barra (scarica in un thread, la finestra resta viva)."""

    def __init__(self, titolo):
        self.ok = None
        if PROVA:
            return
        import tkinter
        from tkinter import ttk
        r = _radice()
        self.w = tkinter.Toplevel(r)
        self.w.title(titolo)
        self.w.resizable(False, False)
        self.w.protocol('WM_DELETE_WINDOW', lambda: None)
        self.testo = tkinter.Label(self.w, text='...', width=60, anchor='w', justify='left')
        self.testo.pack(padx=16, pady=(14, 6))
        self.barra = ttk.Progressbar(self.w, length=420, mode='determinate')
        self.barra.pack(padx=16, pady=(0, 14))
        self._dati = ('...', 0, 0)
        self.w.update()

    def imposta(self, testo, fatti=0, totale=0):
        self._dati = (testo, fatti, totale)
        if PROVA:
            return

    def esegui(self, fn):
        """Esegue fn() in un thread mostrando la barra. Restituisce il risultato o rilancia l'errore."""
        esito = {}

        def lavoro():
            try:
                esito['r'] = fn(self)
            except BaseException as e:
                esito['e'] = e
        t = threading.Thread(target=lavoro, daemon=True)
        t.start()
        while t.is_alive():
            if not PROVA:
                testo, a, b = self._dati
                self.testo.config(text=testo)
                if b:
                    self.barra.config(mode='determinate', maximum=b, value=a)
                self.w.update()
            t.join(0.1)
        if not PROVA:
            self.w.destroy()
        if 'e' in esito:
            raise esito['e']
        return esito.get('r')


# ---------------- internet ----------------
def _contesto():
    import ssl
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def _apri(url, timeout):
    req = urllib.request.Request(url, headers=dict(_UA, **{'Cache-Control': 'no-cache'}))
    if url.startswith('https://'):
        return urllib.request.urlopen(req, timeout=timeout, context=_contesto())
    return urllib.request.urlopen(req, timeout=timeout)


def url_online():
    return os.environ.get('COTW_URL_ONLINE') or 'https://raw.githubusercontent.com/%s/main/online.json' % REPO


def leggi_online(timeout=4):
    try:
        with _apri(url_online(), timeout) as r:
            o = json.loads(r.read().decode('utf-8'))
            return o if isinstance(o, dict) else {}
    except Exception as e:
        registro('online.json non letto: %s' % e)
        return {}


def _chiavi():
    if PROVA and os.environ.get('COTW_AVVIO_CHIAVE_PROVA'):
        return [os.environ['COTW_AVVIO_CHIAVE_PROVA']]
    return None


def _canale():
    try:
        with open(os.path.join(dati_app(), 'impostazioni.json'), encoding='utf-8') as f:
            return 'anteprima' if json.load(f).get('canale') == 'anteprima' else 'normale'
    except Exception:
        return 'normale'


def versione_nuova(online, attuale, rotte=()):
    """Il blocco firmato della versione nuova (programma, o anteprima per chi l'ha scelta), oppure None."""
    blocchi = ['programma'] + (['anteprima'] if _canale() == 'anteprima' else [])
    migliore = None
    for nome in blocchi:
        p = online.get(nome)
        if not isinstance(p, dict) or not p.get('versione') or not p.get('url') or not p.get('sha256'):
            continue
        v = str(p['versione'])
        if not re.fullmatch(r'\d+(\.\d+)*', v) or v in rotte or _num(v) <= _num(attuale):
            continue
        if not firma.firmato(p, _chiavi()):
            registro('versione %s online senza firma valida: ignorata' % v)
            continue
        if migliore is None or _num(v) > _num(migliore['versione']):
            migliore = p
    return migliore


def scarica(url, dest, sha, barra=None, testo='Scarico'):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    h = hashlib.sha256()
    part = dest + '.part'
    with _apri(url, 60) as r, open(part, 'wb') as f:
        tot = int(r.headers.get('Content-Length') or 0)
        fatti = 0
        while True:
            b = r.read(1 << 18)
            if not b:
                break
            f.write(b)
            h.update(b)
            fatti += len(b)
            if barra:
                barra.imposta('%s: %d di %d MB' % (testo, fatti >> 20, max(tot >> 20, 1)), fatti, tot)
    if h.hexdigest() != sha:
        os.remove(part)
        raise RuntimeError('Il file scaricato e\' rovinato (impronta sbagliata). Riprova piu\' tardi.')
    os.replace(part, dest)
    return dest


# ---------------- aggiornamento ----------------
def installa_versione(info, barra):
    """Scarica lo zip del programma, controlla impronta e percorsi e lo mette in programma\\<versione>.
    La versione attuale non si tocca: se qualcosa va storto, si continua a usare lei."""
    v = str(info['versione'])
    base = os.path.join(cartella_programmi(), '_scarico')
    shutil.rmtree(base, ignore_errors=True)
    zp = scarica(info['url'], os.path.join(base, 'programma.zip'), info['sha256'], barra,
                 'Scarico la versione %s' % v)
    barra.imposta('Controllo e preparo la versione %s...' % v)
    est = os.path.join(base, 'estratto')
    with zipfile.ZipFile(zp) as z:
        for m in z.namelist():
            if m.startswith(('/', '\\')) or ':' in m or '..' in m.replace('\\', '/').split('/'):
                raise RuntimeError('Pacchetto del programma non valido.')
        z.extractall(est)
    sorgente = None
    for cart, _, files in os.walk(est):
        if NOME_EXE in files:
            sorgente = cart
            break
    if not sorgente:
        raise RuntimeError('Nel pacchetto scaricato manca %s.' % NOME_EXE)
    dest = os.path.join(cartella_programmi(), v)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.move(sorgente, dest)
    shutil.rmtree(base, ignore_errors=True)
    registro('versione %s scaricata in %s' % (v, dest))
    return v


def aggiorna_avvio(info, barra):
    """Regola 2: l'avvio nuovo si scarica ACCANTO, si prova, e solo se risponde prende il posto di questo.
    Questo resta come  "CotW Italiano.old.exe"  (copia di riserva)."""
    a = info.get('avvio')
    if not isinstance(a, dict) or not a.get('url') or not a.get('sha256'):
        return None
    if _num(a.get('versione')) <= _num(AVVIO_VERSIONE):
        return None
    io = exe_avvio()
    nuovo = os.path.join(cartella_app(), 'CotW Italiano.new.exe')
    vecchio = os.path.join(cartella_app(), 'CotW Italiano.old.exe')
    scarica(a['url'], nuovo, a['sha256'], barra, 'Scarico l\'avvio %s' % a.get('versione'))
    barra.imposta('Provo l\'avvio nuovo...')
    rap = os.path.join(dati_app(), 'prova_avvio_nuovo.json')
    try:
        r = subprocess.run([nuovo, '--prova-avvio', rap, '--senza-internet'], timeout=180,
                           creationflags=0x08000000 if IS_WIN else 0)
        esito = json.load(open(rap, encoding='utf-8'))
        if r.returncode != 0 or not esito.get('ok'):
            raise RuntimeError('la prova dell\'avvio nuovo non e\' riuscita')
    except Exception as e:
        registro('avvio nuovo %s scartato: %s' % (a.get('versione'), e))
        try:
            os.remove(nuovo)
        except OSError:
            pass
        return None
    try:
        if os.path.exists(vecchio):
            os.remove(vecchio)
        os.rename(io, vecchio)                  # Windows permette di rinominare un exe acceso
        try:
            os.rename(nuovo, io)
        except OSError:
            os.rename(vecchio, io)              # rimetto tutto com'era
            raise
    except OSError as e:
        registro('scambio dell\'avvio non riuscito: %s' % e)
        return None
    registro('avvio aggiornato alla %s (riserva: %s)' % (a.get('versione'), vecchio))
    return a.get('versione')


def aggiorna(info):
    """True se la versione nuova e' pronta (diventa attuale in prova al prossimo avvio del programma)."""
    b = Barra('Aggiornamento di CotW Italiano')
    try:
        b.esegui(lambda barra: installa_versione(info, barra))
    except Exception as e:
        avvisa('Aggiornamento non riuscito', 'Non sono riuscito ad aggiornare CotW Italiano alla versione %s:\n%s\n\n'
               'Il programma continua a funzionare come prima.' % (info.get('versione'), e), con_link=True)
        return False
    try:
        Barra('Aggiornamento di CotW Italiano').esegui(lambda barra: aggiorna_avvio(info, barra))
    except Exception as e:
        registro('aggiornamento dell\'avvio saltato: %s' % e)
    return True


def controlla_online(s, attuale, forza=False):
    """Controllo veloce (pochi secondi; senza internet si va avanti subito)."""
    online = leggi_online()
    if not online:
        return False
    info = versione_nuova(online, attuale, s.get('rotte') or [])
    if not info:
        return False
    rin = s.get('rinvio') or {}
    if not forza and rin.get('versione') == info['versione'] and time.time() < rin.get('fino', 0):
        return False
    novita = ''.join('\n - %s' % n for n in (info.get('novita') or [])[:6])
    if not forza and not chiedi('Aggiornamento di CotW Italiano',
                                'E\' uscita la versione %s di CotW Italiano (tu hai la %s).%s\n\nAggiorno adesso? '
                                'Ci vuole un minuto.' % (info['versione'], attuale,
                                                         ('\n\nNovita\':' + novita) if novita else '')):
        s['rinvio'] = {'versione': info['versione'], 'fino': time.time() + 86400}
        salva_stato(s)
        return False
    return aggiorna(info)


# ---------------- apertura del programma, con ritorno indietro ----------------
def apri(versione, argomenti, in_prova):
    cart = os.path.join(cartella_programmi(), versione)
    ok = os.path.join(cart, FILE_OK)
    if in_prova:
        try:
            os.remove(ok)
        except OSError:
            pass
    env = dict(os.environ)
    env['COTW_AVVIO'] = exe_avvio()
    env['COTW_AVVIO_VERSIONE'] = AVVIO_VERSIONE
    registro('apro %s %s%s' % (versione, ' '.join(argomenti), ' (in prova)' if in_prova else ''))
    try:
        p = subprocess.Popen([os.path.join(cart, NOME_EXE)] + list(argomenti), env=env)
    except OSError as e:                         # non parte proprio (file rovinato, bloccato dall'antivirus...)
        registro('la versione %s non si apre: %s' % (versione, e))
        return 'non si apre: %s' % e, 'rotta'
    if not in_prova:
        return p.wait(), None
    while True:
        codice = p.poll()
        if os.path.isfile(ok):
            return p.wait(), 'ok'
        if codice is not None:
            if os.path.isfile(ok):
                return codice, 'ok'
            return codice, ('rotta' if codice != 0 else None)
        time.sleep(0.3)


def torna_indietro(s, rotta, codice):
    s.setdefault('rotte', [])
    if rotta not in s['rotte']:
        s['rotte'].append(rotta)
    prec = s.get('precedente')
    s['in_prova'] = None
    s['attuale'] = prec if prec in versioni() else None
    s.pop('precedente', None)
    salva_stato(s)
    registro('versione %s rotta (codice %s): torno alla %s' % (rotta, codice, s.get('attuale')))
    avvisa('Versione nuova non partita', 'La versione %s di CotW Italiano non e\' partita (errore %s).\n\nTorno da solo '
           'alla versione di prima (%s): funziona come prima. L\'errore e\' stato segnato, la versione rotta non verra\' '
           'piu\' proposta.' % (rotta, codice, s.get('attuale') or '-'), con_link=not s.get('attuale'))


def esegui_programma(argomenti):
    s = leggi_stato()
    for _ in range(3):
        v = scegli_versione(s)
        if not v:
            avvisa('CotW Italiano', 'Non trovo il programma nella cartella di installazione:\n%s\n\nReinstallalo dal '
                   'sito ufficiale.' % cartella_programmi(), con_link=True)
            return 1
        in_prova = s.get('in_prova') == v
        codice, esito = apri(v, argomenti, in_prova)
        if esito == 'ok':
            s = leggi_stato()
            s['in_prova'] = None
            salva_stato(s)
            registro('versione %s confermata (sono ok)' % v)
            try:
                pulisci_vecchie(s)
                salva_stato(s)
            except Exception:
                pass
            return codice
        if esito == 'rotta':
            s = leggi_stato()
            if s.get('precedente') in versioni() or len([x for x in versioni() if x != v]) > 0:
                torna_indietro(s, v, codice)
                continue                        # riapre la precedente con gli stessi argomenti
            avvisa('CotW Italiano', 'Il programma non si apre (%s).\n\nReinstallalo dal sito ufficiale.' % codice,
                   con_link=True)
            return 1
        return codice
    return 1


# ---------------- prova dell'avvio (per lo scambio in due copie e per GitHub) ----------------
def prova_avvio(argv):
    i = argv.index('--prova-avvio')
    uscita = argv[i + 1] if len(argv) > i + 1 else 'prova_avvio.json'
    passi = []

    def passo(nome, fn):
        try:
            passi.append({'nome': nome, 'ok': True, 'info': fn()})
        except Exception as e:
            passi.append({'nome': nome, 'ok': False, 'errore': '%s: %s' % (type(e).__name__, e)})
    passo('certificati inclusi', lambda: __import__('certifi').where())
    passo('verifica firme', lambda: firma.verifica_ed25519(b'\0' * 32, b'', b'\0' * 64) is False and 'ok')
    if '--senza-internet' not in argv:
        def online():
            o = leggi_online(timeout=30)
            if not firma.firmato(o.get('servizi') or {}):
                raise RuntimeError('online.json non letto o firma non verificata')
            return 'programma online %s' % (o.get('programma') or {}).get('versione')
        passo('online.json + firma', online)
    if IS_WIN and not os.environ.get('COTW_AVVIO_SENZA_TK'):
        def finestre():
            import tkinter
            r = tkinter.Tk()
            r.withdraw()
            r.update()
            r.destroy()
            return 'tk %s' % tkinter.TkVersion
        passo('finestre (tkinter)', finestre)
    ok = all(p['ok'] for p in passi)
    with open(uscita, 'w', encoding='utf-8') as f:
        json.dump({'avvio': AVVIO_VERSIONE, 'ok': ok, 'passi': passi}, f, ensure_ascii=False, indent=1)
    return 0 if ok else 1


# ---------------- ingresso ----------------
def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if '--prova-avvio' in argv:
        return prova_avvio(argv)
    argomenti = argv[1:]
    try:
        s = leggi_stato()
        v = scegli_versione(s)
        if '--aggiorna' in argomenti:            # richiesto dal programma (pulsante Aggiorna)
            argomenti = [a for a in argomenti if a != '--aggiorna']
            controlla_online(s, v or '0', forza=True)
        elif v and (not argomenti or argomenti[0] == '--gioco'):
            controlla_online(s, v)               # apertura normale o tasto Gioca: controllo veloce
    except Exception as e:                       # l'aggiornamento non deve MAI impedire di aprire il programma
        registro('controllo aggiornamenti saltato: %s' % e)
    return esegui_programma(argomenti)
