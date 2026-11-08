; Installer di CotW Italiano (Inno Setup 6). Lo costruisce strumenti/costruisci_exe.py dopo l'exe.
; Si installa nella cartella Programmi DELL'UTENTE (%LOCALAPPDATA%\Programs\CotW Italiano):
; non chiede permessi da amministratore e l'aggiornamento automatico del programma continua a funzionare.
; Uso: iscc /DVERSIONE=0.5.2 /DSORGENTE=dist\CotW Italiano /DUSCITA=dist /DAVVIO=dist\avvio\CotW Italiano.exe strumenti\installer.iss
; Dalla 0.5.14:  {app}\CotW Italiano.exe = AVVIO (programmino separato che aggiorna e torna indietro se serve)
;                {app}\programma\<versione>\  = programma vero (una cartella per versione)

#ifndef VERSIONE
  #define VERSIONE "0.0.0"
#endif
#ifndef SORGENTE
  #define SORGENTE "..\dist\CotW Italiano"
#endif
#ifndef USCITA
  #define USCITA "..\dist"
#endif
#ifndef AVVIO
  #define AVVIO "..\dist\avvio\CotW Italiano.exe"
#endif

[Setup]
AppId={{7C3E2A55-4B1D-4E8F-9A61-C07E1A1A0001}
AppName=CotW Italiano
AppVersion={#VERSIONE}
AppVerName=CotW Italiano {#VERSIONE}
AppPublisher=Mirko Del Sette
AppPublisherURL=https://github.com/mirkodls/cotw-italiano
AppSupportURL=https://discord.gg/xPgHkstTDn
DefaultDirName={localappdata}\Programs\CotW Italiano
DefaultGroupName=CotW Italiano
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#USCITA}
OutputBaseFilename=CotW_Italiano_Setup_{#VERSIONE}
SetupIconFile=..\risorse\icona.ico
UninstallDisplayIcon={app}\CotW Italiano.exe
UninstallDisplayName=CotW Italiano
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktop"; Description: "Crea l'icona sul desktop"; GroupDescription: "Icone:"

[InstallDelete]
; installazioni fino alla 0.5.14: il programma stava direttamente in {app}. Tolgo i suoi pezzi (ora sta in programma\)
Type: filesandordirs; Name: "{app}\PySide6"
Type: filesandordirs; Name: "{app}\shiboken6"
Type: filesandordirs; Name: "{app}\certifi"
Type: filesandordirs; Name: "{app}\risorse"
Type: files; Name: "{app}\*.dll"
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\CotW Italiano.new.exe"

[Files]
Source: "{#AVVIO}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SORGENTE}\*"; DestDir: "{app}\programma\{#VERSIONE}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CotW Italiano"; Filename: "{app}\CotW Italiano.exe"
Name: "{group}\Disinstalla CotW Italiano"; Filename: "{uninstallexe}"
Name: "{userdesktop}\CotW Italiano"; Filename: "{app}\CotW Italiano.exe"; Tasks: desktop

[Run]
Filename: "{app}\CotW Italiano.exe"; Description: "Apri CotW Italiano adesso"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; toglie il controllo prima di giocare dalle opzioni di Steam (altrimenti Gioca cercherebbe un exe che non c'e' piu')
Filename: "{app}\CotW Italiano.exe"; Parameters: "--disinstalla"; Flags: waituntilterminated; RunOnceId: "TogliSteam"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
