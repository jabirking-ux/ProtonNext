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
using ProtonVPN.OperatingSystems.Services.Contracts;

namespace ProtonVPN.Client.Logic.Services;

public class CliServiceManager : IServiceManager
{
    public ServiceStatus? GetStatus()
    {
        return ServiceStatus.Running;
    }

    public Task StartAsync()
    {
        return Task.CompletedTask;
    }

    public void Stop()
    {
    }
}
