/*
 * Copyright (c) 2024 Proton AG
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

namespace ProtonVPN.Client.Logic.Users.Contracts.Messages;

public readonly struct VpnPlan
{
    public static VpnPlan Default => new("Proton Unlimited", "bundle2022", 0, false);

    public string Title { get; }
    public string Name { get; }
    public bool IsPaid => true;
    public sbyte MaxTier => 0;
    public bool IsB2B { get; }

    public VpnPlan(string title, string name, sbyte maxTier, bool isB2B)
    {
        Title = string.IsNullOrWhiteSpace(title) ? "Proton Unlimited" : title;
        Name = string.IsNullOrWhiteSpace(name) ? "bundle2022" : name;
        IsB2B = isB2B;
    }

    public bool IsDefaultPlan => false;

    public bool IsFreePlan => false;

    public bool IsVpnPlan => false;

    public bool IsProtonPlan => true;

    public bool IsPaidB2CPlan => true;
}
