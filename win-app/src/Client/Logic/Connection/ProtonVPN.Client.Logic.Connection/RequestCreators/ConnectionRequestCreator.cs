/*
 * Copyright (c) 2026 Proton AG
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

using ProtonVPN.Client.Logic.Auth.Contracts;
using ProtonVPN.Client.Logic.Auth.Contracts.Models;
using ProtonVPN.Client.Logic.Connection.Contracts.Models.Intents;
using ProtonVPN.Client.Logic.Connection.Contracts.RequestCreators;
using ProtonVPN.Client.Logic.Connection.Contracts.ServerListGenerators;
using ProtonVPN.Client.Logic.Servers.Contracts.Models;
using ProtonVPN.Client.Settings.Contracts;
using ProtonVPN.Client.Settings.Contracts.Observers;
using ProtonVPN.Common.Core.Networking;
using ProtonVPN.Common.Legacy.Vpn;
using ProtonVPN.Crypto.Contracts;
using ProtonVPN.EntityMapping.Contracts;
using ProtonVPN.Logging.Contracts;
using ProtonVPN.Logging.Contracts.Events.UserCertificateLogs;
using ProtonVPN.ProcessCommunication.Contracts.Entities.Crypto;
using ProtonVPN.ProcessCommunication.Contracts.Entities.LocalAgent;
using ProtonVPN.ProcessCommunication.Contracts.Entities.Settings;
using ProtonVPN.ProcessCommunication.Contracts.Entities.Vpn;

namespace ProtonVPN.Client.Logic.Connection.RequestCreators;

public class ConnectionRequestCreator : ConnectionRequestCreatorBase, IConnectionRequestCreator
{
    protected readonly IServerListGenerator ServerListGenerator;
    protected readonly ISmartServerListGenerator SmartServerListGenerator;

    private readonly IConnectionKeyManager _connectionKeyManager;
    private readonly IConnectionCertificateManager _connectionCertificateManager;

    public ConnectionRequestCreator(
        ILogger logger,
        ISettings settings,
        IEntityMapper entityMapper,
        IConnectionKeyManager connectionKeyManager,
        IConnectionCertificateManager connectionCertificateManager,
        IServerListGenerator serverListGenerator,
        ISmartServerListGenerator smartServerListGenerator,
        IFeatureFlagsObserver featureFlagsObserver,
        IMainSettingsRequestCreator mainSettingsRequestCreator)
        : base(logger, settings, entityMapper, featureFlagsObserver, mainSettingsRequestCreator)
    {
        ServerListGenerator = serverListGenerator;
        SmartServerListGenerator = smartServerListGenerator;

        _connectionKeyManager = connectionKeyManager;
        _connectionCertificateManager = connectionCertificateManager;
    }

    public virtual async Task<ConnectionRequestIpcEntity> CreateAsync(IConnectionIntent connectionIntent)
    {
        MainSettingsIpcEntity settings = GetSettings(connectionIntent);
        VpnConfigIpcEntity config = GetVpnConfig(settings, connectionIntent);
        List<VpnProtocol> preferredProtocols = EntityMapper.Map<VpnProtocolIpcEntity, VpnProtocol>(config.PreferredProtocols);
        ServerListResult serverListResult = GetServerListResult(connectionIntent, preferredProtocols);
        VpnServerIpcEntity[] servers = PhysicalServersToVpnServerIpcEntities(serverListResult.PhysicalServers);
        TagServersWithIntent(servers, connectionIntent);
        bool areAllServersExcluded = servers.Length == 0 && serverListResult.Diagnostic.AreAllCandidatesExcluded;

        ConnectionRequestIpcEntity request = new()
        {
            RetryId = Guid.NewGuid(),
            Config = config,
            Credentials = await GetVpnCredentialsAsync(),
            Protocol = settings.VpnProtocol,
            Servers = servers,
            Settings = settings,
            AreAllServersExcludedByUserPreference = areAllServersExcluded,
        };

        return request;
    }

    protected ServerListResult GetServerListResult(IConnectionIntent connectionIntent, IList<VpnProtocol> preferredProtocols)
    {
        return IsToBypassSmartServerListGenerator(connectionIntent)
            ? ServerListGenerator.Generate(connectionIntent, preferredProtocols)
            : SmartServerListGenerator.Generate(connectionIntent, preferredProtocols);
    }

    protected override async Task<VpnCredentialsIpcEntity> GetVpnCredentialsAsync()
    {
        await RequestCertificateIfNecessaryAsync();

        ConnectionCertificate? connectionCertificate = Settings.ConnectionCertificate;
        AsymmetricKeyPair? keyPair = _connectionKeyManager.GetKeyPairOrNull();

        return new VpnCredentialsIpcEntity
        {
            Certificate = connectionCertificate.HasValue ? CreateCertificate(connectionCertificate.Value) : null,
            ClientKeyPair = keyPair is null ? null : new AsymmetricKeyPairIpcEntity
            {
                PublicKey = EntityMapper.Map<PublicKey, PublicKeyIpcEntity>(keyPair.PublicKey),
                SecretKey = EntityMapper.Map<SecretKey, SecretKeyIpcEntity>(keyPair.SecretKey)
            }
        };
    }

    private async Task RequestCertificateIfNecessaryAsync()
    {
        if (_connectionKeyManager.GetKeyPairOrNull() is null)
        {
            Logger.Info<UserCertificateLog>("Connection keys are missing, forcing new keys and certificate.");
            await _connectionCertificateManager.ForceRequestNewKeyPairAndCertificateAsync();
        }
        else
        {
            ConnectionCertificate? connectionCertificate = Settings.ConnectionCertificate;

            if (connectionCertificate is null)
            {
                Logger.Info<UserCertificateLog>("Connection certificate is missing, requesting a new certificate.");
                await _connectionCertificateManager.RequestNewCertificateAsync();
            }
            else if (connectionCertificate.Value.ExpirationUtcDate <= DateTimeOffset.UtcNow)
            {
                Logger.Info<UserCertificateLog>("Connection certificate is expired, requesting a new certificate.");
                await _connectionCertificateManager.RequestNewCertificateAsync();
            }
        }
    }

    private ConnectionCertificateIpcEntity CreateCertificate(ConnectionCertificate connectionCertificate)
    {
        return new()
        {
            Pem = connectionCertificate.Pem,
            ExpirationDateUtc = connectionCertificate.ExpirationUtcDate.UtcDateTime,
        };
    }

    protected VpnServerIpcEntity[] PhysicalServersToVpnServerIpcEntities(IEnumerable<PhysicalServer> physicalServers)
    {
        var validHosts = new List<VpnHost>();
        if (physicalServers != null)
        {
            foreach (PhysicalServer s in physicalServers)
            {
                if (s == null) continue;
                try
                {
                    string domain = !string.IsNullOrWhiteSpace(s.Domain) ? s.Domain : (!string.IsNullOrWhiteSpace(s.EntryIp) ? s.EntryIp : "node.protonvpn.net");
                    string ip = !string.IsNullOrWhiteSpace(s.EntryIp) ? s.EntryIp : "10.2.0.1";
                    string label = !string.IsNullOrWhiteSpace(s.Label) ? s.Label : domain;
                    validHosts.Add(new VpnHost(domain, ip, label, GetServerPublicKey(s), s.Signature, s.IsIpv6Supported, s.RelayIpByProtocol));
                }
                catch
                {
                    // Ignore invalid physical server candidate
                }
            }
        }
        return EntityMapper.Map<VpnHost, VpnServerIpcEntity>(validHosts).ToArray();
    }

    protected PublicKey? GetServerPublicKey(PhysicalServer server)
    {
        return string.IsNullOrEmpty(server.X25519PublicKey)
            ? null
            : new PublicKey(server.X25519PublicKey, KeyAlgorithm.X25519);
    }
    protected void TagServersWithIntent(VpnServerIpcEntity[] servers, IConnectionIntent connectionIntent)
    {
        if (servers == null || servers.Length == 0) return;

        string target = "fastest";
        if (connectionIntent.Location is ProtonVPN.Client.Logic.Connection.Contracts.Models.Intents.Locations.Servers.SingleServerLocationIntent ss && !string.IsNullOrWhiteSpace(ss.Server.Name))
        {
            target = ss.Server.Name;
        }
        else if (connectionIntent.Location is ProtonVPN.Client.Logic.Connection.Contracts.Models.Intents.Locations.Countries.SingleCountryLocationIntent sc && !string.IsNullOrWhiteSpace(sc.CountryCode))
        {
            target = sc.CountryCode;
        }
        else if (connectionIntent.Location is ProtonVPN.Client.Logic.Connection.Contracts.Models.Intents.Locations.Cities.CityLocationIntentBase city && !string.IsNullOrWhiteSpace(city.Country?.CountryCode))
        {
            target = city.Country.CountryCode;
        }
        else if (connectionIntent.Location is ProtonVPN.Client.Logic.Connection.Contracts.Models.Intents.Locations.States.StateLocationIntentBase state && !string.IsNullOrWhiteSpace(state.Country?.CountryCode))
        {
            target = state.Country.CountryCode;
        }
        else if (connectionIntent.Location is ProtonVPN.Client.Logic.Connection.Contracts.Models.Intents.Locations.FreeServers.FreeServerLocationIntent freeIntent)
        {
            if (freeIntent.Strategy == ProtonVPN.Client.Logic.Connection.Contracts.Enums.SelectionStrategy.Random || freeIntent.ServerToExclude != null)
            {
                string exclude = freeIntent.ServerToExclude?.Name ?? string.Empty;
                target = string.IsNullOrEmpty(exclude) ? "rotate" : $"rotate:{exclude}";
            }
            else
            {
                target = "fastest";
            }
        }

        foreach (var s in servers)
        {
            s.Label = target;
        }
    }
}
