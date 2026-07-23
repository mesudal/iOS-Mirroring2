[Setup]
AppName=iOS 미러링
AppVersion=1.0
DefaultDirName={autopf}\iOSMirrorCapture
DefaultGroupName=iOS 미러링
OutputDir=C:\Users\zerosoft\Desktop
OutputBaseFilename=Setup_iOSMirrorCapture_v13
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
; Require admin privileges to install Bonjour SDK and write to Program Files
PrivilegesRequired=admin

[Files]
; All files from the pyinstaller dist folder (including our bin folder)
Source: "C:\Users\zerosoft\Desktop\dist\ios_mirror_capture\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "c:\Users\zerosoft\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\local-agent-mode-sessions\777b7bdf-8e8a-4075-9595-53d218721eeb\465b48db-5a2c-43c1-ae11-f7d3e3489edc\local_0af0b912-91f6-4abd-9d9e-2e0c881e771d\outputs\launcher.vbs"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\iOS 미러링"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; IconFilename: "{app}\ios_mirror_capture.exe"
Name: "{autodesktop}\iOS 미러링"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; IconFilename: "{app}\ios_mirror_capture.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
; Run app after installation
Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; Description: "Launch iOS 미러링"; Flags: nowait postinstall skipifsilent

[Code]
function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\iOS Mirror Capture_is1';
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    if not RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString) then
      if not RegQueryStringValue(HKLM64, sUnInstPath, 'UninstallString', sUnInstallString) then
        RegQueryStringValue(HKCU64, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

function UnInstallOldVersion(): Integer;
var
  sUnInstallString: String;
  iResultCode: Integer;
begin
  Result := 0;
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then begin
    sUnInstallString := RemoveQuotes(sUnInstallString);
    if Exec(sUnInstallString, '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, iResultCode) then
      Result := 3
    else
      Result := 2;
  end else
    Result := 1;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) then
  begin
    if IsUpgrade() then
    begin
      UnInstallOldVersion();
    end;
  end;
end;
