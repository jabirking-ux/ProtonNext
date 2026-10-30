"""Linux split tunneling enforcement.

Design notes
------------
*Networks* are handled with plain routes in the main table, so every process
bypasses (exclude mode) or uses (include mode) the tunnel for those prefixes.
Both address families are handled; the old code only ever touched IPv4.

*Applications* are handled with a cgroup v2 directory plus a mangle rule that
marks every packet leaving a socket owned by that cgroup, and an ``ip rule``
that sends marked packets to a private routing table. nftables is preferred and
iptables is only used as a fallback, because ``iptables -m cgroup`` is simply
not available on a growing number of nft-only systems -- that was one reason
app exclusions "did nothing" for some users.

Every object this module creates has a fixed, well-known name so that a
teardown after a crash or a reboot can find and remove it without needing a
state file that may be gone.
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess
from typing import Optional

from pvpn_cli.split import model
from pvpn_cli.split.model import (
    CGROUP_NAME,
    CGROUP_ROOT,
    FWMARK,
    NFT_TABLE,
    ROUTE_TABLE_BYPASS,
    ROUTE_TABLE_TUNNEL,
    RULE_PRIORITY,
    Targets,
)

MARK_HEX = hex(FWMARK)
CGROUP_PATH = os.path.join(CGROUP_ROOT, CGROUP_NAME)


class LinuxSplitBackend:
    """Applies and removes the Linux side of split tunneling."""

    def __init__(self, log=None):
        self._log = log or (lambda message: None)
        self._nft = shutil.which("nft")
        self._iptables = shutil.which("iptables")
        self._ip6tables = shutil.which("ip6tables")

    # ------------------------------------------------------------------ #
    # Process helpers
    # ------------------------------------------------------------------ #

    def _run(self, args, check: bool = False, quiet: bool = False) -> int:
        try:
            completed = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except (OSError, ValueError) as exc:
            if not quiet:
                self._log(f"[split] cannot run {args[0]}: {exc}")
            if check:
                raise
            return 127
        if completed.returncode != 0 and not quiet:
            output = (completed.stdout or "").strip().replace("\n", " ")
            self._log(f"[split] {' '.join(args)} -> {completed.returncode} {output}")
        if completed.returncode != 0 and check:
            raise RuntimeError(f"{' '.join(args)} failed: {completed.stdout}")
        return completed.returncode

    def _capture(self, args) -> str:
        try:
            completed = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            return completed.stdout or ""
        except OSError:
            return ""

    # ------------------------------------------------------------------ #
    # Environment discovery
    # ------------------------------------------------------------------ #

    def default_gateway(self, family: int = 4) -> tuple:
        """Return ``(gateway, interface)`` for the current physical default.

        Re-read rather than cached, because roaming between Wi-Fi networks used
        to leave every exclusion route pointing at a gateway that no longer
        existed, which looks exactly like "split tunneling stopped working".
        """
        flag = "-4" if family == 4 else "-6"
        output = self._capture(["ip", flag, "route", "show", "default"])
        for line in output.splitlines():
            parts = line.split()
            if "dev" not in parts:
                continue
            interface = parts[parts.index("dev") + 1]
            if interface.startswith("awg") or interface.startswith("wg"):
                continue
            gateway = parts[parts.index("via") + 1] if "via" in parts else None
            return gateway, interface
        return None, None

    def cgroup_available(self) -> bool:
        return os.path.isdir(CGROUP_ROOT) and os.path.exists(
            os.path.join(CGROUP_ROOT, "cgroup.controllers")
        )

    # ------------------------------------------------------------------ #
    # cgroup
    # ------------------------------------------------------------------ #

    def ensure_cgroup(self) -> bool:
        if not self.cgroup_available():
            self._log("[split] cgroup v2 is not mounted; app rules unavailable")
            return False
        try:
            os.makedirs(CGROUP_PATH, exist_ok=True)
        except OSError as exc:
            self._log(f"[split] cannot create {CGROUP_PATH}: {exc}")
            return False
        return True

    def attach_pid(self, pid: int) -> bool:
        """Move one process into the split cgroup.

        Children inherit the cgroup automatically, which is why the agent only
        has to catch the moment a process appears rather than track whole trees.
        """
        try:
            with open(os.path.join(CGROUP_PATH, "cgroup.procs"), "w") as handle:
                handle.write(str(int(pid)))
            return True
        except OSError:
            return False

    def cgroup_pids(self) -> list:
        try:
            with open(os.path.join(CGROUP_PATH, "cgroup.procs"), "r") as handle:
                return [int(line) for line in handle.read().split() if line.isdigit()]
        except OSError:
            return []

    def release_cgroup(self) -> None:
        """Evacuate and delete the cgroup; a populated cgroup cannot be removed."""
        root_procs = os.path.join(CGROUP_ROOT, "cgroup.procs")
        for pid in self.cgroup_pids():
            try:
                with open(root_procs, "w") as handle:
                    handle.write(str(pid))
            except OSError:
                pass
        try:
            os.rmdir(CGROUP_PATH)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Packet marking
    # ------------------------------------------------------------------ #

    def _install_nft_mark(self) -> bool:
        if not self._nft:
            return False
        self._run([self._nft, "delete", "table", "inet", NFT_TABLE], quiet=True)
        script = (
            f"add table inet {NFT_TABLE}; "
            f"add chain inet {NFT_TABLE} output "
            "{ type route hook output priority mangle; policy accept; }; "
            f'add rule inet {NFT_TABLE} output socket cgroupv2 level 1 "{CGROUP_NAME}" '
            f"meta mark set {MARK_HEX}; "
        )
        try:
            completed = subprocess.run(
                [self._nft, "-f", "-"],
                input=script,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError:
            return False
        if completed.returncode != 0:
            self._log(
                "[split] nftables cgroup matching unavailable: "
                f"{(completed.stdout or '').strip()}"
            )
            self._run([self._nft, "delete", "table", "inet", NFT_TABLE], quiet=True)
            return False
        return True

    def _install_iptables_mark(self) -> bool:
        installed = False
        for binary in (self._iptables, self._ip6tables):
            if not binary:
                continue
            arguments = [
                "-t",
                "mangle",
                "OUTPUT",
                "-m",
                "cgroup",
                "--path",
                CGROUP_NAME,
                "-j",
                "MARK",
                "--set-mark",
                MARK_HEX,
            ]
            self._run([binary] + ["-t", "mangle", "-D", "OUTPUT"] + arguments[3:], quiet=True)
            if self._run([binary, "-t", "mangle", "-A"] + arguments[2:], quiet=True) == 0:
                installed = True
        return installed

    def _remove_marking(self) -> None:
        if self._nft:
            self._run([self._nft, "delete", "table", "inet", NFT_TABLE], quiet=True)
        for binary in (self._iptables, self._ip6tables):
            if not binary:
                continue
            for _ in range(4):
                if (
                    self._run(
                        [
                            binary,
                            "-t",
                            "mangle",
                            "-D",
                            "OUTPUT",
                            "-m",
                            "cgroup",
                            "--path",
                            CGROUP_NAME,
                            "-j",
                            "MARK",
                            "--set-mark",
                            MARK_HEX,
                        ],
                        quiet=True,
                    )
                    != 0
                ):
                    break

    def install_marking(self) -> Optional[str]:
        """Install the cgroup mangle rule; returns the mechanism used."""
        if self._install_nft_mark():
            return "nftables"
        if self._install_iptables_mark():
            return "iptables"
        self._log("[split] no usable packet marking backend for app rules")
        return None

    # ------------------------------------------------------------------ #
    # Policy routing
    # ------------------------------------------------------------------ #

    def _rule_args(self, family: int, table: int) -> list:
        flag = "-4" if family == 4 else "-6"
        return [
            "ip",
            flag,
            "rule",
            "add",
            "fwmark",
            MARK_HEX,
            "lookup",
            str(table),
            "priority",
            str(RULE_PRIORITY),
        ]

    def _install_rule(self, family: int, table: int) -> None:
        self._delete_rules(family)
        self._run(self._rule_args(family, table), quiet=True)

    def _delete_rules(self, family: int) -> None:
        flag = "-4" if family == 4 else "-6"
        for _ in range(6):
            if (
                self._run(
                    ["ip", flag, "rule", "del", "priority", str(RULE_PRIORITY)], quiet=True
                )
                != 0
            ):
                break

    def _fill_bypass_table(self, family: int, gateway, interface) -> None:
        flag = "-4" if family == 4 else "-6"
        table = str(ROUTE_TABLE_BYPASS)
        self._run(["ip", flag, "route", "flush", "table", table], quiet=True)
        if not interface:
            return
        if gateway:
            self._run(
                ["ip", flag, "route", "replace", gateway, "dev", interface, "scope", "link",
                 "table", table],
                quiet=True,
            )
            self._run(
                ["ip", flag, "route", "replace", "default", "via", gateway, "dev",
                 interface, "table", table],
                quiet=True,
            )
        else:
            self._run(
                ["ip", flag, "route", "replace", "default", "dev", interface, "table", table],
                quiet=True,
            )

    def _fill_tunnel_table(self, family: int, tunnel_interface, source) -> None:
        flag = "-4" if family == 4 else "-6"
        table = str(ROUTE_TABLE_TUNNEL)
        self._run(["ip", flag, "route", "flush", "table", table], quiet=True)
        if not tunnel_interface:
            return
        command = ["ip", flag, "route", "replace", "default", "dev", tunnel_interface]
        if source:
            command += ["src", source]
        command += ["table", table]
        self._run(command, quiet=True)

    def _network_route(
        self, network: str, via_tunnel: bool, tunnel_interface, gateway, interface
    ) -> bool:
        family = ipaddress.ip_network(network, strict=False).version
        flag = "-4" if family == 4 else "-6"
        if via_tunnel:
            if not tunnel_interface:
                return False
            command = ["ip", flag, "route", "replace", network, "dev", tunnel_interface]
        elif gateway:
            command = [
                "ip", flag, "route", "replace", network, "via", gateway, "dev", interface,
            ]
        elif interface:
            command = ["ip", flag, "route", "replace", network, "dev", interface]
        else:
            return False
        return self._run(command, quiet=True) == 0

    def _delete_network_route(self, network: str) -> None:
        family = ipaddress.ip_network(network, strict=False).version
        flag = "-4" if family == 4 else "-6"
        self._run(["ip", flag, "route", "del", network], quiet=True)

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def apply(
        self,
        targets: Targets,
        tunnel_interface: str,
        tunnel_ip4: Optional[str] = None,
        tunnel_ip6: Optional[str] = None,
        gateway4: Optional[str] = None,
        interface4: Optional[str] = None,
        gateway6: Optional[str] = None,
        interface6: Optional[str] = None,
    ) -> dict:
        """Enforce ``targets`` and return the state needed to undo it."""
        if gateway4 is None and interface4 is None:
            gateway4, interface4 = self.default_gateway(4)
        if gateway6 is None and interface6 is None:
            gateway6, interface6 = self.default_gateway(6)

        state = {
            "platform": "linux",
            "mode": targets.mode,
            "tunnel_interface": tunnel_interface,
            "tunnel_ip4": tunnel_ip4,
            "tunnel_ip6": tunnel_ip6,
            "gateway4": gateway4,
            "interface4": interface4,
            "gateway6": gateway6,
            "interface6": interface6,
            "networks": [],
            "apps": list(targets.apps),
            "domains": list(targets.domains),
            "marking": None,
            "cgroup": False,
        }

        via_tunnel = not targets.is_exclude
        for network in list(targets.v4) + list(targets.v6):
            family = ipaddress.ip_network(network, strict=False).version
            gateway = gateway4 if family == 4 else gateway6
            interface = interface4 if family == 4 else interface6
            if self._network_route(
                network, via_tunnel, tunnel_interface, gateway, interface
            ):
                state["networks"].append(network)

        if targets.apps:
            if self.ensure_cgroup():
                state["cgroup"] = True
                state["marking"] = self.install_marking()
                if state["marking"]:
                    if via_tunnel:
                        self._fill_tunnel_table(4, tunnel_interface, tunnel_ip4)
                        self._fill_tunnel_table(6, tunnel_interface, tunnel_ip6)
                        table = ROUTE_TABLE_TUNNEL
                    else:
                        self._fill_bypass_table(4, gateway4, interface4)
                        self._fill_bypass_table(6, gateway6, interface6)
                        table = ROUTE_TABLE_BYPASS
                    self._install_rule(4, table)
                    if interface6 or via_tunnel:
                        self._install_rule(6, table)
                    # Marked packets leave with a source address that does not
                    # belong to the incoming interface's subnet during the reply
                    # path check, so loosen strict reverse-path filtering.
                    self._run(
                        ["sysctl", "-q", "-w", "net.ipv4.conf.all.rp_filter=2"], quiet=True
                    )
                else:
                    targets.warnings.append(
                        "Per-application rules need nftables with cgroupv2 socket "
                        "matching or iptables with the cgroup match."
                    )
            else:
                targets.warnings.append(
                    "Per-application rules need a mounted cgroup v2 hierarchy."
                )

        model.write_state(state)
        return state

    def refresh_networks(self, state: dict, networks: list) -> dict:
        """Apply a new set of prefixes (domain re-resolution, roaming)."""
        wanted = list(dict.fromkeys(networks))
        current = list(state.get("networks", []))
        via_tunnel = state.get("mode") != model.MODE_EXCLUDE

        for network in [item for item in current if item not in wanted]:
            self._delete_network_route(network)
            current.remove(network)
        for network in [item for item in wanted if item not in current]:
            family = ipaddress.ip_network(network, strict=False).version
            gateway = state.get("gateway4") if family == 4 else state.get("gateway6")
            interface = state.get("interface4") if family == 4 else state.get("interface6")
            if self._network_route(
                network, via_tunnel, state.get("tunnel_interface"), gateway, interface
            ):
                current.append(network)

        state["networks"] = current
        model.write_state(state)
        return state

    def teardown(self, state: Optional[dict] = None) -> None:
        """Remove everything, with or without a state file.

        The fallback path matters: after an unclean shutdown or a reboot the
        state file can be missing or stale, and leftover rules are what made
        split tunneling look broken on the next connection.
        """
        state = model.read_state() if state is None else state

        for network in state.get("networks", []):
            self._delete_network_route(network)

        self._delete_rules(4)
        self._delete_rules(6)
        for table in (ROUTE_TABLE_BYPASS, ROUTE_TABLE_TUNNEL):
            self._run(["ip", "-4", "route", "flush", "table", str(table)], quiet=True)
            self._run(["ip", "-6", "route", "flush", "table", str(table)], quiet=True)
        self._remove_marking()
        self.release_cgroup()
        model.clear_state()

    def health(self, state: Optional[dict] = None) -> dict:
        """Report which pieces are currently present in the kernel."""
        state = model.read_state() if state is None else state
        rules = self._capture(["ip", "rule", "show"])
        routes = self._capture(["ip", "route", "show"])
        routes6 = self._capture(["ip", "-6", "route", "show"])
        missing = [
            network
            for network in state.get("networks", [])
            if network.split("/")[0] not in routes and network.split("/")[0] not in routes6
        ]
        gateway4, interface4 = self.default_gateway(4)
        return {
            "cgroup": os.path.isdir(CGROUP_PATH),
            "cgroup_pids": len(self.cgroup_pids()),
            "rule_present": MARK_HEX in rules or str(FWMARK) in rules,
            "missing_networks": missing,
            "gateway_changed": bool(
                state.get("apps") or state.get("networks")
            )
            and (gateway4 != state.get("gateway4") or interface4 != state.get("interface4")),
            "gateway4": gateway4,
            "interface4": interface4,
        }
