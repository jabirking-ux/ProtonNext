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

using ProtonVPN.Client.Logic.Services.Contracts;
using ProtonVPN.Logging.Contracts;
using ProtonVPN.Logging.Contracts.Events.AppLogs;

namespace ProtonVPN.Client.Logic.Services;

public class CliProcessCommunicationStarter : IProcessCommunicationStarter
{
    private readonly ILogger _logger;

    public CliProcessCommunicationStarter(ILogger logger)
    {
        _logger = logger;
    }

    public void Start()
    {
        _logger.Info<AppLog>("[CliProcessCommunicationStarter] Initialized PVPN-Next CLI integration.");
    }
}
