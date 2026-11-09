"""PROVE DEL CODICE (senza finestre, senza il gioco vero): le parti delicate del programma su cartelle finte.
Le lancia GitHub prima di costruire l'exe (crea_exe.yml); si possono lanciare anche sul PC:
    python strumenti/prove_codice.py
Se una prova fallisce esce con codice 1 e scrive quale."""
import os
import sys
import json
import time
import shutil
import struct
import zipfile
import hashlib
import tempfile
import threading
import functools
import traceback
import http.server

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)
LAVORO = tempfile.mkdtemp(prefix='cotw_prove_')
os.environ['COTW_DATI'] = os.path.join(LAVORO, 'dati')

from cotw.core import firma, installa, aggiornamenti, rete, archivi, quad, avvio, programma, percorsi  # noqa: E402

PRIV, PUB = firma.nuova_coppia()
firma.CHIAVI_PUBBLICHE.append(PUB)            # chiave di prova, solo in questo processo
RISULTATI = []


def prova(fn):
    t = time.time()
    try:
        fn()
        RISULTATI.append((fn.__name__, True, ''))
        print('  OK      %s (%.1fs)' % (fn.__name__, time.time() - t), flush=True)
    except Exception:
        RISULTATI.append((fn.__name__, False, traceback.format_exc()))
        print('  ERRORE  %s\n%s' % (fn.__name__, traceback.format_exc()), flush=True)
    return fn


def _scrivi(p, dati):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(dati)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------- server finto (con Range e con "caduta" della connessione a comando) ----------------
CADUTE = {}                                    # nome file -> quante volte far cadere la connessione a meta'


class Server(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.translate_path(self.path)
        if not os.path.isfile(p):
            return self.send_error(404)
        dati = open(p, 'rb').read()
        inizio = 0
        rng = self.headers.get('Range')
        if rng and rng.startswith('bytes='):
            inizio = int(rng[6:].split('-')[0])
            if inizio >= len(dati):
                return self.send_error(416)
            self.send_response(206)
        else:
            self.send_response(200)
        corpo = dati[inizio:]
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        nome = os.path.basename(p)
        if CADUTE.get(nome):
            CADUTE[nome] -= 1
            self.wfile.write(corpo[:len(corpo) // 2])
            self.wfile.flush()
            self.connection.shutdown(2)          # connessione che cade a meta'
            return
        self.wfile.write(corpo)


SRV_DIR = os.path.join(LAVORO, 'server')
os.makedirs(SRV_DIR)
_srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Server, directory=SRV_DIR))
threading.Thread(target=_srv.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:%d' % _srv.server_address[1]


# ---------------- pubblicazione finta della mod ----------------
def _pubblica(versione, file_audio, file_testo, piccoli=()):
    """Crea in SRV_DIR/<tag>/ i pacchetti e versione.json firmato (come lo strumento Pubblica)."""
    tag = 'v' + versione
    d = os.path.join(SRV_DIR, tag)
    os.makedirs(d, exist_ok=True)
    comp = {}
    for nome, files in (('audio', file_audio), ('testo', file_testo)):
        zp = os.path.join(d, '%s_%s.zip' % (nome, versione))
        with zipfile.ZipFile(zp, 'w') as z:
            for rel, b in files.items():
                z.writestr('dropzone/' + rel, b)
        pacchetti = [{'nome': os.path.basename(zp), 'tag': tag, 'sha256': _sha(open(zp, 'rb').read()),
                      'dimensione': os.path.getsize(zp), 'contiene': 'tutto'}]
        for ptag, pnome, prel in piccoli if nome == 'audio' else ():
            pacchetti.append({'nome': pnome, 'tag': ptag, 'sha256': _sha(open(os.path.join(SRV_DIR, ptag, pnome), 'rb').read()),
                              'dimensione': os.path.getsize(os.path.join(SRV_DIR, ptag, pnome)), 'contiene': prel})
        comp[nome] = {'versione': versione, 'file': {r: _sha(b) for r, b in files.items()}, 'pacchetti': pacchetti}
    m = firma.firma({'versione': versione, 'componenti': comp}, PRIV)
    with open(os.path.join(d, 'versione.json'), 'w') as f:
        json.dump(m, f)
    return m


def _piccolo(versione, files):
    tag = 'v' + versione
    d = os.path.join(SRV_DIR, tag)
    os.makedirs(d, exist_ok=True)
    nome = 'audio_aggiornamento_%s.zip' % versione
    with zipfile.ZipFile(os.path.join(d, nome), 'w') as z:
        for rel, b in files.items():
            z.writestr('dropzone/' + rel, b)
    return tag, nome, sorted(files)


os.environ['COTW_URL_ASSET'] = BASE + '/'


def _voci(n, pref=b'v1'):
    return {'sound/dialogue/eng/b%03d.wavc' % i: pref + b'-%03d-' % i + os.urandom(64) for i in range(n)}


TESTO = {'settings/hp_settings/string_ids.stringlookup': b'testo-it-1', 'ui/ui_localization.stringlookup': b'ui-it-1'}


# ======================================= PROVE =======================================
@prova
def installa_e_rimuovi_rispettando_altre_mod():
    dz = os.path.join(LAVORO, 'g1', 'dropzone')
    pac = os.path.join(LAVORO, 'pac1')
    voci = _voci(30)
    for rel, b in voci.items():
        _scrivi(os.path.join(pac, 'mod audio ita', 'dropzone', *rel.split('/')), b)
    altra = os.path.join(dz, 'sound', 'dialogue', 'eng', 'b005.wavc')
    _scrivi(altra, b'FILE DI UN ALTRA MOD')
    n, copiati = installa.installa('audio', pac, dz)
    assert n == 30 and copiati == 30, (n, copiati)
    assert open(altra, 'rb').read() == voci['sound/dialogue/eng/b005.wavc']
    t = time.time()
    n, copiati = installa.installa('audio', pac, dz)        # seconda volta: niente da copiare, veloce
    assert copiati == 0, copiati
    assert installa.stato_componente(dz, 'audio')[0] == 'installato'
    installa.rimuovi('audio', dz)
    assert open(altra, 'rb').read() == b'FILE DI UN ALTRA MOD', 'il file dell\'altra mod non e\' tornato'
    assert sorted(os.listdir(os.path.dirname(altra))) == ['b005.wavc']


@prova
def installazione_interrotta_non_perde_niente():
    dz = os.path.join(LAVORO, 'g2', 'dropzone')
    pac = os.path.join(LAVORO, 'pac2')
    v1 = _voci(40)
    for rel, b in v1.items():
        _scrivi(os.path.join(pac, 'mod audio ita', 'dropzone', *rel.split('/')), b)
    installa.installa('audio', pac, dz, versione='1')
    shutil.rmtree(pac)
    v2 = _voci(40, b'v2')
    for rel, b in v2.items():
        _scrivi(os.path.join(pac, 'mod audio ita', 'dropzone', *rel.split('/')), b)
    conta = {'n': 0}

    def fermati():
        conta['n'] += 1
        return conta['n'] > 10
    installa.installa('audio', pac, dz, fermati=fermati, versione='2')
    st = installa.leggi_stato()['componenti']['audio']
    assert len(st['file']) == 40, len(st['file'])
    assert st.get('incompleto') and st.get('versione') == '1', st.get('versione')
    installa.installa('audio', pac, dz, versione='2')         # ripresa: deve finire senza backup sbagliati
    st = installa.leggi_stato()['componenti']['audio']
    assert st['versione'] == '2' and not st['backup'] and not st.get('incompleto'), st['backup']
    for rel, b in v2.items():
        assert open(os.path.join(dz, *rel.split('/')), 'rb').read() == b


@prova
def aggiornamenti_dalla_base_e_poi_piccoli():
    voci1 = _voci(25)
    m1 = _pubblica('1.0.0', voci1, TESTO)
    dz = os.path.join(LAVORO, 'g3', 'dropzone')
    os.makedirs(dz)
    for comp in ('audio', 'testo'):
        aggiornamenti.aggiorna_componente(m1, comp, dz)
    assert aggiornamenti.confronta(m1, dz) == {'audio': ('1.0.0', '1.0.0', 'aggiornato'),
                                               'testo': ('1.0.0', '1.0.0', 'aggiornato')}
    # 1.0.1 cambia 2 voci, 1.0.2 ne cambia altre 2: chi ha la 1.0.0 deve scaricare SOLO i due piccoli
    voci2 = dict(voci1)
    ch1 = {k: b'new1' + os.urandom(8) for k in list(voci1)[:2]}
    voci2.update(ch1)
    p1 = _piccolo('1.0.1', ch1)
    voci3 = dict(voci2)
    ch2 = {k: b'new2' + os.urandom(8) for k in list(voci1)[5:7]}
    voci3.update(ch2)
    p2 = _piccolo('1.0.2', ch2)
    m3 = _pubblica('1.0.2', voci3, TESTO, piccoli=[p1, p2])
    servono = aggiornamenti.mancanti(m3, 'audio')
    scelti = aggiornamenti.scegli_pacchetti(m3, 'audio', servono)
    assert [p['nome'] for p in scelti] == [p1[1], p2[1]], [p['nome'] for p in scelti]
    aggiornamenti.aggiorna_componente(m3, 'audio', dz)
    for rel, b in voci3.items():
        assert open(os.path.join(dz, *rel.split('/')), 'rb').read() == b, rel
    # un file cambiato due volte: il piccolo vecchio non basta, la base completa si'
    voci4 = dict(voci3)
    k = list(voci1)[0]
    voci4[k] = b'new4'
    m4 = _pubblica('1.0.4', voci4, TESTO, piccoli=[p1])       # p1 ha k ma con il contenuto vecchio
    aggiornamenti.aggiorna_componente(m4, 'audio', dz)
    assert open(os.path.join(dz, *k.split('/')), 'rb').read() == b'new4'


@prova
def scaricamento_che_riprende_se_cade():
    dati = os.urandom(3 * 1024 * 1024)
    _scrivi(os.path.join(SRV_DIR, 'grande.bin'), dati)
    CADUTE['grande.bin'] = 2
    dest = os.path.join(LAVORO, 'scaricati', 'grande.bin')
    rete.scarica(BASE + '/grande.bin', dest, _sha(dati))
    assert open(dest, 'rb').read() == dati
    try:
        rete.scarica(BASE + '/grande.bin', dest + '2', '0' * 64)
    except RuntimeError as e:
        assert 'rovinato' in str(e)
    else:
        raise AssertionError('impronta sbagliata accettata')
    assert not os.path.exists(dest + '2.part')


@prova
def ricerca_negli_archivi():
    g = os.path.join(LAVORO, 'g4')
    h = archivi.hashlittle(quad.INTERNO)
    voci = [(i * 7 + 1, i * 10, 5) for i in range(5000)]
    voci[10] = (99, h, 3)                       # l'impronta compare in una posizione sbagliata: va ignorata
    voci[4000] = (h, 4000, 6)
    _scrivi(os.path.join(g, 'archives_win64', 'game0.tab'), b'\0' * 12 + b''.join(struct.pack('<III', *v) for v in voci))
    _scrivi(os.path.join(g, 'archives_win64', 'game0.arc'), b'x' * 4000 + b'BANCO!' + b'y' * 10)
    assert archivi.leggi(g, quad.INTERNO) == b'BANCO!'


def _banco():
    rec = b'\1' * 34
    evento = b'IBSB' + struct.pack('<I', len(rec)) + rec + b'BUS ' + b'\0' * 4 + b'\0' * 11 + struct.pack('<f', 0.0) + b'\0' * 8
    return b'RIFF' + b'\0' * 4 + b'FEV ' + evento * 3


@prova
def volume_quad_non_cancella_altre_mod():
    g = os.path.join(LAVORO, 'g5')
    banco = _banco()
    h = archivi.hashlittle(quad.INTERNO)
    _scrivi(os.path.join(g, 'archives_win64', 'game0.tab'), b'\0' * 12 + struct.pack('<III', h, 0, len(banco)))
    _scrivi(os.path.join(g, 'archives_win64', 'game0.arc'), banco)
    dz = os.path.join(g, 'dropzone')
    f = quad.file_dropzone(dz)
    _scrivi(f, b'BANCO DI UN ALTRA MOD')
    assert quad.applica(g, dz, 50) == 3
    assert quad.volume_attuale(dz) == 50
    quad.ripristina(dz, g)
    assert open(f, 'rb').read() == b'BANCO DI UN ALTRA MOD'
    # senza altre mod: applica e ripristina toglie il file
    os.remove(f)
    quad.applica(g, dz, 30)
    quad.ripristina(dz, g)
    assert not os.path.exists(f)


@prova
def opzioni_di_avvio_steam():
    testo = ('"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"apps"\n'
             '\t\t\t\t{\n\t\t\t\t\t"518790"\n\t\t\t\t\t{\n\t\t\t\t\t\t"LaunchOptions"\t\t"-windowed \\"x\\""\n'
             '\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n')
    f = os.path.join(LAVORO, 'steam', 'userdata', '1', 'config', 'localconfig.vdf')
    _scrivi(f, testo.encode())
    vecchi = avvio.file_config_steam, avvio.steam_in_esecuzione
    avvio.file_config_steam = lambda: [f]
    avvio.steam_in_esecuzione = lambda: False
    try:
        assert avvio.stato_steam()[0] == 'diverse'
        avvio.imposta_steam(controllo_exe=r'C:\P\CotW Italiano.exe')
        st, v = avvio.stato_steam()
        assert st == 'impostate' and v.startswith('"C:\\P\\CotW Italiano.exe" --gioco %command% -windowed "x"'), v
        assert avvio.controllo_attivo(v) == r'C:\P\CotW Italiano.exe'
        avvio.imposta_steam(togli=True)
        st, v = avvio.stato_steam()
        assert v == '-windowed "x"', v
    finally:
        avvio.file_config_steam, avvio.steam_in_esecuzione = vecchi


@prova
def aggiornamenti_del_programma_e_ultima_spiaggia():
    blocco = firma.firma({'versione': '99.0.0', 'url': 'x', 'sha256': 'y'}, PRIV)
    assert programma.disponibile({'programma': blocco}, canale_scelto='normale')['versione'] == '99.0.0'
    rotto = dict(blocco, versione='99.0.1')
    assert programma.disponibile({'programma': rotto}, canale_scelto='normale') is None
    ant = firma.firma({'versione': '99.5.0', 'url': 'x', 'sha256': 'y'}, PRIV)
    o = {'programma': blocco, 'anteprima': ant}
    assert programma.disponibile(o, canale_scelto='normale')['versione'] == '99.0.0'
    assert programma.disponibile(o, canale_scelto='anteprima')['versione'] == '99.5.0'
    cfg = percorsi.leggi_config()
    cfg['agg_falliti'] = 2
    percorsi.salva_config(cfg)
    assert programma.stato_a_mano(o) == 'falliti'


@prova
def percorsi_pericolosi_rifiutati():
    for cattivo in ('../x', 'a/../../b', 'C:/Windows/x', '/etc/x', 'a\\..\\b', ''):
        assert not firma.percorso_sicuro(cattivo), cattivo
    assert firma.percorso_sicuro('sound/dialogue/eng/x.wavc')


print('\n%d prove, %d errori' % (len(RISULTATI), sum(1 for r in RISULTATI if not r[1])))
_srv.shutdown()
shutil.rmtree(LAVORO, ignore_errors=True)
sys.exit(0 if all(r[1] for r in RISULTATI) else 1)
