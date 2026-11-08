"""PROVA AUTOMATICA prima di pubblicare (la lancia .github/workflows/crea_exe.yml dopo aver costruito l'exe).
Se una sola prova fallisce, la versione NON viene pubblicata.
  1. exe appena costruito, internet vero: parte, ha tutti i pezzi, GitHub con i soli certificati suoi, firme vere ok.
  2. exe appena costruito: sa aggiornarsi a una versione FINTA piu' nuova (99.0.0 e, in anteprima, 99.1.0).
     online.json finto, firmato con una chiave di prova creata adesso, servito da un piccolo server sul PC di prova
     che offre lo zip e l'installer appena costruiti.
  3. (Windows, se c'e' l'installer) installazione silenziosa in una cartella di prova e prova 1 sull'exe installato.
  4. (Windows) AVVIO separato: prova di se stesso; aggiornamento completo tramite l'avvio (scarica la versione finta,
     si aggiorna da solo in due copie, apre la versione nuova che dice "sono ok"); ritorno indietro automatico da una
     versione finta ROTTA (che si chiude con un errore) alla versione buona.
Uso: python strumenti/prova_aggiornamento.py [--exe "dist/CotW Italiano/CotW Italiano.exe"] [--senza-installer]
     (--exe python = usa CotW_Italiano.py con Python, per provare sul PC senza costruire)"""
import os
import sys
import json
import shutil
import argparse
import tempfile
import threading
import subprocess
import functools
import http.server

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)
from cotw.core import firma  # noqa: E402


def comando(exe):
    if exe == 'python':
        return [sys.executable, os.path.join(RADICE, 'CotW_Italiano.py')]
    return [os.path.abspath(exe)]


def lancia(nome, cmd, env_extra, cartella):
    rapporto = os.path.join(cartella, 'rapporto_%s.json' % nome)
    env_extra = dict(env_extra)
    extra = env_extra.pop('_ARG', [])
    env = dict(os.environ)
    env.update(env_extra)
    env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    print('\n=== PROVA: %s ===' % nome, flush=True)
    try:
        r = subprocess.run(cmd + ['--prova', rapporto] + extra, env=env, timeout=600,
                           capture_output=True, text=True)
        codice = r.returncode
        coda = ((r.stdout or '') + (r.stderr or ''))[-3000:]
    except subprocess.TimeoutExpired:
        codice, coda = -1, 'TEMPO SCADUTO (10 minuti)'
    try:
        rap = json.load(open(rapporto, encoding='utf-8'))
    except Exception:
        rap = None
    if not rap:
        print('NESSUN RAPPORTO (il programma non e\' nemmeno partito?) codice %s\n%s' % (codice, coda))
        return False
    for p in rap['passi']:
        print('  [%s] %s  (%ss)  %s' % ('OK' if p['ok'] else 'ERRORE', p['nome'], p['secondi'],
                                        p.get('info') if p['ok'] else p['errore']))
        if not p['ok']:
            print(p.get('dettaglio', ''))
    ok = bool(rap.get('ok')) and codice == 0
    print('  => %s (versione %s, codice %s)' % ('PROVA SUPERATA' if ok else 'PROVA FALLITA', rap.get('versione'), codice))
    return ok


def server(cartella):
    class Silenzioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Silenzioso, directory=cartella)
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, 'http://127.0.0.1:%d' % s.server_address[1]


def online_finto(dist, base, privata):
    info = json.load(open(os.path.join(dist, 'programma.json'), encoding='utf-8'))
    avvio = None
    if info.get('avvio'):
        avvio = {'versione': '999', 'url': '%s/avvio/CotW%%20Italiano.exe' % base, 'sha256': info['avvio']['sha256']}
    blocco = {'versione': '99.0.0', 'url': '%s/%s' % (base, info['zip']), 'sha256': info['sha256'],
              'dimensione': info['dimensione'], 'novita': ['versione finta per la prova automatica']}
    if info.get('setup'):
        blocco['setup_url'] = '%s/%s' % (base, info['setup'])
        blocco['setup_sha256'] = info['setup_sha256']
    if avvio:
        blocco['avvio'] = avvio
    return {'programma': firma.firma(blocco, privata),
            'anteprima': firma.firma(dict(blocco, versione='99.1.0'), privata)}


def _stato(app):
    try:
        return json.load(open(os.path.join(app, 'programma', 'stato.json'), encoding='utf-8'))
    except Exception:
        return {}


def prove_avvio(dist, lavoro, base, pubblica, risultati):
    """Regole 1-3 con l'avvio vero, in una cartella di installazione finta."""
    info = json.load(open(os.path.join(dist, 'programma.json'), encoding='utf-8'))
    avvio = os.path.join(dist, 'avvio', 'CotW Italiano.exe')
    print('\n=== PROVA: avvio, prova di se stesso ===', flush=True)
    rap = os.path.join(lavoro, 'avvio_se_stesso.json')
    r = subprocess.run([avvio, '--prova-avvio', rap], timeout=300, env=dict(os.environ, COTW_DATI=os.path.join(lavoro, 'd4')))
    try:
        esito = json.load(open(rap, encoding='utf-8'))
    except Exception:
        esito = {}
    for p in esito.get('passi', []):
        print('  [%s] %s  %s' % ('OK' if p['ok'] else 'ERRORE', p['nome'], p.get('info') if p['ok'] else p['errore']))
    risultati['avvio: prova di se stesso'] = r.returncode == 0 and bool(esito.get('ok'))

    app = os.path.join(lavoro, 'app')
    shutil.copytree(os.path.join(dist, 'CotW Italiano'), os.path.join(app, 'programma', info['versione']))
    shutil.copy(avvio, os.path.join(app, 'CotW Italiano.exe'))
    env = {'COTW_AVVIO_PROVA': '1', 'COTW_AVVIO_SENZA_TK': '1', 'COTW_DATI': os.path.join(lavoro, 'd5'),
           'COTW_URL_ONLINE': base + '/_prova/online.json', 'COTW_AVVIO_CHIAVE_PROVA': pubblica}
    ok = lancia('avvio_aggiorna', [os.path.join(app, 'CotW Italiano.exe'), '--aggiorna'],
                dict(env, _ARG=['--prova-chiave', pubblica]), lavoro)
    st = _stato(app)
    print('  stato dopo:', st)
    ok = ok and st.get('attuale') == '99.0.0' and not st.get('in_prova') and st.get('precedente') == info['versione']
    scambio = os.path.isfile(os.path.join(app, 'CotW Italiano.old.exe'))
    print('  avvio aggiornato in due copie (riserva .old.exe):', scambio)
    risultati['avvio: aggiorna il programma e se stesso'] = ok and scambio

    rotta = os.path.join(app, 'programma', '99.5.0')
    os.makedirs(rotta)
    shutil.copy(os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'where.exe'),
                os.path.join(rotta, 'CotW Italiano.exe'))       # "programma" che si chiude subito con un errore
    env.pop('COTW_URL_ONLINE')
    env['COTW_DATI'] = os.path.join(lavoro, 'd6')
    ok = lancia('avvio_ritorno', [os.path.join(app, 'CotW Italiano.exe')], env, lavoro)
    st = _stato(app)
    print('  stato dopo:', st)
    risultati['avvio: torna da solo indietro da una versione rotta'] = (
        ok and st.get('attuale') == '99.0.0' and '99.5.0' in (st.get('rotte') or []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=os.path.join(RADICE, 'dist', 'CotW Italiano', 'CotW Italiano.exe'))
    ap.add_argument('--dist', default=os.path.join(RADICE, 'dist'))
    ap.add_argument('--senza-installer', action='store_true')
    a = ap.parse_args()
    cmd = comando(a.exe)
    lavoro = tempfile.mkdtemp(prefix='cotw_prova_')
    risultati = {}

    # 1. internet vero
    risultati['programma appena costruito (internet vero)'] = lancia(
        'reale', cmd, {'COTW_DATI': os.path.join(lavoro, 'dati1')}, lavoro)

    # 2. aggiornamento a una versione finta piu' nuova
    privata, pubblica = firma.nuova_coppia()
    srv, base = server(a.dist)
    try:
        os.makedirs(os.path.join(a.dist, '_prova'), exist_ok=True)
        json.dump(online_finto(a.dist, base, privata), open(os.path.join(a.dist, '_prova', 'online.json'), 'w'))
        risultati['si aggiorna a una versione piu\' nuova'] = lancia(
            'aggiornamento', cmd, {'COTW_DATI': os.path.join(lavoro, 'dati2'),
                                   'COTW_URL_ONLINE': base + '/_prova/online.json',
                                   '_ARG': ['--prova-chiave', pubblica]}, lavoro)
        if sys.platform == 'win32' and os.path.isfile(os.path.join(a.dist, 'avvio', 'CotW Italiano.exe')):
            prove_avvio(a.dist, lavoro, base, pubblica, risultati)
    finally:
        srv.shutdown()
        shutil.rmtree(os.path.join(a.dist, '_prova'), ignore_errors=True)

    # 3. installer silenzioso + exe installato
    info = json.load(open(os.path.join(a.dist, 'programma.json'), encoding='utf-8'))
    if sys.platform == 'win32' and info.get('setup') and not a.senza_installer:
        dest = os.path.join(lavoro, 'installato')
        print('\n=== PROVA: installer silenzioso in %s ===' % dest, flush=True)
        r = subprocess.run([os.path.join(a.dist, info['setup']), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                            '/CURRENTUSER', '/TASKS=', '/DIR=' + dest], timeout=600)
        exe = os.path.join(dest, 'CotW Italiano.exe')
        if r.returncode != 0 or not os.path.isfile(exe):
            print('  => INSTALLER FALLITO (codice %s)' % r.returncode)
            risultati['installer'] = False
        else:
            risultati['installer + programma installato'] = lancia(
                'installato', [exe], {'COTW_DATI': os.path.join(lavoro, 'dati3')}, lavoro)
            un = os.path.join(dest, 'unins000.exe')
            if os.path.isfile(un):
                subprocess.run([un, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], timeout=300)

    print('\n================ RIEPILOGO ================')
    for k, v in risultati.items():
        print('  %s  %s' % ('OK    ' if v else 'ERRORE', k))
    if not all(risultati.values()):
        print('\nPROVA FALLITA: la versione NON viene pubblicata.')
        sys.exit(1)
    print('\nTutte le prove superate.')


if __name__ == '__main__':
    main()
