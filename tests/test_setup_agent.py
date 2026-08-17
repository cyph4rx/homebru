import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

AGENT_DIR = Path(__file__).parents[1] / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import setup_agent  # noqa: E402


class AgentSetupTests(unittest.TestCase):
    def setUp(self):
        self.output = Path(__file__).parent / "fixtures" / "setup_output"
        self.config_path = Path(__file__).parent / "fixtures" / "setup-agent-config.json"
        self._clean_output()
        self.config_path.unlink(missing_ok=True)

    def tearDown(self):
        self._clean_output()
        self.config_path.unlink(missing_ok=True)

    def _clean_output(self):
        for item in self.output.iterdir():
            if item.name != ".gitkeep" and item.is_file():
                item.unlink()

    def test_discord_template_is_created_and_registered(self):
        with patch.object(setup_agent.agent_config, "CONFIG_PATH", self.config_path):
            app = setup_agent.create_discord_bot("My Bot", self.output, "test-token", install=False)
            config = setup_agent.register_app(app)

        self.assertEqual(app["name"], "my-bot")
        self.assertIn("my-bot is online", (self.output / "bot.py").read_text(encoding="utf-8"))
        self.assertEqual((self.output / ".env").read_text(encoding="utf-8"), "DISCORD_TOKEN=test-token\n")
        self.assertIn("discord.py==2.7.1", (self.output / "requirements.txt").read_text(encoding="utf-8"))
        self.assertEqual(config["managed_apps"][0]["name"], "my-bot")
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["managed_apps"][0]["name"], "my-bot")
        with patch.object(setup_agent.agent_config, "CONFIG_PATH", self.config_path):
            loaded = setup_agent.agent_config.load_config(announce_token=False)
        self.assertEqual(loaded["managed_apps"][0]["name"], "my-bot")

    def test_template_rerun_keeps_existing_token(self):
        setup_agent.create_discord_bot("bot", self.output, "original", install=False)
        setup_agent.create_discord_bot("bot", self.output, "", install=False)
        self.assertEqual((self.output / ".env").read_text(encoding="utf-8"), "DISCORD_TOKEN=original\n")

    def test_frozen_agent_config_uses_per_user_storage(self):
        environment_name = "APPDATA" if setup_agent.os.name == "nt" else "XDG_CONFIG_HOME"
        config_root = Path("user-config")
        with (
            patch.object(setup_agent.agent_config.sys, "frozen", True, create=True),
            patch.dict(setup_agent.agent_config.os.environ, {environment_name: str(config_root)}),
        ):
            config_path = setup_agent.agent_config.default_config_path()

        self.assertEqual(config_path, config_root / "homebru" / "agent" / "config.json")


class AdditionalTemplateTests(unittest.TestCase):
    def setUp(self):
        self.output = Path(__file__).parent / "fixtures" / "template_output"
        shutil.rmtree(self.output, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.output, ignore_errors=True)

    def test_minecraft_template_has_safe_eula_and_start_command(self):
        app = setup_agent.create_minecraft_server("My World", self.output, 3072)

        self.assertEqual(app["name"], "my-world")
        self.assertEqual(app["command"], ["java", "-Xms3072M", "-Xmx3072M", "-jar", "server.jar", "nogui"])
        self.assertIn("eula=false", (self.output / "eula.txt").read_text(encoding="utf-8"))
        self.assertIn("my-world", (self.output / "server.properties").read_text(encoding="utf-8"))
        self.assertTrue((self.output / "READ.txt").exists())

    def test_python_and_node_templates_are_runnable_starters(self):
        python_dir = self.output / "python"
        node_dir = self.output / "node"
        python_app = setup_agent.create_python_http_server("Python Site", python_dir, 8080)
        node_app = setup_agent.create_node_http_server("Node Site", node_dir, 3030)

        self.assertEqual(python_app["command"][-2:], ["--port", "8080"])
        self.assertIn("python-site", (python_dir / "public" / "index.html").read_text(encoding="utf-8"))
        self.assertEqual((node_dir / ".env").read_text(encoding="utf-8"), "PORT=3030\n")
        self.assertIn("node-site", (node_dir / "server.js").read_text(encoding="utf-8"))

    def test_custom_server_splits_quoted_command(self):
        app = setup_agent.create_custom_server(
            "Existing App",
            self.output,
            'python "server app.py" --port 9000',
            "Existing application",
        )

        self.assertEqual(app["command"], ["python", "server app.py", "--port", "9000"])
        self.assertEqual(app["description"], "Existing application")

    def test_frozen_build_runs_python_templates_through_homebru(self):
        script = self.output / "server.py"
        with (
            patch.object(setup_agent.sys, "frozen", True, create=True),
            patch.object(setup_agent.sys, "executable", "homebru.exe"),
        ):
            command = setup_agent._python_script_command(
                Path("unused-python"),
                script,
                "--port",
                "8080",
            )

        self.assertEqual(
            command,
            ["homebru.exe", "--run-bundled-script", str(script), "--port", "8080"],
        )


if __name__ == "__main__":
    unittest.main()
