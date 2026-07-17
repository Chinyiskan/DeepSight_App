; Script de Inno Setup moderno para DeepSight
; Se recomienda usar Inno Setup 6 o superior para la compilación

[Setup]
AppName=DeepSight - Entrenador Visual
AppVersion=1.0.0
AppPublisher=DeepSight
DefaultDirName={localappdata}\Programs\DeepSight
DefaultGroupName=DeepSight
DisableProgramGroupPage=yes
; "PrivilegesRequired=lowest" asegura que no pida permisos de administrador y se instale en el espacio del usuario
PrivilegesRequired=lowest
OutputBaseFilename=DeepSight_Setup
SetupIconFile=favicon.ico
Compression=lzma2/max
SolidCompression=yes
; Estilo moderno de Windows 10/11
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
DisableFinishedPage=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Archivo ejecutable principal
Source: "dist\DeepSight\DeepSight.exe"; DestDir: "{app}"; Flags: ignoreversion
; Icono para accesos directos
Source: "favicon.ico"; DestDir: "{app}"; Flags: ignoreversion
; Todos los archivos generados en el directorio dist de PyInstaller
Source: "dist\DeepSight\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: Evitar empaquetar archivos temporales o carpetas de runs antiguas si existieran
ExcludePatterns: "dist\DeepSight\_deepsight_workspace\*"

[Icons]
Name: "{userprograms}\DeepSight"; Filename: "{app}\DeepSight.exe"; IconFilename: "{app}\favicon.ico"
Name: "{userdesktop}\DeepSight"; Filename: "{app}\DeepSight.exe"; IconFilename: "{app}\favicon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\DeepSight.exe"; Description: "{cm:LaunchProgram,DeepSight}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpiar el espacio de trabajo temporal creado por el entrenamiento al desinstalar
Type: filesandordirs; Name: "{app}\_deepsight_workspace"
Type: filesandordirs; Name: "{app}"
