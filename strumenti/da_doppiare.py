"""Elenco delle battute da far doppiare alla community (solo per l'autore, lo usa pubblica.py).
Per ogni battuta prepara GIA' tutto quello che serve a ElevenLabs, con le STESSE regole di
audio italiano\\lavoro_voci\\genera_elevenlabs.py: voce del personaggio, pronunce (pronunce_el.py),
sigle (testo_tts.py), frase prima e dopo (per l'intonazione), velocita' di partenza.
Cosi' il programma di chi aiuta non deve sapere niente: manda a ElevenLabs esattamente cio' che c'e' qui.
SE CAMBI LE IMPOSTAZIONI IN genera_elevenlabs.py CAMBIALE ANCHE QUI (MODELLO, IMPOSTAZIONI, NOTI, CAL, VEL)."""
import os
import re
import sys
import glob
import json

MODELLO = 'eleven_multilingual_v2'
FORMATO = 'mp3_44100_128'
IMPOSTAZIONI = {'stability': 0.45, 'similarity_boost': 0.8, 'style': 0.35, 'use_speaker_boost': True}
NOTI = {'George': 'JBFqnCBsd6RMkjVDRZzb', 'Brian': 'nPczCjzI2devNBz1zQrb', 'Daniel': 'onwK4e9ZLuTAKqWW03F9',
        'Sarah': 'EXAVITQu4vr4xnSDxMaL', 'Alice': 'Xb7hH8MSUJpSbSDYk0k2', 'Matilda': 'XrExE9yKIg1WjnnlVkGX',
        'Bill': 'pqHfZKP75CvOlQylNhV4', 'Roger': 'CwhRBWXzGAHq8TQ4Fs17', 'Laura': 'FGY2WhTYpPnrIDTdsKH5',
        'Charlie': 'IKne3meq5aSn9XLyUdCD', 'Callum': 'N2lVS1w4EtoT3dr4eOWO', 'Charlotte': 'XB0fDUnXU5powFXDhCwa',
        'Will': 'bIHbv24MWmeRgasZH58o', 'Jessica': 'cgSgspJ2msm6clMCkdW9', 'Eric': 'cjVigY5qzO86Huf0OWal',
        'Chris': 'iP95p4xoKVk53GoZ742B', 'Lily': 'pFZP5JQG7iQjIQuC4Bku'}
CAL = {'Eric': 1.15, 'Charlie': 1.15, 'Jessica': 1.18, 'Callum': 1.15, 'Chris': 1.12, 'Roger': 1.15, 'Laura': 1.15,
       'Lily': 1.18, 'Charlotte': 1.18, 'Will': 1.15, 'George': 1.13, 'Brian': 1.11, 'Daniel': 1.21, 'Bill': 1.25,
       'Alice': 1.23, 'Matilda': 1.10, 'Sarah': 1.18}
VEL = {'kiri_f': 1.08, 'alena_f': 1.08, 'doc_m': 1.05, 'devil_m': 0.92, 'cursedhunters_f': 0.85}


def _gruppo(i):
    g, _, n = i.rpartition('_')
    return (g, int(n)) if n.isdigit() else (i, 0)


def crea(modit, audio_ids, nomi=None, mappe=None):
    """modit = Desktop\\mod italiano. audio_ids = battute che hanno gia' l'audio nella versione pubblicata.
    Restituisce la lista delle battute da doppiare (nuove + quelle in da_rifare.txt)."""
    lv = os.path.join(modit, 'audio italiano', 'lavoro_voci')
    sys.path.insert(0, lv)
    try:
        from pronunce_el import pronunce
    except Exception:
        pronunce = lambda t, chi=None: t           # noqa: E731
    try:
        from testo_tts import testo_tts
    except Exception:
        testo_tts = lambda t: t                    # noqa: E731
    nomi, mappe = nomi or {}, mappe or {}
    righe, visti = [], set()
    for f in sorted(glob.glob(os.path.join(lv, 'coda', '*.tsv'))) + [os.path.join(lv, 'battute_tutte.tsv')]:
        if os.path.isfile(f):
            for l in open(f, encoding='utf-8'):
                r = l.rstrip('\r\n').split('\t')
                if l.strip() and len(r) >= 5 and r[0] not in visti:
                    visti.add(r[0])
                    righe.append(r)
    G = {}
    for r in righe:
        g, n = _gruppo(r[0])
        G.setdefault(g, []).append((n, r))
    prec, succ = {}, {}
    for L in G.values():
        L.sort(key=lambda x: x[0])
        for a, b in zip(L, L[1:]):
            if a[1][1] == b[1][1]:
                prec[b[1][0]] = a[1][2]
                succ[a[1][0]] = b[1][2]
    rf = os.path.join(lv, 'da_rifare.txt')
    rifare = set(open(rf, encoding='utf-8-sig').read().split()) if os.path.isfile(rf) else set()
    voci = {}
    vf = os.path.join(lv, 'voci_elevenlabs.json')
    if os.path.isfile(vf):
        voci = json.load(open(vf, encoding='utf-8'))
    pers = {}
    pf = os.path.join(lv, 'personaggi.json')
    if os.path.isfile(pf):
        pers = json.load(open(pf, encoding='utf-8'))
    for f in sorted(glob.glob(os.path.join(lv, 'coda', 'personaggi_*.json'))):
        pers.update(json.load(open(f, encoding='utf-8')))

    out, senza_voce = [], set()
    for g in sorted(G):
        for _, r in sorted(G[g], key=lambda x: x[0]):
            i, k, testo, sec = r[0], r[1], r[2], r[4]
            if i in audio_ids and i not in rifare:
                continue
            v = voci.get(k, {})
            vid, nome_voce = v.get('id'), v.get('name')
            if not vid and nome_voce in NOTI:
                vid = NOTI[nome_voce]
            if not vid:
                nome_voce = 'Sarah' if str(pers.get(k, {}).get('sesso', 'M')).upper() == 'F' else 'Brian'
                vid = NOTI[nome_voce]
                senza_voce.add(k)
            t = testo_tts(pronunce(testo, k))
            try:
                T = float(sec)
            except ValueError:
                T = 0.0
            v0 = VEL.get(k, 1.0)
            if T > 1.5 and nome_voce in CAL:      # stessa stima di genera_elevenlabs.py: se sara' lunga parte piu' veloce
                pred = (len(re.findall(r'\w', t)) * 0.0662 + len(re.findall(r'[,.;:!?]', t)) * 0.082 - 0.026) * CAL[nome_voce] / v0
                if pred > T * 1.05:
                    v0 = min(1.15, max(v0, round(v0 * pred / (T * 1.02), 2)))
            out.append({'id': i, 'chi': nomi.get(k, k), 'mappa': mappe.get(k, '?'), 'voce': vid, 'nome_voce': nome_voce,
                        'testo': t, 'sottotitolo': testo,
                        'prec': testo_tts(pronunce(prec[i], k)) if i in prec else '',
                        'succ': testo_tts(pronunce(succ[i], k)) if i in succ else '',
                        'vel': v0, 'sec': T})
    return out, sorted(senza_voce)


def documento(versione, battute):
    return {'versione': versione, 'modello': MODELLO, 'formato': FORMATO, 'impostazioni': IMPOSTAZIONI,
            'battute': battute}
