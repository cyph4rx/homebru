import sys
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).parents[1] / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import managed_apps  # noqa: E402


class ManagedAppTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

