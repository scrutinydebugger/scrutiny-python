; -- Scrutiny Debugger InnoSetup script  --
; -- Generates an installer for Windows that distribute the Nuitka dist folder

#include "environment.iss"

#define BINNAME "scrutiny.exe"

#pragma message "++ SOURCE_DIR=" + Str(SOURCE_DIR)
#pragma message "++ VERSION=" + Str(VERSION)

[Setup]
;Inform the OS about environment change
ChangesEnvironment=true
;Name for display
AppName=Scrutiny Debugger
;The folder to install. Nuitka output. 
SourceDir={#SOURCE_DIR}
;Version of the app A.B.C[.D].  No v prefix
AppVersion={#VERSION}
;Styling
WizardStyle=modern
;Install dir.  autopf = Auto Program File.  Depends on privileged mode or not.  
DefaultDirName={autopf}\Scrutiny Debugger
;Group is used for the start menu icon
DefaultGroupName=Scrutiny
;Allow uninstall
Uninstallable=true
; Data compression
Compression=lzma2
SolidCompression=yes
;Where to output the installer .exe. Relative to the source dir
OutputDir=installer
;Name of the installer executable
OutputBaseFilename=scrutiny-v{#VERSION}-setup
;Privleged mode will be prompted to the user.
PrivilegesRequiredOverridesAllowed=dialog
;Icon for the installer software. Also included in the app 
SetupIconFile=scrutiny.ico
;Icon for the uninstaller software. Also included in the app
UninstallDisplayIcon={app}\scrutiny.ico

[Tasks]
; Checkbox for icon desktop
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Checkbox for icon PATH change
Name: "envPath";        Description: "Add to PATH variable"

[Files]
; Copy the whole source folder as is
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
; Start menu
Name:"{group}\Scrutiny GUI";            Filename: "{app}\{#BINNAME}"; Parameters: "gui --auto-connect";                       WorkingDir: "{app}";
Name:"{group}\Scrutiny GUI (Local)";    Filename: "{app}\{#BINNAME}"; Parameters: "gui --auto-connect --start-local-server";  WorkingDir: "{app}";
; Desktop icon. Depends on task and privileged mode
Name:"{autodesktop}\Scrutiny GUI";      Filename: "{app}\{#BINNAME}"; Parameters: "gui --auto-connect";                       WorkingDir: "{app}";    Tasks: desktopicon;
Name:"{group}\Uninstall Scrutiny";      Filename: "{uninstallexe}";

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
    if (CurStep = ssPostInstall)  and WizardIsTaskSelected('envPath') then 
        EnvAddPath(ExpandConstant('{app}'), IsAdminInstallMode());
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
    if CurUninstallStep = usPostUninstall then 
        EnvRemovePath(ExpandConstant('{app}'), IsAdminInstallMode());
end;
