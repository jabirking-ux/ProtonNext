"""Platform-independent facade for split tunneling.

Every caller -- the routing layer, the REST API, the CLI and the watchdog --
goes through this module. It picks the platform backend, keeps the runtime state
file in sync, supervises the background agent and knows how to clean up after a
crash or a reboot.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Optional

from pvpn_cli.cli.config import get_config_dir
from pvpn_cli.split import model
from pvpn_cli.split.model import (
    MODE_EXCLUDE,
    MODE_INCLUDE,
    DomainCache,
    Targets,
)

AGENT_PID_FILE = "split-agent.pid"
ENGINE_NAMES = ("pvpn-engine", "pvpn-engine.exe")


def is_windows() -> bool:
    return platform.system() == "Windows"


def get_backend(log=None):
    if is_windows():
        from pvpn_cli.split.windows import WindowsSplitBackend

        return WindowsSplitBackend(log=log)
    from pvpn_cli.split.linux import LinuxSplitBackend

    return LinuxSplitBackend(log=log)


def _default_log(message: str) -> None:
    try:
        with open(os.path.join(get_config_dir(), "split.log"), "a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        pass


def engine_running() -> bool:
    """Is the VPN engine actually alive?

    Used to decide whether a leftover state file describes a live tunnel or the
    remains of a session that ended with a crash, a kill or a reboot.
    """
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        for process in psutil.process_iter(["name"]):
            try:
                if (process.info.get("name") or "") in ENGINE_NAMES:
                    return True
            except Exception:
                continue
        return False
    if is_windows():
        return False
    return (
        subprocess.run(
            ["pgrep", "-x", "pvpn-engine"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #

def plan(
    db=None,
    allow_lan: Optional[bool] = None,
    domain_cache=None,
    config: Optional[dict] = None,
) -> Targets:
    """Resolve one configuration snapshot into concrete targets."""
    return model.build_targets(
        config=config,
        db=db,
        allow_lan_setting=allow_lan,
        domain_cache=domain_cache,
    )


def routes_all_traffic(targets: Optional[Targets] = None, db=None) -> bool:
    """Should the tunnel receive a catch-all default route?

    ``False`` only in include mode with something actually selected: there, the
    physical default has to stay in place and just the chosen apps and prefixes
    are steered into the tunnel. The previous code never implemented this and
    simply discarded include-mode items with a warning.
    """
    targets = plan(db=db) if targets is None else targets
    if targets.mode != MODE_INCLUDE:
        return True
    return targets.empty()


# --------------------------------------------------------------------------- #
# Apply / teardown
# --------------------------------------------------------------------------- #

def apply(
    tunnel_interface: str,
    tunnel_ip4: Optional[str] = None,
    tunnel_ip6: Optional[str] = None,
    db=None,
    allow_lan: Optional[bool] = None,
    targets: Optional[Targets] = None,
    log=None,
    start_agent: bool = True,
) -> dict:
    """Enforce split tunneling for a freshly established tunnel."""
    log = log or _default_log
    cache = DomainCache()
    targets = plan(db=db, allow_lan=allow_lan, domain_cache=cache) if targets is None else targets

    backend = get_backend(log=log)

    # Re-apply is also used by the GUI and CLI while a tunnel is live. Tear
    # down the previous snapshot first, otherwise removed items leave stale
    # routes behind and switching modes mixes bypass and tunnel rules.
    stop_agent()
    try:
        backend.teardown()
    except Exception as exc:
        log(f"[split] could not fully remove the previous rules: {exc}")

    if is_windows():
        # Clear anything an older build left behind in the registry before
        # installing this session's rules, so a stale entry cannot shadow them.
        backend.purge_persistent_artifacts()

    if targets.empty():
        model.clear_state()
        return {"state": {}, "targets": targets, "warnings": targets.warnings, "active": False}

    state = backend.apply(
        targets,
        tunnel_interface=tunnel_interface,
        tunnel_ip4=tunnel_ip4,
        tunnel_ip6=tunnel_ip6,
    )
    state["mode"] = targets.mode
    model.write_state(state)

    if start_agent:
        # The agent also repairs network rules after gateway/interface changes,
        # even when the configuration contains only static IP/CIDR entries.
        spawn_agent(log=log)

    for warning in targets.warnings:
        log(f"[split] {warning}")
    return {"state": state, "targets": targets, "warnings": targets.warnings, "active": True}


def teardown(log=None) -> None:
    """Remove every split tunneling artifact, state file or not."""
    log = log or _default_log
    stop_agent()
    backend = get_backend(log=log)
    try:
        backend.teardown()
    except Exception as exc:  # never let cleanup abort a disconnect
        log(f"[split] teardown error: {exc}")
    if is_windows():
        try:
            backend.purge_persistent_artifacts()
        except Exception:
            pass


def reconcile(log=None) -> dict:
    """Clean up leftovers from a previous session.

    Called when the CLI, the API server or the watchdog starts. If rules exist
    while the engine does not, they are removed. This is the fix for "split
    tunneling stops working after a reboot": the machine used to come back with
    orphaned rules and a stale state file, and the next connection then took a
    recovery path that quietly dropped the user's rules.
    """
    log = log or _default_log
    state = model.read_state()
    helper_or_rules = bool(state)
    if not helper_or_rules and not is_windows():
        return {"cleaned": False}
    if engine_running():
        return {"cleaned": False, "reason": "engine running"}

    log("[split] cleaning up split tunneling leftovers from a previous session")
    teardown(log=log)
    return {"cleaned": True}


# --------------------------------------------------------------------------- #
# Agent supervision
# --------------------------------------------------------------------------- #

def _agent_pid_path() -> str:
    return os.path.join(get_config_dir(), AGENT_PID_FILE)


def _self_command() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "pvpn_cli.cli.app"]


def agent_running() -> bool:
    try:
        with open(_agent_pid_path(), "r", encoding="utf-8") as handle:
            pid = int(handle.read().strip())
    except (OSError, ValueError):
        return False
    try:
        import psutil

        return psutil.Process(pid).is_running()
    except Exception:
        if is_windows():
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def spawn_agent(log=None) -> Optional[int]:
    """Start the background agent that keeps the rules correct over time."""
    log = log or _default_log
    if agent_running():
        return None
    environment = dict(os.environ)
    # PyInstaller's bootstrap variables must not leak into the child, otherwise
    # a frozen build re-extracts into a directory that is deleted underneath it.
    for key in list(environment):
        if key.startswith("_MEI") or key == "PYINSTALLER_RESET_ENVIRONMENT":
            environment.pop(key, None)
    environment["PVPN_CONFIG_DIR"] = get_config_dir()
    creation_flags = 0x08000000 | 0x00000008 if is_windows() else 0
    try:
        process = subprocess.Popen(
            _self_command() + ["_split-agent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=environment,
            creationflags=creation_flags if is_windows() else 0,
            start_new_session=not is_windows(),
        )
    except OSError as exc:
        log(f"[split] could not start the split agent: {exc}")
        return None
    try:
        with open(_agent_pid_path(), "w", encoding="utf-8") as handle:
            handle.write(str(process.pid))
    except OSError:
        pass
    return process.pid


def stop_agent() -> None:
    path = _agent_pid_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            pid = int(handle.read().strip())
    except (OSError, ValueError):
        pid = None
    if pid:
        if is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
    try:
        os.remove(path)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def capabilities() -> dict:
    """What this machine can actually enforce.

    The GUI uses this to explain limits up front instead of letting the user
    configure something that silently does nothing.
    """
    if is_windows():
        from pvpn_cli.split import windows

        return {
            "platform": "windows",
            "apps": os.path.exists(windows.splitter_path()) and windows.windivert_present(),
            "apps_mechanism": "windivert",
            "ipv6": True,
            "include_mode": True,
            "app_picker": "file",
        }
    backend = get_backend()
    return {
        "platform": "linux",
        "apps": backend.cgroup_available(),
        "apps_mechanism": "cgroup2",
        "ipv6": True,
        "include_mode": True,
        "app_picker": "list",
    }


def list_processes(limit: int = 400) -> list:
    """Running user applications, for the GUI application picker.

    Windows had no picker at all before, which is a large part of why the
    feature felt unusable there: there was no way to name an application.
    """
    seen = {}
    try:
        import psutil  # type: ignore
    except ImportError:
        psutil = None

    if psutil is not None:
        for process in psutil.process_iter(["name", "exe", "username"]):
            try:
                info = process.info
                name = info.get("name")
                if not name:
                    continue
                path = info.get("exe") or ""
                key = (path or name).lower()
                if key in seen:
                    continue
                seen[key] = {
                    "name": name,
                    "path": path,
                    "user": info.get("username") or "",
                }
            except Exception:
                continue
    elif not is_windows():
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                path = os.readlink(os.path.join("/proc", entry, "exe"))
            except OSError:
                continue
            key = path.lower()
            if key in seen:
                continue
            seen[key] = {
                "name": os.path.basename(path),
                "path": path,
                "user": "",
            }

    processes = sorted(seen.values(), key=lambda item: item["name"].lower())
    return processes[:limit]


def status(db=None) -> dict:
    """A complete picture for ``pvpn-next status`` and the REST API."""
    config = model.load_config()
    state = model.read_state()
    targets = model.build_targets(config=config, db=db, resolve_domains=False)
    backend = get_backend()
    try:
        health = backend.health(state) if state else {}
    except Exception:
        health = {}
    if health:
        helper_ok = not health.get("helper_expected") or health.get("helper_running")
        rule_ok = not state.get("apps") or is_windows() or health.get("rule_present")
        health["ok"] = bool(
            helper_ok
            and rule_ok
            and not health.get("missing_networks")
            and not health.get("gateway_changed")
        )
    return {
        "enabled": model.master_enabled(config, db=db),
        "mode": config.get("mode", MODE_EXCLUDE),
        "exclude_lan": config.get("exclude_lan", False),
        "items": config.get("items", []),
        "counts": {
            "apps": len(targets.apps),
            "ips": len(targets.v4) + len(targets.v6),
            "domains": len(targets.domains),
        },
        "active": bool(state),
        "agent_running": agent_running(),
        "capabilities": capabilities(),
        "health": health,
        "warnings": targets.warnings,
    }
