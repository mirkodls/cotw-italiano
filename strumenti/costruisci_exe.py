"""Costruisce l'exe di CotW Italiano (cartella  dist\\CotW Italiano  +  dist\\CotW_Italiano_<versione>.zip).
Lo usa la costruzione automatica su GitHub (.github/workflows/crea_exe.yml) e anche CREA_EXE.bat sul PC.
  python costruisci_exe.py --metodo nuitka       consigliato: programma compilato, meno falsi allarmi degli antivirus
                                                 (serve Python 3.13 e un compilatore C: su GitHub c'e' gia')
  python costruisci_exe.py --metodo pyinstaller  piu' semplice, ma alcuni antivirus lo segnalano per sbaglio
Dentro l'exe vengono scritti nome, autore, versione e descrizione (gli antivirus si fidano di piu')."""
import os
import re
import sys
import json
import shutil
import hashlib
import zipfile
import argparse
import subprocess

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
NOME = 'CotW Italiano'
AUTORE = 'Mirko Del Sette'
DESCRIZIONE = 'CotW Italiano - traduzione e doppiaggio italiani di theHunter: Call of the Wild'


def versione():
    t = open(os.path.join(RADICE, 'cotw', '__init__.py'), encoding='utf-8').read()
    return re.search(r"VERSIONE\s*=\s*'([^']+)'", t).group(1)


def quattro(v):
    p = [int(x) for x in v.split('.')][:4]
    return tuple(p + [0] * (4 - len(p)))


def esegui(cmd):
    print('>', ' '.join('"%s"' % c if ' ' in c else c for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=RADICE)


def con_nuitka(ver, build):
    v4 = '.'.join(map(str, quattro(ver)))
    esegui([sys.executable, '-m', 'nuitka', '--standalone', '--enable-plugin=pyside6',
            '--windows-console-mode=disable', '--assume-yes-for-downloads',
            '--windows-icon-from-ico=' + os.path.join(RADICE, 'risorse', 'icona.ico'),
            '--include-data-dir=%s=risorse' % os.path.join(RADICE, 'risorse'),
            '--output-dir=' + build, '--output-filename=' + NOME + '.exe',
            '--company-name=' + AUTORE, '--product-name=' + NOME, '--file-version=' + v4, '--product-version=' + v4,
            '--file-description=' + DESCRIZIONE, '--copyright=(C) ' + AUTORE + ' - GPL-3.0',
            os.path.join(RADICE, 'CotW_Italiano.py')])
    return os.path.join(build, 'CotW_Italiano.dist')


def con_pyinstaller(ver, build):
    v = quattro(ver)
    vf = os.path.join(build, 'versione.txt')
    os.makedirs(build, exist_ok=True)
    campi = {'CompanyName': AUTORE, 'FileDescription': DESCRIZIONE, 'FileVersion': ver, 'InternalName': NOME,
             'LegalCopyright': '(C) %s - GPL-3.0' % AUTORE, 'OriginalFilename': NOME + '.exe',
             'ProductName': NOME, 'ProductVersion': ver}
    open(vf, 'w', encoding='utf-8').write(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=%r, prodvers=%r, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,"
        " subtype=0x0, date=(0, 0)), kids=[StringFileInfo([StringTable('041004B0', [%s])]),"
        " VarFileInfo([VarStruct('Translation', [0x0410, 1200])])])"
        % (v, v, ', '.join('StringStruct(%r, %r)' % kv for kv in campi.items())))
    sep = ';' if os.name == 'nt' else ':'
    esegui([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', NOME,
            '--icon', os.path.join(RADICE, 'risorse', 'icona.ico'),
            '--add-data', os.path.join(RADICE, 'risorse') + sep + 'risorse', '--version-file', vf,
            '--distpath', os.path.join(build, 'out'), '--workpath', os.path.join(build, 'lavoro'), '--specpath', build,
            os.path.join(RADICE, 'CotW_Italiano.py')])
    return os.path.join(build, 'out', NOME)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--metodo', choices=['nuitka', 'pyinstaller'], default='nuitka')
    a = ap.parse_args()
    ver = versione()
    build = os.path.join(RADICE, 'build')
    dist = os.path.join(RADICE, 'dist')
    shutil.rmtree(build, ignore_errors=True)
    os.makedirs(dist, exist_ok=True)
    fatto = con_nuitka(ver, build) if a.metodo == 'nuitka' else con_pyinstaller(ver, build)
    finale = os.path.join(dist, NOME)
    shutil.rmtree(finale, ignore_errors=True)
    shutil.move(fatto, finale)
    exe = os.path.join(finale, NOME + '.exe') if os.name == 'nt' else None
    if exe and not os.path.isfile(exe):
        sys.exit('ERRORE: manca %s' % exe)
    for f in ('LICENSE', 'LICENZA_TRADUZIONE.txt'):
        shutil.copy(os.path.join(RADICE, f), finale)
    zp = os.path.join(dist, 'CotW_Italiano_%s.zip' % ver)
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for cart, _, files in os.walk(finale):
            for n in files:
                p = os.path.join(cart, n)
                z.write(p, os.path.join(NOME, os.path.relpath(p, finale)))
    sha = hashlib.sha256(open(zp, 'rb').read()).hexdigest()
    info = {'versione': ver, 'zip': os.path.basename(zp), 'sha256': sha, 'dimensione': os.path.getsize(zp)}
    json.dump(info, open(os.path.join(dist, 'programma.json'), 'w'))
    print('\nFATTO: %s (%.0f MB)\nsha256 %s' % (zp, info['dimensione'] / 1e6, sha))


if __name__ == '__main__':
    main()
