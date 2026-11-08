"""Finestra dell'aggiornamento del programma: barra con i MB scaricati, poi l'installer (con la sua barra) e il
programma si riapre da solo. Cosi' non sembra mai bloccato."""
import os
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QApplication, QMessageBox
from ..core import programma
from .. import VERSIONE


class _Scarica(QThread):
    avanzamento = Signal(int, int)
    fatto = Signal(str, str)

    def __init__(self, info):
        super().__init__()
        self.info = info

    def run(self):
        try:
            p = programma.prepara(self.info, lambda a, b, _t: self.avanzamento.emit(a, b))
            self.fatto.emit(p, '')
        except Exception as e:
            self.fatto.emit('', str(e))


class Aggiornamento(QDialog):
    """aggiorna(parent, info, argomenti): True se e' partito (il programma si sta chiudendo)."""

    def __init__(self, padre, info, argomenti=None):
        super().__init__(padre)
        self.info, self.argomenti, self.ok = info, argomenti or [], False
        self.setWindowTitle('Aggiornamento di CotW Italiano')
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        t = QLabel('Aggiorno CotW Italiano dalla versione %s alla %s%s' % (
            VERSIONE, info['versione'], ' (versione di prova)' if info.get('anteprima') else ''))
        t.setStyleSheet('font-size: 12pt; font-weight: bold;')
        lay.addWidget(t)
        self.testo = QLabel('Scarico la versione nuova...')
        self.testo.setWordWrap(True)
        lay.addWidget(self.testo)
        self.barra = QProgressBar()
        self.barra.setMaximum(0)
        self.barra.setFormat('%v di %m MB')
        lay.addWidget(self.barra)
        nota = QLabel('Non chiudere: alla fine il programma si chiude, si installa la versione nuova e si riapre da solo.')
        nota.setWordWrap(True)
        nota.setStyleSheet('color: #9aa3a8; font-size: 9pt;')
        lay.addWidget(nota)
        self.th = _Scarica(info)
        self.th.avanzamento.connect(self._av)
        self.th.fatto.connect(self._fatto)
        QTimer.singleShot(100, self.th.start)

    def _av(self, a, b):
        self.barra.setMaximum(max(b, 1))
        self.barra.setValue(min(a, b))

    def _non_riuscito(self, err):
        """Ultima spiaggia: oltre a 'riprova', c'e' sempre il link per scaricare a mano dal sito ufficiale."""
        programma.segna_fallito(err)
        m = QMessageBox(QMessageBox.Warning, 'Aggiornamento non riuscito',
                        err + '\n\nIl programma funziona come prima: puoi riprovare piu\' tardi, oppure scaricare a mano '
                        'l\'ultima versione dal sito ufficiale e installarla sopra questa (impostazioni e traduzione '
                        'restano).', parent=self)
        b = m.addButton('Scarica a mano', QMessageBox.AcceptRole)
        m.addButton('Riprova piu\' tardi', QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() is b:
            QDesktopServices.openUrl(QUrl(programma.SITO_SCARICA))
        self.reject()

    def _fatto(self, percorso, err):
        if err:
            return self._non_riuscito(err)
        self.barra.setMaximum(0)
        if percorso.lower().endswith('.exe') and not programma.installato():
            self.testo.setText('Fatto. Ora si apre l\'installazione: scegli dove metterlo (va bene quella proposta), '
                               'lascia la spunta dell\'icona sul desktop e premi Avanti fino alla fine. Il programma si '
                               'riapre da solo.')
        else:
            self.testo.setText('Fatto. Ora il programma si chiude, si installa la versione nuova (con la sua barra) e '
                               'CotW Italiano si riapre da solo...')
        self.adjustSize()
        try:
            programma.segna_tentativo(self.info)
            programma.installa_e_riavvia(percorso, self.argomenti)
        except Exception as e:
            return self._non_riuscito(str(e))
        self.ok = True
        QTimer.singleShot(3000, _chiudi_programma)

    def keyPressEvent(self, e):          # Esc non lo chiude a meta'
        if e.key() != Qt.Key_Escape:
            super().keyPressEvent(e)


def _chiudi_programma():
    """Chiude DAVVERO il programma, anche dal controllo prima di giocare (li' non c'e' app.exec() e quit() da solo
    non fa niente: lo script dell'aggiornamento aspettava per sempre). Se qualcosa resta aperto, si esce lo stesso."""
    app = QApplication.instance()
    for w in app.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible():
            w.done(0)
    app.closeAllWindows()
    app.quit()
    QTimer.singleShot(2000, lambda: os._exit(0))


def aggiorna(padre, info, argomenti=None):
    d = Aggiornamento(padre, info, argomenti)
    d.exec()
    return d.ok
