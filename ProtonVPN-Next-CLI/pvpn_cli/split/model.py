"""Split tunneling data model: the single owner of ``split_tunnel.json``.

Nothing outside this module is allowed to parse or write that file. The CLI, the
REST API, the routing layer and the background agent all go through here, so
they can never disagree about what the user asked for -- which is exactly how
the previous implementation lost items whenever the GUI saved a partial object.

Schema v2::

    {
      "version": 2,
      "enabled": true,
      "mode": "exclude" | "include",
      "exclude_lan": false,
      "items": [
        {"id": "...", "type": "app"|"ip"|"domain", "value": "...", "enabled": true}
      ]
    }

v1 files only carried ``exclude_lan`` and ``split_items``; they are migrated on
read. ``split_items`` is still written back as a mirror so an older build that
reads the file directly keeps working.
"""

from __future__ import annotations

import ipaddress
import json
import os
import platform
import re
import socket
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from pvpn_cli.cli.config import get_config_dir

CONFIG_NAME = "split_tunnel.json"
STATE_NAME = "split_state.json"
SCHEMA_VERSION = 2

MODE_EXCLUDE = "exclude"
MODE_INCLUDE = "include"
MODES = (MODE_EXCLUDE, MODE_INCLUDE)

TYPE_APP = "app"
TYPE_IP = "ip"
TYPE_DOMAIN = "domain"
ITEM_TYPES = (TYPE_APP, TYPE_IP, TYPE_DOMAIN)

# Kernel-side identifiers. They are constants rather than derived values so that
# a teardown after a crash or a reboot can find and remove every object without
# needing the state file that may be gone.
FWMARK = 0x51820
ROUTE_TABLE_BYPASS = 51820
ROUTE_TABLE_TUNNEL = 51821
RULE_PRIORITY = 8100
CGROUP_NAME = "pvpn.split"
CGROUP_ROOT = "/sys/fs/cgroup"
NFT_TABLE = "pvpn_split"

# RFC1918 plus link-local and CGNAT: what "LAN" means in practice on a desktop.
LAN_V4 = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "100.64.0.0/10",
    "224.0.0.0/4",
)
LAN_V6 = ("fc00::/7", "fe80::/10", "ff00::/8")

DOMAIN_TTL_SECONDS = 300
DOMAIN_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-_]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-_]{1,63}(?<!-))*\.?$"
)


class SplitConfigError(ValueError):
    """The user supplied a value that cannot be enforced."""


def is_windows() -> bool:
    return platform.system() == "Windows"


def config_path() -> str:
    return os.path.join(get_config_dir(), CONFIG_NAME)


def state_path() -> str:
    return os.path.join(get_config_dir(), STATE_NAME)


def default_config() -> dict:
    return {
        "version": SCHEMA_VERSION,
        "enabled": False,
        "mode": MODE_EXCLUDE,
        "exclude_lan": False,
        "items": [],
    }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def normalize_network(value: str) -> str:
    """Accept an address or a CIDR block and return canonical CIDR form.

    The old code matched IPv4 with a regex and then pushed everything through a
    /32 route, so ``10.8.0.0/16`` silently became a single host. Both families
    and every prefix length are handled here instead.
    """
    text = (value or "").strip()
    if not text:
        raise SplitConfigError("An IP address or CIDR block is required")
    try:
        return str(ipaddress.ip_network(text, strict=False))
    except ValueError as exc:
        raise SplitConfigError(f"Not a valid IP address or CIDR block: {value}") from exc


def normalize_domain(value: str) -> str:
    text = (value or "").strip().rstrip(".").lower()
    if text.startswith("http://") or text.startswith("https://"):
        text = text.split("//", 1)[1].split("/", 1)[0]
    if not text or len(text) > 253 or not DOMAIN_RE.match(text):
        raise SplitConfigError(f"Not a valid domain name: {value}")
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return text
    raise SplitConfigError("That is an IP address; add it as an IP item instead")


def normalize_app(value: str) -> str:
    """Normalize an executable reference.

    Both platforms accept either an absolute path or a bare executable name.
    A bare name is deliberately supported: users type ``firefox`` far more often
    than ``/usr/lib/firefox/firefox``, and matching by basename is what the
    enforcement layers do anyway. Windows paths are lower-cased because the
    filesystem is case-insensitive and WFP/WinDivert comparisons are not.
    """
    text = (value or "").strip().strip('"')
    if not text:
        raise SplitConfigError("An application path or executable name is required")
    if any(ch in text for ch in ("\x00", "\n", "\r")):
        raise SplitConfigError("Control characters are not allowed in a path")
    if len(text) > 4096:
        raise SplitConfigError("That path is unreasonably long")
    if is_windows() or re.match(r"^[A-Za-z]:[\\/]", text):
        text = text.replace("/", "\\")
        if "\\" in text:
            text = os.path.normpath(text)
        return text.lower()
    return text


def guess_type(value: str) -> str:
    text = (value or "").strip()
    try:
        ipaddress.ip_network(text, strict=False)
        return TYPE_IP
    except ValueError:
        pass
    if (
        text.startswith("/")
        or text.startswith("~")
        or re.match(r"^[A-Za-z]:[\\/]", text)
        or text.lower().endswith((".exe", ".bat", ".cmd", ".appx"))
        or "\\" in text
    ):
        return TYPE_APP
    try:
        normalize_domain(text)
        return TYPE_DOMAIN
    except SplitConfigError:
        return TYPE_APP


def normalize_value(item_type: str, value: str) -> str:
    if item_type == TYPE_IP:
        return normalize_network(value)
    if item_type == TYPE_DOMAIN:
        return normalize_domain(value)
    if item_type == TYPE_APP:
        return normalize_app(value)
    raise SplitConfigError(f"Unknown item type: {item_type}")


def normalize_item(raw: Any) -> Optional[dict]:
    """Coerce one stored or submitted item, dropping anything unusable."""
    if isinstance(raw, str):
        raw = {"value": raw}
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    item_type = raw.get("type")
    if item_type not in ITEM_TYPES:
        item_type = guess_type(value)
    try:
        value = normalize_value(item_type, value)
    except SplitConfigError:
        return None
    enabled = raw.get("enabled", True)
    item_id = raw.get("id")
    if not isinstance(item_id, str) or not item_id:
        item_id = uuid.uuid4().hex[:12]
    return {
        "id": item_id,
        "type": item_type,
        "value": value,
        "enabled": bool(enabled) if isinstance(enabled, (bool, int)) else True,
    }


def normalize_config(raw: Any) -> dict:
    """Turn anything found on disk or posted by a client into schema v2."""
    config = default_config()
    if not isinstance(raw, dict):
        return config

    mode = raw.get("mode")
    if isinstance(mode, str) and mode.lower() in MODES:
        config["mode"] = mode.lower()

    config["exclude_lan"] = _as_bool(raw.get("exclude_lan"), False)
    if "enabled" in raw:
        config["enabled"] = _as_bool(raw.get("enabled"), False)

    source = raw.get("items")
    if not isinstance(source, list):
        source = raw.get("split_items")
    if not isinstance(source, list):
        source = []

    seen = set()
    items = []
    for entry in source:
        item = normalize_item(entry)
        if not item:
            continue
        key = (item["type"], item["value"])
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    config["items"] = items
    return config


def _as_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "on", "yes"):
            return True
        if lowered in ("false", "0", "off", "no"):
            return False
    return fallback


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def load_config() -> dict:
    path = config_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return default_config()
    return normalize_config(raw)


def save_config(config: dict) -> dict:
    """Write the config atomically, mirroring the legacy key for old builds.

    A plain ``open(path, "w")`` truncates first, so a crash or a full disk in
    the middle of a save used to leave an empty file and silently wipe every
    exclusion. Writing a sibling file and renaming it cannot do that.
    """
    normalized = normalize_config(config)
    payload = dict(normalized)
    payload["split_items"] = [
        {"type": item["type"], "value": item["value"]}
        for item in normalized["items"]
        if item["enabled"]
    ]

    path = config_path()
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    handle_fd, temporary = tempfile.mkstemp(prefix=".split_tunnel-", dir=directory)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        if not is_windows():
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass
    return normalized


def update_config(patch: dict) -> dict:
    """Merge a partial update (what the GUI posts) into the stored config."""
    current = load_config()
    if not isinstance(patch, dict):
        return current

    merged = dict(current)
    for key in ("mode", "exclude_lan", "enabled"):
        if key in patch:
            merged[key] = patch[key]
    if "items" in patch or "split_items" in patch:
        merged["items"] = patch.get("items", patch.get("split_items"))
        merged.pop("split_items", None)
    return save_config(merged)


def master_enabled(config: Optional[dict] = None, db=None) -> bool:
    """Is split tunneling switched on?

    The database keeps the master switch so the GUI settings screen and the CLI
    ``split-tunneling on|off`` agree, but the JSON copy is authoritative when the
    database has never been written -- that is the case for configs created
    before the switch existed.
    """
    from pvpn_cli.database import Database

    try:
        raw = (db or Database()).get_setting("split_tunneling")
    except Exception:
        raw = None
    if raw is not None:
        return str(raw).lower() == "true"
    config = load_config() if config is None else config
    if config.get("enabled"):
        return True
    return bool([item for item in config.get("items", []) if item.get("enabled")])


def set_master_enabled(enabled: bool, db=None) -> None:
    from pvpn_cli.database import Database

    try:
        (db or Database()).set_setting("split_tunneling", "true" if enabled else "false")
    except Exception:
        pass
    config = load_config()
    config["enabled"] = bool(enabled)
    save_config(config)


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

@dataclass
class Targets:
    """Everything the enforcement layers need, already validated."""

    mode: str = MODE_EXCLUDE
    v4: list = field(default_factory=list)
    v6: list = field(default_factory=list)
    apps: list = field(default_factory=list)
    domains: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def is_exclude(self) -> bool:
        return self.mode == MODE_EXCLUDE

    @property
    def has_networks(self) -> bool:
        return bool(self.v4 or self.v6)

    def empty(self) -> bool:
        return not (self.v4 or self.v6 or self.apps)


def resolve_domain(name: str, timeout: float = 3.0) -> tuple:
    """Resolve one name to IPv4 and IPv6 literals.

    ``gethostbyname_ex`` was IPv4-only, which is why an excluded domain served
    over IPv6 kept going through the tunnel.
    """
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    v4, v6 = [], []
    try:
        for family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(
            name, None, proto=socket.IPPROTO_TCP
        ):
            address = sockaddr[0].split("%", 1)[0]
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError:
                continue
            if parsed.version == 4 and address not in v4:
                v4.append(address)
            elif parsed.version == 6 and address not in v6:
                v6.append(address)
    except (socket.gaierror, socket.herror, OSError, UnicodeError):
        pass
    finally:
        socket.setdefaulttimeout(previous)
    return v4, v6


class DomainCache:
    """Re-resolving cache for domain items.

    A domain was previously resolved exactly once, at connect time. Anything
    behind a CDN therefore drifted out of the exclusion within minutes. The
    agent calls :meth:`refresh` on a timer and applies the delta.
    """

    def __init__(self, ttl: float = DOMAIN_TTL_SECONDS):
        self.ttl = ttl
        self._entries: dict = {}

    def refresh(self, domains: Iterable[str], force: bool = False) -> tuple:
        wanted = list(dict.fromkeys(domains))
        now = time.monotonic()
        for stale in [name for name in self._entries if name not in wanted]:
            self._entries.pop(stale, None)
        for name in wanted:
            entry = self._entries.get(name)
            if entry and not force and now - entry["at"] < self.ttl:
                continue
            v4, v6 = resolve_domain(name)
            if not v4 and not v6 and entry:
                # Keep the previous answer instead of dropping the exclusion
                # because one lookup failed on a flaky link.
                entry["at"] = now
                continue
            self._entries[name] = {"v4": v4, "v6": v6, "at": now}
        return self.addresses()

    def addresses(self) -> tuple:
        v4, v6 = [], []
        for entry in self._entries.values():
            for address in entry["v4"]:
                if address not in v4:
                    v4.append(address)
            for address in entry["v6"]:
                if address not in v6:
                    v6.append(address)
        return v4, v6


def build_targets(
    config: Optional[dict] = None,
    db=None,
    domain_cache: Optional[DomainCache] = None,
    resolve_domains: bool = True,
    include_lan: bool = True,
    allow_lan_setting: Optional[bool] = None,
) -> Targets:
    """Turn stored configuration into concrete networks and app matchers."""
    config = load_config() if config is None else normalize_config(config)
    targets = Targets(mode=config.get("mode", MODE_EXCLUDE))

    if not master_enabled(config, db=db):
        if config.get("items"):
            targets.warnings.append(
                "Split tunneling is switched off, so its items are ignored."
            )
        if allow_lan_setting and include_lan and targets.is_exclude:
            _add_lan(targets)
        return targets

    domains = []
    for item in config.get("items", []):
        if not item.get("enabled", True):
            continue
        value = item["value"]
        if item["type"] == TYPE_IP:
            network = ipaddress.ip_network(value, strict=False)
            (targets.v4 if network.version == 4 else targets.v6).append(str(network))
        elif item["type"] == TYPE_DOMAIN:
            domains.append(value)
        elif item["type"] == TYPE_APP:
            targets.apps.append(value)

    targets.domains = domains
    if domains and resolve_domains:
        cache = domain_cache or DomainCache()
        v4, v6 = cache.refresh(domains)
        for address in v4:
            network = f"{address}/32"
            if network not in targets.v4:
                targets.v4.append(network)
        for address in v6:
            network = f"{address}/128"
            if network not in targets.v6:
                targets.v6.append(network)
        if not v4 and not v6:
            targets.warnings.append(
                "None of the configured domains could be resolved yet."
            )

    # LAN is a bypass concept, so it only applies to exclude mode. In include
    # mode the physical route already carries LAN traffic.
    lan_wanted = config.get("exclude_lan", False) or bool(allow_lan_setting)
    if include_lan and lan_wanted and targets.is_exclude:
        _add_lan(targets)

    return targets


def _add_lan(targets: Targets) -> None:
    for network in LAN_V4:
        if network not in targets.v4:
            targets.v4.append(network)
    for network in LAN_V6:
        if network not in targets.v6:
            targets.v6.append(network)


# --------------------------------------------------------------------------- #
# Runtime state
# --------------------------------------------------------------------------- #

def read_state() -> dict:
    try:
        with open(state_path(), "r", encoding="utf-8") as handle:
            state = json.load(handle)
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(state: dict) -> None:
    path = state_path()
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    handle_fd, temporary = tempfile.mkstemp(prefix=".split_state-", dir=directory)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(temporary, path)
    finally:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass


def clear_state() -> None:
    try:
        os.remove(state_path())
    except FileNotFoundError:
        pass
    except OSError:
        pass
