; AAiOS Windows Installer (Inno Setup)
; =====================================
;
; Phase 2 scaffold. The actual install logic (service creation, ACL setup,
; master key generation, dependency installation) lands in Phase 14.
;
; Build with:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" deploy\windows\aaios.iss
;
; Output:
;   deploy\windows\Output\AAiOS-Setup-<version>-x64.exe
;
; See:
;   docs/architecture/08-deployment-topology.md §1-§2 (Windows-native layout)
;   docs/architecture/07-security-model.md §2.4 (service account)

#define AAiOSVersion "0.1.0.0"
#define AAiOSPublisher "AAiOS Contributors"
#define AAiOSURL "https://github.com/rachidSabah/aaios"

[Setup]
AppId={{8F2B5A3E-7C9D-4E1A-B6F2-1A2B3C4D5E6F}
AppName=AAiOS
AppVersion={#AAiOSVersion}
AppVerName=AAiOS {#AAiOSVersion}
AppPublisher={#AAiOSPublisher}
AppPublisherURL={#AAiOSURL}
AppSupportURL={#AAiOSURL}/issues
AppUpdatesURL={#AAiOSURL}/releases
AppLicenseFile=..\..\LICENSE
AppReadmeFile=..\..\README.md

DefaultDirName={pf}\AAiOS
DefaultGroupName=AAiOS
DisableProgramGroupPage=yes

OutputDir=Output
OutputBaseFilename=AAiOS-Setup-{#AAiOSVersion}-x64

Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

PrivilegesRequired=admin
InstallScope=machine

; Wizard styling
WizardStyle=modern
SetupIconFile=aaios.ico
UninstallDisplayIcon={app}\bin\aaios.exe

; Windows version check (Windows 11 = 10.0.22000+)
MinVersion=10.0.22000

; Force restart prompt after install (for service registration)
RestartIfNeededByRun=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Start AAiOS services on system startup"; GroupDescription: "Additional shortcuts:"

[Dirs]
; Install dir (created automatically)
Name: "{app}"; Permissions: admins-readwrite
; ProgramData dir (system-wide config + data)
Name: "{commonappdata}\AAiOS"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\config"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\data"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\data\postgres"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\data\qdrant"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\data\runtime"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\data\plugins"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\data\workspaces"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\logs"; Permissions: admins-readwrite
Name: "{commonappdata}\AAiOS\logs\audit"; Permissions: admins-readwrite

[Files]
; Binaries (built by PyInstaller in Phase 14)
Source: "..\..\dist\aaios.exe"; DestDir: "{app}\bin"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\..\..\dist\aaios.exe'))
Source: "..\..\dist\python\*"; DestDir: "{app}\bin\python"; Flags: ignoreversion recursesubdirs; Check: DirExists(ExpandConstant('{src}\..\..\dist\python'))
Source: "..\..\dist\web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs; Check: DirExists(ExpandConstant('{src}\..\..\dist\web'))
Source: "..\..\dist\lib\*"; DestDir: "{app}\lib"; Flags: ignoreversion recursesubdirs; Check: DirExists(ExpandConstant('{src}\..\..\dist\lib'))

; Default config
Source: "..\..\config\defaults.yaml"; DestDir: "{commonappdata}\AAiOS\config"; DestName: "config.yaml"; Flags: onlyifdoesntexist

; Bootstrap script (creates services, generates master key, etc.)
Source: "bootstrap.ps1"; DestDir: "{app}\bin"; Flags: ignoreversion

[Icons]
Name: "{group}\AAiOS Dashboard"; Filename: "http://127.0.0.1:3000"
Name: "{group}\AAiOS CLI"; Filename: "{cmd}"; Parameters: "/k {app}\bin\aaios.exe"
Name: "{group}\Uninstall AAiOS"; Filename: "{uninstallexe}"
Name: "{commondesktop}\AAiOS Dashboard"; Filename: "http://127.0.0.1:3000"; Tasks: desktopicon

[Run]
; Run the bootstrap script after install
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\bin\bootstrap.ps1"" -Action install -InstallDir ""{app}"" -DataDir ""{commonappdata}\AAiOS"""; \
  WorkingDir: "{app}"; \
  Flags: runhidden waituntilterminated; \
  StatusMsg: "Configuring AAiOS services..."

; Open the dashboard at the end
Filename: "cmd.exe"; \
  Parameters: "/c start http://127.0.0.1:3000"; \
  Flags: nowait postinstall skipifsilent runhidden

[UninstallRun]
; Tear down services on uninstall
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\bin\bootstrap.ps1"" -Action uninstall"; \
  Flags: runhidden waituntilterminated

[UninstallDelete]
; Clean up services and data (but keep user data dir for safety)
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{commonappdata}\AAiOS\logs"
; NOTE: {commonappdata}\AAiOS\data is preserved — user must delete manually

[Code]
function FileExists(const FileName: string): Boolean;
begin
  Result := FileOrDirExists(FileName);
end;

function DirExists(const DirName: string): Boolean;
begin
  Result := FileOrDirExists(DirName);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Phase 14: check Python / Node / Postgres / Qdrant prerequisites
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Phase 14: generate master key on first install, create service account
    Log('AAiOS: post-install step — bootstrap.ps1 handles this.');
  end;
end;
