"""Avvio di CotW Italiano."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from cotw.ui.finestra import Finestra
from cotw.ui import stile


def disinstalla():
    from cotw.core import avvio
    from PySide6.QtWidgets import QMessageBox
    try:
        if not avvio.controllo_attivo(avvio.stato_steam()[1]):
            return 0
        _app = QApplication(sys.argv)  # noqa: F841 (serve per il messaggio)
        avvio.imposta_steam(togli_controllo=True)
    except Exception as e:
        if 'Steam e\' aperto' in str(e):
            QMessageBox.information(None, 'CotW Italiano', 'Steam e\' aperto, quindi non posso togliere il controllo '
                                    'prima di giocare dalle opzioni di avvio.\n\nIn Steam: tasto destro sul gioco -> '
                                    'Proprieta\' -> Opzioni di avvio, e cancella la parte  "...CotW Italiano.exe" --gioco')
    return 0


def main():
    if '--prova' in sys.argv:                  # prova automatica (GitHub, prima di pubblicare): niente finestre
        from cotw import prova
        sys.exit(prova.esegui(sys.argv))
    # avviato senza console (pythonw): gli errori finiscono in un file, cosi' si possono mandare a Claude
    if sys.stderr is None or sys.stdout is None:
        from cotw.core import percorsi
        import os
        log = open(os.path.join(percorsi.dati_app(), 'errori.log'), 'a', encoding='utf-8', buffering=1)
        sys.stderr = sys.stdout = log
    if '--disinstalla' in sys.argv:            # dall'installer: toglie il controllo prima di giocare da Steam
        sys.exit(disinstalla())
    try:                                       # un aggiornamento era partito? e' andato o no (ultima spiaggia)
        from cotw.core import programma
        programma.controlla_esito()
    except Exception:
        pass
    app = QApplication(sys.argv)
    if '--compagno' in sys.argv:               # mentre giochi: scorciatoia che apre Segnala errore sopra il gioco
        app.setApplicationName('CotW Italiano')
        app.setStyle('Fusion')
        app.setStyleSheet(stile.QSS)
        from cotw.ui import compagno
        from cotw.core import programma
        programma.segna_ok()
        sys.exit(compagno.esegui(app))
    if '--gioco' in sys.argv:                 # premuto Gioca (Steam o collegamento): controllo veloce e via
        app.setApplicationName('CotW Italiano')
        app.setStyle('Fusion')
        app.setStyleSheet(stile.QSS)
        from cotw.ui import prima_di_giocare
        from cotw.core import programma
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, programma.segna_ok)   # "sono ok" per l'avvio (ritorno indietro automatico)
        r = prima_di_giocare.esegui(sys.argv)
        programma.segna_ok()
        sys.exit(r)
    app.setApplicationName('CotW Italiano')
    app.setStyle('Fusion')
    app.setStyleSheet(stile.QSS)
    from cotw.core import percorsi
    import os
    ico = os.path.join(percorsi.cartella_risorse(), 'icona.ico')
    if os.path.isfile(ico):
        app.setWindowIcon(QIcon(ico))
    w = Finestra()
    w.show()
    from cotw.core import programma
    from PySide6.QtCore import QTimer
    QTimer.singleShot(3000, programma.segna_ok)       # "sono ok" per l'avvio (ritorno indietro automatico)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
