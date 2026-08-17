import unittest
from pathlib import Path
from unittest.mock import patch

from homebrew_manager import local_setup


class LocalSetupTests(unittest.TestCase):
    def test_frozen_build_uses_a_stable_server_directory(self):
        with patch.object(local_setup.sys, "frozen", True, create=True):
            directory = local_setup.default_server_directory("My Server")

        self.assertEqual(directory, Path.home() / "Homebru Servers" / "my-server")

    def test_discord_setup_installs_registers_starts_and_returns_connection(self):
        project_dir = Path("test-server").resolve()
        app = {
            "name": "test-bot",
            "cwd": str(project_dir),
        }
        agent_config = {"port": 9123, "token": "agent-token"}

        with (
            patch.object(local_setup.setup_agent, "create_discord_bot", return_value=app) as create_bot,
            patch.object(local_setup.setup_agent, "install_requirements") as install,
            patch.object(local_setup.setup_agent, "register_app", return_value=agent_config) as register,
            patch.object(local_setup, "_start_agent") as start_agent,
        ):
            result = local_setup.create_local_template_server(
                "discord-bot", "Test Bot", project_dir, "discord-token"
            )

        create_bot.assert_called_once_with("Test Bot", project_dir, "discord-token", install=False)
        install.assert_called_once()
        register.assert_called_once_with(app)
        start_agent.assert_called_once_with(9123, "agent-token")
        self.assertEqual(result.connection.host, "127.0.0.1")
        self.assertEqual(result.connection.port, 9123)
        self.assertEqual(result.connection.token, "agent-token")
        self.assertEqual(result.server_name, "test-bot")
        self.assertEqual(result.project_dir, project_dir)

    def test_custom_setup_registers_server_and_starts_agent(self):
        project_dir = Path("custom-server").resolve()
        app = {"name": "custom-server", "cwd": str(project_dir)}
        agent_config = {"port": 8420, "token": "agent-token"}

        with (
            patch.object(local_setup.setup_agent, "create_custom_server", return_value=app) as create_custom,
            patch.object(local_setup.setup_agent, "install_requirements") as install,
            patch.object(local_setup.setup_agent, "register_app", return_value=agent_config),
            patch.object(local_setup, "_start_agent") as start_agent,
        ):
            result = local_setup.create_local_custom_server(
                "Custom Server", project_dir, "python server.py", "My server"
            )

        create_custom.assert_called_once_with("Custom Server", project_dir, "python server.py", "My server")
        install.assert_not_called()
        start_agent.assert_called_once_with(8420, "agent-token")
        self.assertIn("registered", result.next_step.lower())

    def test_saved_local_connection_restarts_agent_but_remote_does_not(self):
        local = local_setup.ServerConfig(host="127.0.0.1", port=8420, token="local-token")
        remote = local_setup.ServerConfig(host="192.168.1.50", port=8420, token="remote-token")

        with patch.object(local_setup, "_start_agent") as start_agent:
            local_setup.ensure_local_agent(local)
            local_setup.ensure_local_agent(remote)

        start_agent.assert_called_once_with(8420, "local-token")


if __name__ == "__main__":
    unittest.main()
