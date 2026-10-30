"""Windows split tunneling enforcement.

Why this looks the way it does
------------------------------
*Networks*: every prefix is installed with ``netsh interface ipv4|ipv6 add
route ... store=active``. Two bugs are fixed at once compared to the old
implementation:

* ``route ADD <ip> MASK 255.255.255.255`` was used for every entry, so a CIDR
  block such as ``10.8.0.0/16`` was quietly reduced to one host address.
* ``store=active`` guarantees nothing is written to the registry. Persistent
  entries are precisely why users found dead routes and DNS servers pointing at
  a non-existent ``awg0`` adapter after rebooting, with split tunneling then
  behaving as if it were off.

*Applications*: user-mode WFP cannot redirect a socket to a different
interface -- the bind/connect redirect layers require a kernel callout driver.
So per-application rules are enforced by ``pvpn-split.exe``, a helper built on
WinDivert that rewrites the source address of the selected applications' flows
and reinjects them on the other interface. When WinDivert is unavailable the
helper is skipped and the caller is told, instead of pretending it worked.
"""

from __future__ import annotations

import ipaddress
import json
import os
import subprocess
import time
from typing import Optional

from pvpn_cli.cli.config import get_base_dir, get_config_dir
from pvpn_cli.split import model
from pvpn_cli.split.model import Targets

CREATE_NO_WINDOW = 0x08000000
SPLITTER_NAME = "pvpn-split.exe"
SPLITTER_PID_FILE = "split-helper.pid"
ROUTE_METRIC = "1"


def splitter_path() -> str:
    return os.path.abspath(os.path.join(get_base_dir(), "engine", SPLITTER_NAME))


def windivert_present() -> bool:
    engine = os.path.join(get_base_dir(), "engine")
    return os.path.exists(os.path.join(engine, "WinDivert.dll")) and os.path.exists(
        os.path.join(engine, "WinDivert64.sys")
    )


class WindowsSplitBackend:
    """Applies and removes the Windows side of split tunneling."""

    def __init__(self, log=None):
        self._log = log or (lambda message: None)

    # ------------------------------------------------------------------ #
    # Process helpers
    # ------------------------------------------------------------------ #

    def _run(self, args, quiet: bool = False) -> int:
        try:
            completed = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, ValueError) as exc:
            if not quiet:
                self._log(f"[split] cannot run {args[0]}: {exc}")
            return 127
        if completed.returncode != 0 and not quiet:
            output = (completed.stdout or "").strip().replace("\n", " ")
            self._log(f"[split] {' '.join(args)} -> {completed.returncode} {output}")
        return completed.returncode

    def _powershell(self, script: str) -> str:
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=20,
            )
            return (completed.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    # ------------------------------------------------------------------ #
    # Environment discovery
    # ------------------------------------------------------------------ #

    def physical_link(self, tunnel_alias: str = "awg0") -> dict:
        """Describe the physical default route: gateway, index, local address.

        Looked up fresh on every apply and re-checked by the agent, so switching
        from Wi-Fi to Ethernet no longer leaves the exclusions pointing at a
        gateway that has gone away.
        """
        script = (
            "$r = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |"
            f" Where-Object {{ $_.InterfaceAlias -ne '{tunnel_alias}' }} |"
            " Sort-Object -Property RouteMetric,ifMetric | Select-Object -First 1;"
            "if ($null -eq $r) { '{}' } else {"
            "  $a = Get-NetIPAddress -InterfaceIndex $r.InterfaceIndex -AddressFamily IPv4"
            "    -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -ne '127.0.0.1' } |"
            "    Select-Object -First 1;"
            "  $r6 = Get-NetRoute -DestinationPrefix '::/0' -ErrorAction SilentlyContinue |"
            f"    Where-Object {{ $_.InterfaceAlias -ne '{tunnel_alias}' }} |"
            "    Sort-Object -Property RouteMetric,ifMetric | Select-Object -First 1;"
            "  [pscustomobject]@{ index = $r.InterfaceIndex; alias = $r.InterfaceAlias;"
            "    gateway = $r.NextHop; address = $a.IPAddress;"
            "    index6 = $r6.InterfaceIndex; gateway6 = $r6.NextHop } | ConvertTo-Json -Compress }"
        )
        raw = self._powershell(script)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    def tunnel_link(self, tunnel_alias: str = "awg0") -> dict:
        script = (
            f"$i = Get-NetIPInterface -InterfaceAlias '{tunnel_alias}' -AddressFamily IPv4"
            " -ErrorAction SilentlyContinue | Select-Object -First 1;"
            "if ($null -eq $i) { '{}' } else {"
            "  $a = Get-NetIPAddress -InterfaceIndex $i.InterfaceIndex -AddressFamily IPv4"
            "    -ErrorAction SilentlyContinue | Select-Object -First 1;"
            "  [pscustomobject]@{ index = $i.InterfaceIndex; address = $a.IPAddress }"
            "    | ConvertTo-Json -Compress }"
        )
        raw = self._powershell(script)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #

    def _route_command(
        self, action: str, network: str, interface_index, gateway: Optional[str]
    ) -> list:
        parsed = ipaddress.ip_network(network, strict=False)
        family = "ipv4" if parsed.version == 4 else "ipv6"
        command = [
            "netsh",
            "interface",
            family,
            action,
            "route",
            f"prefix={parsed.with_prefixlen}",
            f"interface={interface_index}",
        ]
        if action == "add":
            unspecified = "0.0.0.0" if parsed.version == 4 else "::"
            command.append(f"nexthop={gateway or unspecified}")
            command.append(f"metric={ROUTE_METRIC}")
            command.append("store=active")
        else:
            command.append("store=active")
        return command

    def add_route(self, network: str, interface_index, gateway: Optional[str]) -> bool:
        if interface_index in (None, ""):
            return False
        self._run(self._route_command("delete", network, interface_index, gateway), quiet=True)
        return self._run(self._route_command("add", network, interface_index, gateway)) == 0

    def delete_route(self, network: str, interface_index, gateway: Optional[str] = None) -> None:
        if interface_index in (None, ""):
            return
        self._run(self._route_command("delete", network, interface_index, gateway), quiet=True)

    # ------------------------------------------------------------------ #
    # Application helper
    # ------------------------------------------------------------------ #

    def _pid_file(self) -> str:
        return os.path.join(get_config_dir(), SPLITTER_PID_FILE)

    def start_helper(self, state: dict, targets: Targets) -> Optional[int]:
        """Start ``pvpn-split.exe`` for per-application rules."""
        binary = splitter_path()
        if not os.path.exists(binary):
            targets.warnings.append(
                "The per-application helper (pvpn-split.exe) is missing from this "
                "installation, so application rules cannot be enforced."
            )
            return None
        if not windivert_present():
            targets.warnings.append(
                "WinDivert (WinDivert.dll and WinDivert64.sys) was not found next to "
                "the helper, so application rules cannot be enforced."
            )
            return None
        if not state.get("tunnel_index") or not state.get("tunnel_ip4"):
            targets.warnings.append(
                "The tunnel adapter was not ready, so application rules were skipped."
            )
            return None
        if not state.get("interface4") or not state.get("address4"):
            targets.warnings.append(
                "No physical network adapter was found, so application rules were skipped."
            )
            return None

        self.stop_helper()
        arguments = [
            binary,
            "-mode",
            targets.mode,
            "-tun-ip",
            str(state["tunnel_ip4"]),
            "-tun-if",
            str(state["tunnel_index"]),
            "-phys-ip",
            str(state["address4"]),
            "-phys-if",
            str(state["interface4"]),
            "-apps",
            ";".join(targets.apps),
            "-log",
            os.path.join(get_config_dir(), "split-helper.log"),
        ]
        try:
            process = subprocess.Popen(
                arguments,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            targets.warnings.append(f"The per-application helper failed to start: {exc}")
            return None

        time.sleep(0.6)
        if process.poll() is not None:
            targets.warnings.append(
                "The per-application helper exited immediately; see split-helper.log. "
                "This usually means the WinDivert driver could not be loaded."
            )
            return None
        try:
            with open(self._pid_file(), "w", encoding="utf-8") as handle:
                handle.write(str(process.pid))
        except OSError:
            pass
        return process.pid

    def helper_running(self, pid: Optional[int] = None) -> bool:
        if pid is None:
            try:
                with open(self._pid_file(), "r", encoding="utf-8") as handle:
                    pid = int(handle.read().strip())
            except (OSError, ValueError):
                return False
        try:
            import psutil

            process = psutil.Process(pid)
            return process.is_running() and SPLITTER_NAME.lower() in (
                process.name() or ""
            ).lower()
        except Exception:
            return False

    def stop_helper(self) -> None:
        path = self._pid_file()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                pid = int(handle.read().strip())
            self._run(["taskkill", "/PID", str(pid), "/F"], quiet=True)
        except (OSError, ValueError):
            pass
        # Catch orphans from an earlier crash as well.
        self._run(["taskkill", "/IM", SPLITTER_NAME, "/F"], quiet=True)
        try:
            os.remove(path)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def apply(
        self,
        targets: Targets,
        tunnel_interface: str = "awg0",
        tunnel_ip4: Optional[str] = None,
        tunnel_ip6: Optional[str] = None,
        gateway4: Optional[str] = None,
        interface4: Optional[str] = None,
        gateway6: Optional[str] = None,
        interface6: Optional[str] = None,
    ) -> dict:
        physical = self.physical_link(tunnel_interface)
        tunnel = self.tunnel_link(tunnel_interface)

        state = {
            "platform": "windows",
            "mode": targets.mode,
            "tunnel_interface": tunnel_interface,
            "tunnel_index": tunnel.get("index"),
            "tunnel_ip4": tunnel_ip4 or tunnel.get("address"),
            "tunnel_ip6": tunnel_ip6,
            "interface4": interface4 or physical.get("index"),
            "gateway4": gateway4 or physical.get("gateway"),
            "address4": physical.get("address"),
            "interface6": interface6 or physical.get("index6"),
            "gateway6": gateway6 or physical.get("gateway6"),
            "alias": physical.get("alias"),
            "networks": [],
            "apps": list(targets.apps),
            "domains": list(targets.domains),
            "helper_pid": None,
        }

        via_tunnel = not targets.is_exclude
        for network in list(targets.v4) + list(targets.v6):
            parsed = ipaddress.ip_network(network, strict=False)
            if via_tunnel:
                index = state["tunnel_index"]
                gateway = None
            elif parsed.version == 4:
                index = state["interface4"]
                gateway = state["gateway4"]
            else:
                index = state["interface6"]
                gateway = state["gateway6"]
            if self.add_route(network, index, gateway):
                state["networks"].append(network)

        if targets.apps:
            state["helper_pid"] = self.start_helper(state, targets)

        model.write_state(state)
        return state

    def refresh_networks(self, state: dict, networks: list) -> dict:
        wanted = list(dict.fromkeys(networks))
        current = list(state.get("networks", []))
        via_tunnel = state.get("mode") != model.MODE_EXCLUDE

        for network in [item for item in current if item not in wanted]:
            parsed = ipaddress.ip_network(network, strict=False)
            index = (
                state.get("tunnel_index")
                if via_tunnel
                else state.get("interface4" if parsed.version == 4 else "interface6")
            )
            self.delete_route(network, index)
            current.remove(network)
        for network in [item for item in wanted if item not in current]:
            parsed = ipaddress.ip_network(network, strict=False)
            if via_tunnel:
                index, gateway = state.get("tunnel_index"), None
            elif parsed.version == 4:
                index, gateway = state.get("interface4"), state.get("gateway4")
            else:
                index, gateway = state.get("interface6"), state.get("gateway6")
            if self.add_route(network, index, gateway):
                current.append(network)

        state["networks"] = current
        model.write_state(state)
        return state

    def teardown(self, state: Optional[dict] = None) -> None:
        state = model.read_state() if state is None else state
        via_tunnel = state.get("mode") != model.MODE_EXCLUDE
        for network in state.get("networks", []):
            try:
                parsed = ipaddress.ip_network(network, strict=False)
            except ValueError:
                continue
            for index in {
                state.get("tunnel_index") if via_tunnel else None,
                state.get("interface4" if parsed.version == 4 else "interface6"),
            }:
                if index:
                    self.delete_route(network, index)
        self.stop_helper()
        model.clear_state()

    def purge_persistent_artifacts(self) -> None:
        """Delete anything an earlier build may have made survive a reboot.

        Persistent IPv6 routes and DNS server entries on the tunnel adapter are
        the concrete reason split tunneling came back dead after a restart: the
        adapter no longer exists, but its registry configuration does.
        """
        self._powershell(
            "Get-NetRoute -PolicyStore PersistentStore -ErrorAction SilentlyContinue |"
            " Where-Object { $_.InterfaceAlias -like 'awg*' -or"
            "   $_.InterfaceAlias -like '*ProtonVPN-Next*' } |"
            " Remove-NetRoute -PolicyStore PersistentStore -Confirm:$false"
            " -ErrorAction SilentlyContinue"
        )
        self._powershell(
            "Get-DnsClientNrptRule -ErrorAction SilentlyContinue |"
            " Where-Object { $_.Comment -eq 'PVPN-Next' } |"
            " Remove-DnsClientNrptRule -Force -ErrorAction SilentlyContinue"
        )

    def health(self, state: Optional[dict] = None) -> dict:
        state = model.read_state() if state is None else state
        physical = self.physical_link(state.get("tunnel_interface", "awg0"))
        routes = self._powershell(
            "(Get-NetRoute -ErrorAction SilentlyContinue |"
            " ForEach-Object { $_.DestinationPrefix }) -join ' '"
        )
        missing = [
            network
            for network in state.get("networks", [])
            if ipaddress.ip_network(network, strict=False).with_prefixlen not in routes
        ]
        return {
            "helper_running": self.helper_running(),
            "helper_expected": bool(state.get("apps")),
            "missing_networks": missing,
            "gateway_changed": bool(physical)
            and bool(state.get("networks") or state.get("apps"))
            and (
                str(physical.get("index")) != str(state.get("interface4"))
                or physical.get("gateway") != state.get("gateway4")
            ),
            "gateway4": physical.get("gateway"),
            "interface4": physical.get("index"),
            "address4": physical.get("address"),
        }
