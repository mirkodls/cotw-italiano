"""RICEVI I CONTRIBUTI (solo per l'autore, gira sul suo PC).
  python ricevi_contributi.py            scarica dal postino gli audio nuovi in  Desktop\\mod italiano\\contributi\\da_ascoltare\\<nome>\\
  python ricevi_contributi.py --accetta  prende TUTTO quello che e' rimasto in da_ascoltare (quello che non ti piace
                                         cancellalo prima) e lo mette nel doppiaggio come se l'avessi fatto tu:
                                         el_raw\\<id>.mp3 + wav_generati\\<id>.wav + _finali.txt, lo toglie da da_rifare.txt e
                                         scrive l'elenco in lavoro_voci\\_contributi_in_lavorazione.txt (poi il .bat installa).
                                         Le battute scartate tornano libere sul postino per gli altri.
  python ricevi_contributi.py --pulisci  toglie dal postino gli audio di battute che ormai sono nella versione pubblicata.
Serve la password dell'autore in  Desktop\\mod italiano\\postino_admin.txt  (la stessa del segreto ADMIN su Cloudflare)."""
import os
import sys
import json
import glob
import shutil
import subprocess
import urllib.request
import urllib.error
import urllib.parse

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))
from cotw.core import rete              # noqa: E402

MODIT = os.environ.get('COTW_MODIT') or os.path.abspath(os.path.join(QUI, '..', '..'))
LV = os.path.join(MODIT, 'audio italiano', 'lavoro_voci')
CONTR = os.path.join(MODIT, 'contributi')
ASCOLTA = os.path.join(CONTR, 'da_ascoltare')
ACCETTATI = os.path.join(CONTR, 'accettati')
SCARICATI = os.path.join(CONTR, 'scaricati.json')         # id -> nome di chi l'ha fatto (tutto cio' che e' stato scaricato)
CONTRIBUTORI = os.path.join(CONTR, 'contributori.json')   # nome -> battute accettate (finisce nei ringraziamenti)


def say(*a):
    print(*a, flush=True)


def leggi_json(p, d):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return d


def scrivi_json(p, v):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(v, open(p + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)


def postino():
    u = os.environ.get('COTW_POSTINO') or rete.leggi_online().get('postino')
    if not u:
        sys.exit('Non trovo l\'indirizzo del postino (online.json su GitHub).')
    return u.rstrip('/')


def password():
    p = os.path.join(MODIT, 'postino_admin.txt')
    if not os.path.isfile(p):
        sys.exit('Manca %s: scrivici la password del segreto ADMIN di Cloudflare.' % p)
    t = open(p, encoding='utf-8-sig').read().strip()
    if not t:
        sys.exit('postino_admin.txt e\' vuoto.')
    return t


def chiama(metodo, percorso, pw):
    r = urllib.request.Request(postino() + percorso, headers={'X-Admin': pw, 'User-Agent': 'CotW-Autore'}, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            return x.read()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            sys.exit('Il postino rifiuta la password (postino_admin.txt diverso dal segreto ADMIN su Cloudflare).')
        if e.code == 503:
            sys.exit('Il deposito non e\' collegato al postino (binding DEPOSITO su Cloudflare).')
        raise


def testi():
    out = {}
    for f in sorted(glob.glob(os.path.join(LV, 'coda', '*.tsv'))) + [os.path.join(LV, 'battute_tutte.tsv')]:
        if os.path.isfile(f):
            for l in open(f, encoding='utf-8'):
                r = l.rstrip('\r\n').split('\t')
                if len(r) >= 5:
                    out.setdefault(r[0], (r[1], r[2]))
    return out


def cartella_nome(chi):
    return ''.join(c if c.isalnum() or c in ' -_.' else '_' for c in (chi or 'Anonimo')).strip() or 'Anonimo'


def scarica():
    pw = password()
    elenco = json.loads(chiama('GET', '/admin/audio', pw)).get('audio', [])
    gia = leggi_json(SCARICATI, {})
    nuovi = [a for a in elenco if a['id'] not in gia]
    say('Sul postino ci sono %d audio, nuovi da scaricare: %d' % (len(elenco), len(nuovi)))
    tt = testi()
    for n, a in enumerate(nuovi):
        d = os.path.join(ASCOLTA, cartella_nome(a.get('chi')))
        os.makedirs(d, exist_ok=True)
        dati = chiama('GET', '/admin/audio/' + urllib.parse.quote(a['id']), pw)
        open(os.path.join(d, a['id'] + '.mp3'), 'wb').write(dati)
        with open(os.path.join(d, 'TESTI.txt'), 'a', encoding='utf-8') as f:
            chi, testo = tt.get(a['id'], ('?', '?'))
            f.write('%s\t%s\t%s\n' % (a['id'], chi, testo))
        gia[a['id']] = a.get('chi') or 'Anonimo'
        scrivi_json(SCARICATI, gia)
        say('  %d/%d  %s  (%s)' % (n + 1, len(nuovi), a['id'], a.get('chi')))
    say('\nAscolta i file in: ' + ASCOLTA + '\n(in ogni cartella TESTI.txt dice cosa deve dire ogni battuta)')
    say('Quello che non va bene CANCELLALO. Poi rilancia e scegli "accetta".')


def ffmpeg():
    f = shutil.which('ffmpeg')
    if f:
        return f
    for c in glob.glob(r'C:\ffmpeg*\bin\ffmpeg.exe'):
        return c
    sys.exit('ffmpeg non trovato: installalo (winget install ffmpeg) e rilancia.')


def accetta():
    pw = password()
    ff = ffmpeg()
    gia = leggi_json(SCARICATI, {})
    conta = leggi_json(CONTRIBUTORI, {})
    raw, wavd = os.path.join(LV, 'el_raw'), os.path.join(LV, 'wav_generati')
    old = os.path.join(LV, 'wav_voxcpm_vecchi')
    for d in (raw, wavd, old):
        os.makedirs(d, exist_ok=True)
    fin_p = os.path.join(wavd, '_finali.txt')
    fin = set(open(fin_p, encoding='utf-8').read().split()) if os.path.isfile(fin_p) else set()
    presi = []
    for mp3 in sorted(glob.glob(os.path.join(ASCOLTA, '*', '*.mp3'))):
        i = os.path.splitext(os.path.basename(mp3))[0]
        chi = gia.get(i) or os.path.basename(os.path.dirname(mp3))
        wv = os.path.join(wavd, i + '.wav')
        if os.path.exists(wv):                                 # come genera_elevenlabs: la vecchia voce va da parte
            if not os.path.exists(os.path.join(old, i + '.wav')):
                shutil.move(wv, os.path.join(old, i + '.wav'))
            else:
                os.remove(wv)
        subprocess.run([ff, '-y', '-loglevel', 'error', '-i', mp3, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', wv],
                       check=True)
        shutil.copyfile(mp3, os.path.join(raw, i + '.mp3'))
        if i not in fin:
            with open(fin_p, 'a', encoding='utf-8') as f:
                f.write(i + '\n')
            fin.add(i)
        dest = os.path.join(ACCETTATI, cartella_nome(chi))
        os.makedirs(dest, exist_ok=True)
        shutil.move(mp3, os.path.join(dest, i + '.mp3'))
        conta[chi] = conta.get(chi, 0) + 1
        presi.append(i)
        say('  accettata %s  (%s)' % (i, chi))
    scrivi_json(CONTRIBUTORI, conta)
    # tolte da da_rifare.txt (ora hanno la voce nuova)
    rf = os.path.join(LV, 'da_rifare.txt')
    if os.path.isfile(rf) and presi:
        resto = [x for x in open(rf, encoding='utf-8-sig').read().split() if x and x not in set(presi)]
        open(rf, 'w', encoding='utf-8').write('\n'.join(resto) + ('\n' if resto else ''))
    open(os.path.join(LV, '_contributi_in_lavorazione.txt'), 'w', encoding='utf-8').write('\n'.join(presi) + '\n')
    # scartate (cancellate da te): tornano libere sul postino
    scartate = [i for i in gia if i not in presi and not glob.glob(os.path.join(ACCETTATI, '*', i + '.mp3'))
                and not glob.glob(os.path.join(ASCOLTA, '*', i + '.mp3'))]
    for i in scartate:
        try:
            chiama('DELETE', '/admin/audio/' + urllib.parse.quote(i), pw)
            gia.pop(i, None)
            say('  scartata %s: torna libera per gli altri' % i)
        except Exception as e:
            say('  (non riesco a liberare %s: %s)' % (i, e))
    scrivi_json(SCARICATI, gia)
    for d in glob.glob(os.path.join(ASCOLTA, '*')):
        if os.path.isdir(d) and not glob.glob(os.path.join(d, '*.mp3')):
            shutil.rmtree(d, ignore_errors=True)
    say('\nAccettate: %d  |  scartate: %d' % (len(presi), len(scartate)))
    return presi


def pulisci():
    """Toglie dal postino gli audio delle battute che non sono piu' da doppiare (gia' nella versione pubblicata)."""
    pw = password()
    m = rete.leggi_manifest()
    ancora = set()
    if m and m.get('da_doppiare'):
        d = m['da_doppiare']
        p = rete.scarica(rete.url_pacchetto(d['tag'], d['nome']), os.path.join(CONTR, '_da_doppiare.json'), d.get('sha256'))
        ancora = {b['id'] for b in json.load(open(p, encoding='utf-8'))['battute']}
    elenco = json.loads(chiama('GET', '/admin/audio', pw)).get('audio', [])
    via = [a['id'] for a in elenco if a['id'] not in ancora]
    for i in via:
        chiama('DELETE', '/admin/audio/' + urllib.parse.quote(i), pw)
    say('Tolti dal postino %d audio gia\' pubblicati (ne restano %d).' % (len(via), len(elenco) - len(via)))


if __name__ == '__main__':
    if '--accetta' in sys.argv:
        accetta()
    elif '--pulisci' in sys.argv:
        pulisci()
    else:
        scarica()
