"""The split tunneling agent: a small root-side loop that keeps rules honest.

It replaces the old ``_pid-scanner``, which polled every three seconds, only
handled Linux applications, never re-resolved domains, ignored network changes
and did not survive a reconnect. Responsibilities now:

* attach newly started matching processes to the split cgroup (Linux) fast
  enough to catch the first outbound packet;
* re-resolve domain items on a TTL and apply only the delta;
* notice when the physical gateway or interface changes (Wi-Fi to Ethernet,
  roaming, VPN-adjacent adapters appearing) and rebuild the affected routes;
* re-add rules that something else removed, and restart the Windows helper if it
  died;
* exit and clean up when the tunnel goes away.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from pvpn_cli.split import manager, model
from pvpn_cli.split.model import DomainCache

PROCESS_POLL_SECONDS = 0.25
HEALTH_POLL_SECONDS = 5.0
ENGINE_GRACE_SECONDS = 20.0


def _log_path() -> str:
    from pvpn_cli.cli.config import get_config_dir

    return os.path.join(get_config_dir(), "split.log")


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    try:
        with open(_log_path(), "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Process matching (Linux)
# --------------------------------------------------------------------------- #

def _matchers(apps) -> tuple:
    paths, names = set(), set()
    for app in apps:
        if os.sep in app or app.startswith("/"):
            paths.add(os.path.realpath(os.path.expanduser(app)))
            names.add(os.path.basename(app))
        else:
            names.add(app)
    return paths, names


def _process_matches(pid: int, paths: set, names: set) -> bool:
    try:
        executable = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        executable = ""
    if executable:
        if os.path.realpath(executable) in paths or os.path.basename(executable) in names:
            return True
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="replace") as handle:
            if handle.read().strip() in names:
                return True
    except OSError:
        pass
    # Interpreted programs (scripts, Electron wrappers, Java) expose the real
    # target only in the command line, which is why the executable check alone
    # used to miss things like Steam or Discord launchers.
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            argv = [part.decode("utf-8", "replace") for part in handle.read().split(b"\x00") if part]
    except OSError:
        return False
    for argument in argv[:2]:
        candidate = os.path.basename(argument)
        if candidate in names:
            return True
        if argument.startswith("/") and os.path.realpath(argument) in paths:
            return True
    return False


def _iter_pids():
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                yield int(entry)
    except OSError:
        return


class LinuxProcessAttacher:
    """Keeps every matching process inside the split cgroup."""

    def __init__(self, backend, apps):
        self._backend = backend
        self._paths, self._names = _matchers(apps)
        self._seen = set()

    def sweep(self) -> int:
        attached = 0
        inside = set(self._backend.cgroup_pids())
        live = set()
        for pid in _iter_pids():
            live.add(pid)
            if pid in inside or pid in self._seen:
                continue
            if _process_matches(pid, self._paths, self._names):
                if self._backend.attach_pid(pid):
                    attached += 1
                    log(f"[split] attached pid {pid} to the split cgroup")
                self._seen.add(pid)
        self._seen &= live
        return attached


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #

def run(once: bool = False) -> int:
    state = model.read_state()
    if not state:
        log("[split] agent started with no active state; nothing to do")
        return 0

    backend = manager.get_backend(log=log)
    cache = DomainCache()
    config = model.load_config()
    domains = [item["value"] for item in config.get("items", []) if item["type"] == "domain" and item.get("enabled", True)]
    base_targets = model.build_targets(config=config, resolve_domains=False)
    static_networks = list(base_targets.v4) + list(base_targets.v6)

    attacher = None
    if not manager.is_windows() and state.get("apps"):
        attacher = LinuxProcessAttacher(backend, state["apps"])

    log(
        "[split] agent running: mode=%s apps=%d networks=%d domains=%d"
        % (
            state.get("mode"),
            len(state.get("apps", [])),
            len(static_networks),
            len(domains),
        )
    )

    last_health = 0.0
    last_domains = 0.0
    engine_missing_since: Optional[float] = None

    while True:
        now = time.monotonic()

        if attacher:
            try:
                attacher.sweep()
            except Exception as exc:
                log(f"[split] process sweep failed: {exc}")

        if now - last_health >= HEALTH_POLL_SECONDS:
            last_health = now

            if not manager.engine_running():
                engine_missing_since = engine_missing_since or now
                if now - engine_missing_since >= ENGINE_GRACE_SECONDS:
                    log("[split] tunnel is gone; removing split tunneling rules")
                    manager.get_backend(log=log).teardown()
                    return 0
            else:
                engine_missing_since = None

            if not model.read_state():
                log("[split] state file disappeared; agent exiting")
                return 0

            try:
                health = backend.health(state)
            except Exception as exc:
                log(f"[split] health check failed: {exc}")
                health = {}

            if health.get("gateway_changed"):
                log("[split] the physical network changed; rebuilding split routes")
                targets = model.build_targets(domain_cache=cache)
                try:
                    backend.teardown(state)
                except Exception:
                    pass
                state = backend.apply(
                    targets,
                    tunnel_interface=state.get("tunnel_interface") or "awg0",
                    tunnel_ip4=state.get("tunnel_ip4"),
                    tunnel_ip6=state.get("tunnel_ip6"),
                )
                if attacher and state.get("apps"):
                    attacher = LinuxProcessAttacher(backend, state["apps"])
                continue

            if health.get("missing_networks"):
                log(
                    "[split] re-adding routes removed by something else: "
                    + ", ".join(health["missing_networks"])
                )
                wanted = list(state.get("networks", []))
                state["networks"] = [
                    network for network in wanted if network not in health["missing_networks"]
                ]
                state = backend.refresh_networks(state, wanted)

            if manager.is_windows() and health.get("helper_expected") and not health.get(
                "helper_running"
            ):
                log("[split] the application helper is not running; restarting it")
                targets = model.build_targets(domain_cache=cache)
                pid = backend.start_helper(state, targets)
                state["helper_pid"] = pid
                model.write_state(state)
                for warning in targets.warnings:
                    log(f"[split] {warning}")

            if not manager.is_windows() and state.get("apps") and not health.get("rule_present"):
                log("[split] the routing rule vanished; reinstalling it")
                targets = model.build_targets(domain_cache=cache)
                state = backend.apply(
                    targets,
                    tunnel_interface=state.get("tunnel_interface") or "awg0",
                    tunnel_ip4=state.get("tunnel_ip4"),
                    tunnel_ip6=state.get("tunnel_ip6"),
                )

        if domains and now - last_domains >= model.DOMAIN_TTL_SECONDS:
            last_domains = now
            resolved4, resolved6 = cache.refresh(domains)
            wanted = list(static_networks)
            wanted += [f"{address}/32" for address in resolved4]
            wanted += [f"{address}/128" for address in resolved6]
            if sorted(wanted) != sorted(state.get("networks", [])):
                log("[split] domain addresses changed; updating routes")
                state = backend.refresh_networks(state, wanted)

        if once:
            return 0
        time.sleep(PROCESS_POLL_SECONDS if attacher else 1.0)


def main(argv=None) -> int:
    argv = argv or []
    try:
        return run(once="--once" in argv)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # a crashed agent must not take the VPN with it
        log(f"[split] agent crashed: {exc}")
        return 1
