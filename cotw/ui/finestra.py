"""Finestra principale di CotW Italiano (tappa 1: Home, Installa, Strumenti, Impostazioni)."""
import os
import sys
import subprocess
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QStackedWidget, QFrame, QCheckBox, QLineEdit, QFileDialog, QProgressBar, QSlider,
                               QComboBox, QMessageBox, QButtonGroup, QScrollArea, QSizePolicy,
                               QListWidget, QListWidgetItem, QInputDialog, QPlainTextEdit)

from ..core import percorsi, installa, quad, missioni, avvio, rete, aggiornamenti, segnala, contribuisci, programma
from .. import VERSIONE
from . import stile

OPZIONI_AVVIO = avvio.OPZIONI


# ---------------- lavori lunghi in background ----------------
class Lavoro(QThread):
    avanzamento = Signal(int, int, str)
    finito = Signal(str)
    errore = Signal(str)

    def __init__(self, funzione):
        super().__init__()
        self.funzione = funzione

    def run(self):
        try:
            msg = self.funzione(lambda a, b, t: self.avanzamento.emit(a, b, t))
            self.finito.emit(msg or 'Fatto.')
        except Exception as e:
            traceback.print_exc()
            self.errore.emit(str(e))


class ControlloOnline(QThread):
    fatto = Signal(object)
    errore = Signal(str)

    def run(self):
        try:
            m = rete.leggi_manifest()
        except Exception as e:
            self.errore.emit(str(e))
            return
        try:
            if m and m.get('battute'):
                aggiornamenti.scarica_battute(m)     # elenco frasi per Segnala (piccolo; se e' gia' uguale non riscarica)
        except Exception:
            pass
        self.doc, self.stato = None, None
        self.online = rete.leggi_online()
        try:
            self.doc = contribuisci.elenco(m)        # battute da doppiare (solo se l'autore le ha aperte)
            if self.doc:
                self.stato = contribuisci.stato()
        except Exception:
            pass
        self.fatto.emit(m)


class Doppiaggio(QThread):
    avanzamento = Signal(int, int, str)
    finito = Signal(int, str)
    errore = Signal(str)

    def __init__(self, chiave, doc, chi):
        super().__init__()
        self.chiave, self.doc, self.chi, self.stop = chiave, doc, chi, False

    def run(self):
        try:
            n, motivo = contribuisci.doppia(self.chiave, self.doc, self.chi,
                                            lambda a, b, t: self.avanzamento.emit(a, b, t), lambda: self.stop)
            self.finito.emit(n, motivo)
        except Exception as e:
            traceback.print_exc()
            self.errore.emit(str(e))


class Crediti(QThread):
    fatto = Signal(object)
    errore = Signal(str)

    def __init__(self, chiave):
        super().__init__()
        self.chiave = chiave

    def run(self):
        try:
            self.fatto.emit(contribuisci.crediti(self.chiave))
        except Exception as e:
            self.errore.emit(str(e))


class Invio(QThread):
    fatto = Signal()
    errore = Signal(str)

    def __init__(self, testo):
        super().__init__()
        self.testo = testo

    def run(self):
        try:
            segnala.invia(self.testo)
            self.fatto.emit()
        except Exception as e:
            self.errore.emit(str(e))


# ---------------- piccoli mattoni grafici ----------------
def scheda():
    f = QFrame()
    f.setObjectName('scheda')
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(8)
    return f, lay


def etichetta(testo, nome=None, a_capo=True):
    l = QLabel(testo)
    if nome:
        l.setObjectName(nome)
    l.setWordWrap(a_capo)
    l.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return l


def bottone(testo, tipo=None):
    b = QPushButton(testo)
    if tipo:
        b.setObjectName(tipo)
    b.setCursor(Qt.PointingHandCursor)
    return b


def pagina(titolo, sottotitolo):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(32, 28, 32, 24)
    lay.setSpacing(14)
    lay.addWidget(etichetta(titolo, 'titolo'))
    lay.addWidget(etichetta(sottotitolo, 'sottotitolo'))
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(w)
    return area, lay


def apri_cartella(p):
    if p and os.path.isdir(p):
        if percorsi.IS_WIN:
            os.startfile(p)
        else:
            subprocess.Popen(['xdg-open', p])


class Finestra(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CotW Italiano  ' + VERSIONE)
        self.resize(1040, 720)
        self.setMinimumSize(880, 600)
        self.lavoro = None
        self.manifest, self.errore_online, self.controllato = None, None, False
        self.c_doc, self.c_stato, self.c_lavoro, self.c_online = None, None, None, {}
        self.gioco = percorsi.trova_gioco()
        cfg = percorsi.leggi_config()
        self.sorgente = cfg.get('pacchetto') or self._pacchetto_predefinito()

        centro = QWidget()
        h = QHBoxLayout(centro)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        barra = QWidget()
        barra.setObjectName('barra')
        barra.setFixedWidth(220)
        bl = QVBoxLayout(barra)
        bl.setContentsMargins(0, 0, 0, 12)
        bl.setSpacing(0)
        bl.addWidget(etichetta('CotW Italiano', 'logo', False))
        bl.addWidget(etichetta('Traduzione e doppiaggio\ndi theHunter: Call of the Wild', 'sottologo'))
        self.pagine = QStackedWidget()
        self.gruppo = QButtonGroup(self)
        for i, (nome, costruttore) in enumerate([('Home', self._home), ('Installa', self._installa), ('Avvio gioco', self._avvio),
                                                 ('Salvataggi', self._salvataggi), ('Strumenti', self._strumenti),
                                                 ('Segnala errore', self._segnala), ('Contribuisci', self._contribuisci),
                                                 ('Impostazioni', self._impostazioni)]):
            b = QPushButton(nome)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.gruppo.addButton(b, i)
            bl.addWidget(b)
            self.pagine.addWidget(costruttore())
        self.gruppo.idClicked.connect(self._vai)
        bl.addStretch(1)
        disc = QPushButton('Entra nel Discord')
        disc.setObjectName('discord')
        disc.setCursor(Qt.PointingHandCursor)
        disc.setToolTip('Apre il server Discord: novita\', aiuto e segnalazioni.')
        disc.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(rete.DISCORD)))
        bl.addWidget(disc)
        dona = QPushButton('\u2665  Sostieni il progetto')
        dona.setObjectName('dona')
        dona.setCursor(Qt.PointingHandCursor)
        dona.setToolTip('Una donazione libera su Ko-fi: aiuta a pagare le voci per le mappe nuove.')
        dona.clicked.connect(self._dona)
        bl.addWidget(dona)
        bl.addWidget(etichetta('di Mirko Del Sette', 'sottologo'))
        h.addWidget(barra)
        h.addWidget(self.pagine, 1)
        self.setCentralWidget(centro)
        self.statusBar().showMessage('Pronto.')
        self.gruppo.button(0).setChecked(True)
        self.aggiorna_tutto()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._controlla_gioco)
        self.timer.start(5000)
        if not self.gioco:
            QTimer.singleShot(300, self._chiedi_gioco)
        QTimer.singleShot(800, self._controlla_online)          # controllo aggiornamenti all'avvio

    # ---------------- utilita' ----------------
    def _pacchetto_predefinito(self):
        p = os.path.join(os.path.expanduser('~'), 'Desktop', 'mod italiano', 'MOD')
        return p if os.path.isdir(p) else ''

    def _vai_a(self, i):
        self.gruppo.button(i).setChecked(True)
        self._vai(i)

    def _vai(self, i):
        self.pagine.setCurrentIndex(i)
        self.aggiorna_tutto()

    def dz(self):
        return percorsi.dropzone(self.gioco) if self.gioco else None

    def _messaggio(self, titolo, testo, tipo='info'):
        f = {'info': QMessageBox.information, 'avviso': QMessageBox.warning, 'errore': QMessageBox.critical}[tipo]
        f(self, titolo, testo)

    def _conferma(self, titolo, testo):
        return QMessageBox.question(self, titolo, testo, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def _pronto(self, serve_gioco=True):
        """Controlli prima di ogni operazione: gioco trovato, gioco chiuso, nessun altro lavoro in corso."""
        if self.lavoro and self.lavoro.isRunning():
            self._messaggio('Attendi', 'C\'e\' gia\' un\'operazione in corso.', 'avviso')
            return False
        if serve_gioco and not self.gioco:
            self._messaggio('Gioco non trovato', 'Indica la cartella del gioco nella scheda Impostazioni.', 'avviso')
            return False
        if percorsi.gioco_in_esecuzione():
            self._messaggio('Chiudi il gioco', 'theHunter: Call of the Wild e\' aperto. Chiudilo e riprova.', 'avviso')
            return False
        return True

    def _avvia(self, funzione, barra=None, etichetta_stato=None, al_termine=None):
        self.lavoro = Lavoro(funzione)

        def av(a, b, t):
            if barra:
                barra.setMaximum(max(b, 1))
                barra.setValue(a)
            if etichetta_stato:
                etichetta_stato.setText(('%s: ' % t if t and '/' not in t else '') + '%d di %d' % (a, b))

        def fine(msg):
            if barra:
                barra.setValue(barra.maximum())
            self.statusBar().showMessage(msg)
            self.aggiorna_tutto()
            self._messaggio('Fatto', msg)
            if al_termine:
                al_termine()

        def err(msg):
            self.statusBar().showMessage('Errore: ' + msg)
            self.aggiorna_tutto()
            self._messaggio('Qualcosa e\' andato storto', msg, 'errore')

        self.lavoro.avanzamento.connect(av)
        self.lavoro.finito.connect(fine)
        self.lavoro.errore.connect(err)
        if barra:
            barra.setValue(0)
            barra.show()
        self.lavoro.start()

    def _controlla_gioco(self):
        aperto = percorsi.gioco_in_esecuzione()
        self.avviso_gioco.setVisible(aperto)

    def _chiedi_gioco(self):
        self._messaggio('Cartella del gioco', 'Non ho trovato theHunter: Call of the Wild da solo.\n'
                        'Scegli la cartella del gioco (quella che contiene theHunterCotW_F.exe).', 'avviso')
        self._scegli_gioco()

    # ======================= HOME =======================
    def _home(self):
        area, lay = pagina('Home', 'Lo stato della traduzione italiana sul tuo PC.')
        self.avviso_gioco = etichetta('Il gioco e\' aperto: chiudilo prima di installare, rimuovere o cambiare qualcosa.', 'avviso')
        self.avviso_gioco.hide()
        lay.addWidget(self.avviso_gioco)
        self.banner_agg = QFrame()
        self.banner_agg.setObjectName('banner')
        bl = QHBoxLayout(self.banner_agg)
        bl.setContentsMargins(16, 10, 12, 10)
        self.banner_testo = etichetta('', None, True)
        bl.addWidget(self.banner_testo, 1)
        b = bottone('Aggiorna adesso', 'primario')
        b.clicked.connect(lambda: self._vai_a(1))
        bl.addWidget(b)
        self.banner_agg.hide()
        lay.addWidget(self.banner_agg)
        self.banner_prog = QFrame()
        self.banner_prog.setObjectName('banner')
        bl = QHBoxLayout(self.banner_prog)
        bl.setContentsMargins(16, 10, 12, 10)
        self.banner_prog_testo = etichetta('', None, True)
        bl.addWidget(self.banner_prog_testo, 1)
        b = bottone('Aggiorna programma', 'primario')
        b.clicked.connect(self._aggiorna_programma)
        bl.addWidget(b)
        self.banner_prog.hide()
        lay.addWidget(self.banner_prog)

        griglia = QGridLayout()
        griglia.setSpacing(14)
        self.h = {}

        def casella(r, c, chiave, nome, righe=1):
            f, l = scheda()
            l.addWidget(etichetta(nome, 'nome'))
            valori = []
            for _ in range(righe):
                v = etichetta('...')
                l.addWidget(v)
                valori.append(v)
            d = etichetta('', 'tenue')
            l.addWidget(d)
            l.addStretch(1)
            self.h[chiave] = (valori, d, l)
            griglia.addWidget(f, r, c)
            griglia.setColumnStretch(c, 1)

        casella(0, 0, 'traduzione', 'Traduzione italiana', 2)
        casella(0, 1, 'avvio', 'Avvio con le mod')
        casella(1, 0, 'missioni', 'Missioni e salvataggi')
        casella(1, 1, 'mod', 'Mod nel gioco (online)')
        casella(2, 0, 'quad', 'Volume del quad')
        casella(2, 1, 'gioco', 'Gioco')
        lay.addLayout(griglia)

        b = bottone('Installa / aggiorna', 'primario')
        b.clicked.connect(lambda: self._vai_a(1))
        self.h['traduzione'][2].addWidget(b)
        b = bottone('Sistema l\'avvio')
        b.clicked.connect(lambda: self._vai_a(2))
        self.h['avvio'][2].addWidget(b)
        r = QHBoxLayout()
        b = bottone('Azzera missioni', 'pericolo')
        b.clicked.connect(lambda: self._vai_a(3))
        r.addWidget(b)
        b = bottone('Backup salvataggi')
        b.clicked.connect(lambda: self._vai_a(3))
        r.addWidget(b)
        self.h['missioni'][2].addLayout(r)
        self.b_attiva = bottone('Disattiva tutte le mod')
        self.b_attiva.clicked.connect(self._attiva_disattiva)
        self.h['mod'][2].addWidget(self.b_attiva)
        b = bottone('Cambia volume')
        b.clicked.connect(lambda: self._vai_a(4))
        self.h['quad'][2].addWidget(b)
        b = bottone('Impostazioni')
        b.clicked.connect(lambda: self._vai_a(7))
        self.h['gioco'][2].addWidget(b)
        lay.addStretch(1)
        return area

    def _copia_opzioni(self):
        QGuiApplication.clipboard().setText(OPZIONI_AVVIO)
        self.statusBar().showMessage('Opzioni di avvio copiate: incollale in Steam > Proprieta\' > Opzioni di avvio.')

    def _imposta(self, widget, testo, tipo):
        widget.setText(testo)
        widget.setObjectName(tipo)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _aggiorna_home(self):
        h = self.h
        conf = aggiornamenti.confronta(self.manifest, self.dz()) if (self.manifest and self.gioco) else {}
        da_agg = [installa.COMPONENTI[c]['nome'] for c, v in conf.items() if v[2] == 'aggiornare']
        self.banner_agg.setVisible(bool(da_agg))
        nuova = programma.disponibile(self.c_online)
        self.banner_prog.setVisible(bool(nuova))
        if nuova:
            self.banner_prog_testo.setText('E\' uscita la versione %s del programma (tu hai la %s).%s' % (
                nuova['versione'], VERSIONE, ('  Novita\': ' + ' / '.join(nuova['novita'])) if nuova.get('novita') else ''))
        if da_agg:
            self.banner_testo.setText('E\' disponibile la versione %s della mod (%s).%s' % (
                self.manifest['versione'], ', '.join(da_agg),
                ('  Novita\': ' + ' / '.join(self.manifest.get('novita', []))) if self.manifest.get('novita') else ''))
        # traduzione: testo + doppiaggio
        nomi = {'testo': 'Testo', 'audio': 'Doppiaggio'}
        for i, comp in enumerate(('testo', 'audio')):
            if not self.gioco:
                self._imposta(h['traduzione'][0][i], nomi[comp] + ': -', 'tenue')
                continue
            st, n = installa.stato_componente(self.dz(), comp, self.sorgente)
            t, tipo = {'installato': ('installato', 'ok'), 'parziale': ('incompleto', 'attenzione'),
                       'presente': ('gia\' presente, diverso dal pacchetto', 'attenzione'),
                       'non installato': ('non installato', 'tenue')}[st]
            self._imposta(h['traduzione'][0][i], '%s: %s' % (nomi[comp], t), tipo)
        h['traduzione'][1].setText('Sottotitoli, menu e missioni + le voci italiane di tutti i personaggi.')
        # avvio
        st = self._aggiorna_avvio()
        self._imposta(h['avvio'][0][0], {'impostate': 'Pronto', 'mancano': 'Da sistemare', 'diverse': 'Da sistemare',
                                         'nessun_steam': 'Steam non trovato'}[st], 'ok' if st == 'impostate' else 'attenzione')
        h['avvio'][1].setText('Senza le opzioni di avvio il gioco ignora tutte le mod.' if st != 'impostate' else
                              'Steam avvia il gioco con le mod.')
        # missioni e salvataggi
        bk = missioni.elenco_backup()
        prof = percorsi.profili_salvataggi()
        self._imposta(h['missioni'][0][0], ('Ultimo backup: %s' % bk[0]['data']) if bk else 'Nessun backup ancora',
                      'ok' if bk else 'tenue')
        h['missioni'][1].setText('Azzera le missioni per rigiocare la storia in italiano (backup automatico).' if prof else
                                 'Salvataggi non trovati: indicali in Impostazioni.')
        # mod attive / online
        attiva = bool(self.gioco) and percorsi.mod_attiva(self.gioco)
        self._imposta(h['mod'][0][0], 'Attive' if attiva else 'Disattivate (gioco originale)', 'ok' if attiva else 'attenzione')
        h['mod'][1].setText('Prima di giocare online disattivale.' if attiva else 'Puoi giocare online. Riattivale per la traduzione.')
        self.b_attiva.setText('Disattiva tutte le mod (per l\'online)' if attiva else 'Riattiva le mod')
        self.b_attiva.setEnabled(bool(self.gioco))
        # quad
        if self.gioco:
            v = quad.volume_attuale(self.dz())
            self._imposta(h['quad'][0][0], 'Originale (100%)' if v == 100 else ('%d%%' % v if v is not None else 'Modificato'),
                          'ok' if v != 100 else 'tenue')
        h['quad'][1].setText('Solo il volume che senti tu, non quello che sentono gli animali.')
        # gioco
        if self.gioco:
            self._imposta(h['gioco'][0][0], 'Trovato', 'ok')
            h['gioco'][1].setText(self.gioco)
        else:
            self._imposta(h['gioco'][0][0], 'Non trovato', 'errore')
            h['gioco'][1].setText('Indicalo nelle Impostazioni.')

    def _attiva_disattiva(self):
        if not self._pronto():
            return
        try:
            if percorsi.mod_attiva(self.gioco):
                installa.disattiva_mod(self.gioco)
                self.statusBar().showMessage('Mod disattivate: il gioco parte originale.')
            else:
                installa.attiva_mod(self.gioco)
                self.statusBar().showMessage('Mod riattivate.')
        except Exception as e:
            self._messaggio('Non riesco', str(e), 'errore')
        self.aggiorna_tutto()

    # ======================= INSTALLA =======================
    def _installa(self):
        area, lay = pagina('Installa', 'Testo e doppiaggio si installano insieme o uno alla volta. '
                                       'Il programma tocca solo i suoi file: le altre mod restano come sono.')
        # --- da internet ---
        f, l = scheda()
        riga = QHBoxLayout()
        riga.addWidget(etichetta('Da internet (consigliato)', 'nome', False))
        riga.addStretch(1)
        self.i_online = etichetta('Controllo...', 'tenue', False)
        riga.addWidget(self.i_online)
        l.addLayout(riga)
        self.i_novita = etichetta('', 'tenue')
        l.addWidget(self.i_novita)
        l.addWidget(etichetta('Scarica solo quello che serve in una cartella del programma, controlla che sia integro e poi '
                              'lo installa. Se la mod e\' gia\' nel gioco, riusa i file che sono uguali.', 'tenue'))
        r = QHBoxLayout()
        b = bottone('Scarica e installa', 'primario')
        b.clicked.connect(self._scarica_installa)
        r.addWidget(b)
        b = bottone('Controlla aggiornamenti')
        b.clicked.connect(lambda: self._controlla_online(mostra=True))
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)

        # --- componenti ---
        self.i_comp = {}
        for comp in ('testo', 'audio'):
            f, l = scheda()
            riga = QHBoxLayout()
            cb = QCheckBox(installa.COMPONENTI[comp]['nome'])
            cb.setChecked(True)
            stato = etichetta('', None, False)
            riga.addWidget(cb)
            riga.addStretch(1)
            riga.addWidget(stato)
            l.addLayout(riga)
            l.addWidget(etichetta(installa.COMPONENTI[comp]['descrizione'], 'tenue'))
            info = etichetta('', 'tenue')
            l.addWidget(info)
            self.i_comp[comp] = (cb, stato, info)
            lay.addWidget(f)

        r = QHBoxLayout()
        self.b_rimuovi = bottone('Rimuovi selezionati', 'pericolo')
        self.b_rimuovi.clicked.connect(self._fai_rimuovi)
        r.addWidget(self.b_rimuovi)
        r.addStretch(1)
        lay.addLayout(r)
        self.i_barra = QProgressBar()
        self.i_barra.hide()
        self.i_testo = etichetta('', 'tenue')
        lay.addWidget(self.i_barra)
        lay.addWidget(self.i_testo)

        # --- da cartella ---
        f, l = scheda()
        l.addWidget(etichetta('Da una cartella (avanzato)', 'nome'))
        l.addWidget(etichetta('Installa da un pacchetto sul PC (la cartella con "mod ita testo" e "mod audio ita", '
                              'es. Desktop\\mod italiano\\MOD).', 'tenue'))
        r = QHBoxLayout()
        self.e_sorgente = QLineEdit(self.sorgente)
        self.e_sorgente.setReadOnly(True)
        r.addWidget(self.e_sorgente, 1)
        bs = bottone('Scegli...')
        bs.clicked.connect(self._scegli_sorgente)
        r.addWidget(bs)
        bi = bottone('Installa da cartella')
        bi.clicked.connect(self._fai_installa)
        r.addWidget(bi)
        l.addLayout(r)
        lay.addWidget(f)
        lay.addStretch(1)
        return area

    def _scegli_sorgente(self):
        p = QFileDialog.getExistingDirectory(self, 'Scegli la cartella del pacchetto (es. mod italiano\\MOD)', self.sorgente or '')
        if p:
            self.sorgente = os.path.normpath(p)
            cfg = percorsi.leggi_config()
            cfg['pacchetto'] = self.sorgente
            percorsi.salva_config(cfg)
            self.e_sorgente.setText(self.sorgente)
            self.aggiorna_tutto()

    def _aggiorna_installa(self):
        m = self.manifest
        conf = aggiornamenti.confronta(m, self.dz()) if (m and self.gioco) else {}
        if self.errore_online:
            self._imposta(self.i_online, 'Non raggiungibile', 'attenzione')
            self.i_novita.setText(self.errore_online)
        elif m is None and self.controllato:
            self._imposta(self.i_online, 'Nessuna versione pubblicata ancora', 'tenue')
            self.i_novita.setText('')
        elif m:
            da_agg = [c for c, v in conf.items() if v[2] != 'aggiornato']
            self._imposta(self.i_online, ('Versione %s disponibile' % m['versione']) if da_agg else
                          ('Aggiornata (%s)' % m['versione']), 'attenzione' if da_agg else 'ok')
            nov = m.get('novita') or []
            self.i_novita.setText(('Novita\' (%s): ' % m.get('data', '')) + ' / '.join(nov) if nov else 'Pubblicata il %s' % m.get('data', ''))
        for comp, (cb, stato, inf) in self.i_comp.items():
            if not self.gioco:
                continue
            st, n = installa.stato_componente(self.dz(), comp, self.sorgente)
            mia = installa.leggi_stato()['componenti'].get(comp, {}).get('versione')
            t, tipo = {'installato': ('Installato' + (' (%s)' % mia if mia else ''), 'ok'), 'parziale': ('Incompleto', 'attenzione'),
                       'presente': ('Gia\' presente (diverso dal pacchetto)', 'attenzione'),
                       'non installato': ('Non installato', 'tenue')}[st]
            if comp in conf and conf[comp][2] == 'aggiornare':
                t, tipo = 'Aggiornamento disponibile: %s' % conf[comp][1], 'attenzione'
            self._imposta(stato, t, tipo)
            if m and comp in m.get('componenti', {}):
                pac = m['componenti'][comp]['pacchetti']
                tot = sum(p.get('dimensione', 0) for p in pac if p.get('contiene') == 'tutto') / 1e6
                inf.setText('Online: %d file, pacchetto completo %s MB (gli aggiornamenti scaricano solo cio\' che cambia).'
                            % (len(m['componenti'][comp]['file']), ('%.0f' % tot) if tot >= 1 else 'meno di 1'))
            else:
                inf.setText('')

    def _selezionati(self):
        return [c for c, (cb, _, _) in self.i_comp.items() if cb.isChecked()]

    # --- controllo online in background ---
    def _controlla_online(self, mostra=False):
        if getattr(self, '_ctrl', None) and self._ctrl.isRunning():
            return
        th = ControlloOnline()
        self._ctrl = th

        def fatto(m):
            self.manifest, self.errore_online, self.controllato = m, None, True
            self.c_doc, self.c_stato, self.c_online = th.doc, th.stato, th.online
            self.aggiorna_tutto()
            if not self._popup_programma():
                self._popup_contribuisci()
            if mostra:
                self._messaggio('Aggiornamenti', self.i_online.text())

        def errore(e):
            self.errore_online, self.controllato = e, True
            self.aggiorna_tutto()
            if mostra:
                self._messaggio('Aggiornamenti', e, 'avviso')
        th.fatto.connect(fatto)
        th.errore.connect(errore)
        th.start()

    def _scarica_installa(self):
        sel = self._selezionati()
        if not sel:
            self._messaggio('Niente da fare', 'Spunta Testo e/o Doppiaggio.', 'avviso')
            return
        if not self._pronto():
            return
        dz = self.dz()

        def lavoro(av):
            m = rete.leggi_manifest()
            if not m:
                raise RuntimeError('Su GitHub non c\'e\' ancora nessuna versione pubblicata.')
            righe = []
            for c in sel:
                nome = installa.COMPONENTI[c]['nome']
                mb, copiati = aggiornamenti.aggiorna_componente(m, c, dz, avanzamento=av)
                righe.append('%s %s: scaricati %.1f MB, %s' % (nome, m['componenti'][c]['versione'], mb,
                                                              ('%d file installati' % copiati) if copiati else 'gia\' aggiornato'))
            self.manifest = m
            return 'Fatto.\n\n' + '\n'.join(righe) + '\n\nPuoi avviare il gioco.'
        self._avvia(lavoro, self.i_barra, self.i_testo)

    def _fai_installa(self):
        sel = self._selezionati()
        if not sel:
            self._messaggio('Niente da fare', 'Spunta Testo e/o Doppiaggio.', 'avviso')
            return
        if not self._pronto():
            return
        info = installa.info_pacchetto(self.sorgente)
        mancano = [installa.COMPONENTI[c]['nome'] for c in sel if not info.get(c)]
        if mancano:
            self._messaggio('Pacchetto incompleto', 'Nel pacchetto non trovo: ' + ', '.join(mancano), 'avviso')
            return
        dz, sorg = self.dz(), self.sorgente

        def lavoro(av):
            righe = []
            for c in sel:
                nome = installa.COMPONENTI[c]['nome']
                n, copiati = installa.installa(c, sorg, dz, avanzamento=lambda a, b, t, nome=nome: av(a, b, nome))
                righe.append('%s: %s' % (nome, ('%d file copiati' % copiati) if copiati else
                                         'gia\' aggiornato, niente da copiare (%d file controllati)' % n))
            return 'Installazione completata.\n\n' + '\n'.join(righe) + '\n\nPuoi avviare il gioco.'
        self._avvia(lavoro, self.i_barra, self.i_testo)

    def _fai_rimuovi(self):
        sel = self._selezionati()
        if not sel or not self._pronto():
            return
        nomi = ', '.join(installa.COMPONENTI[c]['nome'] for c in sel)
        if not self._conferma('Rimuovere?', 'Tolgo dal gioco: %s.\nLe altre mod non vengono toccate. Continuo?' % nomi):
            return
        dz = self.dz()

        def lavoro(av):
            n = sum(installa.rimuovi(c, dz, avanzamento=lambda a, b, t, c=c: av(a, b, installa.COMPONENTI[c]['nome']))
                    for c in sel)
            return 'Rimossi %d file. Il gioco tornera\' in inglese per le parti tolte.' % n
        self._avvia(lavoro, self.i_barra, self.i_testo)

    # ======================= AVVIO GIOCO =======================
    def _avvio(self):
        area, lay = pagina('Avvio gioco', 'Il gioco carica le mod solo se parte con le opzioni giuste. '
                                          'Qui le imposti con un clic.')
        f, l = scheda()
        riga = QHBoxLayout()
        riga.addWidget(etichetta('Steam', 'nome', False))
        riga.addStretch(1)
        self.a_stato = etichetta('', None, False)
        riga.addWidget(self.a_stato)
        l.addLayout(riga)
        l.addWidget(etichetta('Il programma scrive le opzioni di avvio direttamente in Steam. Steam deve essere CHIUSO del tutto '
                              '(anche dall\'icona vicino all\'orologio), altrimenti quando si chiude le cancella. '
                              'Fa sempre un backup della configurazione di Steam.', 'tenue'))
        self.a_steam_aperto = etichetta('Steam e\' aperto: chiudilo del tutto, poi premi "Imposta".', 'avviso')
        self.a_steam_aperto.hide()
        l.addWidget(self.a_steam_aperto)
        r = QHBoxLayout()
        b = bottone('Imposta in automatico', 'primario')
        b.clicked.connect(lambda: self._steam(False))
        r.addWidget(b)
        b = bottone('Togli')
        b.clicked.connect(lambda: self._steam(True))
        r.addWidget(b)
        b = bottone('Ricontrolla')
        b.clicked.connect(self.aggiorna_tutto)
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('Senza launcher (collegamento sul desktop)', 'nome'))
        l.addWidget(etichetta('Crea un\'icona sul desktop, "theHunter COTW con mod", che avvia il gioco direttamente con le mod. '
                              'Usa sempre quella per giocare con la traduzione.', 'tenue'))
        r = QHBoxLayout()
        b = bottone('Crea collegamento sul desktop', 'primario')
        b.clicked.connect(self._collegamento)
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('Epic Games o a mano', 'nome'))
        l.addWidget(etichetta('Epic Games: Libreria > tre puntini sul gioco > Gestisci > Argomenti della riga di comando aggiuntivi: '
                              'incolla le opzioni. In Steam a mano: tasto destro sul gioco > Proprieta\' > Opzioni di avvio.', 'tenue'))
        r = QHBoxLayout()
        e = QLineEdit(OPZIONI_AVVIO)
        e.setReadOnly(True)
        r.addWidget(e, 1)
        b = bottone('Copia')
        b.clicked.connect(self._copia_opzioni)
        r.addWidget(b)
        l.addLayout(r)
        lay.addWidget(f)
        lay.addWidget(etichetta('Le opzioni possono restare sempre: quando premi "Disattiva tutte le mod" il gioco parte originale lo stesso.', 'tenue'))
        lay.addStretch(1)
        return area

    def _aggiorna_avvio(self):
        st, testo = avvio.stato_steam()
        t, n = {'impostate': ('Impostate', 'ok'), 'mancano': ('Da impostare', 'attenzione'),
                'diverse': ('Da impostare (ci sono altre opzioni)', 'attenzione'),
                'nessun_steam': ('Steam non trovato', 'tenue')}[st]
        self.a_stato.setText(t)
        self.a_stato.setObjectName(n)
        self.a_stato.style().unpolish(self.a_stato)
        self.a_stato.style().polish(self.a_stato)
        self.a_steam_aperto.setVisible(st != 'impostate' and avvio.steam_in_esecuzione())
        return st

    def _steam(self, togli):
        if not self._pronto(serve_gioco=False):
            return
        try:
            n = avvio.imposta_steam(togli=togli)
            self._messaggio('Fatto', ('Opzioni tolte da Steam.' if togli else
                                      'Opzioni di avvio impostate in Steam (%d account). Ora puoi aprire Steam e giocare.' % n))
        except Exception as e:
            self._messaggio('Non riesco', str(e), 'avviso')
        self.aggiorna_tutto()

    def _collegamento(self):
        if not self.gioco:
            self._messaggio('Gioco non trovato', 'Indica la cartella del gioco nella scheda Impostazioni.', 'avviso')
            return
        try:
            p = avvio.crea_collegamento(self.gioco)
            self._messaggio('Fatto', 'Collegamento creato:\n%s' % p)
        except Exception as e:
            self._messaggio('Non riesco', str(e), 'errore')

    # ======================= SALVATAGGI =======================
    def _salvataggi(self):
        area, lay = pagina('Salvataggi', 'Azzera le missioni per rigiocare la storia in italiano, e fai backup dei salvataggi.')
        r = QHBoxLayout()
        r.addWidget(etichetta('Salvataggio:', 'nome', False))
        self.c_profili = QComboBox()
        self.c_profili.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        r.addWidget(self.c_profili, 1)
        lay.addLayout(r)

        f, l = scheda()
        l.addWidget(etichetta('Azzera le missioni', 'nome'))
        l.addWidget(etichetta('Rimette TUTTE le missioni di TUTTE le riserve all\'inizio, per rivivere la storia in italiano. '
                              'Livello, soldi, armi e trofei restano.', 'tenue'))
        l.addWidget(etichetta('ATTENZIONE: le missioni gia\' fatte ripartono da zero. Prima di azzerare il programma fa da solo '
                              'un backup ("Prima di azzerare le missioni"), che trovi qui sotto e puoi ripristinare quando vuoi.',
                              'pericolo_box'))
        l.addWidget(etichetta('Prima: disattiva Steam Cloud (Steam > tasto destro sul gioco > Proprieta\' > Generali > togli la '
                              'spunta a Steam Cloud). Dopo: riattivalo e, se chiede, scegli i file LOCALI.', 'avviso'))
        r = QHBoxLayout()
        b = bottone('Azzera le missioni', 'pericolo')
        b.clicked.connect(self._azzera)
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('Backup dei salvataggi', 'nome'))
        l.addWidget(etichetta('Copia tutto il salvataggio (livello, soldi, armi, trofei, missioni). Puoi farne quanti vuoi, '
                              'dargli un nome e rimetterne uno qualsiasi.', 'tenue'))
        r = QHBoxLayout()
        self.e_nome_backup = QLineEdit()
        self.e_nome_backup.setPlaceholderText('Nome del backup (es. "Prima di Cuatro Colinas")')
        r.addWidget(self.e_nome_backup, 1)
        b = bottone('Crea backup', 'primario')
        b.clicked.connect(self._crea_backup)
        r.addWidget(b)
        l.addLayout(r)
        self.l_backup = QListWidget()
        self.l_backup.setMinimumHeight(160)
        l.addWidget(self.l_backup)
        r = QHBoxLayout()
        for testo, fn, tipo in [('Ripristina', self._ripristina_backup, None), ('Rinomina', self._rinomina_backup, None),
                                ('Elimina', self._elimina_backup, 'pericolo'),
                                ('Apri cartella', lambda: apri_cartella(missioni.cartella_backup()), None)]:
            b = bottone(testo, tipo)
            b.clicked.connect(fn)
            r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)
        lay.addStretch(1)
        return area

    def _aggiorna_salvataggi(self):
        sel = self.c_profili.currentData()
        self.c_profili.clear()
        prof = percorsi.profili_salvataggi()
        for p in prof:
            self.c_profili.addItem(p, p)
        if not prof:
            self.c_profili.addItem('Nessun salvataggio trovato (indicalo in Impostazioni)', None)
        elif sel in prof:
            self.c_profili.setCurrentIndex(prof.index(sel))
        self.l_backup.clear()
        bk = missioni.elenco_backup()
        for b in bk:
            it = QListWidgetItem('%s      %s' % (b['nome'], b['data']))
            it.setData(Qt.UserRole, b['cartella'])
            it.setToolTip(b['cartella'])
            self.l_backup.addItem(it)
        if not bk:
            it = QListWidgetItem('Nessun backup ancora')
            it.setFlags(Qt.NoItemFlags)
            self.l_backup.addItem(it)

    def _backup_scelto(self):
        it = self.l_backup.currentItem()
        b = it.data(Qt.UserRole) if it else None
        if not b:
            self._messaggio('Scegli un backup', 'Clicca prima un backup nell\'elenco.', 'avviso')
        return b

    def _crea_backup(self):
        prof = self.c_profili.currentData()
        if not prof:
            self._messaggio('Salvataggio non trovato', 'Indica la cartella dei salvataggi nella scheda Impostazioni.', 'avviso')
            return
        if not self._pronto(serve_gioco=False):
            return
        nome = self.e_nome_backup.text().strip()
        self.e_nome_backup.clear()
        self._avvia(lambda av: 'Backup creato: %s' % os.path.basename(missioni.backup(prof, nome)))

    def _ripristina_backup(self):
        b = self._backup_scelto()
        if not b or not self._pronto(serve_gioco=False):
            return
        if not self._conferma('Ripristinare?', 'Rimetto i salvataggi di questo backup.\n'
                                               '(Lo stato attuale viene salvato prima in un altro backup.)'):
            return
        self._avvia(lambda av: 'Salvataggi ripristinati in:\n%s' % missioni.ripristina(b))

    def _rinomina_backup(self):
        b = self._backup_scelto()
        if not b:
            return
        it = self.l_backup.currentItem()
        attuale = it.text().split('      ')[0]
        nuovo, ok = QInputDialog.getText(self, 'Rinomina backup', 'Nuovo nome:', text=attuale)
        if ok and nuovo.strip():
            missioni.rinomina(b, nuovo)
            self.aggiorna_tutto()

    def _elimina_backup(self):
        b = self._backup_scelto()
        if not b:
            return
        if self._conferma('Eliminare?', 'Elimino definitivamente questo backup?'):
            try:
                missioni.elimina(b)
            except Exception as e:
                self._messaggio('Non riesco', str(e), 'errore')
            self.aggiorna_tutto()

    def _azzera(self):
        prof = self.c_profili.currentData()
        if not prof:
            self._messaggio('Salvataggio non trovato', 'Indica la cartella dei salvataggi nella scheda Impostazioni.', 'avviso')
            return
        if not self._pronto(serve_gioco=False):
            return
        m = QMessageBox(self)
        m.setIcon(QMessageBox.Warning)
        m.setWindowTitle('Sei sicuro?')
        m.setText('<b style="color:#ff8a80">Sei sicuro di voler azzerare le missioni?</b>')
        m.setInformativeText('Tutte le missioni di tutte le riserve ripartono da zero.\n\nSalvataggio: %s\n\n'
                             'Prima faccio un backup completo, che puoi ripristinare quando vuoi.\n'
                             'Hai disattivato Steam Cloud?' % prof)
        si = m.addButton('Si\', azzera', QMessageBox.DestructiveRole)
        m.addButton('Annulla', QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() is not si:
            return
        self._avvia(lambda av: 'Missioni azzerate. Backup "Prima di azzerare le missioni" creato.\n%s' % missioni.azzera(prof))

    # ======================= STRUMENTI =======================
    def _strumenti(self):
        area, lay = pagina('Strumenti', 'Regolazioni del gioco.')
        f, l = scheda()
        l.addWidget(etichetta('Volume del quad', 'nome'))
        l.addWidget(etichetta('Abbassa il motore del quad, cosi\' non copre le voci della narrazione. Cambia solo '
                              'quello che senti tu: gli animali lo sentono come prima. Vale dal prossimo avvio del gioco.', 'tenue'))
        r = QHBoxLayout()
        self.s_quad = QSlider(Qt.Horizontal)
        self.s_quad.setRange(0, 100)
        self.s_quad.setSingleStep(5)
        self.s_quad.setPageStep(10)
        self.s_quad.setValue(50)
        self.l_quad = QLabel('50%')
        self.l_quad.setFixedWidth(52)
        self.s_quad.valueChanged.connect(lambda v: self.l_quad.setText('%d%%' % v))
        r.addWidget(self.s_quad, 1)
        r.addWidget(self.l_quad)
        l.addLayout(r)
        r = QHBoxLayout()
        b1 = bottone('Applica volume', 'primario')
        b2 = bottone('Suono originale')
        b1.clicked.connect(self._applica_quad)
        b2.clicked.connect(self._quad_originale)
        r.addWidget(b1)
        r.addWidget(b2)
        r.addStretch(1)
        self.l_quad_ora = etichetta('', 'tenue', False)
        r.addWidget(self.l_quad_ora)
        l.addLayout(r)
        lay.addWidget(f)
        lay.addStretch(1)
        return area

    def _aggiorna_strumenti(self):
        if self.gioco:
            v = quad.volume_attuale(self.dz())
            self.l_quad_ora.setText('Adesso: ' + ('originale' if v == 100 else ('%d%%' % v if v is not None else '?')))

    def _applica_quad(self):
        if not self._pronto():
            return
        v = self.s_quad.value()
        gioco, dz = self.gioco, self.dz()

        def lavoro(av):
            if v == 100:
                quad.ripristina(dz)
                return 'Quad al volume originale.'
            return 'Volume del quad impostato al %d%% (%d suoni). Vale dal prossimo avvio del gioco.' % (v, quad.applica(gioco, dz, v))
        self._avvia(lavoro)

    def _quad_originale(self):
        if not self._pronto():
            return
        quad.ripristina(self.dz())
        self.statusBar().showMessage('Quad tornato al suono originale.')
        self.aggiorna_tutto()

    # ======================= SEGNALA ERRORE =======================
    def _segnala(self):
        area, lay = pagina('Segnala errore', 'Hai visto una scritta sbagliata o sentito una voce sbagliata? Compila qui sotto '
                                            'e premi Invia: la segnalazione arriva da sola sul Discord della mod.')
        f, l = scheda()
        l.addWidget(etichetta('1. Mappa', 'nome'))
        self.s_mappa = QComboBox()
        self.s_mappa.addItems(segnala.MAPPE)
        self.s_mappa.currentIndexChanged.connect(lambda _=0: self._segnala_cerca())
        l.addWidget(self.s_mappa)

        l.addSpacing(6)
        l.addWidget(etichetta('2. Che problema c\'e\'?', 'nome'))
        self.s_tipo = QComboBox()
        self.s_tipo.addItems(segnala.TIPI)
        l.addWidget(self.s_tipo)

        l.addSpacing(6)
        l.addWidget(etichetta('3. Scrivi la frase o la parola sbagliata', 'nome'))
        self.s_cerca = QLineEdit()
        self.s_cerca.setPlaceholderText('es.  Ecco qui mano ferma adesso')
        self.s_cerca.textChanged.connect(lambda _='': self._segnala_cerca())
        l.addWidget(self.s_cerca)
        self.s_forse = etichetta('Forse e\' una di queste? Se si\', cliccala (non e\' obbligatorio).', 'tenue')
        l.addWidget(self.s_forse)
        self.s_lista = QListWidget()
        self.s_lista.setFixedHeight(84)
        l.addWidget(self.s_lista)
        self.s_forse.hide()
        self.s_lista.hide()

        l.addSpacing(6)
        l.addWidget(etichetta('4. Cosa non va? (facoltativo)', 'nome'))
        self.s_commento = QLineEdit()
        self.s_commento.setPlaceholderText('es.  manca il punto dopo "qui"  /  dice "pennelo"  /  si sente in inglese')
        l.addWidget(self.s_commento)

        l.addSpacing(10)
        r = QHBoxLayout()
        r.addWidget(etichetta('Il tuo nome su Discord (facoltativo)', a_capo=False))
        self.s_autore = QLineEdit(percorsi.leggi_config().get('nome_discord', ''))
        self.s_autore.setMaxLength(40)
        r.addWidget(self.s_autore, 1)
        self.s_invia = bottone('Invia segnalazione', 'primario')
        self.s_invia.clicked.connect(self._segnala_invia)
        r.addWidget(self.s_invia)
        l.addLayout(r)
        lay.addWidget(f)
        lay.addStretch(1)
        return area

    def _segnala_cerca(self):
        self.s_lista.clear()
        testo = self.s_cerca.text()
        ris = segnala.cerca(testo, self.s_mappa.currentText(), massimo=3) if len(testo.split()) >= 2 else []
        for b in ris:
            it = QListWidgetItem('%s:  %s' % (b['chi'], b['it']))
            it.setData(Qt.UserRole, b)
            self.s_lista.addItem(it)
        self.s_forse.setVisible(bool(ris))
        self.s_lista.setVisible(bool(ris))

    def _segnala_testo(self):
        it = self.s_lista.currentItem() if self.s_lista.isVisible() else None
        b = it.data(Qt.UserRole) if it else None
        frase, commento = self.s_cerca.text().strip(), self.s_commento.text().strip()
        if not frase and not commento:
            self._messaggio('Manca qualcosa', 'Scrivi la frase sbagliata, oppure cosa non va.', 'avviso')
            return None
        autore = self.s_autore.text().strip()
        cfg = percorsi.leggi_config()
        if cfg.get('nome_discord', '') != autore:
            cfg['nome_discord'] = autore
            percorsi.salva_config(cfg)
        st = installa.leggi_stato()['componenti']
        mia = st.get('audio', {}).get('versione') or st.get('testo', {}).get('versione')
        return segnala.messaggio(self.s_tipo.currentText(), self.s_mappa.currentText(), frase, commento,
                                 b, autore, mia, VERSIONE)

    def _segnala_invia(self):
        msg = self._segnala_testo()
        if not msg:
            return
        self.s_invia.setEnabled(False)
        self.s_invia.setText('Invio in corso...')
        th = Invio(msg)
        self._invio = th

        def fatto():
            self.s_invia.setEnabled(True)
            self.s_invia.setText('Invia segnalazione')
            self.s_commento.clear()
            self.s_cerca.clear()
            self.statusBar().showMessage('Segnalazione inviata.')
            self._messaggio('Grazie!', 'Grazie mille per la segnalazione!\n\n'
                                       'E\' arrivata sul Discord della mod e verra\' controllata e corretta in un prossimo '
                                       'aggiornamento.\nCosi\' aiuti a migliorare la traduzione per tutti.')

        def errore(e):
            self.s_invia.setEnabled(True)
            self.s_invia.setText('Invia segnalazione')
            QGuiApplication.clipboard().setText(msg)
            if QMessageBox.question(self, 'Non inviata', e + '\n\nHo copiato la segnalazione: vuoi aprire il Discord '
                                    'e incollarla tu (Ctrl+V) nel canale delle segnalazioni?') == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(rete.DISCORD))
        th.fatto.connect(fatto)
        th.errore.connect(errore)
        th.start()

    # ======================= CONTRIBUISCI =======================
    def _contribuisci(self):
        area, lay = pagina('Contribuisci', 'Quando il gioco aggiunge battute nuove, puoi aiutare a doppiarle in italiano: '
                                         'gratis, con un tuo account ElevenLabs. Le voci saranno identiche a quelle della mod.')
        self.c_banner = QFrame()
        self.c_banner.setObjectName('banner')
        bl = QVBoxLayout(self.c_banner)
        bl.setContentsMargins(16, 12, 16, 12)
        self.c_stato_l = etichetta('')
        bl.addWidget(self.c_stato_l)
        self.c_barra_tot = QProgressBar()
        self.c_barra_tot.setFormat('%v di %m battute doppiate')
        bl.addWidget(self.c_barra_tot)
        lay.addWidget(self.c_banner)

        self.c_passi = QWidget()
        pl = QVBoxLayout(self.c_passi)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(14)
        f, l = scheda()
        l.addWidget(etichetta('1. Crea un account ElevenLabs (gratis)', 'nome'))
        l.addWidget(etichetta('Basta il piano gratuito: ogni mese da\' 10.000 crediti, circa 80-100 battute. '
                              'Un account a persona, per favore.', 'tenue'))
        r = QHBoxLayout()
        b = bottone('Crea l\'account')
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(contribuisci.LINK_ACCOUNT)))
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        pl.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('2. Crea la chiave API', 'nome'))
        l.addWidget(etichetta('Nella pagina delle chiavi premi "Create API key". Se ti chiede i permessi, lascia attivi '
                              '"Text to Speech" e "User" (lettura, per vedere i crediti). Poi copia la chiave.', 'tenue'))
        r = QHBoxLayout()
        b = bottone('Apri la pagina delle chiavi')
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(contribuisci.LINK_CHIAVE)))
        r.addWidget(b)
        self.c_video = bottone('Guarda il video')
        self.c_video.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.c_online.get('video_chiave', ''))))
        self.c_video.hide()
        r.addWidget(self.c_video)
        r.addStretch(1)
        l.addLayout(r)
        pl.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('3. Incolla la chiave', 'nome'))
        l.addWidget(etichetta('La chiave resta sul tuo PC e viene usata solo per parlare con ElevenLabs: '
                              'a noi arrivano soltanto gli audio.', 'tenue'))
        r = QHBoxLayout()
        self.c_chiave = QLineEdit(contribuisci.leggi_chiave())
        self.c_chiave.setEchoMode(QLineEdit.Password)
        self.c_chiave.setPlaceholderText('incolla qui la chiave (Ctrl+V)')
        r.addWidget(self.c_chiave, 1)
        b = bottone('Controlla')
        b.clicked.connect(self._c_controlla)
        r.addWidget(b)
        l.addLayout(r)
        self.c_ricorda = QCheckBox('Ricorda la chiave su questo PC (salvata cifrata da Windows)')
        self.c_ricorda.setStyleSheet('font-weight: normal; font-size: 10pt;')
        self.c_ricorda.setChecked(bool(self.c_chiave.text()))
        l.addWidget(self.c_ricorda)
        self.c_crediti = etichetta('', 'tenue')
        l.addWidget(self.c_crediti)
        pl.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('4. Doppia', 'nome'))
        r = QHBoxLayout()
        r.addWidget(etichetta('Il tuo nome nei ringraziamenti', a_capo=False))
        cfg = percorsi.leggi_config()
        self.c_nome = QLineEdit(cfg.get('nome_ringraziamenti') or cfg.get('nome_discord', ''))
        self.c_nome.setMaxLength(32)
        self.c_nome.setPlaceholderText('es. il tuo nick')
        r.addWidget(self.c_nome, 1)
        l.addLayout(r)
        l.addWidget(etichetta('Il programma prenota un gruppo di battute (cosi\' nessun altro fa le stesse), le genera '
                              'con i tuoi crediti e le manda una alla volta. Puoi fermarti quando vuoi.', 'tenue'))
        r = QHBoxLayout()
        self.c_via = bottone('Doppia le battute', 'primario')
        self.c_via.clicked.connect(self._c_doppia)
        r.addWidget(self.c_via)
        self.c_ferma = bottone('Ferma')
        self.c_ferma.clicked.connect(self._c_ferma)
        self.c_ferma.hide()
        r.addWidget(self.c_ferma)
        r.addStretch(1)
        l.addLayout(r)
        self.c_barra = QProgressBar()
        self.c_barra.hide()
        l.addWidget(self.c_barra)
        self.c_info = etichetta('', 'tenue')
        l.addWidget(self.c_info)
        pl.addWidget(f)
        lay.addWidget(self.c_passi)

        f, l = scheda()
        l.addWidget(etichetta('Grazie a chi ha doppiato', 'nome'))
        self.c_grazie = etichetta('', 'tenue')
        l.addWidget(self.c_grazie)
        lay.addWidget(f)
        lay.addStretch(1)
        return area

    def _aggiorna_contribuisci(self):
        doc, st = self.c_doc, self.c_stato
        lavora = bool(self.c_lavoro and self.c_lavoro.isRunning())
        if not self.controllato:
            self.c_stato_l.setText('Controllo se ci sono battute da doppiare...')
            self.c_barra_tot.hide()
        elif not doc:
            self.c_stato_l.setText('Al momento tutte le battute sono doppiate. Quando un aggiornamento del gioco '
                                   'aggiungera\' battute nuove, qui potrai aiutare a farle in italiano.')
            self.c_barra_tot.hide()
        else:
            tot = len(doc['battute'])
            fatte = (st or {}).get('fatte', 0)
            libere = (st or {}).get('libere', tot)
            self.c_stato_l.setText('Ci sono %d battute nuove da doppiare (versione %s): %s. '
                                   'Contribuisci gratuitamente per tutta la community!'
                                   % (tot, doc.get('versione', '?'), 'ne manca 1' if libere == 1 else
                                      ('ne mancano %d' % libere) if libere else 'sono tutte prenotate o fatte'))
            self.c_barra_tot.setMaximum(max(tot, 1))
            self.c_barra_tot.setValue(fatte)
            self.c_barra_tot.show()
        self.c_passi.setEnabled(bool(doc) or lavora)
        self.c_video.setVisible(bool(self.c_online.get('video_chiave')))
        cc = (self.manifest or {}).get('contributori') or []
        self.c_grazie.setText(', '.join('%s (%d)' % (c['nome'], c['battute']) for c in cc) if cc else
                              'Ancora nessuno: potresti essere il primo!')

    def _popup_contribuisci(self):
        d = (self.manifest or {}).get('da_doppiare')
        if not d or not self.c_doc:
            return
        cfg = percorsi.leggi_config()
        if cfg.get('popup_contribuisci') == d.get('tag'):
            return
        cfg['popup_contribuisci'] = d.get('tag')
        percorsi.salva_config(cfg)
        r = QMessageBox.question(self, 'Battute nuove da doppiare',
                                 'Il gioco ha %d battute nuove ancora senza voce italiana.\n\n'
                                 'Contribuisci gratuitamente per tutta la community! Ti serve solo un account '
                                 'ElevenLabs gratuito: il programma fa tutto il resto.\n\nVuoi vedere come?' % d.get('numero', 0))
        if r == QMessageBox.Yes:
            self._vai_a(6)

    def _c_controlla(self):
        k = self.c_chiave.text().strip()
        if not k:
            self._messaggio('Manca la chiave', 'Incolla prima la chiave di ElevenLabs.', 'avviso')
            return
        self.c_crediti.setText('Controllo...')
        th = Crediti(k)
        self._c_cr = th

        def fatto(c):
            if self.c_ricorda.isChecked():
                contribuisci.salva_chiave(k)
            else:
                contribuisci.dimentica_chiave()
            if c is None:
                self.c_crediti.setText('Chiave valida. (Non posso leggere i crediti: va bene lo stesso.)')
            else:
                self.c_crediti.setText('Chiave valida: hai %s crediti questo mese, circa %d battute.'
                                       % ('{:,}'.format(c).replace(',', '.'), max(0, c - contribuisci.MARGINE) // 110))
        th.fatto.connect(fatto)
        th.errore.connect(lambda e: self.c_crediti.setText(e))
        th.start()

    def _c_doppia(self):
        k = self.c_chiave.text().strip()
        if not k:
            self._messaggio('Manca la chiave', 'Incolla prima la chiave di ElevenLabs (passo 3).', 'avviso')
            return
        if not self.c_doc:
            return
        nome = self.c_nome.text().strip()
        cfg = percorsi.leggi_config()
        cfg['nome_ringraziamenti'] = nome
        percorsi.salva_config(cfg)
        if self.c_ricorda.isChecked():
            contribuisci.salva_chiave(k)
        th = Doppiaggio(k, self.c_doc, nome or 'Anonimo')
        self.c_lavoro = th
        self.c_via.setEnabled(False)
        self.c_ferma.show()
        self.c_barra.setValue(0)
        self.c_barra.show()
        self.c_info.setText('Prenoto le battute...')

        def av(a, b, t):
            self.c_barra.setMaximum(max(b, 1))
            self.c_barra.setValue(a)
            self.c_info.setText('%d di %d  -  %s' % (min(a + 1, b), b, t) if a < b else 'Fatto.')

        def fine(n, motivo):
            self.c_via.setEnabled(True)
            self.c_ferma.hide()
            self.c_info.setText(('Hai doppiato %d battute. ' % n if n else '') + (motivo or ''))
            self._controlla_online()
            if n:
                self._messaggio('Grazie!', 'Grazie mille! Hai doppiato %d battute per tutta la community.\n\n'
                                           'Le ascoltiamo e le mettiamo nel prossimo aggiornamento, con il tuo nome '
                                           'nei ringraziamenti.%s' % (n, ('\n\n' + motivo) if motivo else ''))
            elif motivo:
                self._messaggio('Contribuisci', motivo)

        def err(e):
            self.c_via.setEnabled(True)
            self.c_ferma.hide()
            self.c_info.setText(e)
            self._messaggio('Qualcosa e\' andato storto', e + '\n\nLe battute gia\' fatte sono arrivate: non si perde niente.',
                            'avviso')
        th.avanzamento.connect(av)
        th.finito.connect(fine)
        th.errore.connect(err)
        th.start()

    def _c_ferma(self):
        if self.c_lavoro:
            self.c_lavoro.stop = True
            self.c_info.setText('Mi fermo dopo la battuta in corso...')

    # ======================= IMPOSTAZIONI =======================
    def _impostazioni(self):
        area, lay = pagina('Impostazioni', 'Dove si trovano il gioco e i salvataggi.')
        self.imp = {}
        for chiave, nome, desc in [('gioco', 'Cartella del gioco', 'Quella che contiene theHunterCotW_F.exe.'),
                                   ('dropzone', 'Cartella delle mod (dropzone)', 'Qui il programma mette i suoi file.'),
                                   ('salvataggi', 'Salvataggi', 'Documenti\\Avalanche Studios\\COTW\\Saves\\<numero>'),
                                   ('dati', 'Dati del programma', 'Impostazioni, backup dei salvataggi e dei file di altre mod.')]:
            f, l = scheda()
            l.addWidget(etichetta(nome, 'nome'))
            l.addWidget(etichetta(desc, 'tenue'))
            r = QHBoxLayout()
            e = QLineEdit()
            e.setReadOnly(True)
            r.addWidget(e, 1)
            if chiave == 'gioco':
                b = bottone('Cambia...')
                b.clicked.connect(self._scegli_gioco)
                r.addWidget(b)
                b = bottone('Trova da solo')
                b.clicked.connect(self._trova_gioco_auto)
                r.addWidget(b)
            elif chiave == 'salvataggi':
                b = bottone('Cambia...')
                b.clicked.connect(self._scegli_salvataggi)
                r.addWidget(b)
            b = bottone('Apri')
            b.clicked.connect(lambda _=False, e=e: apri_cartella(e.text()))
            r.addWidget(b)
            l.addLayout(r)
            self.imp[chiave] = e
            lay.addWidget(f)
        f, l = scheda()
        l.addWidget(etichetta('Programma', 'nome'))
        self.imp_prog = etichetta('', 'tenue')
        l.addWidget(self.imp_prog)
        r = QHBoxLayout()
        self.imp_prog_b = bottone('Aggiorna programma', 'primario')
        self.imp_prog_b.clicked.connect(self._aggiorna_programma)
        r.addWidget(self.imp_prog_b)
        b = bottone('Controlla')
        b.clicked.connect(lambda: self._controlla_online(mostra=True))
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)

        f, l = scheda()
        l.addWidget(etichetta('Sostieni il progetto', 'nome'))
        l.addWidget(etichetta('La mod e il programma sono gratis e lo resteranno. Le voci italiane costano: se vuoi dare '
                              'una mano per le mappe nuove, puoi lasciare una donazione libera su Ko-fi.', 'tenue'))
        r = QHBoxLayout()
        b = bottone('\u2665  Dona su Ko-fi', 'primario')
        b.clicked.connect(self._dona)
        r.addWidget(b)
        r.addStretch(1)
        l.addLayout(r)
        lay.addWidget(f)
        lay.addWidget(etichetta('CotW Italiano %s  -  di Mirko Del Sette. Voci create con ElevenLabs.\n'
                                'Programma: licenza GPL-3.0 (codice su github.com/%s).  Traduzione e doppiaggio: '
                                'CC BY-NC-ND 4.0 (gratis, citando l\'autore; vietato venderli o ripubblicarli modificati).\n'
                                'Progetto amatoriale non ufficiale: theHunter: Call of the Wild e\' di Expansive Worlds / '
                                'Avalanche Studios Group.' % (VERSIONE, rete.REPO), 'tenue'))
        lay.addStretch(1)
        return area

    def _dona(self):
        QDesktopServices.openUrl(QUrl(rete.KOFI))

    def _aggiorna_impostazioni_programma(self):
        nuova = programma.disponibile(self.c_online)
        if nuova:
            self.imp_prog.setText('Hai la versione %s. E\' uscita la %s.' % (VERSIONE, nuova['versione']))
        else:
            self.imp_prog.setText('Hai la versione %s%s.' % (VERSIONE, ': e\' la piu\' recente' if self.controllato else ''))
        self.imp_prog_b.setVisible(bool(nuova))

    def _popup_programma(self):
        nuova = programma.disponibile(self.c_online)
        if not nuova or not programma.cartella_exe():
            return False
        cfg = percorsi.leggi_config()
        if cfg.get('popup_programma') == nuova['versione']:
            return False
        cfg['popup_programma'] = nuova['versione']
        percorsi.salva_config(cfg)
        if QMessageBox.question(self, 'Programma da aggiornare',
                                'E\' uscita la versione %s di CotW Italiano (tu hai la %s).%s\n\nAggiorno adesso? '
                                'Ci vuole un minuto: il programma si chiude e si riapre da solo.'
                                % (nuova['versione'], VERSIONE, ('\n\nNovita\': ' + '; '.join(nuova['novita']))
                                   if nuova.get('novita') else '')) == QMessageBox.Yes:
            self._aggiorna_programma()
        return True

    def _aggiorna_programma(self):
        nuova = programma.disponibile(self.c_online)
        if not nuova:
            return
        if not programma.cartella_exe():
            self._messaggio('Aggiorna programma', 'Stai usando il programma avviato con Python (AVVIA_COTW_ITALIANO.bat): '
                                                  'scarica la versione nuova da GitHub.', 'avviso')
            QDesktopServices.openUrl(QUrl(rete.PAGINA + '/releases'))
            return
        if self.lavoro and self.lavoro.isRunning():
            self._messaggio('Attendi', 'C\'e\' gia\' un\'operazione in corso.', 'avviso')
            return
        self._vai_a(0)
        self.statusBar().showMessage('Scarico la versione %s del programma...' % nuova['versione'])
        self.lavoro = Lavoro(lambda av: programma.prepara(nuova, av))

        def fine(cartella):
            try:
                programma.installa_e_riavvia(cartella)
            except Exception as e:
                self._messaggio('Aggiornamento non riuscito', str(e), 'errore')
                return
            QApplication.instance().quit()

        def err(e):
            self.statusBar().showMessage('Errore: ' + e)
            self._messaggio('Aggiornamento non riuscito', e + '\n\nRiprova piu\' tardi: il programma funziona come prima.',
                            'errore')
        self.lavoro.avanzamento.connect(lambda a, b, t: self.statusBar().showMessage('%s: %d di %d' % (t, a, b)))
        self.lavoro.finito.connect(fine)
        self.lavoro.errore.connect(err)
        self.lavoro.start()

    def _aggiorna_impostazioni(self):
        self.imp['gioco'].setText(self.gioco or 'Non trovato')
        self.imp['dropzone'].setText(self.dz() or '')
        prof = percorsi.profili_salvataggi()
        self.imp['salvataggi'].setText(prof[0] if prof else 'Non trovati')
        self.imp['dati'].setText(percorsi.dati_app())

    def _scegli_gioco(self):
        p = QFileDialog.getExistingDirectory(self, 'Cartella del gioco (con theHunterCotW_F.exe)', self.gioco or '')
        if not p:
            return
        p = os.path.normpath(p)
        if not percorsi.e_cartella_gioco(p):
            self._messaggio('Cartella sbagliata', 'In questa cartella non c\'e\' theHunterCotW_F.exe.', 'avviso')
            return
        cfg = percorsi.leggi_config()
        cfg['cartella_gioco'] = p
        percorsi.salva_config(cfg)
        self.gioco = p
        self.aggiorna_tutto()

    def _trova_gioco_auto(self):
        cfg = percorsi.leggi_config()
        cfg.pop('cartella_gioco', None)
        percorsi.salva_config(cfg)
        self.gioco = percorsi.trova_gioco()
        if not self.gioco:
            self._messaggio('Non trovato', 'Non trovo il gioco da solo: usa "Cambia...".', 'avviso')
        self.aggiorna_tutto()

    def _scegli_salvataggi(self):
        p = QFileDialog.getExistingDirectory(self, 'Cartella dei salvataggi (Saves)', '')
        if p:
            cfg = percorsi.leggi_config()
            cfg['cartella_salvataggi'] = os.path.normpath(p)
            percorsi.salva_config(cfg)
            self.aggiorna_tutto()

    # ---------------- aggiornamento generale ----------------
    def aggiorna_tutto(self):
        try:
            if self.gioco and self.sorgente:
                installa.riconosci_esistenti(self.sorgente, self.dz())
            self._aggiorna_home()
            self._aggiorna_installa()
            self._aggiorna_strumenti()
            self._aggiorna_salvataggi()
            self._aggiorna_impostazioni()
            self._aggiorna_impostazioni_programma()
            self._aggiorna_contribuisci()
            self._controlla_gioco()
        except Exception:
            traceback.print_exc()
