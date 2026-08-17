import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import install


class InstallerEnvironmentTests(unittest.TestCase):
    def test_environment_without_pyvenv_config_is_unhealthy(self):
        environment = MagicMock(spec=Path)
        config = MagicMock(spec=Path)
        python = MagicMock(spec=Path)
        environment.__truediv__.return_value = config
        config.is_file.return_value = False
        python.is_file.return_value = True

        with (
            patch.object(install, "_environment_python", return_value=python),
            patch.object(install.subprocess, "run") as run,
        ):
            self.assertFalse(install._environment_is_healthy(environment))

        run.assert_not_called()

    def test_ensure_pipx_rebuilds_an_unhealthy_environment(self):
        environment = MagicMock(spec=Path)
        environment.exists.return_value = True
        python = MagicMock(spec=Path)
        builder = Mock()
        with (
            patch.object(install, "_installer_environment", return_value=environment),
            patch.object(install, "_environment_python", return_value=python),
            patch.object(install, "_environment_is_healthy", side_effect=[False, True]),
            patch.object(install.shutil, "rmtree") as remove_environment,
            patch.object(install.venv, "EnvBuilder", return_value=builder),
            patch.object(install.subprocess, "run", return_value=Mock(returncode=0)),
        ):
            result = install._ensure_pipx()

        self.assertIs(result, python)
        remove_environment.assert_called_once_with(environment)
        builder.create.assert_called_once_with(environment)


if __name__ == "__main__":
    unittest.main()
