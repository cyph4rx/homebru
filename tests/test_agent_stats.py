import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

AGENT_DIR = Path(__file__).parents[1] / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import stats  # noqa: E402


class StatsTests(unittest.TestCase):
    @patch.object(stats, "hidden_window_creation_flags", return_value=123)
    @patch.object(stats.shutil, "which", return_value="nvidia-smi")
    @patch.object(stats.subprocess, "run")
    def test_gpu_query_does_not_open_a_console_window(self, run, which, creation_flags):
        run.return_value = subprocess.CompletedProcess(
            args=["nvidia-smi"],
            returncode=0,
            stdout="Example GPU, 10, 100, 1000, 50\n",
            stderr="",
        )

        result = stats.get_gpu_stats()

        self.assertEqual(result[0]["name"], "Example GPU")
        self.assertEqual(run.call_args.kwargs["creationflags"], 123)
        creation_flags.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
