"""PUBBLICA una nuova versione della mod su GitHub (solo per l'autore, gira sul suo PC).
Prende i file da  Desktop\\mod italiano\\MOD  (mod ita testo, mod audio ita), crea i pacchetti e la Release.
Serve un token GitHub in  Desktop\\mod italiano\\github_token.txt  (fine-grained, solo il repository
cotw-italiano, permesso Contents: Read and write). Il token NON va mai condiviso ne' messo nel repository.

Uso:  python pubblica.py [--versione 1.0.1] [--novita "testo; altro testo"] [--apri-doppiaggio] [--prova]
  --prova            prepara tutto in strumenti\\_pubblica ma NON carica niente su GitHub.
  --apri-doppiaggio  le battute senza voce (nuove o in da_rifare.txt) si possono doppiare dalla community
                     (scheda Contribuisci). Da usare SOLO dopo aver ricontrollato i testi."""
import os
import sys
import json
import time
import glob
import zipfile
import argparse
import urllib.request
import urllib.error

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))
from cotw.core import rete              # noqa: E402

MODIT = os.path.abspath(os.path.join(QUI, '..', '..'))          # Desktop\mod italiano
API = 'https://api.github.com/repos/' + rete.REPO
QUOTA_BASE = 0.30          # se cambia piu' del 30% dell'audio si rifa' la base completa

MAPPA = {'florian_m': 'Salzwiesen Park', 'janine': 'Askiy Ridge', 'chris_a': 'Askiy Ridge', 'gabe_a': 'Askiy Ridge',
         'salvador': 'Rancho del Arroyo', 'isla_f': 'Scozia', 'roddy': 'Scozia', 'tam_m': 'Scozia',
         'guida_delta': 'Mississippi Acres', 'zia_betty': 'Mississippi Acres', 'ale_f': 'Cuatro Colinas',
         'hernandez_m': 'Cuatro Colinas', 'ispettore_m': 'Cuatro Colinas', 'kiri_f': 'Te Awaroa',
         'all_m': 'Silver Ridge Peaks', 'remi_m': 'Silver Ridge Peaks', 'asmita_f': 'Sundarpatan',
         'birendra_m': 'Sundarpatan', 'freddy_m': 'Peru', 'maria_f': 'Peru', 'robbo': 'Emerald Coast',
         'soph': 'Emerald Coast', 'nh_trev_m': 'New England', 'nh_doc_m': 'New England', 'conni_f': 'Hirschfelden',
         'doc_m': 'Layton Lake', 'alena_f': 'Medved-Taiga', 'njabulo_m': 'Vurhonga Savanna',
         'carolina_f': 'Parque Fernando', 'jim_f': 'Yukon Valley', 'oiva_m': 'Revontuli Coast',
         'devil_m': 'Eventi', 'cursedhunters_f': 'Eventi', 'halloween_f': 'Eventi'}
NOMI = {'florian_m': 'Florian', 'janine': 'Janine', 'chris_a': 'Chris', 'gabe_a': 'Gabe', 'salvador': 'Salvador',
        'isla_f': 'Isla', 'roddy': 'Roddy', 'tam_m': 'Tam', 'guida_delta': 'Immi', 'zia_betty': 'Zia Betty',
        'ale_f': 'Ale', 'hernandez_m': 'Sindaco Hernandez', 'ispettore_m': 'Ispettore', 'kiri_f': 'Kiri',
        'all_m': 'Allan', 'remi_m': 'Remi', 'asmita_f': 'Asmita', 'birendra_m': 'Birendra', 'freddy_m': 'Freddy',
        'maria_f': 'Maria', 'robbo': 'Robbo', 'soph': 'Soph', 'nh_trev_m': 'Trevor', 'nh_doc_m': 'Doc',
        'conni_f': 'Conni', 'doc_m': 'Doc', 'alena_f': 'Alena', 'njabulo_m': 'Njabulo', 'carolina_f': 'Carolina',
        'jim_f': 'Jim', 'oiva_m': 'Oiva', 'devil_m': 'Diavolo', 'cursedhunters_f': 'Spiriti', 'halloween_f': 'Halloween'}

COMP = {'testo': 'mod ita testo', 'audio': 'mod audio ita'}


def say(*a):
    print(*a, flush=True)


# ---------------- GitHub ----------------
def token():
    p = os.path.join(MODIT, 'github_token.txt')
    if not os.path.isfile(p):
        sys.exit('Manca %s (vedi le istruzioni in cima a questo file).' % p)
    t = open(p, encoding='utf-8-sig').read().split()
    if not t:
        sys.exit('github_token.txt e\' vuoto.')
    return t[0]


def chiama(metodo, url, dati=None, tipo='application/json', tok=None, lunghezza=None):
    h = {'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json', 'User-Agent': 'CotW-Pubblica',
         'X-GitHub-Api-Version': '2022-11-28'}
    if dati is not None:
        h['Content-Type'] = tipo
        if lunghezza is not None:
            h['Content-Length'] = str(lunghezza)
    if isinstance(dati, (dict, list)):
        dati = json.dumps(dati).encode('utf-8')
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=dati, headers=h, method=metodo), timeout=600) as r:
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        sys.exit('GitHub ha rifiutato (%d): %s' % (e.code, e.read().decode('utf-8', 'replace')[:400]))


class _Lettore:
    """File letto a pezzi con avanzamento (per caricare file grandi)."""
    def __init__(self, p):
        self.f = open(p, 'rb')
        self.tot = os.path.getsize(p)
        self.fatti = 0
        self.ultimo = 0

    def read(self, n=-1):
        b = self.f.read(1 << 20 if n is None or n < 0 else n)
        self.fatti += len(b)
        if self.fatti - self.ultimo > 20 << 20 or self.fatti == self.tot:
            self.ultimo = self.fatti
            say('     %d / %d MB' % (self.fatti >> 20, self.tot >> 20))
        return b


def carica_file(rel_id, percorso, tok):
    nome = os.path.basename(percorso)
    say('   carico %s (%.1f MB)...' % (nome, os.path.getsize(percorso) / 1e6))
    url = 'https://uploads.github.com/repos/%s/releases/%d/assets?name=%s' % (rete.REPO, rel_id, urllib.request.quote(nome))
    tipo = 'application/zip' if nome.endswith('.zip') else 'application/json'
    chiama('POST', url, _Lettore(percorso), tipo, tok, os.path.getsize(percorso))


# ---------------- pacchetti ----------------
def file_componente(comp):
    radice = os.path.join(MODIT, 'MOD', COMP[comp], 'dropzone')
    if not os.path.isdir(radice):
        sys.exit('Manca %s: prima lancia 3_CREA_PACCHETTI_NEXUS.bat' % radice)
    out = {}
    for cart, _, files in os.walk(radice):
        for n in files:
            p = os.path.join(cart, n)
            rel = os.path.relpath(p, radice).replace(os.sep, '/')
            low = rel.lower()
            if comp == 'audio' and not (low.startswith('sound/dialogue/') and low.endswith('.wavc')):
                continue
            if comp == 'testo' and low not in ('settings/hp_settings/string_ids.stringlookup', 'ui/ui_localization.stringlookup'):
                continue
            out[rel] = p
    return out


def zip_file(dest, file_map, rels):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, rel in enumerate(sorted(rels)):
            z.write(file_map[rel], 'dropzone/' + rel)
            if i and i % 1000 == 0:
                say('     %d / %d file' % (i, len(rels)))
    return dest


def pacchetto(dest, tag, contiene):
    return {'nome': os.path.basename(dest), 'tag': tag, 'sha256': rete.sha256_file(dest),
            'dimensione': os.path.getsize(dest), 'contiene': contiene}


def elenco_battute(audio_ids):
    coda = os.path.join(MODIT, 'audio italiano', 'lavoro_voci', 'coda')
    visti, out = set(), []
    for f in sorted(glob.glob(os.path.join(coda, '*.tsv'))) + [os.path.join(coda, '..', 'battute_tutte.tsv')]:
        if not os.path.isfile(f):
            continue
        for l in open(f, encoding='utf-8'):
            r = l.rstrip('\r\n').split('\t')
            if len(r) >= 5 and r[0] not in visti:
                visti.add(r[0])
                if r[0] in audio_ids:
                    out.append({'id': r[0], 'chi': NOMI.get(r[1], r[1]), 'mappa': MAPPA.get(r[1], '?'), 'it': r[2]})
    return out


def versione_successiva(v):
    p = [int(x) for x in (v or '0.9.9').split('.')]
    p[-1] += 1
    return '.'.join(str(x) for x in p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--versione')
    ap.add_argument('--novita', default='')
    ap.add_argument('--prova', action='store_true')
    ap.add_argument('--apri-doppiaggio', action='store_true')
    a = ap.parse_args()

    say('1/5 Leggo la versione pubblicata adesso...')
    prec = rete.leggi_manifest()
    ver = a.versione or (versione_successiva(prec['versione']) if prec else '1.0.0')
    tag = 'v' + ver
    say('    precedente: %s  ->  nuova: %s' % (prec['versione'] if prec else 'nessuna', ver))
    out = os.path.join(QUI, '_pubblica', tag)
    os.makedirs(out, exist_ok=True)
    da_caricare = []
    man = {'versione': ver, 'data': time.strftime('%Y-%m-%d'),
           'novita': [x.strip() for x in a.novita.split(';') if x.strip()], 'componenti': {}}

    say('2/5 Testo...')
    ft = file_componente('testo')
    sha_t = {rel: rete.sha256_file(p) for rel, p in ft.items()}
    pt = prec['componenti'].get('testo') if prec else None
    if pt and pt['file'] == sha_t:
        say('    testo invariato: riuso il pacchetto della versione %s' % pt['versione'])
        man['componenti']['testo'] = pt
    else:
        z = zip_file(os.path.join(out, 'testo_%s.zip' % ver), ft, ft.keys())
        man['componenti']['testo'] = {'versione': ver, 'file': sha_t, 'pacchetti': [pacchetto(z, tag, 'tutto')]}
        da_caricare.append(z)

    say('3/5 Doppiaggio (calcolo le impronte di tutti i file)...')
    fa = file_componente('audio')
    sha_a = {}
    for i, (rel, p) in enumerate(fa.items()):
        sha_a[rel] = rete.sha256_file(p)
        if i and i % 1000 == 0:
            say('     %d / %d' % (i, len(fa)))
    pa = prec['componenti'].get('audio') if prec else None
    base = next((p for p in (pa or {}).get('pacchetti', []) if p.get('contiene') == 'tutto'), None)
    if pa and pa['file'] == sha_a:
        say('    doppiaggio invariato: riuso i pacchetti della versione %s' % pa['versione'])
        man['componenti']['audio'] = pa
    else:
        indice_base = None
        if base and base.get('indice'):
            say('    scarico l\'indice della base %s...' % base['tag'])
            p = rete.scarica(rete.url_pacchetto(base['tag'], base['indice']), os.path.join(out, base['indice']))
            indice_base = json.load(open(p, encoding='utf-8'))
        cambiati = [rel for rel, s in sha_a.items() if not indice_base or indice_base.get(rel) != s]
        if indice_base is not None and len(cambiati) <= QUOTA_BASE * len(sha_a):
            say('    %d battute cambiate rispetto alla base %s: pacchetto piccolo' % (len(cambiati), base['tag']))
            pacc = [base]
            if cambiati:
                z = zip_file(os.path.join(out, 'audio_aggiornamento_%s.zip' % ver), fa, cambiati)
                pacc.append(pacchetto(z, tag, sorted(cambiati)))
                da_caricare.append(z)
        else:
            say('    nuova base completa (%d file, ci vuole un po\')...' % len(sha_a))
            z = zip_file(os.path.join(out, 'audio_completo_%s.zip' % ver), fa, fa.keys())
            ind = os.path.join(out, 'audio_indice_%s.json' % ver)
            json.dump(sha_a, open(ind, 'w', encoding='utf-8'))
            pb = pacchetto(z, tag, 'tutto')
            pb['indice'] = os.path.basename(ind)
            pacc = [pb]
            da_caricare += [z, ind]
        man['componenti']['audio'] = {'versione': ver, 'file': sha_a, 'pacchetti': pacc}

    say('4/5 Elenco battute per le segnalazioni...')
    ids = {os.path.splitext(os.path.basename(r))[0] for r in sha_a}
    bf = os.path.join(out, 'battute_%s.json' % ver)
    json.dump(elenco_battute(ids), open(bf, 'w', encoding='utf-8'), ensure_ascii=False)
    man['battute'] = {'nome': os.path.basename(bf), 'tag': tag, 'sha256': rete.sha256_file(bf)}
    da_caricare.append(bf)
    if a.apri_doppiaggio:
        say('    Battute da far doppiare alla community...')
        import da_doppiare
        dd, senza_voce = da_doppiare.crea(MODIT, ids, NOMI, MAPPA)
        for k in senza_voce:
            say('    ATTENZIONE: il personaggio "%s" non ha una voce in voci_elevenlabs.json: uso Sarah/Brian.' % k)
        if dd:
            df = os.path.join(out, 'da_doppiare_%s.json' % ver)
            json.dump(da_doppiare.documento(ver, dd), open(df, 'w', encoding='utf-8'), ensure_ascii=False)
            man['da_doppiare'] = {'nome': os.path.basename(df), 'tag': tag, 'sha256': rete.sha256_file(df), 'numero': len(dd),
                                  'caratteri': sum(len(b['testo']) for b in dd)}
            da_caricare.append(df)
            say('    %d battute aperte alla community (circa %d caratteri ElevenLabs).' % (len(dd), man['da_doppiare']['caratteri']))
        else:
            say('    Nessuna battuta senza voce: niente da far doppiare.')
    cf = os.path.join(MODIT, 'contributi', 'contributori.json')
    if os.path.isfile(cf):
        cc = json.load(open(cf, encoding='utf-8'))
        man['contributori'] = [{'nome': n, 'battute': v} for n, v in sorted(cc.items(), key=lambda x: -x[1])]
    mf = os.path.join(out, 'versione.json')
    json.dump(man, open(mf, 'w', encoding='utf-8'), ensure_ascii=False)
    da_caricare.append(mf)                     # per ultimo: finche' non c'e', la versione non e' visibile

    say('    da caricare: ' + ', '.join('%s (%.1f MB)' % (os.path.basename(f), os.path.getsize(f) / 1e6) for f in da_caricare))
    if a.prova:
        say('PROVA: niente caricato. File pronti in ' + out)
        return
    tok = token()
    say('5/5 Creo la versione %s su GitHub e carico i file...' % tag)
    corpo = 'Mod italiana %s\n\n' % ver + '\n'.join('- ' + x for x in man['novita'])
    rel = chiama('POST', API + '/releases', {'tag_name': tag, 'target_commitish': 'main', 'name': 'Mod italiana ' + ver,
                                             'body': corpo, 'draft': True}, tok=tok)
    for f in da_caricare:                      # in bozza: nessuno la vede finche' non e' tutto caricato
        carica_file(rel['id'], f, tok)
    rel = chiama('PATCH', API + '/releases/%d' % rel['id'], {'draft': False, 'make_latest': 'true'}, tok=tok)
    say('\nFATTO: versione %s pubblicata. Il programma di tutti la vedra\' al prossimo controllo.' % ver)
    say(rel.get('html_url', ''))


if __name__ == '__main__':
    main()
