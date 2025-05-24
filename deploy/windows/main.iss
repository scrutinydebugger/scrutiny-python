; -- Scrutiny Debugger InnoSetup script  --
; -- Generates an installer for windows that distribute the Nuitka dist folder

#include "environment.iss"

#define BINNAME "scrutiny.exe"

[Setup]
ChangesEnvironment=true
AppName=Scrutiny Debugger
SourceDir={#SOURCE_DIR}
AppVersion={#VERSION}
WizardStyle=modern
DefaultDirName={autopf}\Scrutiny Debugger
DefaultGroupName=Scrutiny
Uninstallable=true
Compression=lzma2
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=scrutiny-{#VERSION}-setup
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=scrutiny.ico
UninstallDisplayIcon={app}\scrutiny.ico

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "envPath";        Description: "Add to PATH variable"

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name:"{group}\Scrutiny GUI";            Filename: "{app}\{#BINNAME}"; Parameters: "gui --auto-connect";                       WorkingDir: "{app}";
Name:"{group}\Scrutiny GUI (Local)";    Filename: "{app}\{#BINNAME}"; Parameters: "gui --auto-connect --start-local-server";  WorkingDir: "{app}";
Name:"{userdesktop}\Scrutiny GUI";      Filename: "{app}\{#BINNAME}"; Parameters: "gui --auto-connect";                       WorkingDir: "{app}";    Tasks: desktopicon;
Name:"{group}\Uninstall Scrutiny";      Filename: "{uninstallexe}";

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
    if (CurStep = ssPostInstall)  and IsTaskSelected('envPath') then 
        EnvAddPath(ExpandConstant('{app}'), IsAdminInstallMode());
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
    if CurUninstallStep = usPostUninstall then 
        EnvRemovePath(ExpandConstant('{app}'), IsAdminInstallMode());
end;
