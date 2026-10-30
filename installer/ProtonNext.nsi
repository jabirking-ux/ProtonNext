; ProtonNext NSIS Installer Script
Unicode True
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

Name "ProtonNext"
OutFile "..\ProtonNext-Setup.exe"
InstallDir "$PROGRAMFILES64\ProtonNext"
InstallDirRegKey HKLM "Software\ProtonNext" "InstallLocation"
RequestExecutionLevel admin

; UI Configuration
!define MUI_ICON "..\win-app\Setup\Images\protonvpn.ico"
!define MUI_UNICON "..\win-app\Setup\Images\protonvpn.ico"
!define MUI_ABORTWARNING

; Installer Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ProtonVPN.Client.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ProtonNext"
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "ProtonNext" SecCore
    SectionIn RO

    ; Stop existing running instances if upgrading
    DetailPrint "Terminating existing ProtonNext processes..."
    nsExec::Exec 'taskkill /F /IM ProtonVPN.Client.exe /T'
    nsExec::Exec 'taskkill /F /IM pvpn-engine.exe /T'
    Sleep 1000

    SetOutPath "$INSTDIR"
    
    ; Copy compiled Client application files
    File /r "..\win-app\src\bin\*.*"

    ; Copy ProtonVPN-Next-CLI files into ProtonVPN-Next-CLI subdirectory
    SetOutPath "$INSTDIR\ProtonVPN-Next-CLI"
    File /r /x "__pycache__" /x ".git" /x "*.pyc" /x "result" /x "*.tmp" "..\ProtonVPN-Next-CLI\*.*"

    ; Registry for Install Location & Add/Remove Programs
    WriteRegStr HKLM "Software\ProtonNext" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "DisplayName" "ProtonNext VPN"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "DisplayIcon" "$INSTDIR\ProtonVPN.Client.exe,0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "DisplayVersion" "1.0.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "Publisher" "ProtonNext"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext" "NoRepair" 1

    ; Uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Shortcuts
    CreateDirectory "$SMPROGRAMS\ProtonNext"
    CreateShortcut "$SMPROGRAMS\ProtonNext\ProtonNext.lnk" "$INSTDIR\ProtonVPN.Client.exe" "" "$INSTDIR\ProtonVPN.Client.exe" 0
    CreateShortcut "$SMPROGRAMS\ProtonNext\Uninstall ProtonNext.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
    CreateShortcut "$DESKTOP\ProtonNext.lnk" "$INSTDIR\ProtonVPN.Client.exe" "" "$INSTDIR\ProtonVPN.Client.exe" 0

SectionEnd

Section "Uninstall"
    ; Terminate running processes before uninstalling
    DetailPrint "Terminating existing ProtonNext processes..."
    ExecWait 'taskkill /F /IM ProtonVPN.Client.exe /T'
    ExecWait 'taskkill /F /IM pvpn-engine.exe /T'
    Sleep 1000

    ; Delete shortcuts
    Delete "$DESKTOP\ProtonNext.lnk"
    Delete "$SMPROGRAMS\ProtonNext\ProtonNext.lnk"
    Delete "$SMPROGRAMS\ProtonNext\Uninstall ProtonNext.lnk"
    RMDir "$SMPROGRAMS\ProtonNext"

    ; Delete uninstaller and application files
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR"

    ; Delete Registry Keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext"
    DeleteRegKey HKLM "Software\ProtonNext"

SectionEnd
