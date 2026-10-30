"""Split tunneling subsystem.

Layout::

    model.py    configuration, validation, domain resolution (cross-platform)
    linux.py    cgroup v2 + nftables/iptables + policy routing enforcement
    windows.py  route table, WFP and WinDivert enforcement
    manager.py  the facade every caller uses; picks the platform backend
    agent.py    long-lived helper: app attachment, domain re-resolution, repair

Only ``manager`` and ``model`` are meant to be imported from outside.
"""

from pvpn_cli.split.model import (  # noqa: F401
    MODE_EXCLUDE,
    MODE_INCLUDE,
    TYPE_APP,
    TYPE_DOMAIN,
    TYPE_IP,
    SplitConfigError,
    Targets,
    build_targets,
    load_config,
    master_enabled,
    save_config,
    set_master_enabled,
    update_config,
)

__all__ = [
    "MODE_EXCLUDE",
    "MODE_INCLUDE",
    "TYPE_APP",
    "TYPE_DOMAIN",
    "TYPE_IP",
    "SplitConfigError",
    "Targets",
    "build_targets",
    "load_config",
    "master_enabled",
    "save_config",
    "set_master_enabled",
    "update_config",
]
