import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

AGENT_DIR = Path(__file__).parents[1] / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import managed_apps  # noqa: E402


class ManagedAppTests(unittest.TestCase):
    @staticmethod
    def _wait_for_log(log_path: Path, expected: str) -> str:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            if expected in content:
                return content
            time.sleep(0.05)
        raise AssertionError(f"'{expected}' did not appear in {log_path}")

    @patch.object(managed_apps, "_find_running_process", return_value=None)
    def test_missing_working_directory_has_no_manageable_target(self, find_process):
        app = {"name": "deleted", "cwd": str(Path(__file__).parent / "fixtures" / "missing")}
        runtime = Path(__file__).parent / "fixtures" / "runtime"

        self.assertFalse(managed_apps.has_manageable_target(app, runtime))
        find_process.assert_called_once_with(app, runtime)

    def test_start_status_and_stop(self):
        cwd = Path(__file__).parent / "fixtures" / "managed_app"
        runtime = Path(__file__).parent / "fixtures" / "runtime"
        log = cwd / "test-process.log"
        app = {
            "name": "test-process",
            "command": [sys.executable, "-c", "import time; time.sleep(30)"],
            "cwd": str(cwd),
            "log_file": str(log),
            "description": "Managed app test",
        }
        try:
            managed_apps.start(app, runtime)
            self.assertEqual(managed_apps.get_status(app, runtime)["active_state"], "active")
        finally:
            managed_apps.stop(app, runtime)
            log.unlink(missing_ok=True)
        self.assertEqual(managed_apps.get_status(app, runtime)["active_state"], "inactive")

    def test_reads_live_logs_and_sends_console_input(self):
        cwd = Path(__file__).parent / "fixtures" / "managed_app"
        runtime = Path(__file__).parent / "fixtures" / "runtime"
        log = cwd / "console-process.log"
        app = {
            "name": "console-process",
            "command": [
                sys.executable,
                "-u",
                "-c",
                (
                    "import sys,time; print('ready', flush=True); "
                    "command=sys.stdin.readline().strip(); "
                    "print('received:'+command, flush=True); time.sleep(30)"
                ),
            ],
            "cwd": str(cwd),
            "log_file": str(log),
        }
        try:
            managed_apps.start(app, runtime)
            self._wait_for_log(log, "ready")
            self.assertTrue(managed_apps.console_input_available(app, runtime))
            self.assertIn("ready", managed_apps.read_log_tail(app))

            managed_apps.send_console_command(app, "status", runtime)

            self.assertIn("received:status", self._wait_for_log(log, "received:status"))
        finally:
            managed_apps.stop(app, runtime)
            log.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
