# CotW Italiano

Programma per installare e aggiornare la **traduzione italiana** (testo e doppiaggio) di **theHunter: Call of the Wild**.
Di **Mirko Del Sette**.

## ⬇️ Scarica

<!--scarica-->
**[Scarica l'installer](https://github.com/mirkodls/cotw-italiano/releases/download/programma-v0.5.7/CotW_Italiano_Setup_0.5.7.exe)** (`CotW_Italiano_Setup_0.5.7.exe`)

1. Apri il file scaricato: si installa da solo e mette l'icona **CotW Italiano** sul desktop (non chiede permessi da amministratore).
2. Vai su **Installa** -> **Scarica e installa**: il programma scarica testo e doppiaggio e li mette nel gioco.

_Preferisci senza installer? Nella [pagina della versione](https://github.com/mirkodls/cotw-italiano/releases/tag/programma-v0.5.7) c'e' anche `CotW_Italiano_0.5.7.zip`: estrai TUTTO lo zip in una cartella e apri `CotW Italiano.exe`._
<!--/scarica-->

Non serve installare altro. Il programma **si aggiorna da solo**: quando esce una versione nuova te lo dice e fa tutto lui.

> Se Windows mostra "PC protetto da Windows" è normale per un programma nuovo: *Ulteriori informazioni* → *Esegui comunque*.
> L'exe non viene costruito sul PC dell'autore ma **automaticamente da GitHub** a partire da questo codice (vedi *Actions*), e nella pagina della versione c'è l'impronta SHA-256 per controllarlo.

## Cosa fa

- **Traduzione e doppiaggio**: installa testo e voci italiane insieme o separati, controllando l'integrità di ogni file. Scarica solo quello che cambia.
- **Non tocca i file del gioco**: usa solo la cartella `dropzone`. Le altre mod restano come sono.
- **Avvio del gioco**: imposta da solo le opzioni di avvio di Steam e crea un collegamento sul desktop.
- **Salvataggi**: backup con nome, ripristino, azzeramento delle missioni.
- **Strumenti**: volume del quad (solo per te, non per gli animali).
- **Segnala errore**: scegli mappa e problema, la segnalazione arriva da sola sul Discord.
- **Contribuisci**: quando il gioco aggiunge battute nuove puoi aiutare a doppiarle gratis con un tuo account ElevenLabs. La tua chiave resta sul tuo PC.

⚠️ **Prima di giocare online disattiva le mod** (tasto in Home).

## Community

- Discord (novità, aiuto, segnalazioni): https://discord.gg/xPgHkstTDn
- Sostieni il progetto: https://ko-fi.com/mirkodls

## Licenze

- **Programma** (il codice di questo repository): [GNU GPL v3](LICENSE).
- **Traduzione e doppiaggio italiani** (i file nelle Release): [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/deed.it) — gratis, citando Mirko Del Sette; vietato venderli o ripubblicarli modificati. Dettagli in [LICENZA_TRADUZIONE.txt](LICENZA_TRADUZIONE.txt).
- theHunter: Call of the Wild appartiene a Expansive Worlds / Avalanche Studios Group. Progetto amatoriale non ufficiale. Le voci sono generate con ElevenLabs.

## Per sviluppatori

- Avvio dal codice: `AVVIA_COTW_ITALIANO.bat` (serve Python 3).
- Costruzione dell'exe: GitHub *Actions* → **Crea exe del programma** (Python 3.13 + Nuitka, script `strumenti/costruisci_exe.py`).
- Il postino delle segnalazioni e dei contributi (Cloudflare Worker): [postino/worker.js](postino/worker.js).
