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


def versione_avvio():
    t = open(os.path.join(RADICE, 'avvio', '__init__.py'), encoding='utf-8').read()
    return re.search(r"AVVIO_VERSIONE\s*=\s*'([^']+)'", t).group(1)


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
            '--include-package=certifi', '--include-package-data=certifi',
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
            '--hidden-import', 'certifi', '--collect-data', 'certifi',
            '--distpath', os.path.join(build, 'out'), '--workpath', os.path.join(build, 'lavoro'), '--specpath', build,
            os.path.join(RADICE, 'CotW_Italiano.py')])
    return os.path.join(build, 'out', NOME)


def trova_csc():
    """Compilatore C# di .NET Framework 4 (c'e' su ogni Windows: niente da installare)."""
    win = os.environ.get('WINDIR', r'C:\Windows')
    for c in (os.path.join(win, 'Microsoft.NET', 'Framework64', 'v4.0.30319', 'csc.exe'),
              os.path.join(win, 'Microsoft.NET', 'Framework', 'v4.0.30319', 'csc.exe')):
        if os.path.isfile(c):
            return c
    return shutil.which('csc') or shutil.which('mcs')


def avvio_csharp(av, build):
    """L'AVVIO in C# (avvio_cs/Avvio.cs): exe di poche decine di KB, parte subito, meno falsi allarmi antivirus."""
    src = os.path.join(RADICE, 'avvio_cs', 'Avvio.cs')
    m = re.search(r'AVVIO_VERSIONE\s*=\s*"([^"]+)"', open(src, encoding='utf-8').read())
    if not m or m.group(1) != av:
        sys.exit('ERRORE: AVVIO_VERSIONE in avvio_cs/Avvio.cs (%s) diversa da avvio/__init__.py (%s)'
                 % (m.group(1) if m else '?', av))
    csc = trova_csc()
    if not csc:
        sys.exit('ERRORE: non trovo il compilatore C# (csc.exe di .NET Framework)')
    os.makedirs(build, exist_ok=True)
    out = os.path.join(build, NOME + '.exe')
    cmd = [csc, '/nologo', '/target:winexe', '/optimize+', '/platform:anycpu', '/out:' + out,
           '/win32icon:' + os.path.join(RADICE, 'risorse', 'icona.ico'),
           '/r:System.Web.Extensions.dll', '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll',
           '/r:System.Numerics.dll', '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll', src]
    if os.path.basename(csc).lower().startswith('mcs'):
        cmd = [c.replace('/', '-', 1) if c.startswith('/') and ':' in c[:12] else c for c in cmd]
        cmd.insert(1, '-langversion:5')
    esegui(cmd)
    return out


def avvio_nuitka(av, build):
    """L'AVVIO: un solo file exe (onefile), piccolo, senza Qt. Si estrae una volta nella cache e poi parte subito."""
    v4 = '.'.join(map(str, quattro(av)))
    esegui([sys.executable, '-m', 'nuitka', '--onefile', '--enable-plugin=tk-inter',
            '--windows-console-mode=disable', '--assume-yes-for-downloads',
            '--windows-icon-from-ico=' + os.path.join(RADICE, 'risorse', 'icona.ico'),
            '--include-package=certifi', '--include-package-data=certifi',
            '--onefile-tempdir-spec={CACHE_DIR}/CotW Italiano/avvio-{VERSION}',
            '--output-dir=' + build, '--output-filename=' + NOME + '.exe',
            '--company-name=' + AUTORE, '--product-name=' + NOME, '--file-version=' + v4, '--product-version=' + v4,
            '--file-description=CotW Italiano - avvio e aggiornamenti', '--copyright=(C) ' + AUTORE + ' - GPL-3.0',
            os.path.join(RADICE, 'CotW_Avvio.py')])
    return os.path.join(build, NOME + '.exe')


def avvio_pyinstaller(av, build):
    esegui([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onefile', '--name', NOME,
            '--icon', os.path.join(RADICE, 'risorse', 'icona.ico'),
            '--hidden-import', 'certifi', '--collect-data', 'certifi',
            '--distpath', os.path.join(build, 'out'), '--workpath', os.path.join(build, 'lavoro'), '--specpath', build,
            os.path.join(RADICE, 'CotW_Avvio.py')])
    return os.path.join(build, 'out', NOME + '.exe')


def trova_iscc():
    for p in (shutil.which('iscc'), r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe', r'C:\Program Files\Inno Setup 6\ISCC.exe',
              os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Inno Setup 6', 'ISCC.exe')):
        if p and os.path.isfile(p):
            return p
    return None


def installer(ver, finale, dist, avvio_exe):
    """Installer (Inno Setup): CotW_Italiano_Setup_<ver>.exe. None se Inno Setup non c'e'."""
    iscc = trova_iscc()
    if not iscc:
        print('(Inno Setup non trovato: niente installer)')
        return None
    esegui([iscc, '/Qp', '/DVERSIONE=' + ver, '/DSORGENTE=' + finale, '/DUSCITA=' + dist, '/DAVVIO=' + avvio_exe,
            os.path.join(RADICE, 'strumenti', 'installer.iss')])
    p = os.path.join(dist, 'CotW_Italiano_Setup_%s.exe' % ver)
    if not os.path.isfile(p):
        sys.exit('ERRORE: installer non creato')
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--metodo', choices=['nuitka', 'pyinstaller'], default='nuitka')
    ap.add_argument('--avvio', choices=['csharp', 'python'], default='csharp',
                    help='AVVIO in C# (predefinito, dalla 0.5.15) o in Python (come la 0.5.14)')
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
    # AVVIO (programmino separato che aggiorna e torna indietro): va accanto, nella cartella di installazione
    av = versione_avvio()
    build_av = os.path.join(RADICE, 'build_avvio')
    shutil.rmtree(build_av, ignore_errors=True)
    if a.avvio == 'csharp':
        fatto_av = avvio_csharp(av, build_av)
    else:
        fatto_av = avvio_nuitka(av, build_av) if a.metodo == 'nuitka' else avvio_pyinstaller(av, build_av)
    if os.name == 'nt' and not os.path.isfile(fatto_av):
        sys.exit('ERRORE: manca l\'avvio %s' % fatto_av)
    avvio_exe = os.path.join(dist, 'avvio', NOME + '.exe')
    os.makedirs(os.path.dirname(avvio_exe), exist_ok=True)
    shutil.copy(fatto_av, avvio_exe)
    nome_av = 'CotW_Avvio_%s.exe' % av
    shutil.copy(fatto_av, os.path.join(dist, nome_av))
    info['avvio'] = {'versione': av, 'file': nome_av,
                     'sha256': hashlib.sha256(open(avvio_exe, 'rb').read()).hexdigest()}
    setup = installer(ver, finale, dist, avvio_exe)
    if setup:
        info['setup'] = os.path.basename(setup)
        info['setup_sha256'] = hashlib.sha256(open(setup, 'rb').read()).hexdigest()
        zs = setup[:-4] + '.zip'                 # per Nexus (vuole uno zip): dentro c'e' solo l'installer
        with zipfile.ZipFile(zs, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(setup, os.path.basename(setup))
        info['setup_zip'] = os.path.basename(zs)
    json.dump(info, open(os.path.join(dist, 'programma.json'), 'w'))
    print('\nFATTO: %s (%.0f MB)\nsha256 %s' % (zp, info['dimensione'] / 1e6, sha))


if __name__ == '__main__':
    main()
