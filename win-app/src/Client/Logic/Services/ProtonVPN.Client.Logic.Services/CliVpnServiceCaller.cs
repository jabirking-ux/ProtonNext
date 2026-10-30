/*
 * Copyright (c) 2026 Proton AG / PVPN-Next
 *
 * This file is part of ProtonVPN.
 *
 * ProtonVPN is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

using System.Diagnostics;
using System.Net.NetworkInformation;
using System.Text.Json;
using ProtonVPN.Client.EventMessaging.Contracts;
using ProtonVPN.Client.Logic.Services.Contracts;
using ProtonVPN.Client.Settings.Contracts;
using ProtonVPN.Common.Legacy.Abstract;
using ProtonVPN.Logging.Contracts;
using ProtonVPN.Logging.Contracts.Events.AppLogs;
using ProtonVPN.ProcessCommunication.Contracts.Entities.LocalAgent;
using ProtonVPN.ProcessCommunication.Contracts.Entities.Settings;
using ProtonVPN.ProcessCommunication.Contracts.Entities.Vpn;

namespace ProtonVPN.Client.Logic.Services;

public class CliVpnServiceCaller : IVpnServiceCaller
{
    private readonly ILogger _logger;
    private readonly IEventMessageSender _eventMessageSender;
    private readonly ISettings _settings;

    private static readonly object _lock = new();
    private static string? _lastConnectedServerName;
    private static string? _lastConnectedServerIp;
    private static string? _lastConnectedServerLabel;
    private static VpnProtocolIpcEntity _currentProtocol = VpnProtocolIpcEntity.WireGuardUdp;

    private long _lastBytesIn;
    private long _lastBytesOut;
    private DateTime _lastTrafficSampleTime = DateTime.UtcNow;

    private static readonly SemaphoreSlim _connectionSemaphore = new(1, 1);
    private static CancellationTokenSource? _activeConnectCts;
    private static volatile bool _isConnecting;
    private static volatile bool _isExiting;

    public CliVpnServiceCaller(
        ILogger logger,
        IEventMessageSender eventMessageSender,
        ISettings settings)
    {
        _logger = logger;
        _eventMessageSender = eventMessageSender;
        _settings = settings;
    }

    public async Task ConnectAsync(ConnectionRequestIpcEntity connectionRequest)
    {
        if (_isExiting)
        {
            _logger.Info<AppLog>("[CliVpnServiceCaller] ConnectAsync ignored: application is exiting.");
            return;
        }

        await _connectionSemaphore.WaitAsync();
        CancellationTokenSource cts;
        lock (_lock)
        {
            _activeConnectCts?.Cancel();
            _activeConnectCts = new CancellationTokenSource();
            cts = _activeConnectCts;
            _isConnecting = true;
        }

        try
        {
            VpnServerIpcEntity? targetServer = connectionRequest.Servers.FirstOrDefault();
            string serverCliTarget = "fastest";
            if (targetServer != null)
            {
                if (!string.IsNullOrWhiteSpace(targetServer.Label) && 
                    !targetServer.Label.Equals("Fastest Server", StringComparison.OrdinalIgnoreCase) &&
                    !targetServer.Label.Contains("protonvpn.net", StringComparison.OrdinalIgnoreCase) &&
                    targetServer.Label != "0" && targetServer.Label != "1" && targetServer.Label != "2")
                {
                    serverCliTarget = targetServer.Label;
                }
                else if (!string.IsNullOrWhiteSpace(targetServer.Name) && 
                         !targetServer.Name.Equals("fastest", StringComparison.OrdinalIgnoreCase) &&
                         !targetServer.Name.Contains("protonvpn.net", StringComparison.OrdinalIgnoreCase) &&
                         (targetServer.Name.Contains('#') || targetServer.Name.Length == 2))
                {
                    serverCliTarget = targetServer.Name;
                }
                else if (!string.IsNullOrWhiteSpace(targetServer.Ip) && targetServer.Ip != "10.2.0.1")
                {
                    serverCliTarget = targetServer.Ip;
                }
            }

            string serverIp = targetServer?.Ip ?? "10.2.0.1";
            string serverLabel = targetServer?.Label ?? targetServer?.Name ?? serverCliTarget;
            _currentProtocol = connectionRequest.Protocol;

            lock (_lock)
            {
                _lastConnectedServerName = serverCliTarget;
                _lastConnectedServerIp = serverIp;
                _lastConnectedServerLabel = serverLabel;
            }

            _logger.Info<AppLog>($"[CliVpnServiceCaller] Connecting to target '{serverCliTarget}' ({serverIp}) via PVPN-Next CLI...");

            _eventMessageSender.Send(new VpnStateIpcEntity
            {
                Status = VpnStatusIpcEntity.Connecting,
                EndpointIp = serverIp,
                Label = serverLabel,
                VpnProtocol = _currentProtocol
            });

            await Task.Run(() =>
            {
                try
                {
                    RunCliCommand($"connect \"{serverCliTarget}\"");

                    // Check routing state for up to 35 seconds
                    bool connected = WaitForTunnelState(active: true, timeoutSeconds: 35, cts.Token);
                    if (connected)
                    {
                        var (activeName, activeIp) = ReadRoutingSessionInfo();
                        string finalIp = !string.IsNullOrEmpty(activeIp) ? activeIp : serverIp;
                        string finalLabel = !string.IsNullOrEmpty(activeName) ? activeName : serverLabel;

                        lock (_lock)
                        {
                            _lastConnectedServerName = finalLabel;
                            _lastConnectedServerIp = finalIp;
                            _lastConnectedServerLabel = finalLabel;
                        }

                        _logger.Info<AppLog>($"[CliVpnServiceCaller] Successfully connected to {finalLabel} ({finalIp})");
                        _eventMessageSender.Send(new VpnStateIpcEntity
                        {
                            Status = VpnStatusIpcEntity.Connected,
                            EndpointIp = finalIp,
                            Label = finalLabel,
                            VpnProtocol = _currentProtocol,
                            EndpointPort = 51820
                        });
                    }
                    else
                    {
                        if (cts.IsCancellationRequested)
                        {
                            _logger.Info<AppLog>($"[CliVpnServiceCaller] Connection attempt to {serverCliTarget} was cancelled.");
                        }
                        else
                        {
                            _logger.Warn<AppLog>($"[CliVpnServiceCaller] Connection attempt to {serverCliTarget} timed out or failed.");
                            _eventMessageSender.Send(new VpnStateIpcEntity
                            {
                                Status = VpnStatusIpcEntity.Disconnected,
                                Error = VpnErrorTypeIpcEntity.Unknown
                            });
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.Error<AppLog>($"[CliVpnServiceCaller] Connect exception: {ex.Message}", ex);
                    _eventMessageSender.Send(new VpnStateIpcEntity
                    {
                        Status = VpnStatusIpcEntity.Disconnected,
                        Error = VpnErrorTypeIpcEntity.Unknown
                    });
                }
            });
        }
        finally
        {
            _isConnecting = false;
            _connectionSemaphore.Release();
        }
    }

    public async Task DisconnectAsync(DisconnectionRequestIpcEntity disconnectionRequest)
    {
        lock (_lock)
        {
            _isConnecting = false;
            _activeConnectCts?.Cancel();
        }

        await _connectionSemaphore.WaitAsync();
        try
        {
            _logger.Info<AppLog>("[CliVpnServiceCaller] Disconnecting VPN via PVPN-Next CLI...");

            _eventMessageSender.Send(new VpnStateIpcEntity
            {
                Status = VpnStatusIpcEntity.Disconnecting,
                EndpointIp = _lastConnectedServerIp ?? string.Empty,
                Label = _lastConnectedServerLabel ?? string.Empty,
                VpnProtocol = _currentProtocol
            });

            await Task.Run(() =>
            {
                try
                {
                    RunCliCommand("disconnect");
                    WaitForTunnelState(active: false, timeoutSeconds: 15);

                    bool stillActive = IsRoutingStateActive();
                    if (!stillActive && !_isConnecting)
                    {
                        _eventMessageSender.Send(new VpnStateIpcEntity
                        {
                            Status = VpnStatusIpcEntity.Disconnected
                        });
                    }
                }
                catch (Exception ex)
                {
                    _logger.Error<AppLog>($"[CliVpnServiceCaller] Disconnect exception: {ex.Message}", ex);
                    _eventMessageSender.Send(new VpnStateIpcEntity
                    {
                        Status = VpnStatusIpcEntity.Disconnected
                    });
                }
            });
        }
        finally
        {
            _connectionSemaphore.Release();
        }
    }

    /// <summary>
    /// Synchronously disconnects the VPN tunnel on app exit.
    /// Called during window close or process termination to ensure the tunnel doesn't outlive the process.
    /// </summary>
    public static void DisconnectOnExit()
    {
        _isExiting = true;
        lock (_lock)
        {
            _activeConnectCts?.Cancel();
        }

        try
        {
            string scriptPath = LocateCliScriptPath();
            string pythonExe = LocatePythonPath();
            string workingDir = Path.GetDirectoryName(scriptPath) ?? AppContext.BaseDirectory;

            if (File.Exists(pythonExe) && File.Exists(scriptPath))
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = $"\"{scriptPath}\" disconnect",
                    WorkingDirectory = workingDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false
                };

                using var process = Process.Start(startInfo);
                process?.WaitForExit(5000);
            }

            foreach (var proc in Process.GetProcessesByName("pvpn-engine"))
            {
                try { proc.Kill(true); } catch { }
            }

            RestoreWindowsNetworkOnExit();
        }
        catch
        {
            // Best-effort on exit; swallow all exceptions
        }
    }

    private static void RestoreWindowsNetworkOnExit()
    {
        try
        {
            RunSystemCommand("netsh", "interface ipv4 delete route 0.0.0.0/1 awg0 store=active");
            RunSystemCommand("netsh", "interface ipv4 delete route 128.0.0.0/1 awg0 store=active");
            RunSystemCommand("route", "DELETE 10.2.0.1");
            RunSystemCommand("route", "DELETE 0.0.0.0 MASK 128.0.0.0");
            RunSystemCommand("route", "DELETE 128.0.0.0 MASK 128.0.0.0");
            RunSystemCommand("netsh", "interface ipv4 set dnsservers name=awg0 source=dhcp");
            RunSystemCommand("netsh", "advfirewall firewall delete rule name=pvpn-engine");
            RunSystemCommand("powershell", "-NoProfile -Command \"Get-DnsClientNrptRule | Where-Object { $_.Comment -eq 'PVPN-Next' } | Remove-DnsClientNrptRule -ErrorAction SilentlyContinue -Force\"");
            RunSystemCommand("ipconfig", "/flushdns");

            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string routingPath = Path.Combine(appData, "pvpn-next", "routing_state.json");
            if (File.Exists(routingPath))
            {
                File.Delete(routingPath);
            }
        }
        catch { }
    }

    private static void RunSystemCommand(string fileName, string arguments)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            using var p = Process.Start(psi);
            p?.WaitForExit(2000);
        }
        catch { }
    }

    public Task<Result<NetworkTrafficIpcEntity>> GetNetworkTrafficAsync()
    {
        try
        {
            NetworkInterface? vpnInterface = NetworkInterface.GetAllNetworkInterfaces()
                .FirstOrDefault(nic =>
                    nic.OperationalStatus == OperationalStatus.Up &&
                    (nic.Description.Contains("Wintun", StringComparison.OrdinalIgnoreCase) ||
                     nic.Name.Contains("wintun", StringComparison.OrdinalIgnoreCase) ||
                     nic.Description.Contains("Amnezia", StringComparison.OrdinalIgnoreCase) ||
                     nic.Name.Contains("pvpn", StringComparison.OrdinalIgnoreCase)));

            if (vpnInterface != null)
            {
                IPv4InterfaceStatistics stats = vpnInterface.GetIPv4Statistics();
                long currentIn = stats.BytesReceived;
                long currentOut = stats.BytesSent;

                DateTime now = DateTime.UtcNow;
                double seconds = (now - _lastTrafficSampleTime).TotalSeconds;
                if (seconds <= 0) seconds = 1;

                long speedIn = _lastBytesIn > 0 && currentIn >= _lastBytesIn ? (long)((currentIn - _lastBytesIn) / seconds) : 0;
                long speedOut = _lastBytesOut > 0 && currentOut >= _lastBytesOut ? (long)((currentOut - _lastBytesOut) / seconds) : 0;

                _lastBytesIn = currentIn;
                _lastBytesOut = currentOut;
                _lastTrafficSampleTime = now;

                var traffic = new NetworkTrafficIpcEntity
                {
                    BytesDownloaded = (ulong)Math.Max(0, currentIn),
                    BytesUploaded = (ulong)Math.Max(0, currentOut),
                    UtcDate = now
                };

                return Task.FromResult(Result<NetworkTrafficIpcEntity>.Ok(traffic));
            }
        }
        catch
        {
        }

        return Task.FromResult(Result<NetworkTrafficIpcEntity>.Ok(new NetworkTrafficIpcEntity()));
    }

    public Task RequestNetShieldStatsAsync() => Task.CompletedTask;

    public Task RequestConnectionDetailsAsync() => Task.CompletedTask;

    public Task UpdateLocalAgentTlsCredentialsAsync(LocalAgentTlsCredentialsIpcEntity credentials) => Task.CompletedTask;

    public Task ApplySettingsAsync(MainSettingsIpcEntity settings) => Task.CompletedTask;

    public Task RepeatStateAsync()
    {
        if (_isConnecting)
        {
            // Do NOT overwrite connecting state while a connection is in flight
            return Task.CompletedTask;
        }

        bool isActive = IsRoutingStateActive();
        if (isActive)
        {
            var (activeName, activeIp) = ReadRoutingSessionInfo();
            string finalIp = !string.IsNullOrEmpty(activeIp) ? activeIp : (_lastConnectedServerIp ?? "10.2.0.1");
            string finalLabel = !string.IsNullOrEmpty(activeName) ? activeName : (_lastConnectedServerLabel ?? _lastConnectedServerName ?? "Connected");

            _eventMessageSender.Send(new VpnStateIpcEntity
            {
                Status = VpnStatusIpcEntity.Connected,
                EndpointIp = finalIp,
                Label = finalLabel,
                VpnProtocol = _currentProtocol,
                EndpointPort = 51820
            });
        }
        else
        {
            _eventMessageSender.Send(new VpnStateIpcEntity
            {
                Status = VpnStatusIpcEntity.Disconnected
            });
        }

        return Task.CompletedTask;
    }

    public Task RepeatPortForwardingStateAsync() => Task.CompletedTask;

    public static string LocatePythonPath()
    {
        string? envPath = Environment.GetEnvironmentVariable("PYTHON");
        if (!string.IsNullOrEmpty(envPath) && File.Exists(envPath))
        {
            return envPath;
        }

        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string[] candidates = [
            Path.Combine(localAppData, @"Programs\Python\Python311\python.exe"),
            Path.Combine(localAppData, @"Programs\Python\Python312\python.exe"),
            Path.Combine(localAppData, @"Programs\Python\Python310\python.exe"),
            @"C:\Python311\python.exe",
            @"C:\Python312\python.exe",
            @"C:\Program Files\Python311\python.exe",
            @"C:\Program Files\Python312\python.exe"
        ];

        foreach (string candidate in candidates)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return "python.exe";
    }

    public static string LocateCliScriptPath()
    {
        string? envPath = Environment.GetEnvironmentVariable("PVPN_CLI_PATH");
        if (!string.IsNullOrEmpty(envPath) && File.Exists(envPath))
        {
            return envPath;
        }

        // Relative probe paths
        string[] candidates = [
            @"C:\Users\User\Documents\ProtonNext\ProtonVPN-Next-CLI\pvpn-next",
            Path.Combine(AppContext.BaseDirectory, @"..\..\..\..\..\ProtonVPN-Next-CLI\pvpn-next"),
            Path.Combine(AppContext.BaseDirectory, @"ProtonVPN-Next-CLI\pvpn-next"),
            Path.Combine(AppContext.BaseDirectory, "pvpn-next")
        ];

        foreach (string candidate in candidates)
        {
            string fullPath = Path.GetFullPath(candidate);
            if (File.Exists(fullPath))
            {
                return fullPath;
            }
        }

        return @"C:\Users\User\Documents\ProtonNext\ProtonVPN-Next-CLI\pvpn-next";
    }

    private void RunCliCommand(string arguments)
    {
        string scriptPath = LocateCliScriptPath();
        string workingDir = Path.GetDirectoryName(scriptPath) ?? AppContext.BaseDirectory;
        string pythonExe = LocatePythonPath();

        _logger.Info<AppLog>($"[CliVpnServiceCaller] Executing: {pythonExe} \"{scriptPath}\" {arguments}");

        var startInfo = new ProcessStartInfo
        {
            FileName = pythonExe,
            Arguments = $"\"{scriptPath}\" {arguments}",
            WorkingDirectory = workingDir,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };

        using var process = Process.Start(startInfo);
        if (process != null)
        {
            string stdout = process.StandardOutput.ReadToEnd();
            string stderr = process.StandardError.ReadToEnd();
            process.WaitForExit(60000);

            if (!string.IsNullOrWhiteSpace(stdout))
            {
                _logger.Info<AppLog>($"[CLI Out]: {stdout.Trim()}");
            }
            if (!string.IsNullOrWhiteSpace(stderr))
            {
                _logger.Warn<AppLog>($"[CLI Err]: {stderr.Trim()}");
            }
        }
    }

    private static bool IsRoutingStateActive()
    {
        try
        {
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string routingPath = Path.Combine(appData, "pvpn-next", "routing_state.json");
            if (!File.Exists(routingPath))
            {
                return false;
            }

            if (Process.GetProcessesByName("pvpn-engine").Length > 0)
            {
                return true;
            }

            return NetworkInterface.GetAllNetworkInterfaces()
                .Any(nic => nic.OperationalStatus == OperationalStatus.Up &&
                     (nic.Description.Contains("Wintun", StringComparison.OrdinalIgnoreCase) ||
                      nic.Name.Contains("awg0", StringComparison.OrdinalIgnoreCase) ||
                      nic.Name.Contains("wintun", StringComparison.OrdinalIgnoreCase)));
        }
        catch
        {
            return false;
        }
    }

    private static (string? serverName, string? vpnIp) ReadRoutingSessionInfo()
    {
        try
        {
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string routingPath = Path.Combine(appData, "pvpn-next", "routing_state.json");
            if (File.Exists(routingPath))
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(routingPath));
                string? ip = doc.RootElement.TryGetProperty("vpn_ip", out var ipProp) ? ipProp.GetString() : null;
                string? name = doc.RootElement.TryGetProperty("server_name", out var nameProp) ? nameProp.GetString() : null;
                return (name, ip);
            }
        }
        catch
        {
        }
        return (null, null);
    }

    private static bool WaitForTunnelState(bool active, int timeoutSeconds, CancellationToken cancellationToken = default)
    {
        DateTime deadline = DateTime.UtcNow.AddSeconds(timeoutSeconds);
        while (DateTime.UtcNow < deadline)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                return false;
            }

            bool currentActive = IsRoutingStateActive();
            if (currentActive == active)
            {
                return true;
            }
            Thread.Sleep(500);
        }
        return IsRoutingStateActive() == active;
    }
}
