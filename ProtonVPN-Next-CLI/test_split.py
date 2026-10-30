"""Unit tests for the split-tunneling configuration and planning layer."""

import os
import tempfile
import unittest
from unittest import mock

from pvpn_cli.split import manager, model


class FakeDatabase:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def get_setting(self, key, default=None):
        if key == "split_tunneling":
            return "true" if self.enabled else "false"
        return default

    def set_setting(self, key, value):
        if key == "split_tunneling":
            self.enabled = str(value).lower() == "true"


class SplitModelTest(unittest.TestCase):
    def setUp(self):
        self.config_dir = tempfile.TemporaryDirectory(prefix="pvpn-split-test-")
        self.env = mock.patch.dict(
            os.environ, {"PVPN_CONFIG_DIR": self.config_dir.name}, clear=False
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.config_dir.cleanup()

    def test_guess_type_does_not_confuse_dot_com_domain_with_application(self):
        self.assertEqual(model.TYPE_DOMAIN, model.guess_type("example.com"))
        self.assertEqual(model.TYPE_APP, model.guess_type("firefox.exe"))
        self.assertEqual(model.TYPE_IP, model.guess_type("2001:db8::/32"))

    def test_legacy_config_is_migrated_and_cidr_is_normalized(self):
        saved = model.save_config(
            {
                "exclude_lan": True,
                "split_items": [
                    {"type": "ip", "value": "10.0.0.5"},
                    {"type": "domain", "value": "Example.COM."},
                ],
            }
        )
        self.assertEqual(model.SCHEMA_VERSION, saved["version"])
        self.assertEqual("10.0.0.5/32", saved["items"][0]["value"])
        self.assertEqual("example.com", saved["items"][1]["value"])
        self.assertTrue(all(item.get("id") for item in saved["items"]))

    def test_disabled_rules_are_preserved_but_not_planned(self):
        config = model.save_config(
            {
                "enabled": False,
                "items": [{"type": "ip", "value": "10.0.0.0/8"}],
            }
        )
        self.assertEqual(1, len(config["items"]))
        targets = model.build_targets(config=config, db=FakeDatabase(False))
        self.assertTrue(targets.empty())

    def test_include_mode_uses_tunnel_only_for_selected_prefixes(self):
        config = {
            "enabled": True,
            "mode": model.MODE_INCLUDE,
            "items": [
                {"type": "ip", "value": "10.0.0.0/8", "enabled": True},
                {"type": "ip", "value": "2001:db8::/32", "enabled": True},
            ],
        }
        targets = model.build_targets(config=config, db=FakeDatabase(True))
        self.assertEqual(["10.0.0.0/8"], targets.v4)
        self.assertEqual(["2001:db8::/32"], targets.v6)
        self.assertFalse(manager.routes_all_traffic(targets))

    def test_exclude_lan_contains_ipv4_and_ipv6_local_ranges(self):
        config = {
            "enabled": True,
            "mode": model.MODE_EXCLUDE,
            "exclude_lan": True,
            "items": [],
        }
        targets = model.build_targets(config=config, db=FakeDatabase(True))
        self.assertIn("10.0.0.0/8", targets.v4)
        self.assertIn("fc00::/7", targets.v6)
        self.assertTrue(manager.routes_all_traffic(targets))


if __name__ == "__main__":
    unittest.main()
