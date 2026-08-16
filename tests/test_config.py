import json
import unittest
from pathlib import Path

from homebrew_manager.config import ConfigError, ServerConfig, load_config, save_config
from homebrew_manager.formatting import clamp_percent, format_bytes, format_uptime


class ConfigTests(unittest.TestCase):
    def test_normalizes_connection(self):
        config = ServerConfig(host=" http://server.local/ ", token=" secret ", port="8420")
        self.assertEqual(config.host, "server.local")
        self.assertEqual(config.token, "secret")
        self.assertEqual(config.base_url, "http://server.local:8420")
        secure = ServerConfig(host="https://server.local", token="secret")
        self.assertEqual(secure.base_url, "https://server.local:8420")

    def test_rejects_invalid_values(self):
        with self.assertRaises(ConfigError):
            ServerConfig(host="server.local", token="", port=8420)
        with self.assertRaises(ConfigError):
            ServerConfig(host="bad host", token="secret", port=8420)
        with self.assertRaises(ConfigError):
            ServerConfig(host="server.local", token="secret", port=70000)

    def test_round_trip(self):
        path = Path(__file__).with_name(".round-trip-config.json")
        try:
            expected = ServerConfig(host="10.0.0.5", token="token", scheme="https")
            save_config(expected, path)
            self.assertEqual(load_config(path), expected)
            self.assertTrue(json.loads(path.read_text())["token"] == "token")
        finally:
            path.unlink(missing_ok=True)
            path.with_suffix(".tmp").unlink(missing_ok=True)

    def test_missing_config_is_not_an_error(self):
        path = Path(__file__).with_name(".missing-config.json")
        path.unlink(missing_ok=True)
        self.assertIsNone(load_config(path))


class FormattingTests(unittest.TestCase):
    def test_formatting_is_resilient(self):
        self.assertEqual(clamp_percent(140), 100)
        self.assertEqual(clamp_percent("bad"), 0)
        self.assertEqual(format_bytes(1024**3), "1.0 GB")
        self.assertEqual(format_uptime(90061), "1d 1h 1m")


if __name__ == "__main__":
    unittest.main()
