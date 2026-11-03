"""Compagno di gioco (CotW Italiano.exe --compagno): parte da solo quando parte il gioco, senza finestre.
- appena il gioco e' aperto mostra per qualche secondo l'avviso "Premi Ctrl+Alt+S per segnalare...";
- la scorciatoia apre la finestrella Segnala errore sopra il gioco; Invia (o Esc) e si torna a giocare;
- a gioco chiuso si chiude da solo. La scorciatoia si cambia in Impostazioni (vale subito)."""
import os
import time
from PySide6.QtCore import Qt, QObject, QTimer, Signal, QLockFile
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
                               QListWidget, QListWidgetItem)

from ..core import percorsi, scorciatoia, segnala, installa
from .. import VERSIONE
from .finestra import etichetta, bottone, Invio

ATTESA_GIOCO = 180         # secondi: se il gioco non parte entro questo tempo, il compagno se ne va
OGNI = 5000                # ms tra un controllo e l'altro
AVVISO_DOPO = 8000         # ms dopo che il gioco e' partito
AVVISO_PER = 9000          # ms che l'avviso resta sullo schermo


class Avviso(QWidget):
    """Fumetto in alto al centro, sopra il gioco, che non prende il primo piano (il gioco non si ferma)."""

    def __init__(self, testo):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        lay = QVBoxLayout(self)
        l = QLabel(testo)
        l.setStyleSheet('background: rgba(20, 28, 22, 225); color: #e8f5ea; border: 2px solid #5fa86b; '
                        'border-radius: 10px; padding: 12px 20px; font-size: 15px; font-weight: 600;')
        lay.addWidget(l)
        self.adjustSize()
        sc = QApplication.primaryScreen().geometry()
        self.move(sc.x() + (sc.width() - self.width()) // 2, sc.y() + 40)


class SegnalaRapida(QDialog):
    """Gli stessi campi della pagina Segnala errore, in piccolo e sempre in primo piano."""

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle('CotW Italiano - Segnala errore')
        self.setMinimumWidth(560)
        self.scelta, self.th = None, None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)
        lay.addWidget(etichetta('Segnala un errore della traduzione', 'titolo'))
        lay.addWidget(etichetta('Compila e premi Invia: torni subito al gioco. Esc per chiudere.', 'tenue'))
        lay.addWidget(etichetta('1. Mappa', 'nome'))
        self.mappa = QComboBox()
        self.mappa.addItems(segnala.MAPPE)
        cfg = percorsi.leggi_config()
        i = self.mappa.findText(cfg.get('ultima_mappa_segnala', ''))
        if i >= 0:
            self.mappa.setCurrentIndex(i)
        self.mappa.currentIndexChanged.connect(lambda _=0: self._cerca())
        lay.addWidget(self.mappa)
        lay.addWidget(etichetta('2. Cosa e\' sbagliato?', 'nome'))
        self.tipo = QComboBox()
        self.tipo.addItems(segnala.TIPI)
        lay.addWidget(self.tipo)
        lay.addWidget(etichetta('3. Scrivi la frase o la parola sbagliata', 'nome'))
        self.frase = QLineEdit()
        self.frase.setPlaceholderText('es.  Ecco qui mano ferma adesso')
        self.frase.textChanged.connect(lambda _='': self._cerca())
        lay.addWidget(self.frase)
        self.lista = QListWidget()
        self.lista.setFixedHeight(72)
        self.lista.itemClicked.connect(self._scegli)
        self.lista.hide()
        lay.addWidget(self.lista)
        lay.addWidget(etichetta('4. Spiega brevemente cosa non va', 'nome'))
        self.commento = QLineEdit()
        self.commento.setPlaceholderText('es.  dice "pennelo"  /  si sente in inglese  /  scritta tagliata')
        self.commento.returnPressed.connect(self._invia)
        lay.addWidget(self.commento)
        r = QHBoxLayout()
        r.addWidget(etichetta('Il tuo nome (facoltativo, finisce nei ringraziamenti)', a_capo=False))
        self.autore = QLineEdit(cfg.get('nome_discord', ''))
        self.autore.setMaxLength(40)
        r.addWidget(self.autore, 1)
        lay.addLayout(r)
        self.esito = etichetta('', 'tenue')
        lay.addWidget(self.esito)
        r = QHBoxLayout()
        r.addStretch(1)
        b = bottone('Chiudi')
        b.clicked.connect(self.reject)
        r.addWidget(b)
        self.b_invia = bottone('Invia segnalazione', 'primario')
        self.b_invia.clicked.connect(self._invia)
        r.addWidget(self.b_invia)
        lay.addLayout(r)

    def _cerca(self):
        self.scelta = None
        self.lista.clear()
        t = self.frase.text()
        ris = segnala.cerca(t, self.mappa.currentText(), massimo=3) if len(t.split()) >= 2 else []
        for b in ris:
            it = QListWidgetItem('%s:  %s' % (b['chi'], b['it']))
            it.setData(Qt.UserRole, b)
            self.lista.addItem(it)
        self.lista.setVisible(bool(ris))

    def _scegli(self, it):
        b = it.data(Qt.UserRole)
        self.frase.blockSignals(True)
        self.frase.setText(b.get('it', ''))
        self.frase.blockSignals(False)
        self.lista.clear()
        x = QListWidgetItem('✔  %s:  %s' % (b.get('chi', '?'), b.get('it', '')))
        self.lista.addItem(x)
        self.scelta = b
        self.commento.setFocus()

    def _invia(self):
        if self.th and self.th.isRunning():
            return
        frase, commento = self.frase.text().strip(), self.commento.text().strip()
        if len(commento) < 3:
            self.esito.setText('Al punto 4 spiega brevemente cosa non va.')
            self.commento.setFocus()
            return
        autore = self.autore.text().strip()
        cfg = percorsi.leggi_config()
        cfg['nome_discord'] = autore
        cfg['ultima_mappa_segnala'] = self.mappa.currentText()
        percorsi.salva_config(cfg)
        try:
            st = installa.leggi_stato()['componenti']
            mia = st.get('audio', {}).get('versione') or st.get('testo', {}).get('versione')
        except Exception:
            mia = None
        b = self.scelta
        msg = segnala.messaggio(self.tipo.currentText(), self.mappa.currentText(), frase, commento, b, autore, mia,
                                VERSIONE)
        info = {'tipo': self.tipo.currentText(), 'mappa': self.mappa.currentText(), 'frase': frase,
                'commento': commento, 'battuta': (b or {}).get('id')}
        self.b_invia.setEnabled(False)
        self.esito.setText('Invio in corso...')
        self.th = Invio(msg, info)
        self.th.fatto.connect(self._fatto)
        self.th.errore.connect(self._errore)
        self.th.start()

    def _fatto(self, esito):
        self.esito.setText('✔ Grazie! Segnalazione inviata.' if esito == 'inviata' else
                           '✔ Grazie! La mando da sola tra poco (ora il servizio non risponde).')
        QTimer.singleShot(1500, self.accept)

    def _errore(self, e):
        self.b_invia.setEnabled(True)
        self.esito.setText('Non inviata: %s' % e)


class Compagno(QObject):
    premuto = Signal()

    def __init__(self):
        super().__init__()
        self.inizio = time.time()
        self.visto, self.chiuso_volte = False, 0
        self.finestra, self.gioco_hwnd, self.avviso = None, None, None
        self.tasto, self.tasti = None, None
        self.premuto.connect(self._apri)
        self._registra()
        self.t = QTimer(self)
        self.t.timeout.connect(self._controlla)
        self.t.start(OGNI)
        QTimer.singleShot(1000, self._controlla)

    def _registra(self):
        """(Ri)prende la scorciatoia se l'utente l'ha cambiata o spenta in Impostazioni."""
        nuovi = scorciatoia.tasti() if scorciatoia.attiva() else None
        if nuovi == self.tasti:
            return
        if self.tasto:
            self.tasto.ferma()
            self.tasto = None
        self.tasti = nuovi
        if nuovi:
            self.tasto = scorciatoia.Tasto(nuovi, self.premuto.emit)
            if not self.tasto.avvia():
                self.tasto = None

    def _avviso(self):
        if not self.tasto or not percorsi.gioco_in_esecuzione():
            return
        self.avviso = Avviso('Premi %s per segnalare errori della traduzione durante il gioco' % self.tasti)
        self.avviso.show()
        QTimer.singleShot(AVVISO_PER, self.avviso.close)

    def _apri(self):
        if self.finestra and self.finestra.isVisible():
            scorciatoia.porta_davanti(int(self.finestra.winId()))
            return
        self.gioco_hwnd = scorciatoia.primo_piano_attuale()
        self.finestra = SegnalaRapida()
        self.finestra.finished.connect(self._chiusa)
        self.finestra.show()
        self.finestra.raise_()
        self.finestra.activateWindow()
        scorciatoia.porta_davanti(int(self.finestra.winId()))
        self.finestra.frase.setFocus()

    def _chiusa(self, _r=0):
        scorciatoia.porta_davanti(self.gioco_hwnd)          # si torna al gioco

    def _controlla(self):
        self._registra()
        if percorsi.gioco_in_esecuzione():
            if not self.visto:
                self.visto = True
                QTimer.singleShot(AVVISO_DOPO, self._avviso)
            self.chiuso_volte = 0
            return
        if not self.visto:
            if time.time() - self.inizio > ATTESA_GIOCO:
                self._esci()
            return
        self.chiuso_volte += 1
        if self.chiuso_volte >= 2 and not (self.finestra and self.finestra.isVisible()):
            self._esci()                                     # gioco chiuso davvero

    def _esci(self):
        self.t.stop()
        if self.tasto:
            self.tasto.ferma()
        QApplication.quit()


def esegui(app):
    if not scorciatoia.attiva():
        return 0
    lock = QLockFile(os.path.join(percorsi.dati_app(), 'compagno.lock'))
    if not lock.tryLock(200):                         # c'e' gia' un compagno acceso
        return 0
    app.setQuitOnLastWindowClosed(False)
    c = Compagno()  # noqa: F841
    r = app.exec()
    lock.unlock()
    return r
