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

## 🔒 Sicurezza

- **Aggiornamenti firmati** (dalla 0.5.7): il programma installa solo aggiornamenti con la firma digitale dell'autore (Ed25519). Se qualcuno modifica un file online, il programma lo rifiuta.
- **Controllo di ogni file**: ogni pacchetto scaricato viene verificato con la sua impronta SHA-256; i nomi e i percorsi dei file vengono controllati prima di estrarli.
- **Chiavi dell'autore protette**: le chiavi usate per pubblicare sono custodite in una cassaforte cifrata (AES-256-GCM) con password.
- **Codice aperto**: tutto il codice del programma è in questo repository. Le impronte SHA-256 di ogni versione sono nella pagina della versione.
- Scarica il programma **solo da questa pagina GitHub** (o dalla pagina ufficiale su Nexus Mods).

Nessun software è sicuro al 100%: se noti qualcosa di strano, segnalalo su Discord.
- **Indirizzo delle segnalazioni firmato** (dalla 0.5.8): anche l'indirizzo del servizio che riceve segnalazioni e contributi è firmato dall'autore. Nessuno può dirottarli.

### Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
(Richiesta in corso: finché l'exe non è firmato, Windows SmartScreen può mostrare un avviso. Scegli "Ulteriori informazioni" → "Esegui comunque".)

- **Team roles**: Committer and Reviewer: [Mirko Del Sette (mirkodls)](https://github.com/mirkodls). Approver: Mirko Del Sette. Il progetto è mantenuto da una sola persona: ogni contributo esterno (pull request) viene revisionato dall'autore prima di entrare nel codice; ogni richiesta di firma è approvata dall'autore.
- **Build**: ogni exe è costruito automaticamente da GitHub Actions ([crea_exe.yml](.github/workflows/crea_exe.yml)) a partire dal codice di questo repository. Nessun binario viene costruito a mano.

### Privacy

Il programma non raccoglie dati personali e non ha pubblicità. Collegamenti in uscita:
- **GitHub** (github.com, raw.githubusercontent.com): per controllare e scaricare gli aggiornamenti della traduzione, del doppiaggio e del programma.
- **Servizio segnalazioni** (Cloudflare Worker dell'autore): solo quando l'utente invia una segnalazione o un contributo al doppiaggio. Viene inviato il testo della segnalazione (e il nome che l'utente sceglie di scrivere) oppure l'audio generato. L'indirizzo IP è visto dal servizio solo per limitare lo spam e non viene salvato.
- **ElevenLabs** (api.elevenlabs.io): solo se l'utente sceglie di contribuire al doppiaggio con la PROPRIA chiave ElevenLabs. La chiave resta sul PC dell'utente (cifrata da Windows) e va solo a ElevenLabs.

Non vengono inviati dati del gioco, dell'account Steam o del computer.

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
