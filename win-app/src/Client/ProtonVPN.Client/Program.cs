/*
 * Copyright (c) 2025 Proton AG
 *
 * This file is part of ProtonVPN.
 *
 * ProtonVPN is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * ProtonVPN is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with ProtonVPN.  If not, see <https://www.gnu.org/licenses/>.
 */

using System.Diagnostics;
using System.Security.Principal;
using System.Runtime.InteropServices;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
// Recompile trigger for ProtonVPN Next Proton Unlimited
using ProtonVPN.Common.Core.Extensions;
using ProtonVPN.Client.Services.Bootstrapping.Helpers;

namespace ProtonVPN.Client;

public class Program
{
    // Changed from official app's GUID so both can run simultaneously
    private const string SINGLE_INSTANCE_APP_MUTEX_NAME = "{a3d7f901-2c4b-4e6a-b123-fc9284ad1e72}";
    private const string APP_USER_MODEL_ID = "ProtonVPN.Next";

    private static Mutex? _mutex; // The variable is kept to hold the Mutex lock

    // This method should be async Task to be able to await IsFirstInstanceAsync,
    // but when changing to async Task, the xaml inspector tool is not able to find elements.
    // https://github.com/microsoft/microsoft-ui-xaml/issues/7385
    [STAThread]
    private static void Main(string[] args)
    {
        if (args.ContainsIgnoringCase("-DoUninstallActions"))
        {
            UninstallActions.DeleteClientData();
            UninstallActions.DeleteRegistryKeys(APP_USER_MODEL_ID, App.APPLICATION_NAME);
            return;
        }

        if (!IsAdministrator())
        {
            try
            {
                ProcessStartInfo startInfo = new()
                {
                    FileName = Environment.ProcessPath ?? Process.GetCurrentProcess().MainModule?.FileName ?? "ProtonVPN.Client.exe",
                    Arguments = string.Join(" ", args.Select(a => $"\"{a}\"")),
                    UseShellExecute = true,
                    Verb = "runas"
                };
                Process.Start(startInfo);
            }
            catch
            {
                // User declined UAC
            }
            return;
        }

        if (IsFirstInstance())
        {
            SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID);

            AppDomain.CurrentDomain.ProcessExit += (_, _) => ProtonVPN.Client.Logic.Services.CliVpnServiceCaller.DisconnectOnExit();

            Application.Start(_ =>
            {
                DispatcherQueueSynchronizationContext context = new(DispatcherQueue.GetForCurrentThread());
                SynchronizationContext.SetSynchronizationContext(context);
                new App();
            });
        }
        else
        {
            AppInstanceHelper.RedirectActivation();
        }
    }

    private static bool IsFirstInstance()
    {
        _mutex = new Mutex(true, SINGLE_INSTANCE_APP_MUTEX_NAME, out bool isFirstInstance);
        return isFirstInstance;
    }

    public static void ReleaseMutex()
    {
        try
        {
            _mutex?.ReleaseMutex();
            _mutex?.Dispose();
        }
        catch
        {
        }
    }

    private static bool IsAdministrator()
    {
        using WindowsIdentity identity = WindowsIdentity.GetCurrent();
        WindowsPrincipal principal = new(identity);
        return principal.IsInRole(WindowsBuiltInRole.Administrator);
    }

    [DllImport("shell32.dll", SetLastError = true)]
    private static extern void SetCurrentProcessExplicitAppUserModelID([MarshalAs(UnmanagedType.LPWStr)] string appId);
}