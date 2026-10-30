"""Split tunneling commands.

The heavy lifting lives in :mod:`pvpn_cli.split`; this module is the command
line surface over it. Both platforms expose the same feature set: applications,
IP addresses and CIDR blocks in either family, domains, LAN bypass, and the
choice between excluding and including the selected items.
"""

import os
import shlex
import subprocess
import sys

from pvpn_cli.split import manager, model


def get_split_tunnel_config():
    """Legacy-shaped configuration, for callers that expect ``split_items``."""
    config = model.load_config()
    return dict(
        config,
        split_items=[
            {"type": item["type"], "value": item["value"]}
            for item in config.get("items", [])
            if item.get("enabled", True)
        ],
    )


def save_split_tunnel_config(config):
    return model.save_config(config)


def _print_capabilities():
    capabilities = manager.capabilities()
    if capabilities["apps"]:
        return
    if capabilities["platform"] == "windows":
        print(
            "[WARNING] Per-application rules need the bundled WinDivert driver "
            "(WinDivert.dll and WinDivert64.sys next to pvpn-split.exe)."
        )
    else:
        print(
            "[WARNING] Per-application rules need a mounted cgroup v2 hierarchy "
            "at /sys/fs/cgroup."
        )


def _reapply_if_connected():
    """Push a configuration change onto a live tunnel.

    Changes used to take effect only after a reconnect, so people concluded the
    feature was broken. Now the running session is updated in place whenever the
    agent is able to do it.
    """
    state = model.read_state()
    if not state or not manager.engine_running():
        return
    try:
        manager.apply(
            tunnel_interface=state.get("tunnel_interface") or "awg0",
            tunnel_ip4=state.get("tunnel_ip4"),
            tunnel_ip6=state.get("tunnel_ip6"),
        )
        print("-> Applied the new configuration to the active connection.")
    except Exception as exc:
        print(f"[WARNING] Could not update the active connection: {exc}")
        print("   Reconnect to apply the change.")


def do_exclude_lan(state):
    config = model.load_config()
    config["exclude_lan"] = str(state).lower() in ("on", "true", "1", "yes")
    model.save_config(config)
    print(f"-> LAN bypass {'enabled' if config['exclude_lan'] else 'disabled'}.")
    _reapply_if_connected()


def do_split_mode(mode):
    mode = (mode or "").strip().lower()
    if mode not in model.MODES:
        print(f"[ERROR] Mode must be one of: {', '.join(model.MODES)}")
        return 1
    config = model.load_config()
    config["mode"] = mode
    model.save_config(config)
    if mode == model.MODE_INCLUDE:
        print("-> Include mode: only the selected items will use the VPN.")
    else:
        print("-> Exclude mode: the selected items will bypass the VPN.")
    _reapply_if_connected()
    return 0


def _print_status():
    status = manager.status()
    print(f"[Split]  Enabled:  {'Yes' if status['enabled'] else 'No'}")
    print(f"[Split]  Mode:     {status['mode']}")
    print(f"[Split]  LAN:      {'bypassed' if status['exclude_lan'] else 'in tunnel'}")
    counts = status["counts"]
    print(
        "[Split]  Items:    "
        f"{counts['apps']} apps, {counts['ips']} networks, {counts['domains']} domains"
    )
    print(f"[Split]  Active:   {'Yes' if status['active'] else 'No'}")
    if status["active"]:
        print(f"[Split]  Agent:    {'running' if status['agent_running'] else 'stopped'}")
        health = status.get("health") or {}
        if health.get("missing_networks"):
            print(
                "[Split]  Warning:  routes missing for "
                + ", ".join(health["missing_networks"])
            )
        if health.get("helper_expected") and not health.get("helper_running"):
            print("[Split]  Warning:  the application helper is not running")
    for warning in status.get("warnings", []):
        print(f"[Split]  Note:     {warning}")


def do_split_tunneling(action, value=None, item_type=None):
    action = (action or "").strip().lower()

    if action == "on":
        model.set_master_enabled(True)
        print("-> Split tunneling enabled.")
        _print_capabilities()
        _reapply_if_connected()
        return 0

    if action == "off":
        model.set_master_enabled(False)
        print("-> Split tunneling disabled.")
        manager.teardown()
        return 0

    if action == "status":
        _print_status()
        return 0

    if action == "mode":
        return do_split_mode(value)

    if action == "reconcile":
        result = manager.reconcile()
        if result.get("cleaned"):
            print("-> Removed split tunneling leftovers from a previous session.")
        else:
            print("-> Nothing to clean up.")
        return 0

    if action == "list":
        config = model.load_config()
        items = config.get("items", [])
        if not items:
            print("-> No split tunneling items configured.")
            return 0
        print(f"-> Split tunneling items ({config.get('mode')} mode):")
        for item in items:
            marker = " " if item.get("enabled", True) else "-"
            print(f"  {marker} [{item['type']:<6}] {item['value']}")
        return 0

    if action in ("add", "remove"):
        if not value:
            print(f"[ERROR] A value is required for '{action}'.")
            return 1
        config = model.load_config()
        kind = item_type or model.guess_type(value)
        try:
            normalized = model.normalize_value(kind, value)
        except model.SplitConfigError as exc:
            print(f"[ERROR] {exc}")
            return 1

        items = config.get("items", [])
        if action == "add":
            if any(
                item["type"] == kind and item["value"] == normalized for item in items
            ):
                print(f"-> {normalized} is already in the list.")
                return 0
            if kind == model.TYPE_APP and not manager.is_windows():
                if os.sep in normalized and not os.path.exists(
                    os.path.expanduser(normalized)
                ):
                    print(f"[WARNING] {normalized} does not exist right now.")
            items.append({"type": kind, "value": normalized, "enabled": True})
            config["items"] = items
            model.save_config(config)
            print(f"-> Added {kind}: {normalized}")
            if kind == model.TYPE_APP:
                _print_capabilities()
        else:
            remaining = [
                item
                for item in items
                if not (item["value"] == normalized or item["value"] == value)
            ]
            if len(remaining) == len(items):
                print(f"-> {value} was not in the list.")
                return 0
            config["items"] = remaining
            model.save_config(config)
            print(f"-> Removed {normalized}")
        _reapply_if_connected()
        return 0

    print(
        "[ERROR] Unknown action. Use: list, add, remove, on, off, mode, status, "
        "reconcile"
    )
    return 1


def do_novpn(command_args):
    """Run one command outside the tunnel (Linux).

    The command is placed in the split cgroup, which the running rules already
    route around the VPN, so it works for any program without adding it to the
    configuration first.
    """
    if manager.is_windows():
        print("[ERROR] 'novpn' is Linux only. On Windows, add the application to the list.")
        return 1
    if not command_args:
        print("[ERROR] A command is required.")
        return 1

    if os.geteuid() != 0:
        # Re-exec through the same elevation path the rest of the CLI uses so a
        # bare `novpn curl ...` keeps working without an explicit sudo.
        from pvpn_cli.cli.elevation import elevate_command_linux

        elevate = elevate_command_linux()
        if elevate:
            arguments = elevate + [
                sys.executable,
                os.path.realpath(sys.argv[0]),
                "novpn",
            ] + list(command_args)
            return subprocess.run(arguments).returncode
        print("[ERROR] Root privileges are required to move a process into the cgroup.")
        return 1

    from pvpn_cli.split.linux import CGROUP_PATH, LinuxSplitBackend

    backend = LinuxSplitBackend(log=print)
    state = model.read_state()
    if not state:
        print("[WARNING] Split tunneling is not active; the command will run normally.")
    if not backend.ensure_cgroup():
        return 1
    if not state or not state.get("apps"):
        # The marking rule is only installed when application items exist, so a
        # bare `novpn` on an IP-only configuration would otherwise be a no-op.
        targets = model.build_targets()
        targets.apps = targets.apps or ["novpn"]
        backend.apply(
            targets,
            tunnel_interface=(state or {}).get("tunnel_interface") or "awg0",
            tunnel_ip4=(state or {}).get("tunnel_ip4"),
            tunnel_ip6=(state or {}).get("tunnel_ip6"),
        )

    procs = os.path.join(CGROUP_PATH, "cgroup.procs")
    command = " ".join(shlex.quote(part) for part in command_args)
    script = f'echo $$ > {shlex.quote(procs)} && exec {command}'

    # Drop back to the invoking user: running a browser as root would be both a
    # security problem and a way to break its profile permissions.
    original_user = os.environ.get("SUDO_USER") or os.environ.get("DOAS_USER")
    if original_user and original_user != "root":
        arguments = ["runuser", "-u", original_user, "--", "sh", "-c", script]
    else:
        arguments = ["sh", "-c", script]
    print(f"-> Running outside the VPN: {command}")
    return subprocess.run(arguments).returncode


def do_split_agent(argv=None):
    """Run the background agent (internal command)."""
    from pvpn_cli.split import agent

    return agent.main(argv or [])


def do_pid_scanner():
    """Backwards-compatible alias for the old ``_pid-scanner`` command."""
    return do_split_agent()
