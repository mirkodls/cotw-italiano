"""DIAGNOSI della connessione: quando il programma "non si collega", questo dice PERCHE'.
Prova uno per uno: DNS, GitHub (raw e api), il servizio delle segnalazioni, l'orologio del PC, il proxy di Windows.
Per ogni prova: esito, dettaglio tecnico (l'errore vero) e un consiglio in italiano. Scrive anche un rapporto in
dati_app()\\diagnosi_rete.txt da incollare su Discord."""
import os
import ssl
import sys
import time
import socket
import platform
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from . import rete, percorsi

PROVE = [
    ('DNS GitHub', 'raw.githubusercontent.com'),
    ('DNS API GitHub', 'api.github.com'),
    ('DNS GitHub download', 'github.com'),
]
URL = [
    ('GitHub: impostazioni (online.json)', lambda: rete.url_online()),
    ('GitHub: versioni (api)', lambda: 'https://api.github.com/repos/%s/releases/latest' % rete.REPO),
    ('GitHub: download', lambda: 'https://github.com/%s' % rete.REPO),
]


def _consiglio(e):
    t = ('%s: %s' % (type(e).__name__, e)).lower()
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (403, 429):
            return 'GitHub ha rifiutato (troppe richieste da questa rete o blocco). Riprova tra qualche minuto.'
        if e.code == 407:
            return 'Un PROXY chiede la password: controlla le impostazioni proxy di Windows.'
        return 'Risposta inattesa dal server (%d). Riprova piu\' tardi.' % e.code
    if 'certificate' in t or 'ssl' in t:
        return ('Certificato HTTPS non valido: o l\'ORA del PC e\' sbagliata, o un antivirus/proxy "ispeziona" il traffico '
                '(Kaspersky, ESET, Avast, proxy aziendale). Controlla data e ora; disattiva la scansione HTTPS dell\'antivirus '
                'o metti CotW Italiano tra le eccezioni.')
    if 'getaddrinfo' in t or 'name or service' in t or 'nodename' in t or '11001' in t:
        return 'Il PC non risolve il nome del sito (DNS). Prova a cambiare DNS (1.1.1.1 o 8.8.8.8) o riavvia il router.'
    if 'timed out' in t or 'timeout' in t:
        return ('Nessuna risposta: qualcosa blocca il programma (firewall, antivirus, VPN, rete aziendale/scolastica). '
                'Metti CotW Italiano tra le app consentite nel firewall e nelle eccezioni dell\'antivirus.')
    if 'refused' in t or '10061' in t or 'reset' in t or '10054' in t or 'forcibly' in t:
        return 'Connessione rifiutata o interrotta: firewall, antivirus o proxy. Prova a disattivarli un momento.'
    if '10013' in t or 'permission' in t:
        return 'Windows non permette al programma di aprire la connessione: e\' il firewall o un antivirus che blocca l\'exe.'
    if 'proxy' in t:
        return 'Problema con il proxy: controlla Impostazioni di Windows > Rete e Internet > Proxy.'
    return 'Errore non previsto: copia il rapporto e incollalo su Discord.'


def _dns(nome):
    t0 = time.time()
    ip = socket.gethostbyname(nome)
    return '%s -> %s (%.0f ms)' % (nome, ip, (time.time() - t0) * 1000)


def _https(url, timeout=15):
    t0 = time.time()
    req = urllib.request.Request(url, headers=dict(rete._UA, **{'Cache-Control': 'no-cache'}))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dati = r.read(200000)
        return r.status, r.headers.get('Date'), len(dati), (time.time() - t0) * 1000


def prova_rete(avanzamento=None):
    """Lista di dict: nome, ok (True/False/None=avviso), dettaglio, consiglio."""
    out = []
    n_tot = len(PROVE) + len(URL) + 3
    n = 0

    def passo(nome):
        nonlocal n
        n += 1
        if avanzamento:
            avanzamento(n, n_tot, nome)

    # 0) proxy e sistema
    passo('Impostazioni')
    px = {k: v for k, v in urllib.request.getproxies().items() if k in ('http', 'https')}
    out.append({'nome': 'Proxy di Windows', 'ok': None if px else True,
                'dettaglio': ', '.join('%s=%s' % kv for kv in px.items()) if px else 'nessun proxy',
                'consiglio': ('Il programma passa da un proxy: se non lo hai messo tu, toglilo in Impostazioni > Rete e '
                              'Internet > Proxy.' if px else '')})
    # 1) DNS
    for nome, host in PROVE:
        passo(nome)
        try:
            out.append({'nome': nome, 'ok': True, 'dettaglio': _dns(host), 'consiglio': ''})
        except Exception as e:
            out.append({'nome': nome, 'ok': False, 'dettaglio': '%s: %s' % (type(e).__name__, e), 'consiglio': _consiglio(e)})
    # 2) HTTPS
    data_server = None
    for nome, f_url in URL:
        passo(nome)
        url = f_url()
        try:
            st, data, nb, ms = _https(url)
            data_server = data_server or data
            out.append({'nome': nome, 'ok': True, 'dettaglio': 'HTTP %d, %d byte, %.0f ms' % (st, nb, ms), 'consiglio': ''})
        except Exception as e:
            out.append({'nome': nome, 'ok': False, 'dettaglio': '%s: %s  [%s]' % (type(e).__name__, e, url),
                        'consiglio': _consiglio(e)})
    # 3) postino (firmato)
    passo('Servizio segnalazioni')
    try:
        p = rete.postino()
        if not p:
            out.append({'nome': 'Servizio segnalazioni', 'ok': None, 'dettaglio': 'indirizzo non disponibile (o non firmato)',
                        'consiglio': 'Dipende dalle prove GitHub qui sopra: se quelle passano, riprova tra 5 minuti.'})
        else:
            st, data, nb, ms = _https(p + '/contributi/stato')
            out.append({'nome': 'Servizio segnalazioni', 'ok': True, 'dettaglio': 'HTTP %d, %.0f ms' % (st, ms), 'consiglio': ''})
    except Exception as e:
        out.append({'nome': 'Servizio segnalazioni', 'ok': False, 'dettaglio': '%s: %s' % (type(e).__name__, e),
                    'consiglio': _consiglio(e)})
    # 4) orologio
    passo('Orologio del PC')
    if data_server:
        try:
            diff = abs((parsedate_to_datetime(data_server).timestamp() - time.time()))
            out.append({'nome': 'Orologio del PC', 'ok': diff < 300, 'dettaglio': 'differenza con il server: %.0f secondi' % diff,
                        'consiglio': '' if diff < 300 else 'L\'ora del PC e\' sbagliata: con l\'ora sbagliata HTTPS non funziona. '
                                                            'Impostazioni > Ora e lingua > "Imposta data/ora automaticamente".'})
        except Exception:
            pass
    return out


def rapporto(risultati):
    from .. import VERSIONE
    righe = ['CotW Italiano %s - diagnosi connessione - %s' % (VERSIONE, time.strftime('%d/%m/%Y %H:%M')),
             'Windows %s, Python %s, exe: %s' % (platform.platform(), sys.version.split()[0], getattr(sys, 'frozen', False)),
             'SSL: %s' % ssl.OPENSSL_VERSION, '']
    for r in risultati:
        segno = {True: 'OK  ', False: 'NO  ', None: '??  '}[r['ok']]
        righe.append('%s%s: %s' % (segno, r['nome'], r['dettaglio']))
        if r['consiglio']:
            righe.append('      -> ' + r['consiglio'])
    testo = '\n'.join(righe) + '\n'
    try:
        with open(os.path.join(percorsi.dati_app(), 'diagnosi_rete.txt'), 'w', encoding='utf-8') as f:
            f.write(testo)
    except OSError:
        pass
    return testo


def riassunto(risultati):
    """Una frase: cosa non va (per il banner)."""
    ko = [r for r in risultati if r['ok'] is False]
    if not ko:
        return 'Tutte le prove sono passate: la connessione funziona. Se il problema resta, riavvia il programma.'
    return ko[0]['consiglio'] or ko[0]['dettaglio']
