; Taken from here: https://stackoverflow.com/questions/3304463/how-do-i-modify-the-path-environment-variable-when-running-an-inno-setup-install
; Comment from Wojciech Mleczek


[Code]
const SystemEnvironmentKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
const UserEnvironmentKey = 'Environment';

procedure EnvAddPath(Path: string; System: boolean);
var
    Paths: string;
    HKEY: Integer;
    EnvironmentKey: string;
begin
    if System then
    begin
        HKEY:=HKEY_LOCAL_MACHINE;
        EnvironmentKey:=SystemEnvironmentKey;
    end
    else 
    begin
        HKEY:=HKEY_CURRENT_USER;
        EnvironmentKey:=UserEnvironmentKey;
    end;


    { Retrieve current path (use empty string if entry not exists) }
    if not RegQueryStringValue(HKEY, EnvironmentKey, 'Path', Paths)
    then Paths := '';

    { Skip if string already found in path }
    if Pos(';' + Uppercase(Path) + ';', ';' + Uppercase(Paths) + ';') > 0 then exit;

    { App string to the end of the path variable }
    Paths := Paths + ';'+ Path 

    { Overwrite (or create if missing) path environment variable }
    if RegWriteStringValue(HKEY, EnvironmentKey, 'Path', Paths)
    then Log(Format('The [%s] added to PATH: [%s]', [Path, Paths]))
    else Log(Format('Error while adding the [%s] to PATH: [%s]', [Path, Paths]));
end;

procedure EnvRemovePath(Path: string; System:boolean);
var
    Paths: string;
    P: Integer;
    HKEY: Integer;
    EnvironmentKey: string;
begin
    if System then
    begin
        HKEY:=HKEY_LOCAL_MACHINE;
        EnvironmentKey:=SystemEnvironmentKey;
    end
    else 
    begin
        HKEY:=HKEY_CURRENT_USER;
        EnvironmentKey:=UserEnvironmentKey;
    end;

    { Skip if registry entry not exists }
    if not RegQueryStringValue(HKEY, EnvironmentKey, 'Path', Paths) then
        exit;

    { Skip if string not found in path }
    P := Pos(';' + Uppercase(Path) + ';', ';' + Uppercase(Paths) + ';');
    if P = 0 then exit;

    { Update path variable }
    Delete(Paths, P - 1, Length(Path) + 1);

    { Overwrite path environment variable }
    if RegWriteStringValue(HKEY, EnvironmentKey, 'Path', Paths)
    then Log(Format('The [%s] removed from PATH: [%s]', [Path, Paths]))
    else Log(Format('Error while removing the [%s] from PATH: [%s]', [Path, Paths]));
end;
