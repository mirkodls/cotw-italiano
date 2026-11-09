"""PROVA AUTOMATICA del programma (la usa GitHub prima di pubblicare ogni versione: .github/workflows/crea_exe.yml).
Regola: una versione che non sa aggiornarsi NON deve uscire. L'exe appena costruito si avvia con
    "CotW Italiano.exe" --prova <rapporto.json> [--prova-chiave <pubblica_hex>]
e controlla, senza finestre e senza toccare niente sul PC:
  1. che tutti i pezzi del programma ci siano (moduli, Qt, certificati) e che parta;
  2. che si colleghi a GitHub usando SOLO i certificati che porta con se' (il problema della 0.5.9);
  3. che legga online.json e versione.json veri e ne verifichi la firma dell'autore;
  4. (con --prova-chiave) che sappia aggiornarsi a una versione FINTA piu' nuova (99.0.0): la trova, la scarica,
     controlla impronta e firma (chiave di prova creata solo per questa prova), la estrae e prepara lo script.
Scrive un rapporto JSON e finisce con 0 se tutto e' a posto, 1 se qualcosa non va.
La chiave di prova vale solo dentro questa prova: il programma normale non la usa mai."""
import os
import sys
import json
import time
import traceback


def _passo(rapporto, nome, fn):
    t = time.time()
    try:
        info = fn()
        rapporto['passi'].append({'nome': nome, 'ok': True, 'info': info, 'secondi': round(time.time() - t, 1)})
    except Exception as e:
        rapporto['passi'].append({'nome': nome, 'ok': False, 'errore': '%s: %s' % (type(e).__name__, e),
                                  'dettaglio': traceback.format_exc()[-2000:], 'secondi': round(time.time() - t, 1)})


def _moduli():
    import importlib
    nomi = ['cotw.core.' + n for n in ('aggiornamenti', 'archivi', 'avvio', 'contribuisci', 'diagnosi', 'firma',
                                       'installa', 'missioni', 'percorsi', 'programma', 'quad', 'rete', 'scorciatoia',
                                       'segnala')]
    nomi += ['cotw.ui.' + n for n in ('aggiorna_programma', 'compagno', 'finestra', 'prima_di_giocare', 'stile',
                                      'tutorial')]
    for n in nomi:
        importlib.import_module(n)
    return '%d moduli' % len(nomi)


def _qt():
    from PySide6.QtWidgets import QApplication, QDialog
    app = QApplication.instance() or QApplication([sys.argv[0], '-platform', 'offscreen'])
    from cotw.ui import stile
    app.setStyleSheet(stile.QSS)
    d = QDialog()
    d.show()
    app.processEvents()
    d.close()
    return app.platformName()


def _processi():
    """Elenco dei programmi aperti chiesto direttamente a Windows: deve contenere almeno questo programma."""
    from cotw.core import percorsi
    if sys.platform != 'win32':
        return 'non Windows'
    p = percorsi.processi_attivi()
    io = os.path.basename(sys.executable).lower()
    if not p or io not in p:
        raise RuntimeError('elenco dei programmi aperti sbagliato (%d, %s non c\'e\')' % (len(p), io))
    return '%d programmi aperti' % len(p)


def _certificati():
    """Solo i certificati inclusi nel programma (certifi), come su un Windows a cui mancano: deve funzionare lo stesso."""
    import ssl
    import certifi
    import urllib.request
    from cotw.core import rete
    ctx = ssl.create_default_context(cafile=certifi.where())
    op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    out = []
    for url in ('https://github.com/', 'https://api.github.com/', rete.url_online(), rete.url_manifest()):
        with op.open(urllib.request.Request(url, headers={'User-Agent': 'CotW-Italiano-prova'}), timeout=30) as r:
            r.read(1024)
            out.append('%s %s' % (r.status, url.split('/')[2]))
    return out


def _online_vero():
    from cotw.core import rete, firma
    o = rete.leggi_online(timeout=30)
    if not o:
        raise RuntimeError('online.json non si legge')
    if not firma.firmato(o.get('servizi') or {}):
        raise RuntimeError('il blocco "servizi" di online.json non risulta firmato: la verifica della firma non funziona')
    return 'programma online %s' % (o.get('programma') or {}).get('versione')


def _manifest_vero():
    from cotw.core import rete
    m = rete.leggi_manifest(timeout=30)
    if not m:
        raise RuntimeError('versione.json non c\'e\'')
    return 'mod %s firmata' % m.get('versione')


def _aggiorna_a_finta(chiave):
    """Regola 5(b): questa versione sa aggiornarsi a una ancora piu' nuova. online.json finto (COTW_URL_ONLINE) firmato
    con la chiave di prova, che punta allo zip e all'installer appena costruiti."""
    from cotw.core import rete, programma, percorsi
    o = rete.leggi_online(timeout=30)
    if not o:
        raise RuntimeError('online.json di prova non si legge (%s)' % rete.url_online())
    out = []
    for canale in ('normale', 'anteprima'):
        info = programma.disponibile(o, chiavi=[chiave], canale_scelto=canale)
        if not info or info['versione'] != ('99.0.0' if canale == 'normale' else '99.1.0'):
            raise RuntimeError('canale %s: la versione finta non viene proposta (%r)' % (canale, info))
        out.append('%s -> %s' % (canale, info['versione']))
    if programma.disponibile(o, canale_scelto='normale'):
        raise RuntimeError('una versione firmata con una chiave sconosciuta viene accettata!')
    falsa = dict(o['programma'], versione='99.9.9')
    if programma.disponibile({'programma': falsa}, chiavi=[chiave], canale_scelto='normale'):
        raise RuntimeError('una versione modificata dopo la firma viene accettata!')
    info = programma.disponibile(o, chiavi=[chiave], canale_scelto='normale')
    # con l'installer (come gli utenti su Windows)
    if info.get('setup_url') and sys.platform == 'win32':
        sp = programma.prepara(info)
        if not (os.path.isfile(sp) and sp.lower().endswith('.exe')):
            raise RuntimeError('installer non preparato: %s' % sp)
        righe, _ = programma.script_aggiornamento(sp, os.path.join(percorsi.dati_app(), 'finto_programma'), ['--gioco'],
                                                  pid=1234, gia_installato=True)
        if not any('/SILENT' in r for r in righe) or not righe[-1].startswith('start'):
            raise RuntimeError('script di aggiornamento strano: %r' % righe)
        out.append('installer ok (%d MB)' % (os.path.getsize(sp) >> 20))
    # con lo zip (programma estratto a mano)
    solo_zip = {k: v for k, v in info.items() if not k.startswith('setup')}
    cart = programma.prepara(solo_zip)
    if not os.path.isfile(os.path.join(cart, programma.NOME_EXE)):
        raise RuntimeError('nello zip estratto manca l\'exe')
    out.append('zip ok')
    # impronta sbagliata: deve rifiutare
    rotto = dict(solo_zip, sha256='0' * 64)
    try:
        programma.prepara(rotto)
    except RuntimeError:
        out.append('impronta sbagliata rifiutata')
    else:
        raise RuntimeError('un file con l\'impronta sbagliata viene accettato!')
    # ultima spiaggia
    cfg = percorsi.leggi_config()
    cfg['agg_tentativo'] = {'da': '0.0.1', 'a': '0.0.2', 'quando': 0}
    percorsi.salva_config(cfg)
    if programma.controlla_esito() != 'ok':
        raise RuntimeError('controllo dopo l\'aggiornamento sbagliato')
    cfg = percorsi.leggi_config()
    cfg['agg_tentativo'] = {'da': '0', 'a': '99.0.0', 'quando': 0}
    percorsi.salva_config(cfg)
    programma.controlla_esito()
    programma.segna_fallito('prova')
    if programma.stato_a_mano(o, [chiave]) != 'falliti':
        raise RuntimeError('dopo 2 aggiornamenti falliti non propone di scaricare a mano')
    out.append('ultima spiaggia ok')
    return out


def esegui(argv):
    i = argv.index('--prova')
    uscita = argv[i + 1] if len(argv) > i + 1 and not argv[i + 1].startswith('--') else 'prova_rapporto.json'
    chiave = argv[argv.index('--prova-chiave') + 1] if '--prova-chiave' in argv else None
    from cotw import VERSIONE
    rapporto = {'versione': VERSIONE, 'exe': sys.executable, 'passi': []}
    _passo(rapporto, 'pezzi del programma (moduli)', _moduli)
    _passo(rapporto, 'finestre (Qt)', _qt)
    _passo(rapporto, 'programmi aperti (Windows)', _processi)
    if chiave:
        _passo(rapporto, 'aggiornamento a una versione finta piu\' nuova', lambda: _aggiorna_a_finta(chiave))
    else:
        _passo(rapporto, 'GitHub con i soli certificati del programma', _certificati)
        _passo(rapporto, 'online.json vero + firma', _online_vero)
        _passo(rapporto, 'versione.json vero + firma', _manifest_vero)
    rapporto['ok'] = all(p['ok'] for p in rapporto['passi'])
    rapporto['con_avvio'] = bool(os.environ.get('COTW_AVVIO'))
    if rapporto['ok']:
        from cotw.core import programma
        programma.segna_ok()
    with open(uscita, 'w', encoding='utf-8') as f:
        json.dump(rapporto, f, ensure_ascii=False, indent=1)
    return 0 if rapporto['ok'] else 1
