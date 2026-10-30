"""Controllo prima di giocare: si apre quando premi Gioca (da Steam o dal collegamento), controlla in pochi secondi
se ci sono aggiornamenti della traduzione o del programma, ti chiede se aggiornare e poi avvia il gioco.
Senza internet o se va storto qualcosa: il gioco parte lo stesso, subito."""
import os
import sys
import time
import subprocess
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QProgressBar, QMessageBox
from ..core import percorsi, rete, aggiornamenti, installa, programma
from .finestra import etichetta, bottone
from .. import VERSIONE

APP_ID = '518790'
ATTESA_MAX = 8000          # millisecondi: oltre, si gioca senza aspettare


def _file_ultimo():
    return os.path.join(percorsi.dati_app(), 'ultimo_controllo_gioco.txt')


def controllo_recente(secondi=180):
    """Gia' controllato da poco (es. il collegamento passa da Steam, che riapre il controllo): si salta."""
    try:
        return time.time() - float(open(_file_ultimo()).read().strip()) < secondi
    except Exception:
        return False


def segna_controllo():
    try:
        open(_file_ultimo(), 'w').write(str(time.time()))
    except OSError:
        pass


def avvia_gioco(comando):
    """comando = quello che Steam mette al posto di %command% (+ le opzioni). Vuoto = fai partire il gioco da Steam."""
    if comando:
        exe = comando[0]
        subprocess.Popen(comando, cwd=os.path.dirname(exe) if os.path.isfile(exe) else None,
                         creationflags=0x00000008 | 0x00000200 if sys.platform == 'win32' else 0, close_fds=True)
    else:
        QDesktopServices.openUrl(QUrl('steam://rungameid/' + APP_ID))


class Controllo(QThread):
    fatto = Signal(object, object)

    def run(self):
        m = o = None
        try:
            m = rete.leggi_manifest(timeout=6)
        except Exception:
            pass
        try:
            o = rete.leggi_online(timeout=5)
        except Exception:
            pass
        self.fatto.emit(m, o)


class Aggiorna(QThread):
    avanzamento = Signal(int, int, str)
    fatto = Signal(str)

    def __init__(self, manifest, comp, dz):
        super().__init__()
        self.manifest, self.comp, self.dz = manifest, comp, dz

    def run(self):
        try:
            for c in self.comp:
                aggiornamenti.aggiorna_componente(self.manifest, c, self.dz,
                                                  lambda a, b, t: self.avanzamento.emit(a, b, t))
            self.fatto.emit('')
        except Exception as e:
            self.fatto.emit(str(e))


class PreparaProgramma(QThread):
    fatto = Signal(str, str)

    def __init__(self, info):
        super().__init__()
        self.info = info

    def run(self):
        try:
            self.fatto.emit(programma.prepara(self.info), '')
        except Exception as e:
            self.fatto.emit('', str(e))


class PrimaDiGiocare(QDialog):
    def __init__(self, comando):
        super().__init__()
        self.comando = comando
        self.setWindowTitle('CotW Italiano')
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(etichetta('theHunter: Call of the Wild in italiano', 'titolo'))
        self.testo = etichetta('Controllo gli aggiornamenti della traduzione...', None)
        lay.addWidget(self.testo)
        self.barra = QProgressBar()
        self.barra.setMaximum(0)
        lay.addWidget(self.barra)
        r = QHBoxLayout()
        self.b_agg = bottone('Aggiorna e gioca', 'primario')
        self.b_agg.clicked.connect(self._aggiorna)
        self.b_agg.hide()
        r.addWidget(self.b_agg)
        self.b_prog = bottone('Aggiorna il programma')
        self.b_prog.clicked.connect(self._aggiorna_programma)
        self.b_prog.hide()
        r.addWidget(self.b_prog)
        self.b_contr = bottone('Voglio contribuire')
        self.b_contr.clicked.connect(self._contribuisci)
        self.b_contr.hide()
        r.addWidget(self.b_contr)
        self.b_gioca = bottone('Gioca subito')
        self.b_gioca.clicked.connect(self._gioca)
        r.addWidget(self.b_gioca)
        r.addStretch(1)
        lay.addLayout(r)
        self.piede = etichetta('CotW Italiano %s - di Mirko Del Sette' % VERSIONE, 'tenue')
        lay.addWidget(self.piede)
        self.gioco = percorsi.trova_gioco()
        self.dz = percorsi.dropzone(self.gioco) if self.gioco else None
        self.da_agg, self.prog, self.manifest = [], None, None
        self.th = Controllo()
        self.th.fatto.connect(self._risultato)
        self.th.start()
        QTimer.singleShot(ATTESA_MAX, lambda: self._gioca() if self.th.isRunning() else None)

    def _risultato(self, m, o):
        self.manifest = m
        self.barra.hide()
        if m and self.dz and percorsi.mod_attiva(self.gioco):
            try:
                conf = aggiornamenti.confronta(m, self.dz)
                self.da_agg = [c for c, v in conf.items() if v[2] == 'aggiornare']
            except Exception:
                self.da_agg = []
        self.prog = programma.disponibile(o) if programma.cartella_exe() else None
        self.contr = None                       # battute da doppiare (nuove o corrette): una volta per versione
        d = (m or {}).get('da_doppiare')
        if d and programma.cartella_exe():
            cfg = percorsi.leggi_config()
            if cfg.get('popup_contribuisci_gioco') != d.get('tag'):
                cfg['popup_contribuisci_gioco'] = d.get('tag')
                percorsi.salva_config(cfg)
                self.contr = d
        if not self.da_agg and not self.prog and not self.contr:
            return self._gioca()
        righe = []
        if self.da_agg:
            nomi = ', '.join(installa.COMPONENTI[c]['nome'] for c in self.da_agg)
            righe.append('E\' disponibile la versione %s della traduzione (%s).' % (m.get('versione'), nomi))
            if m.get('novita'):
                righe.append('Novita\': ' + '; '.join(m['novita']))
        if self.prog:
            righe.append('E\' uscita la versione %s del programma CotW Italiano (tu hai la %s): premi "Aggiorna il '
                         'programma", si riapre da solo e poi parte il gioco.' % (self.prog['versione'], VERSIONE))
            self.b_prog.show()
        if self.contr:
            n = self.contr.get('numero', 0)
            righe.append(('C\'e\' 1 battuta da ridoppiare' if n == 1 else 'Ci sono %d battute da doppiare' % n) +
                         ' (nuove o corrette dopo le segnalazioni): vuoi contribuire gratuitamente per tutta la '
                         'community? Basta un account ElevenLabs gratuito.')
            self.b_contr.show()
        self.testo.setText('\n\n'.join(righe))
        if self.da_agg:
            self.b_agg.show()
            self.b_agg.setFocus()
        else:
            self.b_gioca.setText('Gioca')

    def _aggiorna(self):
        if percorsi.gioco_in_esecuzione():
            return self._gioca()
        self.b_agg.setEnabled(False)
        self.b_gioca.setEnabled(False)
        self.barra.setMaximum(0)
        self.barra.show()
        self.testo.setText('Aggiorno la traduzione... (scarica solo i file cambiati)')
        self.ag = Aggiorna(self.manifest, self.da_agg, self.dz)

        def av(a, b, t):
            self.barra.setMaximum(max(b, 1))
            self.barra.setValue(a)
            self.testo.setText('Aggiorno la traduzione: %s' % t)

        def fine(err):
            if err:
                QMessageBox.warning(self, 'Aggiornamento non riuscito', err + '\n\nIl gioco parte lo stesso con la '
                                    'traduzione di prima. Riprova la prossima volta.')
            self._gioca()
        self.ag.avanzamento.connect(av)
        self.ag.fatto.connect(fine)
        self.ag.start()

    def _aggiorna_programma(self):
        for b in (self.b_agg, self.b_prog, self.b_gioca):
            b.setEnabled(False)
        self.barra.setMaximum(0)
        self.barra.show()
        self.testo.setText('Scarico la versione %s del programma...' % self.prog['versione'])
        self.pp = PreparaProgramma(self.prog)

        def fine(cartella, err):
            if err:
                QMessageBox.warning(self, 'Aggiornamento non riuscito', err + '\n\nIl gioco parte lo stesso.')
                return self._gioca()
            try:
                programma.installa_e_riavvia(cartella, ['--gioco'] + list(self.comando))   # si riapre e avvia il gioco
            except Exception as e:
                QMessageBox.warning(self, 'Aggiornamento non riuscito', str(e))
                return self._gioca()
            self._partito = True
            self.accept()
        self.pp.fatto.connect(fine)
        self.pp.start()

    def _contribuisci(self):
        """Apre il programma sulla scheda Contribuisci (il gioco si avvia dopo, quando vuole l'utente)."""
        exe = programma.cartella_exe()
        if exe:
            subprocess.Popen([os.path.join(exe, programma.NOME_EXE), '--contribuisci'],
                             creationflags=0x00000008 | 0x00000200 if sys.platform == 'win32' else 0, close_fds=True)
        self._partito = True
        self.accept()

    def _gioca(self):
        if getattr(self, '_partito', False):
            return
        self._partito = True
        segna_controllo()
        try:
            avvia_gioco(self.comando)
        except Exception as e:
            QMessageBox.critical(self, 'Il gioco non parte', str(e))
        self.accept()


def esegui(argv):
    """Modalita' --gioco: il programma fa solo il controllo e avvia il gioco."""
    i = argv.index('--gioco')
    comando = argv[i + 1:]
    if percorsi.gioco_in_esecuzione():
        return 0
    if controllo_recente():
        avvia_gioco(comando)
        return 0
    d = PrimaDiGiocare(comando)
    d.exec()
    return 0
