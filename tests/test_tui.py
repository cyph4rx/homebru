import unittest
from pathlib import Path

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Static

from homebrew_manager.config import ServerConfig
from homebrew_manager.tui import HomebruApp


class TuiSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_home_action_buttons_stay_centered_at_narrow_width(self):
        app = HomebruApp(None, Path.cwd() / "unused-config.json", save_connection=False)

        async with app.run_test(size=(90, 32)) as pilot:
            await pilot.pause()
            action_row = app.query_one("#welcome-setup-actions", Horizontal)
            buttons = list(action_row.query(Button))
            button_group_center = (buttons[0].region.x + buttons[-1].region.right) / 2
            row_center = action_row.region.x + action_row.region.width / 2
            self.assertAlmostEqual(button_group_center, row_center, delta=1)

            command_input = app.query_one("#command", Input)
            command_input.focus()
            command_input.value = "/"
            await pilot.pause()

            suggestions = app.query_one("#command-suggestions", Static)
            command_bar = app.query_one("#composer-wrap", Horizontal)
            self.assertLessEqual(suggestions.region.height, 4)
            self.assertLessEqual(command_bar.region.bottom, app.screen.region.bottom)

    async def test_command_autocomplete_completes_commands_and_service_names(self):
        app = HomebruApp(None, Path.cwd() / "unused-config.json", save_connection=False)

        async with app.run_test(size=(120, 40)) as pilot:
            command_input = app.query_one("#command", Input)
            command_input.focus()
            command_input.value = "/st"
            await pilot.pause()

            self.assertEqual(
                [option.value for option in app.command_suggestions],
                ["/start ", "/stop "],
            )
            await pilot.press("down", "tab")
            self.assertEqual(command_input.value, "/stop ")

            app.service_names = ["docker", "nginx"]
            command_input.value = "/start d"
            await pilot.pause()
            self.assertEqual([option.value for option in app.command_suggestions], ["/start docker"])
            await pilot.press("tab")
            self.assertEqual(command_input.value, "/start docker")

            command_input.value = "/ref"
            await pilot.pause()
            await pilot.press("enter")
            self.assertEqual(command_input.value, "/refresh")

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
