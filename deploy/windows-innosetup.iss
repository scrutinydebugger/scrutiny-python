; -- Scrutiny Debugger InnoSetup script  --
; -- Generates an installer for windows that distribute the Nuitka dist folder

[Setup]
AppName=Scrutiny Debugger
SourceDir={#SOURCE_DIR}
AppVersion={#VERSION}
WizardStyle=modern
DefaultDirName={autopf}\Scrutiny Debugger
DefaultGroupName=Scrutiny
UninstallDisplayIcon={app}\scrutiny.ico
Compression=lzma2
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=scrutiny-setup

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs


[Icons]
Name:"{group}\Scrutiny GUI"; Filename: "{app}\scrutiny.exe"; Parameters: "gui --auto-connect"; WorkingDir: "{app}"
Name:"{group}\Scrutiny GUI (Local)"; Filename: "{app}\scrutiny.exe"; Parameters: "gui --auto-connect --start-local-server"; WorkingDir: "{app}"
Name:"{group}\Uninstall Scrutiny"; Filename: "{uninstallexe}";
