"""Colori e stile dell'interfaccia (tema scuro, accento verde bosco)."""

VERDE = '#5fa86b'
VERDE_SCURO = '#3f7a4a'
ARANCIO = '#d98a3a'
ROSSO = '#d2584f'
FONDO = '#16191b'
PANNELLO = '#1f2326'
BORDO = '#2e3337'
TESTO = '#e8e6e1'
TESTO_TENUE = '#9aa0a3'

import os as _os
SPUNTA = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), 'risorse', 'spunta.svg').replace('\\', '/')

QSS = f"""
QWidget {{ background: {FONDO}; color: {TESTO}; font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 10.5pt; }}
QLabel {{ background: transparent; }}
#barra {{ background: #121416; border-right: 1px solid {BORDO}; }}
#barra QPushButton {{ text-align: left; padding: 10px 18px; border: none; border-radius: 8px; color: {TESTO_TENUE};
                      font-size: 11pt; background: transparent; margin: 2px 10px; }}
#barra QPushButton:hover {{ background: #1c2023; color: {TESTO}; }}
#barra QPushButton:checked {{ background: #22302a; color: {TESTO}; font-weight: 600; }}
#logo {{ font-size: 17pt; font-weight: 700; color: {TESTO}; padding: 22px 22px 2px 22px; }}
#sottologo {{ color: {TESTO_TENUE}; padding: 0 22px 18px 22px; font-size: 9.5pt; }}
#titolo {{ font-size: 18pt; font-weight: 700; }}
#sottotitolo {{ color: {TESTO_TENUE}; }}
#scheda {{ background: {PANNELLO}; border: 1px solid {BORDO}; border-radius: 12px; }}
#scheda QLabel#nome {{ font-size: 12pt; font-weight: 600; }}
#tenue {{ color: {TESTO_TENUE}; }}
#ok {{ color: {VERDE}; font-weight: 600; }}
#attenzione {{ color: {ARANCIO}; font-weight: 600; }}
#errore {{ color: {ROSSO}; font-weight: 600; }}
#pericolo_box {{ background: #3a1d1b; border: 1px solid {ROSSO}; border-radius: 10px; padding: 10px 14px; color: #ffb4ab; font-weight: 600; }}
#banner {{ background: #1d3024; border: 1px solid {VERDE}; border-radius: 10px; }}
#banner QLabel {{ color: #d6f0db; font-weight: 600; }}
#avviso {{ background: #2e2418; border: 1px solid #5a4325; border-radius: 10px; padding: 10px 14px; color: #f0c48f; }}
QPushButton {{ background: #2a3034; border: 1px solid #3a4146; border-radius: 8px; padding: 8px 16px; }}
QPushButton:hover {{ background: #323a3f; }}
#barra QPushButton#dona {{ color: #f3c58a; background: #2b2419; border: 1px solid #5a4325; border-radius: 8px; text-align: center; font-weight: 600; margin: 4px 14px 8px 14px; padding: 9px 10px; }}
#barra QPushButton#dona:hover {{ background: #3a2f1e; color: #ffd9a6; }}
QPushButton:disabled {{ color: #6b7174; background: #22272a; border-color: #2c3135; }}
QPushButton#primario {{ background: {VERDE_SCURO}; border: 1px solid {VERDE}; color: white; font-weight: 600; }}
QPushButton#primario:hover {{ background: {VERDE}; }}
QPushButton#pericolo {{ background: #4a2522; border: 1px solid {ROSSO}; color: #ffd9d5; font-weight: 600; }}
QPushButton#pericolo:hover {{ background: #5e2e2a; }}
QLineEdit, QComboBox {{ background: #121517; border: 1px solid {BORDO}; border-radius: 6px; padding: 6px 8px; }}
QComboBox QAbstractItemView {{ background: {PANNELLO}; selection-background-color: {VERDE_SCURO}; }}
QCheckBox {{ spacing: 8px; font-size: 11pt; font-weight: 600; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid #4a5156; background: #121517; }}
QCheckBox::indicator:checked {{ background: {VERDE}; border-color: {VERDE}; image: url({SPUNTA}); }}
QProgressBar {{ background: #121517; border: 1px solid {BORDO}; border-radius: 6px; height: 14px; text-align: center; color: {TESTO}; }}
QProgressBar::chunk {{ background: {VERDE}; border-radius: 5px; }}
QSlider::groove:horizontal {{ height: 6px; background: #2a3034; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {VERDE}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {TESTO}; width: 18px; height: 18px; margin: -7px 0; border-radius: 9px; }}
QScrollArea {{ border: none; }}
QStatusBar {{ background: #121416; color: {TESTO_TENUE}; border-top: 1px solid {BORDO}; }}
QMessageBox {{ background: {PANNELLO}; }}
"""
