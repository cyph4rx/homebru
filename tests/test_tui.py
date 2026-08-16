import unittest
from pathlib import Path

from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input

from homebrew_manager.config import ServerConfig
from homebrew_manager.tui import HomebruApp


class TuiSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_screen_mounts_and_renders_agent_data(self):
        config = ServerConfig(host="127.0.0.1", port=9, token="test", request_timeout=1)
        config_path = Path.cwd() / "homebrew-tui-test.json"
        app = HomebruApp(config, config_path, save_connection=False)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertIsNotNone(app.query_one("#service-table", DataTable))
            self.assertIsNotNone(app.query_one("#command", Input))
            self.assertFalse(app.query_one("#welcome-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#content-scroll", VerticalScroll).has_class("hidden"))
            self.assertTrue(app.query_one("#open-dashboard", Button).has_focus)
            self.assertIsNone(app.client)

            app._connect_and_show_dashboard(config)
            await pilot.pause()
            self.assertTrue(app.query_one("#welcome-panel", Vertical).has_class("hidden"))
            self.assertFalse(app.query_one("#content-scroll", VerticalScroll).has_class("hidden"))
            app._render_system_stats({
                "uptime_seconds": 90061,
                "cpu": {"percent": 35, "core_count": 8},
                "memory": {"percent": 62, "used": 8 * 1024**3, "total": 16 * 1024**3},
                "disks": [{"mountpoint": "/", "percent": 44, "used": 44, "total": 100}],
                "gpus": [],
            })
            app._render_services([{
                "name": "docker",
                "active_state": "active",
                "sub_state": "running",
                "enabled": "enabled",
                "description": "Docker service",
            }])
            await pilot.pause()
            self.assertEqual(app.service_names, ["docker"])

            app._show_connection()
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 1)
            self.assertFalse(app.query_one("#connection-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#content-scroll", VerticalScroll).has_class("hidden"))

            app._show_home()
            await pilot.pause()
            self.assertTrue(app.query_one("#connection-panel", Vertical).has_class("hidden"))
            self.assertFalse(app.query_one("#welcome-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#content-scroll", VerticalScroll).has_class("hidden"))
            self.assertTrue(app.query_one("#open-dashboard", Button).has_focus)

    async def test_first_run_uses_inline_setup_choice(self):
        app = HomebruApp(None, Path.cwd() / "unused-config.json", save_connection=False)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 1)
            self.assertFalse(app.query_one("#welcome-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#connection-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#template-picker-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#local-setup-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#custom-setup-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#content-scroll", VerticalScroll).has_class("hidden"))
            self.assertTrue(app.query_one("#setup-templates", Button).has_focus)

            app._show_template_picker()
            await pilot.pause()
            self.assertFalse(app.query_one("#template-picker-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#template-discord", Button).has_focus)

            app._show_template_form("minecraft-java")
            await pilot.pause()
            self.assertTrue(app.query_one("#welcome-panel", Vertical).has_class("hidden"))
            self.assertFalse(app.query_one("#local-setup-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#local-name", Input).has_focus)
            self.assertEqual(app.query_one("#local-name", Input).value, "minecraft-server")
            self.assertEqual(app.query_one("#template-option", Input).value, "2048")

            app._close_template_form()
            self.assertFalse(app.query_one("#template-picker-panel", Vertical).has_class("hidden"))
            app._show_home()
            app._show_custom_form()
            await pilot.pause()
            self.assertFalse(app.query_one("#custom-setup-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#custom-name", Input).has_focus)

            app._show_home()
            app._show_connection()
            await pilot.pause()
            self.assertFalse(app.query_one("#connection-panel", Vertical).has_class("hidden"))
            self.assertTrue(app.query_one("#host", Input).has_focus)

            app._show_home()
            await pilot.pause()
            self.assertFalse(app.query_one("#welcome-panel", Vertical).has_class("hidden"))


if __name__ == "__main__":
    unittest.main()
