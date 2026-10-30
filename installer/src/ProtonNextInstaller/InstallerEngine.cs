using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using Microsoft.Win32;

namespace ProtonNextInstaller;

internal static class InstallerEngine
{
    public const string AppName = "ProtonNext";
    public const string DisplayName = "ProtonNext VPN";
    public const string AppVersion = "1.0.1";
    public const string Publisher = "ProtonNext";

    public static string DefaultInstallDir =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "ProtonNext");

    public static void TerminateRunningProcesses()
    {
        string[] processNames = ["ProtonVPN.Client", "pvpn-engine", "pvpn-watchdog"];
        foreach (string name in processNames)
        {
            try
            {
                foreach (var p in Process.GetProcessesByName(name))
                {
                    try { p.Kill(true); } catch { }
                }
            }
            catch { }
        }
    }

    public static Stream? GetPayloadStream()
    {
        var asm = Assembly.GetExecutingAssembly();
        foreach (string name in asm.GetManifestResourceNames())
        {
            if (name.EndsWith("payload.zip", StringComparison.OrdinalIgnoreCase))
            {
                return asm.GetManifestResourceStream(name);
            }
        }

        // Fallback: check adjacent to executable
        string adjacent = Path.Combine(AppContext.BaseDirectory, "payload.zip");
        if (File.Exists(adjacent))
        {
            return File.OpenRead(adjacent);
        }

        return null;
    }

    public static void Install(string installDir, Action<int, int, string>? onProgress = null, Action<string>? onLog = null)
    {
        TerminateRunningProcesses();

        onLog?.Invoke($"Output folder: {installDir}");
        Directory.CreateDirectory(installDir);

        using Stream? payloadStream = GetPayloadStream();
        if (payloadStream == null)
        {
            throw new InvalidOperationException("Embedded installation payload not found.");
        }

        using var archive = new ZipArchive(payloadStream, ZipArchiveMode.Read);
        int total = archive.Entries.Count;
        int current = 0;

        // Pre-create all subdirectories
        foreach (var entry in archive.Entries)
        {
            if (string.IsNullOrEmpty(entry.Name) || entry.FullName.EndsWith('/') || entry.FullName.EndsWith('\\'))
            {
                string dirPath = Path.Combine(installDir, entry.FullName.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(dirPath);
            }
        }

        byte[] buffer = new byte[65536];

        foreach (var entry in archive.Entries)
        {
            current++;
            if (string.IsNullOrEmpty(entry.Name) || entry.FullName.EndsWith('/') || entry.FullName.EndsWith('\\'))
            {
                continue;
            }

            string destPath = Path.Combine(installDir, entry.FullName.Replace('/', Path.DirectorySeparatorChar));
            string? parent = Path.GetDirectoryName(destPath);
            if (!string.IsNullOrEmpty(parent) && !Directory.Exists(parent))
            {
                Directory.CreateDirectory(parent);
            }

            onProgress?.Invoke(current, total, entry.Name);
            onLog?.Invoke($"Extract: {entry.Name}");

            using (Stream source = entry.Open())
            using (FileStream dest = new(destPath, FileMode.Create, FileAccess.Write, FileShare.None, 65536))
            {
                int read;
                while ((read = source.Read(buffer, 0, buffer.Length)) > 0)
                {
                    dest.Write(buffer, 0, read);
                }
            }
        }

        // Copy installer as Uninstaller
        string currentExe = Environment.ProcessPath ?? string.Empty;
        string uninstallerDest = Path.Combine(installDir, "Uninstall.exe");
        if (File.Exists(currentExe))
        {
            try
            {
                File.Copy(currentExe, uninstallerDest, true);
                onLog?.Invoke("Create uninstaller: " + uninstallerDest);
            }
            catch { }
        }

        // Create Registry Keys
        RegisterAddRemovePrograms(installDir, uninstallerDest);
        onLog?.Invoke("Created Windows registry uninstall entries");

        // Create Shortcuts
        CreateShortcuts(installDir, uninstallerDest, onLog);

        onLog?.Invoke("Completed");
    }

    private static void RegisterAddRemovePrograms(string installDir, string uninstallerPath)
    {
        try
        {
            RegistryKey? key = null;
            try
            {
                key = Registry.LocalMachine.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext");
            }
            catch
            {
                try
                {
                    key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext");
                }
                catch { }
            }

            if (key != null)
            {
                using (key)
                {
                    string clientExe = Path.Combine(installDir, "ProtonVPN.Client.exe");
                    key.SetValue("DisplayName", DisplayName);
                    key.SetValue("DisplayIcon", $"{clientExe},0");
                    key.SetValue("DisplayVersion", AppVersion);
                    key.SetValue("Publisher", Publisher);
                    key.SetValue("InstallLocation", installDir);
                    key.SetValue("UninstallString", $"\"{uninstallerPath}\" /uninstall");
                    key.SetValue("QuietUninstallString", $"\"{uninstallerPath}\" /uninstall /S");
                    key.SetValue("EstimatedSize", 375000, RegistryValueKind.DWord);
                    key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                    key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                }
            }

            RegistryKey? appKey = null;
            try
            {
                appKey = Registry.LocalMachine.CreateSubKey(@"Software\ProtonNext");
            }
            catch
            {
                try
                {
                    appKey = Registry.CurrentUser.CreateSubKey(@"Software\ProtonNext");
                }
                catch { }
            }

            if (appKey != null)
            {
                using (appKey)
                {
                    appKey.SetValue("InstallLocation", installDir);
                }
            }
        }
        catch { }
    }

    private static void CreateShortcuts(string installDir, string uninstallerPath, Action<string>? onLog)
    {
        string clientExe = Path.Combine(installDir, "ProtonVPN.Client.exe");
        if (!File.Exists(clientExe)) return;

        string commonStartMenu = Environment.GetFolderPath(Environment.SpecialFolder.CommonPrograms);
        string userStartMenu = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
        string startMenuDir = Path.Combine(!string.IsNullOrEmpty(commonStartMenu) ? commonStartMenu : userStartMenu, "ProtonNext");

        string appLnk = Path.Combine(startMenuDir, "ProtonNext.lnk");
        NativeShortcuts.CreateShortcut(appLnk, clientExe, description: "ProtonNext VPN", iconPath: clientExe);
        onLog?.Invoke($"Create shortcut: {appLnk}");

        string uninstLnk = Path.Combine(startMenuDir, "Uninstall ProtonNext.lnk");
        NativeShortcuts.CreateShortcut(uninstLnk, uninstallerPath, arguments: "/uninstall", description: "Uninstall ProtonNext", iconPath: uninstallerPath);

        string commonDesktop = Environment.GetFolderPath(Environment.SpecialFolder.CommonDesktopDirectory);
        string userDesktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        string desktopDir = !string.IsNullOrEmpty(commonDesktop) ? commonDesktop : userDesktop;

        string desktopLnk = Path.Combine(desktopDir, "ProtonNext.lnk");
        NativeShortcuts.CreateShortcut(desktopLnk, clientExe, description: "ProtonNext VPN", iconPath: clientExe);
        onLog?.Invoke($"Create shortcut: {desktopLnk}");
    }

    public static void Uninstall(string installDir, Action<string>? onLog = null)
    {
        TerminateRunningProcesses();
        onLog?.Invoke("Terminated running processes");

        // Delete shortcuts
        try
        {
            string commonStartMenu = Environment.GetFolderPath(Environment.SpecialFolder.CommonPrograms);
            string userStartMenu = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
            string startMenuDir = Path.Combine(!string.IsNullOrEmpty(commonStartMenu) ? commonStartMenu : userStartMenu, "ProtonNext");
            if (Directory.Exists(startMenuDir))
            {
                Directory.Delete(startMenuDir, true);
                onLog?.Invoke("Removed Start Menu shortcuts");
            }

            string commonDesktop = Environment.GetFolderPath(Environment.SpecialFolder.CommonDesktopDirectory);
            string userDesktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string desktopDir = !string.IsNullOrEmpty(commonDesktop) ? commonDesktop : userDesktop;
            string desktopLnk = Path.Combine(desktopDir, "ProtonNext.lnk");
            if (File.Exists(desktopLnk))
            {
                File.Delete(desktopLnk);
                onLog?.Invoke("Removed Desktop shortcut");
            }
        }
        catch { }

        // Remove Registry Keys
        try
        {
            Registry.LocalMachine.DeleteSubKeyTree(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext", false);
            Registry.LocalMachine.DeleteSubKeyTree(@"Software\ProtonNext", false);
            Registry.CurrentUser.DeleteSubKeyTree(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\ProtonNext", false);
            Registry.CurrentUser.DeleteSubKeyTree(@"Software\ProtonNext", false);
            onLog?.Invoke("Removed registry keys");
        }
        catch { }

        // Spawn delayed self-deletion for folder
        onLog?.Invoke("Removing installed files...");
        try
        {
            string cmd = $"/C ping 127.0.0.1 -n 2 > nul & rmdir /s /q \"{installDir}\"";
            Process.Start(new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = cmd,
                CreateNoWindow = true,
                UseShellExecute = false
            });
        }
        catch { }
    }
}
