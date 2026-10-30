using System;
using System.IO;
using System.Windows.Forms;

namespace ProtonNextInstaller;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        ApplicationConfiguration.Initialize();

        bool silent = false;
        bool uninstall = false;
        string? targetDir = null;

        // Check if executed as Uninstall.exe
        string exeName = Path.GetFileName(Environment.ProcessPath ?? string.Empty);
        if (exeName.Equals("Uninstall.exe", StringComparison.OrdinalIgnoreCase))
        {
            uninstall = true;
        }

        foreach (string arg in args)
        {
            if (arg.Equals("/S", StringComparison.OrdinalIgnoreCase) ||
                arg.Equals("/silent", StringComparison.OrdinalIgnoreCase) ||
                arg.Equals("-s", StringComparison.OrdinalIgnoreCase))
            {
                silent = true;
            }
            else if (arg.Equals("/uninstall", StringComparison.OrdinalIgnoreCase) ||
                     arg.Equals("-uninstall", StringComparison.OrdinalIgnoreCase) ||
                     arg.Equals("--uninstall", StringComparison.OrdinalIgnoreCase))
            {
                uninstall = true;
            }
            else if (arg.StartsWith("/D=", StringComparison.OrdinalIgnoreCase))
            {
                targetDir = arg[3..].Trim().Trim('"');
            }
            else if (arg.StartsWith("-d=", StringComparison.OrdinalIgnoreCase))
            {
                targetDir = arg[3..].Trim().Trim('"');
            }
        }

        // If uninstalling and no directory was specified, detect current dir or fallback to default
        if (uninstall && string.IsNullOrEmpty(targetDir))
        {
            string? baseDir = AppContext.BaseDirectory;
            if (!string.IsNullOrEmpty(baseDir) && File.Exists(Path.Combine(baseDir, "ProtonVPN.Client.exe")))
            {
                targetDir = Path.GetFullPath(baseDir).TrimEnd('\\', '/');
            }
            else
            {
                targetDir = InstallerEngine.DefaultInstallDir;
            }
        }

        if (silent)
        {
            try
            {
                string effectiveDir = !string.IsNullOrEmpty(targetDir) ? targetDir : InstallerEngine.DefaultInstallDir;
                if (uninstall)
                {
                    InstallerEngine.Uninstall(effectiveDir);
                }
                else
                {
                    InstallerEngine.Install(effectiveDir);
                }
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex.Message);
                return 1;
            }
        }

        Application.Run(new MainForm(uninstall, targetDir));
        return 0;
    }
}
