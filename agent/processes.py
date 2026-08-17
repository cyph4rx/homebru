from __future__ import annotations

import os
import subprocess


def hidden_window_creation_flags(*, new_process_group: bool = False) -> int:
    """Return Windows flags for a child process that should stay in the background."""
    if os.name != "nt":
        return 0

    flags = subprocess.CREATE_NO_WINDOW
    if new_process_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return flags
