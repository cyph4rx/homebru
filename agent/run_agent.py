from __future__ import annotations

import subprocess
import sys

try:
    from .setup_agent import AGENT_DIR, venv_python
except ImportError:  # Support running this file directly.
    from setup_agent import AGENT_DIR, venv_python


def main() -> None:
    agent_python = venv_python(AGENT_DIR / ".venv")
    if not agent_python.exists():
        print("The agent is not set up yet. Run: python setup_agent.py")
        raise SystemExit(1)
    result = subprocess.run([str(agent_python), str(AGENT_DIR / "main.py"), *sys.argv[1:]])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
