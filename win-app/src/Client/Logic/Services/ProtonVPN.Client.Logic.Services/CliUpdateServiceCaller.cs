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

using System.Threading.Tasks;
using ProtonVPN.Client.Logic.Services.Contracts;
using ProtonVPN.ProcessCommunication.Contracts.Entities.Update;

namespace ProtonVPN.Client.Logic.Services;

public class CliUpdateServiceCaller : IUpdateServiceCaller
{
    public Task CheckForUpdateAsync(UpdateSettingsIpcEntity updateSettingsIpcEntity)
    {
        return Task.CompletedTask;
    }

    public Task StartAutoUpdateAsync()
    {
        return Task.CompletedTask;
    }
}
