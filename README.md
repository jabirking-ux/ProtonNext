# ProtonNext

**ProtonNext** is an enhanced Windows client for Proton VPN, pairing the official modern WinUI 3 desktop interface with the fast Next-generation engine backend.

---

## Highlights & Features

- **Full Plan Experience:** Complete UI access to settings, WireGuard protocol, Split Tunneling, and VPN Accelerator.
- **Strict Free Server Enclosure:** Prevents connection attempts to paid Plus/Premium servers or paid-only countries while maintaining clear badges and full server load information. All traffic connects reliably through free server pools (such as Netherlands, United States, Japan, and other free server locations).
- **Dynamic "Change Server" Button:** Quickly cycle between available free servers directly from the main connection card once connected.
- **All-in-One NSIS Installer:** Single installer executable (`ProtonNext-Setup.exe`) that installs or cleanly updates your existing installation, configures desktop and start menu shortcuts, and registers with Windows Add/Remove Programs.
- **Automated CI/CD Releases:** GitHub Actions compiles the solution (`Release x64`), bundles the installer via NSIS, and uploads release assets.
- **Automated Upstream Tracking:** Scheduled GitHub Actions check upstream `win-app` and `ProtonVPN-Next-CLI` changes, flagging newly published commits and updates.

---

## Installation & Setup

1. Download the latest installer `ProtonNext-Setup.exe` from [Releases](https://github.com/jabirking-ux/ProtonNext/releases).
2. Run the installer (Administrator privileges required for VPN network adapter and routing configuration).
3. Launch **ProtonNext** from the Start Menu or Desktop.

---

## Building From Source

### Prerequisites
- Windows 10/11 x64
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- [Python 3.11+](https://www.python.org/)
- [NSIS 3.x](https://nsis.sourceforge.io/) (for building the installer)

### Compile
```powershell
# Restore dependencies and build WinUI 3 Client
dotnet restore win-app/src/Client/ProtonVPN.Client/ProtonVPN.Client.csproj
dotnet build win-app/src/Client/ProtonVPN.Client/ProtonVPN.Client.csproj -c Release -p:Platform=x64

# Package NSIS Installer
makensis installer\ProtonNext.nsi
```
The output installer will be generated as `ProtonNext-Setup.exe`.

---

## Upstream Sources
- Official WinUI Client: [ProtonVPN/win-app](https://github.com/ProtonVPN/win-app)
- Next CLI Engine: [SMH01-MOD-NEXT/ProtonVPN-Next-CLI](https://github.com/SMH01-MOD-NEXT/ProtonVPN-Next-CLI)

---

## License
Licensed under the GNU General Public License v3.0 (GPL-3.0). See [LICENSE](LICENSE) for details.
