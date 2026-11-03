"""Tutorial a popup: al primo avvio un giro di tutte le funzioni; dopo un aggiornamento solo le novita'.
Oscura la finestra, illumina il pezzo di cui parla e mostra un fumetto con Indietro / Avanti / Salta.
Per aggiungere una novita' in una versione futura: un passo in piu' in PASSI con 'dal': '<versione>'."""
from PySide6.QtCore import Qt, QRect, QRectF, QEvent, QTimer
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea

# pagina: indice della scheda (0 Home ... 7 Impostazioni) | bersaglio: nome dell'attributo della finestra (o None)
PASSI = [
    dict(dal='0.5.2', pagina=0, bersaglio=None, titolo='Benvenuto in CotW Italiano!',
         testo='Ti faccio vedere in un minuto dove sta tutto.\nPremi Avanti (o Salta se sai gia\' tutto).'),
    dict(dal='0.5.2', pagina=0, bersaglio='menu:0', titolo='Home',
         testo='Lo stato della traduzione sul tuo PC. Qui c\'e\' anche il tasto per disattivare le mod prima di '
               'giocare online.'),
    dict(dal='0.5.2', pagina=1, bersaglio='i_scarica', titolo='1. Installa la traduzione',
         testo='Il primo passo: "Scarica e installa" mette testo e voci italiane nel gioco.\nQuando esce un '
               'aggiornamento scarica solo i file cambiati.'),
    dict(dal='0.5.2', pagina=2, bersaglio='a_ctrl_on', titolo='2. Avvio del gioco',
         testo='Attiva il "Controllo prima di giocare": quando premi Gioca su Steam controlla gli aggiornamenti e poi '
               'fa partire il gioco con le mod. Cosi\' non devi piu\' aprire il programma.'),
    dict(dal='0.5.2', pagina=3, bersaglio='menu:3', titolo='Salvataggi',
         testo='Backup dei salvataggi e "Azzera missioni" per rigiocare la storia in italiano.'),
    dict(dal='0.5.2', pagina=4, bersaglio='menu:4', titolo='Strumenti',
         testo='Il volume del quad (solo quello che senti tu, non gli animali).'),
    dict(dal='0.5.2', pagina=5, bersaglio='s_tipo', titolo='Hai trovato un errore?',
         testo='Scegli Audio, Testo o Entrambi, scrivi la frase (se ti viene suggerita cliccala) e spiega '
               'brevemente cosa non va. Arriva da sola sul Discord: piu\' ne mandi, meglio e\'!'),
    dict(dal='0.5.2', pagina=6, bersaglio='c_banner', titolo='Contribuisci',
         testo='Quando il gioco aggiunge battute nuove (o ne correggiamo qualcuna) puoi doppiarle tu, gratis, con un '
               'account ElevenLabs. Il programma fa tutto il resto e il tuo nome finisce nei ringraziamenti.'),
    dict(dal='0.5.2', pagina=7, bersaglio='menu:7', titolo='Impostazioni',
         testo='Le cartelle del gioco e dei salvataggi, gli aggiornamenti del programma e il tasto per rivedere '
               'questo tutorial.'),
    dict(dal='0.5.2', pagina=None, bersaglio='b_discord', titolo='Community',
         testo='Aiuto, novita\' e segnalazioni sul Discord. E se ti piace la mod, puoi sostenerla qui sotto.'),
    dict(dal='0.0.0', pagina=0, bersaglio=None, titolo='Tutto pronto!',
         testo='Buona caccia in italiano!\nIl tutorial lo rivedi quando vuoi da Impostazioni.'),
]


def _num(v):
    try:
        return tuple(int(x) for x in str(v).split('.'))
    except ValueError:
        return (0,)


def passi_da_mostrare(visto):
    """Mai visto: tutto. Visto con una versione vecchia: solo le novita' (+ saluto finale). Altrimenti niente."""
    if not visto:
        return list(PASSI)
    nuovi = [p for p in PASSI if _num(p['dal']) > _num(visto)]
    if not nuovi:
        return []
    inizio = dict(PASSI[0], titolo='Novita\' di questa versione', testo='Ti mostro cosa c\'e\' di nuovo. Premi Avanti.')
    return [inizio] + nuovi + [PASSI[-1]]


class Tutorial(QWidget):
    def __init__(self, finestra, passi, alla_fine):
        super().__init__(finestra)
        self.f, self.passi, self.alla_fine, self.i = finestra, passi, alla_fine, 0
        self.buco = QRect()
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.fumetto = QFrame(self)
        self.fumetto.setObjectName('fumetto')
        self.fumetto.setStyleSheet('#fumetto { background: #1f2a22; border: 2px solid #5fa86b; border-radius: 10px; } '
                                   'QLabel { background: transparent; }')
        self.fumetto.setFixedWidth(380)
        lay = QVBoxLayout(self.fumetto)
        lay.setContentsMargins(18, 14, 18, 14)
        self.l_titolo = QLabel()
        self.l_titolo.setStyleSheet('font-size: 13pt; font-weight: bold; color: white;')
        self.l_testo = QLabel()
        self.l_testo.setWordWrap(True)
        self.l_testo.setStyleSheet('font-size: 10.5pt; color: #e3e6e8;')
        self.l_conta = QLabel()
        self.l_conta.setStyleSheet('font-size: 9pt; color: #9aa3a8;')
        lay.addWidget(self.l_titolo)
        lay.addWidget(self.l_testo)
        r = QHBoxLayout()
        r.addWidget(self.l_conta)
        r.addStretch(1)
        self.b_salta = QPushButton('Salta')
        self.b_indietro = QPushButton('Indietro')
        self.b_avanti = QPushButton('Avanti')
        self.b_avanti.setObjectName('primario')
        for b in (self.b_salta, self.b_indietro, self.b_avanti):
            b.setCursor(Qt.PointingHandCursor)
            r.addWidget(b)
        self.b_salta.clicked.connect(self.fine)
        self.b_indietro.clicked.connect(lambda: self.vai(self.i - 1))
        self.b_avanti.clicked.connect(lambda: self.vai(self.i + 1))
        lay.addLayout(r)
        finestra.installEventFilter(self)
        self.setGeometry(finestra.rect())
        self.show()
        self.raise_()
        self.vai(0)

    # la finestra cambia dimensione: si ridisegna
    def eventFilter(self, o, e):
        if o is self.f and e.type() in (QEvent.Resize, QEvent.Move):
            self.setGeometry(self.f.rect())
            QTimer.singleShot(0, self._posiziona)
        return False

    def _bersaglio(self, nome):
        if not nome:
            return None
        if nome.startswith('menu:'):
            return self.f.gruppo.button(int(nome[5:]))
        return getattr(self.f, nome, None)

    def vai(self, i):
        if i >= len(self.passi):
            return self.fine()
        self.i = max(0, i)
        p = self.passi[self.i]
        if p.get('pagina') is not None:
            self.f._vai_a(p['pagina'])
        self.l_titolo.setText(p['titolo'])
        self.l_testo.setText(p['testo'])
        self.l_conta.setText('%d di %d' % (self.i + 1, len(self.passi)))
        self.b_indietro.setVisible(self.i > 0)
        ultimo = self.i == len(self.passi) - 1
        self.b_avanti.setText('Fine' if ultimo else 'Avanti')
        self.b_salta.setVisible(not ultimo)
        w = self._bersaglio(p.get('bersaglio'))
        if w is not None:                     # se sta in una pagina che scorre, la porta in vista
            a = w.parent()
            while a is not None and not isinstance(a, QScrollArea):
                a = a.parent()
            if a is not None:
                a.ensureWidgetVisible(w, 40, 60)
        QTimer.singleShot(30, self._posiziona)
        self.b_avanti.setFocus()

    def _posiziona(self):
        p = self.passi[self.i]
        w = self._bersaglio(p.get('bersaglio'))
        self.fumetto.adjustSize()
        fw, fh = self.fumetto.width(), self.fumetto.sizeHint().height()
        if w is not None and w.isVisible():
            tl = w.mapTo(self.f, w.rect().topLeft())
            self.buco = QRect(tl, w.size()).adjusted(-8, -8, 8, 8)
            b = self.buco
            if b.right() + 20 + fw < self.width():               # a destra
                x, y = b.right() + 20, b.top()
            elif b.left() - 20 - fw > 0:                         # a sinistra
                x, y = b.left() - 20 - fw, b.top()
            elif b.bottom() + 20 + fh < self.height():           # sotto
                x, y = b.left(), b.bottom() + 20
            else:                                                # sopra
                x, y = b.left(), b.top() - 20 - fh
        else:
            self.buco = QRect()
            x, y = (self.width() - fw) // 2, (self.height() - fh) // 2
        x = max(12, min(x, self.width() - fw - 12))
        y = max(12, min(y, self.height() - fh - 12))
        self.fumetto.move(x, y)
        self.fumetto.raise_()
        self.update()

    def paintEvent(self, _e):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.Antialiasing)
        tutto = QPainterPath()
        tutto.addRect(QRectF(self.rect()))
        if not self.buco.isNull():
            buco = QPainterPath()
            buco.addRoundedRect(QRectF(self.buco), 10, 10)
            tutto = tutto.subtracted(buco)
        pt.fillPath(tutto, QColor(0, 0, 0, 165))
        if not self.buco.isNull():
            pt.setPen(QPen(QColor('#5fa86b'), 3))
            pt.drawRoundedRect(QRectF(self.buco), 10, 10)

    def mousePressEvent(self, e):          # i clic fuori dal fumetto non arrivano alla finestra sotto
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.fine()
        elif e.key() in (Qt.Key_Right, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.vai(self.i + 1)
        elif e.key() == Qt.Key_Left:
            self.vai(self.i - 1)

    def fine(self):
        self.f.removeEventFilter(self)
        self.hide()
        self.deleteLater()
        if self.alla_fine:
            self.alla_fine()
