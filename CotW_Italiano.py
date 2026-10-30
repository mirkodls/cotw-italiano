"""Avvio di CotW Italiano."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from cotw.ui.finestra import Finestra
from cotw.ui import stile


def main():
    # avviato senza console (pythonw): gli errori finiscono in un file, cosi' si possono mandare a Claude
    if sys.stderr is None or sys.stdout is None:
        from cotw.core import percorsi
        import os
        log = open(os.path.join(percorsi.dati_app(), 'errori.log'), 'a', encoding='utf-8', buffering=1)
        sys.stderr = sys.stdout = log
    app = QApplication(sys.argv)
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
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
