import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "agent"))
import services  # noqa: E402


SHOW_OUTPUT = """ActiveState=active
SubState=running
UnitFileState=enabled
Description=Example daemon
"""


class ServiceTests(unittest.TestCase):
    @patch.object(services, "backend_name", return_value="systemd")
    @patch.object(services, "_run_systemctl", return_value=SHOW_OUTPUT)
    def test_parses_systemd_service_status(self, run, backend):
        status = services.get_service_status("example")
        self.assertEqual(status["active_state"], "active")
        self.assertEqual(status["description"], "Example daemon")
        run.assert_called_once()

    @patch.object(services, "backend_name", return_value="windows")
    @patch.object(services.psutil, "win_service_get")
    def test_parses_windows_service_status(self, get_service, backend):
        service = MagicMock()
        service.as_dict.return_value = {
            "status": "running",
            "start_type": "automatic",
            "display_name": "Example Service",
        }
        get_service.return_value = service
        status = services.get_service_status("ExampleSvc")
        self.assertEqual(status["active_state"], "active")
        self.assertEqual(status["enabled"], "automatic")
        self.assertEqual(status["description"], "Example Service")

    @patch.object(services, "backend_name", return_value="windows")
    @patch.object(services, "_run_sc")
    @patch.object(services.psutil, "win_service_get")
    def test_controls_windows_service_with_sc(self, get_service, run_sc, backend):
        service = MagicMock()
        service.status.side_effect = ["stopped", "running"]
        get_service.return_value = service
        services.control_service("ExampleSvc", "start", ["ExampleSvc"])
        run_sc.assert_called_once_with(["start", "ExampleSvc"])

    @patch.object(services, "_run_systemctl")
    def test_control_is_allowlisted(self, run):
        with self.assertRaises(services.ServiceError):
            services.control_service("ssh", "restart", ["docker"])
        run.assert_not_called()

    @patch.object(services, "get_service_status")
    def test_one_bad_service_does_not_hide_the_rest(self, status):
        status.side_effect = [services.ServiceError("missing"), {"name": "docker"}]
        result = services.list_services(["missing", "docker"])
        self.assertEqual(result[0]["active_state"], "error")
        self.assertEqual(result[1]["name"], "docker")


if __name__ == "__main__":
    unittest.main()
