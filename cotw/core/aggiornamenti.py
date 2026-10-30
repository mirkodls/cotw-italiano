"""Aggiornamenti da GitHub.
Schema di versione.json (lo scrive lo strumento Pubblica):
{
 "versione": "1.0.1", "data": "2026-10-30", "novita": ["..."], "programma": {"versione": "0.2.0"},
 "componenti": {
   "testo": {"versione": "1.0.1", "file": {"<percorso>": "<sha256>", ...},
             "pacchetti": [{"nome": "testo_1.0.1.zip", "tag": "v1.0.1", "sha256": "...", "dimensione": 123, "contiene": "tutto"}]},
   "audio": {... "pacchetti": [ {base completa, "contiene": "tutto"}, {aggiornamento, "contiene": ["<percorso>", ...]} ]}
 },
 "battute": {"nome": "battute_1.0.1.json", "tag": "v1.0.1", "sha256": "..."}
}
I pacchetti .zip contengono i file con il percorso "dropzone/<percorso>".
I file scaricati stanno in %APPDATA%\\CotW Italiano\\scaricati (una copia completa e verificata della mod);
da li' l'installazione copia nella dropzone solo cio' che serve."""
import os
import json
import shutil
import zipfile
from . import percorsi, rete, installa


def cartella_cache():
    d = os.path.join(percorsi.dati_app(), 'scaricati')
    os.makedirs(d, exist_ok=True)
    return d


def _radice_comp(comp):
    return os.path.join(cartella_cache(), installa.COMPONENTI[comp]['cartella_pacchetto'], 'dropzone')


# indice della cache: percorso -> [dimensione, data modifica, sha256] (evita di ricalcolare ogni volta)
def _file_indice():
    return os.path.join(cartella_cache(), '_indice.json')


def _leggi_indice():
    try:
        return json.load(open(_file_indice(), encoding='utf-8'))
    except Exception:
        return {}


def _salva_indice(ind):
    tmp = _file_indice() + '.tmp'
    json.dump(ind, open(tmp, 'w', encoding='utf-8'))
    os.replace(tmp, _file_indice())


def _sha_cache(comp, rel, ind):
    p = os.path.join(_radice_comp(comp), *rel.split('/'))
    try:
        st = os.stat(p)
    except OSError:
        return None
    k = comp + ':' + rel
    v = ind.get(k)
    if v and v[0] == st.st_size and v[1] == int(st.st_mtime):
        return v[2]
    s = rete.sha256_file(p)
    ind[k] = [st.st_size, int(st.st_mtime), s]
    return s


def mancanti(manifest, comp, avanzamento=None):
    """File del componente che nella cache mancano o sono diversi dalla versione online."""
    ind = _leggi_indice()
    voce = manifest['componenti'][comp]['file']
    out = []
    tot = len(voce)
    for i, (rel, sha) in enumerate(voce.items()):
        if _sha_cache(comp, rel, ind) != sha:
            out.append(rel)
        if avanzamento and i % 200 == 0:
            avanzamento(i, tot, 'Controllo')
    _salva_indice(ind)
    return out


def scegli_pacchetti(manifest, comp, servono):
    """Il minimo da scaricare: un aggiornamento piccolo se basta, altrimenti la base completa (+ aggiornamenti)."""
    pac = manifest['componenti'][comp]['pacchetti']
    if not servono:
        return []
    s = set(servono)
    piccoli = [p for p in pac if p.get('contiene') != 'tutto']
    for p in sorted(piccoli, key=lambda p: p.get('dimensione', 0)):
        if s <= set(p['contiene']):
            return [p]
    completi = [p for p in pac if p.get('contiene') == 'tutto']
    if not completi:
        raise RuntimeError('Nella versione online manca il pacchetto completo di "%s".' % installa.COMPONENTI[comp]['nome'])
    return completi[:1] + piccoli             # prima la base, poi gli aggiornamenti sopra


def _riusa_dalla_dropzone(manifest, comp, dz, servono, avanzamento=None):
    """I file che nella dropzone sono gia' identici alla versione online si copiano nella cache senza scaricarli."""
    if not dz:
        return servono
    voce = manifest['componenti'][comp]['file']
    radice = _radice_comp(comp)
    resto = []
    for i, rel in enumerate(servono):
        src = os.path.join(dz, *rel.split('/'))
        try:
            uguale = os.path.isfile(src) and rete.sha256_file(src) == voce[rel]
        except OSError:
            uguale = False
        if uguale:
            out = os.path.join(radice, *rel.split('/'))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copyfile(src, out)
        else:
            resto.append(rel)
        if avanzamento and i % 200 == 0:
            avanzamento(i, len(servono), 'Controllo i file gia\' presenti')
    return resto


def aggiorna_cache(manifest, comp, avanzamento=None, fermati=None, dz=None):
    """Porta la cache del componente alla versione online. Restituisce quanti MB ha scaricato."""
    voce = manifest['componenti'][comp]
    servono = mancanti(manifest, comp, avanzamento)
    servono = _riusa_dalla_dropzone(manifest, comp, dz, servono, avanzamento)
    pacchetti = scegli_pacchetti(manifest, comp, servono)
    servono = set(servono)
    radice = _radice_comp(comp)
    zipdir = os.path.join(cartella_cache(), '_zip')
    mb = 0.0
    for p in pacchetti:
        dest = os.path.join(zipdir, p['nome'])
        nome = installa.COMPONENTI[comp]['nome']

        def av(a, b, nome=nome, p=p):
            if avanzamento:
                avanzamento(a // (1 << 20), max(b, p.get('dimensione', 0)) // (1 << 20) or 1, 'Scarico %s (MB)' % nome)
        rete.scarica(rete.url_pacchetto(p['tag'], p['nome']), dest, p.get('sha256'), av, fermati)
        mb += os.path.getsize(dest) / 1e6
        with zipfile.ZipFile(dest) as z:
            membri = [m for m in z.namelist() if m.startswith('dropzone/') and not m.endswith('/')]
            for i, m in enumerate(membri):
                rel = m[len('dropzone/'):]
                if rel not in voce['file'] or rel not in servono:
                    continue
                out = os.path.join(radice, *rel.split('/'))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(m) as src, open(out + '.tmp', 'wb') as dst:
                    while True:
                        b = src.read(1 << 20)
                        if not b:
                            break
                        dst.write(b)
                os.replace(out + '.tmp', out)
                if avanzamento and i % 100 == 0:
                    avanzamento(i, len(membri), 'Estraggo %s' % nome)
        os.remove(dest)                          # lo zip non serve piu'
    # file vecchi che nella nuova versione non ci sono piu'
    for cart, _, files in os.walk(radice):
        for n in files:
            rel = os.path.relpath(os.path.join(cart, n), radice).replace(os.sep, '/')
            if rel not in voce['file']:
                os.remove(os.path.join(cart, n))
    rimasti = mancanti(manifest, comp)
    if rimasti:
        raise RuntimeError('Dopo lo scaricamento %d file non corrispondono alla versione online. Riprova.' % len(rimasti))
    return mb


def scarica_battute(manifest):
    """Elenco delle battute (per la ricerca nella scheda Segnala). Restituisce il percorso del file locale."""
    b = manifest.get('battute')
    if not b:
        return None
    dest = os.path.join(cartella_cache(), 'battute.json')
    rete.scarica(rete.url_pacchetto(b['tag'], b['nome']), dest, b.get('sha256'))
    return dest


def aggiorna_componente(manifest, comp, dz, avanzamento=None, fermati=None):
    """Scarica (solo il necessario), verifica e installa nella dropzone. Restituisce (MB scaricati, file copiati)."""
    mb = aggiorna_cache(manifest, comp, avanzamento, fermati, dz)
    n, copiati = installa.installa(comp, cartella_cache(), dz, avanzamento=avanzamento, fermati=fermati,
                                   versione=manifest['componenti'][comp].get('versione'))
    try:
        scarica_battute(manifest)
    except Exception:
        pass
    return mb, copiati


def confronta(manifest, dz):
    """Per ogni componente: (versione installata, versione online, stato) con stato = 'aggiornato' | 'aggiornare' | 'non installato'."""
    out = {}
    st = installa.leggi_stato()['componenti']
    for comp in installa.COMPONENTI:
        online = manifest['componenti'].get(comp, {}).get('versione') if manifest else None
        loc = st.get(comp, {})
        mia = loc.get('versione')
        presente = installa.stato_componente(dz, comp)[0] == 'installato' if dz else False
        if not presente:
            out[comp] = (mia, online, 'non installato')
        elif online and mia != online:
            out[comp] = (mia, online, 'aggiornare')
        else:
            out[comp] = (mia, online, 'aggiornato')
    return out
